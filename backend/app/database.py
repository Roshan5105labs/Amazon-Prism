from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

_url = settings.database_url
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}

engine = create_engine(
    _url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
