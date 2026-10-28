from django.db import migrations

# New prices from 2026-10-28. Savings compare with paying TZS 50,000 every month.
NEW_PRICES = {
    'monthly': (50000, 'Huduma zote kwa mwezi mmoja.'),
    'quarterly': (141000, 'Okoa TZS 9,000 (6%) ukilipia miezi 3.'),
    'yearly': (540000, 'Okoa TZS 60,000 (10%) ukilipia mwaka mzima.'),
}
OLD_PRICES = {
    'monthly': (10000, 'Huduma zote kwa mwezi mmoja.'),
    'quarterly': (27000, 'Okoa 10% ukilipia miezi 3.'),
    'yearly': (100000, 'Okoa zaidi ya 15% ukilipia mwaka mzima.'),
}


def set_prices(prices):
    def apply(apps, schema_editor):
        Plan = apps.get_model('subscriptions', 'Plan')
        for code, (price, description) in prices.items():
            Plan.objects.filter(code=code).update(price=price, description=description)

    return apply


class Migration(migrations.Migration):
    dependencies = [('subscriptions', '0003_sonicpesa_fields')]

    operations = [migrations.RunPython(set_prices(NEW_PRICES), set_prices(OLD_PRICES))]
