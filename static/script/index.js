let updateCycleCounter = 0;
// Always store discounted price in EGP (backend currency)
let discountedPriceEGP = 0;

function getSelectedRate() {
  return (typeof selectedCurrencyRate !== "undefined" && selectedCurrencyRate)
    ? Number(selectedCurrencyRate)
    : 1;
}



document.addEventListener("DOMContentLoaded", () => {
    initializeEventListeners();
    setupInputStyling();
    
    if (hasMultipleDp){
        try{
            if (document.getElementById("dp_needed_percentage").value < Number(getBaseDp())/2){
                document.getElementById("dp_needed_percentage_cumulative").innerHTML = formatPercentageChange(Number(getBaseDp())/2);
                document.getElementById("dp_needed_percentage_cumulative_2").innerHTML = formatPercentageChange(Number(getBaseDp())/2);
        
            }
            else{
                document.getElementById("dp_needed_percentage_cumulative").innerHTML = Number(document.getElementById("dp_needed_percentage").value)  
                document.getElementById("dp_needed_percentage_cumulative_2").innerHTML = Number(document.getElementById("dp_needed_percentage_2").value)      
            }
        }
        catch{
    
        }
        
    }
    else{

        try{
            if (document.getElementById("dp_needed_percentage").value < Number(getBaseDp())){
                document.getElementById("dp_needed_percentage_cumulative").innerHTML = formatPercentageChange(Number(getBaseDp()));
        
            }
            else{
                document.getElementById("dp_needed_percentage_cumulative").innerHTML = Number(document.getElementById("dp_needed_percentage").value)  
            }
        }
        catch{
    
        }

    }

    // Initialize discount field if it exists
    const discountInput = document.getElementById("price_discount");
    if (discountInput) {
        discountInput.value = "";
        discountInput.addEventListener("input", () => {
            // Debounce the discount calculation
            clearTimeout(window.discountTimeout);
            window.discountTimeout = setTimeout(applyPriceDiscount, 500);
        });
    }



    //document.getElementById("dp").value = ""; 
    try{

        document.getElementById("tenor_years").value = document.getElementById("project_config_base_tenor")?.value;
        document.getElementById("dp_date").innerHTML = formatDate(new Date()); 
        document.getElementById("dp").value = "";
    }
    catch(e){

    }

    let dpNeededPercentageContainer_2 = ""
    let dpNeededAmountContainer_2 = ""
    let x_2  = ""
    if (hasMultipleDp){
        document.getElementById("dp_date_2").innerHTML = formatDate(new Date());
        document.getElementById("dp_2").value = "";
        document.getElementById("dp_needed_percentage").innerHTML = formatPercentageChange(Number(getBaseDp())/2);
        document.getElementById("dp_needed_percentage_2").innerHTML = formatPercentageChange(Number(getBaseDp()/2));
        dp_temp = Number(document.getElementById("dp_needed_percentage").innerHTML.replace("%", ''))

        dp_temp_2 = Number(document.getElementById("dp_needed_percentage_2").innerHTML.replace("%", ''))
        document.getElementById("dp_needed_percentage_cumulative").innerHTML = formatPercentageChange(Number(getBaseDp() / 2));
        document.getElementById("dp_needed_percentage_cumulative_2").innerHTML = formatPercentageChange(Number(getBaseDp() / 2));
        
        dpNeededPercentageContainer_2 = document.getElementById("dp_needed_percentage_container_2");
        dpNeededPercentageContainer_2.style.border = "1px solid #ccc";

        dpNeededAmountContainer_2 = document.getElementById("dp_needed_amount_container_2");
        dpNeededAmountContainer_2.style.border = "1px solid #ccc";

        x_2  = document.getElementById("dp_needed_percentage_cumulative_container_2")
        x_2.style.border = "1px solid #ccc";
    }
    else{

        try{
            document.getElementById("dp_needed_percentage").innerHTML = formatPercentageChange(Number(getBaseDp()));
            document.getElementById("dp_needed_percentage_cumulative").innerHTML = formatPercentageChange(Number(getBaseDp()));
        }
        catch(e){}

    }
    
    try{
        const dpNeededPercentageContainer = document.getElementById("dp_needed_percentage_container");
        dpNeededPercentageContainer.style.border = "1px solid #ccc";
        
    
        const dpNeededAmountContainer = document.getElementById("dp_needed_amount_container");
        dpNeededAmountContainer.style.border = "1px solid #ccc";
    
    
        let x  =document.getElementById("dp_needed_percentage_cumulative_container")
        x.style.border = "1px solid #ccc";
    
    
        // ✅ Automatically generate table on page load if base_tenor_years is available
        const tenorYearsInput = document.getElementById("tenor_years");
        const baseTenorYears = parseFloat(tenorYearsInput.value) || parseFloat(document.getElementById("project_config_base_tenor")?.value) || 0;
    
        if (baseTenorYears > 0) {
            tenorYearsInput.value = baseTenorYears; // ✅ Set value if not already set
            realPercentage = []
            // maintenance_fees = []
            // gas_fees = []
            generateInstallmentTable(); // ✅ Generate the table with the correct number of rows
            applyBordersToTable();
            sendInstallmentData(); // ✅ Apply borders to all cells after generating rows
    
        }
    
        const finalPrice = document.getElementById("final_price")
        finalPrice.value = ""
        
        let maintenance_fees = ""
        let gas_fees = ""
    
        if(hasMaintenance){
            maintenance_fees = document.getElementById("maintenance_fees")
            maintenance_fees.value = ""
        }
    
        if(hasGas){
             gas_fees = document.getElementById("gas_fees")
             gas_fees.value = ""
        }
    
    
    
        const dateInput = document.getElementById("contract_date");
        const displayInput = document.getElementById("contract_date_display");
    
        function formatDateToDDMMYYYY(dateStr) {
            const date = new Date(dateStr);
            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const year = date.getFullYear();
            return `${day}/${month}/${year}`;
        }
    
        // Set today's date
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;
        displayInput.value = formatDateToDDMMYYYY(today);
    
        // When user changes the date via calendar
        dateInput.addEventListener("change", function () {
            displayInput.value = formatDateToDDMMYYYY(dateInput.value);
        });
    }
    catch(e){

    }

    try{
        handleSpecialOfferChange()
    }
    catch(e){
        
    }
});


function initializeEventListeners() {

    try {
        document.querySelectorAll(".custom-dropdown .dropdown-options li").forEach(option => {
            option.addEventListener("click", handleDropdownSelection);
        });

        document.querySelectorAll(".custom-dropdown-2 .dropdown-options li").forEach(option => {
            option.addEventListener("click", handleDropdownSelection2);
        });

        document.addEventListener("click", closeDropdownOnClickOutside);
        document.addEventListener("click", closeDropdownOnClickOutside2);

        // Initialize the ID for the currently selected option
        const selectedOption = document.querySelector(".custom-dropdown .selected-option");
        let selectedOption2 = document.querySelector(".custom-dropdown-2 .selected-option-2");
        selectedOption2.innerText = selectedOption2.innerText.replace(/([a-z])([A-Z])/g, '$1 $2');

        const dropdown = selectedOption.closest(".custom-dropdown");
        const dropdown2 = selectedOption2.closest(".custom-dropdown-2");
        // console.log(dropdown)
        // console.log(dropdown2)

        const selectedValue = Array.from(dropdown.querySelectorAll(".dropdown-options li"))
            .find(li => li.classList.contains("selected"))?.textContent.trim();

        const selectedValue2 = Array.from(dropdown2.querySelectorAll(".dropdown-options li"))
            .find(li => li.classList.contains("selected"))?.textContent.trim();

        if (selectedValue) {
            selectedOption.textContent = selectedValue;
            selectedOption.id = "base_payment_frequency";
        }

        // console.log(selectedOption2.innerText)
        if (selectedValue2) {
            // Convert "FlatBackLoaded" to "Flat Back Loaded"
            const spacedOption = selectedValue2.replace(/([a-z])([A-Z])/g, '$1 $2');

            selectedOption2.textContent = spacedOption;

            // selectedOption2.textContent = selectedValue2;
            selectedOption2.id = "payment_scheme";
        }

        let elements = ""
        if (hasMultipleDp) {
            if (special_offers_exist == true) {
                elements = {
                    installmentTableBody: document.getElementById("installmentTableBody"),
                    contractDate: document.getElementById("contract_date"),
                    dpInput: document.getElementById("dp"),
                    dpInput_2: document.getElementById("dp_2"),
                    tenor_years: document.getElementById("tenor_years"),
                    special_offer: document.getElementById("special_offers")
                };
            } else {
                elements = {
                    installmentTableBody: document.getElementById("installmentTableBody"),
                    contractDate: document.getElementById("contract_date"),
                    dpInput: document.getElementById("dp"),
                    dpInput_2: document.getElementById("dp_2"),
                    tenor_years: document.getElementById("tenor_years"),
                };


            }



            elements.installmentTableBody.addEventListener("input", () => {
                const sum = getSumOfInputs();
                const dp = getDpValue() * 100
                const dp_2 = getDpValue_2() * 100
                const inputs = document.querySelectorAll("#installmentTableBody input");


                if (sum + dp + dp_2 >= 100) {
                    inputs.forEach(input => {
                        const inputValue = parseFloat(input.value.trim());
                        if (!isNaN(inputValue) && sum - inputValue < 100) {
                            // CHECK PERMISSION BEFORE ENABLING
                            if (typeof userCanEdit !== 'undefined' && userCanEdit) {
                                input.disabled = false; // Allow editing only if it doesn't exceed 100
                            }
                        } else {
                            input.disabled = true; // Disable further input
                        }
                    });
                } else {
                    inputs.forEach(input => {
                        // CHECK PERMISSION BEFORE ENABLING
                        if (typeof userCanEdit !== 'undefined' && userCanEdit) {
                            input.disabled = false; // Enable all inputs if the sum is below 100
                        }
                    });
                }

                sendInstallmentData();
            });
        } else {

            if (special_offers_exist == true) {

                elements = {
                    installmentTableBody: document.getElementById("installmentTableBody"),
                    contractDate: document.getElementById("contract_date"),
                    dpInput: document.getElementById("dp"),
                    tenor_years: document.getElementById("tenor_years"),
                    special_offer: document.getElementById("special_offers")
                };
            } else {
                elements = {
                    installmentTableBody: document.getElementById("installmentTableBody"),
                    contractDate: document.getElementById("contract_date"),
                    dpInput: document.getElementById("dp"),
                    tenor_years: document.getElementById("tenor_years"),
                };

            }


            elements.installmentTableBody.addEventListener("input", () => {
                const sum = getSumOfInputs();
                const dp = getDpValue() * 100
                const inputs = document.querySelectorAll("#installmentTableBody input");

                if (sum + dp >= 100) {
                    inputs.forEach(input => {
                        const inputValue = parseFloat(input.value.trim());
                        if (!isNaN(inputValue) && sum - inputValue < 100) {
                            // CHECK PERMISSION BEFORE ENABLING
                            if (typeof userCanEdit !== 'undefined' && userCanEdit) {
                                input.disabled = false; // Allow editing only if it doesn't exceed 100
                            }
                        } else {
                            input.disabled = true; // Disable further input
                        }
                    });
                } else {
                    inputs.forEach(input => {
                        // CHECK PERMISSION BEFORE ENABLING
                        if (typeof userCanEdit !== 'undefined' && userCanEdit) {
                            input.disabled = false; // Enable all inputs if the sum is below 100
                        }
                    });
                }

                sendInstallmentData();
            });
        }

        elements.contractDate.addEventListener("input", () => {
            generateInstallmentTable();
            applyBordersToTable();
            sendInstallmentData();
            if (special_offers_exist == true) {
                handleSpecialOfferChange()
            }

        });


        if (special_offers_exist == true) {
            elements.special_offer.addEventListener("input", () => {
                // Regenerate installment table and send data regardless
                realPercentage = [];
                maintenance_fees = [];
                gas_fees = [];
                dates = [];
                generateInstallmentTable();
                hideInstallmentInputs();
                applyBordersToTable();
                sendInstallmentData();



                // ----> This is the new part:
                // Disable #dp
                const dpInput = document.getElementById("dp");
                if (dpInput) {
                    // dpInput.setAttribute("readonly", true); // Or use .disabled = true for grayed-out style
                    // dpInput.disabled = true;
                    dpInput.style.display = "none"

                }

                // Disable #dp_2 if it exists
                const dp2Input = document.getElementById("dp_2");
                if (dp2Input) {
                    // dp2Input.setAttribute("readonly", true);
                    dp2Input.style.display = "none"
                    // dp2Input.disabled = true;
                }


                if (document.getElementById("special_offers").value == "") {
                    dpInput.style.display = ""
                    dpInput.setAttribute("readonly", false);
                    dpInput.disabled = false
                    dpInput.required = true

                    if (dp2Input) {
                        dp2Input.style.display = ""
                        dp2Input.setAttribute("readonly", false);
                        dp2Input.disabled = false

                    }
                }

                hideInstallmentInputs();

            });
        }



        elements.tenor_years.addEventListener("change", () => {
            const tenorValue = elements.tenor_years.value.trim();

            if (tenorValue === "0" || parseFloat(tenorValue) === 0) {
                let discountValue = Number(document.getElementById("project_constraints_max_discount").value);

                const currencySelect = document.getElementById("currency");

                try {
                    handleSpecialOfferChange()
                } catch (e) {}

                let basicPriceText = document.getElementById("basic_price").value;

                // Step 1: Remove commas and extract only the numeric part
                let numericValue = parseFloat(basicPriceText.replace(/[^0-9.]/g, ''));

                // Step 2: Apply discount

                let finalPrice = Math.ceil(((1 - discountValue) * numericValue) / 1000) * 1000;

                // Step 3: Set formatted value back to input (optional)
                document.getElementById("final_price").value = finalPrice.toLocaleString() + currencySelect.value;


                const percentage_change = document.getElementById("percentage_change");
                const raw = discountValue;
                const percentage = (Math.abs(raw) * 100).toFixed(1);

                if (parseFloat(percentage) === 0.0) {
                    percentage_change.value = "-";
                } else {
                    percentage_change.value = `(${percentage}%)`;
                }

                realPercentage = []
                maintenance_fees = []
                gas_fees = []
                dates = []
                try {
                    handleSpecialOfferChange()
                } catch (e) {}




            } else {

                // Regenerate installment table and send data regardless
                // generateInstallmentTable();
                // applyBordersToTable();
                // sendInstallmentData();
                // try {
                //     handleSpecialOfferChange()
                // } catch (e) {}
                // realPercentage = []
                // maintenance_fees = []
                // gas_fees = []
                // dates = []

                stabilizeSchemeCalculation();



            }

        });

        elements.dpInput.addEventListener("input", handleDpInput);
        elements.dpInput.addEventListener("change", handleDpInput);

        if (hasMultipleDp) {
            elements.dpInput_2.addEventListener("input", handleDpInput);
            elements.dpInput_2.addEventListener("change", handleDpInput);
        }

        document.addEventListener("keydown", handleEnterKey);

        // Add this to your input listeners
        elements.dpInput.addEventListener("input", () => {
            updateCycleCounter = 0; // Reset counter because this is a NEW manual change
            handleDpInput();
        });

        if (hasMultipleDp) {
            elements.dpInput_2.addEventListener("input", () => {
                updateCycleCounter = 0; // Reset counter
                handleDpInput();
            });
        }


    } catch {}
}

function setupInputStyling() {
    const styleConfig = {
        border: "none",
        outline: "none",
        background: "none",
        fontSize: "14px",
        textAlign: "center",
        padding: "5px"
    };


    document.querySelectorAll("#installmentTableBody input").forEach(input => {
        Object.assign(input.style, styleConfig);

        

        input.addEventListener("focus", () => {
            if (!input.disabled) {
                input.style.background = "#f1f1f1";
            }
        });

        input.addEventListener("blur", () => {
            if (!input.disabled) {
                input.style.background = "none";
            }
        });
    });
}

function hideInstallmentInputs() {
    document.querySelectorAll("#installmentTableBody input").forEach(input => {
        input.style.display = "none";
    });
}

function showInstallmentInputs() {
    document.querySelectorAll("#installmentTableBody input").forEach(input => {
        input.style.display = "inline-block";
    });

    const dpInput = document.getElementById("dp");
    if (dpInput) {
        // dpInput.setAttribute("readonly", true); // Or use .disabled = true for grayed-out style
        // // dpInput.disabled = true;
        // dpInput.style.display = "inline-block"

    }

    // Disable #dp_2 if it exists
    const dp2Input = document.getElementById("dp_2");
    if (dp2Input) {
        // dp2Input.setAttribute("readonly", true);
        // dp2Input.style.display = "inline-block"
        // // dp2Input.disabled = true;
    }
}


function handleDpInput(skipFetch = false, manualPrice = null) {
    const finalPriceInput = document.getElementById("final_price");
    let finalPriceNum = 0;

    // Use the passed price if available, otherwise parse the input box
    if (manualPrice !== null) {
        finalPriceNum = manualPrice;
    } else {
        const finalPriceStr = finalPriceInput ? finalPriceInput.value : "";
        finalPriceNum = parseFloat(finalPriceStr.replace(/[^\d.]/g, '')) || 0;
    }

    if (hasMultipleDp) {
        const dpInput = document.getElementById("dp");
        const dpInput_2 = document.getElementById("dp_2");
        const dpNeededPercentage = document.getElementById("dp_needed_percentage");
        const dpNeededPercentage_2 = document.getElementById("dp_needed_percentage_2");

        const plan_dp1 = typeof global_plan_dp1 !== 'undefined' ? global_plan_dp1 : (global_base_dp / 2);
        const plan_dp2 = typeof global_plan_dp2 !== 'undefined' ? global_plan_dp2 : (global_base_dp / 2);
        const totalPlanFloor = plan_dp1 + plan_dp2;

        let currentValue = Number(dpInput.value) || 0; 
        let currentValue_2 = Number(dpInput_2.value) || 0;

        // ✅ Store user input before any recalibration
        const userInputDP1 = currentValue;
        const userInputDP2 = currentValue_2;

        // // ✅ ONLY update the .value if the user isn't currently typing (is not focused)
        // if (document.activeElement !== dpInput && currentValue > 0) {
        //     dpInput.value = currentValue; 
        // }
        // if (document.activeElement !== dpInput_2 && currentValue_2 > 0) {
        //     dpInput_2.value = currentValue_2;
        // }

        let effectiveDp1 = Math.max(currentValue, plan_dp1);
        dpNeededPercentage.innerHTML = `${effectiveDp1.toFixed(1)}%`;
        document.getElementById("dp_needed_percentage_cumulative").innerHTML = `${effectiveDp1.toFixed(1)}%`;
        
        let dp2RequiredFloor = Math.max(0, totalPlanFloor - effectiveDp1);
        let effectiveDp2 = Math.max(currentValue_2, dp2RequiredFloor);
        dpNeededPercentage_2.innerHTML = `${effectiveDp2.toFixed(1)}%`;
        document.getElementById("dp_needed_percentage_cumulative_2").innerHTML = `${effectiveDp2.toFixed(1)}%`;

        // ONLY update amounts if we actually have a price, otherwise keep the value from updateResults
        if (!isNaN(finalPriceNum) && finalPriceNum > 0) {
            document.getElementById("dp_needed_amount").innerHTML = ((effectiveDp1 / 100) * finalPriceNum).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
            document.getElementById("dp_needed_amount_2").innerHTML = ((effectiveDp2 / 100) * finalPriceNum).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        }

        // // ✅ RESTORE user input if they typed something
        // if (userInputDP1 > 0) {
        //     dpInput.value = userInputDP1;
        // }
        // if (userInputDP2 > 0) {
        //     dpInput_2.value = userInputDP2;
        // }

        if (currentValue < plan_dp1 && currentValue != 0 ) {
            dpInput.style.color = "red";
            return;
        }
        
        if (currentValue == 0){
            dpInput.style.color = "red";
        }
        else{
            dpInput.style.color = "black";
        }

        if (currentValue_2 < plan_dp2 && currentValue_2 != 0 ) {
            dpInput_2.style.color = "red";
        }
        else{
            dpInput_2.style.color = "black";
        }
        
        if (currentValue_2 == 0){
            dpInput_2.style.color = "red";
        }

        if (!skipFetch) sendInstallmentData();

        dp_temp = Number(effectiveDp1.toFixed(5));
        dp_temp_2 = Number(effectiveDp2.toFixed(5));
        
    } else {
        const dpInput = document.getElementById("dp");
        const baseDp = global_base_dp;
        const currentValue = Number(dpInput.value) || 0;

        // ✅ ONLY update the .value if the user isn't currently typing
        // if (document.activeElement !== dpInput && currentValue > 0) {
        //     dpInput.value = currentValue;
        // }
        
        // ✅ Store user input before any recalibration
        const userInputDP = currentValue;
        
        const effectivePerc = Math.max(currentValue, baseDp);
        
        document.getElementById("dp_needed_percentage").innerHTML = `${effectivePerc.toFixed(1)}%`;
        document.getElementById("dp_needed_percentage_cumulative").innerHTML = `${effectivePerc.toFixed(1)}%`;

        if (!isNaN(finalPriceNum) && finalPriceNum > 0) {
            document.getElementById("dp_needed_amount").innerHTML = ((effectivePerc / 100) * finalPriceNum).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        }
        
        // ✅ RESTORE user input if they typed something
        // if (userInputDP > 0) {
        //     dpInput.value = userInputDP;
        // }

        if (!skipFetch) sendInstallmentData();
        dp_temp = Number(effectivePerc.toFixed(5));
    }
}



function generateInstallmentTable() {
    const tableBody = document.getElementById("installmentTableBody");
    let tableContainer = document.getElementById("installmentTableContainer");

    const tenorYears = parseFloat(document.getElementById("tenor_years").value);
    const selectedOption = document.querySelector(".custom-dropdown .selected-option");
    const paymentFrequency = selectedOption?.textContent.trim().toLowerCase() || "";
    const { monthsToAdd, multiplier } = getFrequencyConfig(paymentFrequency);

    if (!tenorYears || tenorYears <= 0) {
        tableContainer.style.display = "none";
        tableBody.innerHTML = ""; 
        return;
    }

    let years = 0;
    let fullInstallments = 0;
    try {
        let special_offer = document.getElementById("special_offers").value;
        const match = special_offer.match(/(\d+)\s*years/i);
        if (match) years = parseInt(match[1], 10);
    } catch (err) { years = 0; }

    fullInstallments = (years != 0) ? parseInt(years * multiplier) : parseInt(tenorYears * multiplier);

    // ✅ CHECK: If row count matches, do not clear innerHTML. This prevents input deletion.
    const currentRows = tableBody.querySelectorAll("tr");
    const needsRebuild = currentRows.length !== fullInstallments;

    if (needsRebuild) {
        tableBody.innerHTML = ""; 
    }

    // --- Date Logic Fix ---
    const dp1_plan = window.global_plan_dp1 || 0; 
    const dp2_plan = window.global_plan_dp2 || 0;
    const resDateInput = document.getElementById("contract_date").value;
    let currentDate = resDateInput ? new Date(resDateInput) : new Date();

    if (dp1_plan === 0 && dp2_plan === 0) {
        // Case 1: PMT 1 starts exactly on Reservation Date
        contract_date = -1
        contract_date_2 = -1
    } else if (dp2_plan === 0) {
        // Case 2: PMT 1 = Reservation Date + periodBetweenDPandInstallment
        currentDate.setMonth(currentDate.getMonth() + periodBetweenDPandInstallment);
        contract_date_2 = -1
        
    } else {
        currentDate = getContractDate(); 
    }

    dates = []; 
    for (let i = 0; i < fullInstallments; i++) {
        const installmentDate = new Date(currentDate);
        dates.push(installmentDate);

        if (needsRebuild) {
            const row = createInstallmentRow(i + 1, installmentDate);
            tableBody.appendChild(row);
        } else {
            // Update only the date cell, keep the input box focused
            const existingRow = currentRows[i];
            const dateCell = existingRow.cells[1];
            if (dateCell) dateCell.textContent = formatDate(installmentDate);
        }
        currentDate.setMonth(currentDate.getMonth() + monthsToAdd);
    }

    tableContainer.style.display = "block";
    applyBordersToTable();
    
    // ✅ REMOVED: Don't clear DP inputs automatically - only clear when scheme/tenor changes via stabilization
}


let recalibrationAttempts = 0;
const MAX_RECALIBRATION_ATTEMPTS = 3;

function stabilizeSchemeCalculation() {
    recalibrationAttempts = 0;
    
    // ✅ Only clear DP inputs if they're empty or at default values
    // const dpInput = document.getElementById("dp");
    // const dp2Input = document.getElementById("dp_2");
    
    // // Check if DP inputs have user-entered values
    // const hasUserDP1 = dpInput && dpInput.value && dpInput.value.trim() !== "" && parseFloat(dpInput.value) > 0;
    // const hasUserDP2 = dp2Input && dp2Input.value && dp2Input.value.trim() !== "" && parseFloat(dp2Input.value) > 0;
    
    // // Only clear if no user input
    // if (!hasUserDP1) {
    //     dpInput.value = "";
    // }
    // if (!hasUserDP2) {
    //     dp2Input.value = "";
    // }
    
    // Force initial calculation
    sendInstallmentData();
    
    // Then recalibrate up to 3 times
    recalibrateScheme();
}

function recalibrateScheme() {
    if (recalibrationAttempts >= MAX_RECALIBRATION_ATTEMPTS) {
        recalibrationAttempts = 0;
        return;
    }
    
    recalibrationAttempts++;
    
    // Small delay to ensure DOM updates
    setTimeout(() => {
        // Force recalculation
        sendInstallmentData();
        
        // Check if we need another recalibration
        setTimeout(() => {
            // const dp1 = parseFloat(document.getElementById("dp_needed_percentage").innerHTML.replace("%", "")) || 0;
            // const expectedDp1 = window.global_plan_dp1 || (global_base_dp / 2);
            
            // // ✅ Check if DP input has user value - if yes, don't recalibrate
            // const dpInput = document.getElementById("dp");
            // const hasUserDP1 = dpInput && dpInput.value && dpInput.value.trim() !== "" && parseFloat(dpInput.value) > 0;
            
            // if (!hasUserDP1 && Math.abs(dp1 - expectedDp1) > 0.1) {
            //     // Still not correct, recalibrate again
            //     recalibrateScheme();
            // } else {
            //     recalibrationAttempts = 0;
            // }

            // ✅ MODIFIED: Always stop after max attempts, don't check DP values
            // This prevents clearing user input
            if (recalibrationAttempts < MAX_RECALIBRATION_ATTEMPTS) {
                recalibrateScheme();
            } else {
                recalibrationAttempts = 0;
            }
        }, 100);
    }, 100);
}

function applyBordersToTable() {
    document.querySelectorAll("#installmentTableBody tr td").forEach(cell => {
        cell.style.border = "1px solid #ccc"; // ✅ Apply border
        cell.style.padding = "5px"; // ✅ Add padding for better visibility
    });
}


function getFrequencyConfig(frequency) {
    const config = {
        quarterly: { monthsToAdd: 3, multiplier: 4 },
        monthly: { monthsToAdd: 1, multiplier: 12 },
        "semi-annually": { monthsToAdd: 6, multiplier: 2 },
        annually: { monthsToAdd: 12, multiplier: 1 }
    };
    return config[frequency] || { monthsToAdd: 0, multiplier: 1 };
}

function getContractDate() {
    const contractDateInput = document.getElementById("contract_date").value;
    const contractDate = contractDateInput ? new Date(contractDateInput) : new Date();
    
    // Clone the date to avoid modifying the original
    const nextMonthDate = new Date(contractDate);
    const nextMonthDate2 = new Date(contractDate);

    if (hasMultipleDp) {
        // If multiple DPs exist, add both the gap between DPs 
        // AND the gap between the last DP and the first installment
        nextMonthDate.setMonth(
            contractDate.getMonth() + 
            periodBetweenDPs + 
            periodBetweenDPandInstallment
        );
        nextMonthDate2.setMonth(
            contractDate.getMonth()
        );
        contract_date = contractDate
        contract_date_2 = nextMonthDate2

    } else {
        // Standard behavior for single DP
        nextMonthDate.setMonth(
            contractDate.getMonth() + 
            periodBetweenDPandInstallment
        );
        contract_date = contractDate


    }
    
    return nextMonthDate;
}


function applyPriceDiscount() {
    const discountInput = document.getElementById("price_discount");
    const basicPriceInput = document.getElementById("basic_price");
    const discountedPriceInput = document.getElementById("discounted_price");
    const discountedPriceGroup = document.getElementById("discounted-price-group");

    // NEW: Identify Additional Discount percentage but don't apply it to the "Discounted Price" label
    const addDiscInput = document.getElementById("additional_discount");
    let additionalDiscountPct = 0;
    if (hasAdditionalDiscount && addDiscInput && addDiscInput.value !== "-") {
        additionalDiscountPct = parseFloat(addDiscInput.value.replace(/[^\d.]/g, "")) || 0;
    }

    if (!discountInput || !basicPriceInput || !discountedPriceInput) return;

    const discountPercentage = parseFloat(discountInput.value) || 0;

    if (discountPercentage > 0) {
        const basicPriceText = basicPriceInput.value || "";
        let basicPriceNumber = parseFloat(basicPriceText.replace(/[^0-9.]/g, "")) || 0;
        
        const rate = getSelectedRate();
        if (rate && rate !== 1) {
            basicPriceNumber = basicPriceNumber / rate;
        }

        if (basicPriceNumber > 0) {
            // ONLY apply the manual discount percentage here
            let manualFactor = (1 - discountPercentage / 100);
            
            // Calculate discounted price in EGP (Base) - affected ONLY by manual discount
            discountedPrice = basicPriceNumber * manualFactor;
            
            // Round to nearest 1000 EGP
            discountedPrice = Math.ceil(discountedPrice / 1000) * 1000;

            // Store this for the updateResults function
            discountedPriceEGP = discountedPrice;

            // --- DISPLAY LOGIC (Convert back to UI Currency) ---
            const displayPrice = discountedPrice * rate;
            const displayRounded = Math.ceil(displayPrice / 1000) * 1000;

            window.discountedPriceDisplay = displayRounded;

            const currencySymbol = getCurrencySymbol();
            discountedPriceInput.value = displayRounded.toLocaleString() + " " + currencySymbol;
            
            if (discountedPriceGroup) discountedPriceGroup.style.display = "flex";

            recalculateWithDiscount();
            return;
        }
    }

    discountedPrice = 0;
    discountedPriceEGP = 0;
    window.discountedPriceDisplay = 0;

    if (discountedPriceGroup) discountedPriceGroup.style.display = "none";
    discountedPriceInput.value = "";

    recalculateWithDiscount();
}


function getCurrencySymbol() {
    const currencySelect = document.getElementById("currency");
    return currencySelect ? currencySelect.value : "EGP";
}

function recalculateWithDiscount() {
    // This function should trigger the installment recalculations

    const basicPriceInput = document.getElementById("basic_price");

    // ✅ Prefer raw EGP stored in dataset (set by updateBasicPriceDisplay)
    const rawEGP = basicPriceInput && basicPriceInput.dataset && basicPriceInput.dataset.rawEgp
        ? (parseFloat(basicPriceInput.dataset.rawEgp) || 0)
        : 0;

    if (discountedPrice > 0) {
        // Store the discounted price in a hidden field for backend
        // Note: You might want to ensure 'discountedPrice' is also converted back to EGP here if it was calculated from USD
        document.getElementById("unit_base_price").value = discountedPrice;
    } else {
        // ✅ Reset to original price IN EGP 
        if (rawEGP > 0) {
            document.getElementById("unit_base_price").value = rawEGP;
        } else {
            // Fallback: Scraping the UI value
            const basicPriceText = document.getElementById("basic_price").value;
            let originalPrice = parseFloat(basicPriceText.replace(/[^0-9.]/g, '')) || 0;

            // 🔥 CRITICAL FIX STARTS HERE 🔥
            // If the UI is displaying a converted currency (e.g. USD), 
            // we must divide by the rate to get back to EGP before sending to backend.
            const rate = getSelectedRate();
            if (rate && rate !== 1) {
                originalPrice = originalPrice / rate;
            }
            // 🔥 CRITICAL FIX ENDS HERE 🔥

            document.getElementById("unit_base_price").value = originalPrice;
        }
    }

    // Trigger recalculations
    sendInstallmentData();
}

// Update the basic price display function to account for discounts
function updateBasicPriceDisplay() {
  const basicPriceInput = document.getElementById("basic_price");
  const discountInput = document.getElementById("price_discount");
  const discountedPriceInput = document.getElementById("discounted_price");
  const discountedPriceGroup = document.getElementById("discounted-price-group");

  if (!basicPriceInput) return;

  // Raw base price in EGP from server
  const rawEGP = Number("{{ unit.interest_free_unit_price }}");
  if (isNaN(rawEGP)) return;

  // ✅ Store raw EGP for later discount calculations (DON'T parse display text)
  basicPriceInput.dataset.rawEgp = String(rawEGP);

  const rate = getSelectedRate();
  const currency = getCurrencySymbol();

  // Display is converted (UI only)
  const displayOriginal = Math.ceil((rawEGP * rate) / 1000) * 1000;
  basicPriceInput.value = `${displayOriginal.toLocaleString()} ${currency}`;

  // Keep backend base price always in EGP (discounted if exists)
  document.getElementById("unit_base_price").value = discountedPriceEGP > 0 ? discountedPriceEGP : rawEGP;

  // If a discount is already typed, refresh discounted display too
  const discountPct = discountInput ? (parseFloat(discountInput.value) || 0) : 0;
  if (discountPct > 0 && discountedPriceInput && discountedPriceGroup) {
    const displayDiscounted = Math.ceil((discountedPriceEGP * rate) / 1000) * 1000;
    discountedPriceInput.value = `${displayDiscounted.toLocaleString()} ${currency}`;
    discountedPriceGroup.style.display = "flex";
  }
}



function createInstallmentRow(index, date) {
    const row = document.createElement("tr");
    // console.log(`index = ${index}`)
    // console.log(`date = ${date}`)
    row.appendChild(createIndexCell(index));
    row.appendChild(createDateCell(date));
    row.appendChild(createInputCell());

    //row.appendChild(createNeededPercentageCell());
    //row.appendChild(createAmountCell());
    //row.appendChild(createGasPaymentsCell()); 
    
    // Apply border styles to each row cell
    row.querySelectorAll("td").forEach(cell => {
        cell.style.border = "1px solid #ccc"; // Adds a light grey border
        cell.style.padding = "5px"; // Adds padding for better visibility
    });
    
    // console.log(`row = ${row}`)
    return row;
}

function createNeededPercentageCell() {
    const cell = document.createElement("td");
    cell.className = "needed-percentage-cell"; // ✅ Class for styling if needed
    cell.textContent = "0%"; // ✅ Default value (update dynamically later)
    cell.style.border = "1px solid #ccc"; 
    cell.style.padding = "5px";
    return cell;
}

function createGasPaymentsCell() {
    const cell = document.createElement("td");
    cell.className = "needed-percentage-cell"; // ✅ Class for styling if needed
    cell.textContent = "0%"; // ✅ Default value (update dynamically later)
    cell.style.border = "1px solid #ccc"; 
    cell.style.padding = "5px";
    return cell;
}


function createAmountCell() {
    const cell = document.createElement("td");
    cell.className = "needed-percentage-cell"; // ✅ Class for styling if needed
    cell.textContent = "0%"; // ✅ Default value (update dynamically later)
    cell.style.border = "1px solid #ccc"; 
    cell.style.padding = "5px";
    return cell;
}


function createIndexCell(number) {
    const cell = document.createElement("td");
    cell.textContent = `PMT ${number}`;
    cell.style.fontWeight = "bold";
    return cell;
}

function createDateCell(date) {
    const cell = document.createElement("td");
    cell.textContent = formatDate(date);
    return cell;
}

// function formatDate(date) {
//     return date.getDate() + '/' + (date.getMonth() + 1) + '/' + date.getFullYear();
// }

// function formatDate(date) {
//     return date.toLocaleDateString('en-GB', {
//         day: '2-digit',
//         month: 'short',
//         year: 'numeric'
//     }).replace(/ /g, '/').toUpperCase();
// }

function formatDate(date) {
    return date.toLocaleDateString('en-US', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

function createInputCell() {
    const cell = document.createElement("td");
    const input = document.createElement("input");
    input.type = "number";
    input.step = "any";
    input.required = true;
    input.style.maxWidth = "35px";
    input.style.backgroundColor = "#eaeaea";

    if (typeof userCanEdit !== 'undefined' && userCanEdit === false) {
        input.disabled = true;
        input.style.backgroundColor = "transparent";

        document.getElementById("dp").disabled = true;
        document.getElementById("dp").style.backgroundColor = "transparent";

        if (hasMultipleDp){
            document.getElementById("dp_2").disabled = true;
            document.getElementById("dp_2").style.backgroundColor = "transparent";
        }
    }

    // try {
    //     let special_offer = document.getElementById("special_offers").value;
    //     console.log(special_offer);

    //     if (special_offer != "") {
    //         input.style.display = "none";

    //         // Disable reservation date inputs
    //         document.getElementById("contract_date").disabled = true;
    //         document.getElementById("contract_date_display").disabled = true;
    //         document.getElementById("contract_date_display").style.backgroundColor = "#eee";
    //         document.getElementById("contract_date_display").style.cursor = "not-allowed";

    //         // Disable tenor select
    //         document.getElementById("tenor_years").disabled = true;

    //         // Disable payment frequency dropdown click
    //         const freqDropdown = document.getElementById("base_payment_frequency");
    //         if (freqDropdown) {
    //             freqDropdown.style.pointerEvents = "none";
    //             freqDropdown.style.opacity = 0.6;
    //             freqDropdown.style.backgroundColor = "#eee";
    //             freqDropdown.style.cursor = "not-allowed";
    //         }
    //     }
    // } catch (error) {
    //     console.error("Error disabling fields:", error);
    // }


    


    const percent = document.createElement("span");
    percent.textContent = "%";

    cell.appendChild(input);
    cell.appendChild(percent);
    return cell;
}


function createGasPaymentsCell() {
    const cell = document.createElement("td");
    cell.className = "gas-payments-cell";
    cell.textContent = ""; // Placeholder value (will be updated)
    cell.style.border = "1px solid #ccc"; 
    return cell;
}


function createMaintenanceCell() {
    const cell = document.createElement("td");
    cell.className = "maintenance-cell";
    cell.textContent = ""; // Placeholder value (will be updated)
    cell.style.border = "1px solid #ccc"; 
    return cell;
}

function getAllOutputPercentages() {
    const percentages = [];
    document.querySelectorAll("#installmentTableBody tr").forEach(row => {
        const outputCell = row.querySelector(".output-cell");
        if (outputCell && outputCell.textContent.trim()) {
            const percentageValue = parseFloat(outputCell.textContent.replace("%", "").trim());
            if (!isNaN(percentageValue)) percentages.push(percentageValue);
        }
    });
    return percentages;
}

function getBaseDp(){
    try{
        return Number(document.getElementById("base_dp_init").innerHTML)
    }
    catch(e){
        return  0
    }
}

function sendInstallmentData() {

    const inputs = document.querySelectorAll("#installmentTableBody input");
    const dp = getDpValue() * 100;
    let dp_2 = 0
    const sum = getSumOfInputs();

    if (hasMultipleDp){
        dp_2 = getDpValue_2() * 100;
        if (sum + dp  + dp_2> 100) {
            alert("The total cannot exceed 100. Please adjust your inputs.");  
            return;
        }
    }
    else{
        if (sum + dp> 100) {
            alert("The total cannot exceed 100. Please adjust your inputs.");  
            return;
        }
    }
    
    const installmentList = Array.from(
        document.querySelectorAll("#installmentTableBody input"),
        input => input.value.trim() ? Number(input.value) / 100 : null
    ).filter(value => value !== null);

    const sequenceArray = Array.from(
        document.querySelectorAll("#installmentTableBody input"),
        (input, index) => input.value.trim() ? index + 1 : null
    ).filter(value => value !== null);

    let x  = 0
    if (hasMultipleDp){
        const dpInput = document.getElementById("dp");
        dpInput.style.color = 'black';
    
        
        const dpInput_2 = document.getElementById("dp_2");
        // dpInput_2.style.color = 'black';
    
        const baseDp = Number(document.getElementById("project_config_base_dp").value);
        const sendedDP = getDpValue();
        let sendedDP_2 = getDpValue_2();
        x  = 0
        if (sendedDP_2 <= (Number(getBaseDp()/2))){
            sendedDP_2 = Number(getBaseDp()) / 2
            x = getDpValue() + sendedDP_2
        }
        else{
            if (x == 0){
                x = getBaseDp()
            }
        }
        
        x = getDpValue() + getDpValue_2()
    
        if ((sendedDP + sendedDP_2) < baseDp) {
            dpInput.style.color = 'red';
            if (sendedDP_2  < (Number(getBaseDp()/2))){
                dpInput_2.style.color = 'red';
            }
            //dpInput.value =  getBaseDp()
    
            x = getBaseDp() / 100
        
        }

        if (sendedDP == 0 && sendedDP_2  >= (Number(getBaseDp()/2))) {

            // x = sendedDP_2 + (Number(getBaseDp()/2) / 100)
            x = (Number(dpInput_2.value)  / 100) + (Number(getBaseDp()/2) / 100)
            
        }
        else if(sendedDP < (Number(getBaseDp()/2)) && (sendedDP_2 /100)  >= (Number(getBaseDp()/2))){
            // console.log(`sendedDP = ${sendedDP}, sendedDP_2 = ${sendedDP_2}`)
            dpInput.style.color = 'red';
            
            x = (Number(dpInput_2.value)  / 100) + (Number(getBaseDp()/2) / 100)
        }

        // console.log(`x = ${x}, getBaseDp() = ${getBaseDp()}`)
        // if (x < (getBaseDp() /100) && x > ((getBaseDp()/2) /100)) {
        //     console.log(`getBaseDp() = ${getBaseDp()}`)
        //     return
        // }
    }
    else{
        const dpInput = document.getElementById("dp");
        dpInput.style.color = 'black';
        
        const baseDp = Number(document.getElementById("project_config_base_dp").value);
        const sendedDP = getDpValue();

        x  = 0
        x = getDpValue()

        if (sendedDP < baseDp) {
            dpInput.style.color = 'red';
            //dpInput.value =  getBaseDp()
            x = getBaseDp() / 100
        }
    }

    document.getElementById('currency_rate').value = selectedCurrencyRate
    const unitIdInput = document.getElementById("unit_code");
    const formData = new FormData();
    appendFormData(formData, "unit_base_price");
    appendFormData(formData, "project_config_static_npv");
    appendFormData(formData, "project_config_interest_rate");
    appendFormData(formData, "project_config_base_dp");
    appendFormData(formData, "project_config_base_tenor");
    appendFormData(formData, "project_config_max_tenor");
    appendFormData(formData, "contract_date", getContractDateInput());
    appendFormData(formData, "project_config_payment_frequency", getPaymentFrequency());
    appendFormData(formData, "project_config_default_scheme", getPaymentScheme());
    appendFormData(formData, "special_offers");
    appendFormData(formData, "project_constraints_max_discount");
    appendFormData(formData, "unit_maintenance_percent",document.getElementById("unit_maintenance_value").value);
    appendFormData(formData, "currency_rate");
    appendFormData(formData, "unit_contract_date");
    appendFormData(formData, "project_constraints_annual_min");
    appendFormData(formData, "project_constraints_first_year_min");
    try{
        let special_offer = document.getElementById("special_offers").value;
        const match = special_offer.match(/(\d+)\s*years/i);

        if (match) {
            years = parseInt(match[1], 10);
        }
        appendFormData(formData, "tenor_years",years);
        
    } catch(err){
        const dpInput = document.getElementById("dp");
        dpInput.style.display = ""
        appendFormData(formData, "tenor_years",document.getElementById("tenor_years").value);
    }
    appendFormData(formData, "project_config_id");
    appendFormData(formData, "delivery_date");
    appendFormData(formData, "dp", x);
    formData.append("unit_code", unitIdInput.value);

    formData.append("installment_data", JSON.stringify(installmentList));
    formData.append("indixes", JSON.stringify(sequenceArray));

    fetch(window.location.origin + submitDataUrl, {
        method: "POST",
        body: formData,
        headers: {
            "X-CSRFToken": csrfToken,
            "Accept": "application/json",
        }
    })
        .then(handleResponse)
        .then(updateResults)
        .catch(handleError);

        let exportButton = document.getElementById("exportPdfButton");
        exportButton.style.display = "block";  

        
        let exportExcelButton = document.getElementById("exportExcelButton");
        exportExcelButton.style.display = "block";  
   
}

function appendFormData(formData, field, value) {
    formData.append(field, value || document.getElementById(field)?.value);
}

function getContractDateInput() {
    const input = document.getElementById("contract_date").value;
    return input || new Date().toISOString().split('T')[0];
}

function getPaymentFrequency() {
    return document.getElementById("base_payment_frequency").textContent.trim();
}

function getPaymentScheme() {
    return document.getElementById("default_scheme").textContent.trim();
}

function getSpecialOffer() {
    return document.getElementById("special_offers").textContent.trim();
}

function getDpValue() {
    return Number(document.getElementById("dp").value) / 100;
}

function getDpValue_2() {
    return Number(document.getElementById("dp_2").value) / 100;
}


function handleResponse(response) {
    if (!response.ok) throw new Error(response.statusText);
    return response.json();
}

function handleError(error) {
    console.error("Error sending data:", error);
}

function updateResults(data) {

    if (data.dp1 !== undefined) window.global_plan_dp1 = data.dp1;
    if (data.dp2 !== undefined) window.global_plan_dp2 = data.dp2;

    generateInstallmentTable();

    if (data.new_base_dp !== undefined) {
        const baseDpInit = document.getElementById("base_dp_init");
        if (baseDpInit) baseDpInit.innerHTML = data.new_base_dp;
        global_base_dp = data.new_base_dp;
    }

    let rate = typeof selectedCurrencyRate !== 'undefined' ? selectedCurrencyRate : 1;
    const discountInput = document.getElementById("price_discount");
    const discountPercentage = discountInput ? parseFloat(discountInput.value) || 0 : 0;

    let finalPriceNum = 0;

    // If manual discount is present, we calculate from our manual base.
    // Note: If the backend logic also applies the additional discount to the price_with_interest,
    // and you want the Final Price to have BOTH, you multiply by the additional factor here.
    if (discountPercentage > 0 && discountedPriceEGP > 0) {
        const percentageChange = data.percentage_change || 0;
        const additionalDiscountPct = data.additional_discount_var || 0;
        const additionalFactor = (1 - additionalDiscountPct / 100);

        // Final Price = (Manual Discounted Base) * (Additional Discount Factor) * (1 + NPV Change)
        finalPriceNum = (discountedPriceEGP * additionalFactor) * (1 + percentageChange) * rate;
    } else {
        // Default: Price returned from backend already includes Additional Discount
        finalPriceNum = data.price_with_interest * rate;
    }

    const roundedPrice = Math.ceil(finalPriceNum / 1000) * 1000;

    let currencySelect = document.getElementById("currency");
    const finalPriceInput = document.getElementById("final_price");
    if (finalPriceInput) {
        finalPriceInput.value = roundedPrice.toLocaleString() + " " + currencySelect.value;
    }

    if (hasMultipleDp && data.dp1 !== undefined && data.dp2 !== undefined) {
        const dpInput1Val = (Number(document.getElementById("dp").value) || 0);
        const planTotalMin = (data.dp1 + data.dp2);
        const effectiveDp1 = Math.max(dpInput1Val, data.dp1);
        const dpInput2Val = (Number(document.getElementById("dp_2").value) || 0);

        document.getElementById("dp_needed_amount").innerHTML = ((effectiveDp1 / 100) * finalPriceNum).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });

        const neededForTotal = Math.max(0, planTotalMin - effectiveDp1);
        const finalNeededDP2 = Math.max(dpInput2Val, data.dp1 === 0 ? (data.dp2) : neededForTotal);

        document.getElementById("dp_needed_amount_2").innerHTML = ((finalNeededDP2 / 100) * finalPriceNum).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });

    } else {
        const dpInputVal = (Number(document.getElementById("dp").value) || 0);
        const effectivePerc = Math.max(dpInputVal, (data.dp1 || 0));
        document.getElementById("dp_needed_amount").innerHTML = ((effectivePerc / 100) * finalPriceNum).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }

    updateNPV(data);
    updateDeliveryDate(data.contract_date);
    updateInstallmentRows(data);

    if (updateCycleCounter < 5) {
        updateCycleCounter++;
        handleDpInput(true, finalPriceNum);
    } else {
        updateCycleCounter = 0;
    }

    const percentage_change_el = document.getElementById("percentage_change");
    const percentage = (Math.abs(data.percentage_change) * 100).toFixed(1);
    if (percentage_change_el) percentage_change_el.value = parseFloat(percentage) === 0.0 ? "-" : (data.percentage_change < 0 ? `(${percentage}%)` : `${percentage}%`);

    if (hasAdditionalDiscount){
        if (data.additional_discount_var) document.getElementById("additional_discount").value = `(${data.additional_discount_var}%)`
        else document.getElementById("additional_discount").value = `-`
    }

    if (hasMaintenance) {
        document.getElementById("maintenance_fees").value = data.maintenance == 0 ? "-" : `${data.maintenance.toLocaleString()} ${currencySelect.value}`;
    }
    if (hasGas) {
        document.getElementById("gas_fees").value = !data.gas_fees || data.gas_fees === 0 ? "-" : `${Number(data.gas_fees).toLocaleString()} ${currencySelect.value}`;
    }

    updateCumulativeColumn();
}



function colorInputInRow(index, color) {
    const rows = document.querySelectorAll("#installmentTableBody tr");

    // if (index == 1){
    //     const targetRow = rows[0];
    //     const input = targetRow.querySelector("input");

    //     if (input) input.style.color = color;
    // }

    // else if (index >= 0 && index < rows.length) {
    //     const targetRow = rows[index];
    //     const input = targetRow.querySelector("input");

    //     if (input) input.style.color = color;
    // }

    if (index == 0){
        const targetRow = rows[0];
        // console.log(`targetRow = ${targetRow}`)
        const input = targetRow.querySelector("input");

        if (input) input.style.color = color;
    }

    if (index == 1){
        const targetRow = rows[1];
        const input = targetRow.querySelector("input");

        if (input) input.style.color = color;
    }

    else if (index >= 0 && index < rows.length) {
        const targetRow = rows[index];
        const input = targetRow.querySelector("input");

        if (input) input.style.color = color;
    }
}

function updateNPV(data) {
    document.getElementById("calculated_pmt_percentages").innerText = JSON.stringify(data.calculated_pmt_percentages, null, 2);
    document.getElementById("new_npv").innerText = formatPercentage(data.new_npv * 100);
    document.getElementById("percentage_change").innerText = formatPercentageChange(data.percentage_change * 100);
}

function formatPercentage(value) {
     return (Math.floor(value * 100 + 0.00001) / 100).toFixed(1) + "%";
}

function formatPercentageChange(value) {
    const absValue = Math.abs(value).toFixed(1);
    return value < 0 ? `(${absValue}%)` : `${absValue}%`;
}

function updateDeliveryDate(contractDate) {
    document.getElementById("dp_date").innerHTML = formatDate(new Date(contractDate));

    if (hasMultipleDp){
        
        const contractDateObj = new Date(contractDate);
        const nextMonthDate = new Date(contractDateObj);
        nextMonthDate.setMonth(contractDateObj.getMonth() + periodBetweenDPs);
        
        document.getElementById("dp_date_2").innerHTML = formatDate(nextMonthDate);
            
    }

}

function updatePriceWithInterest(data) {
    document.getElementById("price_with_interest").innerText =
        data.price_with_interest.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}



function updateInstallmentRows(data) {
    let rate = typeof selectedCurrencyRate !== 'undefined' ? selectedCurrencyRate : 1;
    let priceWithInterest = data.price_with_interest * rate;
    final_price = priceWithInterest;

    const rows = document.querySelectorAll("#installmentTableBody tr");
    const firstRow = document.getElementById("first-row");
    const secondRow = document.getElementById("second-row");

    // Visibility logic based on your test cases
    const dp1_plan = window.global_plan_dp1 || 0;
    const dp2_plan = window.global_plan_dp2 || 0;

    if (dp1_plan === 0 && dp2_plan === 0) {
        if (firstRow) firstRow.style.display = "none";
        if (secondRow) secondRow.style.display = "none";
    } else if (dp2_plan === 0) {
        if (firstRow) firstRow.style.display = "table-row";
        if (secondRow) secondRow.style.display = "none";
    } else {
        if (firstRow) firstRow.style.display = "table-row";
        if (secondRow) secondRow.style.display = "table-row";
    }

    // Row Updates for the generated PMT table
    rows.forEach((row, index) => {
        const valueCell = getOrCreateCell(row, "value-cell");
        const outputCell = getOrCreateCell(row, "output-cell");
        const cumulativeCell = getOrCreateCell(row, "cumulative-cell");
        const rowInput = row.querySelector("input");
        const neededPercentage = data.calculated_pmt_percentages[index + 1] * 100;

        let maintenanceCell = hasMaintenance ? getOrCreateCell(row, "maintenance-cell") : null;
        let gasPaymentCell = hasGas ? getOrCreateCell(row, "gas-payments-cell") : null;

        const percentage = data.calculated_pmt_percentages[index + 1] * 100;
        const gasPayment = hasGas ? (data.gas_payments[index] || "") : "";
        const maintenance = hasMaintenance ? (data.maintenance_payments[index + 1] || "") : "";

        if (percentage >= 0) {
            realPercentage[index] = Number(percentage.toFixed(5));
            outputCell.textContent = formatPercentage(percentage);
            valueCell.textContent = (percentage * priceWithInterest / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });

            // --- PMT INPUT COLORING ---
            if (rowInput) {
                const userVal = parseFloat(rowInput.value);
                if (!isNaN(userVal) && userVal < Number(neededPercentage.toFixed(1)) && rowInput.value !== "") {
                    rowInput.style.color = "red";
                } else {
                    rowInput.style.color = "black";
                }
            }

            
        }

        if (hasGas && gasPaymentCell) gasPaymentCell.textContent = gasPayment.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
        if (hasMaintenance && maintenanceCell) maintenanceCell.textContent = maintenance.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });

        // Handle 100% DP Edge Case
        if (document.getElementById("dp").value == 100) {
            valueCell.innerHTML = ""; outputCell.innerHTML = ""; cumulativeCell.innerHTML = "";
            if(row.childNodes[2]) row.childNodes[2].style.visibility = "hidden";
            if(row.childNodes[5]) row.childNodes[5].style.visibility = "hidden";
        } else {
            if(row.childNodes[5]) row.childNodes[5].style.visibility = "visible";
            if(row.childNodes[2]) row.childNodes[2].style.visibility = "visible";
        }

        // Delivery Highlighting Logic
        if (index + 1 < data.delivery_payment_index) {
            row.style.fontWeight = "normal"; row.style.backgroundColor = "white"; row.style.display = "table-row";
        } else if (index + 1 === data.delivery_payment_index) {
            row.style.fontWeight = "bold"; row.style.backgroundColor = "#d0d0d0"; row.style.display = "table-row";
        } else {
            row.style.display = (document.getElementById("dp").value == 100) ? "none" : "table-row";
        }
    });
}


// Add a new function to calculate and display the Cumulative column
function updateCumulativeColumn() {

    if (hasMultipleDp){
        const rows = document.querySelectorAll("#installmentTableBody tr");
        let dp = parseFloat(document.getElementById("dp_needed_percentage_cumulative").innerHTML.replace("%", "").trim()) || 0;
        let dp_2 = parseFloat(document.getElementById("dp_needed_percentage_cumulative_2").innerHTML.replace("%", "").trim()) || 0;
        document.getElementById("dp_needed_percentage_cumulative").innerHTML = `${dp}%`;
        document.getElementById("dp_needed_percentage_cumulative_2").innerHTML = `${dp_2}%`;
        // console.log(`dp = ${dp}, dp_2 = ${dp_2}`)
        let cumulative = 0
        if ((dp == getBaseDp() / 2) && (dp_2 == getBaseDp())){
            cumulative = dp_2
        }
        else{
            cumulative = dp + dp_2;
        }

        let hideRowsFromIndex = null;

        rows.forEach((row, index) => {
            dp = parseFloat(document.getElementById("dp_needed_percentage_cumulative").innerHTML.replace("%", "").trim()) || 0;
            dp_2 = parseFloat(document.getElementById("dp_needed_percentage_cumulative_2").innerHTML.replace("%", "").trim()) || 0;

            const outputCell = getOrCreateCell(row, "output-cell");
            const cumulativeCell = getOrCreateCell(row, "cumulative-cell");

            const percentageText = outputCell.textContent.replace("%", "").trim();
            const percentage = parseFloat(percentageText);
            const percentageTwo = realPercentage[index];

            if (!isNaN(percentage)) {
                if (index === 0) {
                    if (dp < Number(getBaseDp()) / 2) {
                        document.getElementById("dp_needed_percentage_cumulative").innerHTML = formatPercentage(Number(getBaseDp() / 2));
                    }


                    if ((dp == getBaseDp() / 2) && (dp_2 == getBaseDp())){
                        cumulative = dp_2 + percentage
                    }
                    else{
                        cumulative = dp + dp_2 + percentage;
                    }
            

                    if (
                        ((dp <= (Number(getBaseDp()) / 2)) && (dp_2 <= (Number(getBaseDp()) / 2))) ||
                        ((dp <= (Number(getBaseDp()) / 2)) && (dp_2 > (Number(getBaseDp()) / 2)) && (dp + dp_2 < getBaseDp())) ||
                        ((dp > (Number(getBaseDp()) / 2)) && (dp_2 <= (Number(getBaseDp()) / 2)) && (dp + dp_2 < getBaseDp()))
                    ) {
                        cumulative = getBaseDp() + parseFloat(realPercentage[index].toFixed(5));
                    }

                } else {
                    cumulative += parseFloat(realPercentage[index].toFixed(5));
                }

                if (cumulative > 100){
                    cumulative = 100;
                }
                cumulativeCell.textContent = formatPercentage(cumulative);

                // ✅ If cumulative hits exactly 100%, mark this index
                if (hideRowsFromIndex === null && Math.round(cumulative * 10) / 10 >= 100.0) {
                    hideRowsFromIndex = index + 1; // hide all rows after this
                }

            } else {
                cumulativeCell.textContent = "0.0%";
            }
        });

        // ✅ Hide rows after the threshold index
        if (hideRowsFromIndex !== null) {
            for (let i = hideRowsFromIndex; i < rows.length; i++) {
                rows[i].style.display = "none";
            }
        }
    }
    else{
        const rows = document.querySelectorAll("#installmentTableBody tr");
        let dp = Number(parseFloat(document.getElementById("dp_needed_percentage_cumulative").innerHTML.replace("%", "").trim())) || 0;
        document.getElementById("dp_needed_percentage_cumulative").innerHTML = `${dp.toFixed(1)}%`;
        dp = dp.toFixed(1)
        // console.log(`dp = ${dp}`) 
        
        let cumulative = dp;

        let hideRowsFromIndex = null;

        rows.forEach((row, index) => {
            dp = parseFloat(document.getElementById("dp_needed_percentage_cumulative").innerHTML.replace("%", "").trim()) || 0;

            const outputCell = getOrCreateCell(row, "output-cell");
            const cumulativeCell = getOrCreateCell(row, "cumulative-cell");

            const percentageText = outputCell.textContent.replace("%", "").trim();
            const percentage = parseFloat(percentageText);
            const percentageTwo = realPercentage[index];

            if (!isNaN(percentage)) {
                if (index === 0) {
                    // if (dp < Number(getBaseDp())) {
                    //     document.getElementById("dp_needed_percentage_cumulative").innerHTML = formatPercentage(Number(getBaseDp()));
                    // }

                    cumulative = dp + percentage;

                    // if (dp < Number(getBaseDp())) {
                    //     cumulative = getBaseDp() + parseFloat(realPercentage[index].toFixed(5));
                    // }

                } else {
                    // console.log(index)
                    cumulative += parseFloat(realPercentage[index].toFixed(5));
                }

                if (cumulative > 100){
                    cumulative = 100;
                }
                cumulativeCell.textContent = formatPercentage(cumulative);

                // ✅ If cumulative hits exactly 100%, mark this index
                if (hideRowsFromIndex === null && Math.round(cumulative * 10) / 10 >= 100.0) {
                    hideRowsFromIndex = index + 1; // hide all rows after this
                }

            } else {
                cumulativeCell.textContent = "0.0%";
            }
        });

        // ✅ Hide rows after the threshold index
        if (hideRowsFromIndex !== null) {
            for (let i = hideRowsFromIndex; i < rows.length; i++) {
                rows[i].style.display = "none";
            }
        }
        
    }
    
}



function getOrCreateCell(row, className) {
    let cell = row.querySelector(`.${className}`);
    if (!cell) {
        cell = document.createElement("td");
        cell.className = className;
        row.appendChild(cell);
    }

    cell.style.border = "1px solid #ccc"; 
    cell.style.padding = "5px";

    return cell;
}

function handleEnterKey(event) {
    if (event.key === "Enter") {
        event.preventDefault();
        sendInstallmentData();
    }
}

function handleDropdownSelection(event) {
    const selectedOption = event.target.textContent.trim();
    const dropdown = event.target.closest(".custom-dropdown");
    const selectedOptionElement = dropdown.querySelector(".selected-option");

    selectedOptionElement.textContent = selectedOption;
    selectedOptionElement.id = "base_payment_frequency";

    dropdown.classList.remove("open");

    let hiddenInput = dropdown.querySelector("input[type='hidden']");
    if (!hiddenInput) {
        hiddenInput = document.createElement("input");
        hiddenInput.type = "hidden";
        hiddenInput.name = "payment_frequency";
        dropdown.appendChild(hiddenInput);
    }
    hiddenInput.value = event.target.dataset.value;

    // ✅ ONLY clear DP inputs when scheme changes, not on every calculation
    // document.getElementById("dp").value = "";
    // if (hasMultipleDp) {
    //     document.getElementById("dp_2").value = "";
    // }
    
    // ✅ Use stabilization for scheme changes
    stabilizeSchemeCalculation();
}

function handleDropdownSelection2(event) {
    const selectedOption = event.target.textContent.trim();
    const dropdown = event.target.closest(".custom-dropdown-2");
    const selectedOptionElement = dropdown.querySelector(".selected-option-2");

    // Convert "FlatBackLoaded" to "Flat Back Loaded"
    const spacedOption = selectedOption.replace(/([a-z])([A-Z])/g, '$1 $2');

    selectedOptionElement.textContent = spacedOption;
    selectedOptionElement.id = "default_scheme";

    dropdown.classList.remove("open");

    let hiddenInput = dropdown.querySelector("input[type='hidden']");
    if (!hiddenInput) {
        hiddenInput = document.createElement("input");
        hiddenInput.type = "hidden";
        hiddenInput.name = "payment_scheme";
        dropdown.appendChild(hiddenInput);
    }
    hiddenInput.value = event.target.dataset.value;

    // Clear the DP inputs so they don't block the new scheme's defaults
    // document.getElementById("dp").value = "";
    // if (hasMultipleDp) {
    //     document.getElementById("dp_2").value = "";
    // }

    // ✅ Use stabilization for scheme changes
    stabilizeSchemeCalculation();
}


function closeDropdownOnClickOutside(event) {
    document.querySelectorAll(".custom-dropdown").forEach(dropdown => {
        if (!dropdown.contains(event.target)) {
            dropdown.classList.remove("open");
        }
    });
}

function closeDropdownOnClickOutside2(event) {
    document.querySelectorAll(".custom-dropdown-2").forEach(dropdown => {
        if (!dropdown.contains(event.target)) {
            dropdown.classList.remove("open");
        }
    });
}

function toggleDropdown() {
    const dropdown = document.querySelector(".custom-dropdown");
    dropdown.classList.toggle("open");
}

function toggleDropdown2() {
    const dropdown = document.querySelector(".custom-dropdown-2");
    dropdown.classList.toggle("open");
}

function getSumOfInputs() {
    const inputs = document.querySelectorAll("#installmentTableBody input");
    let sum = 0;

    inputs.forEach(input => {
        const inputValue = parseFloat(input.value.trim());
        if (!isNaN(inputValue)) {
            sum += inputValue;
        }
    });

    return sum;
}

