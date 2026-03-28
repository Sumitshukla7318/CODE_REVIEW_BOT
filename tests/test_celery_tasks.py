import pytest
from unittest.mock import patch, MagicMock
from tests.factories import (
    WebhookEventFactory,
    PRDiffFactory,
    CodeReviewFactory,
)
from apps.webhooks.models import WebhookEvent
from apps.reviews.models import CodeReview


@pytest.mark.django_db
class TestProcessWebhookEvent:

    @patch('apps.reviews.tasks.fetch_pr_diff.delay')
    def test_valid_event_triggers_fetch(self, mock_fetch):
        event = WebhookEventFactory(action='opened')
        from apps.webhooks.tasks import process_webhook_event
        process_webhook_event(str(event.id))
        event.refresh_from_db()
        assert mock_fetch.called is True

    def test_invalid_action_fails_event(self):
        event = WebhookEventFactory(action='closed')
        from apps.webhooks.tasks import process_webhook_event
        process_webhook_event(str(event.id))
        event.refresh_from_db()
        assert event.status == WebhookEvent.EventStatus.FAILED

    def test_nonexistent_event_does_not_crash(self):
        from apps.webhooks.tasks import process_webhook_event
        process_webhook_event('00000000-0000-0000-0000-000000000000')


@pytest.mark.django_db
class TestPerformAiReview:

    @patch('apps.reviews.services.call_groq_api')
    @patch('apps.reviews.github.post_review_comment')
    def test_successful_review(self, mock_comment, mock_groq):
        mock_groq.return_value = {
            'content': '{"summary": "Good PR", "issues": [], "score": 90, "approved": true}',
            'prompt_tokens': 100,
            'completion_tokens': 50,
            'model': 'llama-3.1-8b-instant',
        }
        mock_comment.return_value = True

        diff = PRDiffFactory()
        from apps.reviews.tasks import perform_ai_review
        perform_ai_review(str(diff.id))

        review = CodeReview.objects.get(webhook_event=diff.webhook_event)
        assert review.status == CodeReview.ReviewStatus.COMPLETED
        assert review.overall_score == 90
        assert review.approved is True

    @patch('apps.reviews.services.call_groq_api')
    @patch('apps.reviews.github.post_review_comment')
    def test_failed_groq_call_marks_review_failed(self, mock_comment, mock_groq):
        import requests
        mock_groq.side_effect = requests.exceptions.RequestException('API Error')
        mock_comment.return_value = False

        diff = PRDiffFactory()
        from apps.reviews.tasks import perform_ai_review

        with pytest.raises(Exception):
            perform_ai_review(str(diff.id))

        review = CodeReview.objects.get(webhook_event=diff.webhook_event)
        assert review.status == CodeReview.ReviewStatus.FAILED

    def test_nonexistent_diff_does_not_crash(self):
        from apps.reviews.tasks import perform_ai_review
        perform_ai_review('00000000-0000-0000-0000-000000000000')