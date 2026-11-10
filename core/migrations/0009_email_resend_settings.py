from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_verify_existing'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysetting',
            name='resend_api_key',
            field=models.CharField(blank=True, default='', help_text='Resend API Key (re_...)', max_length=150),
        ),
        migrations.AddField(
            model_name='companysetting',
            name='sender_email',
            field=models.CharField(blank=True, default='Elvarion Holdings <support@elvarionholdings.com>', help_text='Sender address (must use verified domain in Resend)', max_length=150),
        ),
        migrations.AddField(
            model_name='companysetting',
            name='admin_email',
            field=models.CharField(blank=True, default='support@elvarionholdings.com', help_text='Email address to receive platform administrator notifications', max_length=150),
        ),
        migrations.AddField(
            model_name='companysetting',
            name='smtp_host',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='companysetting',
            name='smtp_port',
            field=models.PositiveIntegerField(default=587),
        ),
        migrations.AddField(
            model_name='companysetting',
            name='smtp_user',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='companysetting',
            name='smtp_password',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='companysetting',
            name='smtp_use_tls',
            field=models.BooleanField(default=True),
        ),
    ]

