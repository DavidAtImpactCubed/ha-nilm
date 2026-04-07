const navToggle = document.getElementById("navToggle");
const sidebar = document.getElementById("sidebar");
const trackedSections = new Set();
const trackedDepths = new Set();

function sendTrackingEvent(payload) {
    const body = JSON.stringify({
        ...payload,
        path: window.location.pathname,
        referrer: document.referrer || "",
        screen: `${window.innerWidth}x${window.innerHeight}`,
        tz_offset: new Date().getTimezoneOffset(),
    });

    if (navigator.sendBeacon) {
        const blob = new Blob([body], { type: "application/json" });
        navigator.sendBeacon("./track.php", blob);
        return;
    }

    fetch("./track.php", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive: true,
    }).catch(() => {});
}

if (navToggle && sidebar) {
    navToggle.addEventListener("click", () => {
        const isOpen = sidebar.classList.toggle("is-open");
        navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });

    sidebar.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            sidebar.classList.remove("is-open");
            navToggle.setAttribute("aria-expanded", "false");
        });
    });
}

sendTrackingEvent({ type: "page_view", label: "docs-index" });

document.querySelectorAll("[data-track]").forEach((element) => {
    element.addEventListener("click", () => {
        sendTrackingEvent({
            type: element.getAttribute("data-track") || "cta",
            label: element.getAttribute("data-track-label") || element.textContent.trim(),
        });
    });
});

const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
        if (!entry.isIntersecting) {
            return;
        }
        const target = entry.target;
        if (!target.id || trackedSections.has(target.id)) {
            return;
        }
        trackedSections.add(target.id);
        sendTrackingEvent({ type: "section_view", section: target.id });
    });
}, { threshold: 0.45 });

document.querySelectorAll(".doc-section").forEach((section) => observer.observe(section));

window.addEventListener("scroll", () => {
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    if (scrollable <= 0) {
        return;
    }
    const depth = Math.round((window.scrollY / scrollable) * 100);
    [25, 50, 75, 100].forEach((mark) => {
        if (depth >= mark && !trackedDepths.has(mark)) {
            trackedDepths.add(mark);
            sendTrackingEvent({ type: "scroll_depth", label: `${mark}%` });
        }
    });
}, { passive: true });
