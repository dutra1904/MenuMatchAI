from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    llm_provider: str = "auto"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    database_url: str = "sqlite:///./menumatch.db"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    browse_minutes: float = 4.2
    agent_minutes: float = 0.7

    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", BACKEND / ".env"),
        extra="ignore",
    )

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url
        prefix = "sqlite:///./"
        if url.startswith(prefix):
            path = (BACKEND / url.removeprefix(prefix)).resolve()
            return "sqlite:///" + path.as_posix()
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
