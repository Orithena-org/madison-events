/* Madison Events - Client-side interactivity */

document.addEventListener("DOMContentLoaded", function () {
    var eventCards = document.querySelectorAll(".event-card");
    var calendarEvents = document.querySelectorAll(".calendar-event");

    // Active filters
    var activeSource = "all";
    var activeCategory = "all";

    function applyFilters() {
        eventCards.forEach(function (card) {
            var sourceMatch = activeSource === "all" || card.dataset.source === activeSource;
            var categoryMatch = activeCategory === "all" || card.dataset.category === activeCategory;
            card.style.display = (sourceMatch && categoryMatch) ? "" : "none";
        });

        calendarEvents.forEach(function (ev) {
            var sourceMatch = activeSource === "all" || ev.dataset.source === activeSource;
            ev.style.display = sourceMatch ? "" : "none";
        });

        // Update visible event count
        var statsBar = document.querySelector(".stats-bar span");
        if (statsBar) {
            var visible = 0;
            eventCards.forEach(function (card) {
                if (card.style.display !== "none") visible++;
            });
            statsBar.textContent = visible + " events";
        }
    }

    // Source filtering
    var sourceFilterBtns = document.querySelectorAll(".filter-btn[data-source]");
    sourceFilterBtns.forEach(function (btn) {
        btn.addEventListener("click", function () {
            sourceFilterBtns.forEach(function (b) { b.classList.remove("active"); });
            btn.classList.add("active");
            activeSource = btn.dataset.source;
            applyFilters();
        });
    });

    // Category filtering
    var categoryFilterBtns = document.querySelectorAll(".filter-btn[data-category]");
    categoryFilterBtns.forEach(function (btn) {
        btn.addEventListener("click", function () {
            categoryFilterBtns.forEach(function (b) { b.classList.remove("active"); });
            btn.classList.add("active");
            activeCategory = btn.dataset.category;
            applyFilters();
        });
    });

    // View toggle (list vs calendar)
    var viewBtns = document.querySelectorAll(".view-btn");
    var listView = document.getElementById("events-list");
    var calView = document.getElementById("events-calendar");

    viewBtns.forEach(function (btn) {
        btn.addEventListener("click", function () {
            viewBtns.forEach(function (b) { b.classList.remove("active"); });
            btn.classList.add("active");

            var view = btn.dataset.view;
            if (view === "calendar") {
                listView.style.display = "none";
                calView.style.display = "";
            } else {
                listView.style.display = "";
                calView.style.display = "none";
            }
        });
    });

    // Past events filtering
    var showPastBtn = document.getElementById("show-past-btn");
    var showingPast = false;

    function getTodayISO() {
        var now = new Date();
        var y = now.getFullYear();
        var m = String(now.getMonth() + 1).padStart(2, "0");
        var d = String(now.getDate()).padStart(2, "0");
        return y + "-" + m + "-" + d;
    }

    function updatePastVisibility() {
        var today = getTodayISO();
        var dateSections = document.querySelectorAll(".date-section[data-date]");
        var calendarDays = document.querySelectorAll(".calendar-day[data-date]");

        dateSections.forEach(function (section) {
            if (section.dataset.date < today) {
                section.style.display = showingPast ? "" : "none";
            }
        });

        calendarDays.forEach(function (day) {
            if (day.dataset.date < today) {
                day.style.display = showingPast ? "" : "none";
            }
        });

        if (showPastBtn) {
            showPastBtn.textContent = showingPast ? "Hide Past Events" : "Show Past Events";
            if (showingPast) {
                showPastBtn.classList.add("active");
            } else {
                showPastBtn.classList.remove("active");
            }
        }
    }

    // Hide past events on page load
    updatePastVisibility();

    if (showPastBtn) {
        showPastBtn.addEventListener("click", function () {
            showingPast = !showingPast;
            updatePastVisibility();
        });
    }

    // Newsletter form
    var forms = document.querySelectorAll(".newsletter-form, .newsletter-form-large");
    forms.forEach(function (form) {
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var email = form.querySelector("input[type='email']").value;
            alert("Thanks for subscribing! We'll send Madison events to " + email + " weekly.");
            form.reset();
        });
    });
});
