import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.rag_document import RagDocument
from app.models.user import User
from app.services import rag as rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[str]


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    description: str | None
    chunk_count: int

    class Config:
        from_attributes = True


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
) -> RagDocument:
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported")
    file_bytes = await file.read()
    doc_id = str(uuid.uuid4())
    chunk_count = rag_service.ingest_pdf(file_bytes, file.filename, doc_id)
    doc = RagDocument(
        id=uuid.UUID(doc_id),
        filename=file.filename,
        description=description,
        chunk_count=chunk_count,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AskResponse:
    result = rag_service.ask_question(payload.question)
    return AskResponse(question=payload.question, answer=result["answer"], sources=result["sources"])


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[RagDocument]:
    return list(db.scalars(select(RagDocument).order_by(RagDocument.created_at.desc())).all())


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    doc = db.get(RagDocument, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    rag_service.delete_document_chunks(str(doc_id))
    db.delete(doc)
    db.commit()
