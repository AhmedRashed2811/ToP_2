# ToP/services/saved_units_service.py

from ..utils.units_pdf_utils import render_units_pdf_bytes


class SavedUnitsService:
    """
    Service layer for saved_units workflows.
    - Does NOT accept HttpRequest
    - Returns session operations + outputs for the view
    """

    @staticmethod
    def build_all_units_pdf(*, saved_units: list, template_path: str):
        """
        Returns:
          { success, status, pdf_bytes?, filename?, error_html? }
        """
        units = saved_units or []

        ok, out = render_units_pdf_bytes(units=units, template_path=template_path)
        if not ok:
            # Preserve your "show HTML on PDF error" behavior.
            return {
                "success": False,
                "status": 500,
                "error_html": out,
            }

        return {
            "success": True,
            "status": 200,
            "pdf_bytes": out,
            "filename": "all_units.pdf",
        }

    @staticmethod
    def clear_saved_units():
        """
        Returns session operations for the view.
        """
        return {
            "success": True,
            "status": 200,
            "session_ops": [
                {"op": "delete", "key": "saved_units"},
            ],
            "redirect": "home",
        }
