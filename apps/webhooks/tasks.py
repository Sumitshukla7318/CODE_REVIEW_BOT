import logging
from celery import shared_task
from django.utils import timezone
from apps.webhooks.models import WebhookEvent

logger = logging.getLogger(__name__)

ACCEPTED_ACTIONS = ['opened', 'synchronize', 'reopened']


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_webhook_event(self, webhook_event_id: str):
    """
    Task 1 in the chain.
    Validates the webhook event and triggers diff fetching.
    """
    from apps.webhooks.models import WebhookEvent

    try:
        event = WebhookEvent.objects.select_related('repository').get(
            id=webhook_event_id
        )
    except WebhookEvent.DoesNotExist:
        logger.error(f"WebhookEvent {webhook_event_id} not found")
        return

    try:
        # Mark as processing
        event.status = WebhookEvent.EventStatus.PROCESSING
        event.save(update_fields=['status'])

        # Validate action
        if event.action not in ACCEPTED_ACTIONS:
            event.status = WebhookEvent.EventStatus.FAILED
            event.error_message = f"Unsupported action: {event.action}"
            event.save(update_fields=['status', 'error_message'])
            return

        logger.info(
            f"Processing webhook event {webhook_event_id} "
            f"PR #{event.pr_number} action={event.action}"
        )

        # Chain to next task: fetch the diff
        from apps.reviews.tasks import fetch_pr_diff
        fetch_pr_diff.delay(str(event.id))

    except Exception as exc:
        logger.error(f"Error processing webhook event {webhook_event_id}: {exc}")
        event.status = WebhookEvent.EventStatus.FAILED
        event.error_message = str(exc)
        event.save(update_fields=['status', 'error_message'])
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)
    

@shared_task
def cleanup_old_webhook_logs():
    """
    Periodic task — runs daily at 2am.
    Deletes webhook events older than 30 days.
    """
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=30)
    deleted_count, _ = WebhookEvent.objects.filter(
        received_at__lt=cutoff,
        status__in=['COMPLETED', 'FAILED'],
    ).delete()

    logger.info(f"Cleaned up {deleted_count} old webhook events")
    return deleted_count