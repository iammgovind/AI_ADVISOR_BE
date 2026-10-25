import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.bank_account import BankAccount
from app.models.expense import Expense
from app.models.statement_upload import StatementUpload
from app.models.user import User
from app.schemas.statement import (
    BulkApproveRequest,
    BulkApproveResult,
    ParsedTransaction,
    StatementPreview,
    StatementUploadOut,
)
from app.services.statement_parser import parse_statement, suggest_category

router = APIRouter(prefix="/expenses/statement", tags=["statement"])


def _match_account(db: Session, user_id, account_number: str | None, bank_name: str | None) -> BankAccount | None:
    """Match pre-registered account by last 4 digits, or fallback by bank name."""
    accounts = list(db.scalars(select(BankAccount).where(BankAccount.user_id == user_id)).all())
    if not accounts:
        return None

    # 1. exact last-4 digit match (strip all non-digits first)
    if account_number:
        digits_from_statement = re.sub(r"\D", "", account_number)
        for acc in accounts:
            digits_registered = re.sub(r"\D", "", acc.account_number)
            if len(digits_from_statement) >= 4 and len(digits_registered) >= 4:
                if digits_registered[-4:] == digits_from_statement[-4:]:
                    return acc

    # 2. fallback: match by bank name if only one account registered for that bank
    if bank_name:
        bank_matches = [a for a in accounts if bank_name.lower() in a.bank_name.lower() or a.bank_name.lower() in bank_name.lower()]
        if len(bank_matches) == 1:
            return bank_matches[0]

    # 3. fallback: if user has only one registered account, match it
    if len(accounts) == 1:
        return accounts[0]

    return None


@router.post("/upload", response_model=StatementPreview)
async def upload_statement(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile | None = File(default=None),
    raw_text: str | None = Form(default=None),
) -> StatementPreview:
    # determine source
    if file and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
        source = "pdf" if ext == "pdf" else "csv"
        file_bytes = await file.read()
        account_info, transactions = parse_statement(source, file_bytes=file_bytes)
        filename = file.filename
    elif raw_text:
        source = "text"
        account_info, transactions = parse_statement(source, raw_text=raw_text)
        filename = None
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide a file or raw_text")

    if not transactions:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No debit transactions found in statement")

    # account verification
    matched = _match_account(db, current_user.id, account_info.get("account_number"), account_info.get("bank_name"))

    # save upload record
    upload = StatementUpload(
        user_id=current_user.id,
        bank_account_id=matched.id if matched else None,
        source=source,
        filename=filename,
        total_transactions=len(transactions),
        status="pending",
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    # build parsed transaction list with suggested categories
    parsed = [
        ParsedTransaction(
            row_index=i,
            date=t["date"],
            description=t["description"],
            amount=t["amount"],
            suggested_category=suggest_category(t["description"])[0],
            confidence=suggest_category(t["description"])[1],
        )
        for i, t in enumerate(transactions)
    ]

    return StatementPreview(
        upload_id=upload.id,
        bank_name=account_info.get("bank_name") or (matched.bank_name if matched else None),
        account_number=account_info.get("account_number"),
        account_holder=account_info.get("account_holder") or (matched.account_holder if matched else None),
        matched_account_id=matched.id if matched else None,
        account_verified=matched is not None,
        total_debits=len(parsed),
        transactions=parsed,
    )


@router.post("/bulk-approve", response_model=BulkApproveResult)
def bulk_approve(
    payload: BulkApproveRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BulkApproveResult:
    upload = db.scalar(
        select(StatementUpload).where(
            StatementUpload.id == payload.upload_id,
            StatementUpload.user_id == current_user.id,
        )
    )
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

    for txn in payload.approved:
        expense = Expense(
            user_id=current_user.id,
            title=txn.description[:255],
            amount=txn.amount,
            category=txn.category,
            expense_date=txn.date,
            note="Imported from bank statement",
        )
        db.add(expense)

    upload.approved_count = len(payload.approved)
    upload.rejected_count = len(payload.rejected_indices)
    upload.status = "completed"
    db.commit()

    return BulkApproveResult(saved=len(payload.approved), rejected=len(payload.rejected_indices))


@router.get("/history", response_model=list[StatementUploadOut])
def upload_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[StatementUpload]:
    return list(
        db.scalars(
            select(StatementUpload)
            .where(StatementUpload.user_id == current_user.id)
            .order_by(StatementUpload.created_at.desc())
        ).all()
    )
