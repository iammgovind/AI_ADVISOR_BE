from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import savings_agent

router = APIRouter(prefix="/savings", tags=["savings-planner"])


@router.get("/plan")
def savings_plan(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return savings_agent.plan_savings(db, current_user.id)
