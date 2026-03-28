from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    path('api/auth/', include('apps.users.urls')),
    path('api/repositories/', include('apps.repositories.urls')),
    path('api/webhooks/', include('apps.webhooks.urls')),
    path('api/reviews/', include('apps.reviews.urls')),
    path('api/events/', include('apps.webhooks.urls')),
]