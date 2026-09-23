from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# Base class for all application models.
class Base(DeclarativeBase):
    pass

db_url = settings.database_url
if db_url.startswith("postgres://"):
    db_url = "postgresql+psycopg://" + db_url[len("postgres://"):]
elif db_url.startswith("postgresql://") and "+psycopg" not in db_url:
    db_url = "postgresql+psycopg://" + db_url[len("postgresql://"):]

connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _add_missing_column(table: str, column: str, ddl: str) -> None:
    """Add a small backward-compatible column to an existing database."""
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns(table)}
    if column in columns:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def init_db():
    # Import models so every mapped table is registered before create_all.
    from app.database import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # create_all does not alter existing tables. These migrations keep the
    # user's existing service_desk.db usable after enabling HITL/memory.
    _add_missing_column("approvals", "thread_id", "VARCHAR(255)")
