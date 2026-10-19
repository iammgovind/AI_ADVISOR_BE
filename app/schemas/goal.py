import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.goal import GoalStatus


class GoalCreate(BaseModel):
    title: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=500)
    target_amount: float = Field(gt=0)
    saved_amount: float = Field(default=0, ge=0)
    target_date: date


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    target_amount: float | None = Field(default=None, gt=0)
    target_date: date | None = None
    status: GoalStatus | None = None


class GoalDeposit(BaseModel):
    amount: float = Field(gt=0)


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    target_amount: float
    saved_amount: float
    target_date: date
    status: GoalStatus
    created_at: datetime
    updated_at: datetime


class GoalProgress(BaseModel):
    goal_id: uuid.UUID
    title: str
    target_amount: float
    saved_amount: float
    remaining_amount: float
    progress_pct: float
    target_date: date
    days_remaining: int
    monthly_savings_required: float
    status: GoalStatus
