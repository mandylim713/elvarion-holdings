from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0010_monthly_plans')]
    operations = [
        migrations.AddField(model_name='companysetting', name='deposits_frozen',
                            field=models.BooleanField(default=True, help_text='When on, investors cannot submit any deposit (bank transfer, cash apps, crypto)')),
    ]
