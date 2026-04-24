from datetime import datetime

from pydantic import BaseModel, Field


class PaperCreate(BaseModel):
    arxiv_id: str = Field(..., description="arXiv paper ID")
    title: str = Field(..., description="Paper title")
    authors: list[str] = Field(..., description="List of author names")
    abstract: str = Field(..., description="Paper abstract")
    categories: list[str] = Field(..., description="Paper categories")
    published_date: datetime = Field(..., description="Date published on arXiv")
    pdf_url: str = Field(..., description="URL to PDF")
