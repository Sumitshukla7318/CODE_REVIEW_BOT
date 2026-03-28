import uuid
from django.db import models
from apps.core.models import TimeStampedModel


class WebhookEvent(TimeStampedModel):

    class EventStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    repository = models.ForeignKey(
        'repositories.Repository',
        on_delete=models.CASCADE,
        related_name='webhook_events',
    )
    event_type = models.CharField(max_length=100)
    action = models.CharField(max_length=100)
    pr_number = models.IntegerField()
    pr_title = models.CharField(max_length=500)
    pr_author = models.CharField(max_length=255)
    head_sha = models.CharField(max_length=255)
    base_branch = models.CharField(max_length=255)
    head_branch = models.CharField(max_length=255)
    raw_payload = models.JSONField()
    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.PENDING,
    )
    error_message = models.TextField(blank=True, null=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'webhook_events'
        ordering = ['-received_at']

    def __str__(self):
        return f"PR #{self.pr_number} - {self.event_type} ({self.status})"