# StudyChat

StudyChat is a local-first WhatsApp study companion. The backend exposes a health endpoint, a signed Twilio WhatsApp webhook, and a PDF study loop. New inbound message SIDs are persisted and deduplicated before returning empty TwiML; replies are sent afterward through Twilio's REST API. PDF uploads are downloaded from Twilio, extracted with page numbers, saved in SQLite, embedded with OpenAI, indexed in persistent ChromaDB, and summarized.

## Run locally

Requires Python 3.11 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt  # focused tests
test -f .env || cp .env.example .env
# Fill in .env with Twilio/OpenAI credentials and the public HTTPS URL below.
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Check `http://localhost:8000/health`; it should return `{"status":"ok"}`. Run focused checks with `python -m pytest -q`.

## Twilio testing setup

1. In the Twilio Console, open the WhatsApp Sandbox and join it from your WhatsApp account using the displayed join instructions.
2. Start a Cloudflare Quick Tunnel in another terminal: `cloudflared tunnel --url http://127.0.0.1:8000`.
3. Copy the temporary `https://….trycloudflare.com` URL printed by `cloudflared` into `PUBLIC_BASE_URL` (without a trailing slash), then restart Uvicorn so it loads the new value. Keep both processes running. Quick Tunnel URLs are temporary and anyone who has the URL can access the exposed service; they stop working when `cloudflared` exits. See [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
4. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_WHATSAPP_FROM` from the Twilio Console. Use the exact sender shown there, prefixed with `whatsapp:`.
5. Configure the Sandbox's **When a message comes in** webhook to `{PUBLIC_BASE_URL}/webhooks/twilio` with HTTP POST. The API also accepts the root path if that is already configured.
6. Send a WhatsApp text to the sandbox. The webhook validates `X-Twilio-Signature`, saves the message, returns empty TwiML, and sends the reply using the Twilio REST API.

Twilio requires replies outside its 24-hour customer service window to use an approved template; this demo's free-form acknowledgement is intended for an active testing conversation. See [Twilio's WhatsApp API guide](https://www.twilio.com/docs/whatsapp/api) and [webhook security guide](https://www.twilio.com/docs/usage/webhooks/webhooks-security).

## Configuration and current scope

`DATABASE_PATH` selects SQLite state and `CHROMA_PATH` selects the persistent vector index. Configuration defaults to `gpt-4.1-mini` for text and `text-embedding-3-small` for embeddings. The OpenAI account's availability for these models was checked during implementation. Use `MAX_PDF_PAGES` and `MAX_PDF_BYTES` to tune the default 10-page and 10 MB PDF limits. Text-based PDFs are supported; scanned PDFs without selectable text are rejected with an explanation. Summary context is bounded by `MAX_CONTEXT_CHARS`.

To study, send one PDF to the sandbox. StudyChat replies with a concise summary and stores page-aware source text. Ask a follow-up question in WhatsApp to retrieve relevant text from that sender's ready materials. Answers include backend-generated page references; if the material does not support an answer, StudyChat says so. Vector search filters by learner in Chroma, then verifies ready source text against SQLite before answering. Chroma records its embedding provider/model/dimension and rejects incompatible index queries; changing the embedding model requires re-indexing.

Never commit `.env`, the database, Chroma files, or private uploads. Notebook photos, audio ingestion, quizzes, flashcards, progress, and quick replies are not implemented. Quick-reply support on this account has not been checked. Background tasks run in the single Uvicorn process and are not a durable queue.

## Next milestones

Add quizzes, scoring, flashcards, and streaks; then implement photo and voice-note ingestion.
