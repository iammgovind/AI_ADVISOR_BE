import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.expense import ExpenseCategory


class ExpenseCreate(BaseModel):
    title: str = Field(max_length=255)
    amount: float = Field(gt=0)
    category: ExpenseCategory
    note: str | None = Field(default=None, max_length=500)
    expense_date: datetime


class ExpenseUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    amount: float | None = Field(default=None, gt=0)
    category: ExpenseCategory | None = None
    note: str | None = Field(default=None, max_length=500)
    expense_date: datetime | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    amount: float
    category: ExpenseCategory
    note: str | None
    expense_date: datetime
    created_at: datetime
    updated_at: datetime


class CategorySummary(BaseModel):
    category: ExpenseCategory
    total: float
    count: int


class MonthlySummary(BaseModel):
    year: int
    month: int
    total: float
    count: int
    by_category: list[CategorySummary]
