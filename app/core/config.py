import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    Centralized configuration management for the support agent.
    Automatically loads environment variables from system environment or a .env file.
    """
    # Application Metadata
    PROJECT_NAME: str = "Customer Support AI Agent"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Security & Authentication
    JWT_SECRET_KEY: str = "super-secret-jwt-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Database Configuration
    DATABASE_URL: str = "sqlite:///./data/support_agent.db"
    
    # LLM Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = "gpt-4o"
    
    # Deterministic Business Policy Limits
    RETURN_WINDOW_DAYS: int = 30
    APPROVAL_THRESHOLD_AMOUNT: float = 100.00
    
    # Pydantic v2 Settings configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Global settings instance for import across services and database modules
settings = Settings()
