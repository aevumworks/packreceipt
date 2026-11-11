"use strict";
(() => {
  const rows = [...document.querySelectorAll(".file-row")];
  const search = document.querySelector("#search");
  const filters = [...document.querySelectorAll("[data-filter]")];
  const counter = document.querySelector("#visible-count");
  let filter = "changes";
  function update() {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const row of rows) {
      const kind = row.dataset.kind;
      const statusMatch = filter === "all" || (filter === "changes" ? kind !== "unchanged" : kind === filter);
      const textMatch = row.dataset.search.toLocaleLowerCase().includes(query);
      row.hidden = !(statusMatch && textMatch);
      if (!row.hidden) visible++;
    }
    counter.textContent = `${counter.dataset.prefix} ${visible} ${counter.dataset.of} ${counter.dataset.total}`;
    document.querySelector("#empty").hidden = visible !== 0;
    for (const button of filters) {
      const selected = button.dataset.filter === filter;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    }
  }
  filters.forEach(button => button.addEventListener("click", () => { filter = button.dataset.filter; update(); }));
  search.addEventListener("input", update);
  document.querySelector("#print").addEventListener("click", () => window.print());
  if (rows.every(row => row.dataset.kind === "unchanged")) filter = "all";
  update();
})();
