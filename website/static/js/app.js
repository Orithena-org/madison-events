/* Madison Events - Client-side interactivity */

document.addEventListener("DOMContentLoaded", function () {
    // Source filtering
    const filterBtns = document.querySelectorAll(".filter-btn");
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
