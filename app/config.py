from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./data/agent.db"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    scheduler_interval_minutes: int = 180
    scheduler_jitter_seconds: int = 900
    immediate_cycle_on_init: bool = True
    max_topics_per_cycle: int = 12
    min_publish_score: float = 0.65
    app_host: str = "0.0.0.0"
    app_port: int = 8001


settings = Settings()
