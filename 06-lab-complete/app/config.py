from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    Centralized configuration management.
    All values read from environment variables.
    """
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Redis
    redis_url: str = "redis://localhost:8080"
    
    # Security
    agent_api_key: str = "secret-key-123"
    
    # Logging
    log_level: str = "INFO"
    
    # Rate Limiting
    rate_limit_per_minute: int = 10
    
    # Cost Guard
    monthly_budget_usd: float = 10.0
    daily_budget_usd: float = 1.0
    
    # App Info
    app_name: str = "Production AI Agent"
    app_version: str = "1.0.0"
    environment: str = "production"
    
    # LLM (optional)
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    max_tokens: int = 500
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()