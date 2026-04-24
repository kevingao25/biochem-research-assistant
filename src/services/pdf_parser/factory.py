def make_pdf_parser_service():
    # Imported here so that docling (a heavy optional dep) is only loaded at startup,
    # not at module import time — keeping tests fast and import-safe without docling installed.
    from src.services.pdf_parser.parser import PDFProcessor
    return PDFProcessor()
