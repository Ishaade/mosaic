from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """All table classes inherit from this so SQLAlchemy can find them."""


# The connection string is the ONLY thing that changes for PostgreSQL later.
# check_same_thread=False: SQLite normally refuses use from multiple threads,
# and FastAPI may run our code on different ones.
engine = create_engine("sqlite:///./mosaic.db", connect_args={"check_same_thread": False})

# A "session" is one conversation with the database (like one transaction scope).
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    """FastAPI dependency: opens a session per request, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()