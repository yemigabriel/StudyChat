import asyncio
import logging
import time

from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient

from backend.app.config import Settings

logger = logging.getLogger(__name__)


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
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError("Twilio message send failed after bounded retries") from last_error


async def send_message(settings: Settings, to: str, body: str) -> None:
    await asyncio.to_thread(_send_message, settings, to, body)
