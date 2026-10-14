from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class IncomingMessage:
    message_sid: str
    sender: str
    body: str
    num_media: int
    media_url: str | None = None
    media_content_type: str | None = None
    button_payload: str | None = None
    button_text: str | None = None

    @classmethod
    def from_form(cls, form: Mapping[str, str]) -> "IncomingMessage":
        try:
            num_media = int(form.get("NumMedia", "0") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("NumMedia must be an integer") from exc

        message = cls(
            message_sid=str(form.get("MessageSid", "")).strip(),
            sender=str(form.get("From", "")).strip(),
            body=str(form.get("Body", "")),
            num_media=num_media,
            media_url=form.get("MediaUrl0"),
            media_content_type=form.get("MediaContentType0"),
            button_payload=form.get("ButtonPayload"),
            button_text=form.get("ButtonText"),
        )
        if not message.message_sid or not message.sender:
            raise ValueError("Missing MessageSid or From")
        return message
