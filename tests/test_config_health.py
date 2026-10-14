import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.main import create_app


def settings_values(tmp_path):
    return {
        "_env_file": None,
        "database_path": tmp_path / "studychat.sqlite3",
        "chroma_path": tmp_path / "chroma",
        "public_base_url": "https://studychat.example",
        "twilio_account_sid": "AC" + "a" * 32,
        "twilio_auth_token": "twilio-test-secret",
        "twilio_whatsapp_from": "whatsapp:+15551234567",
        "openai_api_key": "sk-test-secret",
    }


def test_health_endpoint_and_configured_database(tmp_path):
    settings = Settings(**settings_values(tmp_path))
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert (tmp_path / "studychat.sqlite3").exists()


def test_public_base_url_must_be_https_origin(tmp_path):
    values = settings_values(tmp_path)
    values["public_base_url"] = "http://studychat.example/webhook"

    with pytest.raises(ValidationError, match="PUBLIC_BASE_URL"):
        Settings(**values)


def test_unsupported_provider_fails_configuration_validation(tmp_path):
    values = settings_values(tmp_path)
    values["generation_provider"] = "anthropic"

    with pytest.raises(ValidationError, match="Unsupported provider configuration"):
        Settings(**values)


def test_secrets_are_masked_in_settings_repr(tmp_path):
    settings = Settings(**settings_values(tmp_path))

    assert "twilio-test-secret" not in repr(settings)
    assert "sk-test-secret" not in repr(settings)
