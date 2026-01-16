# import datetime
# import math
# from .models import *
# from datetime import datetime
# import traceback
# import re

# PERIODS_PER_YEAR = {
#     "monthly":12,
#     "quarterly":4,
#     "semi-annually":2,
#     "annually":1
# }

# def calculate_max_tenor_years(project_config, tenor_years, base_tenor_years, first_year_min, annual_min):
    
#     try:
#         max_tenor_years = int((1-float(first_year_min))/float(annual_min)) + 1 ## Force maximum tenor years based on project constraints
#         tenor_years = float(tenor_years)
#         base_tenor_years = float(base_tenor_years)
#         if tenor_years > max_tenor_years:
#             tenor_years = max_tenor_years
#         elif tenor_years == 0:
#             tenor_years = base_tenor_years
#         # print("yes")

#     except:
#         max_tenor_years  = project_config.max_tenor_years # Edittable
#         # tenor_years = base_tenor_years
#         # print("No")
#         traceback.print_exc()

    

#     return tenor_years, max_tenor_years


# def calculate_gas_payments(policy, tenor_years, periods_per_year, contract_date, delivery_date, delivery_payment_index):

#     num_pmts = policy.gas_num_pmts
#     # print(f"num_pmts = {num_pmts}")
#     scheduling = policy.scheduling
#     main_delivery_payment_index = delivery_payment_index
#     years_till_delivery = calculate_years_till_delivery(contract_date, delivery_date)
#     tenor_years = float(tenor_years)
#     # Select gas fee
#     fees = GasPolicyFees.objects.filter(gas_policy=policy)
#     fees = {str(fee.term_period): float(fee.fee_amount) for fee in fees}
#     fees = {float(k):v for k, v in fees.items()}


#     diffs = {abs(years_till_delivery-k):v for k, v in fees.items()}
#     gas_fee = diffs[min(diffs.keys())]
#     # print(f"gas_fee = {gas_fee}")


#     try:
#         offsets = GasPolicyOffsets.objects.filter(gas_policy=policy)
#         offsets = {str(offset.term_period): float(offset.offset_value) for offset in offsets}
#         offsets = {float(k):v for k, v in offsets.items()}
#         diffs = {abs(years_till_delivery-k):v for k, v in offsets.items()}
#         offset = diffs[min(diffs.keys())] * periods_per_year
        
#         if delivery_payment_index - offset > 0:
#             delivery_payment_index = delivery_payment_index - offset

#     except:
#         pass
    
#     # print(f"offset = {offset}")
#     # print(f"scheduling = {scheduling}")
#     if years_till_delivery > tenor_years:
#         n = delivery_payment_index
#     else:
#         n = int(tenor_years) * int(periods_per_year)

#     gas_payments = ["",]*(n+1)
#     # print(f"gas_payments = {gas_payments}")


#     if scheduling == "at_delivery":
#         gas_payments[int(main_delivery_payment_index) -1] = gas_fee

#     elif scheduling == "before_delivery":
#         try:
#             gas_pmt = gas_fee / num_pmts 
#         except:
#             gas_pmt = gas_fee

#         if main_delivery_payment_index != delivery_payment_index:
#             for i in range(num_pmts):
#                 gas_payments[int(delivery_payment_index)+i - 1] = gas_pmt
#         else:
#             for i in range(num_pmts):
#                 gas_payments[int(delivery_payment_index)-i-1] = gas_pmt

#     return gas_payments


# # Calculate maintenance payments 
# def calculate_maintenance_payments(policy, maintenance_fee, tenor_years, periods_per_year, contract_date, delivery_date, delivery_payment_index, currency_rate):

#     num_pmts = policy.maintenance_num_pmts 
#     # print(f"policy.maintenance_num_pmts = {policy.maintenance_num_pmts}")
#     main_delivery_payment_index = delivery_payment_index
#     tenor_years = float(tenor_years)

#     years_till_delivery = calculate_years_till_delivery(contract_date, delivery_date)
#     schedulings = MaintenancePolicyScheduling.objects.filter(maintenance_policy=policy)
#     scheduling = {str(scheduling.term_period): str(scheduling.scheduling) for scheduling in schedulings}   
#     scheduling = {float(k):v for k, v in scheduling.items()}

#     diffs = {abs(years_till_delivery-k):v for k, v in scheduling.items()}
#     scheduling = diffs[min(diffs.keys())]


#     try:
#         offsets = MaintenancePolicyOffsets.objects.filter(maintenance_policy=policy)
#         offsets = {str(offset.term_period): float(offset.offset_value) for offset in offsets}
#         offsets = {float(k):v for k, v in offsets.items()}
#         diffs = {abs(years_till_delivery-k):v for k, v in offsets.items()}
#         offset = diffs[min(diffs.keys())] * periods_per_year
    
#         if delivery_payment_index - offset > 0:
#             delivery_payment_index = delivery_payment_index - offset

#     except:
#             pass
    
#     # print(f"tenor_years = {tenor_years}")
#     if years_till_delivery > tenor_years:
#         n = int(delivery_payment_index)
#     else:
#         n = int(tenor_years) * int(periods_per_year)
    
#     maintenance_payments = ["",]*(n+1)

#     if scheduling == "at_delivery":
#         maintenance_payments[main_delivery_payment_index] = maintenance_fee
#     elif scheduling == "before_delivery":
#         # if delivery_payment_index-num_pmts < 0:
#         #     maintenance_payments[delivery_payment_index] = maintenance_fee
#         # else:
#         currency_rate = float(currency_rate)
#         try:
#             maintenance_pmt = ((maintenance_fee  * currency_rate) / num_pmts)  
#         except:
#             maintenance_pmt = maintenance_fee


#         if main_delivery_payment_index != delivery_payment_index:
#             for i in range(num_pmts):
#                 maintenance_payments[int(delivery_payment_index)+i] = maintenance_pmt

#         else:
#             for i in range(num_pmts):
#                 maintenance_payments[delivery_payment_index+i-num_pmts] = maintenance_pmt

#     return maintenance_payments


# # -------------------------------------------------------------------------------------------------------------------------------- Apply constraints
# def apply_constraints(dp, pmt_percentages, tenor_years, periods_per_year, input_pmts, constraints, contract_date, delivery_date, scheme, special_offer):

#     if dp == "":
#         dp = 0
    
#     project = constraints.project_config.project

#     print(f"project = {project}")
#     print(f"tenor_years = {tenor_years}")
#     print(f"scheme = {scheme}")
#     is_special_offer = False
#     # try:
#     #     exteded_payments = ProjectExtendedPaymentsSpecialOffer.objects.filter(project = project, year = tenor_years).first() 
#     #     is_special_offer = True
#     # except:
#     #     pass

#     match = re.match(r"Special Offer (\d+) years? for (.+)", special_offer)
#     if match:
#         year = int(match.group(1))              # 10
#         project_name = match.group(2).strip()   # "40 Square"
#         # Fetch the actual Project object
#         project_obj = Project.objects.filter(name__iexact=project_name).first()
#         if project_obj:
#             exteded_payments = ProjectExtendedPaymentsSpecialOffer.objects.filter(
#                 project=project_obj, year=year
#             ).first()
#             is_special_offer = True
            
            
#     if is_special_offer == False:
#         exteded_payments = ProjectExtendedPayments.objects.filter(project = project, year = tenor_years, scheme = scheme).first()
#         standard_payments = ProjectStanderdPayments.objects.filter(project = project).first()

    
 
#     # ----------------------------------------------------------------- Minimum Down payment
#     if float(dp) < float(constraints.dp_min):
#         pmt_percentages[0] = float(constraints.dp_min)
#     else:
#         pmt_percentages[0] = float(dp)

#     try:
#         if "." in delivery_date.split()[0]:
#             delivery_date = delivery_date.replace(".", "")

#         delivery_date = parse_human_date(delivery_date)

#     except:
#         # Correct format for "June 30, 2027"
#         delivery_date = datetime.strptime(delivery_date, "%B %d, %Y") 

#     # print(f"input_pmts = {input_pmts}")
    
#     # print(f"pmt_percentages before 1 = {pmt_percentages}")
#     # print() 
#     #^ Calculate the equal remaining payments after deducting the down payment, and custom payments

#     n = int(tenor_years) * int(periods_per_year)  

#     tenor_years = int(tenor_years)
 
#     if n == 1:
#         remaining_percentage1 = 1 - pmt_percentages[0] 
#     else:
#         if n - len(input_pmts) != 0:
#             remaining_percentage1 = (1- float(pmt_percentages[0])  - sum(list(input_pmts.values()))) / (n - len(list(input_pmts.values())))
#         else:
#             remaining_percentage1 = 0

#     remaining_percentages = [remaining_percentage1]
#     # print(f"remaining_percentage1 = {remaining_percentage1}")
#     # print()
#     for k, v in input_pmts.items():
#         if k==0:
#             continue
#         pmt_percentages[k] = v

#     pmt_percentages[0] = float(pmt_percentages[0])

#     pmt_percentages = [p if p!=0 else remaining_percentage1 for p in pmt_percentages]

#     # print(f"pmt_percentages = {pmt_percentages}")
#     # if 1 in input_pmts.keys(): 
#     #     del input_pmts[1]

#     # print(f"pmt_percentages before 2 = {pmt_percentages}")
#     # print()
#     # print()
#     # print()
#     # print()
#     # ----------------------------------------------------------------- Minimum Down payment Plus First Payment



#     #^ Handle minimum down payment plus first payment constraint
#     try:  #  pmt_percentages = [10, 2.5,0,0,0,10]    
#         if float(pmt_percentages[0]) + float(input_pmts[1]) <= float(constraints.dp_plus_first_pmt):
#             pmt_percentages[1] = float(constraints.dp_plus_first_pmt) - pmt_percentages[0]  # [,]
#             # print("yes 1")
#             # print()

#         else:
#             pmt_percentages[1] = float(input_pmts[1])
#             # print("no 1")
#             # print()

#         # print(f"pmt_percentages try = {pmt_percentages}")
#         # print()

#     except:
       
#         if float(pmt_percentages[0]) + float(pmt_percentages[1]) <= float(constraints.dp_plus_first_pmt):
#             pmt_percentages[1] = float(constraints.dp_plus_first_pmt) - pmt_percentages[0] 

#         #     print("yes 2")
#         #     print()
        
#         # print(f"pmt_percentages catch = {pmt_percentages}")
#         # print()


#     if 1 in input_pmts.keys():
#         del input_pmts[1]

#     # print(f"input_pmts = {input_pmts}")
#     # print()


#     #^ Calculate the equal remaining payments after deducting the down payment, first payment, and custom payments
#     if n == 1:
#         remaining_percentage2 = 1 - pmt_percentages[0] - pmt_percentages[1]
        
#         # print(f"remaining_percentage2 yes = {remaining_percentage2}")
#         # print()
#     else:
#         if n - 1 - len(input_pmts) != 0:
#             remaining_percentage2 = (1- pmt_percentages[0] - pmt_percentages[1] -  sum(list(input_pmts.values()))) / (n - 1 - len(list(input_pmts.values())))
#             # print(f"remaining_percentage2 yes 2 = {remaining_percentage2}")
#             # print()
            
#         else:
#             remaining_percentage2 = 0
#             # print(f"remaining_percentage2 no = {remaining_percentage2}")
#             # print()

    
#     remaining_percentages.append(remaining_percentage2)  
    
#     for k, v in input_pmts.items():
#         if k==0 or k==1:
#             continue
#         pmt_percentages[k] = v


#     # print(f"pmt_percentages before updating  = {pmt_percentages}")
#     # print(f"remaining_percentage1 = {remaining_percentage1}") 
#     # pmt_percentages = [p if p!=remaining_percentage1 else remaining_percentage2 for p in pmt_percentages]

#     temp_counter = 0
#     for p in pmt_percentages:
#         if temp_counter == 0:
#             temp_counter += 1
#             continue

#         if p != remaining_percentage1:
#             temp_counter += 1
#             continue
#         else:
#             pmt_percentages[temp_counter] = remaining_percentage2
#             temp_counter += 1



#     # print()
#     # print()
#     # print()
#     # print() 
#     # print(f"pmt_percentages before 3 = {pmt_percentages}")
#     #^ Handle minimum down payment plus first plus second payment constraint
#     try:  #  pmt_percentages = [10, 2.5,0,0,0,10]    
#         if float(pmt_percentages[0]) + float(input_pmts[1]) + float(input_pmts[2]) <= float(constraints.dp_plus_first_plus_second_pmt):
#             pmt_percentages[2] = float(constraints.dp_plus_first_plus_second_pmt) - pmt_percentages[0] - pmt_percentages[1]    # [,]
#         else:
#             pmt_percentages[2] = float(input_pmts[2])

#     except:
       
#         if float(pmt_percentages[0]) + float(pmt_percentages[1])  + float(pmt_percentages[2]) <= float(constraints.dp_plus_first_plus_second_pmt):
#             pmt_percentages[2] = float(constraints.dp_plus_first_plus_second_pmt) - pmt_percentages[0] - pmt_percentages[1] 
        

    
#     # if float(pmt_percentages[0]) + float(temp) < float(constraints.dp_plus_first_pmt):
#     #     pmt_percentages[1] = float(constraints.dp_plus_first_pmt) - pmt_percentages[0]

#     if 2 in input_pmts.keys():
#         del input_pmts[2]


#     #^ Calculate the equal remaining payments after deducting the down payment, first payment, second payment, and custom payments
#     if n == 1:
#         remaining_percentage7 = 1 - pmt_percentages[0] - pmt_percentages[1]  - pmt_percentages[2]
        
#     else:
#         if n - 2 - len(input_pmts) != 0:
#             remaining_percentage7 = (1- pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] -  sum(list(input_pmts.values()))) / (n - 2 - len(list(input_pmts.values())))
#         else:
#             remaining_percentage7 = 0
    
#     remaining_percentages.append(remaining_percentage7)  
    
#     for k, v in input_pmts.items():
#         if k==0 or k==1 or k==2:
#             continue
#         pmt_percentages[k] = v

#     pmt_percentages = [p if p!=remaining_percentage2 else remaining_percentage7 for p in pmt_percentages]

#     # print(f"pmt_percentages before 4 = {pmt_percentages}")
#      #^ Handle minimum down payment plus first plus second payment constraint
#     try:  #  pmt_percentages = [10, 2.5,0,0,0,10]    
#         if float(pmt_percentages[0]) + float(input_pmts[1]) + float(input_pmts[2]) + float(input_pmts[3]) <= float(constraints.dp_plus_first_plus_second_plus_third_pmt):
#             pmt_percentages[3] = float(constraints.dp_plus_first_plus_second_plus_third_pmt) - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2]   # [,]
#         else:
#             pmt_percentages[2] = float(input_pmts[2])

#     except:
       
#         if float(pmt_percentages[0]) + float(pmt_percentages[1])  + float(pmt_percentages[2]) + float(pmt_percentages[3]) <= float(constraints.dp_plus_first_plus_second_plus_third_pmt):
#             pmt_percentages[3] = float(constraints.dp_plus_first_plus_second_plus_third_pmt) - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2]
        

    
#     # if float(pmt_percentages[0]) + float(temp) < float(constraints.dp_plus_first_pmt):
#     #     pmt_percentages[1] = float(constraints.dp_plus_first_pmt) - pmt_percentages[0]

#     if 3 in input_pmts.keys():
#         del input_pmts[3] 


#     #^ Calculate the equal remaining payments after deducting the down payment, first payment, and custom payments
#     if n == 1:
#         remaining_percentage8 = 1 - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3]
        
#     else:
#         if n - 3 - len(input_pmts) != 0:
#             remaining_percentage8 = (1- pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3] -  sum(list(input_pmts.values()))) / (n - 3 - len(list(input_pmts.values())))
#         else:
#             remaining_percentage8 = 0
    
#     remaining_percentages.append(remaining_percentage8)  
    
#     for k, v in input_pmts.items():
#         if k==0 or k==1 or k==2 or k==3:
#             continue
#         pmt_percentages[k] = v

#     pmt_percentages = [p if p!=remaining_percentage7 else remaining_percentage8 for p in pmt_percentages]


 
#     # print(f"pmt_percentages before 5 = {pmt_percentages}")
#      #^ Handle minimum down payment plus first plus second payment constraint
#     try:  #  pmt_percentages = [10, 2.5,0,0,0,10]    
#         if float(pmt_percentages[0]) + float(input_pmts[1]) + float(input_pmts[2]) + float(input_pmts[3]) + float(input_pmts[4]) <= float(constraints.dp_plus_first_plus_second_plus_third_plus_forth_pmt):
#             pmt_percentages[4] = float(constraints.dp_plus_first_plus_second_plus_third_plus_forth_pmt) - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3]   # [,]
#         else:
#             pmt_percentages[3] = float(input_pmts[2])

#     except:
       
#         if float(pmt_percentages[0]) + float(pmt_percentages[1])  + float(pmt_percentages[2]) + float(pmt_percentages[3]) + float(pmt_percentages[4])  <= float(constraints.dp_plus_first_plus_second_plus_third_plus_forth_pmt):
#             pmt_percentages[4] = float(constraints.dp_plus_first_plus_second_plus_third_plus_forth_pmt) - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3] 
         

    
#     # if float(pmt_percentages[0]) + float(temp) < float(constraints.dp_plus_first_pmt):
#     #     pmt_percentages[1] = float(constraints.dp_plus_first_pmt) - pmt_percentages[0]

#     if 4 in input_pmts.keys():
#         del input_pmts[4] 


#     #^ Calculate the equal remaining payments after deducting the down payment, first payment, and custom payments
#     if n == 1:
#         remaining_percentage10 = 1 - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3] - pmt_percentages[4]
        
#     else:
#         if n - 4 - len(input_pmts) != 0:
#             remaining_percentage10 = (1- pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3] - pmt_percentages[4] -  sum(list(input_pmts.values()))) / (n - 4 - len(list(input_pmts.values())))
#         else:
#             remaining_percentage10 = 0
    
#     remaining_percentages.append(remaining_percentage10)  
    
#     for k, v in input_pmts.items():
#         if k==0 or k==1 or k==2 or k==3 or k==4:
#             continue
#         pmt_percentages[k] = v

#     pmt_percentages = [p if p!=remaining_percentage8 else remaining_percentage10 for p in pmt_percentages]


#     # # ----------------------------------------------------------------- First Year Payment
#     # first_year_payments = pmt_percentages[:periods_per_year+1]

    
#     # if sum(first_year_payments) < float(constraints.first_year_min):
#     #     pmt_percentages[periods_per_year] = float(constraints.first_year_min) - sum(first_year_payments[:-1])

    
#     # if sum(pmt_percentages) > 1:

#     #     sum_after_first_year = sum(pmt_percentages[periods_per_year+1:])
#     #     total_custom_payments_after_first_year = float(0)
#     #     num_custom_payments_after_first_year = 0

#     #     for k in input_pmts.keys():
#     #         if k <= periods_per_year:
#     #             continue
#     #         total_custom_payments_after_first_year += pmt_percentages[k]
#     #         num_custom_payments_after_first_year += 1

#     #     excess = sum(pmt_percentages) - 1
        
#     #     remaining_percentage3 = (sum_after_first_year-total_custom_payments_after_first_year-excess) / (len(pmt_percentages[periods_per_year+1:]) - num_custom_payments_after_first_year)
#     #     remaining_percentages.append(remaining_percentage3)

#     #     for i, pmt in enumerate(pmt_percentages[periods_per_year+1:]):
#     #         if pmt in remaining_percentages:
#     #             pmt_percentages[periods_per_year+1+i] = remaining_percentage3

#     # # ----------------------------------------------------------------- Cumulative Minimum Constraint - Before CTD

#     try:
#         years_till_delivery = calculate_years_till_delivery(contract_date, datetime.strptime(delivery_date, "%b. %d, %Y"))
#     except:
#         years_till_delivery = calculate_years_till_delivery(contract_date, delivery_date)
#     for year in range(int(tenor_years)):
#         if year+1 > years_till_delivery:
#             break
    
#         # cummulative_payments = pmt_percentages[:((year+1)*periods_per_year)+1]
        
#         # if sum(cummulative_payments) < (year * float(constraints.annual_min)) + float(constraints.first_year_min):
#         #     pmt_percentages[(year+1)*periods_per_year] = (year * float(constraints.annual_min)) + float(constraints.first_year_min) - sum(cummulative_payments[:-1])

#     # ----------------------------------------------------------------- Cash Till Delivery

#     ctd_entries = CTD.objects.filter(project_constraints=constraints)
#     ctd_mins = {str(ctd.term_period): float(ctd.npv_value) for ctd in ctd_entries}
#     ctd_mins = {float(k):v for k, v in ctd_mins.items()}
#     diffs = {abs(years_till_delivery-k):v for k, v in ctd_mins.items()}

#     ctd_exists = False
#     try:
#         ctd = diffs[min(diffs.keys())]
#         ctd_exists = True
#     except:
#         ctd = 0

#     # print(f"ctd = {ctd}") 

#     delivery_payment_index = math.floor(years_till_delivery * periods_per_year)
    
#     payments_till_delivery = pmt_percentages[:delivery_payment_index+1]

#     if ctd_exists == True:
#         if sum(payments_till_delivery) < ctd:
#             if delivery_payment_index >= len(pmt_percentages):
#                 pmt_percentages[-1] = ctd - sum(payments_till_delivery[:-1])
#             else:
#                 pmt_percentages[delivery_payment_index] = ctd - sum(payments_till_delivery[:-1])
        

#         if sum(pmt_percentages) > 1:
#             sum_after_delivery = sum(pmt_percentages[4:])
#             total_custom_payments_after_delivery = float(0)
#             num_custom_payments_after_delivery = 0

#             for k in input_pmts.keys():
#                 if k <= 4-1:
#                     continue
#                 total_custom_payments_after_delivery += pmt_percentages[k]
#                 num_custom_payments_after_delivery += 1

#             excess = sum(pmt_percentages) - 1


#             remaining_percentage4 = (sum_after_delivery-total_custom_payments_after_delivery-excess) / (len(pmt_percentages[4:]) - num_custom_payments_after_delivery)
#             remaining_percentages.append(remaining_percentage4)

#             for i, pmt in enumerate(pmt_percentages[4:]):
#                 if pmt in remaining_percentages:
#                     pmt_percentages[4+i] = remaining_percentage4



#     # ----------------------------------------------------------------- Cumulative Minimum Constraint - After CTD
#     # print(f"pmt_percentages = {pmt_percentages}")
#     # for year in range(tenor_years):
#     #     if year+1 < years_till_delivery:
#     #         continue
        
#     #     start_index = year * periods_per_year # [4:8]
#     #     end_index = (year + 1) * periods_per_year
#     #     cummulative_payments = pmt_percentages[start_index +1:end_index+1]
#     #     # print(f"cummulative_payments = {cummulative_payments}")
#     #     # break 
#     #     print(f"sum(cummulative_payments)  = {sum(cummulative_payments)}")
#     #     print(f"year * constraints.annual_min  = {year * constraints.annual_min}")
#     #     if sum(cummulative_payments) < (constraints.annual_min) + constraints.first_year_min:
#     #         pmt_percentages[(year+1)*periods_per_year] = (year * float(constraints.annual_min)) + float(constraints.first_year_min) - sum(cummulative_payments[:-1])

#     #         if sum(pmt_percentages) > 1:


#     #             adjustment_index = ((year+1)*periods_per_year)
#     #             sum_after_adjustment = sum(pmt_percentages[adjustment_index+1:])
#     #             total_custom_payments_after_adjustment = 0
#     #             num_custom_payments_after_adjustment = 0
#     #             print(f"adjustment_index = {adjustment_index}")
#     #             for k in input_pmts.keys():
#     #                 if k <= adjustment_index:
#     #                     continue
#     #                 total_custom_payments_after_adjustment += pmt_percentages[k]
#     #                 num_custom_payments_after_adjustment += 1
                
#     #             excess = sum(pmt_percentages) - 1
                 
#     #             remaining_percentage_after_adjustment = (sum_after_adjustment-total_custom_payments_after_adjustment-excess) / (len(pmt_percentages[adjustment_index+1:]) - num_custom_payments_after_adjustment)
                
#     #             remaining_percentages.append(remaining_percentage_after_adjustment)
 
#     #             for i, pmt in enumerate(pmt_percentages[adjustment_index+1:]):
#     #                 if pmt in remaining_percentages:
#     #                     pmt_percentages[adjustment_index+1+i] = remaining_percentage_after_adjustment

    
#     # # ✅ Output

#     # if sum(pmt_percentages) > 1:
#     #     adjustment_index = ((year+1)*periods_per_year)
#     #     sum_after_adjustment = sum(pmt_percentages[adjustment_index+1:])
#     #     total_custom_payments_after_adjustment = 0
#     #     num_custom_payments_after_adjustment = 0

#     #     for k in input_pmts.keys():
#     #         if k <= adjustment_index:
#     #             continue
#     #         total_custom_payments_after_adjustment += pmt_percentages[k]
#     #         num_custom_payments_after_adjustment += 1
        
#     #     excess = sum(pmt_percentages) - 1
#     #     remaining_percentage_after_adjustment = (sum_after_adjustment-total_custom_payments_after_adjustment-excess) / (len(pmt_percentages[adjustment_index+1:]) - num_custom_payments_after_adjustment)
#     #     remaining_percentages.append(remaining_percentage_after_adjustment)

#     #     for i, pmt in enumerate(pmt_percentages[adjustment_index+1:]):
#     #         if pmt in remaining_percentages:
#     #             pmt_percentages[adjustment_index+1+i] = remaining_percentage_after_adjustment


#     if tenor_years in [7, 9, 10]:
        
#         if exteded_payments:
#             values = []
#             cumulatives = []
#             print(f"exteded_payments = {exteded_payments}") 
#             # Add DP1 and DP2 
#             values.append(exteded_payments.dp1 or 0)
#             values.append(exteded_payments.dp2 or 0)
#             cumulatives.append(exteded_payments.cumulative_dp1 or 0)
#             cumulatives.append(exteded_payments.cumulative_dp2 or 0)

#             # Add Installments and Cumulatives
#             for i in range(1, 49):
#                 val = getattr(exteded_payments, f'installment_{i}', 0) or 0
#                 cum = getattr(exteded_payments, f'cumulative_{i}', 0) or 0
#                 values.append(val)
#                 cumulatives.append(cum)


#         index = 0
#         index_2 = 5  
#         for i in pmt_percentages:
#             if index < 4:
#                 index += 1
#                 continue

#             # Only process while we haven't reached the full length (40)
#             if (tenor_years * 4) != len(pmt_percentages[:index]):
#                 cumm = sum(pmt_percentages[:index ]) 
#                 target  = cumulatives[index_2] - cumm 

#                 if i <= target:
#                     pmt_percentages[index] = target 
                
#             index += 1
#             index_2 += 1

#         # print(f"pmt_percentages after modification  = {pmt_percentages}")

#         if sum(pmt_percentages) >= 1:

#             sum_after_delivery_2 = sum(pmt_percentages[5:])
#             total_custom_payments_after_delivery_2 = float(0)
#             num_custom_payments_after_delivery_2 = 0

#             for k in input_pmts.keys():
#                 if k <= 5-1:
#                     continue
#                 total_custom_payments_after_delivery_2 += pmt_percentages[k]
#                 num_custom_payments_after_delivery_2 += 1

#             excess_2 = sum(pmt_percentages) - 1

#             remaining_percentage11 = (sum_after_delivery_2-total_custom_payments_after_delivery_2-excess_2) / (len(pmt_percentages[5:]) - num_custom_payments_after_delivery_2)

#             remaining_percentages.append(remaining_percentage11)

#             for i, pmt in enumerate(pmt_percentages[5:]):
#                 if pmt in remaining_percentages:
#                     pmt_percentages[5+i] = remaining_percentage11 

 

#     elif tenor_years in [1, 2, 3, 4, 5, 6, 8, 11, 12]:
     
#         index = 0 
#         for i in pmt_percentages:
#             if index < 4:
#                 index += 1
#                 continue

#             # Only process while we haven't reached the full length (40)
#             if 40 != len(pmt_percentages[:index]):
#                 cumm = sum(pmt_percentages[:index]) 
 
#                 target = 0.1 + 0.1 + (0.8 / 36) * (index - 4)

#                 if i <= target - cumm:
#                     pmt_percentages[index] = target - cumm

#             index += 1

#         if sum(pmt_percentages) > 1:
#             sum_after_delivery = sum(pmt_percentages[5:])
#             total_custom_payments_after_delivery = float(0)
#             num_custom_payments_after_delivery = 0

#             for k in input_pmts.keys():
#                 if k <= 5-1:
#                     continue
#                 total_custom_payments_after_delivery += pmt_percentages[k]
#                 num_custom_payments_after_delivery += 1

#             excess = sum(pmt_percentages) - 1

    
#             remaining_percentage4 = (sum_after_delivery-total_custom_payments_after_delivery-excess) / (len(pmt_percentages[5:]) - num_custom_payments_after_delivery)
#             remaining_percentages.append(remaining_percentage4)

#             for i, pmt in enumerate(pmt_percentages[5:]):
#                 if pmt in remaining_percentages:
#                     pmt_percentages[5+i] = remaining_percentage4

        
#     if sum(pmt_percentages) < 1:
#         pmt_percentages[-1] = 1 - sum(pmt_percentages[:-1])

#     return pmt_percentages, delivery_payment_index


# # -------------------------------------------------------------------------------------------------------------------------------- Calculate increase/Decrease %
# def calculate_percentage_change(base_npv, new_npv, max_discount):
#     base_npv = float(base_npv)
#     new_npv = round(float(new_npv), 4)
#     max_discount = float(max_discount)
#     percentage_change = 0
#     print(f"new_npv after rounding = {new_npv}")
#     print(f"base_npv after  = {base_npv}")
#     if base_npv >= new_npv:
#         percentage_change = (base_npv / new_npv) - 1
#         print("yes")
#     else:
#         percentage_change = ((base_npv / new_npv) - 1) * (max_discount / (1 - base_npv))
#         print("no")
 
#     print(f"percentage_change = {percentage_change}")
#     return percentage_change


# # -------------------------------------------------------------------------------------------------------------------------------- Calculate price with interest
# def calculate_price_with_interest(base_npv, new_npv, max_discount, base_price):

#     base_npv = float(base_npv)
#     new_npv = float(new_npv)
#     max_discount = float(max_discount)
#     base_price = float(base_price)
#     new_npv = round(new_npv, 4 )


#     percentage_change = 0

#     if base_npv >= new_npv:
#         print(f"base_npv={base_npv}")
#         print(f"new_npv={new_npv}")
#         percentage_change = (base_npv / new_npv) - 1
#     else:
#         print(f"base_npv={base_npv}")
#         print(f"new_npv={new_npv}") 
#         new_npv = round(new_npv, 5)

#         percentage_change = ((base_npv / new_npv) - 1) * (max_discount / (1 - base_npv))

    
#     print(f"percentage_change = {percentage_change}")
#     print(f"(1 + percentage_change) * base_price) = {(1 + percentage_change) * base_price}") 
    
#     return (1 + percentage_change) * base_price


# # -------------------------------------------------------------------------------------------------------------------------------- Calculate period rate
# def calculate_period_rate(interest_rate, periods_per_year):
#     return (1 + float(interest_rate)) ** (1 / periods_per_year) - 1


# # -------------------------------------------------------------------------------------------------------------------------------- Calculate Years till delivery
# from datetime import datetime


# from datetime import datetime, date

# def parse_human_date(value):
#     """
#     Robust date parser (English months) that accepts:
#       - 'September 30, 2028', 'Sep 30, 2028', 'Sept 30, 2028', 'Sep. 30 2028', etc.
#       - '2028-09-30', '30/09/2028', '30-09-2028', '09/30/2028'
#     Returns a datetime (00:00) for date-only inputs, passes through datetime/date unchanged.
#     Raises ValueError on failure.
#     """
#     if isinstance(value, datetime):
#         return value
#     if isinstance(value, date):
#         return datetime(value.year, value.month, value.day)

#     s = str(value).strip()
#     if not s:
#         raise ValueError("Empty date string")

#     # 1) Try common numeric formats first (fast path)
#     numeric_formats = (
#         "%Y-%m-%d",  # 2028-09-30
#         "%Y/%m/%d",  # 2028/09/30
#         "%d/%m/%Y",  # 30/09/2028
#         "%d-%m-%Y",  # 30-09-2028
#         "%m/%d/%Y",  # 09/30/2028
#         "%m-%d-%Y",  # 09-30-2028
#     )
#     for fmt in numeric_formats:
#         try:
#             return datetime.strptime(s, fmt)
#         except ValueError:
#             pass

#     # 2) Normalize month tokens and parse textual forms
#     # Map every month variant (lowercased, with or without '.'), including 'sept'
#     month_map = {
#         "jan": 1, "jan.": 1, "january": 1,
#         "feb": 2, "feb.": 2, "february": 2,
#         "mar": 3, "mar.": 3, "march": 3,
#         "apr": 4, "apr.": 4, "april": 4,
#         "may": 5, "may.": 5,
#         "jun": 6, "jun.": 6, "june": 6,
#         "jul": 7, "jul.": 7, "july": 7,
#         "aug": 8, "aug.": 8, "august": 8,
#         "sep": 9, "sep.": 9, "sept": 9, "sept.": 9, "september": 9,
#         "oct": 10, "oct.": 10, "october": 10,
#         "nov": 11, "nov.": 11, "november": 11,
#         "dec": 12, "dec.": 12, "december": 12,
#     }

#     # Regex: <month word> <day> [optional comma] <year>, with any spacing
#     import re
#     m = re.match(r"^\s*([A-Za-z]+\.?)\s+(\d{1,2})(?:,)?\s+(\d{4})\s*$", s)
#     if m:
#         month_token = m.group(1).lower()
#         day = int(m.group(2))
#         year = int(m.group(3))

#         # Normalize 'sept' -> 'sep' (already mapped too, but this is explicit)
#         if month_token == "sept":
#             month_token = "sep"

#         if month_token not in month_map:
#             raise ValueError(f"Unrecognized month token: {month_token!r} in {s!r}")

#         month = month_map[month_token]

#         # Basic day-range sanity (doesn't validate 30/31/Feb rules—datetime will)
#         if not (1 <= day <= 31):
#             raise ValueError(f"Day out of range in {s!r}")

#         try:
#             return datetime(year, month, day)
#         except ValueError as e:
#             # Catches impossible dates like Feb 30
#             raise ValueError(f"Invalid calendar date in {s!r}: {e}") from e

#     # 3) Try a few generic English textual strptime variants as a last resort
#     textual_formats = ("%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y")
#     # Pre-normalize lone trailing dots on the first token to help strptime
#     tokens = s.split()
#     if tokens:
#         tokens[0] = tokens[0].rstrip(".")
#         s2 = " ".join(tokens)
#         for fmt in textual_formats:
#             try:
#                 return datetime.strptime(s2, fmt)
#             except ValueError:
#                 pass

#     # If everything failed:
#     raise ValueError(
#         f"Invalid date format: {value!r}. "
#         "Examples I accept: 'Sep 30, 2028', 'September 30, 2028', '2028-09-30', '30/09/2028'."
#     )



# def calculate_years_till_delivery(contract_date, delivery_date):
#     # Ensure contract_date is a datetime object
#     if isinstance(contract_date, str):
#         contract_date = datetime.strptime(contract_date, "%Y-%m-%d")  # Adjust format if needed

#     # Convert delivery_date from string to datetime object
#     if isinstance(delivery_date, str):
#         try:
#             # Try parsing the abbreviated month format first (e.g., "Feb. 28, 2027")
#             delivery_date = parse_human_date(delivery_date)
#         except ValueError:
#             try:
#                 # If that fails, try parsing the full month name format (e.g., "June 30, 2027")
#                 if "." in delivery_date.split()[0]:
#                     delivery_date = delivery_date.replace(".", "")
                
#                 delivery_date = parse_human_date(delivery_date)

#             except ValueError:
#                 # Raise an error if neither format matches
#                 raise ValueError(f"Invalid delivery_date format: {delivery_date}. Expected formats: 'Mon. DD, YYYY' or 'Month DD, YYYY'.")
    
#     delivery_date = parse_human_date(delivery_date)
#     # Calculate the difference in years
#     n_years = (delivery_date - contract_date).days / 365
#     return n_years
 
# def apply_constraints(dp, pmt_percentages, tenor_years, periods_per_year, input_pmts, constraints, contract_date, delivery_date, scheme, special_offer = None):

#     print("///////////////////////////////////")
#     print(f"input_pmts = {input_pmts}") 
#     print(f"pmt_percentages = {pmt_percentages}") 
#     print("///////////////////////////////////")
#     if dp == "": 
#         dp = 0
    
#     project = constraints.project_config.project

#     exteded_payments = ProjectExtendedPayments.objects.filter(project = project, year = tenor_years, scheme = scheme).first()
#     standard_payments = ProjectStanderdPayments.objects.filter(project = project).first()
        
#     if special_offer: 
#         print(f"project = {project}")
#         print(f"tenor_years = {tenor_years}") 
#         exteded_payments = ProjectExtendedPaymentsSpecialOffer.objects.filter(project = project, year = tenor_years).first()
    
#         print(f"exteded_payments = {exteded_payments}")  

#     var_dp = exteded_payments.dp1 + exteded_payments.dp2 
#     # ----------------------------------------------------------------- Minimum Down payment
#     if float(dp) < float(var_dp):
#         pmt_percentages[0] = float(var_dp)
#     else:
#         pmt_percentages[0] = float(dp)

#     # print(f"pmt_percentages = {pmt_percentages}") 

#     if "Sept." in delivery_date:
#         delivery_date = delivery_date.replace("Sept.", "Sep.")

#     try:
#         delivery_date = datetime.strptime(delivery_date, "%b. %d, %Y") 
#     except:
#         # Correct format for "June 30, 2027"
#         delivery_date = datetime.strptime(delivery_date, "%B %d, %Y") 

#     # print(f"input_pmts = {input_pmts}")
    
#     # print(f"pmt_percentages before 1 = {pmt_percentages}")
#     # print() 
#     #^ Calculate the equal remaining payments after deducting the down payment, and custom payments

#     n = int(tenor_years) * int(periods_per_year)  

#     tenor_years = int(tenor_years)
 
#     if n == 1:
#         remaining_percentage1 = 1 - pmt_percentages[0] 
#     else:
#         if n - len(input_pmts) != 0:
#             remaining_percentage1 = (1- float(pmt_percentages[0])  - sum(list(input_pmts.values()))) / (n - len(list(input_pmts.values())))
#         else:
#             remaining_percentage1 = 0

#     remaining_percentages = [remaining_percentage1]
#     # print(f"remaining_percentage1 = {remaining_percentage1}")
#     # print()
#     for k, v in input_pmts.items():
#         if k==0:
#             continue
#         pmt_percentages[k] = v

    
#     print("'''''''''''''''''''''''''''")
#     print(f"pmt_percentages = {pmt_percentages}") 
#     print("'''''''''''''''''''''''''''")


    

#     pmt_percentages[0] = float(pmt_percentages[0]) 




#     if exteded_payments:
#         values = []
#         cumulatives = []

#         # Add DP1 and DP2
#         values.append(exteded_payments.dp1 or 0)
#         values.append(exteded_payments.dp2 or 0)
#         cumulatives.append(exteded_payments.cumulative_dp1 or 0)
#         cumulatives.append(exteded_payments.cumulative_dp2 or 0)

#         # Add Installments and Cumulatives
#         for i in range(1, 49):
#             val = getattr(exteded_payments, f'installment_{i}', 0) or 0
#             cum = getattr(exteded_payments, f'cumulative_{i}', 0) or 0
#             values.append(val)
#             cumulatives.append(cum)


#         print(f"values = {values}")
#         print(f"cumulatives = {cumulatives}")
    

#     print(f"pmt_percentages before = {pmt_percentages}") 
#     if not special_offer:

#         for i in range (1, (tenor_years*4) +1):
#             pmt_percentages[i] = excel_formula(cumulatives[i],i,tenor_years, sum(pmt_percentages[0:i]), cumulatives[i+1], pmt_percentages[i], values[i+1])
#             print()
#     else:
#         for i in range (0, (tenor_years*4) +1):
#             pmt_percentages[i] = excel_formula(cumulatives[i],i,tenor_years, sum(pmt_percentages[0:i]), cumulatives[i+1], pmt_percentages[i], values[i+1])
#             print()


 
#     if scheme == "flat":
#         pmt_percentages = [p if p!=55555 else remaining_percentage1 for p in pmt_percentages]
#         # for i in range (1, (tenor_years*4) +1): 
#         #     if pmt_percentages[i] == 55555:

#         #         pmt_percentages[i] = values[i+1] 

#     else:
#         for i in range (1, (tenor_years*4) +1): 
#             if pmt_percentages[i] == 55555:

#                 pmt_percentages[i] = values[i+1] 
 
#     # print(f"pmt_percentages = {pmt_percentages}")
#     # if 1 in input_pmts.keys(): 
#     #     del input_pmts[1]

#     # print(f"pmt_percentages before 2 = {pmt_percentages}")
#     # ----------------------------------------------------------------- Minimum Down payment Plus First Payment
#     # #^ Handle minimum down payment plus first payment constraint
#     # try:  #  pmt_percentages = [10, 2.5,0,0,0,10]    
#     #     if float(pmt_percentages[0]) + float(input_pmts[1]) <= float(constraints.dp_plus_first_pmt):
#     #         pmt_percentages[1] = float(constraints.dp_plus_first_pmt) - pmt_percentages[0]  # [,]
#     #     else:
#     #         pmt_percentages[1] = float(input_pmts[1])

#     # except:
       
#     #     if float(pmt_percentages[0]) + float(pmt_percentages[1]) <= float(constraints.dp_plus_first_pmt):
#     #         pmt_percentages[1] = round(float(constraints.dp_plus_first_pmt) - pmt_percentages[0], 5)
        

#     # if 1 in input_pmts.keys():
#     #     del input_pmts[1]


#     # #^ Calculate the equal remaining payments after deducting the down payment, first payment, and custom payments
#     # if n == 1:
#     #     remaining_percentage2 = 1 - pmt_percentages[0] - pmt_percentages[1]
        
#     # else:
#     #     if n - 1 - len(input_pmts) != 0:
#     #         remaining_percentage2 = (1- pmt_percentages[0] - pmt_percentages[1] -  sum(list(input_pmts.values()))) / (n - 1 - len(list(input_pmts.values())))
#     #     else:
#     #         remaining_percentage2 = 0
    
#     # remaining_percentages.append(remaining_percentage2)  
    
#     # for k, v in input_pmts.items():
#     #     if k==0 or k==1:
#     #         continue
#     #     pmt_percentages[k] = v

#     # pmt_percentages = [p if p!=remaining_percentage1 else remaining_percentage2 for p in pmt_percentages]

#     # # print(f"pmt_percentages before 3 = {pmt_percentages}")
#     # #^ Handle minimum down payment plus first plus second payment constraint
#     # try:  #  pmt_percentages = [10, 2.5,0,0,0,10]    
#     #     if float(pmt_percentages[0]) + float(input_pmts[1]) + float(input_pmts[2]) <= float(constraints.dp_plus_first_plus_second_pmt):
#     #         pmt_percentages[2] = float(constraints.dp_plus_first_plus_second_pmt) - pmt_percentages[0] - pmt_percentages[1]    # [,]
#     #     else:
#     #         pmt_percentages[2] = float(input_pmts[2])

#     # except:
       
#     #     if float(pmt_percentages[0]) + float(pmt_percentages[1])  + float(pmt_percentages[2]) <= float(constraints.dp_plus_first_plus_second_pmt):
#     #         pmt_percentages[2] = float(constraints.dp_plus_first_plus_second_pmt) - pmt_percentages[0] - pmt_percentages[1] 
        

    
#     # # if float(pmt_percentages[0]) + float(temp) < float(constraints.dp_plus_first_pmt):
#     # #     pmt_percentages[1] = float(constraints.dp_plus_first_pmt) - pmt_percentages[0]

#     # if 2 in input_pmts.keys():
#     #     del input_pmts[2]


#     # #^ Calculate the equal remaining payments after deducting the down payment, first payment, second payment, and custom payments
#     # if n == 1:
#     #     remaining_percentage7 = 1 - pmt_percentages[0] - pmt_percentages[1]  - pmt_percentages[2]
        
#     # else:
#     #     if n - 2 - len(input_pmts) != 0:
#     #         remaining_percentage7 = (1- pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] -  sum(list(input_pmts.values()))) / (n - 2 - len(list(input_pmts.values())))
#     #     else:
#     #         remaining_percentage7 = 0
    
#     # remaining_percentages.append(remaining_percentage7)  
    
#     # for k, v in input_pmts.items():
#     #     if k==0 or k==1 or k==2:
#     #         continue
#     #     pmt_percentages[k] = v

#     # pmt_percentages = [p if p!=remaining_percentage2 else remaining_percentage7 for p in pmt_percentages]

#     # # print(f"pmt_percentages before 4 = {pmt_percentages}")
#     #  #^ Handle minimum down payment plus first plus second payment constraint
#     # try:  #  pmt_percentages = [10, 2.5,0,0,0,10]    
#     #     if float(pmt_percentages[0]) + float(input_pmts[1]) + float(input_pmts[2]) + float(input_pmts[3]) <= float(constraints.dp_plus_first_plus_second_plus_third_pmt):
#     #         pmt_percentages[3] = float(constraints.dp_plus_first_plus_second_plus_third_pmt) - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2]   # [,]
#     #     else:
#     #         pmt_percentages[2] = float(input_pmts[2])

#     # except:
       
#     #     if float(pmt_percentages[0]) + float(pmt_percentages[1])  + float(pmt_percentages[2]) + float(pmt_percentages[3]) <= float(constraints.dp_plus_first_plus_second_plus_third_pmt):
#     #         pmt_percentages[3] = float(constraints.dp_plus_first_plus_second_plus_third_pmt) - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2]
        

    
#     # # if float(pmt_percentages[0]) + float(temp) < float(constraints.dp_plus_first_pmt):
#     # #     pmt_percentages[1] = float(constraints.dp_plus_first_pmt) - pmt_percentages[0]

#     # if 3 in input_pmts.keys():
#     #     del input_pmts[3] 


#     # #^ Calculate the equal remaining payments after deducting the down payment, first payment, and custom payments
#     # if n == 1:
#     #     remaining_percentage8 = 1 - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3]
        
#     # else:
#     #     if n - 3 - len(input_pmts) != 0:
#     #         remaining_percentage8 = (1- pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3] -  sum(list(input_pmts.values()))) / (n - 3 - len(list(input_pmts.values())))
#     #     else:
#     #         remaining_percentage8 = 0
    
#     # remaining_percentages.append(remaining_percentage8)  
    
#     # for k, v in input_pmts.items():
#     #     if k==0 or k==1 or k==2 or k==3:
#     #         continue
#     #     pmt_percentages[k] = v

#     # pmt_percentages = [p if p!=remaining_percentage7 else remaining_percentage8 for p in pmt_percentages]


 
#     # # print(f"pmt_percentages before 5 = {pmt_percentages}")
#     #  #^ Handle minimum down payment plus first plus second payment constraint
#     # try:  #  pmt_percentages = [10, 2.5,0,0,0,10]    
#     #     if float(pmt_percentages[0]) + float(input_pmts[1]) + float(input_pmts[2]) + float(input_pmts[3]) + float(input_pmts[4]) <= float(constraints.dp_plus_first_plus_second_plus_third_plus_forth_pmt):
#     #         pmt_percentages[4] = float(constraints.dp_plus_first_plus_second_plus_third_plus_forth_pmt) - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3]   # [,]
#     #     else:
#     #         pmt_percentages[3] = float(input_pmts[2])

#     # except:
       
#     #     if float(pmt_percentages[0]) + float(pmt_percentages[1])  + float(pmt_percentages[2]) + float(pmt_percentages[3]) + float(pmt_percentages[4])  <= float(constraints.dp_plus_first_plus_second_plus_third_plus_forth_pmt):
#     #         pmt_percentages[4] = float(constraints.dp_plus_first_plus_second_plus_third_plus_forth_pmt) - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3] 
         

    
#     # # if float(pmt_percentages[0]) + float(temp) < float(constraints.dp_plus_first_pmt):
#     # #     pmt_percentages[1] = float(constraints.dp_plus_first_pmt) - pmt_percentages[0]

#     # if 4 in input_pmts.keys():
#     #     del input_pmts[4] 


#     # #^ Calculate the equal remaining payments after deducting the down payment, first payment, and custom payments
#     # if n == 1:
#     #     remaining_percentage10 = 1 - pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3] - pmt_percentages[4]
        
#     # else:
#     #     if n - 4 - len(input_pmts) != 0:
#     #         remaining_percentage10 = (1- pmt_percentages[0] - pmt_percentages[1] - pmt_percentages[2] - pmt_percentages[3] - pmt_percentages[4] -  sum(list(input_pmts.values()))) / (n - 4 - len(list(input_pmts.values())))
#     #     else:
#     #         remaining_percentage10 = 0
    
#     # remaining_percentages.append(remaining_percentage10)  
    
#     # for k, v in input_pmts.items():
#     #     if k==0 or k==1 or k==2 or k==3 or k==4:
#     #         continue
#     #     pmt_percentages[k] = v

#     # pmt_percentages = [p if p!=remaining_percentage8 else remaining_percentage10 for p in pmt_percentages]

#     # # print(f"remaining_percentage8 = {remaining_percentage8}")
#     # # print("------------------------------------------------------")
#     # # print("------------------------------------------------------")
#     # # print("------------------------------------------------------")
#     # # print("------------------------------------------------------")
#     # # print("------------------------------------------------------")
#     # print(f"pmt_percentages before 6 = {pmt_percentages}")


#     # # ----------------------------------------------------------------- First Year Payment
#     # first_year_payments = pmt_percentages[:periods_per_year+1]

    
#     # if sum(first_year_payments) < float(constraints.first_year_min):
#     #     pmt_percentages[periods_per_year] = float(constraints.first_year_min) - sum(first_year_payments[:-1])

    
#     # if sum(pmt_percentages) > 1:

#     #     sum_after_first_year = sum(pmt_percentages[periods_per_year+1:])
#     #     total_custom_payments_after_first_year = float(0)
#     #     num_custom_payments_after_first_year = 0

#     #     for k in input_pmts.keys():
#     #         if k <= periods_per_year:
#     #             continue
#     #         total_custom_payments_after_first_year += pmt_percentages[k]
#     #         num_custom_payments_after_first_year += 1

#     #     excess = sum(pmt_percentages) - 1
        
#     #     remaining_percentage3 = (sum_after_first_year-total_custom_payments_after_first_year-excess) / (len(pmt_percentages[periods_per_year+1:]) - num_custom_payments_after_first_year)
#     #     remaining_percentages.append(remaining_percentage3)

#     #     for i, pmt in enumerate(pmt_percentages[periods_per_year+1:]):
#     #         if pmt in remaining_percentages:
#     #             pmt_percentages[periods_per_year+1+i] = remaining_percentage3

#     # # ----------------------------------------------------------------- Cumulative Minimum Constraint - Before CTD

#     try:
#         years_till_delivery = calculate_years_till_delivery(contract_date, datetime.strptime(delivery_date, "%b. %d, %Y"))
#     except:
#         years_till_delivery = calculate_years_till_delivery(contract_date, delivery_date)
#     for year in range(int(tenor_years)):
#         if year+1 > years_till_delivery:
#             break
    
#         # cummulative_payments = pmt_percentages[:((year+1)*periods_per_year)+1]
        
#         # if sum(cummulative_payments) < (year * float(constraints.annual_min)) + float(constraints.first_year_min):
#         #     pmt_percentages[(year+1)*periods_per_year] = (year * float(constraints.annual_min)) + float(constraints.first_year_min) - sum(cummulative_payments[:-1])

#     # ----------------------------------------------------------------- Cash Till Delivery

#     # ctd_entries = CTD.objects.filter(project_constraints=constraints)
#     # ctd_mins = {str(ctd.term_period): float(ctd.npv_value) for ctd in ctd_entries}
#     # ctd_mins = {float(k):v for k, v in ctd_mins.items()}
#     # diffs = {abs(years_till_delivery-k):v for k, v in ctd_mins.items()}
#     # try:
#     #     ctd = diffs[min(diffs.keys())]
#     # except:
#     #     ctd = 0

#     # print(f"ctd = {ctd}") 

#     delivery_payment_index = math.floor(years_till_delivery * periods_per_year)
    
#     # payments_till_delivery = pmt_percentages[:delivery_payment_index+1]

#     # if sum(payments_till_delivery) < ctd:
#     #     if delivery_payment_index >= len(pmt_percentages):
#     #         pmt_percentages[-1] = ctd - sum(payments_till_delivery[:-1])
#     #     else:
#     #         pmt_percentages[delivery_payment_index] = ctd - sum(payments_till_delivery[:-1])
    

#     # if sum(pmt_percentages) > 1:
#     #     sum_after_delivery = sum(pmt_percentages[4:])
#     #     total_custom_payments_after_delivery = float(0)
#     #     num_custom_payments_after_delivery = 0

#     #     for k in input_pmts.keys():
#     #         if k <= 4-1:
#     #             continue
#     #         total_custom_payments_after_delivery += pmt_percentages[k]
#     #         num_custom_payments_after_delivery += 1

#     #     excess = sum(pmt_percentages) - 1


#     #     remaining_percentage4 = (sum_after_delivery-total_custom_payments_after_delivery-excess) / (len(pmt_percentages[4:]) - num_custom_payments_after_delivery)
#     #     remaining_percentages.append(remaining_percentage4)

#     #     for i, pmt in enumerate(pmt_percentages[4:]):
#     #         if pmt in remaining_percentages:
#     #             pmt_percentages[4+i] = remaining_percentage4



#     # ----------------------------------------------------------------- Cumulative Minimum Constraint - After CTD
#     # print(f"pmt_percentages = {pmt_percentages}")
#     # for year in range(tenor_years):
#     #     if year+1 < years_till_delivery:
#     #         continue
        
#     #     start_index = year * periods_per_year # [4:8]
#     #     end_index = (year + 1) * periods_per_year
#     #     cummulative_payments = pmt_percentages[start_index +1:end_index+1]
#     #     # print(f"cummulative_payments = {cummulative_payments}")
#     #     # break 
#     #     print(f"sum(cummulative_payments)  = {sum(cummulative_payments)}")
#     #     print(f"year * constraints.annual_min  = {year * constraints.annual_min}")
#     #     if sum(cummulative_payments) < (constraints.annual_min) + constraints.first_year_min:
#     #         pmt_percentages[(year+1)*periods_per_year] = (year * float(constraints.annual_min)) + float(constraints.first_year_min) - sum(cummulative_payments[:-1])

#     #         if sum(pmt_percentages) > 1:


#     #             adjustment_index = ((year+1)*periods_per_year)
#     #             sum_after_adjustment = sum(pmt_percentages[adjustment_index+1:])
#     #             total_custom_payments_after_adjustment = 0
#     #             num_custom_payments_after_adjustment = 0
#     #             print(f"adjustment_index = {adjustment_index}")
#     #             for k in input_pmts.keys():
#     #                 if k <= adjustment_index:
#     #                     continue
#     #                 total_custom_payments_after_adjustment += pmt_percentages[k]
#     #                 num_custom_payments_after_adjustment += 1
                
#     #             excess = sum(pmt_percentages) - 1
                 
#     #             remaining_percentage_after_adjustment = (sum_after_adjustment-total_custom_payments_after_adjustment-excess) / (len(pmt_percentages[adjustment_index+1:]) - num_custom_payments_after_adjustment)
                
#     #             remaining_percentages.append(remaining_percentage_after_adjustment)
 
#     #             for i, pmt in enumerate(pmt_percentages[adjustment_index+1:]):
#     #                 if pmt in remaining_percentages:
#     #                     pmt_percentages[adjustment_index+1+i] = remaining_percentage_after_adjustment

#     # Step 1: Save and remove the first value
#     # first_value = pmt_percentages[0]
#     # remaining_values = pmt_percentages[1:]

#     # # Step 2: Split into chunks of 4 (quarters)
#     # chunks = [remaining_values[i:i+4] for i in range(0, len(remaining_values), 4)]
 
#     # # Step 3: Adjust each chunk based on sum
#     # adjusted_chunks = []
#     # for chunk in chunks:
#     #     chunk_sum = sum(chunk)
#     #     if chunk_sum < float(constraints.annual_min):
#     #         adjustment = float(constraints.annual_min) - chunk_sum
            
#     #         chunk[-1] = round(chunk[-1] + adjustment, 3)
#     #     adjusted_chunks.append(chunk)

#     # # Step 4: Flatten the adjusted chunks and re-add the first value
#     # pmt_percentages = [first_value] + [value for chunk in adjusted_chunks for value in chunk]

#     # # ✅ Output

#     # if sum(pmt_percentages) > 1:
#     #     adjustment_index = ((year+1)*periods_per_year)
#     #     sum_after_adjustment = sum(pmt_percentages[adjustment_index+1:])
#     #     total_custom_payments_after_adjustment = 0
#     #     num_custom_payments_after_adjustment = 0

#     #     for k in input_pmts.keys():
#     #         if k <= adjustment_index:
#     #             continue
#     #         total_custom_payments_after_adjustment += pmt_percentages[k]
#     #         num_custom_payments_after_adjustment += 1
        
#     #     excess = sum(pmt_percentages) - 1
#     #     remaining_percentage_after_adjustment = (sum_after_adjustment-total_custom_payments_after_adjustment-excess) / (len(pmt_percentages[adjustment_index+1:]) - num_custom_payments_after_adjustment)
#     #     remaining_percentages.append(remaining_percentage_after_adjustment)

#     #     for i, pmt in enumerate(pmt_percentages[adjustment_index+1:]):
#     #         if pmt in remaining_percentages:
#     #             pmt_percentages[adjustment_index+1+i] = remaining_percentage_after_adjustment

#     # pmt_percentages = [round(p, 3) for p in pmt_percentages]

#     # print()
#     # print()
#     # print()
#     # print(f"pmt_percentages = {pmt_percentages}")
#     # print()
#     # print()
#     # print() 

#     # if tenor_years !=5:
     
#     #     index = 0 
#     #     for i in pmt_percentages:
#     #         if index < 4:
#     #             index += 1
#     #             continue

#     #         # Only process while we haven't reached the full length (40)
#     #         if 40 != len(pmt_percentages[:index]):
#     #             cumm = sum(pmt_percentages[:index]) 
#     #             # print(f"cumm at {index} = {cumm:.5f}")  # Rounded for cleaner output

#     #             target = 0.1 + 0.1 + (0.8 / 36) * (index - 4)
#     #             # print(f"target = {target}")
#     #             # print(f"i = {i}")
#     #             # print(f"target - cumm = {target - cumm}")

 
                
#     #             # If current value is less than or equal to the required adjustment, update it
#     #             if i <= target - cumm:
#     #                 pmt_percentages[index] = target - cumm
#     #                 # print("Changed")

#     #             # print()
#     #             # Else, leave it as is

#     #         index += 1



#     #     # print(f"pmt_percentages after modification  = {pmt_percentages}")

#     #     if sum(pmt_percentages) > 1:
#     #         sum_after_delivery = sum(pmt_percentages[5:])
#     #         total_custom_payments_after_delivery = float(0)
#     #         num_custom_payments_after_delivery = 0

#     #         for k in input_pmts.keys():
#     #             if k <= 5-1:
#     #                 continue
#     #             total_custom_payments_after_delivery += pmt_percentages[k]
#     #             num_custom_payments_after_delivery += 1

#     #         excess = sum(pmt_percentages) - 1

    
#     #         remaining_percentage4 = (sum_after_delivery-total_custom_payments_after_delivery-excess) / (len(pmt_percentages[5:]) - num_custom_payments_after_delivery)
#     #         remaining_percentages.append(remaining_percentage4)

#     #         for i, pmt in enumerate(pmt_percentages[5:]):
#     #             if pmt in remaining_percentages:
#     #                 pmt_percentages[5+i] = remaining_percentage4


#     # else:

#     #     # pmt_percentages = [round(float(val), 5) for val in pmt_percentages]
#     #     # print(f"sum  = {sum(pmt_percentages)}")
#     #     # if sum(pmt_percentages) > 1:
#     #     #     sum_after_delivery = sum(pmt_percentages[5:])
#     #     #     total_custom_payments_after_delivery = float(0)
#     #     #     num_custom_payments_after_delivery = 0

#     #     #     for k in input_pmts.keys():
#     #     #         if k <= 5-1:
#     #     #             continue
#     #     #         total_custom_payments_after_delivery += pmt_percentages[k]
#     #     #         num_custom_payments_after_delivery += 1

#     #     #     excess = sum(pmt_percentages) - 1
#     #     #     print(f"excess = {excess}")  

    
#     #     #     remaining_percentage4 = (sum_after_delivery-total_custom_payments_after_delivery-excess) / (len(pmt_percentages[5:]) - num_custom_payments_after_delivery)
#     #     #     remaining_percentages.append(remaining_percentage4)

#     #     #     for i, pmt in enumerate(pmt_percentages[5:]):
#     #     #         if pmt in remaining_percentages:
#     #     #             pmt_percentages[5+i] = remaining_percentage4

        
#     #     if exteded_payments:
#     #         values = []
#     #         cumulatives = []

#     #         # Add DP1 and DP2
#     #         values.append(exteded_payments.dp1 or 0)
#     #         values.append(exteded_payments.dp2 or 0)
#     #         cumulatives.append(exteded_payments.cumulative_dp1 or 0)
#     #         cumulatives.append(exteded_payments.cumulative_dp2 or 0)

#     #         # Add Installments and Cumulatives
#     #         for i in range(1, 49):
#     #             val = getattr(exteded_payments, f'installment_{i}', 0) or 0
#     #             cum = getattr(exteded_payments, f'cumulative_{i}', 0) or 0
#     #             values.append(val)
#     #             cumulatives.append(cum)


#     #     # print(f"values = {values}")
#     #     # print(f"cumulatives = {cumulatives}")
#     #     index = 0
#     #     index_2 = 2 
#     #     for i in pmt_percentages:
#     #         if index < 1:
#     #             index += 1
#     #             continue 

#     #         # Only process while we haven't reached the full length (40)
#     #         if (tenor_years * 4) != len(pmt_percentages[:index]):
#     #             cumm = sum(pmt_percentages[:index ]) 


#     #             # target = 0.1 + 0.075 + (0.825 / 37) * (index - 3) 
#     #             # print(f"index = {index}")   
#     #             # print(f"value = {values[index_2]}")
                
                
#     #             # print(f"cumm at {index} = {cumm:.5f}")  # Rounded for cleaner output
#     #             # print(f"cumulatives[index_2]  = {cumulatives[index_2] }") 
#     #             target  = cumulatives[index_2] - cumm 
                
#     #             # print(f"target = {target}") 
                 

#     #             # print(f"i = {i}")
#     #             # print(f"pmt_percentages[index] before = {pmt_percentages[index]}")
                        

#     #             # if target < 0:
#     #             #     index += 1
#     #             #     index_2 += 1
#     #             #     pmt_percentages[index] = i 
#     #             #     continue 

#     #             # If current value is less than or equal to the required adjustment, update it
#     #             if i <= target:
#     #                 pmt_percentages[index] = target 

                

#     #             # if target < 0:


#     #             # print(f"pmt_percentages[index] after = {pmt_percentages[index]}")
                

#     #             print()
#     #             # Else, leave it as is

#     #         index += 1
#     #         index_2 += 1
    
#     #     print()
#     #     print()
#     #     print()
#     #     print()
#     #     # print(f"pmt_percentages after modification  = {pmt_percentages}")

#     #     if sum(pmt_percentages) >= 1:

#     #         sum_after_delivery_2 = sum(pmt_percentages[5:])
#     #         total_custom_payments_after_delivery_2 = float(0)
#     #         num_custom_payments_after_delivery_2 = 0

#     #         for k in input_pmts.keys():
#     #             if k <= 5-1:
#     #                 continue
#     #             total_custom_payments_after_delivery_2 += pmt_percentages[k]
#     #             num_custom_payments_after_delivery_2 += 1

#     #         excess_2 = sum(pmt_percentages) - 1

#     #         # if len(pmt_percentages[5:]) !=  num_custom_payments_after_delivery:
#     #         #     remaining_percentage4 = (sum_after_delivery-total_custom_payments_after_delivery-excess) / (len(pmt_percentages[5:]) - num_custom_payments_after_delivery)
#     #         # else:
#     #         #     remaining_percentage4 =  0

#     #         remaining_percentage11 = (sum_after_delivery_2-total_custom_payments_after_delivery_2-excess_2) / (len(pmt_percentages[5:]) - num_custom_payments_after_delivery_2)

#     #         remaining_percentages.append(remaining_percentage11)

#     #         for i, pmt in enumerate(pmt_percentages[5:]):
#     #             if pmt in remaining_percentages:
#     #                 pmt_percentages[5+i] = remaining_percentage11 


        
#     # if sum(pmt_percentages) < 1:
#     #     pmt_percentages[-1] = 1 - sum(pmt_percentages[:-1])

#     # print()
#     # print()
#     # print()


 
#     # print(f"pmt_percentages before returning = {pmt_percentages}")
#     # print()
#     # print()
#     # print()

#     return pmt_percentages, delivery_payment_index



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

def calculate_max_tenor_years(project_config, tenor_years, base_tenor_years, first_year_min, annual_min):
    
    try:
        max_tenor_years = int((1-float(first_year_min))/float(annual_min)) + 1 ## Force maximum tenor years based on project constraints
        tenor_years = float(tenor_years)
        base_tenor_years = float(base_tenor_years)
        if tenor_years > max_tenor_years:
            tenor_years = max_tenor_years
        elif tenor_years == 0:
            tenor_years = base_tenor_years
        print("yes")

    except:
        max_tenor_years  = project_config.max_tenor_years # Edittable
        # tenor_years = base_tenor_years
        print("No")
        traceback.print_exc()

    

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
    standard_payments = ProjectStanderdPayments.objects.filter(project = project).first()
        
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