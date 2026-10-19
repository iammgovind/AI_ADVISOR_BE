import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.expense import ExpenseCategory


class BudgetCreate(BaseModel):
    category: ExpenseCategory
    limit_amount: float = Field(gt=0)
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class BudgetUpdate(BaseModel):
    limit_amount: float = Field(gt=0)


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    category: ExpenseCategory
    limit_amount: float
    year: int
    month: int
    created_at: datetime
    updated_at: datetime


class BudgetStatus(BaseModel):
    budget_id: uuid.UUID
    category: ExpenseCategory
    year: int
    month: int
    limit_amount: float
    spent: float
    remaining: float
    utilization_pct: float
    alert: str  # "ok" | "warning" | "exceeded"
