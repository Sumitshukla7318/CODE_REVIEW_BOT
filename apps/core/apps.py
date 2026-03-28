from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        """Run startup validation when Django loads."""
        from apps.core.startup import validate_environment
        validate_environment()