from datetime import date

import yfinance as yf
from google import genai
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.budget import Budget
from app.models.expense import Expense
from app.models.goal import Goal, GoalStatus
from app.models.investment import Investment, InvestmentStatus


def get_market_data(symbol: str) -> dict:
    ticker = yf.Ticker(symbol)
    info = ticker.info
    hist = ticker.history(period="1mo")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or (
        float(hist["Close"].iloc[-1]) if not hist.empty else None
    )
    prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
    change_pct = round(((current_price - prev_close) / prev_close) * 100, 2) if current_price and prev_close else None
    return {
        "symbol": symbol.upper(),
        "name": info.get("longName") or info.get("shortName", symbol),
        "current_price": current_price,
        "previous_close": prev_close,
        "change_pct": change_pct,
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "currency": info.get("currency", "INR"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }


def _build_financial_profile(db: Session, user_id) -> dict:
    today = date.today()
    year, month = today.year, today.month

    # monthly expenses
    monthly_expense = db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.user_id == user_id,
            extract("year", Expense.expense_date) == year,
            extract("month", Expense.expense_date) == month,
        )
    ) or 0

    # expense by category
    cat_rows = db.execute(
        select(Expense.category, func.sum(Expense.amount))
        .where(Expense.user_id == user_id)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
    ).all()
    top_categories = [{"category": r[0], "total": float(r[1])} for r in cat_rows[:3]]

    # budgets
    budgets = db.scalars(
        select(Budget).where(Budget.user_id == user_id, Budget.year == year, Budget.month == month)
    ).all()
    total_budget = sum(float(b.limit_amount) for b in budgets)

    # active goals
    goals = db.scalars(
        select(Goal).where(Goal.user_id == user_id, Goal.status == GoalStatus.active)
    ).all()
    goals_data = [
        {
            "title": g.title,
            "target": float(g.target_amount),
            "saved": float(g.saved_amount),
            "progress_pct": round((float(g.saved_amount) / float(g.target_amount)) * 100, 1) if g.target_amount else 0,
            "target_date": str(g.target_date),
        }
        for g in goals
    ]

    # portfolio
    investments = db.scalars(
        select(Investment).where(Investment.user_id == user_id, Investment.status == InvestmentStatus.active)
    ).all()
    total_invested = sum(float(i.quantity) * float(i.buy_price) for i in investments)
    current_value = sum(float(i.quantity) * float(i.current_price) for i in investments)
    portfolio_pl = round(current_value - total_invested, 2)
    inv_by_type: dict = {}
    for inv in investments:
        t = inv.investment_type.value
        inv_by_type[t] = inv_by_type.get(t, 0) + float(inv.quantity) * float(inv.current_price)

    return {
        "monthly_expense": float(monthly_expense),
        "total_budget": total_budget,
        "budget_utilization_pct": round((float(monthly_expense) / total_budget) * 100, 1) if total_budget > 0 else 0,
        "top_expense_categories": top_categories,
        "active_goals": goals_data,
        "portfolio": {
            "total_invested": round(total_invested, 2),
            "current_value": round(current_value, 2),
            "profit_loss": portfolio_pl,
            "profit_loss_pct": round((portfolio_pl / total_invested) * 100, 2) if total_invested > 0 else 0,
            "by_type": inv_by_type,
            "total_holdings": len(investments),
        },
    }


def _call_gemini(prompt: str) -> str:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    for model in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return response.text
        except Exception:
            continue
    return "AI service temporarily unavailable. Please try again later."


def get_portfolio_insights(db: Session, user_id) -> dict:
    profile = _build_financial_profile(db, user_id)
    prompt = f"""
You are an expert investment advisor. Analyze this user's portfolio and provide insights.

Portfolio Data:
- Total Invested: {profile['portfolio']['total_invested']}
- Current Value: {profile['portfolio']['current_value']}
- Profit/Loss: {profile['portfolio']['profit_loss']} ({profile['portfolio']['profit_loss_pct']}%)
- Holdings by Type: {profile['portfolio']['by_type']}
- Total Holdings: {profile['portfolio']['total_holdings']}

Monthly Expenses: {profile['monthly_expense']}
Budget Utilization: {profile['budget_utilization_pct']}%
Top Expense Categories: {profile['top_expense_categories']}

Provide:
1. Portfolio health score (0-100)
2. Key strengths (2-3 points)
3. Key risks (2-3 points)
4. Diversification assessment
5. 3 specific actionable recommendations

Be concise and specific. Use INR currency.
"""
    return {"profile": profile, "insights": _call_gemini(prompt)}


def get_recommendations(db: Session, user_id) -> dict:
    profile = _build_financial_profile(db, user_id)
    prompt = f"""
You are a SEBI-registered investment advisor. Based on this user's financial profile, provide personalized investment recommendations.

Financial Profile:
- Monthly Expenses: ₹{profile['monthly_expense']}
- Monthly Budget: ₹{profile['total_budget']}
- Budget Used: {profile['budget_utilization_pct']}%
- Top Spending: {profile['top_expense_categories']}
- Active Goals: {profile['active_goals']}
- Current Portfolio: {profile['portfolio']}

Provide:
1. Monthly investable surplus estimate
2. Recommended asset allocation (% in equity/debt/gold/emergency fund)
3. Top 3 specific investment recommendations (with reasons)
4. SIP amount suggestions per goal
5. Risk level assessment (conservative/moderate/aggressive)
6. One key financial habit to improve

Format clearly with sections. Use INR. Be specific and actionable.
"""
    return {"profile": profile, "recommendations": _call_gemini(prompt)}


def analyze_full_profile(db: Session, user_id) -> dict:
    profile = _build_financial_profile(db, user_id)
    prompt = f"""
You are a comprehensive financial advisor. Perform a full financial health analysis.

User Financial Data:
{profile}

Provide a complete analysis with:
1. Financial Health Score (0-100) with breakdown
2. Income vs Expense analysis
3. Savings rate assessment
4. Goal achievement probability
5. Portfolio performance review
6. Top 5 personalized recommendations ranked by priority
7. 30-day action plan

Be detailed but structured. Use INR currency.
"""
    return {"profile": profile, "analysis": _call_gemini(prompt)}
