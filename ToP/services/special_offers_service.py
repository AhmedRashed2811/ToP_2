# ToP/services/special_offers_service.py

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.shortcuts import get_object_or_404

from ..models import Company, Project, ProjectExtendedPaymentsSpecialOffer
from ..utils.payments_plans_utils import apply_dual_payment_updates, recalc_dual_cumulatives


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None


class SpecialOffersPaymentsService:
    """
    Service layer for ProjectExtendedPaymentsSpecialOffer.
    - No HttpRequest dependency.
    - Preserves original behavior (critical).
    ✅ Uploader users are company-scoped: they can access ONLY their company projects.
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
        uploader_company = SpecialOffersPaymentsService._get_uploader_company(user)
        if not uploader_company:
            return True
        return project.company_id == uploader_company.id

    # =========================================================
    # SAVE (partial updates supported)
    # =========================================================
    @staticmethod
    def save(*, user, payload: Dict[str, Any]) -> ServiceResult:
        try:
            project_id = int(payload["project_id"])
            year = int(payload["year"])

            project = get_object_or_404(Project, id=project_id)

            # ✅ uploader/company restriction
            if not SpecialOffersPaymentsService._user_can_access_project(user, project):
                return ServiceResult(
                    success=False,
                    status=403,
                    payload={"success": False, "message": "Forbidden"},
                )

            payment, _ = ProjectExtendedPaymentsSpecialOffer.objects.get_or_create(
                project=project, year=year
            )

            # -------- Delivery Index Update (preserved) --------
            if "delivery_index" in payload:
                delivery_index = payload.get("delivery_index", None)
                if delivery_index is not None:
                    payment.delivery_index = delivery_index

            # -------- Constant Discount Update (preserved) --------
            if "constant_discount" in payload:
                constant_discount = payload.get("constant_discount", None)
                if constant_discount is not None:
                    try:
                        cd = float(constant_discount) / 100.0
                        payment.constant_discount = cd
                    except (ValueError, TypeError):
                        pass

            # -------- Payment Value Update (preserved) --------
            payment_value_updated = False
            index = payload.get("index", None)
            value = payload.get("value", None)

            if index is not None and value is not None:
                try:
                    index_int = int(index)
                    value_float = float(value)
                    payment_value_updated = True
                except (ValueError, TypeError):
                    payment_value_updated = False

            if payment_value_updated:
                if index_int >= 2:
                    installment_num = index_int - 1
                    if not (1 <= installment_num <= 48):
                        payment_value_updated = False

                if payment_value_updated:
                    updates = [{"index": index_int, "value": value_float}]
                    apply_dual_payment_updates(payment, updates)
                    recalc_dual_cumulatives(payment)

            payment.save()
            return ServiceResult(success=True, status=200, payload={"success": True})

        except Exception as e:
            traceback.print_exc()
            return ServiceResult(
                success=False,
                status=200,
                payload={"success": False, "message": str(e), "trace": traceback.format_exc()},
            )

    # =========================================================
    # FETCH
    # =========================================================
    @staticmethod
    def fetch(*, user, project_id: int, year: int) -> ServiceResult:
        try:
            project = get_object_or_404(Project, id=project_id)

            # ✅ uploader/company restriction
            if not SpecialOffersPaymentsService._user_can_access_project(user, project):
                return ServiceResult(
                    success=False,
                    status=403,
                    payload={"success": False, "message": "Forbidden"},
                )

            payment = ProjectExtendedPaymentsSpecialOffer.objects.filter(
                project=project, year=year
            ).first()

            data: Dict[str, Any] = {}

            if payment:
                data["dp1"] = round((payment.dp1 or 0) * 100, 2)
                data["dp2"] = round((payment.dp2 or 0) * 100, 2)

                for i in range(1, 49):
                    val = getattr(payment, f"installment_{i}", 0) or 0
                    data[f"installment_{i}"] = round(val * 100, 2)

                if payment.delivery_index:
                    data["delivery_index"] = payment.delivery_index

                if payment.constant_discount is not None:
                    data["constant_discount"] = round(payment.constant_discount * 100.0, 2)

            return ServiceResult(success=True, status=200, payload={"success": True, "data": data})

        except Exception as e:
            traceback.print_exc()
            return ServiceResult(
                success=False,
                status=200,
                payload={"success": False, "message": str(e), "trace": traceback.format_exc()},
            )

    # =========================================================
    # DELETE
    # =========================================================
    @staticmethod
    def delete(*, user, payload: Dict[str, Any]) -> ServiceResult:
        try:
            project_id = int(payload["project_id"])
            year = int(payload["year"])

            project = get_object_or_404(Project, id=project_id)

            # ✅ uploader/company restriction
            if not SpecialOffersPaymentsService._user_can_access_project(user, project):
                return ServiceResult(
                    success=False,
                    status=403,
                    payload={"success": False, "message": "Forbidden"},
                )

            payment = ProjectExtendedPaymentsSpecialOffer.objects.filter(project=project, year=year).first()

            if payment:
                payment.delete()
                return ServiceResult(
                    success=True,
                    status=200,
                    payload={"success": True, "message": "Payment plan deleted successfully."},
                )

            return ServiceResult(
                success=False,
                status=200,
                payload={"success": False, "message": "No matching payment plan found."},
            )

        except Exception as e:
            traceback.print_exc()
            return ServiceResult(success=False, status=200, payload={"success": False, "message": str(e)})
