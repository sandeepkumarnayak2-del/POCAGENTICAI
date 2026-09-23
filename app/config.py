from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise AI Service Desk"
    environment: str = "local"
    secret_key: str = "change-me"
    database_url: str = "sqlite:///./agent.db"
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_storage_uri: str = ""
    chroma_path: str = "./data/chroma"

    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    max_message_length: int = 1000
    rate_limit_per_minute: int = 20
    cors_origins: str = "http://localhost:8501"
    log_level: str = "INFO"

    # MCP
    mcp_enabled: bool = True
    mcp_server_url: str = "http://localhost:8001/mcp"
    mcp_port: int = 8001

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
