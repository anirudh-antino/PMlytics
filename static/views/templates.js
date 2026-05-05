/**
 * Templates view: gallery of PM templates. Clicking one opens a parameter
 * panel; "Run" calls /api/report with template_id + params.
 */
(function () {
  window.PM = window.PM || {};
  window.PM.views = window.PM.views || {};

  function helpers() {
    return window.PM.components;
  }

  const ICONS = {
    funnel:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M3 4h18l-7 9v6l-4 2v-8L3 4z" stroke-linejoin="round"/></svg>',
    steps:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M4 20h4v-4H4v4zm6-6h4v-4h-4v4zm6-6h4V4h-4v4z" stroke-linejoin="round"/></svg>',
    grid:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>',
    spark:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M3 17l5-7 4 4 4-6 5 4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    currency:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="12" cy="12" r="9"/><path d="M14 9c-.7-.7-1.7-1-2.5-1-1.4 0-2.5.9-2.5 2 0 1.2 1.1 1.7 3 2 1.9.3 3 .8 3 2 0 1.1-1.1 2-2.5 2-1 0-2-.4-2.6-1.2M12 6v2M12 16v2" stroke-linecap="round"/></svg>',
    sparkle:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3zM19 15l.7 1.8L21.5 17l-1.8.7L19 19l-.7-1.3L17 17l1.5-.2L19 15z"/></svg>',
  };

  async function render(_state) {
    const c = helpers();
    c.setTopbar("Templates", "Pre-built PM lenses");

    let templates = [];
    try {
      const res = await window.PM.api.templates();
      templates = res.templates || [];
    } catch (err) {
      const root = c.el("div");
      root.innerHTML = `<div class="empty"><h3>Could not load templates</h3><p>${c.escapeHtml(
        err.message || ""
      )}</p></div>`;
      c.setView(root);
      return;
    }

    const root = c.el("div");
    root.innerHTML = `
      <div style="margin-bottom:18px">
        <div class="section-eyebrow">Workspace</div>
        <h1 class="section-h1">Templates</h1>
        <p class="section-lede">
          Each template is a PM lens with priors. Pick one, fill the params, and
          we'll plan the queries and synthesize a sectioned report.
        </p>
      </div>
      <div id="template-grid" class="template-grid"></div>
      <div id="template-panel" style="margin-top:24px;display:none"></div>
    `;
    c.setView(root);

    const grid = root.querySelector("#template-grid");
    const panel = root.querySelector("#template-panel");

    templates.forEach((t) => {
      const card = c.el("button", { class: "template-card", type: "button" });
      const icon = c.el("span", { class: "template-icon", html: ICONS[t.icon] || ICONS.sparkle });
      card.appendChild(icon);
      card.appendChild(c.el("div", { class: "template-card__title", html: c.escapeHtml(t.name) }));
      card.appendChild(c.el("div", { class: "template-card__tagline", html: c.escapeHtml(t.tagline) }));
      card.addEventListener("click", () => openPanel(t));
      grid.appendChild(card);
    });

    function openPanel(t) {
      panel.style.display = "";
      panel.innerHTML = `
        <div class="card card--pad-lg">
          <div class="section-eyebrow">${c.escapeHtml(t.name)}</div>
          <h2 class="section-h1" style="font-size:20px">${c.escapeHtml(t.tagline)}</h2>
          <div id="param-fields" style="display:grid;gap:12px;margin-top:14px"></div>
          <div style="margin-top:14px">
            <label class="field-label" for="t-question">Question to focus on (optional)</label>
            <textarea id="t-question" class="textarea" rows="2" placeholder="Free-text override of the default focus question"></textarea>
          </div>
          <div style="display:flex;gap:10px;align-items:center;margin-top:14px">
            <button id="t-run" class="btn btn--primary" type="button">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 3l14 9-14 9V3z" stroke-linejoin="round"/></svg>
              Run report
            </button>
            <button id="t-cancel" class="btn btn--ghost" type="button">Cancel</button>
            <span id="t-status" style="font-size:12.5px;color:var(--muted)"></span>
          </div>
        </div>
      `;
      const fields = panel.querySelector("#param-fields");
      (t.params || []).forEach((p) => {
        const wrap = c.el("div");
        wrap.appendChild(c.el("label", { class: "field-label", for: `p-${p.id}`, html: c.escapeHtml(p.label) }));
        if (p.type === "select") {
          const sel = c.el("select", { id: `p-${p.id}`, class: "select" });
          (p.options || []).forEach((opt) => {
            const o = document.createElement("option");
            o.value = opt;
            o.textContent = opt;
            if (opt === p.default) o.selected = true;
            sel.appendChild(o);
          });
          wrap.appendChild(sel);
        } else if (p.type === "number") {
          const inp = c.el("input", {
            id: `p-${p.id}`,
            class: "input input--mono",
            type: "number",
            value: p.default ?? "",
          });
          wrap.appendChild(inp);
        } else {
          const inp = c.el("input", {
            id: `p-${p.id}`,
            class: "input",
            placeholder: p.placeholder || "",
            value: p.default ?? "",
          });
          wrap.appendChild(inp);
        }
        fields.appendChild(wrap);
      });

      panel.querySelector("#t-cancel").addEventListener("click", () => {
        panel.style.display = "none";
        panel.innerHTML = "";
      });

      panel.querySelector("#t-run").addEventListener("click", async () => {
        const params = {};
        (t.params || []).forEach((p) => {
          const e = panel.querySelector(`#p-${p.id}`);
          if (e) params[p.id] = e.value;
        });
        const question =
          panel.querySelector("#t-question").value.trim() || `${t.name}: ${t.tagline}`;
        window.PM.app.runAnalysis({
          mode: "report",
          question,
          template_id: t.id,
          params,
        });
      });
    }
  }

  window.PM.views.templates = { render };
})();
