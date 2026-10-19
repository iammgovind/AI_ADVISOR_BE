import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.investment import InvestmentStatus, InvestmentType


class InvestmentCreate(BaseModel):
    name: str = Field(max_length=255)
    symbol: str | None = Field(default=None, max_length=50)
    investment_type: InvestmentType
    quantity: float = Field(gt=0)
    buy_price: float = Field(gt=0)
    current_price: float = Field(gt=0)
    buy_date: date
    notes: str | None = Field(default=None, max_length=500)


class InvestmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    symbol: str | None = Field(default=None, max_length=50)
    quantity: float | None = Field(default=None, gt=0)
    current_price: float | None = Field(default=None, gt=0)
    status: InvestmentStatus | None = None
    notes: str | None = Field(default=None, max_length=500)


class InvestmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    symbol: str | None
    investment_type: InvestmentType
    quantity: float
    buy_price: float
    current_price: float
    buy_date: date
    status: InvestmentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


class InvestmentPerformance(BaseModel):
    investment_id: uuid.UUID
    name: str
    symbol: str | None
    investment_type: InvestmentType
    quantity: float
    buy_price: float
    current_price: float
    invested_amount: float
    current_value: float
    profit_loss: float
    profit_loss_pct: float
    status: InvestmentStatus


class PortfolioSummary(BaseModel):
    total_invested: float
    current_value: float
    total_profit_loss: float
    total_profit_loss_pct: float
    total_holdings: int
    by_type: list[dict]
    top_performer: str | None
    worst_performer: str | None
    holdings: list[InvestmentPerformance]
