"""
Centralized configuration management for the Image API server.
Handles environment variable loading, validation, and default values.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv


class Settings(BaseSettings):
    """Application settings with environment variable support and validation."""
    
    # Gemini API Configuration
    gemini_api_key: str = Field(
        ..., 
        description="Google Gemini API key for image generation",
        min_length=1
    )
    
    # AWS S3 Configuration
    aws_access_key_id: str = Field(
        ...,
        description="AWS access key ID for S3 operations",
        min_length=1
    )
    aws_secret_access_key: str = Field(
        ...,
        description="AWS secret access key for S3 operations", 
        min_length=1
    )
    aws_region: str = Field(
        default="us-east-1",
        description="AWS region for S3 bucket"
    )
    s3_bucket_name: str = Field(
        ...,
        description="S3 bucket name for image storage",
        min_length=1
    )
    
    # Application Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    port: int = Field(
        default=8000,
        description="Server port number",
        ge=1,
        le=65535
    )
    
    # Environment Detection
    environment: str = Field(
        default="development",
        description="Application environment (development, staging, production)"
    )
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level is a valid Python logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()
    
    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment is a recognized value."""
        valid_envs = ["development", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"Environment must be one of: {', '.join(valid_envs)}")
        return v.lower()
    
    @validator("aws_region")
    def validate_aws_region(cls, v):
        """Basic AWS region format validation."""
        if not v or len(v.split("-")) < 2:
            raise ValueError("AWS region must be in format like 'us-east-1'")
        return v
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Allow environment variables to override settings
        env_prefix = ""


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings with caching.
    
    Uses lru_cache to ensure settings are loaded only once per application run.
    This implements a singleton pattern for the settings instance.
    
    Returns:
        Settings: The application settings instance
        
    Raises:
        ValidationError: If required environment variables are missing or invalid
    """
    # Load .env file if it exists
    load_dotenv()
    
    try:
        settings = Settings()
        return settings
    except Exception as e:
        print(f"❌ Configuration Error: {e}")
        print("\n📋 Required Environment Variables:")
        print("  • GEMINI_API_KEY - Google Gemini API key")
        print("  • AWS_ACCESS_KEY_ID - AWS access key")
        print("  • AWS_SECRET_ACCESS_KEY - AWS secret key")
        print("  • S3_BUCKET_NAME - S3 bucket name")
        print("\n💡 Optional Environment Variables:")
        print("  • AWS_REGION (default: us-east-1)")
        print("  • LOG_LEVEL (default: INFO)")
        print("  • PORT (default: 8000)")
        print("  • ENVIRONMENT (default: development)")
        print("\n📝 Create a .env file or set these environment variables.")
        raise


def validate_settings() -> None:
    """
    Validate all settings on application startup.
    
    This function should be called during application initialization
    to ensure all required configuration is present and valid.
    
    Raises:
        SystemExit: If configuration validation fails
    """
    try:
        settings = get_settings()
        print(f"✅ Configuration loaded successfully")
        print(f"   Environment: {settings.environment}")
        print(f"   Log Level: {settings.log_level}")
        print(f"   AWS Region: {settings.aws_region}")
        print(f"   Port: {settings.port}")
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        exit(1)


# Export settings instance for easy importing
settings = get_settings()