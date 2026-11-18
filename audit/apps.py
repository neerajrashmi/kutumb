from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    # If the app is inside the 'apps' folder, use 'apps.audit'; if in root, use 'audit'
    name = 'audit'
    label = 'audit'

    def ready(self):
        try:
            import audit.signals  # Connect signals on startup
        except ImportError:
            pass