from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.schemas.arxiv.paper import PaperCreate


class PaperRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, paper: PaperCreate) -> Paper:
        db_paper = Paper(**paper.model_dump())
        self.session.add(db_paper)
        self.session.commit()
        self.session.refresh(db_paper)
        return db_paper

    def get_by_arxiv_id(self, arxiv_id: str) -> Paper | None:
        stmt = select(Paper).where(Paper.arxiv_id == arxiv_id)
        return self.session.scalar(stmt)

    def get_by_id(self, paper_id: UUID) -> Paper | None:
        stmt = select(Paper).where(Paper.id == paper_id)
        return self.session.scalar(stmt)

    def get_all(self, limit: int = 100, offset: int = 0) -> list[Paper]:
        stmt = select(Paper).order_by(Paper.published_date.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt))

    def get_count(self) -> int:
        stmt = select(func.count(Paper.id))
        return self.session.scalar(stmt) or 0

    def get_unprocessed(self, limit: int = 100, offset: int = 0) -> list[Paper]:
        stmt = (
            select(Paper)
            .where(Paper.pdf_processed.is_(False))
            .order_by(Paper.published_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt))

    def update(self, paper: Paper) -> Paper:
        # Persists changes made to an already-loaded Paper object
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(paper)
        return paper

    def upsert(self, paper_create: PaperCreate) -> Paper:
        existing = self.get_by_arxiv_id(paper_create.arxiv_id)
        if existing:
            return existing
        return self.create(paper_create)

    def get_processed(self, limit: int = 100, offset: int = 0) -> list[Paper]:
        stmt = (
            select(Paper)
            .where(Paper.pdf_processed.is_(True))
            .order_by(Paper.pdf_processing_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt))

    def get_papers_with_text(self, limit: int = 100, offset: int = 0) -> list[Paper]:
        stmt = (
            select(Paper)
            .where(Paper.raw_text.is_not(None))
            .order_by(Paper.pdf_processing_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt))

    def get_processing_stats(self) -> dict:
        # Quick overview of how far along PDF processing is
        total = self.get_count()
        processed_stmt = select(func.count(Paper.id)).where(Paper.pdf_processed.is_(True))
        processed = self.session.scalar(processed_stmt) or 0
        text_stmt = select(func.count(Paper.id)).where(Paper.raw_text.is_not(None))
        with_text = self.session.scalar(text_stmt) or 0
        return {
            "total_papers": total,
            "processed_papers": processed,
            "papers_with_text": with_text,
        }
