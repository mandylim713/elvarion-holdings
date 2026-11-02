from decimal import Decimal
from django.db import migrations

ASSETS = [
    # symbol, name, category, base price, volatility, qty decimals, icon
    ('BTC', 'Bitcoin', 'crypto', '95000', '1.2', 6, 'bitcoin-sign'),
    ('ETH', 'Ethereum', 'crypto', '3200', '1.3', 5, 'ethereum'),
    ('SOL', 'Solana', 'crypto', '160', '1.8', 4, 'coins'),
    ('BNB', 'BNB', 'crypto', '620', '1.2', 4, 'coins'),
    ('XRP', 'XRP', 'crypto', '2.4', '1.6', 2, 'coins'),
    ('XAU', 'Gold (per oz)', 'metal', '4000', '0.5', 4, 'ring'),
    ('XAG', 'Silver (per oz)', 'metal', '48', '0.8', 3, 'gem'),
    ('AAPL', 'Apple Inc.', 'stock', '230', '0.7', 3, 'apple-whole'),
    ('MSFT', 'Microsoft', 'stock', '500', '0.6', 3, 'window-maximize'),
    ('NVDA', 'NVIDIA', 'stock', '180', '1.1', 3, 'microchip'),
    ('TSLA', 'Tesla', 'stock', '400', '1.4', 3, 'car'),
    ('AMZN', 'Amazon', 'stock', '220', '0.8', 3, 'box'),
]

def seed(apps, schema_editor):
    Asset = apps.get_model('core', 'TradingAsset')
    for i, (sym, name, cat, price, vol, dec, icon) in enumerate(ASSETS):
        Asset.objects.get_or_create(symbol=sym, defaults=dict(
            name=name, category=cat, base_price=Decimal(price), volatility=Decimal(vol),
            decimals=dec, icon=icon, order=i))

class Migration(migrations.Migration):
    dependencies = [('core', '0004_trading')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
