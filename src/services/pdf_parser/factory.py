from src.services.pdf_parser.parser import PdfProcessor


def make_pdf_parser_service() -> PdfProcessor:
    return PdfProcessor()
