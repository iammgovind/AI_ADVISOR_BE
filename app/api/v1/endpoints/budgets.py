from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.budget import Budget
from app.models.expense import Expense
from app.models.user import User
from app.schemas.budget import BudgetCreate, BudgetOut, BudgetStatus, BudgetUpdate

router = APIRouter(prefix="/budgets", tags=["budgets"])

WARNING_THRESHOLD = 80.0  # %


def _get_or_404(db: Session, budget_id: UUID, user_id: UUID) -> Budget:
    budget = db.scalar(select(Budget).where(Budget.id == budget_id, Budget.user_id == user_id))
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


def _spent_for(db: Session, user_id: UUID, category: str, year: int, month: int) -> float:
    result = db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.user_id == user_id,
            Expense.category == category,
            extract("year", Expense.expense_date) == year,
            extract("month", Expense.expense_date) == month,
        )
    )
    return float(result or 0)


def _to_status(budget: Budget, spent: float) -> BudgetStatus:
    limit = float(budget.limit_amount)
    remaining = max(limit - spent, 0)
    utilization_pct = round((spent / limit) * 100, 2) if limit > 0 else 0.0
    if spent >= limit:
        alert = "exceeded"
    elif utilization_pct >= WARNING_THRESHOLD:
        alert = "warning"
    else:
        alert = "ok"
    return BudgetStatus(
        budget_id=budget.id,
        category=budget.category,
        year=budget.year,
        month=budget.month,
        limit_amount=limit,
        spent=spent,
        remaining=remaining,
        utilization_pct=utilization_pct,
        alert=alert,
    )


@router.post("", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Budget:
    existing = db.scalar(
        select(Budget).where(
            Budget.user_id == current_user.id,
            Budget.category == payload.category,
            Budget.year == payload.year,
            Budget.month == payload.month,
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Budget already exists for this category/month")
    budget = Budget(**payload.model_dump(), user_id=current_user.id)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("", response_model=list[BudgetOut])
def list_budgets(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Annotated[int | None, Query()] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
) -> list[Budget]:
    q = select(Budget).where(Budget.user_id == current_user.id)
    if year:
        q = q.where(Budget.year == year)
    if month:
        q = q.where(Budget.month == month)
    return list(db.scalars(q.order_by(Budget.year.desc(), Budget.month.desc())).all())


@router.get("/status", response_model=list[BudgetStatus])
def budget_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Annotated[int, Query()],
    month: Annotated[int, Query(ge=1, le=12)],
) -> list[BudgetStatus]:
    budgets = db.scalars(
        select(Budget).where(
            Budget.user_id == current_user.id,
            Budget.year == year,
            Budget.month == month,
        )
    ).all()

    result = []
    for budget in budgets:
        spent = _spent_for(db, current_user.id, budget.category, year, month)
        result.append(_to_status(budget, spent))

    result.sort(key=lambda x: x.utilization_pct, reverse=True)
    return result


@router.get("/{budget_id}", response_model=BudgetOut)
def get_budget(
    budget_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Budget:
    return _get_or_404(db, budget_id, current_user.id)


@router.get("/{budget_id}/status", response_model=BudgetStatus)
def get_budget_status(
    budget_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BudgetStatus:
    budget = _get_or_404(db, budget_id, current_user.id)
    spent = _spent_for(db, current_user.id, budget.category, budget.year, budget.month)
    return _to_status(budget, spent)


@router.patch("/{budget_id}", response_model=BudgetOut)
def update_budget(
    budget_id: UUID,
    payload: BudgetUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Budget:
    budget = _get_or_404(db, budget_id, current_user.id)
    budget.limit_amount = payload.limit_amount
    db.commit()
    db.refresh(budget)
    return budget


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    budget = _get_or_404(db, budget_id, current_user.id)
    db.delete(budget)
    db.commit()
