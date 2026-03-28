from rest_framework import serializers
from apps.reviews.models import CodeReview, ReviewIssue, PRDiff


class ReviewIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewIssue
        fields = (
            'id', 'file_path', 'line_number',
            'severity', 'issue_type',
            'message', 'suggestion', 'created_at',
        )
        read_only_fields = fields


class CodeReviewSerializer(serializers.ModelSerializer):
    issues = ReviewIssueSerializer(many=True, read_only=True)
    repository_name = serializers.CharField(
        source='repository.full_name',
        read_only=True,
    )
    pr_number = serializers.IntegerField(
        source='webhook_event.pr_number',
        read_only=True,
    )
    pr_title = serializers.CharField(
        source='webhook_event.pr_title',
        read_only=True,
    )

    class Meta:
        model = CodeReview
        fields = (
            'id', 'repository_name', 'pr_number', 'pr_title',
            'summary', 'overall_score', 'approved',
            'model_used', 'prompt_tokens', 'completion_tokens',
            'status', 'error_message',
            'issues', 'created_at', 'completed_at',
        )
        read_only_fields = fields


class CodeReviewListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list view — no issues included."""
    repository_name = serializers.CharField(
        source='repository.full_name',
        read_only=True,
    )
    pr_number = serializers.IntegerField(
        source='webhook_event.pr_number',
        read_only=True,
    )

    class Meta:
        model = CodeReview
        fields = (
            'id', 'repository_name', 'pr_number',
            'overall_score', 'approved', 'status',
            'created_at', 'completed_at',
        )
        read_only_fields = fields