import asyncio
from types import SimpleNamespace

import pytest

from backend.app.config import Settings
from backend.app.database import connect
from backend.app.telegram_bot import WELCOME, build_application, claim_update, record_quiz_answer, send_quiz_question, start_command


def make_settings(tmp_path, **overrides):
    values = {
        "_env_file": None,
        "database_path": tmp_path / "studychat.sqlite3",
        "chroma_path": tmp_path / "chroma",
        "openai_api_key": "sk-test-only",
        "telegram_bot_token": "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
    }
    values.update(overrides)
    return Settings(**values)


def test_telegram_application_starts_without_twilio_configuration(tmp_path):
    settings = make_settings(tmp_path)

    application = build_application(settings)

    assert application.bot_data["settings"] is settings
    assert settings.public_base_url is None
    assert settings.twilio_configured is False
    assert "start" in application.handlers[0][0].commands


def test_start_replies_once_for_private_chat_and_persists_update(tmp_path):
    settings = make_settings(tmp_path)

    class Message:
        def __init__(self):
            self.replies = []

        async def reply_text(self, text):
            self.replies.append(text)

    message = Message()
    update = SimpleNamespace(
        update_id=1001,
        effective_message=message,
        effective_user=SimpleNamespace(id=4567),
        effective_chat=SimpleNamespace(type="private"),
    )
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"settings": settings}))

    asyncio.run(start_command(update, context))
    asyncio.run(start_command(update, context))

    assert message.replies == [WELCOME]
    with connect(settings) as db:
        row = db.execute("SELECT update_id, telegram_user_id FROM telegram_updates").fetchone()
    assert tuple(row) == (1001, "4567")


def test_update_claim_is_idempotent_and_user_ids_are_distinct(tmp_path):
    settings = make_settings(tmp_path)

    assert claim_update(settings, 77, 11) is True
    assert claim_update(settings, 77, 11) is False
    assert claim_update(settings, 78, 12) is True
    with connect(settings) as db:
        assert db.execute("SELECT COUNT(*) FROM telegram_updates").fetchone()[0] == 2


def test_build_application_requires_token_without_exposing_it(tmp_path):
    settings = make_settings(tmp_path, telegram_bot_token=None)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN is required") as error:
        build_application(settings)
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in str(error.value)


def test_quiz_question_includes_choices_and_stable_answer_callbacks():
    class Message:
        async def reply_text(self, text, reply_markup=None):
            self.text = text
            self.reply_markup = reply_markup

    message = Message()
    items = [{"question": "Which process changes liquid into vapor?", "choices": ["Evaporation", "Condensation", "Freezing"], "answer": 0, "explanation": "Heat causes evaporation."}]

    asyncio.run(send_quiz_question(message, 42, "quiz123", items, 0))

    assert "A. Evaporation" in message.text
    assert [button.text for button in message.reply_markup.inline_keyboard[0]] == ["A", "B", "C"]
    assert [button.callback_data for button in message.reply_markup.inline_keyboard[0]] == [
        "study:answer:quiz123:0:0", "study:answer:quiz123:0:1", "study:answer:quiz123:0:2"
    ]


def test_quiz_answer_scores_once_and_rejects_repeated_or_stale_actions(tmp_path):
    settings = make_settings(tmp_path)
    items = [
        {"question": f"Question {i+1}", "choices": ["A", "B", "C"], "answer": i % 3, "explanation": "Because."}
        for i in range(3)
    ]
    with connect(settings) as db:
        db.execute("INSERT INTO telegram_study_state(telegram_user_id, active_material_id, quiz_id, quiz_json) VALUES (?, ?, ?, ?)", ("42", "material", "quiz123", __import__("json").dumps(items)))

    result = record_quiz_answer(settings, 42, "quiz123", 0, 0)
    assert result is not None and result[1:] == (True, 1)
    assert record_quiz_answer(settings, 42, "quiz123", 0, 2) is None
    assert record_quiz_answer(settings, 42, "quiz123", 2, 2) is None
    with connect(settings) as db:
        state = db.execute("SELECT quiz_index, quiz_score FROM telegram_study_state WHERE telegram_user_id='42'").fetchone()
    assert tuple(state) == (1, 1)
