from sqlalchemy.orm import Session

from app.services.risk_agent import assess_risk
from app.services.savings_agent import plan_savings
from app.services.agent import _build_financial_profile


def _budget_agent(savings: dict) -> dict:
    util = savings["monthly_expense"] / savings["total_budget"] * 100 if savings["total_budget"] > 0 else 0
    if util == 0:
        status, alert = "no_budget", "⚠️ No budget set — create monthly budgets for each category"
    elif util > 100:
        status, alert = "exceeded", f"🚨 Budget exceeded by {round(util - 100, 1)}% — immediate action needed"
    elif util > 80:
        status, alert = "warning", f"⚠️ Budget {round(util, 1)}% used — approaching limit"
    else:
        status, alert = "ok", f"✅ Budget utilization {round(util, 1)}% — healthy"
    return {"utilization_pct": round(util, 1), "status": status, "alert": alert}


def _investment_agent(profile: dict) -> dict:
    portfolio = profile["portfolio"]
    total_invested = portfolio["total_invested"]
    pl_pct = portfolio["profit_loss_pct"]
    holdings = portfolio["total_holdings"]
    by_type = portfolio["by_type"]

    if holdings == 0:
        status = "not_started"
        insight = "⚠️ No investments yet — start with a small SIP in Nifty 50 Index Fund"
    elif pl_pct >= 15:
        status = "excellent"
        insight = f"✅ Portfolio up {pl_pct}% — excellent performance, consider rebalancing"
    elif pl_pct >= 5:
        status = "good"
        insight = f"✅ Portfolio up {pl_pct}% — good returns, stay invested"
    elif pl_pct >= 0:
        status = "neutral"
        insight = f"💡 Portfolio up {pl_pct}% — moderate returns, review holdings"
    else:
        status = "loss"
        insight = f"🚨 Portfolio down {abs(pl_pct)}% — review and rebalance"

    diversification = "well_diversified" if len(by_type) >= 3 else "needs_diversification" if len(by_type) >= 2 else "not_diversified"

    return {
        "status": status,
        "total_invested": total_invested,
        "current_value": portfolio["current_value"],
        "profit_loss_pct": pl_pct,
        "total_holdings": holdings,
        "diversification": diversification,
        "insight": insight,
    }


def _generate_recommendations(risk: dict, savings: dict, budget: dict, investment: dict) -> list[dict]:
    recs = []
    priority = 1

    # critical — budget exceeded
    if budget["status"] == "exceeded":
        recs.append({
            "priority": priority,
            "category": "budget",
            "urgency": "critical",
            "action": "Reduce monthly expenses immediately",
            "detail": budget["alert"],
        })
        priority += 1

    # no savings
    if savings["savings_capacity"] <= 0:
        recs.append({
            "priority": priority,
            "category": "savings",
            "urgency": "critical",
            "action": "Cut expenses to create savings capacity",
            "detail": f"Currently spending ₹{abs(savings['savings_capacity'])} more than budget",
        })
        priority += 1

    # no investments
    if investment["status"] == "not_started":
        recs.append({
            "priority": priority,
            "category": "investment",
            "urgency": "high",
            "action": "Start investing immediately",
            "detail": f"Based on your {risk['risk_level']} risk profile, start with: {risk['suitable_investments'][0]}",
        })
        priority += 1

    # at-risk goals
    at_risk_goals = [g for g in savings["goal_plans"] if g["status"] == "at_risk"]
    for g in at_risk_goals:
        recs.append({
            "priority": priority,
            "category": "goals",
            "urgency": "high",
            "action": f"Increase savings for goal: {g['title']}",
            "detail": f"Need ₹{g['monthly_saving_needed']}/month — extend deadline or reduce target",
        })
        priority += 1

    # emergency fund
    if savings["emergency_fund"]["status"] == "insufficient":
        recs.append({
            "priority": priority,
            "category": "emergency_fund",
            "urgency": "medium",
            "action": "Build emergency fund",
            "detail": f"Target ₹{savings['emergency_fund']['target']} — save ₹{savings['emergency_fund']['monthly_contribution_suggested']}/month",
        })
        priority += 1

    # diversification
    if investment["diversification"] == "not_diversified" and investment["status"] != "not_started":
        recs.append({
            "priority": priority,
            "category": "investment",
            "urgency": "medium",
            "action": "Diversify portfolio",
            "detail": f"Add {risk['recommended_allocation']} allocation across asset classes",
        })
        priority += 1

    # investable surplus
    if savings["monthly_allocation"]["investable_surplus"] > 0:
        recs.append({
            "priority": priority,
            "category": "investment",
            "urgency": "low",
            "action": f"Invest surplus ₹{savings['monthly_allocation']['investable_surplus']}/month",
            "detail": f"Suitable for your {risk['risk_level']} profile: {', '.join(risk['suitable_investments'][:2])}",
        })
        priority += 1

    return recs


def run_multi_agent(db: Session, user_id) -> dict:
    # run all agents
    risk = assess_risk(db, user_id)
    savings = plan_savings(db, user_id)
    profile = _build_financial_profile(db, user_id)
    budget = _budget_agent(savings)
    investment = _investment_agent(profile)

    # overall financial health score
    health_score = round((
        (min(risk["risk_score"], 100) * 0.25) +
        (min(max(savings["savings_rate_pct"], 0), 100) * 0.25) +
        (max(100 - budget["utilization_pct"], 0) * 0.25) +
        (min(max(investment["profit_loss_pct"] + 50, 0), 100) * 0.25)
    ), 1)

    if health_score >= 75:
        health_status = "excellent"
    elif health_score >= 50:
        health_status = "good"
    elif health_score >= 25:
        health_status = "needs_improvement"
    else:
        health_status = "critical"

    recommendations = _generate_recommendations(risk, savings, budget, investment)

    return {
        "financial_health_score": health_score,
        "financial_health_status": health_status,
        "agents": {
            "risk": {
                "risk_score": risk["risk_score"],
                "risk_level": risk["risk_level"],
                "recommended_allocation": risk["recommended_allocation"],
                "suitable_investments": risk["suitable_investments"],
                "warnings": risk["warnings"],
            },
            "savings": {
                "savings_capacity": savings["savings_capacity"],
                "savings_rate_pct": savings["savings_rate_pct"],
                "emergency_fund": savings["emergency_fund"],
                "monthly_allocation": savings["monthly_allocation"],
                "goal_plans": savings["goal_plans"],
            },
            "budget": budget,
            "investment": investment,
        },
        "recommendations": recommendations,
    }
