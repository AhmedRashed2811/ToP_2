from __future__ import annotations

from typing import Dict, List, Any, Optional

from django.shortcuts import get_object_or_404

from ..models import Company, SalesTeam, SalesHead, Sales, User


class SalesTeamService:
    """CRUD for SalesTeam + assignment of SalesHead and Sales members.

    CompanyAdmin restrictions (security enforced server-side):
    - Can only view/manage teams for their own company
    - Cannot create/update/delete teams in other companies
    - Cannot move a team to another company
    - Can only assign heads/members from their own company
    """

    @staticmethod
    def _actor_can_manage(actor: User) -> bool:
        if actor.is_superuser:
            return True
        return actor.groups.filter(name__in=["Admin", "CompanyAdmin"]).exists()

    @staticmethod
    def _get_actor_company(actor: User) -> Optional[Company]:
        """Returns the actor's company only if actor is CompanyAdmin (not Admin/Superuser)."""
        if actor.is_superuser or actor.groups.filter(name="Admin").exists():
            return None
        if actor.groups.filter(name="CompanyAdmin").exists():
            prof = getattr(actor, "company_admin_profile", None)
            if prof and getattr(prof, "company", None):
                return prof.company
        return None

    @staticmethod
    def _parse_ids(post_data, key: str) -> List[str]:
        raw = post_data.getlist(key) if hasattr(post_data, "getlist") else []
        return [str(x).strip() for x in raw if str(x).strip()]

    @staticmethod
    def sales_teams(*, actor: User, method: str, post_data) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = []

        if not SalesTeamService._actor_can_manage(actor):
            messages.append({"level": "error", "text": "You do not have permission to manage sales teams."})
            return {"redirect": "home", "messages": messages}

        actor_company = SalesTeamService._get_actor_company(actor)
        is_company_admin = actor_company is not None

        if method == "POST":
            action = (post_data.get("action") or "").strip()

            if action == "create":
                company_id = post_data.get("company_id")
                name = (post_data.get("name") or "").strip()

                # CompanyAdmin: force company to own company
                if is_company_admin:
                    if str(company_id or "") != str(actor_company.id):
                        messages.append({"level": "error", "text": "Permission Denied: You can only create teams for your company."})
                        return {"redirect": "sales_teams", "messages": messages}

                if not company_id or not name:
                    messages.append({"level": "error", "text": "Company and Team Name are required."})
                else:
                    company = get_object_or_404(Company, id=company_id)
                    SalesTeam.objects.create(company=company, name=name)
                    messages.append({"level": "success", "text": "Team created successfully."})

                return {"redirect": "sales_teams", "messages": messages}

            if action == "update":
                team_id = post_data.get("team_id")
                team = get_object_or_404(SalesTeam, id=team_id)

                # CompanyAdmin: can only edit their own company's teams
                if is_company_admin and str(team.company_id) != str(actor_company.id):
                    messages.append({"level": "error", "text": "Permission Denied: You can only manage teams for your company."})
                    return {"redirect": "sales_teams", "messages": messages}

                new_company_id = post_data.get("company_id")
                new_name = (post_data.get("name") or "").strip()

                # CompanyAdmin: block moving companies
                if is_company_admin:
                    new_company_id = str(actor_company.id)

                if new_company_id and str(new_company_id) != str(team.company_id):
                    team.company = get_object_or_404(Company, id=new_company_id)

                if new_name:
                    team.name = new_name
                team.save()

                # Assign heads/members (only within team.company)
                head_ids = SalesTeamService._parse_ids(post_data, "head_ids")
                member_ids = SalesTeamService._parse_ids(post_data, "member_ids")

                # Heads: set selected to this team, unselect removed heads
                current_heads = SalesHead.objects.filter(team=team)
                current_heads.exclude(id__in=head_ids).update(team=None)

                selected_heads = SalesHead.objects.filter(pk__in=head_ids, company=team.company)
                selected_heads.update(team=team)

                # Members: set selected to this team, unselect removed members
                current_members = Sales.objects.filter(team=team)
                current_members.exclude(id__in=member_ids).update(team=None)

                selected_members = Sales.objects.filter(pk__in=member_ids, company=team.company)
                selected_members.update(team=team)

                messages.append({"level": "success", "text": "Team updated successfully."})
                return {"redirect": "sales_teams", "messages": messages}

            if action == "delete":
                team_id = post_data.get("team_id")
                team = get_object_or_404(SalesTeam, id=team_id)

                # CompanyAdmin: can only delete their company's teams
                if is_company_admin and str(team.company_id) != str(actor_company.id):
                    messages.append({"level": "error", "text": "Permission Denied: You can only manage teams for your company."})
                    return {"redirect": "sales_teams", "messages": messages}

                # detach assignments first (clean UX)
                SalesHead.objects.filter(team=team).update(team=None)
                Sales.objects.filter(team=team).update(team=None)

                team.delete()
                messages.append({"level": "success", "text": "Team deleted successfully."})
                return {"redirect": "sales_teams", "messages": messages}

        # GET => context
        teams_qs = SalesTeam.objects.select_related("company").prefetch_related("heads__user", "members__user")
        companies_qs = Company.objects.all()
        heads_qs = SalesHead.objects.select_related("user", "company", "team")
        sales_qs = Sales.objects.select_related("user", "company", "team")

        if is_company_admin:
            teams_qs = teams_qs.filter(company=actor_company)
            companies_qs = companies_qs.filter(id=actor_company.id)
            heads_qs = heads_qs.filter(company=actor_company)
            sales_qs = sales_qs.filter(company=actor_company)

        teams = teams_qs.order_by("company__name", "name")
        companies = companies_qs.order_by("name")
        heads = heads_qs.order_by("company__name", "user__full_name")
        sales = sales_qs.order_by("company__name", "user__full_name")

        return {
            "context": {
                "teams": teams,
                "companies": companies,
                "heads": heads,
                "sales_members": sales,
                "is_company_admin": bool(is_company_admin),
                "actor_company_id": actor_company.id if actor_company else None,
            },
            "messages": messages,
        }
