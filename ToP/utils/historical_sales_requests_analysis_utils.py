from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..models import Company, CompanyUser, CompanyManager


@dataclass
class HistoricalAnalysisScope:
    role: str  # "admin_like" | "manager" | "sales" | "other"
    company: Optional[Company] = None


def _in_group(user, name: str) -> bool:
    return user.groups.filter(name=name).exists()


def resolve_historical_analysis_scope(*, user) -> HistoricalAnalysisScope:
    """
    Rules:
    - Admin/Developer/TeamMember => admin_like (can choose company)
    - Manager group => manager (company fixed)
    - Client group + user.role == "CompanyUser" => sales (only own data, company fixed)
    """
    if _in_group(user, "Admin") or _in_group(user, "Developer") or _in_group(user, "TeamMember"):
        return HistoricalAnalysisScope(role="admin_like", company=None)

    if _in_group(user, "Manager"):
        manager = CompanyManager.objects.filter(user=user).select_related("company").first()
        return HistoricalAnalysisScope(role="manager", company=manager.company if manager else None)

    if _in_group(user, "Client") and getattr(user, "role", None) == "CompanyUser":
        cu = CompanyUser.objects.filter(user=user).select_related("company").first()
        return HistoricalAnalysisScope(role="sales", company=cu.company if cu else None)

    return HistoricalAnalysisScope(role="other", company=None)
