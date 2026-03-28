from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import extend_schema
from apps.users.views import RegisterView, LoginView, LogoutView

# Add schema to the built-in refresh view
TokenRefreshView = extend_schema(
    summary="Refresh access token",
    description="Get a new access token using your refresh token.",
    tags=['Auth'],
)(TokenRefreshView)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', LoginView.as_view(), name='auth-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
]
