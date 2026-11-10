from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./allocat_ai.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    solver_timeout_seconds: int = 30
    upload_max_bytes: int = 10_000_000
    upload_max_csv_rows: int = 10_000
    llm_provider: str = "disabled"
    llm_model: str = "llama3.2"
    llm_base_url: str = "http://localhost:11434"
    llm_api_key: str = ""
    llm_timeout_seconds: int = 45
    auth_enabled: bool = True
    admin_api_token: str = ""
    placement_api_token: str = ""
    auditor_api_token: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
