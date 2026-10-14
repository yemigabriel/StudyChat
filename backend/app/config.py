from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "production"] = "development"
    database_path: Path = Path("./studychat.db")
    chroma_path: Path = Path("./chroma")
    public_base_url: str = Field(min_length=1)

    twilio_account_sid: str = Field(pattern=r"^AC[0-9a-fA-F]{32}$")
    twilio_auth_token: SecretStr
    twilio_whatsapp_from: str = Field(pattern=r"^whatsapp:\+\d+$")

    openai_api_key: SecretStr
    openai_text_model: str = "gpt-4.1-mini"
    openai_vision_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_transcription_model: str = "gpt-4o-mini-transcribe"

    generation_provider: str = "openai"
    vision_provider: str = "openai"
    embedding_provider: str = "openai"
    transcription_provider: str = "openai"

    max_pdf_pages: int = Field(default=10, ge=1, le=100)
    max_pdf_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    max_context_chars: int = Field(default=24000, ge=4000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: str) -> str:
        value = value.rstrip("/")
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
            raise ValueError("PUBLIC_BASE_URL must be an HTTPS origin without a path or query")
        return value

    @model_validator(mode="after")
    def reject_unsupported_providers(self) -> "Settings":
        configured = {
            "GENERATION_PROVIDER": self.generation_provider,
            "VISION_PROVIDER": self.vision_provider,
            "EMBEDDING_PROVIDER": self.embedding_provider,
            "TRANSCRIPTION_PROVIDER": self.transcription_provider,
        }
        unsupported = [f"{name}={value}" for name, value in configured.items() if value != "openai"]
        if unsupported:
            raise ValueError("Unsupported provider configuration: " + ", ".join(unsupported))
        return self

    @property
    def twilio_auth_token_value(self) -> str:
        return self.twilio_auth_token.get_secret_value()

    @property
    def openai_api_key_value(self) -> str:
        return self.openai_api_key.get_secret_value()

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token_value and self.twilio_whatsapp_from)


@lru_cache
def get_settings() -> Settings:
    return Settings()
