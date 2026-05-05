/**
 * Settings view: API keys + model picker.
 */
(function () {
  window.PM = window.PM || {};
  window.PM.views = window.PM.views || {};

  function helpers() {
    return window.PM.components;
  }

  async function render(_state) {
    const c = helpers();
    c.setTopbar("Settings", "API keys and model selection");

    const root = c.el("div");
    root.innerHTML = `
      <div style="margin-bottom:18px">
        <div class="section-eyebrow">Workspace</div>
        <h1 class="section-h1">Settings</h1>
        <p class="section-lede">
          Keys are kept in the server's memory while it runs and also saved to your
          browser's localStorage so they survive restarts. Don't run this app on a
          shared computer or expose it to the public internet.
        </p>
      </div>

      <div class="card" style="margin-bottom:16px;display:flex;align-items:flex-start;gap:12px;background:#fff8e6;border-color:#fde68a">
        <span style="flex-shrink:0;color:#b45309;margin-top:2px">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" style="width:18px;height:18px"><path d="M12 9v4m0 4h.01M10.3 3.86l-8.18 14.18A2 2 0 003.84 21h16.32a2 2 0 001.72-2.96L13.7 3.86a2 2 0 00-3.4 0z" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </span>
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;font-size:13.5px;color:#92400e">Browser persistence is on</div>
          <div id="s-persist-info" style="font-size:12.5px;color:#92400e;margin-top:4px"></div>
        </div>
        <button id="s-clear-browser" type="button" class="btn btn--danger" style="flex:initial;align-self:center">Clear browser data</button>
      </div>

      <div class="card card--pad-lg" style="margin-bottom:16px">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px">
          <div class="section-eyebrow" style="margin:0">Anthropic (Claude)</div>
          <span id="s-anthropic-pill" class="key-pill" hidden></span>
        </div>
        <label class="field-label" for="s-anthropic">API key</label>
        <input id="s-anthropic" class="input input--mono" type="password" autocomplete="off" placeholder="sk-ant-api03-…" />
        <p id="s-anthropic-help" class="field-help" hidden></p>
        <div style="margin-top:12px">
          <label class="field-label" for="s-anthropic-model">Model</label>
          <input id="s-anthropic-model" class="input input--mono" list="dl-anthropic" placeholder="claude-3-5-sonnet-20241022" autocomplete="off" />
          <datalist id="dl-anthropic"></datalist>
          <p class="field-help">Type any model name your key has access to. Suggestions in the dropdown are starters.</p>
        </div>
      </div>

      <div class="card card--pad-lg" style="margin-bottom:16px">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px">
          <div class="section-eyebrow" style="margin:0">OpenAI (optional)</div>
          <span id="s-openai-pill" class="key-pill" hidden></span>
        </div>
        <label class="field-label" for="s-openai">API key</label>
        <input id="s-openai" class="input input--mono" type="password" autocomplete="off" placeholder="sk-…" />
        <p id="s-openai-help" class="field-help" hidden></p>
        <div style="margin-top:12px">
          <label class="field-label" for="s-openai-model">Model</label>
          <input id="s-openai-model" class="input input--mono" list="dl-openai" placeholder="gpt-4o-mini" autocomplete="off" />
          <datalist id="dl-openai"></datalist>
          <p class="field-help">Type any model name your key has access to. Used when no Anthropic key is set.</p>
        </div>
      </div>

      <div class="card card--pad-lg" style="margin-bottom:16px">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px">
          <div class="section-eyebrow" style="margin:0">Google (Gemini)</div>
          <span id="s-gemini-pill" class="key-pill" hidden></span>
        </div>
        <label class="field-label" for="s-gemini">API key</label>
        <input id="s-gemini" class="input input--mono" type="password" autocomplete="off" placeholder="AIza…" />
        <p id="s-gemini-help" class="field-help" hidden></p>
        <div style="margin-top:12px">
          <label class="field-label" for="s-gemini-model">Model</label>
          <input id="s-gemini-model" class="input input--mono" list="dl-gemini" placeholder="gemini-flash-latest" autocomplete="off" />
          <datalist id="dl-gemini"></datalist>
          <p class="field-help">Used when neither Claude nor OpenAI keys are set, unless you pick another provider in the top bar. Default order is Claude first, then OpenAI, then Gemini.</p>
        </div>
      </div>

      <div style="display:flex;gap:10px;align-items:center">
        <button id="s-save" class="btn btn--primary" type="button">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Save settings
        </button>
        <span id="s-status" style="font-size:12.5px;color:var(--muted)"></span>
      </div>
    `;
    c.setView(root);

    const aSel = root.querySelector("#s-anthropic-model");
    const oSel = root.querySelector("#s-openai-model");
    const gSel = root.querySelector("#s-gemini-model");
    const status = root.querySelector("#s-status");

    function updateKeyPill(provider, hasServerKey) {
      const pill = root.querySelector(`#s-${provider}-pill`);
      const help = root.querySelector(`#s-${provider}-help`);
      const input = root.querySelector(`#s-${provider}`);
      if (!pill || !help || !input) return;
      if (hasServerKey) {
        pill.hidden = false;
        pill.textContent = "● Stored";
        pill.className = "key-pill key-pill--ok";
        help.hidden = false;
        help.textContent = "A key is loaded. Leave blank to keep it, or type a new one to replace.";
        input.placeholder = "•••••••• (stored — type to replace)";
      } else {
        pill.hidden = false;
        pill.textContent = "○ Not set";
        pill.className = "key-pill key-pill--idle";
        help.hidden = true;
        input.placeholder =
          provider === "anthropic"
            ? "sk-ant-api03-…"
            : provider === "gemini"
            ? "AIza…"
            : "sk-…";
      }
    }

    async function refreshKeyPills() {
      try {
        const s = await window.PM.api.status();
        updateKeyPill("anthropic", !!s.has_anthropic_key);
        updateKeyPill("openai", !!s.has_openai_key);
        updateKeyPill("gemini", !!s.has_gemini_key);
      } catch {}
    }

    const aDl = root.querySelector("#dl-anthropic");
    const oDl = root.querySelector("#dl-openai");
    const gDl = root.querySelector("#dl-gemini");

    try {
      const m = await window.PM.api.models();
      (m.anthropic || []).forEach((name) => {
        const o = document.createElement("option");
        o.value = name;
        aDl.appendChild(o);
      });
      (m.openai || []).forEach((name) => {
        const o = document.createElement("option");
        o.value = name;
        oDl.appendChild(o);
      });
      (m.gemini || []).forEach((name) => {
        const o = document.createElement("option");
        o.value = name;
        gDl.appendChild(o);
      });
      aSel.value = (m.selected && m.selected.anthropic) || aSel.value || "";
      oSel.value = (m.selected && m.selected.openai) || oSel.value || "";
      gSel.value = (m.selected && m.selected.gemini) || gSel.value || "";
    } catch (err) {
      status.textContent = "Could not load model list.";
      status.style.color = "var(--danger)";
    }

    root.querySelector("#s-save").addEventListener("click", async () => {
      status.textContent = "Saving…";
      status.style.color = "var(--muted)";
      const body = {
        anthropic_model: aSel.value,
        openai_model: oSel.value,
        gemini_model: gSel.value,
      };
      const ak = root.querySelector("#s-anthropic").value.trim();
      const ok = root.querySelector("#s-openai").value.trim();
      const gk = root.querySelector("#s-gemini").value.trim();
      if (ak) body.anthropic_api_key = ak;
      if (ok) body.openai_api_key = ok;
      if (gk) body.gemini_api_key = gk;
      try {
        await window.PM.api.saveSettings(body);
        try {
          window.PM.storage.saveSecrets({
            anthropic_model: aSel.value,
            openai_model: oSel.value,
            gemini_model: gSel.value,
            ...(ak ? { anthropic_api_key: ak } : {}),
            ...(ok ? { openai_api_key: ok } : {}),
            ...(gk ? { gemini_api_key: gk } : {}),
          });
        } catch {}
        await window.PM.app.refreshStatus();
        root.querySelector("#s-anthropic").value = "";
        root.querySelector("#s-openai").value = "";
        root.querySelector("#s-gemini").value = "";
        const saved = [];
        if (ak) saved.push("Claude key");
        if (ok) saved.push("OpenAI key");
        if (gk) saved.push("Gemini key");
        if (aSel.value || oSel.value || gSel.value) saved.push("model");
        status.textContent = saved.length ? `Saved: ${saved.join(", ")}.` : "Saved.";
        status.style.color = "var(--ok)";
        c.showToast(saved.length ? `Saved ${saved.join(" + ")}` : "Settings saved");
        await refreshKeyPills();
        updatePersistInfo();
      } catch (err) {
        status.textContent = err.message || String(err);
        status.style.color = "var(--danger)";
      }
    });

    const clearBtn = root.querySelector("#s-clear-browser");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        if (!confirm("Clear saved keys, models, and connections from this browser?")) return;
        try {
          window.PM.storage.clearAll();
          c.showToast("Browser data cleared");
          updatePersistInfo();
        } catch (err) {
          c.showToast(err.message || String(err), "error");
        }
      });
    }
    updatePersistInfo();
    refreshKeyPills();

    function updatePersistInfo() {
      const info = root.querySelector("#s-persist-info");
      if (!info) return;
      if (!window.PM.storage || !window.PM.storage.available) {
        info.textContent = "Browser storage is unavailable; settings will clear on refresh.";
        return;
      }
      const conns = window.PM.storage.loadConnections().length;
      const sec = window.PM.storage.loadSecrets();
      const hasKey = !!(
        sec.anthropic_api_key ||
        sec.openai_api_key ||
        sec.gemini_api_key
      );
      const bits = [];
      bits.push(`${conns} connection${conns === 1 ? "" : "s"}`);
      bits.push(hasKey ? "API key saved" : "no API key saved");
      info.textContent = `In this browser: ${bits.join(" · ")}.`;
    }
  }

  window.PM.views.settings = { render };
})();
