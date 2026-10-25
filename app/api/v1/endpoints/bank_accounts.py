from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.bank_account import BankAccount
from app.models.user import User
from app.schemas.bank_account import BankAccountCreate, BankAccountOut

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])


@router.post("", response_model=BankAccountOut, status_code=status.HTTP_201_CREATED)
def register_bank_account(
    payload: BankAccountCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BankAccount:
    account = BankAccount(**payload.model_dump(), user_id=current_user.id)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("", response_model=list[BankAccountOut])
def list_bank_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[BankAccount]:
    return list(db.scalars(select(BankAccount).where(BankAccount.user_id == current_user.id)).all())


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bank_account(
    account_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    account = db.scalar(select(BankAccount).where(BankAccount.id == account_id, BankAccount.user_id == current_user.id))
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank account not found")
    db.delete(account)
    db.commit()
