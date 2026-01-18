# ToP/services/extended_payments_service.py

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

from django.shortcuts import get_object_or_404

from ..models import Company, Project, ProjectConfiguration, ProjectExtendedPayments
from ..utils.payments_plans_utils import (
    normalize_updates,
    apply_dual_payment_updates,
    recalc_dual_cumulatives,
)


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ProjectExtendedPaymentsService:
    """
    Extended payments logic (year + scheme + bulk updates + disable flag).
    ✅ Uploader users are company-scoped: they can access ONLY their company projects.
    No HttpRequest dependency.
    """

    # =========================================================
    # Uploader scoping helpers (NEW)
    # =========================================================
    @staticmethod
    def _get_uploader_company(user) -> Optional[Company]:
        uploader_profile = getattr(user, "uploader_profile", None)
        if uploader_profile and getattr(uploader_profile, "company_id", None):
            return uploader_profile.company
        return None

    @staticmethod
    def _user_can_access_project(user, project: Project) -> bool:
        uploader_company = ProjectExtendedPaymentsService._get_uploader_company(user)
        if not uploader_company:
            return True
        return project.company_id == uploader_company.id

    # =========================================================
    # SAVE
    # =========================================================
    @staticmethod
    def save(*, user, payload: Dict[str, Any]) -> ServiceResult:
        """
        Preserves old save_extended_payment_ajax behavior + adds uploader restriction.
        """
        try:
            project_id = int(payload["project_id"])
            year = int(payload.get("year", 1))
            scheme = payload.get("scheme", "flat")

            project = get_object_or_404(Project, id=project_id)

            # ✅ uploader/company restriction
            if not ProjectExtendedPaymentsService._user_can_access_project(user, project):
                return ServiceResult(
                    success=False,
                    status=403,
                    payload={"success": False, "message": "Forbidden"},
                )

            payment, _ = ProjectExtendedPayments.objects.get_or_create(
                project=project, year=year, scheme=scheme
            )

            # 1) Update flag if present (preserved)
            if "disable_additional_discount" in payload:
                payment.disable_additional_discount = bool(payload["disable_additional_discount"])

            # 2) Normalize updates (bulk or single) (preserved)
            updates, _ = normalize_updates(payload)

            # 3) Apply updates in memory (preserved mapping)
            apply_dual_payment_updates(payment, updates)

            # 4) Recalculate cumulatives once (preserved)
            recalc_dual_cumulatives(payment)

            # 5) Save once (preserved)
            payment.save()

            return ServiceResult(success=True, status=200, payload={"success": True})

        except Exception as e:
            traceback.print_exc()
            return ServiceResult(
                success=False,
                status=200,
                payload={"success": False, "message": str(e)},
            )

    # =========================================================
    # FETCH
    # =========================================================
    @staticmethod
    def fetch(*, user, project_id: int, year: int = 1, scheme: str = "flat") -> ServiceResult:
        """
        Preserves old fetch_extended_payment_ajax behavior + adds uploader restriction.
        """
        try:
            project = get_object_or_404(Project, id=project_id)

            # ✅ uploader/company restriction
            if not ProjectExtendedPaymentsService._user_can_access_project(user, project):
                return ServiceResult(
                    success=False,
                    status=403,
                    payload={"success": False, "message": "Forbidden"},
                )

            payment = ProjectExtendedPayments.objects.filter(project=project, year=year, scheme=scheme).first()
            config = ProjectConfiguration.objects.filter(project=project).first()

            data: Dict[str, Any] = {}

            if payment:
                data["dp1"] = round((payment.dp1 or 0) * 100, 4)
                data["dp2"] = round((payment.dp2 or 0) * 100, 4)

                # installment_0..47 in response (mapped to installment_1..48 in DB)
                for i in range(48):
                    val = getattr(payment, f"installment_{i + 1}", 0) or 0
                    data[f"installment_{i}"] = round(val * 100, 4)

                data["disable_additional_discount"] = bool(payment.disable_additional_discount)
            else:
                data["disable_additional_discount"] = False

            interest_rate = float(config.interest_rate) if config and config.interest_rate else 0
            data["interest_rate"] = round(interest_rate, 5)

            return ServiceResult(success=True, status=200, payload={"success": True, "data": data})

        except Exception as e:
            traceback.print_exc()
            return ServiceResult(
                success=False,
                status=200,
                payload={"success": False, "message": str(e)},
            )

    # =========================================================
    # DELETE
    # =========================================================
    @staticmethod
    def delete(*, user, payload: Dict[str, Any]) -> ServiceResult:
        """
        Preserves old delete_extended_payment_ajax behavior + adds uploader restriction.
        """
        try:
            project_id = int(payload.get("project_id"))
            year = int(payload.get("year"))
            scheme = payload.get("scheme")

            project = get_object_or_404(Project, id=project_id)

            # ✅ uploader/company restriction
            if not ProjectExtendedPaymentsService._user_can_access_project(user, project):
                return ServiceResult(
                    success=False,
                    status=403,
                    payload={"success": False, "message": "Forbidden"},
                )

            deleted_count, _ = ProjectExtendedPayments.objects.filter(
                project=project,
                year=year,
                scheme=scheme,
            ).delete()

            if deleted_count > 0:
                return ServiceResult(
                    success=True,
                    status=200,
                    payload={"success": True, "message": "Plan deleted successfully."},
                )

            return ServiceResult(
                success=False,
                status=200,
                payload={"success": False, "message": "No plan found to delete."},
            )

        except Exception as e:
            traceback.print_exc()
            return ServiceResult(
                success=False,
                status=200,
                payload={"success": False, "message": str(e)},
            )
