class RepositoryException(Exception):
    """Base exception for repository-related errors."""


class PaperNotFound(RepositoryException):
    """Raised when a paper is not found in the database."""


class PaperNotSaved(RepositoryException):
    """Raised when a paper fails to save."""


class ParsingException(Exception):
    """Base exception for parsing errors."""


class PDFParsingException(ParsingException):
    """Base exception for PDF parsing errors."""


class PDFValidationError(PDFParsingException):
    """Raised when PDF validation fails."""


class PDFDownloadException(Exception):
    """Base exception for PDF download errors."""


class PDFDownloadTimeoutError(PDFDownloadException):
    """Raised when PDF download times out."""


class ArxivAPIException(Exception):
    """Base exception for arXiv API errors."""


class ArxivAPITimeoutError(ArxivAPIException):
    """Raised when arXiv API request times out."""


class ArxivAPIRateLimitError(ArxivAPIException):
    """Raised when arXiv API rate limit is exceeded."""


class ArxivParseError(ArxivAPIException):
    """Raised when arXiv API response cannot be parsed."""


class LLMException(Exception):
    """Base exception for LLM errors."""


class OllamaException(LLMException):
    """Raised for Ollama service errors."""


class OllamaConnectionError(OllamaException):
    """Raised when Ollama cannot be reached."""


class OllamaTimeoutError(OllamaException):
    """Raised when Ollama request times out."""


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
