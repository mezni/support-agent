import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./data/support_agent.db"

# Ensure the data directory exists locally
os.makedirs("./data", exist_ok=True)

# SQLite engine configuration
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

# Force SQLite to enforce foreign key constraints on every connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency for FastAPI endpoints to get database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
