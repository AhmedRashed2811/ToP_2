class Dashboard {
    constructor() {
        this.currentCompany = null;
        this.filters = {
            projects: [],
            unitTypes: [],
            statuses: [],
            areas: [],
            timePeriod: 'ytd'
        };
        this.charts = {};
        this.units = [];
        this.init();
    }

    async init() {
        this.initEventListeners();

        // Check if there's a pre-selected company (for managers)
        const companySelect = document.getElementById("companySelect");
        const selectedCompanyId = companySelect ? companySelect.value : "{{ selected_company_id }}";

        if (selectedCompanyId) {
            await this.loadCompanyData(selectedCompanyId);
        }

        // Setup chart buttons
        this.setupChartButtons();
    }

    initEventListeners() {
        // Time period filter
        document.getElementById("timePeriod")?.addEventListener("change", (e) => {
            this.filters.timePeriod = e.target.value;
            this.updateDashboard();
        });

        // Refresh button
        document.getElementById("refreshBtn")?.addEventListener("click", () => {
            if (this.currentCompany) {
                this.loadCompanyData(this.currentCompany);
            }
        });

        // Export button
        document.getElementById("exportData")?.addEventListener("click", () => {
            this.exportData();
        });

        // Company select change
        document.getElementById("companySelect")?.addEventListener("change", (e) => {
            this.loadCompanyData(e.target.value);
        });

        // Filter checkboxes
        document.querySelectorAll('.filter-options input[type="checkbox"]').forEach(input => {
            input.addEventListener('change', () => this.updateFilters());
        });
    }

    setupChartButtons() {
        // Handle all download buttons
        document.querySelectorAll('.chart-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const chartCard = button.closest('.chart-card');
                const canvas = chartCard?.querySelector('canvas[id$="Chart"]');

                if (!canvas) {
                    console.warn('Canvas not found in chart card:', chartCard);
                    return;
                }

                this.downloadChart(canvas);
            });
        });

        // Handle all expand buttons
        document.querySelectorAll('.chart-btn').forEach(button => {
            const icon = button.querySelector('.fa-expand');
            if (!icon) return; // Skip if button doesn't contain an expand icon

            button.addEventListener('click', (e) => {
                e.preventDefault();

                const chartCard = button.closest('.chart-card');
                const canvas = chartCard?.querySelector('canvas[id$="Chart"]');

                if (!canvas) {
                    console.warn('Canvas not found in chart card:', chartCard);
                    return;
                }

                this.expandChart(canvas);
            });
        });
    }

    downloadChart(canvas) {
        try {
            const link = document.createElement('a');
            const chartName = canvas.id.replace('Chart', '');
            link.download = `${chartName}_${new Date().toISOString().slice(0,10)}.png`;
            link.href = canvas.toDataURL('image/png');
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (error) {
            console.error('Error downloading chart:', error);
            alert('Failed to download chart. Please try again.');
        }
    }

    expandChart(canvas) {
        try {
            const modal = document.createElement('div');
            modal.className = 'chart-modal';

            const container = document.createElement('div');
            container.className = 'chart-modal-container';

            const expandedCanvas = document.createElement('canvas');
            expandedCanvas.width = window.innerWidth * 0.8;
            expandedCanvas.height = window.innerHeight * 0.7;

            // Copy the chart
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = canvas.width;
            tempCanvas.height = canvas.height;
            const tempCtx = tempCanvas.getContext('2d');
            tempCtx.drawImage(canvas, 0, 0);

            const ctx = expandedCanvas.getContext('2d');
            ctx.drawImage(tempCanvas, 0, 0, expandedCanvas.width, expandedCanvas.height);

            const closeBtn = document.createElement('button');
            closeBtn.className = 'chart-modal-close';
            closeBtn.innerHTML = '&times;';

            closeBtn.addEventListener('click', () => {
                document.body.removeChild(modal);
            });

            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    document.body.removeChild(modal);
                }
            });

            container.appendChild(expandedCanvas);
            container.appendChild(closeBtn);
            modal.appendChild(container);
            document.body.appendChild(modal);
        } catch (error) {
            console.error('Error expanding chart:', error);
            alert('Failed to expand chart. Please try again.');
        }
    }

    async loadCompanyData(companyId) {
        if (!companyId) {
            this.clearDashboard();
            document.querySelector(".buttons").style.display = "none";
            return;
        }

        this.currentCompany = companyId;

        try {
            this.showLoading(true);

            const response = await fetch(`/ajax/get_company_units/?company_id=${companyId}`);
            const data = await response.json();

            this.units = data.units || [];
            document.querySelector(".buttons").style.display = "flex";

            // Initialize filters
            this.initFilters();

            // Initialize charts if not already done
            if (Object.keys(this.charts).length === 0) {
                this.initCharts();
            }

            // Update dashboard
            this.updateDashboard();

        } catch (error) {
            console.error('Error loading company data:', error);
            alert('Failed to load company data. Please try again.');
        } finally {
            this.showLoading(false);
        }
    }

    clearDashboard() {
        // Clear all dashboard data
        this.units = [];
        this.updateKPIs([]);
        this.updateCharts([]);
        this.updateDataTable([]);
        document.getElementById("homeSection").innerHTML =
            "<h2>Welcome</h2><p>Select a company from the dropdown above.</p>";
    }

    initFilters() {
        // Get unique values for filters
        const projects = [...new Set(this.units.map(u => u.project))].filter(Boolean);
        const unitTypes = [...new Set(this.units.map(u => u.unit_type))].filter(Boolean);
        const statuses = [...new Set(this.units.map(u => u.status))].filter(Boolean);
        const areas = [...new Set(this.units.map(u => u.area_range))].filter(Boolean);

        // Populate project filter
        const projectFilter = document.getElementById("projectFilter");
        if (projectFilter) {
            projectFilter.innerHTML = projects.map(p => `
                <label>
                    <input type="checkbox" name="project" value="${p}" checked> ${p}
                </label>
            `).join('');
        }

        // Populate unit type filter
        const unitTypeFilter = document.getElementById("unitTypeFilter");
        if (unitTypeFilter) {
            unitTypeFilter.innerHTML = unitTypes.map(t => `
                <label>
                    <input type="checkbox" name="unitType" value="${t}" checked> ${t}
                </label>
            `).join('');
        }

        // Populate status filter
        const statusFilter = document.getElementById("statusFilter");
        if (statusFilter) {
            statusFilter.innerHTML = statuses.map(s => `
                <label>
                    <input type="checkbox" name="status" value="${s}" checked> ${s}
                </label>
            `).join('');
        }

        // Populate area filter
        const areaFilter = document.getElementById("areaFilter");
        if (areaFilter) {
            areaFilter.innerHTML = areas.map(a => `
                <label>
                    <input type="checkbox" name="area" value="${a}" checked> ${a}
                </label>
            `).join('');
        }

        // Reinitialize event listeners for the new filter elements
        this.initEventListeners();
    }

    updateFilters() {
        // Get current filter values
        this.filters.projects = Array.from(
            document.querySelectorAll('#projectFilter input:checked')
        ).map(el => el.value);

        this.filters.unitTypes = Array.from(
            document.querySelectorAll('#unitTypeFilter input:checked')
        ).map(el => el.value);

        this.filters.statuses = Array.from(
            document.querySelectorAll('#statusFilter input:checked')
        ).map(el => el.value);

        this.filters.areas = Array.from(
            document.querySelectorAll('#areaFilter input:checked')
        ).map(el => el.value);

        // Update dashboard with new filters
        this.updateDashboard();
    }

    initCharts() {
        // Sales Trend Chart
        const salesTrendCanvas = document.getElementById("salesTrendChart");
        this.charts.salesTrend = new Chart(
            salesTrendCanvas, {
                type: 'line',
                data: { labels: [], datasets: [] },
                options: this.getChartOptions('Sales Trend')
            }
        );
        salesTrendCanvas.chartInstance = this.charts.salesTrend;

        // Inventory Chart
        const inventoryCanvas = document.getElementById("inventoryChart");
        this.charts.inventory = new Chart(
            inventoryCanvas, {
                type: 'doughnut',
                data: { labels: [], datasets: [] },
                options: this.getChartOptions('Inventory Status')
            }
        );
        inventoryCanvas.chartInstance = this.charts.inventory;

        // Unit Type Chart
        const unitTypeCanvas = document.getElementById("unitTypeChart");
        this.charts.unitType = new Chart(
            unitTypeCanvas, {
                type: 'bar',
                data: { labels: [], datasets: [] },
                options: this.getChartOptions('Unit Type Distribution')
            }
        );
        unitTypeCanvas.chartInstance = this.charts.unitType;

        // Scatter Chart
        const scatterCanvas = document.getElementById("scatterChart");
        this.charts.scatter = new Chart(
            scatterCanvas, {
                type: 'scatter',
                data: { datasets: [] },
                options: this.getChartOptions('Price vs Area')
            }
        );
        scatterCanvas.chartInstance = this.charts.scatter;
    }

    getChartOptions(title) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    onClick: (e, legendItem, legend) => {
                        const index = legendItem.datasetIndex;
                        const label = legend.chart.data.labels[index];
                        this.applyFilter(this.getFilterTypeFromChartId(legend.chart.canvas.id), label);
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== undefined) {
                                label += new Intl.NumberFormat('en-US', {
                                    style: 'currency',
                                    currency: 'USD'
                                }).format(context.parsed.y);
                            }
                            return label;
                        }
                    }
                }
            },
            onClick: (e, elements, chart) => {
                if (elements.length > 0) {
                    try {
                        const element = elements[0];
                        const datasetIndex = element.datasetIndex;
                        const dataIndex = element.index;

                        const chartId = chart.canvas.id;
                        const chartType = chartId.replace("Chart", "");

                        if (chartType === 'inventory') {
                            const label = this.charts[chartType].data.labels[dataIndex];
                            this.applyFilter('status', label);
                        } else if (chartType === 'unitType') {
                            const label = this.charts[chartType].data.labels[dataIndex];
                            this.applyFilter('unitType', label);
                        }
                    } catch (error) {
                        console.error('Error handling chart click:', error);
                    }
                }
            }
        };
    }

    getFilterTypeFromChartId(chartId) {
        switch (chartId) {
            case 'inventoryChart':
                return 'status';
            case 'unitTypeChart':
                return 'unitType';
            case 'salesTrendChart':
                return 'project';
            case 'scatterChart':
                return 'area';
            default:
                return 'project';
        }
    }

    applyFilter(filterName, value) {
        const filterContainer = document.getElementById(`${filterName}Filter`);

        if (filterContainer) {
            document.querySelectorAll(`#${filterName}Filter input`).forEach(input => {
                input.checked = false;
            });

            const checkbox = document.querySelector(`#${filterName}Filter input[value="${value}"]`);
            if (checkbox) {
                checkbox.checked = true;
            }

            this.updateFilters();
        }
    }

    updateDashboard() {
        const filteredUnits = this.units.filter(unit => {
            return (
                (this.filters.projects.length === 0 || this.filters.projects.includes(unit.project)) &&
                (this.filters.unitTypes.length === 0 || this.filters.unitTypes.includes(unit.unit_type)) &&
                (this.filters.statuses.length === 0 || this.filters.statuses.includes(unit.status)) &&
                (this.filters.areas.length === 0 || this.filters.areas.includes(unit.area_range))
            );
        });

        this.updateKPIs(filteredUnits);
        this.updateCharts(filteredUnits);
        this.updateDataTable(filteredUnits);
    }

    updateKPIs(units) {
        document.getElementById("totalUnits").textContent = units.length.toLocaleString();

        const soldUnits = units.filter(u => u.status === 'Contracted').length;
        document.getElementById("soldUnits").textContent = soldUnits.toLocaleString();
        const soldPercent = units.length > 0 ? (soldUnits / units.length * 100).toFixed(1) : 0;
        document.getElementById("soldTrend").textContent = `${soldPercent}%`;

        const totalValue = units.reduce((sum, u) => sum + (parseFloat(u.sales_value) || 0), 0);
        document.getElementById("inventoryValue").textContent = `$${(totalValue / 1000000).toFixed(1)}M`;

        const avgPSM = units.length > 0 ?
            units.reduce((sum, u) => sum + (parseFloat(u.psm) || 0), 0) / units.length : 0;
        document.getElementById("avgPSM").textContent = `$${avgPSM.toFixed(0)}`;
    }

    updateCharts(units) {
        this.updateSalesTrendChart(units);
        this.updateInventoryChart(units);
        this.updateUnitTypeChart(units);
        this.updateScatterChart(units);
    }

    updateSalesTrendChart(units) {
        const monthlySales = this.groupByMonth(units);
        this.charts.salesTrend.data = {
            labels: Object.keys(monthlySales),
            datasets: [{
                label: 'Sales Value',
                data: Object.values(monthlySales).map(m => m.sales),
                borderColor: '#4472C4',
                backgroundColor: 'rgba(68, 114, 196, 0.1)',
                tension: 0.3,
                fill: true
            }]
        };
        this.charts.salesTrend.update();
    }

    updateInventoryChart(units) {
        const statusCounts = this.groupByStatus(units);
        this.charts.inventory.data = {
            labels: Object.keys(statusCounts),
            datasets: [{
                data: Object.values(statusCounts),
                backgroundColor: [
                    '#5B9BD5', '#ED7D31', '#A5A5A5', '#FFC000', '#70AD47'
                ]
            }]
        };
        this.charts.inventory.update();
    }

    updateUnitTypeChart(units) {
        const typeCounts = this.groupByUnitType(units);
        this.charts.unitType.data = {
            labels: Object.keys(typeCounts),
            datasets: [{
                label: 'Units',
                data: Object.values(typeCounts),
                backgroundColor: '#4472C4'
            }]
        };
        this.charts.unitType.update();
    }

    updateScatterChart(units) {
        this.charts.scatter.data = {
            datasets: [{
                label: 'Price vs Area',
                data: units.map(u => ({
                    x: parseFloat(u.gross_area) || 0,
                    y: parseFloat(u.sales_value) || 0
                })),
                backgroundColor: '#4472C4',
                pointRadius: 5
            }]
        };
        this.charts.scatter.update();
    }

    updateDataTable(units) {
        const tableBody = document.querySelector('#unitsTable tbody');
        if (!tableBody) return;

        tableBody.innerHTML = units.map(unit => `
            <tr>
                <td>${unit.project || '-'}</td>
                <td>${unit.unit_type || '-'}</td>
                <td>${this.formatNumber(unit.gross_area)}</td>
                <td>${unit.status || '-'}</td>
                <td>${this.formatCurrency(unit.sales_value)}</td>
                <td>${this.formatCurrency(unit.psm)}</td>
                <td>${unit.reservation_date ? new Date(unit.reservation_date).toLocaleDateString() : '-'}</td>
            </tr>
        `).join('');
    }

    groupByMonth(units) {
        const months = {};
        units.forEach(unit => {
            if (unit.reservation_date) {
                const date = new Date(unit.reservation_date);
                const monthYear = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
                if (!months[monthYear]) {
                    months[monthYear] = { sales: 0, count: 0 };
                }
                months[monthYear].sales += parseFloat(unit.sales_value) || 0;
                months[monthYear].count++;
            }
        });

        return Object.keys(months)
            .sort()
            .reduce((obj, key) => {
                obj[key] = months[key];
                return obj;
            }, {});
    }

    groupByStatus(units) {
        const statuses = {};
        units.forEach(unit => {
            const status = unit.status || 'Unknown';
            statuses[status] = (statuses[status] || 0) + 1;
        });
        return statuses;
    }

    groupByUnitType(units) {
        const types = {};
        units.forEach(unit => {
            const type = unit.unit_type || 'Unknown';
            types[type] = (types[type] || 0) + 1;
        });
        return types;
    }

    exportData() {
        const filteredUnits = this.getFilteredUnits();
        const ws = XLSX.utils.json_to_sheet(filteredUnits);
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, "Units Data");
        XLSX.writeFile(wb, `Units_Export_${new Date().toISOString().slice(0,10)}.xlsx`);
    }

    getFilteredUnits() {
        return this.units.filter(unit => {
            return (
                (this.filters.projects.length === 0 || this.filters.projects.includes(unit.project)) &&
                (this.filters.unitTypes.length === 0 || this.filters.unitTypes.includes(unit.unit_type)) &&
                (this.filters.statuses.length === 0 || this.filters.statuses.includes(unit.status)) &&
                (this.filters.areas.length === 0 || this.filters.areas.includes(unit.area_range))
            );
        });
    }

    showLoading(show) {
        const loader = document.getElementById("dashboardLoader");
        if (show) {
            if (!loader) {
                const loaderDiv = document.createElement('div');
                loaderDiv.id = 'dashboardLoader';
                loaderDiv.className = 'dashboard-loader';
                loaderDiv.innerHTML = `
                    <div class="loader-spinner"></div>
                    <p>Loading data...</p>
                `;
                document.querySelector('.dashboard-container').appendChild(loaderDiv);
            }
        } else if (loader) {
            loader.remove();
        }
    }

    formatNumber(num) {
        const value = parseFloat(num);
        if (isNaN(value)) return '-';
        return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    formatCurrency(num) {
        const value = parseFloat(num);
        if (isNaN(value)) return '-';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 0
        }).format(value);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
    window.dashboard = new Dashboard();
});

// Add CSS for loader and modal
const loaderStyles = document.createElement('style');
loaderStyles.textContent = `
    .dashboard-loader {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.8);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        z-index: 1000;
    }
    
    .loader-spinner {
        border: 5px solid #f3f3f3;
        border-top: 5px solid #4472C4;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .chart-modal {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0,0,0,0.8);
        z-index: 2000;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    
    .chart-modal-container {
        position: relative;
        background: white;
        padding: 20px;
        border-radius: 8px;
        max-width: 90%;
        max-height: 90%;
        overflow: auto;
    }
    
    .chart-modal-close {
        position: absolute;
        top: 10px;
        right: 10px;
        background: #dc3545;
        color: white;
        border: none;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        font-size: 18px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
    }
`;
document.head.appendChild(loaderStyles);