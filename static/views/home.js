/**
 * Home / New analysis view: composer + suggested starter prompts.
 */
(function () {
  window.PM = window.PM || {};
  window.PM.views = window.PM.views || {};

  const STARTERS = [
    {
      label: "Onboarding",
      text: "Why are users dropping off during onboarding in the last 30 days?",
    },
    {
      label: "Activation",
      text: "What is our sign-up to first-action conversion rate, broken down by week?",
    },
    {
      label: "Retention",
      text: "Show weekly retention cohorts for the last 12 weeks and call out any cliffs.",
    },
    {
      label: "Feature",
      text: "How is feature adoption trending since launch — DAU, repeat usage, time-to-first-use?",
    },
    {
      label: "Revenue",
      text: "Summarize MRR, churn, and expansion for the last 90 days. Where is the biggest risk?",
    },
    {
      label: "Diagnostic",
      text: "Sign-ups dropped last week — what changed across acquisition channels and segments?",
    },
  ];

  function render(_state) {
    const { setView, setTopbar, escapeHtml } = window.PM.components;
    setTopbar("New analysis", "Ask anything about your data");

    const root = document.createElement("div");
    root.innerHTML = `
      <div style="margin-bottom:18px">
        <div class="section-eyebrow">Workspace</div>
        <h1 class="section-h1">Ask your warehouse anything</h1>
        <p class="section-lede">
          Plain-language questions become read-only queries against your live schema.
          Pick <strong>Quick answer</strong> for a single chart or <strong>Full report</strong>
          for an executive summary, KPIs, findings, hypotheses, and recommended actions.
        </p>
      </div>

      <div class="composer">
        <div class="composer-mode-row">
          <div class="mode-toggle" role="tablist" aria-label="Analysis mode">
            <button type="button" data-mode="report" class="is-active" role="tab" aria-selected="true">Full report</button>
            <button type="button" data-mode="chat" role="tab" aria-selected="false">Quick answer</button>
          </div>
          <span id="composer-hint" class="composer-hint"></span>
        </div>
        <textarea
          id="home-input"
          class="composer-textarea"
          rows="4"
          placeholder="e.g. Why are new users dropping off between sign-up and activation in the last 30 days?"
        ></textarea>
        <div class="composer-actions">
          <span class="composer-hint">
            <kbd>Enter</kbd> to run · <kbd>Shift</kbd>+<kbd>Enter</kbd> for newline
          </span>
          <button id="home-run" class="btn btn--primary" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M5 3l14 9-14 9V3z" stroke-linejoin="round" />
            </svg>
            Run analysis
          </button>
        </div>
      </div>

      <div style="margin-top:28px">
        <div class="section-h2">Starter prompts</div>
        <div class="starter-grid">
          ${STARTERS.map(
            (s) => `
            <button class="starter-card" data-text="${escapeHtml(s.text)}" type="button">
              <span class="label">${escapeHtml(s.label)}</span>
              <span class="text">${escapeHtml(s.text)}</span>
            </button>`
          ).join("")}
        </div>
      </div>

      <div style="margin-top:28px">
        <div class="section-h2">Templates</div>
        <p class="section-lede" style="margin-bottom:12px">
          Need something more structured? Pick a PM lens with parameters.
        </p>
        <div class="form-row" style="gap:8px">
          <a href="#/templates" class="btn btn--ghost" style="flex:initial">Browse templates</a>
          <a href="#/schema" class="btn btn--ghost" style="flex:initial">Explore schema</a>
        </div>
      </div>
    `;
    setView(root);

    const input = root.querySelector("#home-input");
    const runBtn = root.querySelector("#home-run");
    const hint = root.querySelector("#composer-hint");
    const modeBtns = root.querySelectorAll(".mode-toggle button");
    let mode = "report";

    function refreshGate() {
      const s = window.PM.state || {};
      const needConn = !s.activeConnectionId;
      const needKey =
        !s.hasAnthropic && !s.hasOpenai && !s.hasGemini;
      runBtn.disabled = needConn || needKey;
      if (needConn && needKey) hint.textContent = "Add a connection and an API key in Settings.";
      else if (needConn) hint.textContent = "Add a database connection to run analyses.";
      else if (needKey)
        hint.textContent =
          "Add a Claude, OpenAI, or Google (Gemini) API key in Settings.";
      else hint.textContent = "";
    }
    refreshGate();
    document.addEventListener("pm:status", refreshGate);

    modeBtns.forEach((b) => {
      b.addEventListener("click", () => {
        modeBtns.forEach((x) => {
          x.classList.remove("is-active");
          x.setAttribute("aria-selected", "false");
        });
        b.classList.add("is-active");
        b.setAttribute("aria-selected", "true");
        mode = b.dataset.mode;
      });
    });

    root.querySelectorAll(".starter-card").forEach((card) => {
      card.addEventListener("click", () => {
        input.value = card.dataset.text;
        input.focus();
      });
    });

    async function go() {
      const q = (input.value || "").trim();
      if (!q || runBtn.disabled) return;
      window.PM.app.runAnalysis({ mode, question: q });
    }

    runBtn.addEventListener("click", go);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        go();
      }
    });
    requestAnimationFrame(() => input.focus());
  }

  window.PM.views.home = { render };
})();
