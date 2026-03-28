from rest_framework import serializers
from apps.webhooks.models import WebhookEvent


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEvent
        fields = (
            'id', 'repository', 'event_type', 'action',
            'pr_number', 'pr_title', 'pr_author',
            'head_sha', 'base_branch', 'head_branch',
            'status', 'error_message',
            'received_at', 'processed_at',
        )
        read_only_fields = fields