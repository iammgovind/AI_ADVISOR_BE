import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.expense import ExpenseCategory


class ParsedTransaction(BaseModel):
    row_index: int
    date: datetime
    description: str
    amount: float
    suggested_category: ExpenseCategory
    confidence: str  # "high" | "medium" | "low"


class StatementPreview(BaseModel):
    upload_id: uuid.UUID
    bank_name: str | None
    account_number: str | None
    account_holder: str | None
    matched_account_id: uuid.UUID | None
    account_verified: bool
    total_debits: int
    transactions: list[ParsedTransaction]


class ApproveTransaction(BaseModel):
    row_index: int
    date: datetime
    description: str
    amount: float
    category: ExpenseCategory  # user may have edited this


class BulkApproveRequest(BaseModel):
    upload_id: uuid.UUID
    approved: list[ApproveTransaction]
    rejected_indices: list[int]
    duplicate_mode: Literal["check", "skip", "allow"] = "skip"


class BulkApproveResult(BaseModel):
    saved: int
    rejected: int
    skipped_duplicates: int = 0


class StatementUploadOut(BaseModel):
    id: uuid.UUID
    source: str
    filename: str | None
    total_transactions: int
    approved_count: int
    rejected_count: int
    status: str
    created_at: datetime
