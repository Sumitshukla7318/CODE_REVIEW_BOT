from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ImproperlyConfigured


def validate_environment():
    """
    Validate all required environment variables on startup.
    Raises ImproperlyConfigured if any are missing.
    """
    from django.conf import settings
    import os

    required_vars = {
        'SECRET_KEY': settings.SECRET_KEY,
        'REDIS_URL': settings.REDIS_URL,
        'WEBHOOK_SECRET_ENCRYPTION_KEY': settings.WEBHOOK_SECRET_ENCRYPTION_KEY,
    }

    missing = []
    for var_name, value in required_vars.items():
        if not value:
            missing.append(var_name)

    if missing:
        raise ImproperlyConfigured(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please check your .env file."
        )

    # Warn about optional but recommended vars
    import logging
    logger = logging.getLogger(__name__)

    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set — AI reviews will fail")

    if not settings.GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not set — PR comments will be skipped")