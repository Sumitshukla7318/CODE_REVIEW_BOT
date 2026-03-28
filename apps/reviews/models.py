import uuid
from django.db import models
from apps.core.models import TimeStampedModel


class PRDiff(TimeStampedModel):
    webhook_event = models.OneToOneField(
        'webhooks.WebhookEvent',
        on_delete=models.CASCADE,
        related_name='pr_diff',
    )
    files_changed = models.JSONField(default=list)
    total_additions = models.IntegerField(default=0)
    total_deletions = models.IntegerField(default=0)
    filtered_files = models.JSONField(default=list)
    raw_diff = models.TextField(blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pr_diffs'

    def __str__(self):
        return f"Diff for PR #{self.webhook_event.pr_number}"


class CodeReview(TimeStampedModel):

    class ReviewStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    webhook_event = models.OneToOneField(
        'webhooks.WebhookEvent',
        on_delete=models.CASCADE,
        related_name='code_review',
    )
    pr_diff = models.OneToOneField(
        PRDiff,
        on_delete=models.CASCADE,
        related_name='code_review',
    )
    repository = models.ForeignKey(
        'repositories.Repository',
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    summary = models.TextField(blank=True)
    overall_score = models.IntegerField(default=0)
    approved = models.BooleanField(default=False)
    model_used = models.CharField(max_length=100, default='llama-3.1-8b-instant')
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    error_message = models.TextField(blank=True, null=True)
    ai_raw_response = models.TextField(blank=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'code_reviews'
        ordering = ['-created_at']

    def __str__(self):
        return f"Review for PR #{self.webhook_event.pr_number} ({self.status})"


class ReviewIssue(TimeStampedModel):

    class Severity(models.TextChoices):
        CRITICAL = 'critical', 'Critical'
        WARNING = 'warning', 'Warning'
        SUGGESTION = 'suggestion', 'Suggestion'

    class IssueType(models.TextChoices):
        SECURITY = 'security', 'Security'
        PERFORMANCE = 'performance', 'Performance'
        STYLE = 'style', 'Style'
        LOGIC = 'logic', 'Logic'
        BUG = 'bug', 'Bug'

    review = models.ForeignKey(
        CodeReview,
        on_delete=models.CASCADE,
        related_name='issues',
    )
    file_path = models.CharField(max_length=500)
    line_number = models.IntegerField(blank=True, null=True)
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
    )
    issue_type = models.CharField(
        max_length=20,
        choices=IssueType.choices,
    )
    message = models.TextField()
    suggestion = models.TextField()

    class Meta:
        db_table = 'review_issues'
        ordering = ['severity', 'file_path']

    def __str__(self):
        return f"{self.severity} in {self.file_path}"