from django.core.management.base import BaseCommand
from ToP.services.company_auto_sync_service import CompanyAutoSyncService

class Command(BaseCommand):
    help = "Runs auto sync for companies that enabled it."

    def handle(self, *args, **options):
        CompanyAutoSyncService.run()
        self.stdout.write(self.style.SUCCESS("Auto sync run completed."))
