import datetime
import math
from .models import *
from datetime import datetime
import traceback

PERIODS_PER_YEAR = {
    "monthly":12,
    "quarterly":4,
    "semi-annually":2,
    "annually":1
}

def calculate_max_tenor_years(project_config, tenor_years):
    
    tenor_years = float(tenor_years)
    max_tenor_years  = project_config.max_tenor_years
    
 
    return tenor_years, max_tenor_years


def calculate_gas_payments(policy, tenor_years, periods_per_year, contract_date, delivery_date, delivery_payment_index):

    num_pmts = policy.gas_num_pmts
    # print(f"num_pmts = {num_pmts}")
    scheduling = policy.scheduling
    main_delivery_payment_index = delivery_payment_index
    years_till_delivery = calculate_years_till_delivery(contract_date, delivery_date)
    tenor_years = float(tenor_years)
    # Select gas fee
    fees = GasPolicyFees.objects.filter(gas_policy=policy)
    fees = {str(fee.term_period): float(fee.fee_amount) for fee in fees}
    fees = {float(k):v for k, v in fees.items()}


    diffs = {abs(years_till_delivery-k):v for k, v in fees.items()}
    gas_fee = diffs[min(diffs.keys())]
    # print(f"gas_fee = {gas_fee}")


    try:
        offsets = GasPolicyOffsets.objects.filter(gas_policy=policy)
        offsets = {str(offset.term_period): float(offset.offset_value) for offset in offsets}
        offsets = {float(k):v for k, v in offsets.items()}
        diffs = {abs(years_till_delivery-k):v for k, v in offsets.items()}
        offset = diffs[min(diffs.keys())] * periods_per_year
        
        if delivery_payment_index - offset > 0:
            delivery_payment_index = delivery_payment_index - offset

    except:
        pass
    
    # print(f"offset = {offset}")
    # print(f"scheduling = {scheduling}")
    if years_till_delivery > tenor_years:
        n = delivery_payment_index
    else:
        n = int(tenor_years) * int(periods_per_year)

    gas_payments = ["",]*(n+1)
    # print(f"gas_payments = {gas_payments}")


    if scheduling == "at_delivery":
        gas_payments[int(main_delivery_payment_index) -1] = gas_fee

    elif scheduling == "before_delivery":
        try:
            gas_pmt = gas_fee / num_pmts 
        except:
            gas_pmt = gas_fee

        if main_delivery_payment_index != delivery_payment_index:
            for i in range(num_pmts):
                gas_payments[int(delivery_payment_index)+i - 1] = gas_pmt
        else:
            for i in range(num_pmts):
                gas_payments[int(delivery_payment_index)-i-1] = gas_pmt

    return gas_payments


# Calculate maintenance payments 
def calculate_maintenance_payments(policy, maintenance_fee, tenor_years, periods_per_year, contract_date, delivery_date, delivery_payment_index, currency_rate):

    num_pmts = policy.maintenance_num_pmts 
    # print(f"policy.maintenance_num_pmts = {policy.maintenance_num_pmts}")
    main_delivery_payment_index = delivery_payment_index
    tenor_years = float(tenor_years)

    years_till_delivery = calculate_years_till_delivery(contract_date, delivery_date)
    schedulings = MaintenancePolicyScheduling.objects.filter(maintenance_policy=policy)
    scheduling = {str(scheduling.term_period): str(scheduling.scheduling) for scheduling in schedulings}   
    scheduling = {float(k):v for k, v in scheduling.items()}

    diffs = {abs(years_till_delivery-k):v for k, v in scheduling.items()}
    scheduling = diffs[min(diffs.keys())]


    try:
        offsets = MaintenancePolicyOffsets.objects.filter(maintenance_policy=policy)
        offsets = {str(offset.term_period): float(offset.offset_value) for offset in offsets}
        offsets = {float(k):v for k, v in offsets.items()}
        diffs = {abs(years_till_delivery-k):v for k, v in offsets.items()}
        offset = diffs[min(diffs.keys())] * periods_per_year
    
        if delivery_payment_index - offset > 0:
            delivery_payment_index = delivery_payment_index - offset

    except:
            pass
    
    # print(f"tenor_years = {tenor_years}")
    if years_till_delivery > tenor_years:
        n = int(delivery_payment_index)
    else:
        n = int(tenor_years) * int(periods_per_year)
    
    maintenance_payments = ["",]*(n+1)

    if scheduling == "at_delivery":
        maintenance_payments[main_delivery_payment_index] = maintenance_fee
    elif scheduling == "before_delivery":
        # if delivery_payment_index-num_pmts < 0:
        #     maintenance_payments[delivery_payment_index] = maintenance_fee
        # else:
        currency_rate = float(currency_rate)
        try:
            maintenance_pmt = ((maintenance_fee  * currency_rate) / num_pmts)  
        except:
            maintenance_pmt = maintenance_fee


        if main_delivery_payment_index != delivery_payment_index:
            for i in range(num_pmts):
                maintenance_payments[int(delivery_payment_index)+i] = maintenance_pmt

        else:
            for i in range(num_pmts):
                maintenance_payments[delivery_payment_index+i-num_pmts] = maintenance_pmt

    return maintenance_payments



def excel_formula(Z6, E7, C11, J6, Z7, G7, Y7, *, eps=1e-12):
    def is_blank(x):
        return x is None or (isinstance(x, float) and math.isnan(x)) or x == ""

    if Z6 == 1:
        return 0.0

    if E7 == C11 * 4:
        return 1.0 - J6

    candidate1 = Z7 - J6     # cumulatives[i] - sum(pmt_percentages[0:i])
    
    # ADD THIS CONSTRAINT: candidate1 cannot be negative
    candidate1 = max(candidate1, 0.0)

    if G7 == 55555:
        denom = 1.0 - Z6     
        if abs(denom) < eps:
            raise ZeroDivisionError("Denominator (1 - Z6) is too close to zero.")
        candidate2 = (1.0 - J6) * Y7 / denom
    else:
        candidate2 = G7   # pmt_percentages[i]

    result = max(candidate1, candidate2)
    
    # ADD THIS CONSTRAINT: result cannot exceed remaining percentage
    remaining = 1.0 - J6
    result = min(result, remaining)
    
    return result


# -------------------------------------------------------------------------------------------------------------------------------- Apply constraints
# 


def apply_constraints(dp, pmt_percentages, tenor_years, periods_per_year, input_pmts, constraints, contract_date, delivery_date, scheme, special_offer = None):

    
    if dp == "": 
        dp = 0
    
    project = constraints.project_config.project

    exteded_payments = ProjectExtendedPayments.objects.filter(project = project, year = tenor_years, scheme = scheme).first()
        
    if special_offer: 
        exteded_payments = ProjectExtendedPaymentsSpecialOffer.objects.filter(project = project, year = tenor_years).first()
    
    if exteded_payments:
        var_dp = exteded_payments.dp1 + exteded_payments.dp2 
    else:
        var_dp = 0
    
    if float(dp) < float(var_dp):
        pmt_percentages[0] = float(var_dp)
    else:
        pmt_percentages[0] = float(dp)


    if "Sept." in delivery_date:
        delivery_date = delivery_date.replace("Sept.", "Sep.")

    try:
        delivery_date = datetime.strptime(delivery_date, "%b. %d, %Y") 
    except:
        delivery_date = datetime.strptime(delivery_date, "%B %d, %Y") 

    n = int(tenor_years) * int(periods_per_year)  

    tenor_years = int(tenor_years)
 
    if n == 1:
        remaining_percentage1 = 1 - pmt_percentages[0] 
    else:
        if n - len(input_pmts) != 0:
            remaining_percentage1 = (1- float(pmt_percentages[0])  - sum(list(input_pmts.values()))) / (n - len(list(input_pmts.values())))
        else:
            remaining_percentage1 = 0

    remaining_percentages = [remaining_percentage1]
    # print(f"remaining_percentage1 = {remaining_percentage1}")
    # print()
    for k, v in input_pmts.items():
        if k==0:
            continue
        pmt_percentages[k] = v

    
    pmt_percentages[0] = float(pmt_percentages[0]) 




    if exteded_payments:
        values = []
        cumulatives = []

        # Add DP1 and DP2
        values.append(exteded_payments.dp1 or 0)
        values.append(exteded_payments.dp2 or 0)
        cumulatives.append(exteded_payments.cumulative_dp1 or 0)
        cumulatives.append(exteded_payments.cumulative_dp2 or 0)

        # Add Installments and Cumulatives
        for i in range(1, 49):
            val = getattr(exteded_payments, f'installment_{i}', 0) or 0
            cum = getattr(exteded_payments, f'cumulative_{i}', 0) or 0
            values.append(val)
            cumulatives.append(cum)


    print(f"pmt_percentages before = {pmt_percentages}")
    if not special_offer:

        for i in range (1, (tenor_years*4) +1):
            pmt_percentages[i] = excel_formula(cumulatives[i],i,tenor_years, sum(pmt_percentages[0:i]), cumulatives[i+1], pmt_percentages[i], values[i+1])
            print()
    else:
        for i in range (0, (tenor_years*4) +1):
            pmt_percentages[i] = excel_formula(cumulatives[i],i,tenor_years, sum(pmt_percentages[0:i]), cumulatives[i+1], pmt_percentages[i], values[i+1])
            print()


 
    if scheme == "flat":
        pmt_percentages = [p if p!=55555 else remaining_percentage1 for p in pmt_percentages]

    else:
        for i in range (1, (tenor_years*4) +1): 
            if pmt_percentages[i] == 55555:

                pmt_percentages[i] = values[i+1] 
 
    try:
        years_till_delivery = calculate_years_till_delivery(contract_date, datetime.strptime(delivery_date, "%b. %d, %Y"))
    except:
        years_till_delivery = calculate_years_till_delivery(contract_date, delivery_date)
    for year in range(int(tenor_years)):
        if year+1 > years_till_delivery:
            break
    

    delivery_payment_index = math.floor(years_till_delivery * periods_per_year)

    print(f"pmt_percentages after = {pmt_percentages}")
    return pmt_percentages, delivery_payment_index



from copy import deepcopy

def adjust_pmts(pmt_percentages, values):
    adjusted = pmt_percentages[:]
    total = sum(adjusted)

    for i in range(len(adjusted)):
        if adjusted[i] > values[i]:
            diff = adjusted[i] - values[i]

            # distribute difference proportionally across the rest
            rest_sum = sum(adjusted[i+1:])
            if rest_sum > 0:
                factor = (rest_sum - diff) / rest_sum
                for j in range(i+1, len(adjusted)):
                    adjusted[j] *= factor

    # normalize to make sure sum = 1
    total = sum(adjusted)
    if abs(total - 1) > 1e-9:
        adjusted = [x / total for x in adjusted]

    return adjusted






import math

# --------------------------------------------------------------------------------------------------------------------------------
# Calculate increase/Decrease %
def calculate_percentage_change(
    base_npv,
    new_npv,
    max_discount,
    special_offer=0,
    real_discount=False,
    constant_discount=0,
    epsilon=1e-4  
):
    base_npv = float(base_npv)
    new_npv = float(new_npv)  
    print(f"constant_discount_2 = {constant_discount}") 

    # --- Constant discount logic ---
    if constant_discount != 0 and special_offer and constant_discount != None:
        percentage_change = -1 * constant_discount

    else:
        # --- Special offer with real discount ---
        if special_offer and real_discount is True:
            max_discount = 1 - base_npv

        max_discount = float(max_discount)
        percentage_change = 0

        print(f"new_npv = {new_npv}")
        print(f"base_npv = {base_npv}")

        if math.isclose(base_npv, new_npv, rel_tol=0, abs_tol=epsilon):
            percentage_change = 0
            print("≈ Equal → percentage_change forced to 0")

        elif base_npv >= new_npv:
            percentage_change = (base_npv / new_npv) - 1
            print("yes")
        else:
            percentage_change = ((base_npv / new_npv) - 1) * (max_discount / (1 - base_npv))
            print("no")

        print(f"percentage_change = {percentage_change}")

    return percentage_change


# --------------------------------------------------------------------------------------------------------------------------------
# Calculate price with interest
def calculate_price_with_interest(
    base_npv,
    new_npv,
    max_discount,
    base_price,
    additional_disc=0,
    special_offer=0,
    real_discount=False,
    constant_discount=0,
    epsilon=1e-4   # tolerance for tiny differences
):
    base_npv   = float(base_npv)
    new_npv    = float(new_npv)     # ✅ no rounding here
    max_discount = float(max_discount)
    base_price = float(base_price)

    print(f"special_offer = {special_offer}")
    print(f"constant_discount = {constant_discount}")

    # --- If constant discount applies in special offer mode, use it directly ---
    if constant_discount != 0 and special_offer and constant_discount != None:
        percentage_change = -1 * constant_discount

    else:
        # --- If it's a special offer with a "real discount", cap by (1 - base_npv) ---
        if special_offer and real_discount is True:
            max_discount = 1 - base_npv

        print(f"max_discount = {max_discount}")

        # Default
        percentage_change = 0.0

        # ✅ Treat nearly equal NPVs as equal → no change
        if math.isclose(base_npv, new_npv, rel_tol=0.0, abs_tol=epsilon):
            percentage_change = 0.0
            print("≈ Equal → percentage_change forced to 0")

        elif base_npv >= new_npv:
            # Guard against division by ~0
            denom = new_npv if not math.isclose(new_npv, 0.0, rel_tol=0.0, abs_tol=epsilon) else epsilon
            print(f"base_npv={base_npv}")
            print(f"new_npv={new_npv}")
            percentage_change = (base_npv / denom) - 1.0
        else:
            # Guard against division by ~0
            denom = new_npv if not math.isclose(new_npv, 0.0, rel_tol=0.0, abs_tol=epsilon) else epsilon
            print(f"base_npv={base_npv}")
            print(f"new_npv={new_npv}")
            # Note: keep the same formula you had, just without rounding new_npv
            percentage_change = ((base_npv / denom) - 1.0) * (max_discount / (1.0 - base_npv))

    print(f"percentage_change = {percentage_change}")

    # ---- Apply additional discount (if any) and round up to nearest 1000 ----
    if not additional_disc:  # covers 0, None, '', etc.
        result = (1.0 + percentage_change) * base_price
        rounded_result = math.ceil(result / 1000.0) * 1000.0
        print(f"rounded_result = {rounded_result}")
        return rounded_result
    else:
        # additional_disc is percentage (e.g., 5 → 5%)
        result = (1.0 + (percentage_change - (float(additional_disc) / 100.0))) * base_price
        rounded_result = math.ceil(result / 1000.0) * 1000.0
        print(f"rounded_result = {rounded_result}")
        return rounded_result


 






# -------------------------------------------------------------------------------------------------------------------------------- Calculate period rate
def calculate_period_rate(interest_rate, periods_per_year):
    return (1 + float(interest_rate)) ** (1 / periods_per_year) - 1


# -------------------------------------------------------------------------------------------------------------------------------- Calculate Years till delivery
from datetime import datetime

def calculate_years_till_delivery(contract_date, delivery_date):
    # Ensure contract_date is a datetime object
    if isinstance(contract_date, str):
        contract_date = datetime.strptime(contract_date, "%Y-%m-%d")  # Adjust format if needed

    # Convert delivery_date from string to datetime object
    if isinstance(delivery_date, str):
        try:
            # Try parsing the abbreviated month format first (e.g., "Feb. 28, 2027")
            delivery_date = datetime.strptime(delivery_date, "%b. %d, %Y")
        except ValueError:
            try:
                # If that fails, try parsing the full month name format (e.g., "June 30, 2027")
                delivery_date = datetime.strptime(delivery_date, "%B %d, %Y")
            except ValueError:
                # Raise an error if neither format matches
                raise ValueError(f"Invalid delivery_date format: {delivery_date}. Expected formats: 'Mon. DD, YYYY' or 'Month DD, YYYY'.")

    # Calculate the difference in years
    n_years = (delivery_date - contract_date).days / 365
    return n_years