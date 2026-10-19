from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.budget import Budget
from app.models.expense import Expense
from app.models.user import User
from app.schemas.budget import BudgetStatus
from app.schemas.dashboard import BudgetOverview, Dashboard, ExpenseSummary, SpendingTrend
from app.schemas.expense import CategorySummary, MonthlySummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _monthly_totals(db: Session, user_id, year: int, month: int) -> MonthlySummary:
    rows = db.execute(
        select(Expense.category, func.sum(Expense.amount), func.count())
        .where(
            Expense.user_id == user_id,
            extract("year", Expense.expense_date) == year,
            extract("month", Expense.expense_date) == month,
        )
        .group_by(Expense.category)
    ).all()
    by_category = [CategorySummary(category=r[0], total=float(r[1]), count=r[2]) for r in rows]
    return MonthlySummary(
        year=year, month=month,
        total=sum(c.total for c in by_category),
        count=sum(c.count for c in by_category),
        by_category=by_category,
    )


def _budget_status(budget: Budget, spent: float) -> BudgetStatus:
    limit = float(budget.limit_amount)
    utilization_pct = round((spent / limit) * 100, 2) if limit > 0 else 0.0
    remaining = max(limit - spent, 0)
    alert = "exceeded" if spent >= limit else "warning" if utilization_pct >= 80 else "ok"
    return BudgetStatus(
        budget_id=budget.id, category=budget.category,
        year=budget.year, month=budget.month,
        limit_amount=limit, spent=spent,
        remaining=remaining, utilization_pct=utilization_pct, alert=alert,
    )


@router.get("", response_model=Dashboard)
def get_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    year: Annotated[int, Query()] = date.today().year,
    month: Annotated[int, Query(ge=1, le=12)] = date.today().month,
) -> Dashboard:
    uid = current_user.id

    # --- expense summary ---
    this = _monthly_totals(db, uid, year, month)
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    last = _monthly_totals(db, uid, prev_year, prev_month)
    mom_change = round(((this.total - last.total) / last.total) * 100, 2) if last.total > 0 else 0.0
    top_cat = max(this.by_category, key=lambda c: c.total).category if this.by_category else None

    expense_summary = ExpenseSummary(
        total_this_month=this.total,
        total_last_month=last.total,
        month_over_month_change_pct=mom_change,
        top_category=top_cat,
        this_month=this,
    )

    # --- budget overview ---
    budgets = db.scalars(
        select(Budget).where(Budget.user_id == uid, Budget.year == year, Budget.month == month)
    ).all()

    spent_map = {}
    if budgets:
        rows = db.execute(
            select(Expense.category, func.sum(Expense.amount))
            .where(
                Expense.user_id == uid,
                extract("year", Expense.expense_date) == year,
                extract("month", Expense.expense_date) == month,
            )
            .group_by(Expense.category)
        ).all()
        spent_map = {r[0]: float(r[1]) for r in rows}

    statuses = [_budget_status(b, spent_map.get(b.category, 0.0)) for b in budgets]
    alerts = sorted([s for s in statuses if s.alert != "ok"], key=lambda x: x.utilization_pct, reverse=True)
    total_limit = sum(s.limit_amount for s in statuses)
    total_spent = sum(s.spent for s in statuses)

    budget_overview = BudgetOverview(
        total_budgets=len(statuses),
        exceeded=sum(1 for s in statuses if s.alert == "exceeded"),
        warning=sum(1 for s in statuses if s.alert == "warning"),
        ok=sum(1 for s in statuses if s.alert == "ok"),
        total_limit=total_limit,
        total_spent=total_spent,
        overall_utilization_pct=round((total_spent / total_limit) * 100, 2) if total_limit > 0 else 0.0,
        alerts=alerts,
    )

    # --- spending trend (last 6 months) ---
    trend_rows = db.execute(
        select(
            extract("year", Expense.expense_date).label("y"),
            extract("month", Expense.expense_date).label("m"),
            func.sum(Expense.amount),
        )
        .where(Expense.user_id == uid)
        .group_by("y", "m")
        .order_by("y", "m")
        .limit(6)
    ).all()
    spending_trend = [SpendingTrend(year=int(r[0]), month=int(r[1]), total=float(r[2])) for r in trend_rows]

    # --- all-time category breakdown ---
    cat_rows = db.execute(
        select(Expense.category, func.sum(Expense.amount), func.count())
        .where(Expense.user_id == uid)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
    ).all()
    category_breakdown = [CategorySummary(category=r[0], total=float(r[1]), count=r[2]) for r in cat_rows]

    return Dashboard(
        year=year, month=month,
        expense_summary=expense_summary,
        budget_overview=budget_overview,
        spending_trend=spending_trend,
        category_breakdown=category_breakdown,
    )
