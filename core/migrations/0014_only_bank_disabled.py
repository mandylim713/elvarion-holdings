from django.db import migrations

ALL = 'BTC,USDT_TRC20,USDT_ERC20,ETH,BANK_WIRE,ZELLE,PAYPAL,VENMO,CASHAPP,WISE'.split(',')


def only_bank(apps, schema_editor):
    CS = apps.get_model('core', 'CompanySetting')
    for cs in CS.objects.all():
        cur = [m.strip() for m in (cs.disabled_deposit_methods or '').split(',') if m.strip()]
        if set(cur) == set(ALL):  # still the earlier "everything off" default
            cs.disabled_deposit_methods = 'BANK_WIRE'
            cs.save(update_fields=['disabled_deposit_methods'])


class Migration(migrations.Migration):
    dependencies = [("core", "0013_deposit_options")]
    operations = [migrations.RunPython(only_bank, migrations.RunPython.noop)]
