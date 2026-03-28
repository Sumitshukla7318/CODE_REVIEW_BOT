from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.reviews.views import CodeReviewViewSet

router = DefaultRouter()
router.register(r'', CodeReviewViewSet, basename='reviews')

urlpatterns = [
    path('', include(router.urls)),
]