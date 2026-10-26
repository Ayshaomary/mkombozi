from django.db import migrations

from accounts.utils import normalize_phone


def normalize_existing_phones(apps, schema_editor):
    """Convert phones saved before normalization (e.g. by createsuperuser) to +255 format.

    A phone is skipped if its normalized form already belongs to another account.
    """
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all():
        phone = normalize_phone(user.phone)
        if phone != user.phone and not User.objects.filter(phone=phone).exists():
            user.phone = phone
            user.save(update_fields=['phone'])


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]

    operations = [migrations.RunPython(normalize_existing_phones, migrations.RunPython.noop)]
