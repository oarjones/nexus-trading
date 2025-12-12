
/**
 * Chart.js wrapper for Nexus Dashboard.
 * Handles TimeSeries rendering for Equity Curves.
 */

// Format currency
const fmtMoney = (value) => {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(value);
};

// Generic Line Chart
function renderEquityCurve(canvasId, dataPoints, label = "Equity") {
    const ctx = document.getElementById(canvasId).getContext('2d');

    // Destroy previous instance if exists to avoid overlay
    const existingChart = Chart.getChart(canvasId);
    if (existingChart) {
        existingChart.destroy();
    }

    const labels = dataPoints.map(d => new Date(d.timestamp).toLocaleTimeString());
    const values = dataPoints.map(d => d.total_value);

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: values,
                borderColor: '#00e676', // Green accent
                backgroundColor: 'rgba(0, 230, 118, 0.1)',
                borderWidth: 2,
                pointRadius: 0, // Smooth line
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function (context) {
                            return fmtMoney(context.raw);
                        }
                    }
                }
            },
            scales: {
                x: { display: false }, // Clean look
                y: {
                    display: true,
                    grid: { color: '#333' },
                    ticks: { callback: (val) => fmtMoney(val) }
                }
            },
            animation: { duration: 0 } // Disable animation for performance updates
        }
    });
}
