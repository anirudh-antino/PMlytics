/**
 * App bootstrap: tiny hash router + global status + analysis orchestrator.
 *
 * Routes:
 *   #/home (default)
 *   #/templates
 *   #/connections
 *   #/schema
 *   #/history
 *   #/settings
 *   #/report/<id>
 */
(function () {
  window.PM = window.PM || {};
  window.PM.state = {
    activeConnectionId: null,
    activeConnectionName: null,
    dialect: null,
    hasAnthropic: false,
    hasOpenai: false,
    hasGemini: false,
    anthropicModel: "",
    openaiModel: "",
    geminiModel: "",
    llmProvider: "auto",
  };

  function components() {
    return window.PM.components;
  }

  const ROUTES = {
    home: () => window.PM.views.home.render(window.PM.state),
    templates: () => window.PM.views.templates.render(window.PM.state),
    connections: () => window.PM.views.connections.render(window.PM.state),
    schema: () => window.PM.views.schema.render(window.PM.state),
    history: () => window.PM.views.history.render(window.PM.state),
    settings: () => window.PM.views.settings.render(window.PM.state),
  };

  async function navigate(name, params) {
    const target = name === "home" || !name ? "#/home" : `#/${name}${params ? `/${params}` : ""}`;
    if (location.hash !== target) {
      location.hash = target;
    } else {
      handleRoute();
    }
  }

  function setActiveNav(name) {
    document.querySelectorAll(".nav-item").forEach((el) => {
      el.classList.toggle("is-active", el.dataset.route === name);
    });
  }

  async function handleRoute() {
    const hash = location.hash.replace(/^#\/?/, "") || "home";
    const parts = hash.split("/");
    const route = parts[0];

    window.PM.charts && window.PM.charts.disposeAll();

    if (route === "report" && parts[1]) {
      setActiveNav("history");
      try {
        const rep = await window.PM.api.getReport(parts[1]);
        window.PM.views.report.renderReport(rep);
      } catch (err) {
        const c = components();
        const root = c.el("div");
        root.innerHTML = `<div class="empty"><h3>Report not found</h3><p>${c.escapeHtml(
          err.message || ""
        )}</p><a class="btn btn--ghost" style="flex:initial" href="#/home">Back to home</a></div>`;
        c.setView(root);
      }
      return;
    }

    const fn = ROUTES[route] || ROUTES.home;
    setActiveNav(ROUTES[route] ? route : "home");
    try {
      await fn();
    } catch (err) {
      const c = components();
      const root = c.el("div");
      root.innerHTML = `<div class="empty"><h3>Couldn't load this view</h3><p>${c.escapeHtml(
        err.message || ""
      )}</p></div>`;
      c.setView(root);
    }
  }

  async function refreshStatus() {
    const c = components();
    const switcher = document.getElementById("conn-switcher");
    const modelSwitcher = document.getElementById("model-switcher");
    const chip = document.getElementById("active-conn-chip");

    let status = null;
    let conns = { connections: [] };
    try {
      [status, conns] = await Promise.all([
        window.PM.api.status(),
        window.PM.api.listConnections(),
      ]);
    } catch (err) {
      if (chip) {
        chip.querySelector(".dot").className = "dot dot--idle";
        chip.querySelector(".active-conn-name").textContent = "Server unreachable";
      }
      return;
    }

    const active = status.active_connection;
    window.PM.state.activeConnectionId = active ? active.id : null;
    window.PM.state.activeConnectionName = active ? active.name : null;
    window.PM.state.dialect = active ? active.dialect : null;
    window.PM.state.hasAnthropic = !!status.has_anthropic_key;
    window.PM.state.hasOpenai = !!status.has_openai_key;
    window.PM.state.hasGemini = !!status.has_gemini_key;
    window.PM.state.anthropicModel = status.anthropic_model || "";
    window.PM.state.openaiModel = status.openai_model || "";
    window.PM.state.geminiModel = status.gemini_model || "";
    window.PM.state.llmProvider = (status.llm_provider || "auto").toLowerCase();

    if (switcher) {
      switcher.innerHTML = "";
      if (!conns.connections.length) {
        const o = document.createElement("option");
        o.value = "";
        o.textContent = "No connection";
        switcher.appendChild(o);
      } else {
        conns.connections.forEach((conn) => {
          const o = document.createElement("option");
          o.value = conn.id;
          o.textContent = `${conn.name} · ${conn.dialect}`;
          if (conn.is_active) o.selected = true;
          switcher.appendChild(o);
        });
      }
      switcher.onchange = async (e) => {
        const id = e.target.value;
        if (!id) return;
        try {
          await window.PM.api.activateConnection(id);
          await refreshStatus();
          c.showToast("Active connection switched");
        } catch (err) {
          c.showToast(err.message || String(err), "error");
        }
      };
    }

    if (modelSwitcher) {
      const ha = window.PM.state.hasAnthropic;
      const ho = window.PM.state.hasOpenai;
      const hg = window.PM.state.hasGemini;
      const pref = window.PM.state.llmProvider;
      const eff = (status.llm_effective_provider || "").toLowerCase();
      const provName = {
        anthropic: "Claude",
        openai: "OpenAI",
        gemini: "Gemini",
      };

      function addOpt(value, label) {
        const o = document.createElement("option");
        o.value = value;
        o.textContent = label;
        modelSwitcher.appendChild(o);
      }

      modelSwitcher.innerHTML = "";
      const autoLabel =
        eff && pref === "auto"
          ? `Auto (using ${provName[eff] || eff})`
          : "Auto — Claude → OpenAI → Gemini";
      addOpt("auto", autoLabel);
      if (ha)
        addOpt("anthropic", `Claude: ${window.PM.state.anthropicModel || "model"}`);
      if (ho)
        addOpt("openai", `OpenAI: ${window.PM.state.openaiModel || "model"}`);
      if (hg)
        addOpt("gemini", `Gemini: ${window.PM.state.geminiModel || "model"}`);

      let chosen = ["auto", "anthropic", "openai", "gemini"].includes(pref)
        ? pref
        : "auto";
      if (chosen === "anthropic" && !ha) chosen = "auto";
      if (chosen === "openai" && !ho) chosen = "auto";
      if (chosen === "gemini" && !hg) chosen = "auto";
      modelSwitcher.value = chosen;
      if (modelSwitcher.value !== chosen) {
        modelSwitcher.value = "auto";
      }

      modelSwitcher.onchange = async () => {
        const v = modelSwitcher.value;
        try {
          await window.PM.api.saveSettings({ llm_provider: v });
          try {
            window.PM.storage.saveSecrets({ llm_provider: v });
          } catch (_) {}
          await refreshStatus();
          c.showToast("LLM provider updated");
        } catch (err) {
          c.showToast(err.message || String(err), "error");
          await refreshStatus();
        }
      };
    }

    if (chip) {
      const dot = chip.querySelector(".dot");
      const name = chip.querySelector(".active-conn-name");
      if (active) {
        dot.className = "dot dot--ok";
        name.textContent = `${active.name} · ${active.dialect}`;
      } else {
        dot.className = "dot dot--warn";
        name.textContent = "Not connected";
      }
    }

    document.dispatchEvent(new Event("pm:status"));
  }

  async function runAnalysis(opts) {
    const c = components();
    const { mode, question, template_id, params } = opts;

    if (!window.PM.state.activeConnectionId) {
      c.showToast("Add a connection first", "error");
      navigate("connections");
      return;
    }
    if (
      !window.PM.state.hasAnthropic &&
      !window.PM.state.hasOpenai &&
      !window.PM.state.hasGemini
    ) {
      c.showToast("Add an API key in Settings", "error");
      navigate("settings");
      return;
    }

    setActiveNav("home");
    location.hash = "#/home";
    window.PM.views.report.renderLoading(question, mode);

    if (mode === "report") {
      c.setProgress(true, "Planning steps…");
    } else {
      c.setProgress(true, "Running query…");
    }

    try {
      let payload;
      if (mode === "report") {
        const labelTimers = [
          [400, "Planning steps…"],
          [3500, "Running queries…"],
          [9000, "Synthesizing report…"],
        ];
        const startedAt = Date.now();
        const tick = () => {
          const elapsed = Date.now() - startedAt;
          const last = labelTimers.filter(([t]) => t <= elapsed).pop();
          if (last) c.setProgress(true, last[1]);
        };
        const interval = setInterval(tick, 600);
        try {
          payload = await window.PM.api.report({
            question,
            template_id: template_id || null,
            params: params || {},
          });
        } finally {
          clearInterval(interval);
        }
        c.setProgress(false);
        location.hash = `#/report/${payload.id}`;
      } else {
        payload = await window.PM.api.chat({ question });
        c.setProgress(false);
        payload.question = question;
        window.PM.views.report.renderChat(payload);
        setActiveNav("home");
      }
    } catch (err) {
      c.setProgress(false);
      const c2 = components();
      const root = c2.el("div");
      root.innerHTML = `
        <div style="margin-bottom:18px">
          <div class="section-eyebrow">Could not finish</div>
          <h1 class="section-h1">${c2.escapeHtml(question)}</h1>
        </div>
        <div class="empty">
          <h3>${c2.escapeHtml(err.message || "Something went wrong.")}</h3>
          <p>Try a slightly different question, or check your connection and API key.</p>
          <a href="#/home" class="btn btn--ghost" style="flex:initial">Back to home</a>
        </div>
      `;
      c2.setView(root);
    }
  }

  /**
   * Replay the user's saved settings + connections to the in-memory server.
   * Runs once on boot so a hard refresh / server restart restores state.
   */
  async function hydrateFromBrowser() {
    const storage = window.PM.storage;
    if (!storage || !storage.isEnabled()) return { restored: 0 };

    let serverStatus = null;
    let serverConns = [];
    try {
      [serverStatus, { connections: serverConns = [] }] = await Promise.all([
        window.PM.api.status(),
        window.PM.api.listConnections(),
      ]);
    } catch {
      return { restored: 0 };
    }

    const secrets = storage.loadSecrets();
    const wantsKeys = !!(
      secrets.anthropic_api_key ||
      secrets.openai_api_key ||
      secrets.gemini_api_key
    );
    const wantsModel = !!(
      secrets.anthropic_model ||
      secrets.openai_model ||
      secrets.gemini_model
    );
    const wantsLlmPref = !!(
      secrets.llm_provider &&
      ["auto", "anthropic", "openai", "gemini"].includes(
        String(secrets.llm_provider).toLowerCase()
      )
    );
    const serverHasKey =
      serverStatus.has_anthropic_key ||
      serverStatus.has_openai_key ||
      serverStatus.has_gemini_key;

    if (wantsKeys || wantsModel || wantsLlmPref) {
      try {
        const body = {};
        if (!serverStatus.has_anthropic_key && secrets.anthropic_api_key)
          body.anthropic_api_key = secrets.anthropic_api_key;
        if (!serverStatus.has_openai_key && secrets.openai_api_key)
          body.openai_api_key = secrets.openai_api_key;
        if (!serverStatus.has_gemini_key && secrets.gemini_api_key)
          body.gemini_api_key = secrets.gemini_api_key;
        if (secrets.anthropic_model) body.anthropic_model = secrets.anthropic_model;
        if (secrets.openai_model) body.openai_model = secrets.openai_model;
        if (secrets.gemini_model) body.gemini_model = secrets.gemini_model;
        if (wantsLlmPref) {
          body.llm_provider = String(secrets.llm_provider).toLowerCase();
        }
        if (Object.keys(body).length) await window.PM.api.saveSettings(body);
      } catch {}
    }

    const stored = storage.loadConnections();
    let restored = 0;
    let failed = 0;
    if (stored.length && serverConns.length === 0) {
      for (const cfg of stored) {
        try {
          await window.PM.api.addConnection(cfg);
          restored += 1;
        } catch {
          failed += 1;
        }
      }
    }

    const wantedName = storage.getActiveName();
    if (wantedName) {
      try {
        const { connections = [] } = await window.PM.api.listConnections();
        const match = connections.find((c) => c.name === wantedName);
        if (match && !match.is_active) await window.PM.api.activateConnection(match.id);
      } catch {}
    }

    return { restored, failed, hadKey: wantsKeys && !serverHasKey };
  }

  window.PM.app = {
    navigate,
    refreshStatus,
    runAnalysis,
    hydrateFromBrowser,
  };

  async function boot() {
    if (!location.hash) location.hash = "#/home";
    const result = await hydrateFromBrowser();
    await refreshStatus();
    handleRoute();
    if (result && (result.restored || result.hadKey)) {
      const c = components();
      const bits = [];
      if (result.restored) bits.push(`${result.restored} connection${result.restored === 1 ? "" : "s"}`);
      if (result.hadKey) bits.push("API key");
      if (bits.length) c.showToast(`Restored ${bits.join(" + ")} from browser`);
      if (result.failed) c.showToast(`${result.failed} saved connection(s) failed to restore`, "error");
    }
  }

  window.addEventListener("hashchange", handleRoute);
  document.addEventListener("DOMContentLoaded", boot);
  if (document.readyState !== "loading") {
    boot();
  }
})();
