feather.replace();

document.querySelectorAll("[data-dismiss]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = document.querySelector(button.dataset.dismiss);
    if (target) {
      target.classList.add("is-hidden");
    }
    document.body.classList.add("guide-hidden");
  });
});

const navToggle = document.querySelector("[data-nav-toggle]");
const navBackdrop = document.querySelector("[data-nav-backdrop]");
const navClose = document.querySelector("[data-nav-close]");

const setNavOpen = (isOpen) => {
  document.body.classList.toggle("nav-open", isOpen);
  if (navToggle) {
    navToggle.setAttribute("aria-expanded", String(isOpen));
  }
};

if (navToggle) {
  navToggle.addEventListener("click", () => {
    const isOpen = document.body.classList.contains("nav-open");
    setNavOpen(!isOpen);
  });
}

if (navBackdrop) {
  navBackdrop.addEventListener("click", () => setNavOpen(false));
}

if (navClose) {
  navClose.addEventListener("click", () => setNavOpen(false));
}
