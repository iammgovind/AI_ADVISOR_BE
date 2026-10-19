from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.investment import Investment, InvestmentStatus, InvestmentType
from app.models.user import User
from app.schemas.investment import (
    InvestmentCreate,
    InvestmentOut,
    InvestmentPerformance,
    InvestmentUpdate,
    PortfolioSummary,
)

router = APIRouter(prefix="/investments", tags=["investments"])


def _get_or_404(db: Session, investment_id: UUID, user_id: UUID) -> Investment:
    inv = db.scalar(select(Investment).where(Investment.id == investment_id, Investment.user_id == user_id))
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment not found")
    return inv


def _to_performance(inv: Investment) -> InvestmentPerformance:
    qty = float(inv.quantity)
    buy = float(inv.buy_price)
    current = float(inv.current_price)
    invested = round(qty * buy, 2)
    current_value = round(qty * current, 2)
    profit_loss = round(current_value - invested, 2)
    profit_loss_pct = round((profit_loss / invested) * 100, 2) if invested > 0 else 0.0
    return InvestmentPerformance(
        investment_id=inv.id,
        name=inv.name,
        symbol=inv.symbol,
        investment_type=inv.investment_type,
        quantity=qty,
        buy_price=buy,
        current_price=current,
        invested_amount=invested,
        current_value=current_value,
        profit_loss=profit_loss,
        profit_loss_pct=profit_loss_pct,
        status=inv.status,
    )


@router.post("", response_model=InvestmentOut, status_code=status.HTTP_201_CREATED)
def create_investment(
    payload: InvestmentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Investment:
    inv = Investment(**payload.model_dump(), user_id=current_user.id)
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@router.get("", response_model=list[InvestmentOut])
def list_investments(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    investment_type: Annotated[InvestmentType | None, Query()] = None,
    status_filter: Annotated[InvestmentStatus | None, Query(alias="status")] = None,
) -> list[Investment]:
    q = select(Investment).where(Investment.user_id == current_user.id)
    if investment_type:
        q = q.where(Investment.investment_type == investment_type)
    if status_filter:
        q = q.where(Investment.status == status_filter)
    return list(db.scalars(q.order_by(Investment.buy_date.desc())).all())


@router.get("/portfolio", response_model=PortfolioSummary)
def portfolio_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PortfolioSummary:
    investments = db.scalars(
        select(Investment).where(
            Investment.user_id == current_user.id,
            Investment.status == InvestmentStatus.active,
        )
    ).all()

    holdings = [_to_performance(inv) for inv in investments]
    total_invested = round(sum(h.invested_amount for h in holdings), 2)
    current_value = round(sum(h.current_value for h in holdings), 2)
    total_pl = round(current_value - total_invested, 2)
    total_pl_pct = round((total_pl / total_invested) * 100, 2) if total_invested > 0 else 0.0

    # group by type
    type_map: dict[str, dict] = {}
    for h in holdings:
        t = h.investment_type.value
        if t not in type_map:
            type_map[t] = {"type": t, "invested": 0.0, "current_value": 0.0, "count": 0}
        type_map[t]["invested"] = round(type_map[t]["invested"] + h.invested_amount, 2)
        type_map[t]["current_value"] = round(type_map[t]["current_value"] + h.current_value, 2)
        type_map[t]["count"] += 1

    top = max(holdings, key=lambda h: h.profit_loss_pct).name if holdings else None
    worst = min(holdings, key=lambda h: h.profit_loss_pct).name if holdings else None

    return PortfolioSummary(
        total_invested=total_invested,
        current_value=current_value,
        total_profit_loss=total_pl,
        total_profit_loss_pct=total_pl_pct,
        total_holdings=len(holdings),
        by_type=list(type_map.values()),
        top_performer=top,
        worst_performer=worst,
        holdings=sorted(holdings, key=lambda h: h.profit_loss_pct, reverse=True),
    )


@router.get("/{investment_id}", response_model=InvestmentOut)
def get_investment(
    investment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Investment:
    return _get_or_404(db, investment_id, current_user.id)


@router.get("/{investment_id}/performance", response_model=InvestmentPerformance)
def investment_performance(
    investment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvestmentPerformance:
    inv = _get_or_404(db, investment_id, current_user.id)
    return _to_performance(inv)


@router.patch("/{investment_id}", response_model=InvestmentOut)
def update_investment(
    investment_id: UUID,
    payload: InvestmentUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Investment:
    inv = _get_or_404(db, investment_id, current_user.id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(inv, field, value)
    db.commit()
    db.refresh(inv)
    return inv


@router.delete("/{investment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investment(
    investment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    inv = _get_or_404(db, investment_id, current_user.id)
    db.delete(inv)
    db.commit()
