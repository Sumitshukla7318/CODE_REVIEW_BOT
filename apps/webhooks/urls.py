from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.webhooks.views import GithubWebhookView, WebhookEventViewSet

router = DefaultRouter()
router.register(r'events', WebhookEventViewSet, basename='webhook-events')

urlpatterns = [
    path('github/', GithubWebhookView.as_view(), name='github-webhook'),
    path('', include(router.urls)),
]