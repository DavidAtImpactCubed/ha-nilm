const navToggle = document.getElementById("navToggle");
const sidebar = document.getElementById("sidebar");

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
