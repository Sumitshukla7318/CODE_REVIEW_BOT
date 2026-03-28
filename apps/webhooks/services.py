import hashlib
import logging
from apps.webhooks.models import WebhookEvent

logger = logging.getLogger(__name__)


def get_repository_by_full_name(owner: str, repo: str):
    """Fetch repository from DB by owner and repo name."""
    from apps.repositories.models import Repository
    try:
        return Repository.objects.get(
            owner=owner,
            name=repo,
            is_active=True,
        )
    except Repository.DoesNotExist:
        return None


def verify_webhook_secret(payload: bytes, signature: str, encrypted_secret: str) -> bool:
    """
    Decrypt the stored secret and verify the GitHub webhook signature.
    """
    from apps.webhooks.validators import verify_github_signature
    from apps.repositories.services import decrypt_secret

    try:
        plain_secret = decrypt_secret(encrypted_secret)
        return verify_github_signature(payload, signature, plain_secret)
    except Exception as e:
        logger.error(f"Error decrypting webhook secret: {e}")
        return False

def parse_pr_webhook(payload: dict) -> dict:
    """
    Extract relevant fields from a GitHub pull_request webhook payload.
    Returns a clean dict with only what we need.
    """
    pr = payload.get('pull_request', {})
    repo = payload.get('repository', {})

    return {
        'action': payload.get('action', ''),
        'pr_number': payload.get('number', 0),
        'pr_title': pr.get('title', ''),
        'pr_author': pr.get('user', {}).get('login', ''),
        'head_sha': pr.get('head', {}).get('sha', ''),
        'base_branch': pr.get('base', {}).get('ref', ''),
        'head_branch': pr.get('head', {}).get('ref', ''),
        'repo_name': repo.get('name', ''),
        'repo_owner': repo.get('owner', {}).get('login', ''),
    }


def create_webhook_event(repository, parsed_data: dict, raw_payload: dict) -> WebhookEvent:
    """
    Create and save a WebhookEvent record in the database.
    """
    return WebhookEvent.objects.create(
        repository=repository,
        event_type='pull_request',
        action=parsed_data['action'],
        pr_number=parsed_data['pr_number'],
        pr_title=parsed_data['pr_title'],
        pr_author=parsed_data['pr_author'],
        head_sha=parsed_data['head_sha'],
        base_branch=parsed_data['base_branch'],
        head_branch=parsed_data['head_branch'],
        raw_payload=raw_payload,
        status=WebhookEvent.EventStatus.PENDING,
    )