# ToP/services/market_research_service.py

from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List, Iterable, Tuple
from collections import defaultdict

from django.db.models import Avg, Min, Max, Count, QuerySet

from ..models import (
    MarketUnitData,
    MarketProject,
    MarketProjectLocation,
    MarketProjectDeveloper,
)

from ..utils.market_research_utils import (
    build_base_context,
    get_filters_from_request,
    apply_filters,
    format_number,
    format_range,  # wrapper around your format_number or uses it
)


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    trace: Optional[str] = None


class MarketResearchService:
    """
    Clean service layer for:
    - report context
    - pivot api
    - projects explorer + project filters
    - dashboard (context + APIs)
    - candlestick API + server-rendered hierarchical charts
    """

    # -----------------------------
    # Common helpers
    # -----------------------------
    @staticmethod
    def _ok(payload: Dict[str, Any], status: int = 200) -> ServiceResult:
        return ServiceResult(success=True, status=status, payload=payload)

    @staticmethod
    def _fail(status: int, error: str, trace: Optional[str] = None) -> ServiceResult:
        return ServiceResult(success=False, status=status, error=error, trace=trace)

    @staticmethod
    def _distinct_list(qs: QuerySet, field: str) -> List[Any]:
        """
        Returns distinct list of non-null, non-empty values ordered by field.
        """
        return list(
            qs.exclude(**{f"{field}__isnull": True})
              .exclude(**{field: ""})
              .values_list(field, flat=True)
              .distinct()
              .order_by(field)
        )

    @staticmethod
    def _project_unit_queryset(project_name: str) -> QuerySet:
        return MarketUnitData.objects.filter(project_name=project_name)

    @staticmethod
    def _unit_stats(qs: QuerySet) -> Dict[str, Any]:
        """
        Single aggregate call for project stats (preserves the exact metrics you used).
        """
        return qs.aggregate(
            avg_price=Avg("unit_price"),
            min_price=Min("unit_price"),
            max_price=Max("unit_price"),
            avg_psm=Avg("psm"),
            min_psm=Min("psm"),
            max_psm=Max("psm"),
            avg_bua=Avg("bua"),
            min_bua=Min("bua"),
            max_bua=Max("bua"),
            avg_down_payment=Avg("down_payment"),
            unit_count=Count("id"),
        )

    @staticmethod
    def _distinct_values(qs: QuerySet, field: str) -> List[Any]:
        return list(
            qs.exclude(**{f"{field}__isnull": True})
              .exclude(**{f"{field}__exact": ""})
              .values_list(field, flat=True)
              .distinct()
        )

    # ---------------------------------------------------------
    # 1) Report Page
    # ---------------------------------------------------------
    @staticmethod
    def get_report_context(*, user) -> ServiceResult:
        try:
            context = {
                "page_title": "Market Research Report",
                **build_base_context(user),
            }
            return MarketResearchService._ok(context)
        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 2) Pivot Data API
    # ---------------------------------------------------------
    @staticmethod
    def get_market_data() -> ServiceResult:
        try:
            units = MarketUnitData.objects.all().values(
                "project_name", "developer_name", "location", "asset_type", "unit_type",
                "bua", "unit_price", "psm", "payment_yrs", "down_payment",
                "delivery_date", "finishing_specs", "date_of_update",
                "updated_by", "source_of_info", "months_from_update", "dp_percentage"
            )
            return MarketResearchService._ok({"units": list(units)})
        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 3) Projects Explorer Page Context
    # ---------------------------------------------------------
    @staticmethod
    def get_projects_explorer_context(*, user) -> ServiceResult:
        try:
            projects_with_coords = (
                MarketProject.objects.filter(latitude__isnull=False, longitude__isnull=False)
                .select_related("developer", "location")
            )

            context = {
                "all_projects": projects_with_coords,
                "locations": MarketProjectLocation.objects.all().order_by("name"),
                "developers": MarketProjectDeveloper.objects.all().order_by("name"),
                "finishing_specs": MarketResearchService._distinct_list(MarketUnitData.objects.all(), "finishing_specs"),
                "asset_types": MarketResearchService._distinct_list(MarketUnitData.objects.all(), "asset_type"),
                **build_base_context(user),
            }
            return MarketResearchService._ok(context)

        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 5) Filter Projects API
    # ---------------------------------------------------------
    @staticmethod
    def filter_projects(*, request) -> ServiceResult:
        try:
            params = {
                "location_ids": request.GET.getlist("locations[]", []),
                "developer_ids": request.GET.getlist("developers[]", []),
                "finishing_specs": request.GET.getlist("finishing_specs[]", []),
                "asset_types": request.GET.getlist("asset_types[]", []),
                "clicked_location_name": (request.GET.get("clicked_location_name", "") or "").strip(),
            }

            projects = MarketResearchService._build_filtered_projects_queryset(params)

            available_filters = MarketResearchService._build_available_project_filters(projects)

            projects_data = [MarketResearchService._serialize_project_card(p) for p in projects]

            return MarketResearchService._ok({
                "projects": projects_data,
                "available_filters": available_filters,
            })

        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    @staticmethod
    def _build_filtered_projects_queryset(params: Dict[str, Any]) -> QuerySet:
        projects = MarketProject.objects.select_related("developer", "location")

        if params["clicked_location_name"]:
            projects = projects.filter(location__name__iexact=params["clicked_location_name"])

        if params["location_ids"]:
            projects = projects.filter(location_id__in=params["location_ids"])

        if params["developer_ids"]:
            projects = projects.filter(developer_id__in=params["developer_ids"])

        unit_filters = {}
        if params["finishing_specs"]:
            unit_filters["finishing_specs__in"] = params["finishing_specs"]
        if params["asset_types"]:
            unit_filters["asset_type__in"] = params["asset_types"]

        if unit_filters:
            matching_project_names = (
                MarketUnitData.objects.filter(**unit_filters)
                .values_list("project_name", flat=True)
                .distinct()
            )
            projects = projects.filter(name__in=matching_project_names)

        return projects

    @staticmethod
    def _build_available_project_filters(projects: QuerySet) -> Dict[str, Any]:
        available_locations = MarketProjectLocation.objects.filter(marketproject__in=projects).distinct().order_by("name")
        available_developers = MarketProjectDeveloper.objects.filter(marketproject__in=projects).distinct().order_by("name")

        project_names = projects.values_list("name", flat=True)

        available_finishing_specs = (
            MarketUnitData.objects.filter(project_name__in=project_names)
            .exclude(finishing_specs__isnull=True)
            .exclude(finishing_specs__exact="")
            .values_list("finishing_specs", flat=True)
            .distinct()
            .order_by("finishing_specs")
        )

        available_asset_types = (
            MarketUnitData.objects.filter(project_name__in=project_names)
            .exclude(asset_type__isnull=True)
            .exclude(asset_type__exact="")
            .values_list("asset_type", flat=True)
            .distinct()
            .order_by("asset_type")
        )

        return {
            "locations": [{"id": loc.id, "name": loc.name} for loc in available_locations],
            "developers": [{"id": dev.id, "name": dev.name} for dev in available_developers],
            "finishing_specs": list(available_finishing_specs),
            "asset_types": list(available_asset_types),
        }

    @staticmethod
    def _serialize_project_card(project: MarketProject) -> Dict[str, Any]:
        unit_qs = MarketResearchService._project_unit_queryset(project.name)
        stats = MarketResearchService._unit_stats(unit_qs)

        sample_unit = unit_qs.first()

        unit_types = MarketResearchService._distinct_values(unit_qs, "unit_type")
        asset_types = MarketResearchService._distinct_values(unit_qs, "asset_type")
        finishing_specs = MarketResearchService._distinct_values(unit_qs, "finishing_specs")
        payment_years = MarketResearchService._distinct_values(unit_qs, "payment_yrs")
        delivery_dates = MarketResearchService._distinct_values(unit_qs, "delivery_date")

        return {
            "id": project.id,
            "name": project.name,
            "developer": project.developer.name if project.developer else "N/A",
            "location": project.location.name if project.location else "N/A",
            "latitude": str(project.latitude) if project.latitude else None,
            "longitude": str(project.longitude) if project.longitude else None,

            "unit_count": stats["unit_count"] or 0,
            "unit_types": unit_types,
            "asset_types": asset_types,
            "finishing_specs": finishing_specs,
            "payment_years": payment_years,
            "delivery_dates": delivery_dates,

            "price_range": format_range(stats["min_price"], stats["max_price"], suffix=" EGP"),
            "avg_price": f"{format_number(stats['avg_price'])} EGP" if stats["avg_price"] else "0 EGP",
            "min_price": stats["min_price"],
            "max_price": stats["max_price"],

            "psm_range": format_range(stats["min_psm"], stats["max_psm"], suffix=" EGP/m²"),
            "avg_psm": f"{format_number(stats['avg_psm'])} EGP/m²" if stats["avg_psm"] else "0 EGP/m²",

            "bua_range": format_range(stats["min_bua"], stats["max_bua"], suffix=" m²"),
            "avg_bua": f"{format_number(stats['avg_bua'])} m²" if stats["avg_bua"] else "0 m²",

            "avg_down_payment": f"{stats['avg_down_payment']:.1f}%" if stats["avg_down_payment"] else "N/A",

            "maintenance": f"{sample_unit.maintenance:.0f} EGP" if sample_unit and sample_unit.maintenance else "N/A",
            "cash_discount": f"{sample_unit.cash_discount:.1f}%" if sample_unit and sample_unit.cash_discount else "N/A",
            "delivery_percentage": f"{sample_unit.delivery_percentage:.1f}%" if sample_unit and sample_unit.delivery_percentage else "N/A",
            "last_updated": sample_unit.date_of_update.strftime("%Y-%m-%d") if sample_unit and sample_unit.date_of_update else "N/A",
            "months_from_update": sample_unit.months_from_update if sample_unit and sample_unit.months_from_update else "N/A",
            "source_of_info": sample_unit.source_of_info if sample_unit and sample_unit.source_of_info else "N/A",
            "notes": sample_unit.notes if sample_unit and sample_unit.notes else "",
        }

    # ---------------------------------------------------------
    # 6) Dashboard Context (template)
    # ---------------------------------------------------------
    @staticmethod
    def get_dashboard_context(*, user) -> ServiceResult:
        try:
            context = {
                "locations": MarketProjectLocation.objects.all().order_by("name"),
                "developers": MarketProjectDeveloper.objects.all().order_by("name"),
                "asset_types": MarketResearchService._distinct_list(MarketUnitData.objects.all(), "asset_type"),
                "unit_types": MarketResearchService._distinct_list(MarketUnitData.objects.all(), "unit_type"),
                "finishing_specs": MarketResearchService._distinct_list(MarketUnitData.objects.all(), "finishing_specs"),
                **build_base_context(user),
            }
            return MarketResearchService._ok(context)
        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 7) Dashboard KPIs API
    # ---------------------------------------------------------
    @staticmethod
    def dashboard_kpis(*, request) -> ServiceResult:
        try:
            filters = get_filters_from_request(request)
            qs = apply_filters(MarketUnitData.objects.all(), filters)

            # One aggregate instead of multiple
            stats = qs.aggregate(
                avg_price=Avg("unit_price"),
                avg_psm=Avg("psm"),
                avg_bua=Avg("bua"),
                avg_dp=Avg("down_payment"),
                min_price=Min("unit_price"),
                max_price=Max("unit_price"),
            )

            payload = {
                "total_units": qs.count(),
                "total_projects": qs.values("project_name").distinct().count(),
                "total_developers": qs.values("developer_name").distinct().count(),
                "total_locations": qs.values("location").distinct().count(),

                "avg_price": round(stats["avg_price"] or 0, 0),
                "avg_psm": round(stats["avg_psm"] or 0, 0),
                "avg_bua": round(stats["avg_bua"] or 0, 1),
                "avg_down_payment": round(stats["avg_dp"] or 0, 1),

                "min_price": stats["min_price"] or 0,
                "max_price": stats["max_price"] or 0,

                "recent_updates": qs.filter(
                    date_of_update__gte=datetime.now().date() - timedelta(days=30)
                ).count(),

                "price_range": (
                    f"{format_number(stats['min_price'])} - {format_number(stats['max_price'])}"
                    if stats["min_price"] and stats["max_price"] else "N/A"
                ),
            }

            return MarketResearchService._ok(payload)
        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 8) Dashboard Charts Data API
    # ---------------------------------------------------------
    @staticmethod
    def dashboard_charts_data(*, request) -> ServiceResult:
        try:
            filters = get_filters_from_request(request)
            qs = apply_filters(MarketUnitData.objects.all(), filters)

            payload = {
                "price_by_asset": list(
                    qs.values("asset_type")
                      .annotate(avg_price=Avg("unit_price"), count=Count("id"))
                      .filter(asset_type__isnull=False)
                      .order_by("-avg_price")
                ),
                "units_by_developer": list(
                    qs.values("developer_name")
                      .annotate(count=Count("id"), avg_price=Avg("unit_price"))
                      .filter(developer_name__isnull=False)
                      .order_by("-count")[:10]
                ),
                "price_vs_bua": list(
                    qs.filter(
                        unit_price__isnull=False,
                        bua__isnull=False,
                        bua__gt=0,
                        unit_price__gt=0
                    ).values("unit_price", "bua", "asset_type", "project_name")[:500]
                ),
                "units_by_location": list(
                    qs.values("location")
                      .annotate(count=Count("id"), avg_price=Avg("unit_price"))
                      .filter(location__isnull=False)
                      .order_by("-count")[:15]
                ),
                "price_by_finishing": list(
                    qs.values("finishing_specs")
                      .annotate(avg_price=Avg("unit_price"), count=Count("id"))
                      .filter(finishing_specs__isnull=False)
                      .order_by("-avg_price")
                ),
                "unit_type_distribution": list(
                    qs.values("unit_type")
                      .annotate(count=Count("id"))
                      .filter(unit_type__isnull=False)
                      .order_by("-count")
                ),
                "payment_analysis": list(
                    qs.values("payment_yrs")
                      .annotate(count=Count("id"), avg_down_payment=Avg("down_payment"))
                      .filter(payment_yrs__isnull=False)
                      .order_by("payment_yrs")
                ),
            }

            monthly_data = list(
                qs.filter(date_of_update__isnull=False)
                  .extra(select={"month": "DATE_FORMAT(date_of_update, '%%Y-%%m')"})
                  .values("month")
                  .annotate(count=Count("id"), avg_price=Avg("unit_price"))
                  .order_by("month")
            )
            payload["monthly_trends"] = monthly_data[-12:] if len(monthly_data) > 12 else monthly_data

            return MarketResearchService._ok(payload)
        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 9) Dashboard Filter Data API
    # ---------------------------------------------------------
    @staticmethod
    def dashboard_filter_data(*, request) -> ServiceResult:
        try:
            filters = get_filters_from_request(request)
            qs = apply_filters(MarketUnitData.objects.all(), filters)

            price_range = qs.aggregate(min_price=Min("unit_price"), max_price=Max("unit_price"))
            bua_range = qs.aggregate(min_bua=Min("bua"), max_bua=Max("bua"))

            payload = {
                "developers": list(
                    qs.values("developer_name").annotate(count=Count("id"))
                      .filter(developer_name__isnull=False).order_by("developer_name")
                ),
                "locations": list(
                    qs.values("location").annotate(count=Count("id"))
                      .filter(location__isnull=False).order_by("location")
                ),
                "asset_types": list(
                    qs.values("asset_type").annotate(count=Count("id"))
                      .filter(asset_type__isnull=False).order_by("asset_type")
                ),
                "unit_types": list(
                    qs.values("unit_type").annotate(count=Count("id"))
                      .filter(unit_type__isnull=False).order_by("unit_type")
                ),
                "finishing_specs": list(
                    qs.values("finishing_specs").annotate(count=Count("id"))
                      .filter(finishing_specs__isnull=False).order_by("finishing_specs")
                ),
                "price_range": {
                    "min": price_range["min_price"] or 0,
                    "max": price_range["max_price"] or 10000000000,
                },
                "bua_range": {
                    "min": bua_range["min_bua"] or 0,
                    "max": bua_range["max_bua"] or 10000,
                },
            }

            return MarketResearchService._ok(payload)
        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 10) Dashboard Export API
    # ---------------------------------------------------------
    @staticmethod
    def dashboard_export_data(*, request) -> ServiceResult:
        try:
            filters = get_filters_from_request(request)
            qs = apply_filters(MarketUnitData.objects.all(), filters)

            export_data = list(qs.values(
                "project_name", "developer_name", "location", "asset_type", "unit_type",
                "bua", "unit_price", "psm", "down_payment", "payment_yrs",
                "delivery_date", "finishing_specs", "maintenance"
            ))

            return MarketResearchService._ok({
                "data": export_data,
                "count": len(export_data),
                "filters_applied": filters,
            })
        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 11) Candlestick Dashboard Template Context
    # ---------------------------------------------------------
    @staticmethod
    def get_candlestick_dashboard_context(*, user) -> ServiceResult:
        try:
            return MarketResearchService._ok({
                "page_title": "Market Dashboard - Candlestick Charts",
                **build_base_context(user),
            })
        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 12) Candlestick Hierarchical Data API
    # ---------------------------------------------------------
    @staticmethod
    def get_candlestick_data(*, request) -> ServiceResult:
        try:
            queryset = MarketUnitData.objects.all()

            location_filter = request.GET.get("location", "")
            asset_type_filter = request.GET.get("asset_type", "")
            unit_type_filter = request.GET.get("unit_type", "")

            if location_filter:
                queryset = queryset.filter(location__icontains=location_filter)
            if asset_type_filter:
                queryset = queryset.filter(asset_type__icontains=asset_type_filter)
            if unit_type_filter:
                queryset = queryset.filter(unit_type__icontains=unit_type_filter)

            data = queryset.values(
                "finishing_specs", "developer_name", "project_name", "payment_yrs",
                "unit_price", "bua", "psm"
            ).exclude(finishing_specs__isnull=True)\
             .exclude(developer_name__isnull=True)\
             .exclude(project_name__isnull=True)\
             .exclude(payment_yrs__isnull=True)

            hierarchy: Dict[str, Any] = {}

            for item in data:
                fs = item["finishing_specs"] or "Unknown"
                dev = item["developer_name"] or "Unknown"
                proj = item["project_name"] or "Unknown"
                py = item["payment_yrs"] or "Unknown"

                bucket = hierarchy.setdefault(fs, {}).setdefault(dev, {}).setdefault(proj, {}).setdefault(
                    py, {"unit_prices": [], "bua_values": [], "psm_values": []}
                )

                if item["unit_price"] is not None:
                    bucket["unit_prices"].append(item["unit_price"])
                if item["bua"] is not None:
                    bucket["bua_values"].append(item["bua"])
                if item["psm"] is not None:
                    bucket["psm_values"].append(item["psm"])

            def stats(values: List[float]) -> Dict[str, Any]:
                if not values:
                    return {"min": 0, "avg": 0, "max": 0, "count": 0}
                return {"min": min(values), "avg": sum(values) / len(values), "max": max(values), "count": len(values)}

            processed: Dict[str, Any] = {}
            for fs, devs in hierarchy.items():
                processed[fs] = {}
                for dev, projs in devs.items():
                    processed[fs][dev] = {}
                    for proj, pys in projs.items():
                        processed[fs][dev][proj] = {}
                        for py, vals in pys.items():
                            processed[fs][dev][proj][py] = {
                                "unit_price": stats(vals["unit_prices"]),
                                "bua": stats(vals["bua_values"]),
                                "psm": stats(vals["psm_values"]),
                            }

            return MarketResearchService._ok({"success": True, "data": processed})

        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 13) Filter dropdown options for candlestick
    # ---------------------------------------------------------
    @staticmethod
    def get_filter_options() -> ServiceResult:
        try:
            locations = MarketResearchService._distinct_list(MarketUnitData.objects.all(), "location")
            asset_types = MarketResearchService._distinct_list(MarketUnitData.objects.all(), "asset_type")
            unit_types = MarketResearchService._distinct_list(MarketUnitData.objects.all(), "unit_type")

            return MarketResearchService._ok({
                "locations": locations,
                "asset_types": asset_types,
                "unit_types": unit_types,
            })
        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())

    # ---------------------------------------------------------
    # 14) Server-rendered hierarchical charts view
    # ---------------------------------------------------------
    @staticmethod
    def get_market_charts_view_context(*, user, request) -> ServiceResult:
        try:
            locations = request.GET.getlist("location")
            asset_types = request.GET.getlist("asset_type")
            unit_types = request.GET.getlist("unit_type")

            qs = MarketUnitData.objects.all()

            if locations and any(x.strip() for x in locations):
                qs = qs.filter(location__in=locations)
            if asset_types and any(x.strip() for x in asset_types):
                qs = qs.filter(asset_type__in=asset_types)
            if unit_types and any(x.strip() for x in unit_types):
                qs = qs.filter(unit_type__in=unit_types)

            grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))

            for item in qs:
                fs = item.finishing_specs.strip() if item.finishing_specs and item.finishing_specs.strip() else "Unknown"
                dev = item.developer_name.strip() if item.developer_name and item.developer_name.strip() else "Unknown"
                proj = item.project_name.strip() if item.project_name and item.project_name.strip() else "Unknown"
                py = str(item.payment_yrs) if item.payment_yrs is not None else "Unknown"

                grouped[fs][dev][proj][py].append({
                    "unit_price": item.unit_price,
                    "bua": item.bua,
                    "psm": item.psm,
                    "count": 1,
                })

            def build_chart_data(data_dict, metric_key: str):
                result = []
                for fs_key, devs in data_dict.items():
                    fs_group = {"label": fs_key, "children": []}
                    for dev_key, projs in devs.items():
                        dev_group = {"label": dev_key, "children": []}
                        for proj_key, pays in projs.items():
                            proj_group = {"label": proj_key, "children": []}
                            for pay_key, items in pays.items():
                                valid = [it for it in items if it.get(metric_key) is not None]
                                if not valid:
                                    continue

                                values = [it[metric_key] for it in valid]
                                weights = [it["count"] for it in valid]
                                total_w = sum(weights) or 0
                                if total_w == 0:
                                    continue

                                min_val = min(values)
                                max_val = max(values)
                                avg_val = sum(v * w for v, w in zip(values, weights)) / total_w

                                proj_group["children"].append({
                                    "label": pay_key,
                                    "min": min_val,
                                    "avg": avg_val,
                                    "max": max_val,
                                })

                            if proj_group["children"]:
                                dev_group["children"].append(proj_group)

                        if dev_group["children"]:
                            fs_group["children"].append(dev_group)

                    if fs_group["children"]:
                        result.append(fs_group)

                return result

            context = {
                "price_data": build_chart_data(grouped, "unit_price"),
                "bua_data": build_chart_data(grouped, "bua"),
                "psm_data": build_chart_data(grouped, "psm"),

                "locations": MarketUnitData.objects.values_list("location", flat=True).distinct().order_by("location"),
                "asset_types": MarketUnitData.objects.values_list("asset_type", flat=True).distinct().order_by("asset_type"),
                "unit_types": MarketUnitData.objects.values_list("unit_type", flat=True).distinct().order_by("unit_type"),

                "selected_locations": locations,
                "selected_asset_types": asset_types,
                "selected_unit_types": unit_types,

                **build_base_context(user),
            }

            return MarketResearchService._ok(context)

        except Exception as e:
            return MarketResearchService._fail(500, str(e), traceback.format_exc())
