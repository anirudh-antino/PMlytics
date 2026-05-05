/**
 * Connections view: list existing connections, add a new one (per-type tabs
 * with proper fields, plus a Raw URL fallback tab), activate, delete.
 */
(function () {
  window.PM = window.PM || {};
  window.PM.views = window.PM.views || {};

  function helpers() {
    return window.PM.components;
  }

  const TYPE_DEFAULTS = {
    postgresql: { port: 5432, label: "PostgreSQL" },
    mysql: { port: 3306, label: "MySQL" },
    mongodb: { port: 27017, label: "MongoDB" },
  };

  const RAW_PLACEHOLDERS = {
    postgresql: "postgresql+psycopg2://user:pass@host:5432/db",
    mysql: "mysql+pymysql://user:pass@host:3306/db",
    mongodb: "mongodb://user:pass@host:27017/db",
  };

  async function render(_state) {
    const c = helpers();
    c.setTopbar("Connections", "Read-only Postgres, MySQL, or MongoDB");

    const root = c.el("div");
    root.innerHTML = `
      <div style="margin-bottom:18px">
        <div class="section-eyebrow">Workspace</div>
        <h1 class="section-h1">Database connections</h1>
        <p class="section-lede">
          Connect read-only Postgres, MySQL, or MongoDB. Saved configurations
          (including credentials) are persisted in your browser's localStorage
          so they survive restarts. The server holds them in memory only.
        </p>
      </div>

      <div class="card card--pad-lg" style="margin-bottom:24px">
        <div class="section-eyebrow" style="margin-bottom:6px">Add connection</div>

        <div class="tabs" id="conn-type-tabs">
          <button class="tab-btn is-active" data-type="postgresql" type="button">PostgreSQL</button>
          <button class="tab-btn" data-type="mysql" type="button">MySQL</button>
          <button class="tab-btn" data-type="mongodb" type="button">MongoDB</button>
        </div>

        <div class="tabs" id="conn-mode-tabs" style="margin-top:-8px">
          <button class="tab-btn is-active" data-mode="form" type="button">Fields</button>
          <button class="tab-btn" data-mode="raw" type="button">Raw URL</button>
        </div>

        <div id="conn-form-fields"></div>
        <div id="conn-form-raw" style="display:none"></div>

        <div style="display:flex;align-items:center;gap:10px;margin-top:14px">
          <button id="conn-test" class="btn btn--primary" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Test &amp; save
          </button>
          <span id="conn-form-status" style="font-size:12.5px;color:var(--muted)"></span>
        </div>
      </div>

      <div class="section-h2">Saved connections</div>
      <div id="conn-list" class="conn-list"></div>
    `;
    c.setView(root);

    const fieldsHost = root.querySelector("#conn-form-fields");
    const rawHost = root.querySelector("#conn-form-raw");
    const status = root.querySelector("#conn-form-status");
    const listHost = root.querySelector("#conn-list");

    let activeType = "postgresql";
    let activeMode = "form";

    function fieldsFor(type) {
      const def = TYPE_DEFAULTS[type] || TYPE_DEFAULTS.postgresql;
      const isMongo = type === "mongodb";
      fieldsHost.innerHTML = `
        <div style="display:grid;gap:12px;grid-template-columns:1fr 1fr">
          <div style="grid-column:1 / -1">
            <label class="field-label" for="f-name">Connection name</label>
            <input id="f-name" class="input" placeholder="${def.label} prod read-replica" />
          </div>
          <div>
            <label class="field-label" for="f-host">Host</label>
            <input id="f-host" class="input input--mono" placeholder="db.internal" />
          </div>
          <div>
            <label class="field-label" for="f-port">Port</label>
            <input id="f-port" class="input input--mono" placeholder="${def.port}" />
          </div>
          <div>
            <label class="field-label" for="f-database">${isMongo ? "Database" : "Database"}</label>
            <input id="f-database" class="input input--mono" placeholder="analytics" />
          </div>
          <div>
            <label class="field-label" for="f-user">User</label>
            <input id="f-user" class="input input--mono" placeholder="readonly" />
          </div>
          <div style="grid-column:1 / -1">
            <label class="field-label" for="f-password">Password</label>
            <input id="f-password" class="input input--mono" type="password" autocomplete="off" />
          </div>
          <div>
            <label style="display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--ink2)">
              <input id="f-ssl" type="checkbox" /> Require SSL/TLS
            </label>
          </div>
        </div>
      `;
    }

    function rawFor(type) {
      const placeholder = RAW_PLACEHOLDERS[type] || RAW_PLACEHOLDERS.postgresql;
      rawHost.innerHTML = `
        <div>
          <label class="field-label" for="f-name-raw">Connection name</label>
          <input id="f-name-raw" class="input" placeholder="Production" />
        </div>
        <div style="margin-top:12px">
          <label class="field-label" for="f-raw">Connection URL</label>
          <textarea id="f-raw" class="textarea textarea--mono" rows="3" placeholder="${placeholder}"></textarea>
          <div class="field-help">SQLAlchemy URL for SQL, or a standard <code>mongodb://</code> URI for MongoDB.</div>
        </div>
      `;
    }

    function setType(t) {
      activeType = t;
      root.querySelectorAll("#conn-type-tabs .tab-btn").forEach((b) => {
        b.classList.toggle("is-active", b.dataset.type === t);
      });
      fieldsFor(t);
      rawFor(t);
    }

    function setMode(m) {
      activeMode = m;
      root.querySelectorAll("#conn-mode-tabs .tab-btn").forEach((b) => {
        b.classList.toggle("is-active", b.dataset.mode === m);
      });
      fieldsHost.style.display = m === "form" ? "" : "none";
      rawHost.style.display = m === "raw" ? "" : "none";
    }

    setType("postgresql");
    setMode("form");

    root.querySelectorAll("#conn-type-tabs .tab-btn").forEach((b) => {
      b.addEventListener("click", () => setType(b.dataset.type));
    });
    root.querySelectorAll("#conn-mode-tabs .tab-btn").forEach((b) => {
      b.addEventListener("click", () => setMode(b.dataset.mode));
    });

    root.querySelector("#conn-test").addEventListener("click", async () => {
      status.textContent = "Connecting…";
      status.style.color = "var(--muted)";
      let body;
      if (activeMode === "form") {
        const name = root.querySelector("#f-name").value.trim();
        const host = root.querySelector("#f-host").value.trim();
        const portStr = root.querySelector("#f-port").value.trim();
        const database = root.querySelector("#f-database").value.trim();
        const user = root.querySelector("#f-user").value.trim();
        const password = root.querySelector("#f-password").value;
        const ssl = root.querySelector("#f-ssl").checked;
        body = {
          name: name || `${TYPE_DEFAULTS[activeType].label} connection`,
          type: activeType,
          host,
          port: portStr ? Number(portStr) : null,
          database,
          user,
          password,
          ssl,
          options: {},
        };
      } else {
        const name = root.querySelector("#f-name-raw").value.trim();
        const raw = root.querySelector("#f-raw").value.trim();
        body = {
          name: name || `${TYPE_DEFAULTS[activeType].label} connection`,
          type: activeType,
          raw_url: raw,
        };
      }

      try {
        const created = await window.PM.api.addConnection(body);
        try {
          window.PM.storage.saveConnection(body);
          if (created && created.is_active) {
            window.PM.storage.setActiveName(created.name);
          }
        } catch {}
        status.textContent = "Saved.";
        status.style.color = "var(--ok)";
        await window.PM.app.refreshStatus();
        await loadList();
        // reset form
        if (activeMode === "form") {
          ["f-host", "f-port", "f-database", "f-user", "f-password", "f-name"].forEach((id) => {
            const e = root.querySelector(`#${id}`);
            if (e) e.value = "";
          });
          root.querySelector("#f-ssl").checked = false;
        } else {
          root.querySelector("#f-raw").value = "";
          root.querySelector("#f-name-raw").value = "";
        }
        c.showToast("Connection saved");
      } catch (err) {
        status.textContent = String(err.message || err);
        status.style.color = "var(--danger)";
      }
    });

    async function loadList() {
      listHost.innerHTML = "";
      let conns = [];
      try {
        const res = await window.PM.api.listConnections();
        conns = res.connections || [];
      } catch (err) {
        listHost.innerHTML = `<div class="empty"><h3>Could not load connections</h3><p>${c.escapeHtml(
          err.message || ""
        )}</p></div>`;
        return;
      }
      if (!conns.length) {
        listHost.innerHTML = `
          <div class="empty">
            <h3>No connections yet</h3>
            <p>Add a Postgres, MySQL, or MongoDB connection above. The active connection is used for every analysis. Saved here, persisted in your browser.</p>
          </div>`;
        return;
      }
      conns.forEach((conn) => {
        const card = c.el("div", {
          class: "conn-card" + (conn.is_active ? " is-active" : ""),
        });
        const head = c.el("div", { class: "conn-card__head" });
        head.appendChild(c.el("span", { class: "conn-card__title", html: c.escapeHtml(conn.name) }));
        head.appendChild(c.el("span", { class: "conn-card__type", html: c.escapeHtml(conn.dialect || conn.type) }));
        card.appendChild(head);

        const meta = conn.has_raw_url
          ? "Raw URL connection"
          : `${conn.user || "?"}@${conn.host || "?"}:${conn.port || "?"} / ${conn.database || ""}`;
        card.appendChild(c.el("div", { class: "conn-card__meta", html: c.escapeHtml(meta) }));

        const actions = c.el("div", { class: "conn-card__actions" });
        if (conn.is_active) {
          actions.appendChild(
            c.el("span", {
              style:
                "display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--ok);font-weight:600",
              html: '<span class="dot dot--ok"></span> Active',
            })
          );
        } else {
          const actBtn = c.el(
            "button",
            { class: "btn btn--ghost", style: "flex:initial" },
            "Use this connection"
          );
          actBtn.addEventListener("click", async () => {
            try {
              await window.PM.api.activateConnection(conn.id);
              try { window.PM.storage.setActiveName(conn.name); } catch {}
              await window.PM.app.refreshStatus();
              await loadList();
              c.showToast("Active connection switched");
            } catch (err) {
              c.showToast(err.message || String(err), "error");
            }
          });
          actions.appendChild(actBtn);
        }
        const delBtn = c.el(
          "button",
          { class: "btn btn--danger", style: "flex:initial;margin-left:auto" },
          "Remove"
        );
        delBtn.addEventListener("click", async () => {
          if (!confirm(`Remove connection "${conn.name}"?`)) return;
          try {
            await window.PM.api.removeConnection(conn.id);
            try {
              window.PM.storage.removeConnectionByName(conn.name);
              if (window.PM.storage.getActiveName() === conn.name) {
                window.PM.storage.setActiveName(null);
              }
            } catch {}
            await window.PM.app.refreshStatus();
            await loadList();
            c.showToast("Connection removed");
          } catch (err) {
            c.showToast(err.message || String(err), "error");
          }
        });
        actions.appendChild(delBtn);
        card.appendChild(actions);

        listHost.appendChild(card);
      });
    }

    await loadList();
  }

  window.PM.views.connections = { render };
})();
