
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    expenses,
    budgets,
    dashboard,
    goals,
    investments,
    rag,
    agent,
    risk,
    savings,
    multi_agent,
    chat,
    bank_accounts,
    statement,
    notifications,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(expenses.router)
api_router.include_router(budgets.router)
api_router.include_router(dashboard.router)
api_router.include_router(goals.router)
api_router.include_router(investments.router)
api_router.include_router(rag.router)
api_router.include_router(agent.router)
api_router.include_router(risk.router)
api_router.include_router(savings.router)
api_router.include_router(multi_agent.router)

api_router.include_router(chat.router)
api_router.include_router(bank_accounts.router)
api_router.include_router(statement.router)
api_router.include_router(notifications.router)
