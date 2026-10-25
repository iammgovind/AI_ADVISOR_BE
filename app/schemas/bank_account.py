import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BankAccountCreate(BaseModel):
    bank_name: str = Field(max_length=100)
    account_number: str = Field(max_length=50)
    account_holder: str | None = Field(default=None, max_length=255)


class BankAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    bank_name: str
    account_number: str
    account_holder: str | None
    created_at: datetime
