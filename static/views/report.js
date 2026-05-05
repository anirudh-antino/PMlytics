/**
 * Report view: sectioned PM report (summary, KPIs, charts, findings,
 * hypotheses, recommended actions, methodology).
 *
 * Two render paths:
 *   - renderLoading(question, mode): skeleton shell while the API works
 *   - renderResult(payload): full report from /api/report (or /api/chat fallback)
 */
(function () {
  window.PM = window.PM || {};
  window.PM.views = window.PM.views || {};

  function helpers() {
    return window.PM.components;
  }

  function el(tag, attrs, kids) {
    return helpers().el(tag, attrs, kids);
  }

  function setView(node) {
    return helpers().setView(node);
  }

  function loadingShell(question, mode) {
    const c = helpers();
    setTopbarFor(question);
    const root = el("div");
    root.innerHTML = `
      <div style="margin-bottom:18px">
        <div class="section-eyebrow">${mode === "chat" ? "Quick answer" : "Generating report"}</div>
        <h1 class="section-h1">${c.escapeHtml(question)}</h1>
        <p class="section-lede">Decomposing your question, running read-only queries, then synthesizing the report.</p>
      </div>
      <div class="kpi-grid">
        ${["", "", "", ""].map(() => `<div class="skel skel-kpi"></div>`).join("")}
      </div>
      <div class="section-h2">Chart</div>
      <div class="skel skel-chart"></div>
      <div class="section-h2">Findings</div>
      <div class="card">
        <div class="skel skel-row"></div>
        <div class="skel skel-row"></div>
        <div class="skel skel-row"></div>
      </div>
    `;
    setView(root);
  }

  function setTopbarFor(question) {
    helpers().setTopbar(
      question.length > 70 ? question.slice(0, 67) + "…" : question,
      "Report"
    );
  }

  function trendIcon(trend) {
    if (trend === "up") return "▲";
    if (trend === "down") return "▼";
    return "";
  }

  function trendClass(trend) {
    if (trend === "up") return "kpi-delta--up";
    if (trend === "down") return "kpi-delta--down";
    return "";
  }

  function findStepRows(steps, stepId) {
    if (!Array.isArray(steps)) return null;
    return steps.find((s) => s && s.id === stepId) || null;
  }

  function renderKpis(kpis) {
    if (!Array.isArray(kpis) || !kpis.length) return null;
    const grid = el("div", { class: "kpi-grid" });
    kpis.forEach((k) => {
      const card = el("div", { class: "kpi-card" });
      card.appendChild(el("span", { class: "kpi-label", html: helpers().escapeHtml(k.label || "") }));
      card.appendChild(el("span", { class: "kpi-value", html: helpers().escapeHtml(String(k.value ?? "")) }));
      if (k.delta) {
        const trend = (k.trend || "flat").toLowerCase();
        card.appendChild(
          el("span", {
            class: "kpi-delta " + trendClass(trend),
            html: `${trendIcon(trend)} ${helpers().escapeHtml(k.delta)}`,
          })
        );
      }
      grid.appendChild(card);
    });
    return grid;
  }

  function renderCharts(charts, steps) {
    if (!Array.isArray(charts) || !charts.length) return null;
    const wrap = el("div", { style: "display:flex;flex-direction:column;gap:14px" });
    charts.forEach((ch, i) => {
      const frame = el("div", { class: "chart-frame" });
      if (ch.title) frame.appendChild(el("div", { class: "chart-frame__title", html: helpers().escapeHtml(ch.title) }));
      const host = el("div", { class: "chart-host", id: `chart-${i}` });
      frame.appendChild(host);
      if (ch.how_to_read) {
        frame.appendChild(
          el("p", { class: "chart-frame__hint", html: helpers().escapeHtml(ch.how_to_read) })
        );
      }
      wrap.appendChild(frame);
      requestAnimationFrame(() => {
        if (ch.echarts_option) window.PM.charts.render(host, ch.echarts_option);
      });
    });
    return wrap;
  }

  function renderFindings(findings) {
    if (!Array.isArray(findings) || !findings.length) return null;
    const ul = el("ul", { class: "list-clean" });
    findings.forEach((f, i) => {
      const li = el("li", { class: "finding" });
      li.appendChild(el("span", { class: "finding__bullet", html: String(i + 1) }));
      const body = el("div", { style: "flex:1" });
      body.appendChild(el("div", { html: helpers().renderMarkdown(f.text || "") }));
      if (f.evidence_step_id) {
        body.appendChild(
          el("div", {
            class: "finding__cite",
            html: `Source: <code>${helpers().escapeHtml(f.evidence_step_id)}</code>`,
          })
        );
      }
      li.appendChild(body);
      ul.appendChild(li);
    });
    return ul;
  }

  function renderHypotheses(hyps) {
    if (!Array.isArray(hyps) || !hyps.length) return null;
    const ul = el("ul", { class: "list-clean" });
    hyps.forEach((h) => {
      const li = el("li", { class: "finding" });
      const conf = (h.confidence || "low").toLowerCase();
      li.appendChild(
        el("span", {
          class: "confidence confidence--" + conf,
          style: "align-self:flex-start;margin-top:2px",
          html: helpers().escapeHtml(conf),
        })
      );
      const body = el("div", { style: "flex:1" });
      body.appendChild(el("div", { html: helpers().renderMarkdown(h.text || "") }));
      if (h.evidence_step_id) {
        body.appendChild(
          el("div", {
            class: "finding__cite",
            html: `Source: <code>${helpers().escapeHtml(h.evidence_step_id)}</code>`,
          })
        );
      }
      li.appendChild(body);
      ul.appendChild(li);
    });
    return ul;
  }

  function renderActions(actions) {
    if (!Array.isArray(actions) || !actions.length) return null;
    const ul = el("ul", { class: "list-clean" });
    actions.forEach((a, i) => {
      const li = el("li", { class: "action-card" });
      li.appendChild(el("span", { class: "finding__bullet", html: String(i + 1) }));
      const body = el("div", { style: "flex:1" });
      body.appendChild(el("div", { html: helpers().renderMarkdown(a.text || "") }));
      li.appendChild(body);
      if (a.owner_hint) {
        li.appendChild(
          el("span", { class: "action-card__owner", html: helpers().escapeHtml(a.owner_hint) })
        );
      }
      ul.appendChild(li);
    });
    return ul;
  }

  function renderMethodology(methodology, steps) {
    if (!Array.isArray(methodology) || !methodology.length) return null;
    const wrap = el("div", { style: "display:flex;flex-direction:column;gap:10px" });
    methodology.forEach((m) => {
      const step = findStepRows(steps, m.step_id) || {};
      const card = el("div", { class: "method-step" });
      const head = el("div", { class: "method-step__head" });
      head.appendChild(el("span", { class: "method-step__id", html: helpers().escapeHtml(m.step_id || "") }));
      head.appendChild(
        el("span", {
          style: "font-size:11.5px;color:var(--muted)",
          html: `${m.row_count || 0} rows`,
        })
      );
      card.appendChild(head);
      card.appendChild(
        el("div", {
          class: "method-step__intent",
          html: helpers().escapeHtml(m.intent || step.intent || ""),
        })
      );
      const queryText =
        typeof step.query === "string"
          ? step.query
          : step.query
          ? JSON.stringify(step.query, null, 2)
          : m.query_preview || "";
      if (queryText) {
        card.appendChild(el("pre", { class: "code-block", html: helpers().escapeHtml(queryText) }));
      }
      if (step.error) {
        card.appendChild(
          el("div", {
            style:
              "margin-top:8px;font-size:12px;color:var(--danger);background:#fef2f2;border:1px solid #fee2e2;padding:6px 8px;border-radius:6px",
            html: `Error: ${helpers().escapeHtml(step.error)}`,
          })
        );
      } else if (step.columns && step.rows && step.rows.length) {
        const tbl = helpers().previewTable(step.columns, step.rows, 12);
        tbl.style.marginTop = "8px";
        card.appendChild(tbl);
      }
      wrap.appendChild(card);
    });
    return wrap;
  }

  function renderReport(payload) {
    const c = helpers();
    const root = el("div");
    const r = (payload && payload.report) || payload;
    const steps = (payload && payload.steps) || [];
    const title = r.title || payload.question || "Analysis";
    setTopbarFor(title);

    const head = el("div", { style: "margin-bottom:18px" });
    head.appendChild(el("div", { class: "section-eyebrow", html: "Report" }));
    head.appendChild(el("h1", { class: "section-h1", html: c.escapeHtml(title) }));
    if (payload.connection_name) {
      head.appendChild(
        el("p", {
          style: "font-size:12px;color:var(--muted);margin-top:4px",
          html: `${c.escapeHtml(payload.connection_name)} · ${c.escapeHtml(payload.dialect || "")} · ${c.timeAgo(payload.created_at)}`,
        })
      );
    }
    if (r.summary) {
      head.appendChild(el("div", { class: "prose", style: "margin-top:14px", html: c.renderMarkdown(r.summary) }));
    }
    const actionsRow = el("div", { class: "form-row", style: "gap:8px;flex:initial;margin-top:14px" });
    actionsRow.appendChild(
      el(
        "button",
        {
          class: "btn btn--ghost",
          style: "flex:initial",
          onclick: () => copyAsMarkdown(payload),
        },
        "Copy as Markdown"
      )
    );
    actionsRow.appendChild(
      el(
        "button",
        {
          class: "btn btn--ghost",
          style: "flex:initial",
          onclick: () => {
            window.PM.app.navigate("home");
          },
        },
        "New analysis"
      )
    );
    head.appendChild(actionsRow);
    root.appendChild(head);

    const kpis = renderKpis(r.kpis);
    if (kpis) {
      root.appendChild(el("div", { class: "section-h2", html: "Key metrics" }));
      root.appendChild(kpis);
    }

    const charts = renderCharts(r.charts, steps);
    if (charts) {
      root.appendChild(el("div", { class: "section-h2", html: "Charts" }));
      root.appendChild(charts);
    }

    const findings = renderFindings(r.findings);
    if (findings) {
      root.appendChild(el("div", { class: "section-h2", html: "Findings" }));
      root.appendChild(findings);
    }

    const hyps = renderHypotheses(r.hypotheses);
    if (hyps) {
      root.appendChild(el("div", { class: "section-h2", html: "Hypotheses" }));
      root.appendChild(hyps);
    }

    const actions = renderActions(r.actions);
    if (actions) {
      root.appendChild(el("div", { class: "section-h2", html: "Recommended actions" }));
      root.appendChild(actions);
    }

    const method = renderMethodology(r.methodology, steps);
    if (method) {
      root.appendChild(el("div", { class: "section-h2", html: "Methodology" }));
      root.appendChild(method);
    }

    setView(root);
  }

  function renderChat(data) {
    const c = helpers();
    const root = el("div");
    const title = data.question || "Quick answer";
    setTopbarFor(title);

    const head = el("div", { style: "margin-bottom:18px" });
    head.appendChild(el("div", { class: "section-eyebrow", html: "Quick answer" }));
    head.appendChild(el("h1", { class: "section-h1", html: c.escapeHtml(title) }));
    root.appendChild(head);

    if (data.answer_markdown) {
      const card = el("div", { class: "card" });
      card.appendChild(
        el("div", { class: "prose", html: c.renderMarkdown(data.answer_markdown) })
      );
      root.appendChild(card);
    }

    if (data.echarts_option) {
      const frame = el("div", { class: "chart-frame", style: "margin-top:16px" });
      const host = el("div", { class: "chart-host" });
      frame.appendChild(host);
      if (data.chart_notes_markdown) {
        frame.appendChild(
          el("p", {
            class: "chart-frame__hint",
            html: c.escapeHtml(data.chart_notes_markdown),
          })
        );
      }
      root.appendChild(frame);
      requestAnimationFrame(() => window.PM.charts.render(host, data.echarts_option));
    }

    if (data.reasoning) {
      const card = el("div", { class: "card", style: "margin-top:16px" });
      card.appendChild(el("div", { class: "section-eyebrow", html: "Reasoning" }));
      card.appendChild(el("div", { class: "prose", html: c.renderMarkdown(data.reasoning) }));
      root.appendChild(card);
    }

    if (data.sql || (data.columns && data.rows_preview && data.rows_preview.length)) {
      root.appendChild(el("div", { class: "section-h2", html: "Methodology" }));
      const card = el("div", { class: "method-step" });
      const queryText =
        typeof data.sql === "string"
          ? data.sql
          : data.sql
          ? JSON.stringify(data.sql, null, 2)
          : "(no query)";
      card.appendChild(el("pre", { class: "code-block", html: c.escapeHtml(queryText) }));
      if (data.sql_error) {
        card.appendChild(
          el("div", {
            style:
              "margin-top:8px;font-size:12px;color:var(--danger);background:#fef2f2;border:1px solid #fee2e2;padding:6px 8px;border-radius:6px",
            html: `Note: ${c.escapeHtml(data.sql_error)}`,
          })
        );
      }
      if (data.columns && data.rows_preview && data.rows_preview.length) {
        const tbl = c.previewTable(data.columns, data.rows_preview, 25);
        tbl.style.marginTop = "8px";
        card.appendChild(tbl);
        card.appendChild(
          el("p", {
            style: "font-size:11.5px;color:var(--muted);margin-top:6px",
            html: `Showing up to ${data.rows_preview.length} of ${data.row_count} rows.`,
          })
        );
      }
      root.appendChild(card);
    }

    setView(root);
  }

  function copyAsMarkdown(payload) {
    const r = (payload && payload.report) || payload;
    if (!r) return;
    const lines = [];
    lines.push(`# ${r.title || payload.question || "Report"}`);
    if (r.summary) lines.push("", r.summary);
    if (Array.isArray(r.kpis) && r.kpis.length) {
      lines.push("", "## Key metrics");
      r.kpis.forEach((k) => {
        lines.push(`- **${k.label}**: ${k.value}${k.delta ? ` (${k.delta})` : ""}`);
      });
    }
    if (Array.isArray(r.findings) && r.findings.length) {
      lines.push("", "## Findings");
      r.findings.forEach((f) => lines.push(`- ${f.text}`));
    }
    if (Array.isArray(r.hypotheses) && r.hypotheses.length) {
      lines.push("", "## Hypotheses");
      r.hypotheses.forEach((h) =>
        lines.push(`- (${h.confidence || "low"}) ${h.text}`)
      );
    }
    if (Array.isArray(r.actions) && r.actions.length) {
      lines.push("", "## Recommended actions");
      r.actions.forEach((a) =>
        lines.push(`- ${a.text}${a.owner_hint ? ` _(${a.owner_hint})_` : ""}`)
      );
    }
    const text = lines.join("\n");
    navigator.clipboard
      .writeText(text)
      .then(() => helpers().showToast("Copied report to clipboard"))
      .catch(() => helpers().showToast("Could not copy to clipboard", "error"));
  }

  window.PM.views.report = {
    renderLoading: loadingShell,
    renderReport,
    renderChat,
  };
})();
