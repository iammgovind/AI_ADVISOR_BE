from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import agent as agent_service

router = APIRouter(prefix="/agent", tags=["investment-agent"])


@router.get("/market/{symbol}")
def market_data(
    symbol: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    try:
        return agent_service.get_market_data(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not fetch data for {symbol}: {str(e)}")


@router.get("/portfolio/insights")
def portfolio_insights(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return agent_service.get_portfolio_insights(db, current_user.id)


@router.get("/recommendations")
def recommendations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return agent_service.get_recommendations(db, current_user.id)


@router.post("/analyze")
def analyze(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return agent_service.analyze_full_profile(db, current_user.id)
