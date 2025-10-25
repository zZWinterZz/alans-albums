from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # Import signal handlers to ensure they are connected
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
