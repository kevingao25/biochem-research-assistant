import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
import src.models.paper  # noqa: F401 — ensures Paper model is registered with Base

logger = logging.getLogger(__name__)


def make_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_tables(engine) -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created (or already exist)")


@contextmanager
def get_session(session_factory):
    session = session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
