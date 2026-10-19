from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models import user as user_model  # noqa: F401
from app.models import expense as expense_model  # noqa: F401
from app.models import budget as budget_model  # noqa: F401
from app.models import goal as goal_model  # noqa: F401
from app.models import investment as investment_model  # noqa: F401
from app.models import rag_document as rag_document_model  # noqa: F401
from app.models import conversation as conversation_model  # noqa: F401

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FI API",
    version="0.1.0",
    description="JWT authentication and user management",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
