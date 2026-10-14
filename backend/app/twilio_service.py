import asyncio
import logging
import time

from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient

from backend.app.config import Settings

logger = logging.getLogger(__name__)


class TwilioSendError(RuntimeError):
    def __init__(self, code: int | None, status: int | None):
        self.code = code
        self.status = status
        if code == 21654:
            message = "Twilio rejected the message (21654: ContentSid required with ContentVariables)."
        else:
            message = f"Twilio rejected the message (HTTP {status or 'unknown'}, error {code or 'unknown'})."
        super().__init__(message)


def _send_message(settings: Settings, to: str, body: str) -> None:
    http_client = TwilioHttpClient(timeout=10, max_retries=0)
    client = Client(
        settings.twilio_account_sid,
        settings.twilio_auth_token_value,
        http_client=http_client,
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            client.messages.create(from_=settings.twilio_whatsapp_from, to=to, body=body)
            return
        except Exception as exc:
            last_error = exc
            status = getattr(exc, "status", None)
            code = getattr(exc, "code", None)
            if status and status < 500 and status != 429:
                raise TwilioSendError(code, status) from exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    raise TwilioSendError(getattr(last_error, "code", None), getattr(last_error, "status", None)) from last_error


async def send_message(settings: Settings, to: str, body: str) -> None:
    await asyncio.to_thread(_send_message, settings, to, body)
