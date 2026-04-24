from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgreSQLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    database_url: str = Field(default="postgresql://biochem:biochem@localhost:5432/biochem_research")
    echo_sql: bool = Field(default=False)
    pool_size: int = Field(default=20)
    max_overflow: int = Field(default=0)
