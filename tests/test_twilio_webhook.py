import sqlite3

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from backend.app import main, message_processor
from backend.app.config import Settings
from backend.app.incoming import IncomingMessage


def make_settings(tmp_path):
    return Settings(
        _env_file=None,
        database_path=tmp_path / "webhook.sqlite3",
        chroma_path=tmp_path / "chroma",
        public_base_url="https://studychat.example",
        twilio_account_sid="AC" + "a" * 32,
        twilio_auth_token="twilio-test-secret",
        twilio_whatsapp_from="whatsapp:+15551234567",
        openai_api_key="sk-test-secret",
    )


def signed_headers(settings, path, form):
    url = settings.public_base_url + path
    signature = RequestValidator(settings.twilio_auth_token_value).compute_signature(url, form)
    return {"X-Twilio-Signature": signature}


def test_root_callback_acknowledges_once_and_sends_one_reply(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    sent = []

    async def fake_send_message(_settings, to, body):
        sent.append((to, body))

    monkeypatch.setattr(message_processor, "send_message", fake_send_message)
    payload = {
        "MessageSid": "SM" + "1" * 32,
        "From": "whatsapp:+15557654321",
        "Body": "hi",
        "NumMedia": "0",
    }
    headers = signed_headers(settings, "/", payload)

    with TestClient(main.create_app(settings)) as client:
        first = client.post("/", data=payload, headers=headers)
        duplicate = client.post("/", data=payload, headers=headers)

    assert first.status_code == duplicate.status_code == 200
    assert first.text == '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    assert first.headers["content-type"].startswith("application/xml")
    assert len(sent) == 1
    assert sent[0][0] == payload["From"]
    assert sent[0][1].startswith("Hi! Welcome to StudyChat.")
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM inbound_messages").fetchone()[0] == 1
        assert db.execute("SELECT reply_status FROM inbound_messages").fetchone()[0] == "sent"


def test_webhook_route_validates_its_exact_public_url(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)

    async def fake_send_message(*_args):
        return None

    monkeypatch.setattr(message_processor, "send_message", fake_send_message)
    payload = {"MessageSid": "SM" + "2" * 32, "From": "whatsapp:+15557654321", "Body": "hi"}

    with TestClient(main.create_app(settings)) as client:
        response = client.post(
            "/webhooks/twilio",
            data=payload,
            headers=signed_headers(settings, "/webhooks/twilio", payload),
        )

    assert response.status_code == 200


def test_invalid_signature_is_rejected_without_persistence(tmp_path):
    settings = make_settings(tmp_path)
    payload = {"MessageSid": "SM" + "3" * 32, "From": "whatsapp:+15557654321", "Body": "hi"}

    with TestClient(main.create_app(settings)) as client:
        response = client.post("/", data=payload, headers={"X-Twilio-Signature": "invalid"})

    assert response.status_code == 403
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM inbound_messages").fetchone()[0] == 0


def test_incoming_message_parses_media_and_button_fields():
    incoming = IncomingMessage.from_form(
        {
            "MessageSid": "SM123",
            "From": "whatsapp:+15557654321",
            "Body": "",
            "NumMedia": "1",
            "MediaUrl0": "https://api.twilio.com/media/123",
            "MediaContentType0": "application/pdf",
            "ButtonPayload": "summary",
            "ButtonText": "Summary",
        }
    )

    assert incoming.num_media == 1
    assert incoming.media_content_type == "application/pdf"
    assert incoming.button_payload == "summary"
    assert incoming.button_text == "Summary"


def test_invalid_num_media_fails_normalization():
    with pytest.raises(ValueError, match="NumMedia"):
        IncomingMessage.from_form({"MessageSid": "SM1", "From": "whatsapp:+1", "NumMedia": "no"})
