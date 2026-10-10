import pytest
from pydantic import SecretStr

from app.config import Settings, SettingsError


def test_local_defaults_are_safe_and_non_secret() -> None:
    settings = Settings.from_environment({"APP_ENV": "test"})
    assert settings.app_env == "test"
    assert settings.llm_mode == "fake"
    assert settings.fake_identity is True
    assert settings.database_url is None


@pytest.mark.parametrize(
    "environment",
    [
        {"APP_ENV": "production"},
        {
            "APP_ENV": "production",
            "DATABASE_URL": "",
            "PUBLIC_BASE_URL": "https://example.test",
            "SESSION_SECRET": "x" * 40,
        },
        {
            "APP_ENV": "production",
            "DATABASE_URL": "postgresql://db",
            "PUBLIC_BASE_URL": "http://example.test",
            "SESSION_SECRET": "x" * 40,
            "AUTH_ENABLED": "true",
            "FAKE_IDENTITY": "false",
            "SECURE_COOKIES": "true",
        },
    ],
)
def test_production_requires_secure_complete_configuration(environment: dict[str, str]) -> None:
    with pytest.raises(SettingsError):
        Settings.from_environment(environment)


def test_production_rejects_fake_identity_and_insecure_cookies(tmp_path) -> None:
    values = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql+psycopg://user:password@db/bsi",
        "STORAGE_ROOT": str(tmp_path.resolve()),
        "PUBLIC_BASE_URL": "https://example.test",
        "SESSION_SECRET": "s" * 40,
        "AUTH_ENABLED": "true",
        "FAKE_IDENTITY": "true",
        "SECURE_COOKIES": "true",
    }
    with pytest.raises(SettingsError, match="CONFIG_PRODUCTION_AUTH_INVALID"):
        Settings.from_environment(values)


def test_production_accepts_native_absolute_storage_root(tmp_path) -> None:
    settings = Settings.from_environment(
        {
            "APP_ENV": "production",
            "DATABASE_URL": "postgresql+psycopg://user:password@db/bsi",
            "STORAGE_ROOT": str(tmp_path.resolve()),
            "PUBLIC_BASE_URL": "https://example.test",
            "SESSION_SECRET": "s" * 40,
            "AUTH_ENABLED": "true",
            "FAKE_IDENTITY": "false",
            "SECURE_COOKIES": "true",
        }
    )
    assert settings.storage_root.is_absolute()


def test_provider_requires_model_key_and_https_base() -> None:
    with pytest.raises(SettingsError, match="CONFIG_PROVIDER_INCOMPLETE"):
        Settings.from_environment({"LLM_MODE": "provider"})
    with pytest.raises(SettingsError, match="CONFIG_PROVIDER_URL_INVALID"):
        Settings.from_environment(
            {
                "LLM_MODE": "provider",
                "LLM_MODEL": "example-model",
                "LLM_API_BASE": "http://provider.test/v1",
                "LLM_API_KEY": "example-secret",
                "LLM_ALLOWED_HOSTS": "provider.test",
            }
        )
    with pytest.raises(SettingsError, match="CONFIG_PROVIDER_HOST_NOT_ALLOWED"):
        Settings.from_environment(
            {
                "LLM_MODE": "provider",
                "LLM_MODEL": "example-model",
                "LLM_API_BASE": "https://provider.test/v1",
                "LLM_API_KEY": "example-secret",
            }
        )
    allowed = Settings.from_environment(
        {
            "LLM_MODE": "provider",
            "LLM_MODEL": "example-model",
            "LLM_API_BASE": "https://provider.test/v1",
            "LLM_API_KEY": "example-secret",
            "LLM_ALLOWED_HOSTS": "provider.test,other.test",
        }
    )
    assert allowed.llm_model == "example-model"


def test_invalid_limits_and_booleans_fail_without_values() -> None:
    with pytest.raises(SettingsError, match="CONFIG_INVALID") as caught:
        Settings.from_environment({"SOURCE_MAX_BYTES": "-1", "AUTH_ENABLED": "secret-ish"})
    assert "secret-ish" not in str(caught.value)


def test_storage_root_rejects_parent_traversal_and_file(tmp_path) -> None:
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("x", encoding="utf-8")
    for path in ("../outside", str(file_path)):
        with pytest.raises(SettingsError, match="CONFIG_STORAGE_ROOT_INVALID"):
            Settings.from_environment({"STORAGE_ROOT": path})


def test_secret_type_masks_values() -> None:
    secret = SecretStr("example-secret")
    assert str(secret) == "**********"
