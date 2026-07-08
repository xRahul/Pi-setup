/* Custom JS for Homepage */

(() => {
  const filterId = "homepage-service-filter";
  const hiddenClass = "homepage-service-filter-hidden";
  const cardSelector = ".services .service-card";
  let query = "";
  let applying = false;
  let scheduled = 0;

  function serviceCards() {
    return Array.from(document.querySelectorAll(cardSelector));
  }

  function serviceName(card) {
    const explicitName = card.getAttribute("aria-label") || card.getAttribute("title");
    if (explicitName) return explicitName;

    const text = (card.innerText || card.textContent || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    return text[0] || "";
  }

  function serviceGroups(cards) {
    const grids = new Set(
      cards
        .map((card) => card.closest(".services"))
        .filter(Boolean)
    );

    return Array.from(grids).map((grid) => {
      const parent = grid.parentElement;
      const group = parent && parent.querySelectorAll(".services").length === 1 ? parent : grid;
      return { grid, group };
    });
  }

  function applyFilter() {
    if (applying) return;
    applying = true;

    const needle = query.trim().toLowerCase();
    const cards = serviceCards();

    cards.forEach((card) => {
      const matches = !needle || serviceName(card).toLowerCase().includes(needle);
      card.classList.toggle(hiddenClass, !matches);
    });

    serviceGroups(cards).forEach(({ grid, group }) => {
      const visibleCards = Array.from(grid.querySelectorAll(".service-card"))
        .some((card) => !card.classList.contains(hiddenClass));
      group.classList.toggle(hiddenClass, Boolean(needle) && !visibleCards);
    });

    applying = false;
  }

  function scheduleFilter() {
    window.clearTimeout(scheduled);
    scheduled = window.setTimeout(applyFilter, 80);
  }

  function ensureFilter() {
    const cards = serviceCards();
    if (!cards.length || document.getElementById(filterId)) return;

    const firstGrid = cards[0].closest(".services");
    if (!firstGrid) return;

    const wrapper = document.createElement("div");
    wrapper.className = "homepage-service-filter";

    const input = document.createElement("input");
    input.id = filterId;
    input.type = "search";
    input.placeholder = "Filter services";
    input.autocomplete = "off";
    input.setAttribute("aria-label", "Filter services by name");
    input.value = query;

    input.addEventListener("input", () => {
      query = input.value;
      scheduleFilter();
    });

    wrapper.appendChild(input);
    firstGrid.before(wrapper);
    applyFilter();
  }

  const observer = new MutationObserver(() => {
    ensureFilter();
    scheduleFilter();
  });

  function start() {
    ensureFilter();
    applyFilter();
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
