from django.core.management.base import BaseCommand

from accounts.models import Business
from notifications.automations import run_automations


class Command(BaseCommand):
    help = 'Run automatic tasks (recurring expenses, daily summary, subscription reminders) for every business.'

    def handle(self, *args, **options):
        businesses = Business.objects.all()
        for business in businesses:
            run_automations(business, force=True)
        self.stdout.write(self.style.SUCCESS(f'Automations ran for {businesses.count()} business(es).'))
