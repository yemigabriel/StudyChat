from twilio.http.http_client import TwilioHttpClient
from twilio.http.response import Response

from backend.app.twilio_service import _send_message
from test_pdf_ingestion import make_settings


def test_plain_text_send_does_not_include_content_template_fields(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    captured: dict[str, object] = {}

    def request(self, method, url, params=None, data=None, headers=None, auth=None, timeout=None, allow_redirects=False):
        captured.update(data or {})
        return Response(201, '{"sid":"SMtest","account_sid":"ACtest"}', {})

    monkeypatch.setattr(TwilioHttpClient, "request", request)

    _send_message(settings, "whatsapp:+15557654321", "Hi! Welcome to StudyChat.")

    assert set(captured) == {"From", "To", "Body"}
