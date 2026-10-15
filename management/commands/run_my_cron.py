from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Runs my scheduled DRF task'

    def handle(self, *args, **options):
        # Put your logic here (e.g., calling a service function, cleaning up DB)
        self.stdout.write(self.style.SUCCESS('Successfully ran cron task.'))
