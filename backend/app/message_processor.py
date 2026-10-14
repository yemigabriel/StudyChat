import asyncio
import logging
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from backend.app.chroma_store import ChromaVectorStore
from backend.app.config import Settings
from backend.app.incoming import IncomingMessage
from backend.app.ingestion import ingest_pdf
from backend.app.openai_provider import OpenAIProvider
from backend.app.database import connect
from backend.app.twilio_media import download_twilio_media
from backend.app.twilio_service import send_message

logger = logging.getLogger(__name__)
_sender_locks: dict[tuple[int, str], asyncio.Lock] = {}


def _set_reply_status(settings: Settings, message_sid: str, status: str) -> None:
    with connect(settings) as db:
        db.execute("UPDATE inbound_messages SET reply_status=? WHERE message_sid=?", (status, message_sid))


async def _reply(settings: Settings, incoming: IncomingMessage, text: str) -> None:
    try:
        await send_message(settings, incoming.sender, text)
        _set_reply_status(settings, incoming.message_sid, "sent")
        logger.info("Sent WhatsApp reply for inbound message (SID …%s)", incoming.message_sid[-8:])
    except Exception as exc:
        _set_reply_status(settings, incoming.message_sid, "failed")
        logger.error("WhatsApp send failed for inbound SID …%s (%s)", incoming.message_sid[-8:], exc.__class__.__name__)


async def _process_pdf(settings: Settings, incoming: IncomingMessage) -> None:
    if incoming.num_media != 1 or not incoming.media_url or incoming.media_content_type != "application/pdf":
        await _reply(settings, incoming, "I can process one text-based PDF per message right now. Please send a PDF file.")
        return

    try:
        data, content_type = await download_twilio_media(settings, incoming.media_url, settings.max_pdf_bytes)
        if content_type != "application/pdf":
            raise ValueError("The uploaded attachment is not a PDF.")
        url_name = PurePosixPath(urlsplit(incoming.media_url).path).name or "study-material.pdf"
        filename = url_name if url_name.lower().endswith(".pdf") else f"{url_name}.pdf"
        provider = OpenAIProvider(settings)
        vector_store = ChromaVectorStore(settings.chroma_path, "openai", settings.openai_embedding_model)
        result = await asyncio.to_thread(
            ingest_pdf,
            settings,
            incoming.sender,
            filename,
            data,
            incoming.message_sid,
            provider,
            provider,
            vector_store,
        )
        await _reply(
            settings,
            incoming,
            f"Your PDF is ready ({result.page_count} pages).\n\n{result.summary}\n\nAsk me a question about it any time.",
        )
        logger.info("Indexed PDF material for inbound SID …%s (%d pages, %d chunks)", incoming.message_sid[-8:], result.page_count, result.chunk_count)
    except ValueError as exc:
        await _reply(settings, incoming, str(exc))
    except Exception as exc:
        logger.error("PDF processing failed for inbound SID …%s (%s)", incoming.message_sid[-8:], exc.__class__.__name__)
        await _reply(settings, incoming, "I couldn't process that PDF just now. Please try again in a moment.")


async def process_incoming(settings: Settings, incoming: IncomingMessage) -> None:
    loop_key = (id(asyncio.get_running_loop()), incoming.sender)
    lock = _sender_locks.setdefault(loop_key, asyncio.Lock())
    async with lock:
        if incoming.num_media:
            await _process_pdf(settings, incoming)
            return

        normalized = incoming.body.strip().lower()
        if normalized in {"hi", "hello", "hey"}:
            reply = "Hi! Welcome to StudyChat. Send a text-based PDF, notebook photo, or short lecture voice note to get started."
        elif incoming.body.strip():
            reply = f"I received your message: {incoming.body[:1000]}\n\nSend a PDF to start studying."
        else:
            reply = "Welcome to StudyChat! Send a PDF, notebook photo, or short lecture voice note to start studying."
        await _reply(settings, incoming, reply)
