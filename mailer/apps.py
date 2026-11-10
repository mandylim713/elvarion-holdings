from django.apps import AppConfig


class MailerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name  = 'mailer'
    label = 'mailer'
    verbose_name = 'Elvarion Mailer'
