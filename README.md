# StudyChat

StudyChat is a Telegram-first study companion. Its MVP runs as a standalone `python-telegram-bot` long-polling process. FastAPI and the Twilio WhatsApp adapter remain available as optional paths; Telegram does not use a public webhook or require Twilio credentials.

## Setup

Requires Python 3.11 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt  # optional focused tests
cp .env.example .env  # skip if .env already exists
```

Create a Telegram bot with BotFather and put its token in the local `.env` as `TELEGRAM_BOT_TOKEN`; keep `OPENAI_API_KEY` configured for study features. Do not paste the token into chat, commit it, or print it. SQLite and Chroma paths are controlled by `DATABASE_PATH` and `CHROMA_PATH`.

## Run Telegram

From the repository root, start the standalone long-polling process:

```sh
.venv/bin/python -m backend.app.telegram_bot
```

Open the bot in Telegram and send `/start` in a private chat. The bot replies with a welcome and upload instructions. Private-chat learners are scoped with IDs prefixed by `telegram:`. Telegram update IDs are stored in SQLite to ignore duplicate deliveries. Do not run multiple polling processes against the same bot token.

Run focused local checks with:

```sh
.venv/bin/python -m pytest -q
```

## FastAPI and optional Twilio

FastAPI remains available for `GET /health` and the signed Twilio webhook at `POST /webhooks/twilio` (also `/`). Start it with:

```sh
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Only the Twilio adapter needs `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, and `PUBLIC_BASE_URL`. To use it, expose port 8000 over HTTPS, then configure the exact public webhook URL in Twilio. Telegram long polling needs neither a tunnel nor `PUBLIC_BASE_URL`.

## Current scope

The Telegram bot accepts PDFs, notebook photos, and voice/audio files in private chats. It extracts selectable PDF text with page numbers, sends notebook images to the configured vision model, transcribes voice uploads, then stores learner-scoped source chunks in SQLite and explicit OpenAI embeddings in persistent ChromaDB. Upload replies include Summary, Flashcards, and Quiz buttons. Retrieval is learner-scoped and answers only from ready source text with page references; unsupported questions receive an explicit unsupported response. Quiz answers are scored in SQLite and repeated answers are rejected. `/start` and a PDF ingestion/reply have been verified live; buttons and other media types still need manual live checks.

PDFs are limited to 10 pages and 10 MB by default; scanned PDFs without selectable text are not OCR'd. Text and embedding defaults are `gpt-4.1-mini` and `text-embedding-3-small`. Change the corresponding OpenAI model variables only when the index is re-created for a new embedding model. Twilio webhook jobs remain process-local and are not a durable queue.

Never commit `.env`, private uploads, SQLite databases, Chroma files, or temporary media. The Telegram Bot API download URL contains the bot token, so the application must never log it.
