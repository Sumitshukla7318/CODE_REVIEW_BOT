import json
import logging

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.webhooks.models import WebhookEvent
from apps.webhooks.serializers import WebhookEventSerializer
from apps.webhooks.services import (
    get_repository_by_full_name,
    parse_pr_webhook,
    create_webhook_event,
)
from apps.webhooks.validators import verify_github_signature

logger = logging.getLogger(__name__)


class GithubWebhookView(APIView):
    """
    Receives GitHub webhook events for pull requests.
    Verifies HMAC signature, stores event, dispatches Celery task.
    Rate limited to 60 requests per hour per IP.
    """
    permission_classes = (AllowAny,)

    @method_decorator(ratelimit(key='ip', rate='60/h', method='POST', block=True))
    def post(self, request):
        # 1. Get headers
        signature = request.headers.get('X-Hub-Signature-256', '')
        event_type = request.headers.get('X-GitHub-Event', '')

        # 2. Only handle pull_request events
        if event_type == 'ping':
            return Response(
                {'success': True, 'data': {'message': 'pong'}},
                status=status.HTTP_200_OK,
            )

        if event_type != 'pull_request':
            return Response(
                {'success': False, 'error': {'code': 400, 'message': 'Unsupported event type'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Parse payload
        try:
            payload = request.data
            repo_name = payload.get('repository', {}).get('name', '')
            repo_owner = payload.get('repository', {}).get('owner', {}).get('login', '')
        except Exception:
            return Response(
                {'success': False, 'error': {'code': 400, 'message': 'Invalid payload'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Find the repository
        repository = get_repository_by_full_name(repo_owner, repo_name)
        if not repository:
            return Response(
                {'success': False, 'error': {'code': 404, 'message': 'Repository not registered'}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 5. Verify HMAC signature
        raw_body = request.body
        from apps.webhooks.services import verify_webhook_secret
        if not verify_webhook_secret(raw_body, signature, repository.webhook_secret):
            logger.warning(f"Invalid webhook signature for repo {repository.full_name}")
            return Response(
                {'success': False, 'error': {'code': 401, 'message': 'Invalid signature'}},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # 6. Parse PR data
        parsed = parse_pr_webhook(payload)
        action = parsed.get('action', '')

        if action not in ['opened', 'synchronize', 'reopened']:
            return Response(
                {'success': True, 'data': {'message': f'Action {action} ignored'}},
                status=status.HTTP_200_OK,
            )

        # 7. Store webhook event
        event = create_webhook_event(repository, parsed, payload)

        # 8. Dispatch Celery task asynchronously
        from apps.webhooks.tasks import process_webhook_event
        process_webhook_event.delay(str(event.id))

        logger.info(
            f"Webhook received for {repository.full_name} "
            f"PR #{parsed['pr_number']} action={action}"
        )

        # 9. Return 200 immediately
        return Response(
            {'success': True, 'data': {'message': 'Webhook received', 'event_id': str(event.id)}},
            status=status.HTTP_200_OK,
        )


class WebhookEventViewSet(ReadOnlyModelViewSet):
    """
    Read-only API to inspect webhook events for debugging.
    """
    serializer_class = WebhookEventSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return WebhookEvent.objects.filter(
            repository__user=self.request.user,
        ).select_related('repository')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'success': True, 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({'success': True, 'data': serializer.data})