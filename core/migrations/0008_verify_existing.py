from django.db import migrations


def verify_existing(apps, schema_editor):
    # accounts that existed before email codes were introduced stay usable
    apps.get_model('core', 'UserProfile').objects.update(email_verified=True)


class Migration(migrations.Migration):
    dependencies = [('core', '0007_otp_options_settings')]
    operations = [migrations.RunPython(verify_existing, migrations.RunPython.noop)]
