from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    debug: bool = True
    max_transaction_amount: float = 150000.0
    critical_transaction_amount: float = 500000.0
    velocity_window_seconds: int = 60
    velocity_max_count: int = 3
    geo_max_speed_kmh: float = 800.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
