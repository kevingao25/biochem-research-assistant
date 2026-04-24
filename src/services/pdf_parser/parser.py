import logging
import tempfile
from pathlib import Path
from typing import Optional

import requests
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import SectionHeaderItem, TextItem

from src.schemas.pdf_parser.models import PaperSection, PdfContent

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 50
DOCUMENT_TIMEOUT_SECONDS = 120.0


class PdfProcessor:
    """Downloads and parses PDFs using docling."""

    def __init__(self):
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False          # OCR is very slow; arXiv PDFs are programmatic
        pipeline_options.do_table_structure = False
        pipeline_options.document_timeout = DOCUMENT_TIMEOUT_SECONDS

        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

    def download_pdf(self, url: str, dest: Path) -> None:
        """Download a PDF from url to dest, enforcing the size limit."""
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    raise ValueError(f"PDF exceeds {MAX_FILE_SIZE_MB}MB size limit")
                f.write(chunk)

    def parse_pdf(self, pdf_path: Path) -> Optional[PdfContent]:
        """Run docling on a local PDF file and return structured content."""
        result = self._converter.convert(str(pdf_path))
        doc = result.document

        sections = []
        current_title = "Content"
        current_text_parts = []

        for item, _level in doc.iterate_items():
            if isinstance(item, SectionHeaderItem):
                # Save the section we were building before starting a new one
                if current_text_parts:
                    sections.append(PaperSection(
                        title=current_title,
                        content=" ".join(current_text_parts).strip(),
                    ))
                current_title = item.text.strip()
                current_text_parts = []
            elif isinstance(item, TextItem) and item.text:
                current_text_parts.append(item.text)

        # Don't forget the last section
        if current_text_parts:
            sections.append(PaperSection(
                title=current_title,
                content=" ".join(current_text_parts).strip(),
            ))

        return PdfContent(
            sections=sections,
            raw_text=doc.export_to_text(),
            parser_metadata={"source": "docling", "num_sections": len(sections)},
        )

    def process(self, arxiv_id: str, pdf_url: str) -> Optional[PdfContent]:
        """Download and parse a single paper's PDF. Returns None if processing fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / f"{arxiv_id}.pdf"
            try:
                self.download_pdf(pdf_url, pdf_path)
                return self.parse_pdf(pdf_path)
            except Exception as e:
                logger.error(f"Failed to process PDF for {arxiv_id}: {e}")
                return None
