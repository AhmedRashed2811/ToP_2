import json
import traceback
from datetime import datetime
from dateutil.relativedelta import relativedelta

from ..models import (
    Unit,
    ProjectConfiguration,
    Constraints,
    ProjectWebConfiguration,
    BaseNPV,
    ProjectExtendedPayments,
    ProjectExtendedPaymentsSpecialOffer,
    GasPolicy,
    MaintenancePolicy,
)

from ..calculations import (
    calculate_max_tenor_years,
    apply_constraints,
    calculate_period_rate,
    calculate_price_with_interest,
    calculate_percentage_change,
    calculate_gas_payments,
    calculate_maintenance_payments,
)

PERIODS_PER_YEAR = {
    "monthly": 12,
    "quarterly": 4,
    "semi-annually": 2,
    "annually": 1,
}


class TopCalculationService:
    """
    Phase 2 – Step 1
    Structural refactor ONLY.
    Logic and behavior are unchanged.
    """

    # =====================================================
    # PUBLIC ENTRY POINT
    # =====================================================

    @staticmethod
    def calculate(*, user, data):
        parsed = TopCalculationService._parse_request_data(data)

        payment_scheme = TopCalculationService._resolve_payment_scheme(
            parsed["payment_scheme_2"]
        )

        project_ctx = TopCalculationService._resolve_project_context(
            parsed, payment_scheme
        )

        delivery_date = TopCalculationService._resolve_delivery_date(
            parsed, project_ctx["project_config"]
        )

        tenor_ctx = TopCalculationService._resolve_tenor(
            parsed, project_ctx["project_config"]
        )
        if tenor_ctx.get("error"):
            return tenor_ctx["error"]

        base_npv_ctx = TopCalculationService._resolve_base_npv(
            parsed,
            project_ctx["project_config"],
            tenor_ctx["tenor_years"]
        )

        payment_ctx = TopCalculationService._calculate_payment_plan(
            parsed,
            project_ctx,
            tenor_ctx,
            payment_scheme,
            delivery_date,
        )

        pricing_ctx = TopCalculationService._calculate_pricing(
            parsed,
            project_ctx,
            payment_ctx,
            base_npv_ctx,
            tenor_ctx,
            payment_scheme,
            delivery_date,
        )

        gas_ctx, maintenance_ctx = TopCalculationService._calculate_gas_and_maintenance(
            parsed,
            project_ctx,
            tenor_ctx,
            payment_ctx,
            delivery_date,
        )

        return TopCalculationService._build_response(
            parsed,
            tenor_ctx,
            payment_ctx,
            pricing_ctx,
            gas_ctx,
            maintenance_ctx,
            delivery_date,
        )

    # =====================================================
    # REQUEST PARSING
    # =====================================================

    @staticmethod
    def _parse_request_data(data):
        try:
            installment_percentages = json.loads(
                data.get("installment_data", "[]")
            )
        except json.JSONDecodeError:
            installment_percentages = []

        try:
            indixes = json.loads(data.get("indixes", "[]"))
        except json.JSONDecodeError:
            indixes = []

        installment_percentages_dict = dict(zip(indixes, installment_percentages))

        base_price = data.get("unit_base_price")
        price_discount = data.get("price_discount", "0")

        try:
            discount_percentage = float(price_discount)
            if discount_percentage > 0:
                base_price = str(
                    float(base_price) * (1 - discount_percentage / 100)
                )
        except:
            pass

        return {
            "installment_percentages": installment_percentages,
            "installment_percentages_dict": installment_percentages_dict,
            "base_price": base_price,
            "interest_rate": data.get("project_config_interest_rate"),
            "base_dp": data.get("project_config_base_dp"),
            "base_tenor_years": data.get("project_config_base_tenor"),
            "max_tenor_years_received": data.get("project_config_max_tenor"),
            "base_payment_frequency": data.get(
                "project_config_payment_frequency"
            ),
            "payment_scheme_2": data.get(
                "project_config_default_scheme"
            ),
            "max_discount": data.get(
                "project_constraints_max_discount"
            ),
            "maintenance_fee_percent": data.get(
                "unit_maintenance_percent"
            ),
            "unit_code": data.get("unit_code"),
            "currency_rate": data.get("currency_rate"),
            "selected_tenor_years": float(
                data.get("tenor_years")
            ),
            "project_config_id": data.get("project_config_id"),
            "delivery_date": data.get("delivery_date"),
            "dp": data.get("dp"),
            "contract_date": data.get("contract_date"),
            "special_offer": data.get("special_offers"),
            "static_npv": data.get("project_config_static_npv") == "True",
        }

    # =====================================================
    # PAYMENT SCHEME
    # =====================================================

    @staticmethod
    def _resolve_payment_scheme(payment_scheme_2):
        if payment_scheme_2 in ["Flat Back Loaded", "FlatBackLoaded"]:
            return "flat_back_loaded"
        elif payment_scheme_2 in ["Bullet Back Loaded", "BulletBackLoaded"]:
            return "bullet_back_loaded"
        elif payment_scheme_2 == "Flat":
            return "flat"
        elif payment_scheme_2 == "Bullet":
            return "bullet"
        return None

    # =====================================================
    # PROJECT CONTEXT
    # =====================================================

    @staticmethod
    def _resolve_project_context(data, payment_scheme):
        unit = Unit.objects.filter(unit_code=data["unit_code"]).first()
        project_config = ProjectConfiguration.objects.filter(
            id=data["project_config_id"]
        ).first()
        project_constraints = Constraints.objects.filter(
            project_config=project_config
        ).first()
        project_web_config = ProjectWebConfiguration.objects.filter(
            project=project_config.project
        ).first()

        try:
            if project_web_config.show_payment_scheme is False:
                if (
                    project_config.default_scheme
                    != data["payment_scheme_2"].replace(" ", "")
                ):
                    return {"force_logout": True}
        except:
            pass

        return {
            "unit": unit,
            "project_config": project_config,
            "project_constraints": project_constraints,
            "project_web_config": project_web_config,
        }

    # =====================================================
    # DELIVERY DATE
    # =====================================================

    @staticmethod
    def _resolve_delivery_date(data, project_config):
        if data["delivery_date"]:
            return data["delivery_date"]

        return None

    # =====================================================
    # TENOR
    # =====================================================

    @staticmethod
    def _resolve_tenor(data, project_config):
        tenor_years, max_tenor_years = calculate_max_tenor_years(
            project_config,
            data["selected_tenor_years"],
        )

        tenor_years = float(tenor_years)
        max_tenor_years = float(max_tenor_years)

        if float(data["max_tenor_years_received"]) > 0:
            max_tenor_years = float(data["max_tenor_years_received"])

        if data["selected_tenor_years"] > max_tenor_years:
            return {
                "error": {
                    "tenor_years_error": f"Tenor Years Can not Exceed {max_tenor_years}"
                }
            }

        return {
            "tenor_years": tenor_years,
            "max_tenor_years": max_tenor_years,
        }

    # =====================================================
    # BASE NPV
    # =====================================================

    @staticmethod
    def _resolve_base_npv(parsed, project_config, tenor_years):
        base_npv = 0
        have_static_npv = False

        if parsed["static_npv"]:
            have_static_npv = True
            base_npvs = BaseNPV.objects.filter(project_config=project_config)
            if base_npvs.exists():
                base_npvs_dict = {
                    float(npv.term_period): npv.npv_value for npv in base_npvs
                }
                diffs = {
                    abs(tenor_years - k): v for k, v in base_npvs_dict.items()
                }
                base_npv = diffs[min(diffs.keys())]

        return {
            "base_npv": base_npv,
            "have_static_npv": have_static_npv,
        }

    # =====================================================
    # PAYMENT PLAN
    # =====================================================

    @staticmethod
    def _calculate_payment_plan(data, project_ctx, tenor_ctx, payment_scheme, delivery_date):
        periods_per_year = PERIODS_PER_YEAR[data["base_payment_frequency"].lower()]
        n = int(tenor_ctx["tenor_years"]) * periods_per_year

        installment_dict = data["installment_percentages_dict"]
        excess_input = 0

        for k in list(installment_dict.keys()):
            if k > n:
                excess_input += installment_dict[k]
                del installment_dict[k]
        if excess_input > 0:
            installment_dict[n] = excess_input

        payment_plan = ProjectExtendedPayments.objects.filter(
            project=project_ctx["project_config"].project,
            year=tenor_ctx["tenor_years"],
            scheme=payment_scheme,
        ).first()

        if payment_plan:
            new_base_dp = (payment_plan.dp1 + payment_plan.dp2) * 100
            var_dp = payment_plan.dp1 + payment_plan.dp2
        else:
            new_base_dp = float(data["base_dp"]) * 100
            var_dp = float(data["base_dp"])

        if len(installment_dict) == 0 or 0 not in installment_dict:
            dp_percentage = var_dp
        else:
            dp_percentage = data["dp"] if data["dp"] >= var_dp else var_dp

        calculated_pmt_percentages = [55555] * (n + 1)
        calculated_pmt_percentages[0] = dp_percentage

        if data["special_offer"] == "undefined":
            calculated_pmt_percentages, delivery_payment_index = apply_constraints(
                data["dp"],
                calculated_pmt_percentages,
                tenor_ctx["tenor_years"],
                periods_per_year,
                installment_dict,
                project_ctx["project_constraints"],
                data["contract_date"],
                delivery_date,
                payment_scheme,
                special_offer=None,
            )
        else:
            calculated_pmt_percentages, delivery_payment_index = apply_constraints(
                data["dp"],
                calculated_pmt_percentages,
                tenor_ctx["tenor_years"],
                periods_per_year,
                installment_dict,
                project_ctx["project_constraints"],
                data["contract_date"],
                delivery_date,
                payment_scheme,
                data["special_offer"],
            )

        return {
            "periods_per_year": periods_per_year,
            "n": n,
            "payment_plan": payment_plan,
            "new_base_dp": new_base_dp,
            "calculated_pmt_percentages": calculated_pmt_percentages,
            "delivery_payment_index": delivery_payment_index,
        }

    # =====================================================
    # PRICING
    # =====================================================

    @staticmethod
    def _calculate_pricing(
        data, project_ctx, payment_ctx, base_npv_ctx, tenor_ctx, payment_scheme, delivery_date
    ):
        interest_rate = data["interest_rate"]
        periods_per_year = payment_ctx["periods_per_year"]

        r = float(project_ctx["project_config"].interest_rate)
        quarterly_rate = (1 + r) ** (1 / 4) - 1

        dp = payment_ctx["calculated_pmt_percentages"][0]
        installments = payment_ctx["calculated_pmt_percentages"][1:]

        new_npv = sum(
            cf / ((1 + quarterly_rate) ** (i + 1))
            for i, cf in enumerate(installments)
        ) + dp

        if not base_npv_ctx["have_static_npv"]:
            base_period_rate = calculate_period_rate(
                interest_rate,
                PERIODS_PER_YEAR[data["base_payment_frequency"].lower()],
            )
            base_npv = float(data["base_dp"])
            for i, pmt in enumerate(payment_ctx["calculated_pmt_percentages"][1:], start=1):
                base_npv += float(pmt) * (1 + float(base_period_rate)) ** (-i)
        else:
            base_npv = base_npv_ctx["base_npv"]

        special_offer = data["special_offer"] or "undefined"

        try:
            if special_offer != "undefined":
                special_offer_constant_discount = (
                    ProjectExtendedPaymentsSpecialOffer.objects.filter(
                        project=project_ctx["project_config"].project,
                        year=tenor_ctx["tenor_years"],
                    ).first().constant_discount
                )
            else:
                special_offer_constant_discount = 0
        except:
            special_offer_constant_discount = 0

        additional_discount_var = None
        project_web_config = project_ctx["project_web_config"]

        if project_web_config.show_additional_discount:
            additional_discount = float(project_web_config.additional_discount)
            needed_dp = float(project_web_config.dp_for_additional_discount)

            if payment_ctx["payment_plan"] and payment_ctx["payment_plan"].disable_additional_discount:
                additional_discount = 0

            if payment_ctx["calculated_pmt_percentages"][0] >= needed_dp / 100:
                additional_discount_var = additional_discount
                price_with_interest = calculate_price_with_interest(
                    base_npv,
                    new_npv,
                    data["max_discount"],
                    data["base_price"],
                    additional_discount_var,
                    special_offer,
                    project_web_config.real_discount,
                    special_offer_constant_discount,
                )
            else:
                price_with_interest = calculate_price_with_interest(
                    base_npv,
                    new_npv,
                    data["max_discount"],
                    data["base_price"],
                    None,
                    special_offer,
                    project_web_config.real_discount,
                    special_offer_constant_discount,
                )
        else:
            price_with_interest = calculate_price_with_interest(
                base_npv,
                new_npv,
                data["max_discount"],
                data["base_price"],
                None,
                special_offer,
                project_web_config.real_discount,
                special_offer_constant_discount,
            )

        percentage_change = calculate_percentage_change(
            base_npv,
            new_npv,
            data["max_discount"],
            special_offer,
            project_web_config.real_discount,
            special_offer_constant_discount,
        )

        return {
            "base_npv": base_npv,
            "new_npv": new_npv,
            "price_with_interest": price_with_interest,
            "percentage_change": percentage_change,
            "additional_discount_var": additional_discount_var,
        }

    # =====================================================
    # GAS & MAINTENANCE
    # =====================================================

    @staticmethod
    def _calculate_gas_and_maintenance(data, project_ctx, tenor_ctx, payment_ctx, delivery_date):
        periods_per_year = payment_ctx["periods_per_year"]
        n = payment_ctx["n"]

        project_web_config = project_ctx["project_web_config"]

        # =====================================================
        # GAS (RESPECT show_gas)
        # =====================================================
        if not project_web_config.show_gas:
            gas_payments = [0] * (n + 1)
            sum_gas = 0
        else:
            try:
                project_gas_policy = GasPolicy.objects.filter(
                    project_config=project_ctx["project_config"]
                ).first()

                if project_gas_policy and project_gas_policy.is_applied:
                    gas_payments = calculate_gas_payments(
                        project_gas_policy,
                        tenor_ctx["tenor_years"],
                        periods_per_year,
                        data["contract_date"],
                        delivery_date,
                        payment_ctx["delivery_payment_index"],
                    )
                else:
                    gas_payments = [0] * (n + 1)
            except:
                gas_payments = [0] * (n + 1)

            try:
                sum_gas = sum(p for p in gas_payments if p != "")
            except:
                sum_gas = 0

        # =====================================================
        # MAINTENANCE (RESPECT show_maintenance)
        # =====================================================
        if not project_web_config.show_maintenance:
            maintenance_payments = [0] * (n + 1)
            maintenance = 0
        else:
            try:
                project_maintenance_policy = MaintenancePolicy.objects.filter(
                    project_config=project_ctx["project_config"]
                ).first()

                maintenance_fee_percent = float(data["maintenance_fee_percent"] or 0)
                x = round(
                    maintenance_fee_percent
                    * payment_ctx["calculated_pmt_percentages"][0],
                    -3,
                )

                if project_maintenance_policy and project_maintenance_policy.is_applied:
                    maintenance_payments = calculate_maintenance_payments(
                        project_maintenance_policy,
                        x,
                        tenor_ctx["tenor_years"],
                        periods_per_year,
                        data["contract_date"],
                        delivery_date,
                        payment_ctx["delivery_payment_index"],
                        data["currency_rate"],
                    )
                else:
                    maintenance_payments = [0] * (n + 1)

                maintenance = sum(p for p in maintenance_payments if p != "")
            except Exception:
                maintenance_payments = []
                maintenance = 0
                traceback.print_exc()

        return (
            {"gas_payments": gas_payments, "gas_fees": sum_gas},
            {
                "maintenance_payments": maintenance_payments,
                "maintenance": maintenance,
            },
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    @staticmethod
    def _build_response(
        data, tenor_ctx, payment_ctx, pricing_ctx, gas_ctx, maintenance_ctx, delivery_date
    ):
        payment_plan = payment_ctx["payment_plan"]

        return {
            "calculated_pmt_percentages": payment_ctx["calculated_pmt_percentages"],
            "new_base_dp": payment_ctx["new_base_dp"],
            "dp1": (payment_plan.dp1 * 100) if payment_plan else (payment_ctx["new_base_dp"] / 2),
            "dp2": (payment_plan.dp2 * 100) if payment_plan else (payment_ctx["new_base_dp"] / 2),
            "delivery_payment_index": payment_ctx["delivery_payment_index"],
            "delivery_date": delivery_date,
            "new_npv": pricing_ctx["new_npv"],
            "percentage_change": pricing_ctx["percentage_change"],
            "price_with_interest": pricing_ctx["price_with_interest"],
            "contract_date": data["contract_date"] or "",
            "gas_payments": gas_ctx["gas_payments"],
            "maintenance_payments": maintenance_ctx["maintenance_payments"],
            "maintenance": maintenance_ctx["maintenance"],
            "gas_fees": gas_ctx["gas_fees"],
            "tenor_years": tenor_ctx["tenor_years"],
            "tenor_years_error": None,
            "additional_discount_var": pricing_ctx["additional_discount_var"],
            "force_logout": False,
        }
