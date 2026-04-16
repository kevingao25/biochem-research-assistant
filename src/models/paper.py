import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.db.base import Base


class Paper(Base):
    __tablename__ = "papers"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    arxiv_id       = Column(String, unique=True, nullable=False, index=True)
    title          = Column(String, nullable=False)
    authors        = Column(JSONB, nullable=False)
    abstract       = Column(Text, nullable=False)
    categories     = Column(JSONB, nullable=False)
    published_date = Column(DateTime, nullable=False)
    pdf_url        = Column(String, nullable=False)
    pdf_processed  = Column(Boolean, nullable=False, default=False)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
