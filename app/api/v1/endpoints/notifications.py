from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.budget import Budget
from app.models.expense import Expense
from app.models.goal import Goal, GoalStatus
from app.models.user import User
from app.schemas.notification import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[Notification])
def get_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Notification]:
    today = date.today()
    year, month = today.year, today.month
    notifications: list[Notification] = []

    # --- Budget alerts ---
    budgets = db.scalars(
        select(Budget).where(Budget.user_id == current_user.id, Budget.year == year, Budget.month == month)
    ).all()

    for budget in budgets:
        spent = float(db.scalar(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.user_id == current_user.id,
                Expense.category == budget.category,
                extract("year", Expense.expense_date) == year,
                extract("month", Expense.expense_date) == month,
            )
        ) or 0)
        limit = float(budget.limit_amount)
        utilization = round((spent / limit) * 100, 1) if limit > 0 else 0

        if spent >= limit:
            notifications.append(Notification(
                type="budget",
                alert="exceeded",
                message=f"{budget.category.value.capitalize()} budget exceeded!",
                detail=f"Spent ₹{spent} of ₹{limit} limit ({utilization}% used)",
            ))
        elif utilization >= 80:
            notifications.append(Notification(
                type="budget",
                alert="warning",
                message=f"{budget.category.value.capitalize()} budget at {utilization}%",
                detail=f"Spent ₹{spent} of ₹{limit} — ₹{round(limit - spent, 2)} remaining",
            ))

    # --- Goal deadline alerts ---
    goals = db.scalars(
        select(Goal).where(Goal.user_id == current_user.id, Goal.status == GoalStatus.active)
    ).all()

    for goal in goals:
        days_left = (goal.target_date - today).days
        progress = round((float(goal.saved_amount) / float(goal.target_amount)) * 100, 1) if goal.target_amount else 0

        if days_left <= 0:
            notifications.append(Notification(
                type="goal",
                alert="exceeded",
                message=f"Goal '{goal.title}' deadline passed!",
                detail=f"Only {progress}% achieved — consider extending the deadline",
            ))
        elif days_left <= 30:
            notifications.append(Notification(
                type="goal",
                alert="warning",
                message=f"Goal '{goal.title}' due in {days_left} days",
                detail=f"{progress}% achieved — ₹{round(float(goal.target_amount) - float(goal.saved_amount), 2)} remaining",
            ))

    # --- High single expense alert (any expense > 5000) ---
    big_expenses = db.scalars(
        select(Expense).where(
            Expense.user_id == current_user.id,
            Expense.amount > 5000,
            extract("year", Expense.expense_date) == year,
            extract("month", Expense.expense_date) == month,
        ).order_by(Expense.amount.desc()).limit(3)
    ).all()

    for exp in big_expenses:
        notifications.append(Notification(
            type="expense",
            alert="warning",
            message=f"Large expense: {exp.title}",
            detail=f"₹{float(exp.amount)} spent on {exp.category.value} on {exp.expense_date.strftime('%d %b %Y')}",
        ))

    # --- Monthly total expense spike (this month > last month by 20%) ---
    this_month_total = float(db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.user_id == current_user.id,
            extract("year", Expense.expense_date) == year,
            extract("month", Expense.expense_date) == month,
        )
    ) or 0)

    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    last_month_total = float(db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.user_id == current_user.id,
            extract("year", Expense.expense_date) == prev_year,
            extract("month", Expense.expense_date) == prev_month,
        )
    ) or 0)

    if last_month_total > 0:
        spike_pct = round(((this_month_total - last_month_total) / last_month_total) * 100, 1)
        if spike_pct >= 20:
            notifications.append(Notification(
                type="expense",
                alert="warning",
                message=f"Spending up {spike_pct}% vs last month!",
                detail=f"This month ₹{this_month_total} vs last month ₹{last_month_total}",
            ))

    # --- Savings alert (no budget set) ---
    if not budgets:
        notifications.append(Notification(
            type="savings",
            alert="info",
            message="No budget set for this month",
            detail="Create monthly budgets to track your spending and get alerts",
        ))

    # sort: exceeded first, then warning, then info
    order = {"exceeded": 0, "warning": 1, "info": 2}
    notifications.sort(key=lambda n: order.get(n.alert, 3))

    return notifications
