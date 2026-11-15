from django.apps import AppConfig


class MailerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name  = 'mailer'
    label = 'mailer'
    verbose_name = 'Elvarion Mailer'

    def ready(self):
        """
        On every startup: if RESEND_API_KEY is set in the environment and
        CompanySetting.resend_api_key is currently blank, write the key into the DB
        so the mailer works immediately without any manual admin step.
        """
        import os
        env_key = os.environ.get('RESEND_API_KEY', '').strip()
        if not env_key:
            return
        try:
            from django.db import connection
            tables = connection.introspection.table_names()
            if 'core_companysetting' not in tables:
                return  # DB not migrated yet — skip safely
            from core.models import CompanySetting
            cs, _ = CompanySetting.objects.get_or_create(id=1)
            changed = False
            if not cs.resend_api_key:
                cs.resend_api_key = env_key
                changed = True
            if not cs.sender_email:
                cs.sender_email = os.environ.get(
                    'DEFAULT_FROM_EMAIL',
                    'Elvarion Holdings <support@elvarionholdings.com>'
                )
                changed = True
            if not cs.admin_email:
                cs.admin_email = 'support@elvarionholdings.com'
                changed = True
            if changed:
                cs.save(update_fields=['resend_api_key', 'sender_email', 'admin_email'])
        except Exception:
            # Never crash the app startup for a seeding issue
            pass
