import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.expense import Expense
    from app.models.budget import Budget
    from app.models.goal import Goal
    from app.models.investment import Investment
    from app.models.bank_account import BankAccount
    from app.models.statement_upload import StatementUpload


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda members: [item.value for item in members], native_enum=False),
        default=UserRole.user,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    monthly_income: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    risk_appetite: Mapped[str | None] = mapped_column(String(20), nullable=True)  # conservative | moderate | aggressive
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def age(self) -> int | None:
        """Computed from date_of_birth on every read, so it updates automatically each birthday."""
        if self.date_of_birth is None:
            return None
        today = date.today()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="user", cascade="all, delete-orphan")
    budgets: Mapped[list["Budget"]] = relationship("Budget", back_populates="user", cascade="all, delete-orphan")
    goals: Mapped[list["Goal"]] = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    investments: Mapped[list["Investment"]] = relationship("Investment", back_populates="user", cascade="all, delete-orphan")
    bank_accounts: Mapped[list["BankAccount"]] = relationship("BankAccount", back_populates="user", cascade="all, delete-orphan")
    statement_uploads: Mapped[list["StatementUpload"]] = relationship("StatementUpload", back_populates="user", cascade="all, delete-orphan")
