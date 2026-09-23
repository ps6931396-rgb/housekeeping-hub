/* ==========================================================================
   Admin Panel JavaScript — sidebar toggle & Chart.js dashboard charts
   ========================================================================== */
(function () {
    "use strict";

    function initSidebarToggle() {
        var toggle = document.getElementById("adminMenuToggle");
        var sidebar = document.getElementById("adminSidebar");
        if (toggle && sidebar) {
            toggle.addEventListener("click", function () {
                sidebar.classList.toggle("open");
            });
        }
    }

    function getCssVar(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    function initCharts() {
        if (typeof Chart === "undefined") return;

        var trendCanvas = document.getElementById("bookingsTrendChart");
        if (trendCanvas && window.__chartDays) {
            new Chart(trendCanvas, {
                type: "line",
                data: {
                    labels: window.__chartDays,
                    datasets: [{
                        label: "Bookings",
                        data: window.__chartCounts,
                        borderColor: "#2563EB",
                        backgroundColor: "rgba(37,99,235,0.12)",
                        tension: 0.4,
                        fill: true,
                        pointRadius: 3,
                        pointBackgroundColor: "#7C3AED",
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                },
            });
        }

        var statusCanvas = document.getElementById("statusPieChart");
        if (statusCanvas && window.__statusLabels) {
            new Chart(statusCanvas, {
                type: "doughnut",
                data: {
                    labels: window.__statusLabels,
                    datasets: [{
                        data: window.__statusCounts,
                        backgroundColor: ["#F59E0B", "#2563EB", "#10B981", "#EF4444"],
                        borderWidth: 0,
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } } },
                },
            });
        }

        var revenueCanvas = document.getElementById("revenueChart");
        if (revenueCanvas && window.__revenueLabels) {
            new Chart(revenueCanvas, {
                type: "bar",
                data: {
                    labels: window.__revenueLabels,
                    datasets: [{
                        label: "Revenue",
                        data: window.__revenueData,
                        backgroundColor: "#7C3AED",
                        borderRadius: 6,
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true } },
                },
            });
        }
    }

    function initImagePreview() {
        var input = document.getElementById("serviceImageInput");
        var preview = document.getElementById("serviceImagePreview");
        if (input && preview) {
            input.addEventListener("change", function () {
                if (this.files && this.files[0]) {
                    var reader = new FileReader();
                    reader.onload = function (e) { preview.src = e.target.result; preview.style.display = "block"; };
                    reader.readAsDataURL(this.files[0]);
                }
            });
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        initSidebarToggle();
        initCharts();
        initImagePreview();
    });
})();
