/**
 * Session history view.
 */
(function () {
  window.PM = window.PM || {};
  window.PM.views = window.PM.views || {};

  function helpers() {
    return window.PM.components;
  }

  async function render(_state) {
    const c = helpers();
    c.setTopbar("History", "Analyses run since the server started");

    const root = c.el("div");
    root.innerHTML = `
      <div style="margin-bottom:18px">
        <div class="section-eyebrow">Workspace</div>
        <h1 class="section-h1">Session history</h1>
        <p class="section-lede">
          Everything you've run since the server started. History clears on restart.
        </p>
      </div>
      <div id="history-host" class="history-list"></div>
    `;
    c.setView(root);

    const host = root.querySelector("#history-host");
    let items = [];
    try {
      const res = await window.PM.api.history();
      items = res.history || [];
    } catch (err) {
      host.innerHTML = `<div class="empty"><h3>Could not load history</h3><p>${c.escapeHtml(
        err.message || ""
      )}</p></div>`;
      return;
    }

    if (!items.length) {
      host.innerHTML = `<div class="empty"><h3>Nothing yet</h3><p>Run a quick answer or full report from the home page or templates gallery.</p></div>`;
      return;
    }

    items.forEach((it) => {
      const isReport = it.kind === "report";
      const row = c.el("a", {
        href: isReport ? `#/report/${it.id}` : "#/home",
        class: "history-row",
      });
      row.appendChild(
        c.el("span", {
          class: "history-row__kind",
          html: it.kind === "report" ? "Report" : "Quick answer",
        })
      );
      row.appendChild(
        c.el("span", {
          class: "history-row__title",
          html: c.escapeHtml(it.title || it.question || ""),
        })
      );
      row.appendChild(
        c.el("span", {
          class: "history-row__when",
          html: `${c.escapeHtml(it.connection_name || "")} · ${c.timeAgo(it.created_at)}`,
        })
      );
      host.appendChild(row);
    });
  }

  window.PM.views.history = { render };
})();
