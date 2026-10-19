from collections.abc import Generator
from urllib.parse import urlparse
import re

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def _ensure_mysql_database(database_url: str) -> None:
    parsed = urlparse(database_url)
    db_name = (parsed.path or "").lstrip("/")
    if not db_name or not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        return
    admin_url = database_url.rsplit("/", 1)[0]
    admin_engine = create_engine(admin_url, pool_pre_ping=True)
    with admin_engine.connect() as connection:
        connection.execute(
            text(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
        connection.commit()
    admin_engine.dispose()


engine_kwargs: dict = {"pool_pre_ping": True}
database_url = settings.sqlalchemy_url
if database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    if ":memory:" in database_url:
        engine_kwargs["poolclass"] = StaticPool
elif database_url.startswith("mysql"):
    _ensure_mysql_database(database_url)

engine = create_engine(database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
