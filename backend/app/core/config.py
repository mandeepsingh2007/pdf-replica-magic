from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    APP_NAME: str = "AI Test Generator"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./test_generator.db"

    REDIS_URL: str = "redis://localhost:6379/0"

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "qwen/qwen3.8-27b"
    GEMINI_MODEL: str = "gemini-3.6-flash"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    MIN_CONTEXT_CHARS: int = 2000
    # Selected-chapter slices can be short (Class 1, image-heavy pages).
    MIN_CHAPTER_CONTEXT_CHARS: int = 250
    MAX_LLM_CONTEXT_CHARS: int = 12000
    LLM_CALL_TIMEOUT_SEC: int = 120
    CHUNKS_PER_GENERATION_BATCH: int = 10

    @model_validator(mode="after")
    def _use_google_key_for_gemini(self) -> "Settings":
        if not self.GEMINI_API_KEY and self.GOOGLE_API_KEY:
            self.GEMINI_API_KEY = self.GOOGLE_API_KEY
        return self


settings = Settings()


def min_context_chars_for_generation(chapter_ids: list | None) -> int:
    """Full book needs more text; a few selected chapters can be shorter."""
    if not chapter_ids:
        return settings.MIN_CONTEXT_CHARS
    n = max(1, len(chapter_ids))
    scaled = settings.MIN_CHAPTER_CONTEXT_CHARS * n
    return max(settings.MIN_CHAPTER_CONTEXT_CHARS, min(settings.MIN_CONTEXT_CHARS, scaled))
