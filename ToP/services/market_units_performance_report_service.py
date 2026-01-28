from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Count
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.utils import timezone
from django.utils.dateparse import parse_date

from ..models import MarketUnitData


@dataclass
class _Result:
    success: bool
    status: int = 200
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MarketUnitsPerformanceReportService:
    """
    Performance report for MarketUnitData based on updated_by + date_of_update.

    - members_options: only members who have touched>0 in the selected period
    - summary_rows: only members with touched>0
    - POST-only AJAX filter updates
    """

    DEFAULT_DAYS_BACK = 30
    MAX_SERIES_MEMBERS = 8

    # -------------------------------
    # Public API
    # -------------------------------
    def build_page_context(self) -> Dict[str, Any]:
        """
        Used on GET to render initial page.
        """
        start_date, end_date = self._default_range()
        granularity = "day"
        selected_members: List[str] = []

        data = self._build_report(
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            selected_members=selected_members,
        )

        return {"success": True, "data": data}

    def build_report_payload(self, *, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Used on POST from AJAX.
        payload: {start_date, end_date, granularity, members: []}
        """
        start_date, end_date = self._parse_range_from_payload(payload)
        granularity = (payload.get("granularity") or "day").strip().lower()
        if granularity not in ("day", "week", "month"):
            granularity = "day"

        members = payload.get("members") or []
        if isinstance(members, str):
            members = [members]
        selected_members = [str(m).strip() for m in members if str(m).strip()]

        data = self._build_report(
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            selected_members=selected_members,
        )

        return {"success": True, "data": data}

    # -------------------------------
    # Core builder
    # -------------------------------
    def _build_report(
        self,
        *,
        start_date: date,
        end_date: date,
        granularity: str,
        selected_members: List[str],
    ) -> Dict[str, Any]:

        base_qs = (
            MarketUnitData.objects
            .exclude(updated_by__isnull=True)
            .exclude(updated_by__exact="")
            .filter(date_of_update__isnull=False)
            .filter(date_of_update__gte=start_date, date_of_update__lte=end_date)
        )

        # Active members in period (touched > 0) — used for dropdown options
        active_members_counts = (
            base_qs.values("updated_by")
            .annotate(touched=Count("id"))
            .filter(touched__gt=0)
            .order_by("-touched", "updated_by")
        )

        members_options = [r["updated_by"] for r in active_members_counts]

        # If user selected members, keep only those that are active in this period
        # (requirement: don't show zeros at all)
        selected_members = [m for m in selected_members if m in members_options]

        # Summary table (if selected, restrict)
        summary_qs = base_qs
        if selected_members:
            summary_qs = summary_qs.filter(updated_by__in=selected_members)

        summary_counts = (
            summary_qs.values("updated_by")
            .annotate(touched=Count("id"))
            .filter(touched__gt=0)
            .order_by("-touched", "updated_by")
        )

        summary_rows = [
            {"member": r["updated_by"], "touched": int(r["touched"])}
            for r in summary_counts
        ]

        totals = {
            "members": len(summary_rows),
            "touched": sum(r["touched"] for r in summary_rows),
        }

        # Time series members:
        # - If user selected members, chart those (only active ones)
        # - Else chart top N active members for the period
        if selected_members:
            series_members = selected_members[:]
        else:
            series_members = members_options[: self.MAX_SERIES_MEMBERS]

        labels, bucket_keys = self._build_buckets(start_date, end_date, granularity)

        # Group counts by member + bucket
        trunc = self._trunc_func(granularity)
        bucketed = (
            base_qs.filter(updated_by__in=series_members) if series_members else base_qs.none()
        ).annotate(bucket=trunc("date_of_update")).values("updated_by", "bucket").annotate(c=Count("id"))

        # Map: (member, bucket_date)->count
        counts_map: Dict[Tuple[str, date], int] = {}
        for r in bucketed:
            b = r["bucket"]
            if hasattr(b, "date"):
                b = b.date()
            counts_map[(r["updated_by"], b)] = int(r["c"])

        datasets = []
        for member in series_members:
            data_points = [counts_map.get((member, b), 0) for b in bucket_keys]
            if sum(data_points) == 0:
                # extra safety: don't include zero series
                continue
            datasets.append({"label": member, "data": data_points})

        report_json = {"labels": labels, "datasets": datasets}

        return {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "granularity": granularity,
            "members_options": members_options,      # dropdown options (active only)
            "selected_members": selected_members,    # active selections only
            "totals": totals,
            "summary_rows": summary_rows,            # no zero rows
            "report_json": report_json,
            "defaults": {
                "start_date": (timezone.localdate() - timedelta(days=self.DEFAULT_DAYS_BACK)).strftime("%Y-%m-%d"),
                "end_date": timezone.localdate().strftime("%Y-%m-%d"),
                "granularity": "day",
            }
        }

    # -------------------------------
    # Helpers
    # -------------------------------
    def _default_range(self) -> Tuple[date, date]:
        today = timezone.localdate()
        return today - timedelta(days=self.DEFAULT_DAYS_BACK), today

    def _parse_range_from_payload(self, payload: Dict[str, Any]) -> Tuple[date, date]:
        def _p(v: Any) -> Optional[date]:
            if not v:
                return None
            d = parse_date(str(v).strip())
            return d

        sd = _p(payload.get("start_date"))
        ed = _p(payload.get("end_date"))

        if not sd or not ed:
            return self._default_range()

        if sd > ed:
            sd, ed = ed, sd

        return sd, ed

    def _trunc_func(self, granularity: str):
        if granularity == "week":
            return TruncWeek
        if granularity == "month":
            return TruncMonth
        return TruncDay

    def _build_buckets(self, start: date, end: date, granularity: str) -> Tuple[List[str], List[date]]:
        labels: List[str] = []
        keys: List[date] = []

        if granularity == "day":
            cur = start
            while cur <= end:
                labels.append(cur.strftime("%Y-%m-%d"))
                keys.append(cur)
                cur += timedelta(days=1)
            return labels, keys

        if granularity == "week":
            # Normalize to Monday
            cur = start - timedelta(days=start.weekday())
            last = end - timedelta(days=end.weekday())
            while cur <= last:
                labels.append(cur.strftime("%Y-%m-%d"))  # week start
                keys.append(cur)
                cur += timedelta(days=7)
            return labels, keys

        # month
        cur = date(start.year, start.month, 1)
        last = date(end.year, end.month, 1)
        while cur <= last:
            labels.append(cur.strftime("%Y-%m"))
            keys.append(cur)
            cur = self._add_month(cur)
        return labels, keys

    def _add_month(self, d: date) -> date:
        y = d.year + (d.month // 12)
        m = (d.month % 12) + 1
        return date(y, m, 1)
