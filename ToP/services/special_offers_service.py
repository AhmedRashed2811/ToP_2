# ToP/services/special_offers_service.py

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.shortcuts import get_object_or_404

from ..models import Project, ProjectExtendedPaymentsSpecialOffer
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
    """

    # =========================================================
    # SAVE (partial updates supported)
    # =========================================================
    @staticmethod
    def save(*, payload: Dict[str, Any]) -> ServiceResult:
        """
        Mirrors save_special_offer_payment_ajax logic:
        - project_id, year are required
        - delivery_index optional (update even if no other payment changes)
        - constant_discount optional (stored as decimal)
        - payment update optional (index+value), recalculates cumulatives ONLY if payment updated
        """
        try:
            project_id = int(payload["project_id"])
            year = int(payload["year"])

            project = get_object_or_404(Project, id=project_id)
            payment, _ = ProjectExtendedPaymentsSpecialOffer.objects.get_or_create(
                project=project, year=year
            )

            # -------- Delivery Index Update (preserved) --------
            if "delivery_index" in payload:
                # allow empty string "" as valid (preserved style: is not None)
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
                        # ignore invalid input (preserved)
                        pass

            # -------- Payment Value Update (preserved) --------
            payment_value_updated = False
            index = payload.get("index", None)
            value = payload.get("value", None)

            if index is not None and value is not None:
                try:
                    index_int = int(index)
                    value_float = float(value)  # percent number; conversion happens inside helper
                    payment_value_updated = True
                except (ValueError, TypeError):
                    payment_value_updated = False

            if payment_value_updated:
                # preserve installment range check (1..48) for index>=2
                # mapping: index 2 -> installment_1 ... index 49 -> installment_48
                if index_int >= 2:
                    installment_num = index_int - 1
                    if not (1 <= installment_num <= 48):
                        # out of range -> do nothing (preserved intent)
                        payment_value_updated = False

                if payment_value_updated:
                    # Use shared mapping:
                    # index 0 -> dp1, index 1 -> dp2, index>=2 -> installment_(index-1)
                    updates = [{"index": index_int, "value": value_float}]
                    apply_dual_payment_updates(payment, updates)

                    # Recalculate cumulatives ONLY if payment value updated (preserved)
                    recalc_dual_cumulatives(payment)

            # Save once (preserved)
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
    def fetch(*, project_id: int, year: int) -> ServiceResult:
        """
        Mirrors fetch_special_offer_payment_ajax:
        - Return dp1/dp2 as %
        - Return installment_1..48 as %
        - Include delivery_index if present
        - Include constant_discount as % if present
        """
        try:
            project = get_object_or_404(Project, id=project_id)
            payment = ProjectExtendedPaymentsSpecialOffer.objects.filter(
                project=project, year=year
            ).first()

            data: Dict[str, Any] = {}

            if payment:
                data["dp1"] = round((payment.dp1 or 0) * 100, 2)
                data["dp2"] = round((payment.dp2 or 0) * 100, 2)

                # Return installments as installment_1..installment_48 (preserved)
                for i in range(1, 49):
                    val = getattr(payment, f"installment_{i}", 0) or 0
                    data[f"installment_{i}"] = round(val * 100, 2)

                if payment.delivery_index:
                    data["delivery_index"] = payment.delivery_index

                # constant_discount as percentage (preserved)
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
    def delete(*, payload: Dict[str, Any]) -> ServiceResult:
        """
        Mirrors delete_special_offer_payment_ajax:
        - delete by project+year
        """
        try:
            project_id = int(payload["project_id"])
            year = int(payload["year"])

            project = get_object_or_404(Project, id=project_id)
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
