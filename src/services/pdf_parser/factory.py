from src.services.pdf_parser.parser import PDFProcessor


def make_pdf_parser_service() -> PDFProcessor:
    return PDFProcessor()
