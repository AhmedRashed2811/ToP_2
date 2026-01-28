# ToP/services/pivot_units_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import re
from datetime import datetime, date
from decimal import Decimal

from django.utils import timezone
from django.db import models, transaction
from django.contrib.auth import get_user_model

from ToP.models import Company, Unit, PivotUnitsSnapshot


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    trace: Optional[str] = None


class PivotUnitsService:
    """
    Provides:
    - Data endpoint for the Pivot Builder (units + fields meta).
    - Save/overwrite pivot snapshot (HTML) for managers to DB.
    - Load that snapshot for manager view (AJAX).
    """

    # ---------------------------------------------------------------------
    # Company scoping helpers
    # ---------------------------------------------------------------------
    @staticmethod
    def get_user_scoped_company(user) -> Optional[Company]:
        profile_attrs = [
            "sales_head_profile",
            "sales_profile",
            "sales_ops_profile",
            "viewer_profile",
            "manager_profile",
            "uploader_profile",
            "company_admin_profile",
        ]
        for attr in profile_attrs:
            prof = getattr(user, attr, None)
            if prof and getattr(prof, "company_id", None):
                return prof.company
        return None

    @staticmethod
    def ensure_company_access(*, user, company_id: int) -> Tuple[bool, Optional[Company], str]:
        scoped = PivotUnitsService.get_user_scoped_company(user)
        if scoped and int(scoped.id) != int(company_id):
            return False, None, "Forbidden (company scope)."

        company = scoped or Company.objects.filter(id=company_id).first()
        if not company:
            return False, None, "Company not found."
        return True, company, ""

    @staticmethod
    def resolve_company_for_manager_view(*, user, company_id: Optional[int]) -> Tuple[bool, Optional[Company], str]:
        scoped = PivotUnitsService.get_user_scoped_company(user)
        if scoped:
            return True, scoped, ""

        if not company_id:
            return False, None, "Company ID is required."

        company = Company.objects.filter(id=company_id).first()
        if not company:
            return False, None, "Company not found."
        return True, company, ""

    # ---------------------------------------------------------------------
    # Pivot data (fields meta + units)
    # ---------------------------------------------------------------------
    @staticmethod
    def _field_type(field: models.Field) -> str:
        if isinstance(field, (models.IntegerField, models.FloatField, models.DecimalField, models.BigIntegerField)):
            return "number"
        if isinstance(field, (models.DateField, models.DateTimeField)):
            return "date"
        if isinstance(field, models.BooleanField):
            return "boolean"
        return "string"

    @staticmethod
    def _field_label(field: models.Field) -> str:
        try:
            vn = str(field.verbose_name).strip()
            if vn:
                return vn.title()
        except Exception:
            pass
        return field.name.replace("_", " ").title()

    @staticmethod
    def build_fields_meta() -> List[Dict[str, Any]]:
        fields_meta: List[Dict[str, Any]] = []
        for f in Unit._meta.fields:
            if getattr(f, "is_relation", False):
                continue
            fields_meta.append(
                {"name": f.name, "label": PivotUnitsService._field_label(f), "type": PivotUnitsService._field_type(f)}
            )
        fields_meta.sort(key=lambda x: (x["label"] or x["name"]).lower())
        return fields_meta

    @staticmethod
    def serialize_units(units_qs) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        unit_fields = [f for f in Unit._meta.fields if not getattr(f, "is_relation", False)]

        for u in units_qs:
            row: Dict[str, Any] = {}
            for f in unit_fields:
                v = getattr(u, f.name, None)

                if isinstance(v, (datetime, date)):
                    row[f.name] = v.isoformat()
                    continue

                if isinstance(v, Decimal):
                    try:
                        row[f.name] = float(v)
                    except Exception:
                        row[f.name] = None
                    continue

                row[f.name] = v
            out.append(row)

        return out

    @staticmethod
    def get_pivot_units_data(*, user, company_id: int) -> ServiceResult:
        allowed, company, err = PivotUnitsService.ensure_company_access(user=user, company_id=company_id)
        if not allowed:
            return ServiceResult(success=False, status=403, error=err)

        qs = Unit.objects.filter(company_id=company.id)
        units = PivotUnitsService.serialize_units(qs)

        payload = {
            "success": True,
            "company": {"id": company.id, "name": company.name},
            "count": len(units),
            "fields": PivotUnitsService.build_fields_meta(),
            "units": units,
        }
        return ServiceResult(success=True, status=200, payload=payload)

    # ---------------------------------------------------------------------
    # Snapshot storage ("Send Managers") -> DB (overwrite)
    # ---------------------------------------------------------------------
    @staticmethod
    def _sanitize_snapshot_html(html: str) -> str:
        if not html:
            return ""

        html = re.sub(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", html, flags=re.I | re.S)
        html = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", html, flags=re.I)
        html = re.sub(r"\son\w+\s*=\s*'[^']*'", "", html, flags=re.I)
        html = re.sub(r"(href|src)\s*=\s*\"javascript:[^\"]*\"", r'\1=""', html, flags=re.I)
        html = re.sub(r"(href|src)\s*=\s*'javascript:[^']*'", r"\1=''", html, flags=re.I)

        return html.strip()

    @staticmethod
    def save_pivot_snapshot(
        *,
        user,
        company_id: int,
        table_html: str,
        meta_text: str = "",
        measures_text: str = "",
    ) -> ServiceResult:
        allowed, company, err = PivotUnitsService.ensure_company_access(user=user, company_id=company_id)
        if not allowed:
            return ServiceResult(success=False, status=403, error=err)

        html = (table_html or "").strip()
        if not html or "<table" not in html:
            return ServiceResult(success=False, status=400, error="table_html must contain a rendered pivot table.")

        clean_html = PivotUnitsService._sanitize_snapshot_html(html)
        now = timezone.now()

        with transaction.atomic():
            PivotUnitsSnapshot.objects.update_or_create(
                company=company,
                defaults={
                    "table_html": clean_html,
                    "meta_text": (meta_text or "").strip(),
                    "measures_text": (measures_text or "").strip(),
                    "sent_at": now,
                    "sent_by": user if getattr(user, "is_authenticated", False) else None,
                },
            )

        return ServiceResult(
            success=True,
            status=200,
            payload={
                "success": True,
                "message": "Snapshot saved to DB (overwritten).",
                "company": {"id": company.id, "name": company.name},
                "sent_at": now.isoformat(),
            },
        )

    @staticmethod
    def load_pivot_snapshot(*, user, company_id: Optional[int]) -> ServiceResult:
        allowed, company, err = PivotUnitsService.resolve_company_for_manager_view(user=user, company_id=company_id)
        if not allowed:
            return ServiceResult(success=False, status=403, error=err)

        snap = PivotUnitsSnapshot.objects.filter(company=company).select_related("sent_by").first()

        if not snap:
            return ServiceResult(
                success=True,
                status=200,
                payload={
                    "success": True,
                    "company": {"id": company.id, "name": company.name},
                    "meta_text": "",
                    "measures_text": "",
                    "table_html": "",
                    "sent_at": None,
                    "sent_by": "",
                },
            )

        # resolve sent_by (name > email > username)
        sent_by = ""
        u = snap.sent_by
        if u:
            full = (f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}").strip()
            sent_by = full or getattr(u, "email", "") or getattr(u, "username", "") or ""

        return ServiceResult(
            success=True,
            status=200,
            payload={
                "success": True,
                "company": {"id": company.id, "name": company.name},
                "meta_text": snap.meta_text or "",
                "measures_text": snap.measures_text or "",
                "table_html": snap.table_html or "",
                "sent_at": snap.sent_at.isoformat() if snap.sent_at else None,
                "sent_by": sent_by,
            },
        )
