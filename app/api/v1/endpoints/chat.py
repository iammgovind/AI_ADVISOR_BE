from typing import Annotated
 
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
 
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import chat as chat_service
 
router = APIRouter(prefix="/chat", tags=["chat"])
 
 
class ChatRequest(BaseModel):
    message: str
 
 
@router.post("")
def send_message(
    body: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    reply = chat_service.chat(db, current_user.id, body.message)
    return {"reply": reply}
 
 
@router.get("/history")
def history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
) -> list[dict]:
    return chat_service.get_history(db, current_user.id, limit)
 
 
@router.delete("/history")
def clear_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    count = chat_service.clear_history(db, current_user.id)
    return {"deleted": count}
 