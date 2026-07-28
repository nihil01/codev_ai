from __future__ import annotations

import logging
import mimetypes
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx

from services.openai_messaging import transcribe_audio_bytes
from services.security import validate_voice_duration, validate_audio_size, MAX_VOICE_DURATION_SECONDS

logger = logging.getLogger(__name__)

AUDIO_MIME_PREFIXES = ("audio/",)
VOICE_MESSAGE_TYPES = {"audio", "voice", "ptt", "voice_message", "ogg", "m4a", "mp3", "opus"}
URL_KEYS = ("url", "downloadUrl", "download_url", "mediaUrl", "media_url", "href", "link")


def is_audio_message_type(message_type: str | None) -> bool:
    normalized = str(message_type or "").strip().lower()
    return normalized in VOICE_MESSAGE_TYPES or normalized.startswith("audio")


def extract_voice_duration(payload):
    # type: (Mapping[str, Any]) -> float | None
    # Extract voice message duration from payload in seconds.
    for item in _walk_mappings(payload):
        duration = item.get("duration") or item.get("duration_ms") or item.get("voice_duration")
        if duration is not None:
            try:
                dur = float(duration)
                # If duration is in milliseconds, convert to seconds
                if dur > 1000:
                    dur = dur / 1000
                return dur
            except (ValueError, TypeError):
                continue
    return None


def _walk_mappings(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        nested = [value]
        for item in value.values():
            nested.extend(_walk_mappings(item))
        return nested
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        nested: list[Mapping[str, Any]] = []
        for item in value:
            nested.extend(_walk_mappings(item))
        return nested
    return []


def extract_audio_url(payload: Mapping[str, Any]) -> str | None:
    for item in _walk_mappings(payload):
        mime_type = str(item.get("mime_type") or item.get("mimeType") or item.get("content_type") or "").lower()
        item_type = str(item.get("type") or item.get("media_type") or item.get("message_type") or "").lower()
        looks_audio = mime_type.startswith(AUDIO_MIME_PREFIXES) or is_audio_message_type(item_type)
        if not looks_audio:
            continue
        for key in URL_KEYS:
            value = item.get(key)
            if value:
                return str(value)
    return None


def extract_whatsapp_cloud_audio_media_id(message: Mapping[str, Any]) -> str | None:
    message_type = str(message.get("type") or "").lower()
    if message_type not in {"audio", "voice"}:
        return None
    audio = message.get("audio")
    if isinstance(audio, Mapping) and audio.get("id"):
        return str(audio["id"])
    return None


async def download_url_bytes(url: str, *, headers: Mapping[str, str] | None = None, max_bytes: int = 25 * 1024 * 1024) -> tuple[bytes, str | None, str]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url, headers=dict(headers or {}))
    response.raise_for_status()
    content = response.content
    if len(content) > max_bytes:
        raise ValueError("Audio file is too large for transcription")
    content_type = response.headers.get("content-type")
    suffix = Path(url.split("?", 1)[0]).suffix or mimetypes.guess_extension(content_type or "") or ".ogg"
    return content, content_type, suffix


async def transcribe_audio_url(url: str, *, headers: Mapping[str, str] | None = None) -> str | None:
    try:
        audio_bytes, content_type, suffix = await download_url_bytes(url, headers=headers)

        # Validate audio size
        if not validate_audio_size(len(audio_bytes)):
            logger.warning("Audio file too large: %d bytes", len(audio_bytes))
            return None

        return transcribe_audio_bytes(audio_bytes, filename=f"voice{suffix}", content_type=content_type)
    except Exception:
        logger.exception("Audio URL transcription failed url=%s", url)
        return None


async def transcribe_whatsapp_cloud_audio(message: Mapping[str, Any], *, access_token: str) -> str | None:
    media_id = extract_whatsapp_cloud_audio_media_id(message)
    if not media_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            media_response = await client.get(
                f"https://graph.facebook.com/v25.0/{media_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        media_response.raise_for_status()
        media_url = str(media_response.json().get("url") or "")
        if not media_url:
            return None
        return await transcribe_audio_url(media_url, headers={"Authorization": f"Bearer {access_token}"})
    except Exception:
        logger.exception("WhatsApp Cloud voice transcription failed media_id=%s", media_id)
        return None
