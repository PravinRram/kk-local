const showMoreBtn = document.querySelector("[data-show-more]");
if (showMoreBtn) {
  showMoreBtn.addEventListener("click", () => {
    document.querySelectorAll("[data-mutual-list] .mutual-card.is-hidden").forEach((card) => {
      card.classList.remove("is-hidden");
    });
    showMoreBtn.classList.add("is-hidden");
  });
}
