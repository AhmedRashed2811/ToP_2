import logging
from datetime import timedelta
from django.utils.timezone import now
from django.db import transaction

from ..models import Company
from .unit_warehouse_service import UnitWarehouseService

logger = logging.getLogger(__name__)


class CompanyAutoSyncService:
    """
    Cron-friendly auto sync service.

    - Runs for companies where auto_sync=True and auto_sync_timer>0
    - Timer interpreted as MINUTES
    - Sync Sheets if configured
    - Sync ERP if configured
    - Uses DB row locking to prevent concurrent runs per company
    """

    @staticmethod
    def run():
        qs = Company.objects.filter(auto_sync=True, auto_sync_timer__gt=0)

        for company in qs:
            try:
                CompanyAutoSyncService._run_for_company(company.id)
            except Exception as e:
                logger.exception(f"[AUTO_SYNC] Company {company.id} failed: {e}")

    @staticmethod
    def _due(last_run, minutes: int) -> bool:
        if not last_run:
            return True
        return now() >= (last_run + timedelta(minutes=minutes))

    @staticmethod
    def _run_for_company(company_id: int):
        with transaction.atomic():
            c = Company.objects.select_for_update().get(id=company_id)

            # Prevent overlapping runs
            if c.auto_sync_running:
                return

            if not c.auto_sync or c.auto_sync_timer <= 0:
                return

            if not CompanyAutoSyncService._due(c.last_auto_sync_at, c.auto_sync_timer):
                return

            # Mark running (inside lock)
            c.auto_sync_running = True
            c.save(update_fields=["auto_sync_running"])

        # run imports OUTSIDE the lock to avoid holding DB lock during network IO
        sheet_ok = False
        erp_ok = False
        errors = []

        try:
            if c.google_sheet_url:
                res = UnitWarehouseService.trigger_import(company=c, source_type="sheet")
                sheet_ok = bool(res.get("success"))
                if not sheet_ok:
                    errors.append(f"SHEET: {res.get('error') or res}")

            if c.erp_url:
                res = UnitWarehouseService.trigger_import(company=c, source_type="erp")
                erp_ok = bool(res.get("success"))
                if not erp_ok:
                    errors.append(f"ERP: {res.get('error') or res}")

        finally:
            # Clear running flag + update last run timestamp (only if any source ran)
            ran_any = bool(c.google_sheet_url) or bool(c.erp_url)

            with transaction.atomic():
                c2 = Company.objects.select_for_update().get(id=company_id)
                c2.auto_sync_running = False

                if ran_any and (sheet_ok or erp_ok or not errors):
                    # even if one source failed, you may still want to mark last run to avoid hammering.
                    # adjust rule if you prefer "only mark last run if both succeeded".
                    c2.last_auto_sync_at = now()

                c2.save(update_fields=["auto_sync_running", "last_auto_sync_at"])

            if errors:
                logger.error(f"[AUTO_SYNC] Company {company_id} partial errors: {errors}")
