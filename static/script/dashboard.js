// Dashboard JavaScript - Interactive Charts and KPIs
class MarketDashboard {
    constructor() {
        this.charts = {};
        this.currentFilters = {};
        this.isLoading = false;
        this.init();
    }

    init() {
        this.initializeFilters();
        this.initializeSliders();
        this.bindEvents();
        this.loadInitialData();
    }

    initializeFilters() {
        // Initialize Select2 for all filter dropdowns
        $('.filter-select').select2({
            placeholder: "Select options...",
            allowClear: true,
            closeOnSelect: false,
            width: '100%'
        });
    }

    initializeSliders() {
        // Price Range Slider
        const priceSlider = document.getElementById('priceSlider');
        if (priceSlider) {
            noUiSlider.create(priceSlider, {
                start: [0, 10000000],
                connect: true,
                range: {
                    'min': 0,
                    'max': 10000000
                },
                format: {
                    to: function (value) {
                        return Math.round(value);
                    },
                    from: function (value) {
                        return Number(value);
                    }
                }
            });

            priceSlider.noUiSlider.on('update', (values) => {
                document.getElementById('minPriceValue').textContent = this.formatNumber(values[0]);
                document.getElementById('maxPriceValue').textContent = this.formatNumber(values[1]);
            });
        }

        // BUA Range Slider
        const buaSlider = document.getElementById('buaSlider');
        if (buaSlider) {
            noUiSlider.create(buaSlider, {
                start: [0, 1000],
                connect: true,
                range: {
                    'min': 0,
                    'max': 1000
                },
                format: {
                    to: function (value) {
                        return Math.round(value);
                    },
                    from: function (value) {
                        return Number(value);
                    }
                }
            });

            buaSlider.noUiSlider.on('update', (values) => {
                document.getElementById('minBuaValue').textContent = values[0] + ' m²';
                document.getElementById('maxBuaValue').textContent = values[1] + ' m²';
            });
        }
    }

    bindEvents() {
        // Apply filters button
        document.getElementById('applyFilters').addEventListener('click', () => {
            this.applyFilters();
        });

        // Reset filters button
        document.getElementById('resetFilters').addEventListener('click', () => {
            this.resetFilters();
        });

        // Auto-apply filters on select change (debounced)
        $('.filter-select').on('select2:select select2:unselect', 
            this.debounce(() => this.applyFilters(), 1000)
        );

        // Chart action buttons
        document.querySelectorAll('.chart-action').forEach(action => {
            action.addEventListener('click', (e) => {
                const icon = e.target.closest('.chart-action').querySelector('i');
                if (icon.classList.contains('fa-sync-alt')) {
                    this.refreshCharts();
                } else if (icon.classList.contains('fa-download')) {
                    this.exportData();
                }
            });
        });
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    getCurrentFilters() {
        const priceSlider = document.getElementById('priceSlider');
        const buaSlider = document.getElementById('buaSlider');
        
        return {
            developers: $('#developerFilter').val() || [],
            locations: $('#locationFilter').val() || [],
            asset_types: $('#assetTypeFilter').val() || [],
            unit_types: $('#unitTypeFilter').val() || [],
            finishing_specs: $('#finishingFilter').val() || [],
            min_price: priceSlider ? priceSlider.noUiSlider.get()[0] : 0,
            max_price: priceSlider ? priceSlider.noUiSlider.get()[1] : 10000000,
            min_bua: buaSlider ? buaSlider.noUiSlider.get()[0] : 0,
            max_bua: buaSlider ? buaSlider.noUiSlider.get()[1] : 1000
        };
    }

    applyFilters() {
        this.currentFilters = this.getCurrentFilters();
        this.loadDashboardData();
    }

    resetFilters() {
        // Reset all select2 dropdowns
        $('.filter-select').val(null).trigger('change');
        
        // Reset sliders
        const priceSlider = document.getElementById('priceSlider');
        const buaSlider = document.getElementById('buaSlider');
        
        if (priceSlider) priceSlider.noUiSlider.set([0, 10000000]);
        if (buaSlider) buaSlider.noUiSlider.set([0, 1000]);
        
        this.currentFilters = {};
        this.loadDashboardData();
    }

    loadInitialData() {
        this.loadDashboardData();
    }

    async loadDashboardData() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading();

        try {
            // Load KPIs and Charts data in parallel
            const [kpisResponse, chartsResponse] = await Promise.all([
                this.fetchKPIs(),
                this.fetchChartsData()
            ]);

            this.updateKPIs(kpisResponse);
            this.updateCharts(chartsResponse);
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Failed to load dashboard data');
        } finally {
            this.isLoading = false;
            this.hideLoading();
        }
    }

    async fetchKPIs() {
        const params = new URLSearchParams();
        Object.entries(this.currentFilters).forEach(([key, value]) => {
            if (Array.isArray(value)) {
                value.forEach(v => params.append(`${key}[]`, v));
            } else if (value !== undefined && value !== '') {
                params.append(key, value);
            }
        });

        const response = await fetch(`/dashboard/kpis/?${params}`);
        return await response.json();
    }

    async fetchChartsData() {
        const params = new URLSearchParams();
        Object.entries(this.currentFilters).forEach(([key, value]) => {
            if (Array.isArray(value)) {
                value.forEach(v => params.append(`${key}[]`, v));
            } else if (value !== undefined && value !== '') {
                params.append(key, value);
            }
        });

        const response = await fetch(`/dashboard/charts/?${params}`);
        return await response.json();
    }

    updateKPIs(data) {
        const kpisContainer = document.getElementById('kpisContainer');
        
        const kpis = [
            {
                title: 'Total Units',
                value: this.formatNumber(data.total_units),
                icon: 'fas fa-home',
                color: '#2563eb',
                change: '+12%',
                changeType: 'positive'
            },
            {
                title: 'Total Projects',
                value: this.formatNumber(data.total_projects),
                icon: 'fas fa-building',
                color: '#10b981',
                change: '+8%',
                changeType: 'positive'
            },
            {
                title: 'Average Price',
                value: this.formatCurrency(data.avg_price),
                icon: 'fas fa-dollar-sign',
                color: '#f59e0b',
                change: '+5%',
                changeType: 'positive'
            },
            {
                title: 'Average PSM',
                value: this.formatCurrency(data.avg_psm),
                icon: 'fas fa-chart-area',
                color: '#ef4444',
                change: '+3%',
                changeType: 'positive'
            },
            {
                title: 'Average BUA',
                value: data.avg_bua + ' m²',
                icon: 'fas fa-expand-arrows-alt',
                color: '#8b5cf6',
                change: '+2%',
                changeType: 'positive'
            },
            {
                title: 'Avg Down Payment',
                value: data.avg_down_payment + '%',
                icon: 'fas fa-percentage',
                color: '#06b6d4',
                change: '-1%',
                changeType: 'negative'
            },
            {
                title: 'Developers',
                value: this.formatNumber(data.total_developers),
                icon: 'fas fa-users',
                color: '#84cc16',
                change: '+4%',
                changeType: 'positive'
            },
            {
                title: 'Locations',
                value: this.formatNumber(data.total_locations),
                icon: 'fas fa-map-marker-alt',
                color: '#f97316',
                change: '+6%',
                changeType: 'positive'
            }
        ];

        kpisContainer.innerHTML = kpis.map(kpi => `
            <div class="kpi-card">
                <div class="kpi-header">
                    <span class="kpi-title">${kpi.title}</span>
                    <div class="kpi-icon" style="background: ${kpi.color}">
                        <i class="${kpi.icon}"></i>
                    </div>
                </div>
                <div class="kpi-value">${kpi.value}</div>
                <div class="kpi-change ${kpi.changeType}">
                    <i class="fas fa-arrow-${kpi.changeType === 'positive' ? 'up' : 'down'}"></i>
                    ${kpi.change} from last month
                </div>
            </div>
        `).join('');
    }

    updateCharts(data) {
        this.createPriceByAssetChart(data.price_by_asset);
        this.createUnitsByDeveloperChart(data.units_by_developer);
        this.createPriceVsBuaChart(data.price_vs_bua);
        this.createUnitsByLocationChart(data.units_by_location);
        this.createUnitTypeChart(data.unit_type_distribution);
        this.createMonthlyTrendsChart(data.monthly_trends);
    }

    createPriceByAssetChart(data) {
        const ctx = document.getElementById('priceByAssetChart');
        if (!ctx) return;

        if (this.charts.priceByAsset) {
            this.charts.priceByAsset.destroy();
        }

        this.charts.priceByAsset = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.asset_type),
                datasets: [{
                    label: 'Average Price (EGP)',
                    data: data.map(item => item.avg_price),
                    backgroundColor: this.generateColors(data.length),
                    borderColor: this.generateColors(data.length, 0.8),
                    borderWidth: 2,
                    borderRadius: 8,
                    borderSkipped: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return `Average Price: ${this.formatCurrency(context.parsed.y)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => this.formatNumber(value)
                        }
                    }
                }
            }
        });
    }

    createUnitsByDeveloperChart(data) {
        const ctx = document.getElementById('unitsByDeveloperChart');
        if (!ctx) return;

        if (this.charts.unitsByDeveloper) {
            this.charts.unitsByDeveloper.destroy();
        }

        this.charts.unitsByDeveloper = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(item => item.developer_name),
                datasets: [{
                    data: data.map(item => item.count),
                    backgroundColor: this.generateColors(data.length),
                    borderWidth: 3,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed * 100) / total).toFixed(1);
                                return `${context.label}: ${context.parsed} units (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    createPriceVsBuaChart(data) {
        const ctx = document.getElementById('priceVsBuaChart');
        if (!ctx) return;

        if (this.charts.priceVsBua) {
            this.charts.priceVsBua.destroy();
        }

        // Group data by asset type for different colors
        const assetTypes = [...new Set(data.map(item => item.asset_type))];
        const datasets = assetTypes.map((assetType, index) => {
            const assetData = data.filter(item => item.asset_type === assetType);
            return {
                label: assetType,
                data: assetData.map(item => ({
                    x: item.bua,
                    y: item.unit_price
                })),
                backgroundColor: this.generateColors(assetTypes.length)[index],
                borderColor: this.generateColors(assetTypes.length, 0.8)[index],
                borderWidth: 2
            };
        });

        this.charts.priceVsBua = new Chart(ctx, {
            type: 'scatter',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return `${context.dataset.label}: ${context.parsed.x} m², ${this.formatCurrency(context.parsed.y)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'BUA (m²)'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Price (EGP)'
                        },
                        ticks: {
                            callback: (value) => this.formatNumber(value)
                        }
                    }
                }
            }
        });
    }

    createUnitsByLocationChart(data) {
        const ctx = document.getElementById('unitsByLocationChart');
        if (!ctx) return;

        if (this.charts.unitsByLocation) {
            this.charts.unitsByLocation.destroy();
        }

        this.charts.unitsByLocation = new Chart(ctx, {
            type: 'horizontalBar',
            data: {
                labels: data.map(item => item.location),
                datasets: [{
                    label: 'Number of Units',
                    data: data.map(item => item.count),
                    backgroundColor: this.generateColors(data.length),
                    borderColor: this.generateColors(data.length, 0.8),
                    borderWidth: 2,
                    borderRadius: 8,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    createUnitTypeChart(data) {
        const ctx = document.getElementById('unitTypeChart');
        if (!ctx) return;

        if (this.charts.unitType) {
            this.charts.unitType.destroy();
        }

        this.charts.unitType = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: data.map(item => item.unit_type),
                datasets: [{
                    data: data.map(item => item.count),
                    backgroundColor: this.generateColors(data.length),
                    borderWidth: 3,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    }
                }
            }
        });
    }

    createMonthlyTrendsChart(data) {
        const ctx = document.getElementById('monthlyTrendsChart');
        if (!ctx) return;

        if (this.charts.monthlyTrends) {
            this.charts.monthlyTrends.destroy();
        }

        this.charts.monthlyTrends = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(item => item.month),
                datasets: [
                    {
                        label: 'Units Count',
                        data: data.map(item => item.count),
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Average Price',
                        data: data.map(item => item.avg_price),
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 3,
                        fill: false,
                        tension: 0.4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Units Count'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Average Price (EGP)'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                        ticks: {
                            callback: (value) => this.formatNumber(value)
                        }
                    }
                }
            }
        });
    }

    generateColors(count, alpha = 0.7) {
        const colors = [
            `rgba(37, 99, 235, ${alpha})`,   // Blue
            `rgba(16, 185, 129, ${alpha})`,  // Green
            `rgba(245, 158, 11, ${alpha})`,  // Yellow
            `rgba(239, 68, 68, ${alpha})`,   // Red
            `rgba(139, 92, 246, ${alpha})`,  // Purple
            `rgba(6, 182, 212, ${alpha})`,   // Cyan
            `rgba(132, 204, 22, ${alpha})`,  // Lime
            `rgba(249, 115, 22, ${alpha})`,  // Orange
            `rgba(236, 72, 153, ${alpha})`,  // Pink
            `rgba(107, 114, 128, ${alpha})`  // Gray
        ];
        
        const result = [];
        for (let i = 0; i < count; i++) {
            result.push(colors[i % colors.length]);
        }
        return result;
    }

    formatNumber(value) {
        if (value === null || value === undefined) return '0';
        if (value >= 1000000) {
            return (value / 1000000).toFixed(1) + 'M';
        } else if (value >= 1000) {
            return (value / 1000).toFixed(0) + 'K';
        }
        return value.toLocaleString();
    }

    formatCurrency(value) {
        if (value === null || value === undefined) return '0 EGP';
        return this.formatNumber(value) + ' EGP';
    }

    showLoading() {
        // Add loading spinners to chart containers
        document.querySelectorAll('.chart-container').forEach(container => {
            container.innerHTML = `
                <div class="loading-spinner">
                    <div class="spinner"></div>
                    <span style="margin-left: 10px;">Loading...</span>
                </div>
            `;
        });
    }

    hideLoading() {
        // Loading will be hidden when charts are rendered
    }

    showError(message) {
        console.error(message);
        // You could show a toast notification here
    }

    refreshCharts() {
        this.loadDashboardData();
    }

    async exportData() {
        try {
            const params = new URLSearchParams();
            Object.entries(this.currentFilters).forEach(([key, value]) => {
                if (Array.isArray(value)) {
                    value.forEach(v => params.append(`${key}[]`, v));
                } else if (value !== undefined && value !== '') {
                    params.append(key, value);
                }
            });

            const response = await fetch(`/dashboard/export/?${params}`);
            const data = await response.json();
            
            // Create and download CSV
            this.downloadCSV(data.data, 'market_data_export.csv');
        } catch (error) {
            console.error('Export failed:', error);
            this.showError('Export failed');
        }
    }

    downloadCSV(data, filename) {
        if (!data.length) return;
        
        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => headers.map(header => `"${row[header] || ''}"`).join(','))
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new MarketDashboard();
});