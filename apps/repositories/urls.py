from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.repositories.views import RepositoryViewSet

router = DefaultRouter()
router.register(r'', RepositoryViewSet, basename='repositories')

urlpatterns = [
    path('', include(router.urls)),
]