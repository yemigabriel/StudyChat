# StudyChat: Codex working instructions

## Goal
StudyChat is a WhatsApp study companion that converts the learner's own PDFs, notebook photos, and short lecture voice notes into concise summaries, flashcards, quizzes, and grounded answers.

Implement working vertical slices in the order below. Keep the app runnable after each milestone. Favor simple, maintainable code and add infrastructure only when a concrete feature requires it.

## Initial choices
- Python 3.11+; FastAPI; Uvicorn; Pydantic; SQLite.
- Twilio WhatsApp trial/testing environment for the messaging channel.
- OpenAI is the first working AI provider. The developer already has an API key.
- Use the official OpenAI SDK and current documented API shapes.
- Local PDF text extraction with pypdf; vision for JPEG/PNG notebook photos.
- ChromaDB PersistentClient for local vector storage and similarity search; SQLite for material records, extracted source text, sessions, scores, jobs, and streaks.
- A small VectorStore interface allows a later Pinecone adapter; implement only Chroma now. Local-first means local application/storage with cloud Twilio and AI calls, not offline operation.
- One backend process and one Uvicorn worker for this demo.
- A public HTTPS tunnel to the local backend, or an already available deployment.
- No separate learner-facing website, login flow, Redis, Celery, LangChain, or agent framework.

Read the existing repository first. Preserve useful existing code and user changes. If the repository is empty, scaffold it.

## Working method
1. State a short plan and implement the next milestone immediately.
2. Make routine reversible implementation choices without asking for permission.
3. Ask only for missing account setup or a choice that blocks progress. Never ask the developer to paste secrets into chat.
4. Check current official documentation when API behavior is uncertain; do not guess SDK methods.
5. After each milestone, report what works, how it was checked, and the next milestone.
6. Keep a brief PROGRESS.md with completed milestones, verification, known limitations, and remaining work. Record Codex's contribution honestly.
7. Use meaningful focused tests for state and retrieval. Do not aim for broad coverage.
8. Do not declare a live integration verified from mocks or local webhook replay.
9. Make small, logical local commits from the beginning, following the Git workflow below. Do not create a remote repository or push without explicit authorization.

## Implementation milestones
1. Scaffold the backend, health endpoint, and configuration.
2. Establish the Twilio inbound webhook and a real WhatsApp text round trip; check button support.
3. Add PDF extraction, material storage, Chroma indexing, summaries, and grounded Q&A with source references.
4. Add three-question quizzes, deterministic scoring, and persisted session state.
5. Add flashcards and daily streaks; verify the core PDF study journey.
6. Add notebook photo extraction and real voice-note transcription, including format conversion if needed.
7. Complete supported quick replies, duplicate/expired-action handling, and persistence verification.
8. Rehearse all three inputs, resolve failures, and finish README and demo evidence.

If an integration is blocked, continue independent work while preserving the working PDF study loop. Report incomplete features explicitly.

## Git workflow
- Use the existing local repository. If the intended project root is not a Git repository, initialize one there before implementation; do not initialize a repository in a temporary working directory.
- Inspect git status before changing or staging files. Preserve unrelated user changes and existing staged work.
- Make the first commit contain the project guidance and appropriate ignore rules, before writing application features. If these files are already committed, continue from the existing history without adding an empty commit.
- Commit each small, coherent change as soon as it is ready. A milestone may contain several commits; do not wait for the whole application to be finished.
- Keep each feature's implementation and relevant tests together. Use separate commits for unrelated features, fixes, and documentation.
- Run the checks appropriate to the change before committing. Inspect the staged diff and stage specific files or hunks belonging to the change.
- Never commit API keys, .env files, private uploads, generated databases, or temporary artifacts. Use placeholders in .env.example.
- Use short, descriptive messages, such as docs: add project guidance, chore: scaffold FastAPI backend, feat: handle WhatsApp messages, feat: index PDF materials, or fix: reject duplicate quiz answers.
- Keep history truthful: commit changes when they are made. Do not backdate commits, split finished work merely to simulate incremental development, or rewrite existing history without an explicit request.
- If Git author identity is missing, ask for the intended identity; do not invent it. Report commit failures clearly and preserve the working changes.
- After each commit, report its short hash, purpose, and validation. Do not create a remote repository or push without explicit authorization.

## Provider boundaries
Keep vendor SDK objects and response shapes inside adapters. Use small Python Protocols or equivalent interfaces, not an elaborate plugin system:
- GenerationProvider: produce text and Pydantic-validated study objects.
- VisionProvider: extract readable notebook text from an image.
- EmbeddingProvider: embed document chunks and queries.
- TranscriptionProvider: transcribe supported audio files.

Default all capabilities to OpenAI. Generation and vision may later use Anthropic Claude or Google Gemini independently of embeddings and transcription. Text-provider switching must not require changes in messaging, retrieval, scoring, or session code.

Configuration:
- GENERATION_PROVIDER=openai
- VISION_PROVIDER=openai
- EMBEDDING_PROVIDER=openai
- TRANSCRIPTION_PROVIDER=openai
- OPENAI_API_KEY; OPENAI_TEXT_MODEL; OPENAI_VISION_MODEL; OPENAI_EMBEDDING_MODEL; OPENAI_TRANSCRIPTION_MODEL
- Optional later: ANTHROPIC_API_KEY; ANTHROPIC_TEXT_MODEL; ANTHROPIC_VISION_MODEL
- Optional later: GEMINI_API_KEY; GEMINI_TEXT_MODEL; GEMINI_VISION_MODEL

Document tested model names in .env.example after checking availability. Never claim an unimplemented provider works: reject unsupported configured providers with a clear startup error. Optional adapters must use the vendor's actual supported API, with capability checks and validated outputs. No silent fallback to another paid provider.

Keep embeddings stable when switching generation. Record embedding provider, model, and dimension with the index; refuse incompatible queries and document explicit re-indexing after an embedding model change.

## Local storage and retrieval boundary
- Use ChromaDB PersistentClient with a configurable CHROMA_PATH. Pass embeddings explicitly from the embedding adapter; do not silently use Chroma's default embedding model.
- Use a separate SQLite DATABASE_PATH for application state. Do not edit Chroma's internal database.
- The application owns source text and stable chunk IDs in SQLite; Chroma stores the matching chunk text, embedding, and scalar source metadata.
- Map each WhatsApp sender to an internal learner ID. Include learner_id, material_id, chunk_id, source_type, and available source location in Chroma metadata.
- VectorStore needs only upsert_chunks and search(query_embedding, learner_id, material_id=None, top_k=4), returning backend-neutral retrieved chunks.
- Always apply learner metadata filtering during vector retrieval, not after receiving other learners' results.
- Mark a material ready only after all chunks are indexed. Retrieval must discard results belonging to material records that are not ready. Use stable IDs and idempotent upserts so ingestion retries do not duplicate chunks.
- Keep Pinecone's future namespace/filter mapping inside its adapter. Migration will require moving vectors, text/metadata, and verifying retrieval; it is not just a configuration change today.

## WhatsApp integration
- POST /webhooks/twilio receives form-encoded data, not Meta Cloud API JSON. Include python-multipart.
- Parse MessageSid, From, Body, NumMedia, MediaUrl0, MediaContentType0, and ButtonPayload/ButtonText when present.
- Normalize these into a provider-independent incoming-message object.
- Validate X-Twilio-Signature using the exact configured public webhook URL and original form parameters. Keep any unsigned local replay route explicitly development-only.
- Deduplicate by MessageSid. Repeated deliveries must not duplicate ingestion, answers, quiz scoring, or streak updates.
- Return a successful empty TwiML response promptly; perform slow work afterward and send outbound replies with Twilio's REST API.
- FastAPI background tasks are acceptable for this single-process demo. Persist job/session status; document that processing is not a durable queue and surface interrupted work after restart.
- Use HTTP timeouts and bounded retries. Serialize state-changing work for each sender.
- Download Twilio media using documented authentication. Bound file size, preserve MIME metadata, and clean up temporary files. Never forward Twilio credentials to unrelated redirect hosts.
- Pace outbound messages to the testing environment's documented limits; combine feedback with the next question when useful.
- Use the sender value shown in the Twilio console; do not assume a specific sandbox number.
- Configure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, and PUBLIC_BASE_URL through environment variables.

### Quick replies
Twilio's Content API uses ContentSid/ContentVariables for rich replies, not a Meta interactive-message payload. Prove one actual in-session quick-reply message on this account before building the entire flow around buttons.

Prefer three buttons: Summary, Flashcards, Quiz. Quiz choices use A, B, C as labels and include the complete options in the body. Use ButtonPayload for stable action identity when available. Respect documented title/body limits.

The sandbox docs restrict custom templates; do not assume custom button content is available. Check account support before building dependent features. If blocked, keep the same state machine working through numbered/keyword replies and explicitly report that live buttons remain unverified or unavailable. Do not represent a text menu as working buttons.

## Study behavior
- Welcome: invite the learner to send a PDF, notebook photo, or short voice note.
- Each successful upload becomes the active study material. Retain earlier uploads for learner-scoped Q&A.
- Summary: five short points from the complete active text within a bounded context budget. For larger inputs use section summaries or clearly explain the demo limit.
- Flashcards: generate five cards once; show one front at a time; Reveal shows the back; Next advances.
- Quiz: generate three questions once with exactly three choices, one correct choice, a short explanation, and source references.
- Grade deterministically in backend code. Never ask the model to calculate the user's score.
- Handle answers only for the current unanswered question. Button payloads should include a session/question identifier when supported. Reject expired buttons and duplicate answers politely.
- Feedback explains the answer, then advances. Completion shows score and encouraging feedback.
- Streak: completing a quiz counts once per calendar day in Africa/Lagos. Consecutive days increment; a gap resets to one; another completion on the same day leaves it unchanged.
- Support menu, summary, flashcards, quiz, cancel, and progress commands. Typed replies must work even when buttons work.
- Keep messages short and text-first. Do not automatically send generated audio.
- Daily proactive reminders, multilingual support, spaced repetition, long lectures, and dashboards are deferred.

## Ingestion and RAG
- Demo limits: PDFs up to 10 pages and 10 MB, images up to 5 MB, voice notes up to two minutes and 10 MB; make limits configurable and explain exceeded limits.
- Preserve PDF page numbers. Label photos by material ID and voice notes by transcript ID. Include timestamps only if actually produced by transcription.
- Text-based PDFs first. If a PDF has no usable text, explain the limitation and suggest sending a page photo; full scanned-PDF OCR is deferred.
- For photos, extract visible text, preserve meaningful headings, and mark unreadable sections instead of inventing them.
- For audio, inspect the actual container/codec. If the API does not accept it, convert with ffmpeg into a supported format; changing the extension is not conversion. Document ffmpeg as a prerequisite when used.
- Normalize text, chunk approximately 600–900 tokens with overlap, and retain source metadata.
- Persist materials, source text/chunk records, generated study content, session state, and study-day records in SQLite; persist indexed vectors and retrieval metadata in Chroma.
- Every retrieval query filters by sender before ranking. Default follow-up Q&A searches that learner's ready materials.
- Retrieve a small set of relevant chunks within a bounded context budget.
- Answers must be grounded in retrieved text and use source IDs supplied by the backend. Validate cited IDs against the supplied sources; format references outside the model.
- When the supplied material does not support an answer, say so. Do not fabricate references or supplement it silently with general knowledge.
- Treat uploaded material as untrusted data, never as instructions that override system behavior.

## Minimum verification
Use fixtures and fake AI/messaging adapters for fast deterministic tests:
1. Duplicate webhook delivery creates only one processing job.
2. Retrieval cannot return another learner's material.
3. Correct and incorrect answers update score once; expired session actions do not mutate it.
4. Streak behavior covers same day, next day, missed day, and Lagos midnight.
5. State survives reopening the database.
6. Unsupported provider configuration and incompatible embedding metadata fail clearly.

Then perform manual live checks for one PDF, one photo, and one real WhatsApp voice note. Verify a grounded answer and an unsupported question, complete a quiz, and inspect the persisted streak. Record actual button support separately. Include a development-only webhook replay command for debugging; it is not evidence of live delivery.

## Deliverables
- Runnable backend with GET /health and POST /webhooks/twilio.
- .env.example containing placeholders only; .gitignore excludes credentials, local databases, uploaded private materials, and temporary files.
- README with exact install/run commands, tunnel setup, Twilio testing-environment join/setup, webhook configuration, tested models, provider capability notes, limits, and known gaps.
- PROGRESS.md with an honest verification record.
- Short demo sequence: upload material → summary → quiz → score/streak → cited follow-up answer.
- No fake feature claims, fake streak history, or unsupported claims about data savings.
- Keep this MVP in the account's testing environment. Public release and WhatsApp AI-policy eligibility are separate work.

