import base64

import httpx
import pytest

from backend.app.config import Settings
from backend.app.twilio_media import download_twilio_media


@pytest.fixture
def anyio_backend():
    return "asyncio"


def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_path=tmp_path / "db.sqlite3",
        chroma_path=tmp_path / "chroma",
        public_base_url="https://studychat.example",
        twilio_account_sid="AC" + "a" * 32,
        twilio_auth_token="twilio-test-secret",
        twilio_whatsapp_from="whatsapp:+15551234567",
        openai_api_key="sk-test-secret",
    )


@pytest.mark.anyio
async def test_media_redirect_does_not_forward_twilio_credentials(tmp_path, monkeypatch):
    real_client = httpx.AsyncClient
    auth_headers = []

    def handler(request):
        auth_headers.append(request.headers.get("Authorization"))
        if request.url.host == "api.twilio.com":
            return httpx.Response(302, headers={"Location": "https://mms.twiliocdn.com/short-lived"})
        return httpx.Response(200, headers={"Content-Type": "application/pdf"}, content=b"%PDF-test")

    monkeypatch.setattr(
        "backend.app.twilio_media.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    data, content_type = await download_twilio_media(
        settings(tmp_path),
        "https://api.twilio.com/2010-04-01/Accounts/AC" + "a" * 32 + "/Messages/MM/Media/ME",
        max_bytes=100,
    )

    expected = "Basic " + base64.b64encode(("AC" + "a" * 32 + ":twilio-test-secret").encode()).decode()
    assert auth_headers == [expected, None]
    assert data == b"%PDF-test"
    assert content_type == "application/pdf"


@pytest.mark.anyio
async def test_media_download_enforces_size_limit(tmp_path, monkeypatch):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "backend.app.twilio_media.httpx.AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, headers={"Content-Type": "application/pdf"}, content=b"12345")
            ),
            **kwargs,
        ),
    )

    with pytest.raises(ValueError, match="size limit"):
        await download_twilio_media(
            settings(tmp_path),
            "https://api.twilio.com/2010-04-01/Accounts/AC" + "a" * 32 + "/Messages/MM/Media/ME",
            max_bytes=4,
        )


@pytest.mark.anyio
async def test_media_url_must_use_twilio_https_host(tmp_path):
    with pytest.raises(ValueError, match="approved HTTPS Twilio host"):
        await download_twilio_media(settings(tmp_path), "http://example.com/file.pdf", max_bytes=100)
