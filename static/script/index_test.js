
document.addEventListener("DOMContentLoaded", () => {
    initializeEventListeners();
    setupInputStyling();

    try{
        if (document.getElementById("dp_needed_percentage").value < getBaseDp()){
            document.getElementById("dp_needed_percentage_cumulative").innerHTML = formatPercentageChange(getBaseDp());
    
        }
        else{
            document.getElementById("dp_needed_percentage_cumulative").innerHTML = document.getElementById("dp_needed_percentage").value 
        }
    }
    catch{

    }


    //document.getElementById("dp").value = ""; 
    document.getElementById("tenor_years").value = document.getElementById("project_config_base_tenor")?.value;
    document.getElementById("dp_date").innerHTML = formatDate(new Date());
    //dates[0] = new Date()

    document.getElementById("dp").value = "";

    
    document.getElementById("dp_needed_percentage").innerHTML = formatPercentageChange(getBaseDp());
    dp_temp = Number(document.getElementById("dp_needed_percentage").innerHTML.replace("%", ''))
    document.getElementById("dp_needed_percentage_cumulative").innerHTML = formatPercentageChange(getBaseDp());
    const dpNeededPercentageContainer = document.getElementById("dp_needed_percentage_container");
    dpNeededPercentageContainer.style.border = "1px solid #ccc";
    
    const dpNeededAmountContainer = document.getElementById("dp_needed_amount_container");
    dpNeededAmountContainer.style.border = "1px solid #ccc";

    let x  =document.getElementById("dp_needed_percentage_cumulative_container")
    x.style.border = "1px solid #ccc";

    // ✅ Automatically generate table on page load if base_tenor_years is available
    const tenorYearsInput = document.getElementById("tenor_years");
    const baseTenorYears = parseInt(tenorYearsInput.value) || parseInt(document.getElementById("project_config_base_tenor")?.value) || 0;

    if (baseTenorYears > 0) {
        tenorYearsInput.value = baseTenorYears; // ✅ Set value if not already set
        generateInstallmentTable(); // ✅ Generate the table with the correct number of rows
        applyBordersToTable();
        sendInstallmentData(); // ✅ Apply borders to all cells after generating rows
    }

    const finalPrice = document.getElementById("final_price")
    finalPrice.value = ""



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
});




function initializeEventListeners() {

    

    try{
        document.querySelectorAll(".custom-dropdown .dropdown-options li").forEach(option => {
            option.addEventListener("click", handleDropdownSelection);
        });
    
        document.addEventListener("click", closeDropdownOnClickOutside);
    
        // Initialize the ID for the currently selected option
        const selectedOption = document.querySelector(".custom-dropdown .selected-option");
        
    
        const dropdown = selectedOption.closest(".custom-dropdown");
        const selectedValue = Array.from(dropdown.querySelectorAll(".dropdown-options li"))
            .find(li => li.classList.contains("selected"))?.textContent.trim();
        
        if (selectedValue) {
            selectedOption.textContent = selectedValue;
            selectedOption.id = "base_payment_frequency";
        }
        
        
    
        const elements = {
            installmentTableBody: document.getElementById("installmentTableBody"),
            contractDate: document.getElementById("contract_date"),
            dpInput: document.getElementById("dp"),
            tenor_years : document.getElementById("tenor_years")
        };
    
        elements.installmentTableBody.addEventListener("input", () => {
            const sum = getSumOfInputs();
            const dp = getDpValue() *100
            const inputs = document.querySelectorAll("#installmentTableBody input");
    
            if (sum + dp >= 100) {
                inputs.forEach(input => {
                    const inputValue = parseFloat(input.value.trim());
                    if (!isNaN(inputValue) && sum - inputValue < 100) {
                        input.disabled = false; // Allow editing only if it doesn't exceed 100
                    } else {
                        input.disabled = true; // Disable further input
                    }
                });
            } else {
                inputs.forEach(input => {
                    input.disabled = false; // Enable all inputs if the sum is below 100
                });
            }
    
            sendInstallmentData();
        });
    
        elements.contractDate.addEventListener("input", () => {
            generateInstallmentTable();
            applyBordersToTable();
            sendInstallmentData();
        });

        elements.tenor_years.addEventListener("input", () => {
            generateInstallmentTable();
            applyBordersToTable();
            sendInstallmentData();
        });
    
    
        elements.dpInput.addEventListener("input", handleDpInput);
    
        document.addEventListener("keydown", handleEnterKey);

        
    }
    catch{

    }

    
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

function handleDpInput() {
    const dpInput = document.getElementById("dp");

    const dpNeededPercentage = document.getElementById("dp_needed_percentage");
    
    const dpNeededPercentageContainer = document.getElementById("dp_needed_percentage_container");
    dpNeededPercentageContainer.style.border = "1px solid #ccc";
    
    const dpNeededAmountContainer = document.getElementById("dp_needed_amount_container");
    dpNeededAmountContainer.style.border = "1px solid #ccc";
    
    const baseDp = Number(document.getElementById("project_config_base_dp").value) * 100;
    const currentValue = Number(dpInput.value) || 0;

    document.getElementById("dp_needed_percentage_cumulative").innerHTML = currentValue

    dpNeededPercentage.innerHTML = currentValue > baseDp
        ? `${currentValue.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`
        : `${baseDp.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;

    sendInstallmentData();

    


    dp_temp = Number(dpNeededPercentage.innerHTML.replace("%", ''))
    
}

function generateInstallmentTable() {

    
            
    // if (is_not_native_company == "True"){
    //     let holdButton = document.getElementById("hold-button")
    //     if (holdButton) holdButton.style.display = "block";
    // }
    // else{
    //     let holdButton = document.getElementById("hold-button")
    //     if (holdButton) holdButton.style.display = "none";
    // }


    const tableBody = document.getElementById("installmentTableBody");
    let tableContainer = document.getElementById("installmentTableContainer");
    tableBody.innerHTML = "";

    const tenorYears = document.getElementById("tenor_years").value;
    const selectedOption = document.querySelector(".custom-dropdown .selected-option");
    const paymentFrequency = selectedOption?.textContent.trim().toLowerCase() || "";
    

    const { monthsToAdd, multiplier } = getFrequencyConfig(paymentFrequency);

    if (!tenorYears || tenorYears <= 0) {
        tableContainer.style.display = "none";  // Hide table
        return;
    }

    tableContainer.style.display = "block";  // Show table
    

    let currentDate = getContractDate();
    currentDate.setMonth(currentDate.getMonth() + monthsToAdd);
    dates = []

    for (let i = 0; i < tenorYears * multiplier; i++) {

        if(dates.length > ((tenorYears * multiplier) +1)){}
        else{
            dates.push(new Date(currentDate));
        }


        const row = createInstallmentRow(i + 1, currentDate);
        tableBody.appendChild(row);
        currentDate.setMonth(currentDate.getMonth() + monthsToAdd);
    }

  

    document.getElementById("installmentTableContainer").style.display = "block";
    applyBordersToTable();
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
    return contractDateInput ? new Date(contractDateInput) : new Date();
}

function createInstallmentRow(index, date) {
    const row = document.createElement("tr");
    row.appendChild(createIndexCell(index));
    row.appendChild(createDateCell(date));
    row.appendChild(createInputCell());
    //row.appendChild(createNeededPercentageCell());
    //row.appendChild(createAmountCell());

    // Apply border styles to each row cell
    row.querySelectorAll("td").forEach(cell => {
        cell.style.border = "1px solid #ccc"; // Adds a light grey border
        cell.style.padding = "5px"; // Adds padding for better visibility
    });

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

function formatDate(date) {
    return date.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    }).replace(/ /g, '/').toUpperCase();
}

function createInputCell() {
    const cell = document.createElement("td");
    const input = document.createElement("input");
    input.type = "number";
    input.step = "0";
    input.required = true;
    input.style.maxWidth = "35px";
    input.style.backgroundColor = "#eaeaea";


    const percent = document.createElement("span");
    percent.textContent = "%";

    cell.appendChild(input);
    cell.appendChild(percent);
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
    return Number(document.getElementById("base_dp_init").innerHTML)
}

function sendInstallmentData() {

    const inputs = document.querySelectorAll("#installmentTableBody input");
    const dp = getDpValue() * 100;
    const sum = getSumOfInputs();

    if (sum + dp > 100) {
        alert("The total cannot exceed 100. Please adjust your inputs.");  
        return;
    }


    const installmentList = Array.from(
        document.querySelectorAll("#installmentTableBody input"),
        input => input.value.trim() ? Number(input.value) / 100 : null
    ).filter(value => value !== null);

    const sequenceArray = Array.from(
        document.querySelectorAll("#installmentTableBody input"),
        (input, index) => input.value.trim() ? index + 1 : null
    ).filter(value => value !== null);

    const dpInput = document.getElementById("dp");
    dpInput.style.color = 'black';

    const baseDp = Number(document.getElementById("project_config_base_dp").value);
    const sendedDP = getDpValue();
    let x = getDpValue()
    if (sendedDP < baseDp) {
        dpInput.style.color = 'red';
        //dpInput.value =  getBaseDp()
        x = getBaseDp() / 100
        // let exportButton = document.getElementById("exportPdfButton");
        // exportButton.style.display = "none";  

        // let exportExcelButton = document.getElementById("exportExcelButton");
        // exportExcelButton.style.display = "none";  
    
    }


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
    appendFormData(formData, "project_constraints_max_discount");
    appendFormData(formData, "unit_maintenance_percent",document.getElementById("unit_maintenance_value").value);
    appendFormData(formData, "unit_contract_date");
    appendFormData(formData, "project_constraints_annual_min");
    appendFormData(formData, "project_constraints_first_year_min");
    appendFormData(formData, "tenor_years");
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

function getDpValue() {
    return Number(document.getElementById("dp").value) / 100;
}

function handleResponse(response) {
    if (!response.ok) throw new Error(response.statusText);
    return response.json();
}

function handleError(error) {
    console.error("Error sending data:", error);
}

function updateResults(data) {
    try {
        const priceWithInterest = data.price_with_interest;
        if (priceWithInterest == undefined) {
            alert(data.tenor_years_error)
            throw new Error("price_with_interest is undefined");
        }
    } catch (error) {

        console.error("An error occurred:", error.message); // Output: An error occurred: price_with_interest is undefined
        throw error;
    }
    updateNPV(data);
    updateDeliveryDate(data.contract_date);
    updatePriceWithInterest(data);
    updateInstallmentRows(data);

    contract_date = data.contract_date

    const installmentListTest = Array.from(
        document.querySelectorAll("#installmentTableBody input"),
        input => {
            if (!input.value.trim()) {
                input.style.backgroundColor = "#eaeaea"; // Color empty inputs green
                return "";
            } else {
                input.style.backgroundColor = "white"; // Reset background for non-empty inputs
                return Number(input.value) / 100;
            }
        }
    );

    const neededPercentages = getAllOutputPercentages();
    let error = 0;

    document.querySelectorAll("#installmentTableBody input").forEach(input => {
        input.style.color = "black";
    });


    for (let i = 0; i < neededPercentages.length; i++) {
        if (installmentListTest[i] === "") continue;


        if (installmentListTest[i] < (neededPercentages[i] / 100)) {
            error = i === 0 ? i + 1 : i;
            if (error) colorInputInRow(error, "red");
            // let exportButton = document.getElementById("exportPdfButton");
            // exportButton.style.display = "none";  // ✅ Show the Export PDF button
        }
    }


    const finalPrice = document.getElementById("final_price")
    finalPrice.value = data.price_with_interest.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })


    
}

function colorInputInRow(index, color) {
    const rows = document.querySelectorAll("#installmentTableBody tr");

    if (index == 1){
        const targetRow = rows[0];
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
    return (Math.round(value * 100) / 100).toFixed(1) + "%";
}

function formatPercentageChange(value) {
    const absValue = Math.abs(value).toFixed(1);
    return value < 0 ? `(${absValue}%)` : `${absValue}%`;
}

function updateDeliveryDate(contractDate) {
    document.getElementById("dp_date").innerHTML = formatDate(new Date(contractDate));
    
}

function updatePriceWithInterest(data) {
    document.getElementById("price_with_interest").innerText =
        data.price_with_interest.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}




function updateInstallmentRows(data) {
    const priceWithInterest = data.price_with_interest;
    final_price = priceWithInterest
    const rows = document.querySelectorAll("#installmentTableBody tr");

    const baseDp = Number(document.getElementById("project_config_base_dp").value);
    const sendedDP = getDpValue();
    let x = getDpValue()
    if (sendedDP < baseDp) {
        //dpInput.value =  getBaseDp()
        x = getBaseDp() / 100
        // let exportButton = document.getElementById("exportPdfButton");
        // exportButton.style.display = "none";  

        // let exportExcelButton = document.getElementById("exportExcelButton");
        // exportExcelButton.style.display = "none";  

        document.getElementById("dp_needed_amount").innerHTML =
        (x * priceWithInterest).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    
    }

    else {
        document.getElementById("dp_needed_amount").innerHTML =
        (getDpValue() * priceWithInterest).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }

    const inputs = document.querySelectorAll("#installmentTableBody input");

    let hideRows = false; // Flag to track when to start hiding rows


    rows.forEach((row, index) => {
        const valueCell = getOrCreateCell(row, "value-cell");
        const outputCell = getOrCreateCell(row, "output-cell");
        const cumulativeCell = getOrCreateCell(row, "cumulative-cell");
        const percentage = data.calculated_pmt_percentages[index + 1] * 100;
        if (percentage >= 0){
            realPercentage[index] = percentage
            outputCell.textContent = formatPercentage(percentage);
            valueCell.textContent = (percentage * priceWithInterest / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });            }
            
            else{
            outputCell.textContent = 0.0
            valueCell.textContent = 0.0
        }

        

        // if (document.getElementById("dp").value == 100){
        //     document.getElementById("first-row").style.fontWeight = "bold"
        //     document.getElementById("first-row").style.backgroundColor = "#d0d0d0";

        //     if (index + 1 === data.delivery_payment_index) {
        //         row.style.fontWeight = "normal";
        //         row.style.backgroundColor = "rgb(255 255 255)";
        //     }
        //     row.style.display = "none";
        // }
        // else{

        //     document.getElementById("first-row").style.fontWeight = "normal"
        //     document.getElementById("first-row").style.backgroundColor = "rgb(255 255 255)";
        //     if (index + 1 === data.delivery_payment_index) {
        //         row.style.fontWeight = "bold";
        //         row.style.backgroundColor = "#d0d0d0";
        //     }
        //     row.style.display = "table-row";
        // }

        // if (document.getElementById("dp").value == 100){
        //     valueCell.innerHTML = ""
        //     outputCell.innerHTML = ""
        //     cumulativeCell.innerHTML = ""
            
        //     if (index  === data.delivery_payment_index) {
        //         hideRows = true;
        //     }



        // }
        // else{
        //     row.childNodes[2].style.display = "block"
        // }

        // Hide rows starting from the delivery payment index
        // if (hideRows) {
        //     row.innerHTML = "";
        //     console.log(1)
        // } else {
        //     row.style.display = "table-row"; // Ensure rows before the condition are visible
        // }

        if (document.getElementById("dp").value == 100){

            valueCell.innerHTML = ""
            outputCell.innerHTML = ""
            cumulativeCell.innerHTML = ""
            row.childNodes[2].style.visibility  = "hidden"
            // row.childNodes[2].style.border  = "1px solid #ccc";
            // row.childNodes[3].style.border  = "1px solid #ccc";
            
            row.childNodes[5].style.visibility  = "hidden"
        }
        else{
            // row.childNodes[2].style.display = "block"
            row.childNodes[5].style.visibility  = "visible"
            row.childNodes[2].style.visibility  = "visible"
        }

        // 🧠 Here's the logic you asked:
        if (index + 1 < data.delivery_payment_index) {
            row.style.fontWeight = "normal";
            row.style.backgroundColor = "white";
            row.style.display = "table-row"; // show normally
        } else if (index + 1 === data.delivery_payment_index) {
            row.style.fontWeight = "bold";
            row.style.backgroundColor = "#d0d0d0";
            row.style.display = "table-row"; // keep the delivery row visible
        } else {
            if (document.getElementById("dp").value == 100){
                
                row.style.display = "none"; // 🚫 Hide rows after the delivery_payment_index
            }
            else{
                row.style.display = "table-row"; // 🚫 Hide rows after the delivery_payment_index
            }
        }
    });

    updateCumulativeColumn(); // ✅ Update the Cumulative column after rows are updated

}


// Add a new function to calculate and display the Cumulative column
function updateCumulativeColumn() {
    const rows = document.querySelectorAll("#installmentTableBody tr");
    let dp = parseFloat(document.getElementById("dp_needed_percentage_cumulative").innerHTML.replace("%", "").trim()) || 0;
    document.getElementById("dp_needed_percentage_cumulative").innerHTML = `${dp}%`
    let cumulative = dp;

    rows.forEach((row, index) => {
        dp = parseFloat(document.getElementById("dp_needed_percentage_cumulative").innerHTML.replace("%", "").trim()) || 0;

        const outputCell = getOrCreateCell(row, "output-cell");
        const cumulativeCell = getOrCreateCell(row, "cumulative-cell");

        const percentageText = outputCell.textContent.replace("%", "").trim();
        const percentage = parseFloat(percentageText);
        const percentageTwo = realPercentage[index]

        if (document.getElementById("dp").value == 100){

            cumulativeCell.innerHTML = ""

            
            
        }



        if (!isNaN(percentage)) {
            if (index === 0) {
                if (dp < getBaseDp()){
                    document.getElementById("dp_needed_percentage_cumulative").innerHTML = formatPercentage(getBaseDp())
                }
               // cumulative = dp + parseFloat(realPercentage[index + 1].toFixed(1));
                cumulative = dp + percentage
                if (dp <= getBaseDp()){
                    cumulative = getBaseDp() + parseFloat(realPercentage[index].toFixed(5));
                }
                
            } else {

                cumulative = cumulative + parseFloat(realPercentage[index].toFixed(5));
                //cumulative += percentage
            }

            if (document.getElementById("dp").value == 100){

                valueCell.innerHTML = ""
                outputCell.innerHTML = ""
                cumulativeCell.innerHTML = ""
    
                
                
            }else{

                cumulativeCell.textContent = formatPercentage(cumulative);
            }
        } else {
            cumulativeCell.textContent = "";
        }
    });
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

    // ✅ Re-generate table and update values like on DOMContentLoaded
    generateInstallmentTable();
    applyBordersToTable();
    sendInstallmentData();
}

function closeDropdownOnClickOutside(event) {
    document.querySelectorAll(".custom-dropdown").forEach(dropdown => {
        if (!dropdown.contains(event.target)) {
            dropdown.classList.remove("open");
        }
    });
}

function toggleDropdown() {
    const dropdown = document.querySelector(".custom-dropdown");
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





try{
// Namespace to avoid conflicts
const App = {
    // Export PDF functionality
    exportPdf: function () {
        document.getElementById("exportPdfButton").addEventListener("click", function () {
            let tableContainer = document.getElementById("installmentTableContainer");

            if (tableContainer.style.display === "none") {
                alert("No table to export!");
                return;
            }

            const { jsPDF } = window.jspdf;
            const doc = new jsPDF({
                orientation: "landscape",
                unit: "mm",
                format: "a4"
            });

            doc.setFont("times", "normal");
            doc.setFontSize(12);

            // Gather Additional Info
            const currentDate = new Date().toLocaleString("en-GB", {
                day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"
            });
            const unitCode = document.getElementById("unit_code")?.value || "N/A";

            // Add Report Details
            doc.text(`Exported By: ${userName}`, 14, 15);
            doc.text(`Exported By: ${fullName}`, 14, 22);
            doc.text(`Date & Time: ${currentDate}`, 14, 29);
            doc.text(`Company Name: ${companyName}`, 14, 36);
            doc.text(`Unit Code: ${unitCode}`, 14, 43);


            doc.line(14, 46, 280, 46); // Separator line before the table

            // Extract Table Data
            const table = document.querySelector(".installment-table");
            const tableData = [];
            const headers = ["", "DATE", "INSTALLMENT", "AMOUNT"]; // Final headers
            tableData.push(headers);

            let totalAmount = 0;

            table.querySelectorAll("tbody tr").forEach(row => {
                const cells = row.querySelectorAll("td, input");
                const rowData = [];

                if (cells.length >= 5) {
                    rowData.push(cells[0].innerText.trim() || "");  // First column
                    rowData.push(cells[1].innerText.trim() || "");  // Date
                    rowData.push(cells[4].innerText.trim() || "");  // Installment
                    rowData.push(cells[5].innerText.trim() || "");  // Amount
                    let amount = parseFloat(cells[4].innerText.replace(/[^\d.]/g, "")) || 0;
                    totalAmount += amount;
                }

                tableData.push(rowData);
            });

            // Add Total Row
            const totalRow = ["",  "Total Price", totalAmount.toLocaleString() + " EGP"];
            tableData.push(totalRow);

            // Generate PDF Table
            doc.autoTable({
                head: [headers],
                body: tableData.slice(1), // Exclude headers from body
                startY: 45,
                styles: {
                    font: "times",
                    fontSize: 10,
                    cellPadding: 4,
                    halign: "center",
                    valign: "middle"
                },
                columnStyles: {
                    0: { cellWidth: 35 },  // First column width
                    1: { cellWidth: 45 },  // Date column width
                    2: { cellWidth: 45 },  // Installment column width
                    3: { cellWidth: 45 },  // Amount column width
                },
                theme: "grid",
                margin: { right: 60 },
                didParseCell: function (data) {
                    if (data.row.index === tableData.length - 1) {
                        data.cell.styles.fontStyle = "bold";
                    }
                }
            });

            // Save the PDF
            doc.save(`Installment_Report_${unitCode}.pdf`);
        });
    },

    // Export Excel functionality
    exportExcel: function () {
        document.getElementById("exportExcelButton").addEventListener("click", function () {
            let tableContainer = document.getElementById("installmentTableContainer");

            if (tableContainer.style.display === "none") {
                alert("No table to export!");
                return;
            }

            const XLSX = window.XLSX;

            // Gather Additional Info
            const userName = "{{user.email}}"; // Fetch dynamically if available
            const currentDate = new Date().toLocaleString("en-GB", {
                day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"
            });
            const companyName = "{{ project.company }}"; // Fetch dynamically if needed
            const unitCode = document.getElementById("unit_code")?.value || "N/A";

            // Prepare the data for the Excel sheet
            const table = document.querySelector(".installment-table");
            const tableData = [];
            const headers = ["", "DATE", "INSTALLMENT", "AMOUNT"]; // Final headers
            tableData.push(headers);

            let totalAmount = 0;

            table.querySelectorAll("tbody tr").forEach(row => {
                const cells = row.querySelectorAll("td, input");
                const rowData = [];

                if (cells.length >= 5) {
                    rowData.push(cells[0].innerText.trim() || "");  // First column
                    rowData.push(cells[1].innerText.trim() || "");  // Date
                    rowData.push(cells[4].innerText.trim() || "");  // Installment
                    rowData.push(cells[5].innerText.trim() || "");  // Amount

                    let amount = parseFloat(cells[4].innerText.replace(/[^\d.]/g, "")) || 0;
                    totalAmount += amount;
                }

                tableData.push(rowData);
            });

            // Add Total Row
            const totalRow = ["",  "Total Price", totalAmount.toLocaleString() + " EGP"];
            tableData.push(totalRow);

            // Create a worksheet
            const worksheet = XLSX.utils.aoa_to_sheet(tableData);

            // Create a workbook and append the worksheet
            const workbook = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(workbook, worksheet, "Installment Report");

            // Generate and download the Excel file
            XLSX.writeFile(workbook, `Installment_Report_${unitCode}.xlsx`);
        });
    },

    // Floor input values functionality
    floorInputValues: function () {
        function floorInputValue(inputId) {
            const inputElement = document.getElementById(inputId);
            if (inputElement) {
                const value = parseFloat(inputElement.value);
                if (!isNaN(value)) {
                    inputElement.value = Math.floor(value); // Floor the value
                }
                else {
                    inputElement.value = "-"; // Handle invalid or missing values
                }
            }
        }

        // Apply flooring to all relevant inputs
        floorInputValue("net_area"); // Gross Area
        floorInputValue("garden_area"); // Garden Area
        floorInputValue("penthouse_area"); // Penthouse Area
        floorInputValue("uncovered_terraces"); // Terrace / Roof Area
    },

    // Initialize all functionalities
    init: function () {
        document.addEventListener("DOMContentLoaded", function () {
            App.exportPdf(); // Initialize PDF export
            App.exportExcel(); // Initialize Excel export
            App.floorInputValues(); // Initialize flooring of input values
        });
    }
};

// Initialize the application
App.init();

document.addEventListener("DOMContentLoaded", function () {
    try{

        // Store all original options for resetting the datalist
        const unitCodeSearch = document.getElementById("unitCodeSearch");
        const unitCodeOptions = document.getElementById("unitCodeOptions");
        const originalOptions = Array.from(unitCodeOptions.options);
        
        // Add event listener to filter options dynamically
        unitCodeSearch.addEventListener("input", function () {
            const searchTerm = unitCodeSearch.value.trim().toLowerCase();

            // Clear the datalist
            unitCodeOptions.innerHTML = "";

            // Filter and populate the datalist with matching options
            const filteredOptions = originalOptions.filter(option => {
                return option.value.toLowerCase().includes(searchTerm);
            });

            if (filteredOptions.length > 0) {
                filteredOptions.forEach(option => unitCodeOptions.appendChild(option.cloneNode(true)));
            } else {
                // If no matches, show a "No results" option
                const noResultsOption = document.createElement("option");
                noResultsOption.value = "";
                noResultsOption.textContent = "No matching Unit Codes";
                noResultsOption.disabled = true;
                unitCodeOptions.appendChild(noResultsOption);
            }
        });
    }catch{
        
    }
    

    
});


document.addEventListener("DOMContentLoaded", function () {

    if(isCompanyERPUnits == false){
        const unitCodeSearch = document.getElementById("unitCodeSearchNew");
        const unitCodeOptions = document.getElementById("unitCodeOptionsNew");
    
        // Store all original options for resetting the datalist
        const originalOptions = Array.from(unitCodeOptions.options);
    
        // Add event listener to filter options dynamically
        unitCodeSearch.addEventListener("input", function () {
            const searchTerm = unitCodeSearch.value.trim().toLowerCase();
    
            // Clear the datalist
            unitCodeOptions.innerHTML = "";
    
            // Filter and populate the datalist with matching options
            const filteredOptions = originalOptions.filter(option => {
                return option.value.toLowerCase().includes(searchTerm);
            });
    
            if (filteredOptions.length > 0) {
                filteredOptions.forEach(option => unitCodeOptions.appendChild(option.cloneNode(true)));
            } else {
                // If no matches, show a "No results" option
                const noResultsOption = document.createElement("option");
                noResultsOption.value = "";
                noResultsOption.textContent = "No matching Unit Codes";
                noResultsOption.disabled = true;
                unitCodeOptions.appendChild(noResultsOption);
            }
        });
        
    }
    
});


document.addEventListener("DOMContentLoaded", function () {
    const searchForm = document.getElementById("searchForm");
    const projectSelect = document.getElementById("projectName");
    const unitInput = document.getElementById("unitCodeSearch") || document.getElementById("unitCodeSearchNew");
    const warningModal = new bootstrap.Modal(document.getElementById("warningModal"));

    searchForm.addEventListener("submit", function (e) {
        const projectValue = projectSelect.value.trim();
        const unitValue = unitInput.value.trim();

        if (!projectValue || !unitValue) {
            e.preventDefault();
            warningModal.show();
        }
        else{
            let holdButton = document.getElementById("hold-button")
            holdButton.style.display = "none";
        }
    });

    // Hide modal when user interacts with dropdowns
    [projectSelect, unitInput].forEach(dropdown => {
        dropdown.addEventListener("change", () => {
            warningModal.hide(); // Hide the modal if user starts interacting
        });
    });
    
});

function closeModal() {
    const modal = document.getElementById("warningModal");

    // Hide the modal
    modal.style.display = "none";
    modal.classList.remove("show"); // remove bootstrap "show" class

    // Remove backdrop manually
    const backdrop = document.querySelector('.modal-backdrop');
    if (backdrop) {
        backdrop.remove();
    }

    // Allow body scrolling and remove blur/freeze effects
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
}  


document.addEventListener("DOMContentLoaded", function () {
    try{
        const companyFilter = document.getElementById("companyFilter");
        const unitCodeSearch = document.getElementById("unitCodeSearch");
        const unitCodeOptions = document.getElementById("unitCodeOptions");

        // Store all unit codes globally
        const allUnits = Array.from(unitCodeOptions.querySelectorAll("option")).map(option => ({
            value: option.value,
            text: option.textContent
        }));

        // Disable unitCodeSearch initially
        unitCodeSearch.disabled = true;

        // Add event listener to companyFilter
        companyFilter.addEventListener("change", function () {
            const selectedCompany = companyFilter.value;

            // Enable or disable unitCodeSearch based on selection
            if (selectedCompany) {
                unitCodeSearch.disabled = false;
            } else {
                unitCodeSearch.disabled = true;
                unitCodeSearch.value = ""; // Clear the input
            }

            // Filter unit codes based on the selected company
            unitCodeOptions.innerHTML = ""; // Clear existing options

            if (selectedCompany) {
                const filteredUnits = allUnits.filter(unit => unit.value.startsWith(selectedCompany + "_"));
                filteredUnits.forEach(unit => {
                    const option = document.createElement("option");
                    option.value = unit.value;
                    option.textContent = unit.text;
                    unitCodeOptions.appendChild(option);
                });
            }
        });
        
    }
    catch{

    }
});


document.addEventListener("DOMContentLoaded", function () {
    try{
        const companyFilter = document.getElementById("companyFilter");
        const projectSelect = document.getElementById("projectName");
        const unitCodeSearch = document.getElementById("unitCodeSearch");
        const unitCodeOptions = document.getElementById("unitCodeOptions");

        // 🟡 Store all unit codes globally with their text and project info
        const allUnits = Array.from(unitCodeOptions.querySelectorAll("option")).map(option => ({
            value: option.value,
            text: option.textContent,
            project: option.dataset.project || ""
        }));

        // 🔴 Disable both unit and project fields initially
        unitCodeSearch.disabled = true;
        projectSelect.disabled = true;

        // 🟢 Triggered when Company changes
        companyFilter.addEventListener("change", function () {
            const selectedCompany = this.value;

            // Enable/disable project and unit fields
            projectSelect.disabled = !selectedCompany;
            unitCodeSearch.disabled = !selectedCompany;

            // Clear unit search
            unitCodeSearch.value = "";

            // 🔄 Re-filter unit codes
            filterUnitCodes();

            // 🆕 Optional: reset project list if you want to refetch project options
            // otherwise skip this if project list is already filtered by Django
        });

        // 🟢 Triggered when Project changes
        projectSelect.addEventListener("change", function () {
            filterUnitCodes();  // Re-filter based on selected project
        });

        // 🟢 Search field filter logic
        unitCodeSearch.addEventListener("input", function () {
            const searchTerm = unitCodeSearch.value.trim().toLowerCase();
            const selectedCompany = companyFilter.value;
            const selectedProject = projectSelect.value;

            unitCodeOptions.innerHTML = "";

            const filteredOptions = allUnits.filter(option =>
                option.value.toLowerCase().includes(searchTerm) &&
                option.value.startsWith(selectedCompany + "_") &&
                (!selectedProject || option.project === selectedProject)
            );

            if (filteredOptions.length > 0) {
                filteredOptions.forEach(option => {
                    const opt = document.createElement("option");
                    opt.value = option.value;
                    opt.textContent = option.text;
                    unitCodeOptions.appendChild(opt);
                });
            } else {
                const noResultsOption = document.createElement("option");
                noResultsOption.value = "";
                noResultsOption.textContent = "No matching Unit Codes";
                noResultsOption.disabled = true;
                unitCodeOptions.appendChild(noResultsOption);
            }
        });

        // ✅ Function to filter unit codes on company/project change
        function filterUnitCodes() {
            const selectedCompany = companyFilter.value;
            const selectedProject = projectSelect.value;

            unitCodeOptions.innerHTML = "";

            if (!selectedCompany) return;

            const filteredUnits = allUnits.filter(unit =>
                unit.value.startsWith(selectedCompany + "_") &&
                (!selectedProject || unit.project === selectedProject)
            );

            filteredUnits.forEach(unit => {
                const option = document.createElement("option");
                option.value = unit.value;
                option.textContent = unit.text;
                option.dataset.project = unit.project;
                unitCodeOptions.appendChild(option);
            });
        }
        
    }
    catch{

    }
});


document.addEventListener("DOMContentLoaded", function () {
    try {
        const companyFilter = document.getElementById("companyFilter");
        const projectSelect = document.getElementById("projectName");

        // Store all project options initially
        const allProjectOptions = Array.from(projectSelect.options);

        companyFilter.addEventListener("change", function () {
            const selectedCompany = this.value;

            // Clear current options except the placeholder
            projectSelect.innerHTML = "";
            const placeholderOption = document.createElement("option");
            placeholderOption.textContent = "-- Select Project --";
            placeholderOption.value = "";
            projectSelect.appendChild(placeholderOption);

            // Filter and append relevant projects
            allProjectOptions.forEach(option => {
                if (
                    option.value &&  // skip placeholder
                    option.dataset.company === selectedCompany
                ) {
                    projectSelect.appendChild(option.cloneNode(true));
                }
            });
        });
        
    } catch (e) {
        console.error("Error filtering project dropdown:", e);
    }
});

}
catch{
    
}
