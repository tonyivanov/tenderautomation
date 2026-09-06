from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str

    # Platform credentials
    b2bcenter_username: str
    b2bcenter_password: str
    # Bidzaar uses the public integrator endpoint; credentials are legacy-only.
    bidzaar_username: str = ""
    bidzaar_password: str = ""

    # Paths
    data_dir: Path = Path("data")
    filters_dir: Path = Path("filters")

    # Build metadata
    app_commit_sha: str = "unknown"

    # Pipeline tuning
    qualification_threshold: int = 50
    collection_max_retries: int = 3
    collection_retry_base_sec: float = 1.0

    # Notifications — Telegram
    telegram_bot_token: str = ""
    telegram_chat_ids: str = ""  # comma-separated
    web_base_url: str = ""

    # Notifications — Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    email_recipients: str = ""  # comma-separated
    digest_hours: int = 24

    def get_telegram_chat_ids(self) -> list[str]:
        return [c.strip() for c in self.telegram_chat_ids.split(",") if c.strip()]

    def get_email_recipients(self) -> list[str]:
        return [e.strip() for e in self.email_recipients.split(",") if e.strip()]


settings = Settings()
