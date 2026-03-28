import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify GitHub webhook signature using HMAC-SHA256.
    GitHub sends: X-Hub-Signature-256: sha256=<hash>
    We compare it against HMAC(secret, payload).
    """
    if not signature or not secret:
        return False

    try:
        sig_parts = signature.split('=', 1)
        if len(sig_parts) != 2 or sig_parts[0] != 'sha256':
            return False

        expected = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, sig_parts[1])
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False