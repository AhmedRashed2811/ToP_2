# ToP/services/standard_payments_service.py

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.shortcuts import get_object_or_404

from ..models import Project, ProjectConfiguration, ProjectStanderdPayments
from ..utils.payments_plans_utils import apply_dual_payment_updates, recalc_dual_cumulatives


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ProjectStandardPaymentsService:
    """
    Standard payments logic (one plan per project).
    No HttpRequest dependency.
    """

    @staticmethod
    def save(*, payload: Dict[str, Any]) -> ServiceResult:
        """
        Preserves old save_standard_payment_ajax behavior.
        (Single index update only, but we reuse shared apply logic.)
        """
        try:
            project_id = int(payload["project_id"])
            index = int(payload["index"])
            value = float(payload["value"])  # keep as percent number; conversion happens in apply_dual_payment_updates

            project = get_object_or_404(Project, id=project_id)
            payment, _ = ProjectStanderdPayments.objects.get_or_create(project=project)

            # apply single update via shared helper
            updates = [{"index": index, "value": value}]
            apply_dual_payment_updates(payment, updates)

            # recalc cumulatives (preserved)
            recalc_dual_cumulatives(payment)

            payment.save()
            return ServiceResult(success=True, status=200, payload={"success": True})

        except Exception as e:
            traceback.print_exc()
            return ServiceResult(success=False, status=200, payload={"success": False, "message": str(e)})

    @staticmethod
    def fetch(*, project_id: int) -> ServiceResult:
        """
        Preserves old fetch_standard_payment_ajax behavior.
        """
        try:
            project = get_object_or_404(Project, id=project_id)
            payment = ProjectStanderdPayments.objects.filter(project=project).first()
            config = ProjectConfiguration.objects.filter(project=project).first()

            data: Dict[str, Any] = {}

            if payment:
                data["dp1"] = round((payment.dp1 or 0) * 100, 2)
                data["dp2"] = round((payment.dp2 or 0) * 100, 2)
                for i in range(48):
                    val = getattr(payment, f"installment_{i + 1}", 0) or 0
                    data[f"installment_{i}"] = round(val * 100, 2)

            interest_rate = float(config.interest_rate) if config and config.interest_rate else 0
            data["interest_rate"] = round(interest_rate, 5)

            return ServiceResult(success=True, status=200, payload={"success": True, "data": data})

        except Exception as e:
            traceback.print_exc()
            return ServiceResult(success=False, status=200, payload={"success": False, "message": str(e)})
