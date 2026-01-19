# ToP/services/sales_team_report_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Count, Max, Sum, Q
from django.shortcuts import get_object_or_404

from ..models import Company, SalesTeam, SalesHead, Sales, Manager, SalesRequestAnalytical, User


@dataclass
class ServiceResult:
    ok: bool
    status: int
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SalesTeamReportService:
    """
    Sales Team Report (AJAX):
    - Admin/Business chooses company -> teams -> report
    - Manager auto locked to his company
    - SalesHead auto locked to his team
    """

    # You said: "admin or business (not related to a company)"
    # In your project BusinessTeam users are assigned to group "TeamMember" :contentReference[oaicite:2]{index=2}
    ADMINISH_GROUPS = ["Admin", "Developer", "TeamMember"]
    MANAGER_GROUP = "Manager"
    SALESHEAD_GROUP = "SalesHead"
    SALES_GROUP = "Sales"

    @staticmethod
    def _is_adminish(user: User) -> bool:
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=SalesTeamReportService.ADMINISH_GROUPS).exists()

    @staticmethod
    def _is_manager(user: User) -> bool:
        return user.groups.filter(name=SalesTeamReportService.MANAGER_GROUP).exists()

    @staticmethod
    def _is_saleshead(user: User) -> bool:
        return user.groups.filter(name=SalesTeamReportService.SALESHEAD_GROUP).exists()

    @staticmethod
    def _resolve_manager_company(user: User) -> Optional[Company]:
        mgr = Manager.objects.select_related("company").filter(user=user).first()
        return mgr.company if mgr and mgr.company else None  # :contentReference[oaicite:3]{index=3}

    @staticmethod
    def _resolve_saleshead_team(user: User) -> Tuple[Optional[Company], Optional[SalesTeam]]:
        head = SalesHead.objects.select_related("company", "team").filter(user=user).first()
        if not head:
            return None, None
        return head.company, head.team  # :contentReference[oaicite:4]{index=4}

    # -----------------------------
    # Page Context
    # -----------------------------
    @staticmethod
    def build_page_context(*, user: User) -> ServiceResult:
        try:
            mode = "ADMIN"
            companies = []
            initial_company_id = None
            company = None
            initial_team_id = None
            company_locked_name = None

            if SalesTeamReportService._is_saleshead(user):
                mode = "SALESHEAD"
                c, t = SalesTeamReportService._resolve_saleshead_team(user)
                if c:
                    initial_company_id = c.id
                    company_locked_name = c.name
                    company = c
                if t:
                    initial_team_id = t.id

            elif SalesTeamReportService._is_manager(user):
                mode = "MANAGER"
                c = SalesTeamReportService._resolve_manager_company(user)
                if c:
                    initial_company_id = c.id
                    company_locked_name = c.name
                    company = c

            else:
                # Admin/Business
                if not SalesTeamReportService._is_adminish(user):
                    return ServiceResult(False, 403, error="Not authorized.")
                companies = list(Company.objects.all().order_by("name"))

            return ServiceResult(
                True,
                200,
                payload={
                    "mode": mode,
                    "companies": companies,
                    "initial_company_id": initial_company_id,
                    "initial_team_id": initial_team_id,
                    "company_locked_name": company_locked_name,
                    "company": company
                },
            )
        except Exception as e:
            return ServiceResult(False, 500, error=str(e))

    # -----------------------------
    # AJAX: teams by company
    # -----------------------------
    @staticmethod
    def list_teams_for_user(*, user: User, company_id: Optional[int]) -> ServiceResult:
        try:
            # SalesHead: only his team
            if SalesTeamReportService._is_saleshead(user):
                c, t = SalesTeamReportService._resolve_saleshead_team(user)
                if not c or not t:
                    return ServiceResult(True, 200, payload={"company_id": None, "teams": []})
                return ServiceResult(True, 200, payload={"company_id": c.id, "teams": [{"id": t.id, "name": t.name}]})

            # Manager: only his company (ignore passed company_id)
            if SalesTeamReportService._is_manager(user):
                c = SalesTeamReportService._resolve_manager_company(user)
                if not c:
                    return ServiceResult(True, 200, payload={"company_id": None, "teams": []})
                teams = list(SalesTeam.objects.filter(company=c).order_by("name").values("id", "name"))
                return ServiceResult(True, 200, payload={"company_id": c.id, "teams": teams})

            # Admin/Business: any company_id must be provided
            if not SalesTeamReportService._is_adminish(user):
                return ServiceResult(False, 403, error="Not authorized.")

            if not company_id:
                return ServiceResult(True, 200, payload={"company_id": None, "teams": []})

            company = get_object_or_404(Company, id=company_id)
            teams = list(SalesTeam.objects.filter(company=company).order_by("name").values("id", "name"))
            return ServiceResult(True, 200, payload={"company_id": company.id, "teams": teams})

        except Exception as e:
            return ServiceResult(False, 500, error=str(e))

    # -----------------------------
    # AJAX: report by team
    # -----------------------------
    @staticmethod
    def build_team_report(*, user: User, team_id: int) -> ServiceResult:
        try:
            team = get_object_or_404(SalesTeam.objects.select_related("company"), id=team_id)

            # Security checks
            if SalesTeamReportService._is_saleshead(user):
                c, t = SalesTeamReportService._resolve_saleshead_team(user)
                if not t or t.id != team.id:
                    return ServiceResult(False, 403, error="Not allowed for this team.")

            elif SalesTeamReportService._is_manager(user):
                c = SalesTeamReportService._resolve_manager_company(user)
                if not c or c.id != team.company_id:
                    return ServiceResult(False, 403, error="Not allowed for this company/team.")

            else:
                if not SalesTeamReportService._is_adminish(user):
                    return ServiceResult(False, 403, error="Not authorized.")

            # Team heads & members (profiles)
            head_profiles = list(
                SalesHead.objects.filter(team=team).select_related("user").order_by("user__full_name")
            )
            member_profiles = list(
                Sales.objects.filter(team=team).select_related("user").order_by("user__full_name")
            )

            head_user_ids = [h.user_id for h in head_profiles]
            member_user_ids = [m.user_id for m in member_profiles]
            all_user_ids = list({*head_user_ids, *member_user_ids})

            analytics_map = SalesTeamReportService._aggregate_analytics(company_id=team.company_id, user_ids=all_user_ids)

            def row_for(u: User) -> Dict[str, Any]:
                a = analytics_map.get(u.id, {})
                last_dt = a.get("last_dt")
                return {
                    "id": u.id,
                    "full_name": u.full_name,
                    "email": u.email,
                    "total_requests": int(a.get("total", 0) or 0),
                    "approved_requests": int(a.get("approved", 0) or 0),
                    "fake_requests": int(a.get("fake", 0) or 0),
                    "last_request": last_dt.isoformat() if last_dt else None,
                    "sum_base_price": float(a.get("sum_base") or 0),
                    "approved_sum_final_price": float(a.get("sum_final") or 0),
                }

            heads_rows = [row_for(h.user) for h in head_profiles]
            members_rows = [row_for(m.user) for m in member_profiles]

            return ServiceResult(
                True,
                200,
                payload={
                    "company": {"id": team.company_id, "name": team.company.name},
                    "team": {"id": team.id, "name": team.name},
                    "heads": heads_rows,
                    "members": members_rows,
                },
            )

        except Exception as e:
            return ServiceResult(False, 500, error=str(e))

    @staticmethod
    def _aggregate_analytics(*, company_id: int, user_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        if not user_ids:
            return {}

        qs = (
            SalesRequestAnalytical.objects.filter(company_id=company_id, sales_man_id__in=user_ids)
            .values("sales_man_id")
            .annotate(
                total=Count("id"),
                approved=Count("id", filter=Q(is_approved=True)),
                fake=Count("id", filter=Q(is_fake=True)),
                last_dt=Max("date"),
                sum_base=Sum("base_price"),
                sum_final=Sum("final_price"),
            )
        )

        out: Dict[int, Dict[str, Any]] = {}
        for row in qs:
            out[int(row["sales_man_id"])] = row
        return out
