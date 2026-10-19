from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import multi_agent

router = APIRouter(prefix="/multi-agent", tags=["multi-agent"])


@router.get("/recommend")
def recommend(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return multi_agent.run_multi_agent(db, current_user.id)
