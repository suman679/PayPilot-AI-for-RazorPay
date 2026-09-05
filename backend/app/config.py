"""
Centralized application configuration.

Every policy / financial-safety knob lives here and ONLY here. Services must
import `settings` rather than hardcoding numbers, so the policy engine has a
single, auditable source of truth.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Razorpay (TEST MODE) ---
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./paypilot.db"

    # --- Agent / LLM ---
    ANTHROPIC_API_KEY: str = ""
    AGENT_MODEL: str = "claude-sonnet-4-6"

    # --- Policy engine (THE financial safety model) ---
    MAX_TRANSACTION_AMOUNT_INR: int = 5000
    REQUIRE_USER_CONFIRMATION: bool = True
    MAX_PAYMENT_RETRY_ATTEMPTS: int = 2
    MAX_ORDER_CREATION_ATTEMPTS: int = 1
    ALLOW_AUTOMATIC_UPSELL: bool = False
    ALLOW_AUTOMATIC_PAYMENT: bool = False
    MAX_UPSELL_SUGGESTIONS: int = 2

    # --- App ---
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def razorpay_configured(self) -> bool:
        return bool(self.RAZORPAY_KEY_ID and self.RAZORPAY_KEY_SECRET)

    @property
    def agent_llm_configured(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
