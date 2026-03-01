/* Madison Events - Client-side interactivity */

document.addEventListener("DOMContentLoaded", function () {
    // Source filtering
    const filterBtns = document.querySelectorAll(".filter-btn[data-source]");
    const eventCards = document.querySelectorAll(".event-card");
    const calendarEvents = document.querySelectorAll(".calendar-event");

    filterBtns.forEach(function (btn) {
        btn.addEventListener("click", function () {
            filterBtns.forEach(function (b) { b.classList.remove("active"); });
            btn.classList.add("active");

            const source = btn.dataset.source;

            eventCards.forEach(function (card) {
                if (source === "all" || card.dataset.source === source) {
                    card.style.display = "";
                } else {
                    card.style.display = "none";
                }
            });

            calendarEvents.forEach(function (ev) {
                if (source === "all" || ev.dataset.source === source) {
                    ev.style.display = "";
                } else {
                    ev.style.display = "none";
                }
            });
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
        var hiddenCount = 0;

        dateSections.forEach(function (section) {
            if (section.dataset.date < today) {
                section.style.display = showingPast ? "" : "none";
                if (!showingPast) {
                    hiddenCount += section.querySelectorAll(".event-card").length;
                }
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

    // Nav tab filtering (All Events / This Week / Weekend)
    var navTabs = document.querySelectorAll(".nav-tab[data-tab]");
    var activeTab = "all";

    function toISO(d) {
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, "0");
        var dd = String(d.getDate()).padStart(2, "0");
        return y + "-" + m + "-" + dd;
    }

    function getThisWeekDates() {
        var today = new Date();
        today.setHours(0, 0, 0, 0);
        var end = new Date(today);
        end.setDate(end.getDate() + 7);
        return { start: toISO(today), end: toISO(end) };
    }

    function getWeekendDates() {
        var today = new Date();
        today.setHours(0, 0, 0, 0);
        var day = today.getDay(); // 0=Sun, 6=Sat
        var sat;
        if (day === 6) {
            sat = new Date(today);
        } else if (day === 0) {
            // Sunday: show current weekend (yesterday Sat + today Sun)
            sat = new Date(today);
            sat.setDate(sat.getDate() - 1);
        } else {
            sat = new Date(today);
            sat.setDate(sat.getDate() + (6 - day));
        }
        var sun = new Date(sat);
        sun.setDate(sun.getDate() + 1);
        return [toISO(sat), toISO(sun)];
    }

    function applyTabFilter() {
        var dateSections = document.querySelectorAll(".date-section[data-date]");
        var calendarDays = document.querySelectorAll(".calendar-day[data-date]");
        var inlineCTA = document.querySelector(".newsletter-inline-cta");
        var today = getTodayISO();

        if (activeTab === "all") {
            // Restore default: respect past-events toggle
            dateSections.forEach(function (section) {
                if (!showingPast && section.dataset.date < today) {
                    section.style.display = "none";
                } else {
                    section.style.display = "";
                }
            });
            calendarDays.forEach(function (day) {
                if (!showingPast && day.dataset.date < today) {
                    day.style.display = "none";
                } else {
                    day.style.display = "";
                }
            });
            if (inlineCTA) inlineCTA.style.display = "";
            return;
        }

        if (inlineCTA) inlineCTA.style.display = "none";

        var allowed;
        if (activeTab === "this-week") {
            var range = getThisWeekDates();
            allowed = function (d) { return d >= range.start && d < range.end; };
        } else if (activeTab === "weekend") {
            var weekendDays = getWeekendDates();
            allowed = function (d) { return weekendDays.indexOf(d) !== -1; };
        }

        dateSections.forEach(function (section) {
            section.style.display = allowed(section.dataset.date) ? "" : "none";
        });
        calendarDays.forEach(function (day) {
            day.style.display = allowed(day.dataset.date) ? "" : "none";
        });
    }

    navTabs.forEach(function (tab) {
        tab.addEventListener("click", function (e) {
            e.preventDefault();
            navTabs.forEach(function (t) { t.classList.remove("active"); });
            tab.classList.add("active");
            activeTab = tab.dataset.tab;
            applyTabFilter();
        });
    });

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
