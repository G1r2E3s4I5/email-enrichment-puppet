"""Application Configuration Settings powered by Pydantic."""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed application configuration settings."""

    # Environment
    ENVIRONMENT: str = Field(default="development", description="Execution environment")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Supabase Credentials
    SUPABASE_URL: str = Field(default="", description="Supabase Project URL")
    SUPABASE_ANON_KEY: str = Field(default="", description="Supabase Anon/Public Key")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="", description="Supabase Service Role Key")

    # Domain Resolution Concurrency
    DOMAIN_RESOLUTION_CONCURRENCY: int = Field(default=20, description="Max concurrent domain resolution tasks")

    # Circuit Breaker Configuration
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(default=3, description="Consecutive failures to open circuit")
    CIRCUIT_BREAKER_RESET_TIMEOUT: float = Field(default=30.0, description="Cooldown timeout in seconds before HALF_OPEN")
    CIRCUIT_BREAKER_HALF_OPEN_REQUESTS: int = Field(default=3, description="Trial requests permitted in HALF_OPEN state")

    # External Provider API Keys & Settings
    EMAIL_VERIFICATION_PROVIDER: str = Field(default="composite", description="Selected email verification provider (mock, mx, smtp, composite, hunter, zerobounce, etc.)")
    EMAIL_VERIFICATION_MODE: str = Field(default="composite", description="Email verification mode: mock, mx, smtp, composite")
    EMAIL_VERIFICATION_BATCH_SIZE: int = Field(default=50, description="Max candidate emails per verification batch chunk")
    EMAIL_VERIFICATION_MAX_CONCURRENCY: int = Field(default=5, description="Max simultaneous parallel batch worker tasks")
    EMAIL_VERIFICATION_RETRY_COUNT: int = Field(default=3, description="Max retries for transient batch errors")
    EMAIL_VERIFICATION_TIMEOUT: float = Field(default=10.0, description="Verification request timeout in seconds")
    EMAIL_VERIFICATION_REQUESTS_PER_SECOND: float = Field(default=20.0, description="Rate limit ceiling in requests per second")
    EMAIL_VERIFICATION_BACKOFF_BASE: float = Field(default=1.0, description="Exponential backoff base delay in seconds")

    # Real Email Verification Phase 6.x Settings
    ENABLE_MX_LOOKUP: bool = Field(default=True, description="Enable DNS MX record lookup")
    ENABLE_SMTP_VERIFICATION: bool = Field(default=True, description="Enable SMTP handshake verification")
    SMTP_TIMEOUT: float = Field(default=10.0, description="SMTP connection and response timeout in seconds")
    SMTP_PORT: int = Field(default=25, description="SMTP server target port")
    SMTP_HELO: str = Field(default="email-enrichment.local", description="SMTP HELO/EHLO hostname identifier")
    ROLE_ACCOUNT_PENALTY: float = Field(default=10.0, description="Confidence penalty for role email accounts (info@, admin@)")
    DISPOSABLE_PENALTY: float = Field(default=30.0, description="Confidence penalty for disposable domain emails")
    CATCH_ALL_PENALTY: float = Field(default=15.0, description="Confidence penalty for catch-all email domains")
    MX_CONFIDENCE_BONUS: float = Field(default=20.0, description="Confidence bonus when valid MX records exist")
    SMTP_CONFIDENCE_BONUS: float = Field(default=40.0, description="Confidence bonus when SMTP handshake succeeds")

    # Domain Provider Keys & Priority
    DOMAIN_PROVIDER_PRIORITY: str = Field(default="tavily,serpapi,cache,brandfetch", description="Domain provider resolution priority order")
    HUNTER_API_KEY: Optional[str] = Field(default=None, description="Hunter.io API Key")
    APOLLO_API_KEY: Optional[str] = Field(default=None, description="Apollo.io API Key")
    BRANDFETCH_API_KEY: Optional[str] = Field(default=None, description="Brandfetch API Key")
    SERPAPI_API_KEY: Optional[str] = Field(default=None, description="SerpAPI Key")
    TAVILY_API_KEY: Optional[str] = Field(default=None, description="Tavily API Key")
    BRAVE_API_KEY: Optional[str] = Field(default=None, description="Brave Search API Key")
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API Key")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI Model Name for Heuristic Domain Resolution")

    # Redis Configuration
    REDIS_HOST: str = Field(default="localhost", description="Redis Server Host")
    REDIS_PORT: int = Field(default=6379, description="Redis Server Port")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis Server Password")
    REDIS_DB: int = Field(default=0, description="Redis Database Index")
    REDIS_URL: Optional[str] = Field(default=None, description="Redis connection URL string")
    REDIS_SOCKET_TIMEOUT: float = Field(default=1.5, description="Redis Socket Timeout in seconds")
    REDIS_QUEUE_NAME: str = Field(default="email_enrichment_jobs", description="Redis Job Queue List Key")

    # Phase 5 Performance Optimization & Multi-Worker Settings
    WORKER_COUNT: int = Field(default=1, description="Number of parallel worker instances")
    CSV_CHUNK_SIZE: int = Field(default=500, description="Streaming CSV rows per processing chunk")
    DATABASE_BATCH_SIZE: int = Field(default=500, description="Max database record insertion batch size")
    REDIS_PIPELINE_SIZE: int = Field(default=100, description="Max Redis pipeline command batch size")
    MAX_JOB_RETRIES: int = Field(default=3, description="Max retry attempts for transient job failures")
    WORKER_HEARTBEAT_INTERVAL: float = Field(default=5.0, description="Worker heartbeat pulse interval in seconds")
    JOB_CHECKPOINT_INTERVAL: int = Field(default=500, description="Rows processed between job checkpoints")
    MEMORY_WARNING_THRESHOLD_MB: float = Field(default=512.0, description="Worker RAM warning ceiling in MB")

    # Phase 6 Configuration Settings
    MX_CACHE_TTL: int = Field(default=86400, description="MX lookup DNS record cache TTL in seconds")
    EXPORT_BATCH_SIZE: int = Field(default=1000, description="Batch chunk size for export record compilation")
    EXPORT_STREAM_SIZE: int = Field(default=1000, description="Streaming export row chunk size")
    ANALYTICS_RETENTION_DAYS: int = Field(default=30, description="Analytics historical metric retention period in days")
    VERIFICATION_PROVIDER: str = Field(default="composite", description="Selected verification provider (mock, mx, smtp, composite, etc.)")
    CORS_ORIGINS: list[str] = Field(default=["*"], description="CORS Allowed Origins")
    UPLOAD_DIR: str = Field(default="", description="Custom upload storage directory path")
    EXPORT_DIR: str = Field(default="", description="Custom export storage directory path")
    ENABLE_INPROCESS_WORKER: bool = Field(default=True, description="Auto-start in-process enrichment worker inside FastAPI lifespan")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        """Check if application is running in production mode."""
        return self.ENVIRONMENT.lower() in ("production", "prod")


# Singleton instance
settings = Settings()
