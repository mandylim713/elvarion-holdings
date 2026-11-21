from django.db import migrations, models


def bank_on(apps, schema_editor):
    CS = apps.get_model('core', 'CompanySetting')
    for cs in CS.objects.all():
        cur = [m.strip() for m in (cs.disabled_deposit_methods or '').split(',') if m.strip()]
        if cur == ['BANK_WIRE']:
            cs.disabled_deposit_methods = ''
            cs.save(update_fields=['disabled_deposit_methods'])


class Migration(migrations.Migration):
    dependencies = [("core", "0014_only_bank_disabled")]
    operations = [
        migrations.AlterField(
            model_name="companysetting",
            name="disabled_deposit_methods",
            field=models.TextField(blank=True, default='', help_text="Comma-separated deposit methods the admin has switched off (shown grayed out to investors)"),
        ),
        migrations.RunPython(bank_on, migrations.RunPython.noop),
    ]
