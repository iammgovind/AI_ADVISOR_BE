from pydantic import BaseModel

from app.schemas.expense import CategorySummary, MonthlySummary
from app.schemas.budget import BudgetStatus


class ExpenseSummary(BaseModel):
    total_this_month: float
    total_last_month: float
    month_over_month_change_pct: float
    top_category: str | None
    this_month: MonthlySummary


class BudgetOverview(BaseModel):
    total_budgets: int
    exceeded: int
    warning: int
    ok: int
    total_limit: float
    total_spent: float
    overall_utilization_pct: float
    alerts: list[BudgetStatus]  # only exceeded + warning


class SpendingTrend(BaseModel):
    year: int
    month: int
    total: float


class Dashboard(BaseModel):
    year: int
    month: int
    expense_summary: ExpenseSummary
    budget_overview: BudgetOverview
    spending_trend: list[SpendingTrend]   # last 6 months
    category_breakdown: list[CategorySummary]  # all-time top categories
