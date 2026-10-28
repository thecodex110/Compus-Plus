from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from printing.models import PrintOrder

S = PrintOrder.Status


class Command(BaseCommand):
    help = ('Delete print files older than PRINT_FILE_RETENTION_DAYS (and their payment screenshots), '
            'and drop unpaid draft orders older than a day. Run daily (cron).')

    def handle(self, *args, **opts):
        now = timezone.now()

        drafts = PrintOrder.objects.filter(status=S.DRAFT, created_at__lt=now - timedelta(days=1))
        n_drafts = 0
        for order in drafts:
            if order.file:
                order.file.delete(save=False)
            order.delete()
            n_drafts += 1

        cutoff = now - timedelta(days=settings.PRINT_FILE_RETENTION_DAYS)
        n_files = 0
        for order in PrintOrder.objects.exclude(status=S.DRAFT).filter(created_at__lt=cutoff):
            changed = False
            if order.file:
                order.file.delete(save=False)
                order.file_deleted_at = now
                changed = True
            if order.payment_screenshot:
                order.payment_screenshot.delete(save=False)
                changed = True
            if changed:
                order.save(update_fields=['file', 'payment_screenshot', 'file_deleted_at', 'updated_at'])
                n_files += 1

        self.stdout.write(self.style.SUCCESS(f'Removed {n_drafts} stale drafts; purged files from {n_files} orders.'))
