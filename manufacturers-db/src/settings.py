from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://mdb:mdb@localhost:5432/manufacturers"

    companies_house_api_key: str = ""
    opencorporates_api_token: str = ""
    comtrade_primary_key: str = ""

    export_dir: Path = Path("./exports")
    http_user_agent: str = "manufacturers-db/0.1 (contact: unknown@example.com)"
    log_level: str = "INFO"


settings = Settings()
