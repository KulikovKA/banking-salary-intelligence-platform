"""Validated runtime settings with secret-safe configuration errors."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class SettingsError(ValueError):
    """Configuration error that never includes environment values."""


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    app_env: Literal["poc", "test", "production"] = "poc"
    database_url: SecretStr | None = None
    storage_root: Path = Path(".local/storage")
    public_base_url: str | None = None
    session_secret: SecretStr | None = None
    secure_cookies: bool = False
    auth_enabled: bool = False
    fake_identity: bool = True
    source_max_bytes: int = Field(default=52_428_800, gt=0, le=52_428_800)
    ingestion_mode: Literal["offline", "live"] = "offline"
    bank_fetch_tls_mode: Literal["system", "certifi"] = "system"
    bank_fetch_extra_ca_file: Path | None = None
    fetch_total_timeout_seconds: float = Field(default=60, gt=0, le=300)
    fetch_max_redirects: int = Field(default=5, ge=0, le=5)
    fetch_connect_timeout_seconds: float = Field(default=5, gt=0, le=120)
    fetch_read_timeout_seconds: float = Field(default=20, gt=0, le=300)
    fetch_max_attempts: int = Field(default=3, gt=0)
    llm_mode: Literal["fake", "provider"] = "fake"
    llm_model: str | None = None
    llm_api_base: str | None = None
    llm_api_key: SecretStr | None = None
    llm_allowed_hosts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_runtime_contract(self) -> Settings:
        if self.app_env == "test" and self.ingestion_mode != "offline":
            raise SettingsError("CONFIG_TEST_EGRESS_FORBIDDEN")
        if ".." in self.storage_root.parts:
            raise SettingsError("CONFIG_STORAGE_ROOT_INVALID: STORAGE_ROOT cannot traverse parents")
        if self.storage_root.exists() and not self.storage_root.is_dir():
            raise SettingsError("CONFIG_STORAGE_ROOT_INVALID: STORAGE_ROOT must be a directory")
        if self.llm_mode == "provider":
            if (
                not self.llm_model
                or not self.llm_api_base
                or not self.llm_api_key
                or not self.llm_api_key.get_secret_value()
            ):
                raise SettingsError("CONFIG_PROVIDER_INCOMPLETE: provider settings are required")
            parsed = urlsplit(self.llm_api_base)
            if parsed.scheme != "https" or not parsed.hostname:
                raise SettingsError("CONFIG_PROVIDER_URL_INVALID: LLM_API_BASE must use HTTPS")
            if parsed.hostname.lower() not in {host.lower() for host in self.llm_allowed_hosts}:
                raise SettingsError(
                    "CONFIG_PROVIDER_HOST_NOT_ALLOWED: provider host is not allowlisted"
                )

        if self.app_env == "production":
            if (
                not self.database_url
                or not self.database_url.get_secret_value()
                or not self.public_base_url
                or not self.session_secret
                or not self.session_secret.get_secret_value()
            ):
                raise SettingsError(
                    "CONFIG_PRODUCTION_REQUIRED: required production setting is missing"
                )
            if not self.storage_root.is_absolute():
                raise SettingsError(
                    "CONFIG_STORAGE_ROOT_INVALID: production STORAGE_ROOT must be absolute"
                )
            if len(self.session_secret.get_secret_value()) < 32:
                raise SettingsError("CONFIG_SESSION_SECRET_TOO_SHORT: minimum is 32 characters")
            public = urlsplit(self.public_base_url)
            if public.scheme != "https" or not public.hostname:
                raise SettingsError("CONFIG_PUBLIC_URL_INVALID: production origin must use HTTPS")
            if not self.secure_cookies or not self.auth_enabled or self.fake_identity:
                raise SettingsError(
                    "CONFIG_PRODUCTION_AUTH_INVALID: unsafe identity or cookie setting"
                )
        return self

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> Settings:
        source = os.environ if environ is None else environ
        aliases = {
            "APP_ENV": "app_env",
            "DATABASE_URL": "database_url",
            "STORAGE_ROOT": "storage_root",
            "PUBLIC_BASE_URL": "public_base_url",
            "SESSION_SECRET": "session_secret",
            "SECURE_COOKIES": "secure_cookies",
            "AUTH_ENABLED": "auth_enabled",
            "FAKE_IDENTITY": "fake_identity",
            "SOURCE_MAX_BYTES": "source_max_bytes",
            "INGESTION_MODE": "ingestion_mode",
            "BANK_FETCH_TLS_MODE": "bank_fetch_tls_mode",
            "BANK_FETCH_EXTRA_CA_FILE": "bank_fetch_extra_ca_file",
            "FETCH_TOTAL_TIMEOUT_SECONDS": "fetch_total_timeout_seconds",
            "FETCH_MAX_REDIRECTS": "fetch_max_redirects",
            "FETCH_CONNECT_TIMEOUT_SECONDS": "fetch_connect_timeout_seconds",
            "FETCH_READ_TIMEOUT_SECONDS": "fetch_read_timeout_seconds",
            "FETCH_MAX_ATTEMPTS": "fetch_max_attempts",
            "LLM_MODE": "llm_mode",
            "LLM_MODEL": "llm_model",
            "LLM_API_BASE": "llm_api_base",
            "LLM_API_KEY": "llm_api_key",
            "LLM_ALLOWED_HOSTS": "llm_allowed_hosts",
        }
        values: dict[str, object] = {}
        for variable, field_name in aliases.items():
            if variable not in source:
                continue
            raw = source[variable]
            if field_name in {"secure_cookies", "auth_enabled", "fake_identity"}:
                lowered = raw.strip().lower()
                if lowered not in {"true", "false", "1", "0"}:
                    raise SettingsError(f"CONFIG_INVALID: {variable} must be boolean")
                values[field_name] = lowered in {"true", "1"}
            else:
                values[field_name] = (
                    tuple(host.strip() for host in raw.split(",") if host.strip())
                    if field_name == "llm_allowed_hosts"
                    else raw
                )
        try:
            return cls.model_validate(values)
        except SettingsError:
            raise
        except Exception as exc:
            # Pydantic validation errors can include input values; keep only field names/codes.
            errors: Any = getattr(exc, "errors", lambda **_: [])(include_input=False)
            codes = [
                str(error.get("msg", ""))[len("Value error, ") :]
                for error in errors
                if str(error.get("msg", "")).startswith("Value error, CONFIG_")
            ]
            fields = ", ".join(
                str((error.get("loc") or ("settings",))[0])
                for error in errors
                if not str(error.get("msg", "")).startswith("Value error, CONFIG_")
            )
            detail = ", ".join(codes) if codes else fields or "unknown"
            raise SettingsError(f"CONFIG_INVALID: {detail}") from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_environment()
