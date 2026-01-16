# ToP/services/modification_records_service.py

from dataclasses import dataclass
from datetime import timedelta
from typing import List, Tuple

from django.db.models import QuerySet
from django.utils.timezone import now

from ..models import ModificationRecords
from ..utils.modification_records_utils import unique_preserve_order


@dataclass(frozen=True)
class ModificationRecordsConfig:
    retention_days: int = 90
    types: Tuple[str, ...] = ("CREATE", "UPDATE", "DELETE", "REPLACE")


class ModificationRecordsService:
    """
    Handles:
    - cleanup of old records
    - querying records
    - preparing unique users list
    """

    def __init__(self, config: ModificationRecordsConfig | None = None):
        self.config = config or ModificationRecordsConfig()

    def cleanup_old_records(self) -> int:
        """
        Deletes records older than retention_days.
        Returns number of deleted rows (Django delete returns (count, details)).
        """
        cutoff = now() - timedelta(days=self.config.retention_days)
        deleted_count, _ = ModificationRecords.objects.filter(timestamp__lt=cutoff).delete()
        return deleted_count

    def get_records(self) -> QuerySet:
        """
        Returns ordered queryset with user joined.
        """
        return ModificationRecords.objects.select_related("user").order_by("-timestamp")

    def get_unique_user_full_names(self, records: QuerySet) -> List[str]:
        """
        Preserves the same behavior:
        iterate records in order and extract user.full_name uniquely.
        """
        names = [r.user.full_name for r in records]
        return unique_preserve_order(names)

    def build_view_context(self) -> dict:
        """
        One-shot context builder for the view.
        """
        self.cleanup_old_records()
        records = self.get_records()

        return {
            "records": records,
            "types": list(self.config.types),
            "unique_users": self.get_unique_user_full_names(records),
        }
