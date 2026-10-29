from pydantic import BaseModel


class Notification(BaseModel):
    type: str        # "budget" | "goal" | "savings"
    alert: str       # "warning" | "exceeded" | "info"
    message: str
    detail: str
