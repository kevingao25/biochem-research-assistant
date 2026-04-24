import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import src.models.paper  # noqa: F401 — registers Paper with Base.metadata
from src.db.base import Base
from src.db.interfaces.base import BaseDatabase
from src.schemas.database.config import PostgreSQLSettings

logger = logging.getLogger(__name__)


class PostgreSQLDatabase(BaseDatabase):

    def __init__(self, config: PostgreSQLSettings):
        self.config = config
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None

    def startup(self) -> None:
        host_hint = self.config.database_url.split("@")[-1] if "@" in self.config.database_url else "localhost"
        logger.info(f"Connecting to PostgreSQL at {host_hint}")

        self.engine = create_engine(
            self.config.database_url,
            echo=self.config.echo_sql,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_pre_ping=True,
        )
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        inspector = inspect(self.engine)
        existing = set(inspector.get_table_names())
        Base.metadata.create_all(bind=self.engine)
        new_tables = set(inspector.get_table_names()) - existing
        if new_tables:
            logger.info(f"Created tables: {', '.join(new_tables)}")
        else:
            logger.info("All tables already exist")

    def teardown(self) -> None:
        if self.engine:
            self.engine.dispose()
            logger.info("PostgreSQL connections closed")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        if not self.session_factory:
            raise RuntimeError("Database not initialized — call startup() first")
        session = self.session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
