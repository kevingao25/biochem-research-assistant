from typing import Any, Dict, List

from pydantic import BaseModel


class PaperSection(BaseModel):
    """One titled section of a paper as extracted by docling (e.g. 'Introduction', 'Methods')."""

    title: str
    content: str


class PdfContent(BaseModel):
    """Full output of a single PDF parse.

    sections:        structured content — used by the chunker to respect section boundaries.
    raw_text:        unstructured full text — fallback if sections are empty or malformed.
    parser_metadata: freeform docling output (e.g. section count); stored as-is in Postgres JSONB.
    """

    sections: List[PaperSection]
    raw_text: str
    parser_metadata: Dict[str, Any]
