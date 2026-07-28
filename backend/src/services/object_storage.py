from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@dataclass(frozen=True)
class ObjectStorageConfig:
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    region: str = "auto"
    public_base_url: str = ""

    @property
    def configured(self) -> bool:
        return all([
            self.endpoint_url.strip(),
            self.access_key_id.strip(),
            self.secret_access_key.strip(),
            self.bucket.strip(),
        ])


_CYRILLIC_TRANSLIT = str.maketrans({
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "E", "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U", "Ф": "F", "Х": "H", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh", "Щ": "Sch", "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "Yu", "Я": "Ya",
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
})


def _split_extension(filename: str) -> tuple[str, str]:
    raw = filename.strip().replace("\\", "/").split("/")[-1]
    if "." not in raw:
        return raw, ".jpg"
    stem, ext = raw.rsplit(".", 1)
    ext = f".{ext.lower()}"
    if ext not in _ALLOWED_EXTENSIONS:
        return "file", ".jpg"
    return stem, ext


def sanitize_filename(filename: str) -> str:
    stem, ext = _split_extension(filename or "file.jpg")
    transliterated = stem.translate(_CYRILLIC_TRANSLIT)
    normalized = unicodedata.normalize("NFKD", transliterated).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    if not slug:
        slug = "file"
    return f"{slug[:80]}{ext}"


def build_object_key(*, company_id: uuid.UUID, folder: str, filename: str) -> str:
    safe_folder = re.sub(r"[^a-zA-Z0-9/_-]+", "-", folder.strip("/")) or "uploads"
    safe_filename = sanitize_filename(filename)
    return f"{safe_folder}/{company_id}/{uuid.uuid4()}-{safe_filename}"


def public_object_url(*, key: str, endpoint_url: str, bucket: str, public_base_url: str = "") -> str:
    clean_key = key.lstrip("/")
    if public_base_url.strip():
        return f"{public_base_url.rstrip('/')}/{clean_key}"
    return f"{endpoint_url.rstrip('/')}/{bucket.strip('/')}/{clean_key}"


def normalize_public_object_url(*, url: str | None, config: ObjectStorageConfig) -> str | None:
    if not url:
        return None

    value = url.strip()
    if not value or not config.public_base_url.strip():
        return value or None

    endpoint_prefix = f"{config.endpoint_url.rstrip('/')}/{config.bucket.strip('/')}/"
    public_prefix = f"{config.public_base_url.rstrip('/')}/"

    if value.startswith(public_prefix):
        return value
    if value.startswith(endpoint_prefix):
        return f"{public_prefix}{value[len(endpoint_prefix):].lstrip('/')}"

    return value


def content_type_for_filename(filename: str, fallback: str = "application/octet-stream") -> str:
    _, ext = _split_extension(filename)
    return _MIME_BY_EXT.get(ext, fallback)


def config_from_settings(settings: Any) -> ObjectStorageConfig:
    return ObjectStorageConfig(
        endpoint_url=getattr(settings, "object_storage_endpoint_url", ""),
        access_key_id=getattr(settings, "object_storage_access_key_id", ""),
        secret_access_key=getattr(settings, "object_storage_secret_access_key", ""),
        bucket=getattr(settings, "object_storage_bucket", ""),
        region=getattr(settings, "object_storage_region", "auto"),
        public_base_url=getattr(settings, "object_storage_public_base_url", ""),
    )


def upload_bytes_to_object_storage(
    *,
    config: ObjectStorageConfig,
    key: str,
    content: bytes,
    content_type: str,
) -> str:
    if not config.configured:
        raise RuntimeError("Cloudflare R2 storage is not configured")
    try:
        import boto3  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - dependency failure path
        raise RuntimeError("boto3 is required for Cloudflare R2 uploads") from exc

    client: Any = boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=config.region or "auto",
    )
    client.put_object(
        Bucket=config.bucket,
        Key=key,
        Body=content,
        ContentType=content_type,
        CacheControl="public, max-age=31536000, immutable",
    )
    logger.info("Uploaded object to R2 bucket=%s key=%s content_type=%s size=%s", config.bucket, key, content_type, len(content))
    return public_object_url(
        key=key,
        endpoint_url=config.endpoint_url,
        bucket=config.bucket,
        public_base_url=config.public_base_url,
    )
