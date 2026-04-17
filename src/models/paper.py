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
    raw_text            = Column(Text, nullable=True)
    sections            = Column(JSONB, nullable=True)   # structured sections from docling
    references          = Column("references", JSONB, nullable=True)   # bibliography entries ("references" is a reserved word in Postgres)
    parser_used         = Column(String, nullable=True)  # e.g. "docling"
    parser_metadata     = Column(JSONB, nullable=True)   # extra output from the parser

    pdf_processed       = Column(Boolean, nullable=False, default=False)
    pdf_processing_date = Column(DateTime, nullable=True)

    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))
