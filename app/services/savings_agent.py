from datetime import date
from math import ceil

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.models.expense import Expense
from app.models.goal import Goal, GoalStatus


def _suggest_goal_timeline(remaining: float, savings_capacity: float, today: date) -> dict:
    """For an at-risk goal, suggest realistic achievement date with and without salary growth."""
    if savings_capacity <= 0:
        return {
            "realistic_date": None,
            "optimistic_date": None,
            "message": "⚠️ No savings capacity currently. Reduce expenses to start working toward this goal.",
        }

    # --- flat savings: how many months at current capacity ---
    flat_months = ceil(remaining / savings_capacity)
    flat_date = date(
        today.year + (today.month - 1 + flat_months) // 12,
        (today.month - 1 + flat_months) % 12 + 1,
        1,
    )

    # --- with 10% annual growth: simulate month by month ---
    accumulated = 0.0
    monthly = savings_capacity
    optimistic_months = 0
    for m in range(1, 361):  # cap at 30 years
        if m > 1 and (m - 1) % 12 == 0:
            monthly = round(monthly * 1.10, 2)  # 10% raise each year
        accumulated += monthly
        optimistic_months = m
        if accumulated >= remaining:
            break

    optimistic_date = date(
        today.year + (today.month - 1 + optimistic_months) // 12,
        (today.month - 1 + optimistic_months) % 12 + 1,
        1,
    )

    message = (
        f"💡 With your current savings of ₹{savings_capacity:,.0f}/month, you can achieve this goal by "
        f"{flat_date.strftime('%b %Y')}. "
        f"If your income grows 10% each year, you could reach it as early as {optimistic_date.strftime('%b %Y')}."
    )

    return {
        "realistic_date": str(flat_date),
        "optimistic_date": str(optimistic_date),
        "message": message,
    }


def plan_savings(db: Session, user_id) -> dict:
    today = date.today()
    year, month = today.year, today.month

    # --- monthly expense ---
    monthly_expense = float(db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.user_id == user_id,
            extract("year", Expense.expense_date) == year,
            extract("month", Expense.expense_date) == month,
        )
    ) or 0)

    # --- total budget ---
    budgets = db.scalars(
        select(Budget).where(Budget.user_id == user_id, Budget.year == year, Budget.month == month)
    ).all()
    total_budget = sum(float(b.limit_amount) for b in budgets)

    # --- savings capacity ---
    savings_capacity = round(total_budget - monthly_expense, 2)
    savings_rate_pct = round((savings_capacity / total_budget) * 100, 1) if total_budget > 0 else 0

    # --- emergency fund ---
    emergency_fund_target = round(monthly_expense * 6, 2)
    emergency_fund_status = "sufficient" if savings_capacity >= monthly_expense else "insufficient"

    # --- last 3 months avg expense ---
    trend = db.execute(
        select(func.sum(Expense.amount))
        .where(Expense.user_id == user_id)
        .group_by(
            extract("year", Expense.expense_date),
            extract("month", Expense.expense_date),
        )
        .order_by(
            extract("year", Expense.expense_date).desc(),
            extract("month", Expense.expense_date).desc(),
        )
        .limit(3)
    ).scalars().all()
    avg_monthly_expense = round(sum(float(t) for t in trend) / len(trend), 2) if trend else monthly_expense

    # --- goal-based saving plans ---
    goals = db.scalars(
        select(Goal).where(Goal.user_id == user_id, Goal.status == GoalStatus.active)
    ).all()

    goal_plans = []
    total_monthly_needed = 0.0
    for g in goals:
        target = float(g.target_amount)
        saved = float(g.saved_amount)
        remaining = max(target - saved, 0)
        days_left = max((g.target_date - today).days, 1)
        months_left = max(round(days_left / 30, 1), 1)
        monthly_needed = round(remaining / months_left, 2)
        total_monthly_needed += monthly_needed
        feasible = monthly_needed <= savings_capacity
        plan = {
            "goal_id": str(g.id),
            "title": g.title,
            "target_amount": target,
            "saved_amount": saved,
            "remaining_amount": remaining,
            "progress_pct": round((saved / target) * 100, 1) if target > 0 else 0,
            "target_date": str(g.target_date),
            "months_left": months_left,
            "monthly_saving_needed": monthly_needed,
            "feasible": feasible,
            "status": "on_track" if feasible else "at_risk",
        }
        if not feasible:
            plan["suggestion"] = _suggest_goal_timeline(remaining, savings_capacity, today)
        goal_plans.append(plan)

    # sort by priority — at_risk first, then by monthly needed desc
    goal_plans.sort(key=lambda x: (x["status"] == "on_track", -x["monthly_saving_needed"]))

    # --- allocation suggestion ---
    allocatable = max(savings_capacity, 0)
    emergency_monthly = round(monthly_expense * 0.1, 2)  # 10% of expense toward emergency
    investable = max(round(allocatable - total_monthly_needed - emergency_monthly, 2), 0)

    # --- recommendations ---
    recommendations = []
    if savings_capacity <= 0:
        recommendations.append("⚠️ No savings capacity — reduce monthly expenses immediately")
    elif savings_rate_pct < 10:
        recommendations.append("⚠️ Savings rate below 10% — aim for at least 20%")
    elif savings_rate_pct < 20:
        recommendations.append("💡 Savings rate is low — try to reach 20% by cutting discretionary spending")
    else:
        recommendations.append("✅ Good savings rate — keep it consistent")

    if total_monthly_needed > savings_capacity:
        recommendations.append(f"⚠️ Goals need ₹{total_monthly_needed}/month but only ₹{savings_capacity} available — extend goal deadlines or reduce targets")
    elif total_monthly_needed > 0:
        recommendations.append(f"✅ All goals are achievable with ₹{total_monthly_needed}/month allocation")

    if investable > 0:
        recommendations.append(f"💰 ₹{investable}/month available for investments after goals and emergency fund")
    else:
        recommendations.append("📌 Focus on goals and emergency fund before investing")

    return {
        "savings_capacity": savings_capacity,
        "savings_rate_pct": savings_rate_pct,
        "monthly_expense": monthly_expense,
        "avg_monthly_expense_3m": avg_monthly_expense,
        "total_budget": total_budget,
        "emergency_fund": {
            "target": emergency_fund_target,
            "monthly_contribution_suggested": emergency_monthly,
            "months_to_build": round(emergency_fund_target / emergency_monthly, 1) if emergency_monthly > 0 else 0,
            "status": emergency_fund_status,
        },
        "goal_plans": goal_plans,
        "monthly_allocation": {
            "goals": round(total_monthly_needed, 2),
            "emergency_fund": emergency_monthly,
            "investable_surplus": investable,
            "total_allocated": round(total_monthly_needed + emergency_monthly, 2),
        },
        "recommendations": recommendations,
    }
