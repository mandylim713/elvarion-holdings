from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0015_bank_deposits_on")]
    operations = [
        migrations.AddField(
            model_name="companysetting",
            name="qr_codes",
            field=models.JSONField(blank=True, default=dict, help_text="Uploaded QR code image per payment method (key -> stored file name)"),
        ),
    ]
