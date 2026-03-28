from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.repositories.models import Repository
from apps.repositories.serializers import RepositorySerializer, RepositorySecretSerializer
from apps.repositories.services import rotate_webhook_secret


class RepositoryViewSet(ModelViewSet):
    serializer_class = RepositorySerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Repository.objects.filter(
            user=self.request.user,
            is_active=True,
        ).select_related('user')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        cache.delete(f"repo_list:{request.user.id}")

        # Show plain secret ONCE on creation
        instance = serializer.instance
        plain_secret = getattr(instance, '_plain_secret', None)

        data = serializer.data
        if plain_secret:
            data = dict(data)
            data['webhook_secret'] = plain_secret
            data['webhook_secret_notice'] = 'Save this secret now — it will never be shown again.'

        return Response(
            {'success': True, 'data': data},
            status=status.HTTP_201_CREATED,
        )
    

    def list(self, request, *args, **kwargs):
        cache_key = f"repo_list:{request.user.id}"
        cached = cache.get(cache_key)
        if cached:
            return Response({'success': True, 'data': cached})

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        cache.set(cache_key, serializer.data, timeout=300)
        return Response({'success': True, 'data': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        cache_key = f"repo_detail:{instance.id}"
        cached = cache.get(cache_key)
        if cached:
            return Response({'success': True, 'data': cached})

        serializer = self.get_serializer(instance)
        cache.set(cache_key, serializer.data, timeout=300)
        return Response({'success': True, 'data': serializer.data})

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Invalidate caches
        cache.delete(f"repo_detail:{instance.id}")
        cache.delete(f"repo_list:{request.user.id}")
        return Response({'success': True, 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        # Invalidate caches
        cache.delete(f"repo_detail:{instance.id}")
        cache.delete(f"repo_list:{request.user.id}")
        return Response({'success': True, 'data': {'message': 'Repository deleted.'}})

    @action(detail=True, methods=['post'], url_path='rotate-secret')
    def rotate_secret(self, request, pk=None):
        """Rotate the webhook secret for a repository."""
        repository = self.get_object()
        repository, plain_secret = rotate_webhook_secret(repository)
        cache.delete(f"repo_detail:{repository.id}")
        serializer = RepositorySecretSerializer(
            repository,
            context={'plain_secret': plain_secret},
        )
        return Response({'success': True, 'data': serializer.data})

    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        """GET /api/repositories/{id}/stats/"""
        from apps.reviews.services import calculate_review_stats

        repository = self.get_object()
        cache_key = f"repo_stats:{repository.id}"
        cached = cache.get(cache_key)

        if cached:
            return Response({'success': True, 'data': cached})

        stats = calculate_review_stats(repository)
        cache.set(cache_key, stats, timeout=300)  # 5 minutes
        return Response({'success': True, 'data': stats})

    @action(detail=True, methods=['get'], url_path='reviews')
    def reviews(self, request, pk=None):
        """GET /api/repositories/{id}/reviews/"""
        from apps.reviews.models import CodeReview
        from apps.reviews.serializers import CodeReviewListSerializer

        repository = self.get_object()
        reviews = CodeReview.objects.filter(
            repository=repository,
        ).select_related('webhook_event').order_by('-created_at')

        serializer = CodeReviewListSerializer(reviews, many=True)
        return Response({'success': True, 'data': serializer.data})