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
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "")
        self.pokemon_tcg_api_key = os.getenv("POKEMON_TCG_API_KEY", "")
        
        # Server Configuration
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        self.environment = os.getenv("ENVIRONMENT", "production")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Gemini AI Configuration
        self.gemini_model = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash-preview-05-20")
        self.gemini_max_tokens = int(os.getenv("GEMINI_MAX_TOKENS", "2000"))
        self.gemini_temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.1"))
        self.gemini_max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
        self.gemini_timeout_seconds = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "60"))
        
        # Image Processing Configuration
        self.image_max_dimension = int(os.getenv("IMAGE_MAX_DIMENSION", "1024"))
        self.image_jpeg_quality = int(os.getenv("IMAGE_JPEG_QUALITY", "85"))
        self.image_max_file_size_mb = int(os.getenv("IMAGE_MAX_FILE_SIZE_MB", "10"))
        self.image_min_dimension = int(os.getenv("IMAGE_MIN_DIMENSION", "400"))
        
        # Caching Configuration
        self.cache_enabled = os.getenv("CACHE_ENABLED", "true").lower() == "true"
        self.cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
        self.cache_max_entries = int(os.getenv("CACHE_MAX_ENTRIES", "1000"))
        
        # Rate Limiting
        self.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
        self.rate_limit_burst = int(os.getenv("RATE_LIMIT_BURST", "20"))
        self.rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        
        # Security Configuration
        self.cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
        self.allowed_hosts = os.getenv("ALLOWED_HOSTS", "*").split(",")
        self.enable_api_docs = os.getenv("ENABLE_API_DOCS", "true").lower() == "true"
        self.api_key_header = os.getenv("API_KEY_HEADER", "X-API-Key")
        
        # Monitoring and Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() == "true"
        self.metrics_port = int(os.getenv("METRICS_PORT", "9090"))
        self.enable_cost_tracking = os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"
        
        # Error Notification Hooks
        self.error_webhook_url = os.getenv("ERROR_WEBHOOK_URL", "")
        self.error_webhook_enabled = os.getenv("ERROR_WEBHOOK_ENABLED", "false").lower() == "true"
        self.error_webhook_timeout = int(os.getenv("ERROR_WEBHOOK_TIMEOUT", "10"))
        self.error_webhook_min_level = os.getenv("ERROR_WEBHOOK_MIN_LEVEL", "ERROR")
        self.error_webhook_include_traceback = os.getenv("ERROR_WEBHOOK_INCLUDE_TRACEBACK", "true").lower() == "true"
        self.error_webhook_rate_limit = int(os.getenv("ERROR_WEBHOOK_RATE_LIMIT", "5"))
        self.error_webhook_environment_tag = os.getenv("ERROR_WEBHOOK_ENVIRONMENT_TAG", "production")
        
        # Static Files
        self.serve_static_files = os.getenv("SERVE_STATIC_FILES", "true").lower() == "true"
        self.static_file_cache_age = int(os.getenv("STATIC_FILE_CACHE_AGE", "86400"))
        
        # Health Checks
        self.health_check_interval = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))
        self.startup_timeout = int(os.getenv("STARTUP_TIMEOUT", "60"))
        self.shutdown_timeout = int(os.getenv("SHUTDOWN_TIMEOUT", "30"))
    
    def validate(self, require_api_key: bool = True):
        """Validate required configuration values."""
        errors = []
        
        if require_api_key and not self.google_api_key:
            errors.append("GOOGLE_API_KEY is required")
            
        if self.image_max_dimension < self.image_min_dimension:
            errors.append("IMAGE_MAX_DIMENSION must be greater than IMAGE_MIN_DIMENSION")
            
        if self.image_jpeg_quality < 1 or self.image_jpeg_quality > 100:
            errors.append("IMAGE_JPEG_QUALITY must be between 1 and 100")
            
        if self.rate_limit_burst > self.rate_limit_per_minute:
            errors.append("RATE_LIMIT_BURST cannot exceed RATE_LIMIT_PER_MINUTE")
            
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
    # Only validate basic config during import, API key validation happens later
    config.validate(require_api_key=False)
    return config