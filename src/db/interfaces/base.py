from abc import ABC, abstractmethod
from typing import Any, ContextManager, Dict, List, Optional

from sqlalchemy.orm import Session


class BaseDatabase(ABC):
    """Abstract database interface."""

    @abstractmethod
    def startup(self) -> None:
        """Initialize the connection and create tables."""

    @abstractmethod
    def teardown(self) -> None:
        """Close all connections cleanly."""

    @abstractmethod
    def get_session(self) -> ContextManager[Session]:
        """Yield a SQLAlchemy session, rolling back on exception."""


class BaseRepository(ABC):
    """Abstract repository for a single model type."""

    def __init__(self, session: Session):
        self.session = session

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Any:
        """Insert a new record."""

    @abstractmethod
    def get_by_id(self, record_id: Any) -> Optional[Any]:
        """Fetch a record by primary key."""

    @abstractmethod
    def update(self, record_id: Any, data: Dict[str, Any]) -> Optional[Any]:
        """Update a record by primary key."""

    @abstractmethod
    def delete(self, record_id: Any) -> bool:
        """Delete a record by primary key."""

    @abstractmethod
    def list(self, limit: int = 100, offset: int = 0) -> List[Any]:
        """Return paginated records."""
