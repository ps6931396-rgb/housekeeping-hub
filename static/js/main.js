/* ==========================================================================
   Housekeeping Hub PRO — Core client-side JavaScript
   Theme toggle, toasts, scroll reveal, mobile nav, page loader
   ========================================================================== */

(function () {
    "use strict";

    /* ---------------- Page loader ---------------- */
    window.addEventListener("load", function () {
        var loader = document.getElementById("page-loader");
        if (loader) {
            setTimeout(function () { loader.classList.add("hidden"); }, 150);
        }
    });

    /* ---------------- Theme toggle ---------------- */
    function initTheme() {
        var toggleBtns = document.querySelectorAll("#themeToggle");
        var root = document.documentElement;
        var saved = localStorage.getItem("hh-theme");
        if (saved) root.setAttribute("data-theme", saved);

        toggleBtns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                var current = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
                var next = current === "dark" ? "light" : "dark";
                root.setAttribute("data-theme", next);
                localStorage.setItem("hh-theme", next);
            });
        });
    }

    /* ---------------- Mobile nav ---------------- */
    function initMobileNav() {
        var navToggle = document.getElementById("navToggle");
        var mainNav = document.getElementById("mainNav");
        if (navToggle && mainNav) {
            navToggle.addEventListener("click", function () {
                mainNav.classList.toggle("open");
            });
        }
    }

    /* ---------------- Toast notifications ---------------- */
    var toastIcons = { success: "✅", error: "⚠️", info: "ℹ️" };

    function showToast(message, category) {
        category = category || "info";
        var container = document.getElementById("toast-container");
        if (!container) return;

        var toast = document.createElement("div");
        toast.className = "toast toast-" + category;
        toast.innerHTML =
            '<span class="toast-icon">' + (toastIcons[category] || toastIcons.info) + "</span>" +
            '<span class="toast-message">' + message + "</span>" +
            '<button class="toast-close" aria-label="Dismiss">&times;</button>';

        container.appendChild(toast);

        var remove = function () {
            toast.classList.add("toast-hide");
            setTimeout(function () { toast.remove(); }, 350);
        };
        toast.querySelector(".toast-close").addEventListener("click", remove);
        setTimeout(remove, 5500);
    }
    window.showToast = showToast;

    function initFlashToasts() {
        if (window.__flashMessages && Array.isArray(window.__flashMessages)) {
            window.__flashMessages.forEach(function (pair, i) {
                var category = pair[0] === "error" ? "error" : "success";
                setTimeout(function () { showToast(pair[1], category); }, i * 150);
            });
        }
    }

    /* ---------------- Scroll reveal (IntersectionObserver) ---------------- */
    function initScrollReveal() {
        var items = document.querySelectorAll("[data-aos]");
        if (!items.length) return;

        if (!("IntersectionObserver" in window)) {
            items.forEach(function (el) { el.classList.add("aos-visible"); });
            return;
        }

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry, idx) {
                if (entry.isIntersecting) {
                    setTimeout(function () {
                        entry.target.classList.add("aos-visible");
                    }, (idx % 6) * 80);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });

        items.forEach(function (el) { observer.observe(el); });
    }

    /* ---------------- Animated counters ---------------- */
    function initCounters() {
        var counters = document.querySelectorAll("[data-count]");
        if (!counters.length || !("IntersectionObserver" in window)) return;

        var animate = function (el) {
            var target = parseInt(el.getAttribute("data-count"), 10) || 0;
            var duration = 1200;
            var start = null;

            function step(timestamp) {
                if (!start) start = timestamp;
                var progress = Math.min((timestamp - start) / duration, 1);
                el.textContent = Math.floor(progress * target).toLocaleString();
                if (progress < 1) {
                    requestAnimationFrame(step);
                } else {
                    el.textContent = target.toLocaleString();
                }
            }
            requestAnimationFrame(step);
        };

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    animate(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.4 });

        counters.forEach(function (el) { observer.observe(el); });
    }

    /* ---------------- Header shrink on scroll ---------------- */
    function initHeaderScroll() {
        var header = document.getElementById("siteHeader");
        if (!header) return;
        window.addEventListener("scroll", function () {
            if (window.scrollY > 12) header.classList.add("scrolled");
            else header.classList.remove("scrolled");
        });
    }

    /* ---------------- FAQ accordion ---------------- */
    function initFaqAccordion() {
        document.querySelectorAll(".faq-question").forEach(function (q) {
            q.addEventListener("click", function () {
                var item = q.closest(".faq-item");
                var wasOpen = item.classList.contains("open");
                item.parentElement.querySelectorAll(".faq-item").forEach(function (el) {
                    el.classList.remove("open");
                });
                if (!wasOpen) item.classList.add("open");
            });
        });
    }

    /* ---------------- Password visibility toggle ---------------- */
    function initPasswordToggles() {
        document.querySelectorAll(".password-toggle").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var input = btn.previousElementSibling;
                if (!input) return;
                input.type = input.type === "password" ? "text" : "password";
                btn.textContent = input.type === "password" ? "👁️" : "🙈";
            });
        });
    }

    /* ---------------- Client-side form helpers ---------------- */
    function initFormHelpers() {
        var registerForm = document.querySelector('form[data-form="register"]');
        if (registerForm) {
            registerForm.addEventListener("submit", function (e) {
                var password = registerForm.querySelector('[name="password"]');
                var confirm = registerForm.querySelector('[name="confirm_password"]');
                if (password && confirm && password.value !== confirm.value) {
                    e.preventDefault();
                    showToast("Passwords do not match.", "error");
                }
            });
        }

        document.querySelectorAll('input[type="tel"]').forEach(function (input) {
            input.addEventListener("input", function () {
                this.value = this.value.replace(/[^0-9+\-\s]/g, "");
            });
        });

        var dateInputs = document.querySelectorAll('input[type="date"][data-min-today]');
        var today = new Date().toISOString().split("T")[0];
        dateInputs.forEach(function (input) { input.min = today; });
    }

    /* ---------------- Init ---------------- */
    document.addEventListener("DOMContentLoaded", function () {
        initTheme();
        initMobileNav();
        initFlashToasts();
        initScrollReveal();
        initCounters();
        initHeaderScroll();
        initFaqAccordion();
        initPasswordToggles();
        initFormHelpers();
    });
})();
