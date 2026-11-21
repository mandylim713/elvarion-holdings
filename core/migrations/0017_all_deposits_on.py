from django.db import migrations


def all_on(apps, schema_editor):
    # Every deposit method (bank and crypto included) is open; admin can still switch any off afterwards.
    apps.get_model('core', 'CompanySetting').objects.update(disabled_deposit_methods='', deposits_frozen=False)


class Migration(migrations.Migration):
    dependencies = [("core", "0016_qr_codes")]
    operations = [migrations.RunPython(all_on, migrations.RunPython.noop)]
