from datetime import date

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.models.expense import Expense
from app.models.goal import Goal, GoalStatus
from app.models.investment import Investment, InvestmentStatus


def _get_risk_profile(db: Session, user_id) -> dict:
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
    budget_utilization = round((monthly_expense / total_budget) * 100, 1) if total_budget > 0 else 0

    # --- goals ---
    goals = db.scalars(
        select(Goal).where(Goal.user_id == user_id, Goal.status == GoalStatus.active)
    ).all()
    total_goals = len(goals)
    avg_goal_progress = round(
        sum((float(g.saved_amount) / float(g.target_amount)) * 100 for g in goals if g.target_amount) / total_goals, 1
    ) if total_goals > 0 else 0

    # --- investments ---
    investments = db.scalars(
        select(Investment).where(Investment.user_id == user_id, Investment.status == InvestmentStatus.active)
    ).all()
    total_invested = sum(float(i.quantity) * float(i.buy_price) for i in investments)
    current_value = sum(float(i.quantity) * float(i.current_price) for i in investments)
    portfolio_pl_pct = round(((current_value - total_invested) / total_invested) * 100, 2) if total_invested > 0 else 0

    inv_types = list({i.investment_type.value for i in investments})
    has_high_risk = any(t in ["stock", "crypto", "etf"] for t in inv_types)
    has_low_risk = any(t in ["fd", "bond"] for t in inv_types)

    # --- expense trend (last 3 months) ---
    trend = db.execute(
        select(
            extract("year", Expense.expense_date).label("y"),
            extract("month", Expense.expense_date).label("m"),
            func.sum(Expense.amount),
        )
        .where(Expense.user_id == user_id)
        .group_by("y", "m")
        .order_by("y", "m")
        .limit(3)
    ).all()
    expense_trend = [float(r[2]) for r in trend]
    expense_growing = len(expense_trend) >= 2 and expense_trend[-1] > expense_trend[0]

    return {
        "monthly_expense": monthly_expense,
        "total_budget": total_budget,
        "budget_utilization": budget_utilization,
        "total_goals": total_goals,
        "avg_goal_progress": avg_goal_progress,
        "total_invested": round(total_invested, 2),
        "current_value": round(current_value, 2),
        "portfolio_pl_pct": portfolio_pl_pct,
        "investment_types": inv_types,
        "has_high_risk_assets": has_high_risk,
        "has_low_risk_assets": has_low_risk,
        "total_holdings": len(investments),
        "expense_growing": expense_growing,
    }


def _score_risk(profile: dict) -> dict:
    score = 0
    breakdown = {}

    # 1. Budget discipline (0-25)
    util = profile["budget_utilization"]
    if util == 0:
        b_score = 10  # no budget set
    elif util <= 70:
        b_score = 25
    elif util <= 90:
        b_score = 18
    elif util <= 100:
        b_score = 10
    else:
        b_score = 0
    breakdown["budget_discipline"] = b_score
    score += b_score

    # 2. Investment behavior (0-25)
    holdings = profile["total_holdings"]
    if holdings == 0:
        i_score = 5
    elif holdings <= 2:
        i_score = 12
    elif holdings <= 5:
        i_score = 20
    else:
        i_score = 25
    breakdown["investment_behavior"] = i_score
    score += i_score

    # 3. Goal commitment (0-25)
    goals = profile["total_goals"]
    progress = profile["avg_goal_progress"]
    if goals == 0:
        g_score = 5
    elif progress >= 50:
        g_score = 25
    elif progress >= 25:
        g_score = 15
    else:
        g_score = 8
    breakdown["goal_commitment"] = g_score
    score += g_score

    # 4. Portfolio diversity (0-25)
    types = len(profile["investment_types"])
    has_high = profile["has_high_risk_assets"]
    has_low = profile["has_low_risk_assets"]
    if types == 0:
        d_score = 5
    elif types == 1:
        d_score = 10
    elif types >= 2 and has_high and has_low:
        d_score = 25
    elif types >= 2:
        d_score = 18
    else:
        d_score = 12
    breakdown["portfolio_diversity"] = d_score
    score += d_score

    return {"total_score": score, "breakdown": breakdown}


def _determine_risk_level(score: int, profile: dict) -> dict:
    if score >= 75:
        level = "aggressive"
        description = "You have strong financial discipline and active investment behavior. You can handle high-risk, high-return investments."
        suitable_investments = ["Small Cap Funds", "Mid Cap Funds", "Direct Stocks", "Crypto (small %)", "Sectoral ETFs"]
        allocation = {"equity": 70, "debt": 15, "gold": 10, "cash": 5}
        avoid = ["Keeping large cash idle", "Only FDs"]
    elif score >= 50:
        level = "moderate"
        description = "You have decent financial habits with room for improvement. Balanced investments suit you best."
        suitable_investments = ["Large Cap Funds", "Balanced Advantage Funds", "Nifty 50 Index Fund", "Corporate Bonds", "Gold ETF"]
        allocation = {"equity": 50, "debt": 30, "gold": 15, "cash": 5}
        avoid = ["High-risk crypto", "Penny stocks", "Leveraged products"]
    else:
        level = "conservative"
        description = "Your financial foundation needs strengthening. Focus on stability and building an emergency fund first."
        suitable_investments = ["PPF", "Fixed Deposits", "Liquid Funds", "Government Bonds", "Nifty 50 Index Fund (small SIP)"]
        allocation = {"equity": 20, "debt": 50, "gold": 10, "cash": 20}
        avoid = ["Direct stocks", "Crypto", "Small/Mid cap funds", "Leveraged products"]

    warnings = []
    if profile["budget_utilization"] > 100:
        warnings.append("Spending exceeds budget — reduce expenses before investing")
    if profile["total_holdings"] == 0:
        warnings.append("No investments yet — start with a small SIP immediately")
    if profile["total_goals"] == 0:
        warnings.append("No financial goals set — define goals to stay motivated")
    if profile["expense_growing"]:
        warnings.append("Expenses are growing month over month — review spending habits")
    if not profile["has_low_risk_assets"] and profile["has_high_risk_assets"]:
        warnings.append("Portfolio has only high-risk assets — add debt/FD for stability")

    return {
        "risk_level": level,
        "description": description,
        "suitable_investments": suitable_investments,
        "recommended_allocation": allocation,
        "warnings": warnings,
    }


def assess_risk(db: Session, user_id) -> dict:
    profile = _get_risk_profile(db, user_id)
    scored = _score_risk(profile)
    risk = _determine_risk_level(scored["total_score"], profile)

    return {
        "risk_score": scored["total_score"],
        "score_breakdown": scored["breakdown"],
        "risk_level": risk["risk_level"],
        "description": risk["description"],
        "suitable_investments": risk["suitable_investments"],
        "recommended_allocation": risk["recommended_allocation"],
        "warnings": risk["warnings"],
        "profile_summary": {
            "monthly_expense": profile["monthly_expense"],
            "total_budget": profile["total_budget"],
            "budget_utilization_pct": profile["budget_utilization"],
            "total_goals": profile["total_goals"],
            "avg_goal_progress_pct": profile["avg_goal_progress"],
            "total_holdings": profile["total_holdings"],
            "portfolio_pl_pct": profile["portfolio_pl_pct"],
            "investment_types": profile["investment_types"],
        },
    }
