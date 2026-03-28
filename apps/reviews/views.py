from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.reviews.models import CodeReview, ReviewIssue
from apps.reviews.serializers import (
    CodeReviewSerializer,
    CodeReviewListSerializer,
    ReviewIssueSerializer,
)


class CodeReviewViewSet(ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = CodeReview.objects.filter(
            repository__user=self.request.user,
        ).select_related(
            'repository',
            'webhook_event',
            'pr_diff',
        ).prefetch_related('issues')

        # Filters
        repo = self.request.query_params.get('repo')
        pr_number = self.request.query_params.get('pr_number')
        severity = self.request.query_params.get('severity')

        if repo:
            queryset = queryset.filter(repository__name=repo)
        if pr_number:
            queryset = queryset.filter(webhook_event__pr_number=pr_number)
        if severity:
            queryset = queryset.filter(issues__severity=severity).distinct()

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return CodeReviewListSerializer
        return CodeReviewSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'success': True, 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({'success': True, 'data': serializer.data})

    @action(detail=True, methods=['get'], url_path='issues')
    def issues(self, request, pk=None):
        """GET /api/reviews/{id}/issues/"""
        review = self.get_object()
        issues = review.issues.all()
        serializer = ReviewIssueSerializer(issues, many=True)
        return Response({'success': True, 'data': serializer.data})

    @action(detail=True, methods=['post'], url_path='retry')
    def retry(self, request, pk=None):
        """POST /api/reviews/{id}/retry/ — retry a failed review."""
        review = self.get_object()

        if review.status != CodeReview.ReviewStatus.FAILED:
            return Response(
                {
                    'success': False,
                    'error': {
                        'code': 400,
                        'message': 'Only failed reviews can be retried.'
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        review.status = CodeReview.ReviewStatus.PENDING
        review.error_message = None
        review.save(update_fields=['status', 'error_message'])

        from apps.reviews.tasks import perform_ai_review
        perform_ai_review.delay(str(review.pr_diff.id))

        return Response(
            {'success': True, 'data': {'message': 'Review retry triggered.'}},
            status=status.HTTP_200_OK,
        )