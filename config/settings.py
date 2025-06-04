import os
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ScrapingConfig:
    """Core configuration for the layout-aware scraper"""

    # LLM Configuration
    openai_api_key: str
    llm_model: str = "gpt-4"
    max_tokens: int = 1000
    temperature: float = 0.1

    # Browser Configuration
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    # Rate Limiting
    request_delay_min: float = 1.0
    request_delay_max: float = 3.0
    max_concurrent_browsers: int = 3

    # Retry Configuration
    max_retries: int = 3
    retry_delay: float = 2.0
    action_timeout: int = 30

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'ScrapingConfig':
        """Load configuration from environment variables"""
        return cls(
            openai_api_key=os.getenv('OPENAI_API_KEY', ''),
            llm_model=os.getenv('LLM_MODEL', 'gpt-4'),
            max_tokens=int(os.getenv('MAX_TOKENS', '1000')),
            temperature=float(os.getenv('TEMPERATURE', '0.1')),

            headless=os.getenv('HEADLESS', 'true').lower() == 'true',
            viewport_width=int(os.getenv('VIEWPORT_WIDTH', '1920')),
            viewport_height=int(os.getenv('VIEWPORT_HEIGHT', '1080')),

            request_delay_min=float(os.getenv('REQUEST_DELAY_MIN', '1.0')),
            request_delay_max=float(os.getenv('REQUEST_DELAY_MAX', '3.0')),
            max_concurrent_browsers=int(os.getenv('MAX_CONCURRENT_BROWSERS', '3')),

            max_retries=int(os.getenv('MAX_RETRIES', '3')),
            retry_delay=float(os.getenv('RETRY_DELAY', '2.0')),
            action_timeout=int(os.getenv('ACTION_TIMEOUT', '30')),

            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_file=os.getenv('LOG_FILE')
        )

    def validate(self) -> None:
        """Validate configuration parameters"""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required")

        if self.max_concurrent_browsers < 1:
            raise ValueError("max_concurrent_browsers must be >= 1")

        if self.request_delay_min < 0 or self.request_delay_max < self.request_delay_min:
            raise ValueError("Invalid request delay configuration")
