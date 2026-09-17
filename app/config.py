from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="N3XUS_API_")

    searxng_url: str = "http://searxng:8080"
    search_ddg_enabled: bool = True
    search_variant_limit: int = 5
    request_timeout_secs: float = 25
    browser_fallback: bool = True
    human_challenge: bool = True
    human_challenge_timeout_secs: float = 180
    user_agent: str = "n3xusAPI/0.2 (+local self-hosted API)"
    data_dir: str = "data"
    api_key: str | None = None
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "qwen3:8b"
    smtp_url: str | None = None
    smtp_from: str | None = None
    transcription_model: str = "base"
    transcription_device: str = "cpu"
    transcription_compute_type: str | None = None
    uploads_dir: str = "data/uploads"
    stable_diffusion_url: str | None = None
    vm_host_data_dir: str | None = None
    meta_ads_access_token: str | None = None


settings = Settings()
