"""
database.py
-----------
SQLite by default (zero setup). To switch to PostgreSQL later, change ONE line:

    DATABASE_URL = "postgresql+psycopg://user:pass@localhost:5432/secondlife"

and `pip install psycopg[binary]`. Everything else (SQLModel) stays the same.
"""
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///./secondlife.db"

# check_same_thread=False is needed for SQLite + FastAPI's threaded server.
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)


def init_db() -> None:
    """Create all tables. (For a hackathon this replaces Alembic migrations.)"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: yields a DB session per request."""
    with Session(engine) as session:
        yield session
