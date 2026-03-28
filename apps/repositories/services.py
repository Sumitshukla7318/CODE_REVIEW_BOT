import secrets
from cryptography.fernet import Fernet
from django.conf import settings


def get_fernet():
    """Get Fernet encryption instance using the secret key."""
    key = settings.WEBHOOK_SECRET_ENCRYPTION_KEY
    if not key:
        raise ValueError("WEBHOOK_SECRET_ENCRYPTION_KEY is not set in environment.")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plain_secret: str) -> str:
    """Encrypt a plain secret for storage."""
    f = get_fernet()
    return f.encrypt(plain_secret.encode()).decode()


def decrypt_secret(encrypted_secret: str) -> str:
    """Decrypt a stored secret back to plain text."""
    f = get_fernet()
    return f.decrypt(encrypted_secret.encode()).decode()


def generate_webhook_secret() -> tuple:
    """
    Generate a secure random webhook secret.
    Returns (plain_secret, encrypted_secret).
    Plain secret is shown once to user.
    Encrypted secret is stored in DB.
    """
    plain_secret = secrets.token_hex(32)
    encrypted = encrypt_secret(plain_secret)
    return plain_secret, encrypted


def rotate_webhook_secret(repository) -> tuple:
    """
    Generate a new webhook secret for a repository.
    Returns (repository, plain_secret).
    """
    plain_secret, encrypted = generate_webhook_secret()
    repository.webhook_secret = encrypted
    repository.save(update_fields=['webhook_secret', 'updated_at'])
    return repository, plain_secret