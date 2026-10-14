import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from twilio.request_validator import RequestValidator

from backend.app.config import Settings, get_settings
from backend.app.database import connect
from backend.app.incoming import IncomingMessage
from backend.app.message_processor import process_incoming

logging.basicConfig(level=logging.INFO)
logging.getLogger("twilio.http_client").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    selected_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db_path = selected_settings.database_path
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with connect(selected_settings):
            pass
        yield

    application = FastAPI(title="StudyChat API", version="0.1.0", lifespan=lifespan)
    application.state.settings = selected_settings

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/")
    @application.post("/webhooks/twilio")
    async def inbound_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
        return await twilio_webhook(request, background_tasks)

    return application


async def twilio_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    settings: Settings = request.app.state.settings
    if not settings.twilio_auth_token_value or not settings.public_base_url:
        raise HTTPException(status_code=503, detail="Twilio webhook validation is not configured")

    form = await request.form()
    webhook_url = settings.public_base_url + request.url.path
    signature = request.headers.get("X-Twilio-Signature", "")
    if not RequestValidator(settings.twilio_auth_token_value).validate(webhook_url, form, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    try:
        incoming = IncomingMessage.from_form(form)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with connect(settings) as db:
        cursor = db.execute(
            "INSERT OR IGNORE INTO inbound_messages(message_sid, sender, body) VALUES (?, ?, ?)",
            (incoming.message_sid, incoming.sender, incoming.body),
        )
        is_new = cursor.rowcount == 1

    if not is_new:
        logger.info("Ignored duplicate Twilio delivery (SID …%s)", incoming.message_sid[-8:])
    elif settings.twilio_configured:
        logger.info("Accepted Twilio message (SID …%s); queued reply", incoming.message_sid[-8:])
        background_tasks.add_task(process_incoming, settings, incoming)

    # Twilio expects a quick successful response; the actual reply is sent via the REST API.
    return Response(content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>", media_type="application/xml")


app = create_app()
