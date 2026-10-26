from django.db import migrations

DEFAULT_PLANS = [
    {'code': 'monthly', 'name': 'Mwezi 1 (Monthly)', 'price': 10000, 'duration_days': 30, 'sort_order': 1,
     'description': 'Huduma zote kwa mwezi mmoja.'},
    {'code': 'quarterly', 'name': 'Miezi 3 (Quarterly)', 'price': 27000, 'duration_days': 90, 'sort_order': 2,
     'description': 'Okoa 10% ukilipia miezi 3.'},
    {'code': 'yearly', 'name': 'Mwaka 1 (Yearly)', 'price': 100000, 'duration_days': 365, 'sort_order': 3,
     'description': 'Okoa zaidi ya 15% ukilipia mwaka mzima.'},
]


def create_plans(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    for plan in DEFAULT_PLANS:
        Plan.objects.update_or_create(code=plan['code'], defaults=plan)


def remove_plans(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    Plan.objects.filter(code__in=[p['code'] for p in DEFAULT_PLANS]).delete()


class Migration(migrations.Migration):
    dependencies = [('subscriptions', '0001_initial')]

    operations = [migrations.RunPython(create_plans, remove_plans)]
