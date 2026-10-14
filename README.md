# StudyChat

StudyChat is a local-first WhatsApp study companion. This first backend slice exposes a health endpoint and a Twilio WhatsApp text webhook. For each new inbound text, it stores the Twilio message SID, responds promptly with empty TwiML, then sends a short acknowledgement through Twilio's REST API. Repeated delivery of the same SID does not send another reply.

## Run locally

Requires Python 3.11 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env with Twilio credentials and the public HTTPS URL below.
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Check `http://localhost:8000/health`; it should return `{"status":"ok"}`.

## Twilio testing setup

1. In the Twilio Console, open the WhatsApp Sandbox and join it from your WhatsApp account using the displayed join instructions.
2. Start a Cloudflare Quick Tunnel in another terminal: `cloudflared tunnel --url http://127.0.0.1:8000`.
3. Copy the temporary `https://….trycloudflare.com` URL printed by `cloudflared` into `PUBLIC_BASE_URL` (without a trailing slash), then restart Uvicorn so it loads the new value. Keep both processes running. Quick Tunnel URLs are temporary and anyone who has the URL can access the exposed service; they stop working when `cloudflared` exits. See [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
4. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_WHATSAPP_FROM` from the Twilio Console. Use the exact sender shown there, prefixed with `whatsapp:`.
5. Configure the Sandbox's **When a message comes in** webhook to `{PUBLIC_BASE_URL}/webhooks/twilio` with HTTP POST.
6. Send a WhatsApp text to the sandbox. The webhook validates `X-Twilio-Signature`, saves the message, returns empty TwiML, and sends the reply using the Twilio REST API.

Twilio requires replies outside its 24-hour customer service window to use an approved template; this demo's free-form acknowledgement is intended for an active testing conversation. See [Twilio's WhatsApp API guide](https://www.twilio.com/docs/whatsapp/api) and [webhook security guide](https://www.twilio.com/docs/usage/webhooks/webhooks-security).

## Configuration and current scope

`DATABASE_PATH` selects the local SQLite state file. Never commit `.env`, the database, or private uploads. The current reply is a connectivity acknowledgement; PDF, image, audio ingestion, AI study actions, progress, and quick replies have not been implemented. The inbound handler parses common media and button fields for the next ingestion slice but does not yet process them. Quick-reply support on this account has not been checked. Background tasks run in the single Uvicorn process and are not a durable queue.

## Next milestones

Add PDF extraction, learner-scoped material storage, explicit-embedding Chroma indexing, summaries, and grounded answers; then add quizzes, scoring, flashcards, and streaks.
