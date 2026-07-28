import hashlib
import hmac
import logging

from config.app_config import settings

logger = logging.getLogger(__name__)


def verify_signature_ig(body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False

    try:
        sha_name, signature = signature_header.split("=")
    except ValueError:
        logger.warning("Invalid signature header format")
        return False

    if sha_name != "sha256":
        logger.warning("Unsupported signature type: %s", sha_name)
        return False

    expected = hmac.new(
        settings.INSTAGRAM_APP_SECRET.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)

def verify_signature_wp(body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False

    try:
        sha_name, signature = signature_header.split("=")
    except ValueError:
        logger.warning("Invalid signature header format")
        return False

    if sha_name != "sha256":
        logger.warning("Unsupported signature type: %s", sha_name)
        return False

    expected = hmac.new(
        settings.meta_app_secret.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)