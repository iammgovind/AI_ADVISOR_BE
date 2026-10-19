from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.expense import Expense, ExpenseCategory
from app.models.user import User
from app.schemas.expense import CategorySummary, ExpenseCreate, ExpenseOut, ExpenseUpdate, MonthlySummary

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _get_or_404(db: Session, expense_id: UUID, user_id: UUID) -> Expense:
    expense = db.scalar(select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id))
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    return expense


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = Expense(**payload.model_dump(), user_id=current_user.id)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    category: Annotated[ExpenseCategory | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Expense]:
    q = select(Expense).where(Expense.user_id == current_user.id)
    if category:
        q = q.where(Expense.category == category)
    q = q.order_by(Expense.expense_date.desc()).offset(skip).limit(limit)
    return list(db.scalars(q).all())


@router.get("/summary/monthly", response_model=MonthlySummary)
def monthly_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Annotated[int, Query()],
    month: Annotated[int, Query(ge=1, le=12)],
) -> MonthlySummary:
    base = select(Expense).where(
        Expense.user_id == current_user.id,
        extract("year", Expense.expense_date) == year,
        extract("month", Expense.expense_date) == month,
    )

    totals = db.execute(
        select(Expense.category, func.sum(Expense.amount), func.count())
        .where(
            Expense.user_id == current_user.id,
            extract("year", Expense.expense_date) == year,
            extract("month", Expense.expense_date) == month,
        )
        .group_by(Expense.category)
    ).all()

    by_category = [CategorySummary(category=row[0], total=float(row[1]), count=row[2]) for row in totals]
    total = sum(c.total for c in by_category)
    count = sum(c.count for c in by_category)

    return MonthlySummary(year=year, month=month, total=total, count=count, by_category=by_category)


@router.get("/summary/analytics", response_model=list[CategorySummary])
def analytics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CategorySummary]:
    rows = db.execute(
        select(Expense.category, func.sum(Expense.amount), func.count())
        .where(Expense.user_id == current_user.id)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
    ).all()
    return [CategorySummary(category=row[0], total=float(row[1]), count=row[2]) for row in rows]


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(
    expense_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    return _get_or_404(db, expense_id, current_user.id)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: UUID,
    payload: ExpenseUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_or_404(db, expense_id, current_user.id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    expense = _get_or_404(db, expense_id, current_user.id)
    db.delete(expense)
    db.commit()
