from urllib.parse import urljoin, urlsplit

import httpx

from backend.app.config import Settings

_MEDIA_REDIRECT_HOSTS = {"mms.twiliocdn.com"}


def _is_twilio_api_host(host: str) -> bool:
    return host == "api.twilio.com" or (host.startswith("api.") and host.endswith(".twilio.com"))


async def download_twilio_media(settings: Settings, media_url: str, max_bytes: int) -> tuple[bytes, str]:
    parsed = urlsplit(media_url)
    if parsed.scheme != "https" or not parsed.hostname or not _is_twilio_api_host(parsed.hostname):
        raise ValueError("Twilio media URL is not an approved HTTPS Twilio host.")

    original_host = parsed.hostname.lower()
    url = media_url
    auth: httpx.BasicAuth | None = httpx.BasicAuth(
        settings.twilio_account_sid,
        settings.twilio_auth_token_value,
    )
    timeout = httpx.Timeout(20.0, connect=5.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for redirect_count in range(3):
            async with client.stream("GET", url, auth=auth) as response:
                if response.is_redirect:
                    if redirect_count >= 2:
                        raise ValueError("Twilio media redirected too many times.")
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Twilio media redirect did not include a target URL.")
                    next_url = urljoin(url, location)
                    target = urlsplit(next_url)
                    if target.scheme != "https" or not target.hostname:
                        raise ValueError("Twilio media redirect must use HTTPS.")
                    target_host = target.hostname.lower()
                    if target_host != original_host and target_host not in _MEDIA_REDIRECT_HOSTS:
                        raise ValueError("Twilio media redirected to an unapproved host.")
                    if target_host != original_host:
                        auth = None
                    url = next_url
                    continue

                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                declared_size = response.headers.get("content-length")
                if declared_size and int(declared_size) > max_bytes:
                    raise ValueError("PDF exceeds the configured upload size limit.")
                content = bytearray()
                async for part in response.aiter_bytes(64 * 1024):
                    content.extend(part)
                    if len(content) > max_bytes:
                        raise ValueError("PDF exceeds the configured upload size limit.")
                return bytes(content), content_type
    raise ValueError("Could not download the Twilio media file.")
