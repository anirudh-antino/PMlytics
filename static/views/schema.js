/**
 * Schema explorer: tree of tables/collections, click to see columns/fields
 * with a 5-row sample preview.
 */
(function () {
  window.PM = window.PM || {};
  window.PM.views = window.PM.views || {};

  function helpers() {
    return window.PM.components;
  }

  async function render(_state) {
    const c = helpers();
    c.setTopbar("Schema", "Tables, collections, and sample rows");

    const root = c.el("div");
    root.innerHTML = `
      <div style="margin-bottom:18px">
        <div class="section-eyebrow">Workspace</div>
        <h1 class="section-h1">Schema explorer</h1>
        <p class="section-lede">Browse the active connection's structure and inspect a quick sample of any object.</p>
      </div>
      <div class="schema-layout">
        <div class="schema-tree">
          <input id="schema-search" class="schema-tree__search" placeholder="Search tables, columns, fields…" />
          <div id="schema-list"></div>
        </div>
        <div id="schema-detail" class="schema-detail">
          <div class="empty" style="padding:32px 16px">
            <h3>Select an object</h3>
            <p>Click any table or collection to see its columns and a sample of recent rows.</p>
          </div>
        </div>
      </div>
    `;
    c.setView(root);

    const listEl = root.querySelector("#schema-list");
    const search = root.querySelector("#schema-search");
    const detail = root.querySelector("#schema-detail");

    let objects = [];
    let dialect = "";

    try {
      const res = await window.PM.api.schema();
      objects = res.objects || [];
      dialect = res.dialect || "";
    } catch (err) {
      listEl.innerHTML = `<div class="empty"><h3>Could not read schema</h3><p>${c.escapeHtml(
        err.message || ""
      )}</p><a class="btn btn--ghost" style="flex:initial" href="#/connections">Open Connections</a></div>`;
      return;
    }

    if (!objects.length) {
      listEl.innerHTML = `<div class="empty"><h3>Empty schema</h3><p>No tables or collections were returned.</p></div>`;
      return;
    }

    function renderList(filter) {
      listEl.innerHTML = "";
      const f = (filter || "").toLowerCase();
      objects
        .filter((o) => {
          if (!f) return true;
          if (o.name.toLowerCase().includes(f)) return true;
          return (o.columns || []).some((col) => col.name.toLowerCase().includes(f));
        })
        .forEach((o) => {
          const iconSvg =
            o.kind === "collection"
              ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" style="width:14px;height:14px;opacity:.7"><rect x="4" y="6" width="16" height="12" rx="2"/></svg>'
              : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" style="width:14px;height:14px;opacity:.7"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16" stroke-linecap="round"/></svg>';
          const row = c.el("div", {
            class: "schema-item",
            dataset: { name: o.name, kind: o.kind },
          });
          row.appendChild(c.el("span", { html: iconSvg, style: "display:inline-flex" }));
          row.appendChild(c.el("span", { html: c.escapeHtml(o.name) }));
          row.appendChild(
            c.el("span", {
              class: "schema-item__count",
              html: `${(o.columns || []).length}`,
            })
          );
          row.addEventListener("click", () => openDetail(o, row));
          listEl.appendChild(row);
        });
    }

    async function openDetail(obj, rowEl) {
      listEl.querySelectorAll(".schema-item").forEach((e) => e.classList.remove("is-active"));
      if (rowEl) rowEl.classList.add("is-active");

      detail.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px">
          <div>
            <div class="section-eyebrow">${c.escapeHtml(obj.kind)}</div>
            <h2 class="section-h1" style="font-size:18px">${c.escapeHtml(obj.name)}</h2>
            <p class="section-lede" style="font-size:12px;color:var(--muted)">${(obj.columns || []).length} ${
              obj.kind === "collection" ? "fields" : "columns"
            }${dialect ? ` · ${c.escapeHtml(dialect)}` : ""}</p>
          </div>
          <button id="copy-name" class="btn btn--ghost" style="flex:initial">Copy name</button>
        </div>
        <table class="schema-cols-table">
          <thead><tr><th>Name</th><th>Type</th></tr></thead>
          <tbody>
            ${(obj.columns || [])
              .map(
                (col) =>
                  `<tr><td>${c.escapeHtml(col.name)}</td><td style="color:var(--muted)">${c.escapeHtml(col.type || "")}</td></tr>`
              )
              .join("")}
          </tbody>
        </table>
        <div class="section-h2" style="margin:18px 0 8px">Sample rows</div>
        <div id="sample-host">
          <div class="skel skel-row"></div>
          <div class="skel skel-row"></div>
          <div class="skel skel-row"></div>
        </div>
      `;
      detail.querySelector("#copy-name").addEventListener("click", () => {
        navigator.clipboard.writeText(obj.name).then(
          () => c.showToast("Copied"),
          () => c.showToast("Could not copy", "error")
        );
      });

      const host = detail.querySelector("#sample-host");
      try {
        const res = await window.PM.api.schemaSample(undefined, obj.name, 5);
        host.innerHTML = "";
        if (res.rows && res.rows.length) {
          host.appendChild(c.previewTable(res.columns, res.rows, 25));
        } else {
          host.innerHTML = `<div class="empty" style="padding:24px"><h3>No rows</h3><p>The object exists but no sample rows were returned.</p></div>`;
        }
      } catch (err) {
        host.innerHTML = `<div class="empty" style="padding:24px"><h3>Could not load sample</h3><p>${c.escapeHtml(
          err.message || ""
        )}</p></div>`;
      }
    }

    search.addEventListener("input", (e) => renderList(e.target.value));
    renderList("");
  }

  window.PM.views.schema = { render };
})();
