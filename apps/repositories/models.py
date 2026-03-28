import uuid
from django.db import models
from apps.core.models import TimeStampedModel


class Repository(TimeStampedModel):
    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='repositories',
    )
    name = models.CharField(max_length=255)
    owner = models.CharField(max_length=255)
    full_name = models.CharField(max_length=512)
    github_url = models.URLField()
    webhook_secret = models.CharField(max_length=512)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'repositories'
        unique_together = ('user', 'full_name')
        ordering = ['-created_at']

    def __str__(self):
        return self.full_name