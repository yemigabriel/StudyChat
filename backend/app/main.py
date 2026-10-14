import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from twilio.request_validator import RequestValidator

from backend.app.config import Settings, get_settings
from backend.app.database import connect
from backend.app.twilio_service import send_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    if not settings.database_path.startswith(":memory:"):
        Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(settings):
        pass
    yield


app = FastAPI(title="StudyChat API", version="0.1.0", lifespan=lifespan)
app.state.settings = get_settings()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def deliver_reply(settings: Settings, message_sid: str, sender: str, body: str) -> None:
    reply = (
        "Welcome to StudyChat! Send a PDF, notebook photo, or short lecture voice note "
        "to start studying."
        if not body.strip()
        else f"I received your message: {body[:1200]}\n\nSend a PDF, notebook photo, or short lecture voice note to start studying."
    )
    try:
        await send_message(settings, sender, reply)
        with connect(settings) as db:
            db.execute("UPDATE inbound_messages SET reply_status='sent' WHERE message_sid=?", (message_sid,))
    except Exception:
        logger.exception("Could not send WhatsApp reply for inbound message")
        with connect(settings) as db:
            db.execute("UPDATE inbound_messages SET reply_status='failed' WHERE message_sid=?", (message_sid,))


@app.post("/webhooks/twilio")
async def twilio_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    settings: Settings = request.app.state.settings
    if not settings.twilio_auth_token or not settings.public_base_url:
        raise HTTPException(status_code=503, detail="Twilio webhook validation is not configured")

    form = await request.form()
    webhook_url = f"{settings.public_base_url}/webhooks/twilio"
    signature = request.headers.get("X-Twilio-Signature", "")
    if not RequestValidator(settings.twilio_auth_token).validate(webhook_url, form, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    message_sid = str(form.get("MessageSid", "")).strip()
    sender = str(form.get("From", "")).strip()
    body = str(form.get("Body", ""))
    if not message_sid or not sender:
        raise HTTPException(status_code=400, detail="Missing MessageSid or From")

    with connect(settings) as db:
        cursor = db.execute(
            "INSERT OR IGNORE INTO inbound_messages(message_sid, sender, body) VALUES (?, ?, ?)",
            (message_sid, sender, body),
        )
        is_new = cursor.rowcount == 1

    # Parse media/button fields now so the normalized webhook surface is ready for ingestion work.
    _incoming = {
        "message_sid": message_sid,
        "sender": sender,
        "body": body,
        "num_media": int(form.get("NumMedia", "0") or 0),
        "media_url": form.get("MediaUrl0"),
        "media_content_type": form.get("MediaContentType0"),
        "button_payload": form.get("ButtonPayload"),
        "button_text": form.get("ButtonText"),
    }
    if is_new and settings.twilio_configured:
        background_tasks.add_task(deliver_reply, settings, message_sid, sender, body)
    elif is_new:
        logger.warning("Inbound message stored; Twilio outbound credentials are not configured")

    # Twilio expects a quick successful response; the actual reply is sent via the REST API.
    return Response(content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>", media_type="application/xml")
