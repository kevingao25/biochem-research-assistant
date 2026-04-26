from functools import lru_cache
from pathlib import Path
from typing import Literal, cast

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"


def env_field[T](default: T, *aliases: str) -> T:
    return cast(T, Field(default, validation_alias=AliasChoices(*aliases)))


class BaseConfigSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )


class ArxivSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="ARXIV__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    base_url: str = "https://export.arxiv.org/api/query"
    pdf_cache_dir: str = "./data/arxiv_pdfs"
    rate_limit_delay: float = 3.0
    timeout_seconds: int = 30
    max_results: int = 15
    max_concurrent_downloads: int = 5
    max_concurrent_parsing: int = 1
    search_categories: list[str] = ["q-bio.BM", "q-bio.MN", "q-bio.GN"]


class PDFParserSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="PDF_PARSER__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    max_pages: int = 30
    max_file_size_mb: int = 20
    do_ocr: bool = False
    do_table_structure: bool = True


class ChunkingSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="CHUNKING__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    chunk_size: int = 600
    overlap_size: int = 100
    min_chunk_size: int = 100
    section_based: bool = True


class QdrantSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="QDRANT__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    url: str = env_field("http://localhost:6333", "QDRANT__URL", "QDRANT_URL")
    collection_name: str = "papers_chunks"
    vector_dimension: int = 1024
    sparse_model_name: str = "Qdrant/bm25"


class LangfuseSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="LANGFUSE__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    public_key: str = env_field("", "LANGFUSE__PUBLIC_KEY", "LANGFUSE_PUBLIC_KEY")
    secret_key: str = env_field("", "LANGFUSE__SECRET_KEY", "LANGFUSE_SECRET_KEY")
    host: str = env_field("https://cloud.langfuse.com", "LANGFUSE__HOST", "LANGFUSE_BASE_URL")
    enabled: bool = True
    flush_at: int = 15
    flush_interval: float = 1.0
    debug: bool = False


class RedisSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="REDIS__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    url: str = env_field("redis://localhost:6379", "REDIS__URL", "REDIS_URL")
    ttl_hours: int = 24


class AgentSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="AGENT__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    max_retrieval_attempts: int = 2
    guardrail_enabled: bool = True


class Settings(BaseConfigSettings):
    app_version: str = "0.1.0"
    debug: bool = env_field(True, "APP_DEBUG")
    environment: Literal["development", "staging", "production"] = env_field("development", "APP_ENVIRONMENT")
    service_name: str = "biochem-rag-api"

    postgres_database_url: str = env_field(
        "postgresql://biochem:biochem@localhost:5432/biochem_research",
        "POSTGRES_DATABASE_URL",
        "DATABASE_URL",
    )
    postgres_echo_sql: bool = False
    postgres_pool_size: int = 20
    postgres_max_overflow: int = 0

    ollama_host: str = env_field("http://localhost:11434", "OLLAMA_HOST", "OLLAMA_URL")
    ollama_model: str = "llama3.2:1b"
    ollama_timeout: int = 300

    jina_api_key: str = ""

    arxiv: ArxivSettings = Field(default_factory=ArxivSettings)
    pdf_parser: PDFParserSettings = Field(default_factory=PDFParserSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)

    @field_validator("postgres_database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not (v.startswith("postgresql://") or v.startswith("postgresql+psycopg2://")):
            raise ValueError("Database URL must start with 'postgresql://'")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
