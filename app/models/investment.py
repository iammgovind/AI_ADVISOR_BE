import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class InvestmentType(str, enum.Enum):
    stock = "stock"
    mutual_fund = "mutual_fund"
    sip = "sip"
    etf = "etf"
    crypto = "crypto"
    bond = "bond"
    fd = "fd"
    other = "other"


class InvestmentStatus(str, enum.Enum):
    active = "active"
    sold = "sold"


class Investment(Base):
    __tablename__ = "investments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    symbol: Mapped[str | None] = mapped_column(String(50), nullable=True)
    investment_type: Mapped[InvestmentType] = mapped_column(
        Enum(InvestmentType, values_callable=lambda m: [i.value for i in m], native_enum=False)
    )
    quantity: Mapped[float] = mapped_column(Numeric(16, 4))
    buy_price: Mapped[float] = mapped_column(Numeric(12, 4))
    current_price: Mapped[float] = mapped_column(Numeric(12, 4))
    buy_date: Mapped[date] = mapped_column(Date)
    status: Mapped[InvestmentStatus] = mapped_column(
        Enum(InvestmentStatus, values_callable=lambda m: [i.value for i in m], native_enum=False),
        default=InvestmentStatus.active,
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="investments")
