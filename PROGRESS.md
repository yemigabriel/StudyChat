# Progress

## Completed

- Added FastAPI health checks, validated configuration, a signed Twilio webhook, Twilio REST replies, and optional Twilio PDF handling. Twilio remains available but is not the MVP channel because the account's trial blocked generated outbound replies.
- Added PDF extraction with page numbers, SQLite source persistence, explicit OpenAI embeddings, persistent ChromaDB indexing, concise summaries, and learner-filtered grounded retrieval with source references.
- Added standalone Telegram long polling with private-chat `/start`, channel-prefixed learner identities, persistent update deduplication, and safe logging that suppresses Telegram Bot API URLs.
- Added Telegram PDF ingestion, notebook-photo text extraction, audio transcription, persistent source indexing, summary/flashcard/quiz actions, one-at-a-time flashcards, and quiz state/scoring with duplicate-answer rejection.

## Verification

- `.venv/bin/python -m pytest -q`: 24 passed. One third-party Chroma deprecation warning remains.
- Started Telegram long polling with the local token. A real private `/start` update was received and its welcome reply completed successfully; the process logged `Handled Telegram /start update`.
- The user sent a real PDF to the bot. The bot indexed it, sent a ready confirmation, and the SQLite store showed one ready PDF material. The PDF content was not printed or inspected in the verification output.
- Live Summary, Flashcards generation/reveal/advance, Quiz generation, and three answer scores were verified on the uploaded PDF. The completed quiz persisted 2/3. The last answer feedback now precedes a separate completion/score message; quiz and flashcard progress indicators are added and covered by tests. A repeated quiz answer has local test coverage but a manual live retap remains unverified. Button-action logs record actions and quiz outcomes without logging user content.
- Earlier OpenAI synthetic-PDF checks verified embedding, summary, learner-scoped retrieval, supported answers with references, and an unsupported answer. Earlier Cloudflare `/health` and Twilio inbound delivery checks are recorded in the Git history; Twilio outbound remained blocked by the trial restriction.

## Limitations and remaining work

- Keep Telegram startup separate from FastAPI: run only one polling process per bot token. Telegram needs neither Twilio credentials nor `PUBLIC_BASE_URL`.
- Flashcard and quiz generation use bounded ready source text from the active learner-owned material.
- Live notebook-photo and voice-note checks remain outstanding. A live grounded/unsupported follow-up and repeated quiz-answer retap also remain to be checked.
- Voice transcription requires the configured OpenAI transcription capability and compatible uploaded audio encoding. Scanned PDFs remain unsupported; use a photo of a page instead.
- SQLite and Chroma are local persistent stores. The Twilio FastAPI background-task path remains process-local and is not a durable queue.
