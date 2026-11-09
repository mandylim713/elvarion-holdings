from decimal import Decimal
from django.db import migrations, models

# Monthly rates for plans that used to be priced daily / weekly / yearly.
RATES = {
    'Luxury Residential Developments': '2.67',
    'Logistics Infrastructure Syndicate': '7.00',
    'Precious Metals Arbitrage': '2.00',
    'Fast-Track Bullion Liquidity': '5.00',
    'Sovereign Endowment Trust': '3.75',
    'Institutional Daily Liquidity Fund': '4.00',
    'Stablecoin Yield Account': '7.00',
}


def to_monthly(apps, schema_editor):
    Plan = apps.get_model('core', 'InvestmentPlan')
    Area = apps.get_model('core', 'InvestmentArea')
    Inv = apps.get_model('core', 'UserInvestment')
    for inv in Inv.objects.filter(term_months=0).select_related('plan'):
        days = max(1, round((inv.end_date - inv.start_date).total_seconds() / 86400))
        inv.term_months = min((1, 3, 6, 12), key=lambda m: abs(m * 30 - days))
        inv.save(update_fields=['term_months'])
    for p in Plan.objects.all():
        if p.duration_unit != 'monthly':
            if p.title in RATES:
                p.roi_percentage = Decimal(RATES[p.title])
            elif p.duration_unit == 'yearly':
                p.roi_percentage = (p.roi_percentage / 12).quantize(Decimal('0.01'))
            elif p.duration_unit == 'weekly':
                p.roi_percentage = (p.roi_percentage * 4).quantize(Decimal('0.01'))
            else:
                p.roi_percentage = (p.roi_percentage * 30).quantize(Decimal('0.01'))
        p.duration_unit = 'monthly'
        p.duration_count = 12
        p.features_list = (f"{p.roi_percentage}% Monthly Return\nChoose 1, 3, 6 or 12 months\n"
                           "Capital Returned at Maturity\nLive ROI in Your Dashboard")
        if p.badge in ('WEEKLY YIELD', 'DAILY PAYOUT'):
            p.badge = 'HIGH YIELD' if p.badge.startswith('WEEK') else 'FLEXIBLE'
        p.save()
    for a in Area.objects.all():
        rates = [pl.roi_percentage for pl in Plan.objects.filter(area=a)]
        if rates:
            a.expected_roi_range = f"{min(rates)}% - {max(rates)}% monthly"
            a.save(update_fields=['expected_roi_range'])


class Migration(migrations.Migration):
    dependencies = [('core', '0008_verify_existing')]
    operations = [
        migrations.AddField(model_name='userinvestment', name='term_months',
                            field=models.PositiveSmallIntegerField(default=0, help_text='Chosen term: 1, 3, 6 or 12 months')),
        migrations.RunPython(to_monthly, migrations.RunPython.noop),
    ]
