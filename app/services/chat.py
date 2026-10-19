from sqlalchemy import select
from sqlalchemy.orm import Session
 
from app.models.conversation import ConversationMessage
from app.services.agent import _build_financial_profile, _call_gemini
 
HISTORY_WINDOW = 20  # last N messages sent as context
 
 
def _load_history(db: Session, user_id) -> list[ConversationMessage]:
    return list(
        db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.user_id == user_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(HISTORY_WINDOW)
        ).all()
    )[::-1]  # chronological order
 
 
def chat(db: Session, user_id, message: str) -> str:
    profile = _build_financial_profile(db, user_id)
    history = _load_history(db, user_id)
 
    history_text = "\n".join(
        f"{msg.role.capitalize()}: {msg.content}" for msg in history
    )
 
    prompt = f"""You are a personal financial advisor AI with memory of this user's conversation history. User's current financial profile: {profile} Conversation history: {history_text} User: {message} Respond as a helpful financial advisor. Reference prior context when relevant. Be concise."""
 
    reply = _call_gemini(prompt)
 
    db.add(ConversationMessage(user_id=user_id, role="user", content=message))
    db.add(ConversationMessage(user_id=user_id, role="model", content=reply))
    db.commit()
 
    return reply
 
 
def get_history(db: Session, user_id, limit: int = 50) -> list[dict]:
    messages = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.user_id == user_id)
        .order_by(ConversationMessage.created_at.asc())
        .limit(limit)
    ).all()
    return [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages]
 
 
def clear_history(db: Session, user_id) -> int:
    messages = db.scalars(
        select(ConversationMessage).where(ConversationMessage.user_id == user_id)
    ).all()
    count = len(messages)
    for m in messages:
        db.delete(m)
    db.commit()
    return count
 