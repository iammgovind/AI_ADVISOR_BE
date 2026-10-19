import io
from pathlib import Path

import chromadb
import pdfplumber
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from google import genai
from google.genai import types

from app.core.config import settings

CHROMA_PATH = Path("chroma_db")
COLLECTION_NAME = "fi_knowledge"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def _get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    return client.get_or_create_collection(COLLECTION_NAME, embedding_function=ef)


def _chunk_text(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end].strip())
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if c]


def ingest_pdf(file_bytes: bytes, filename: str, doc_id: str) -> int:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    chunks = _chunk_text(text)
    collection = _get_collection()
    collection.add(
        documents=chunks,
        ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        metadatas=[{"doc_id": doc_id, "filename": filename, "chunk": i} for i in range(len(chunks))],
    )
    return len(chunks)


def delete_document_chunks(doc_id: str) -> None:
    collection = _get_collection()
    results = collection.get(where={"doc_id": doc_id})
    if results["ids"]:
        collection.delete(ids=results["ids"])


def ask_question(question: str, top_k: int = 5) -> dict:
    collection = _get_collection()
    count = collection.count()
    if count == 0:
        return {
            "answer": "No relevant documents found. Please upload financial documents first.",
            "sources": [],
        }
    results = collection.query(query_texts=[question], n_results=min(top_k, count))
    docs = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []

    if not docs:
        return {
            "answer": "No relevant documents found. Please upload financial documents first.",
            "sources": [],
        }

    context = "\n\n".join([f"[{m['filename']}]\n{d}" for d, m in zip(docs, metadatas)])
    if not settings.GEMINI_API_KEY:
        return {"answer": "Gemini API key not configured. Please set GEMINI_API_KEY in .env", "sources": []}
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    prompt = (
        "You are a financial advisor assistant. Answer questions about financial planning, "
        "tax, investments, and mutual funds using only the provided context. "
        "Be concise, accurate, and helpful. If the answer is not in the context, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    for model in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return {"answer": response.text, "sources": list({m["filename"] for m in metadatas})}
        except Exception:
            continue
    return {"answer": "Gemini is currently unavailable. Please try again in a few minutes.", "sources": []}
