# services.py (append this class)

from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import QueryDict # Import QueryDict

from ..models import (
    BaseNPV,
    GasPolicyFees,
    GasPolicyOffsets,
    MaintenancePolicyOffsets,
    CTD,
    MaintenancePolicyScheduling,
    # Add other related models if needed
)

class ConfigurationRecordDeletionService:
    """
    Handles deletion of specific configuration records (BaseNPV, Gas Fees/Offsets, Maintenance Offsets/Scheduling, CTD).
    Phase 4 – Step 1: Refactor deletion operations into a service.
    Logic and behavior are unchanged.
    """

    # ==================================================
    # PUBLIC ENTRY POINTS
    # ==================================================

    @staticmethod
    def delete_npv(*, user, npv_id):
        """
        Handles deletion of a BaseNPV record.
        """
        try:
            npv = BaseNPV.objects.get(id=npv_id)
            npv.delete()
            return {"success": True, "message": "NPV record deleted successfully!"}
        except BaseNPV.DoesNotExist:
            return {"success": False, "error": "NPV record not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_gas_fee(*, user, fee_id):
        """
        Handles deletion of a GasPolicyFees record.
        """
        try:
            fee = GasPolicyFees.objects.get(id=fee_id)
            fee.delete()
            return {"success": True, "message": "Gas Policy Fee deleted successfully!"}
        except GasPolicyFees.DoesNotExist:
            return {"success": False, "error": "Gas Policy Fee not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_gas_offset(*, user, offset_id):
        """
        Handles deletion of a GasPolicyOffsets record.
        """
        try:
            offset = GasPolicyOffsets.objects.get(id=offset_id)
            offset.delete()
            return {"success": True, "message": "Gas Policy Offset deleted successfully!"}
        except GasPolicyOffsets.DoesNotExist:
            return {"success": False, "error": "Gas Policy Offset not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_maintenance_offset(*, user, offset_id):
        """
        Handles deletion of a MaintenancePolicyOffsets record.
        """
        try:
            # Note: The original view had GasPolicyOffsets.DoesNotExist for this,
            # which seems like a bug. Corrected to MaintenancePolicyOffsets.DoesNotExist.
            offset = MaintenancePolicyOffsets.objects.get(id=offset_id)
            offset.delete()
            return {"success": True, "message": "Maintenance Policy Offset deleted successfully!"}
        except MaintenancePolicyOffsets.DoesNotExist:
            return {"success": False, "error": "Maintenance Policy Offset not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_ctd(*, user, ctd_id):
        """
        Handles deletion of a CTD record.
        """
        try:
            ctd = CTD.objects.get(id=ctd_id)
            ctd.delete()
            return {"success": True, "message": "CTD Value deleted successfully!"}
        except CTD.DoesNotExist:
            return {"success": False, "error": "CTD Value not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_maintenance_schedule(*, user, schedule_id):
        """
        Handles deletion of a MaintenancePolicyScheduling record.
        """
        try:
            schedule = MaintenancePolicyScheduling.objects.get(id=schedule_id)
            schedule.delete()
            return {"success": True, "message": "Maintenance Schedule deleted successfully!"}
        except MaintenancePolicyScheduling.DoesNotExist:
            return {"success": False, "error": "Maintenance Schedule not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
