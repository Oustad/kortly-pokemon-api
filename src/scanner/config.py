"""Configuration management for Pokemon Card Scanner."""
import os
from typing import Optional
from functools import lru_cache

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()


class Config:
    """Application configuration with environment variable support."""

    def __init__(self):
        # Core API Configuration
        # Clean API keys to remove any whitespace or hidden characters that might cause issues
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self.pokemon_tcg_api_key = os.getenv("POKEMON_TCG_API_KEY", "").strip()

        # Server Configuration
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        self.environment = os.getenv("ENVIRONMENT", "production")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"

        # Gemini AI Configuration (Model configurable, other settings hardcoded)
        self.gemini_model = os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash")
        self.gemini_max_tokens = 2000
        self.gemini_temperature = 0.1
        self.gemini_max_retries = 3
        self.gemini_timeout_seconds = 60

        self.image_max_dimension = 1024
        self.image_jpeg_quality = 85
        self.image_max_file_size_mb = 10
        self.image_min_dimension = 400



        # Rate Limiting (Hardcoded defaults)
        self.rate_limit_per_minute = 60
        self.rate_limit_burst = 20
        self.rate_limit_enabled = True

        # Security Configuration
        self.cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
        self.enable_api_docs = os.getenv("ENABLE_API_DOCS", "true").lower() == "true"

        # Monitoring and Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.enable_metrics = True
        self.enable_cost_tracking = True

        # Error Notification Hooks
        self.error_webhook_url = os.getenv("ERROR_WEBHOOK_URL", "")
        self.error_webhook_enabled = os.getenv("ERROR_WEBHOOK_ENABLED", "false").lower() == "true"
        self.error_webhook_timeout = int(os.getenv("ERROR_WEBHOOK_TIMEOUT", "10"))
        self.error_webhook_min_level = os.getenv("ERROR_WEBHOOK_MIN_LEVEL", "ERROR")
        self.error_webhook_include_traceback = os.getenv("ERROR_WEBHOOK_INCLUDE_TRACEBACK", "true").lower() == "true"
        self.error_webhook_rate_limit = int(os.getenv("ERROR_WEBHOOK_RATE_LIMIT", "5"))
        self.error_webhook_environment_tag = os.getenv("ERROR_WEBHOOK_ENVIRONMENT_TAG", "production")




    def validate(self, require_api_key: bool = True):
        """Validate required configuration values."""
        errors = []

        if require_api_key and not self.google_api_key:
            errors.append("GOOGLE_API_KEY is required")

        # Pokemon TCG API key is required for production capacity
        if self.environment == "production" and not self.pokemon_tcg_api_key:
            errors.append("POKEMON_TCG_API_KEY is required in production for full API capacity (20,000 requests/day vs 1,000)")

        # Validation for hardcoded values removed - they're always valid now

        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def get_log_config(self) -> dict:
        """Get logging configuration."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": self.log_level,
                    "formatter": "json" if self.is_production else "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": self.log_level,
                "handlers": ["console"],
            },
        }


@lru_cache()
def get_config() -> Config:
    """Get cached configuration instance."""
    config = Config()
    config.validate(require_api_key=False)
    return config
