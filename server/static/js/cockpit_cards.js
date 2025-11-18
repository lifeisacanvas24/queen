// queen/server/static/js/cockpit_cards.js
// ============================================================
// Queen Cockpit Cards — v1.0
// Pills, cards, grids, sorting, history
// Requires: cockpit_core.js, cockpit_portfolio.js
// ============================================================

window.Cockpit = window.Cockpit || {};
window.qs = window.qs || {};

(function (C, qs) {
  // ------------------------------------------------------------
  // 1. Pills & badges
  // ------------------------------------------------------------
  //
  // Ensure container is a CSS grid container
  C.makeGrid = function (el) {
    if (!el) return;
    el.classList.add("q-grid");
  };

  C.pill = function (text, tone) {
    const t = tone || "gray";
    return `<span class="pill ${t}">${text}</span>`;
  };

  C.cprBadge = function (ctx) {
    const t = C.normCtx(ctx);
    const tone =
      t === "Above"
        ? "green"
        : t === "At"
          ? "gray"
          : t === "Below"
            ? "red"
            : "amber";
    return C.pill(t.toUpperCase(), tone);
  };

  C.emaBadge = function (bias) {
    const b = bias || "Neutral";
    const tone = b === "Bullish" ? "green" : b === "Bearish" ? "red" : "gray";
    return C.pill(b.toUpperCase(), tone);
  };

  C.rsiBadge = function (v) {
    if (v == null || isNaN(v)) return C.pill("—", "gray");
    const n = Number(v);
    const tone = n >= 60 ? "green" : n >= 45 ? "amber" : "red";
    return C.pill(n.toFixed(1), tone);
  };
  C.trendBadge = function (bias) {
    const raw = (bias || "").toString();
    if (!raw) return C.pill("TREND", "gray");

    const b = raw.toLowerCase();
    let tone = "gray";
    let label = raw.toUpperCase();

    if (b.includes("bull")) {
      tone = "green";
      label = "BULL TREND";
    } else if (b.includes("bear")) {
      tone = "red";
      label = "BEAR TREND";
    } else if (
      b.includes("range") ||
      b.includes("sideways") ||
      b.includes("flat")
    ) {
      tone = "amber";
      label = "RANGE";
    }

    return C.pill(label, tone);
  };

  C.decisionBadge = function (dec, score) {
    const d = (dec || "").toUpperCase();
    const map = C.DECISION_COLOR || {};
    const strong = (d === "BUY" || d === "ADD") && Number(score || 0) >= 9;
    const label = strong ? "ENTER" : d || "";
    const cls = map[d] || "amber";
    return `<span class="badge ${cls}">${label}</span>`;
  };

  // ------------------------------------------------------------
  // 2. Spinner + error cards
  // ------------------------------------------------------------
  C.spinGrid = function (containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    C.makeGrid(el);
    el.innerHTML = `
      <div class="q-card row-dim">
        <div class="q-card-top">
          <span class="sym q-muted">Refreshing…</span>
        </div>
      </div>`;
  };

  C.errorGrid = function (containerId, err) {
    const el = document.getElementById(containerId);
    if (!el) return;
    C.makeGrid(el);
    const msg = (err && (err.message || String(err))) || "Failed to load data.";
    el.innerHTML = `
      <div class="q-card row-dim">
        <div class="q-card-top">
          <span class="sym">Error</span>
        </div>
        <div class="q-card-notes">${C.htmlEscape(msg)}</div>
      </div>`;
  };

  // ------------------------------------------------------------
  // 3. Sorting helpers
  // ------------------------------------------------------------
  C.sortByDecisionScore = function (rows) {
    const pr = C.PR_MAP;
    return rows.slice().sort((a, b) => {
      const ta = Number(
        a.trend_score ??
          a.trend_strength ??
          a.trend_score_10 ??
          a.trendIndex ??
          0,
      );
      const tb = Number(
        b.trend_score ??
          b.trend_strength ??
          b.trend_score_10 ??
          b.trendIndex ??
          0,
      );
      if (tb !== ta) return tb - ta; // 🔥 trend strength desc

      const da = pr[(a.decision || "").toUpperCase()] ?? 9;
      const db = pr[(b.decision || "").toUpperCase()] ?? 9;
      if (da !== db) return da - db;

      const sa = Number(a.score || 0);
      const sb = Number(b.score || 0);
      return sb - sa; // score desc
    });
  };

  C.sortByEarly = function (rows) {
    const pr = C.PR_MAP;
    return rows.slice().sort((a, b) => {
      const ea = Number(a.early ?? a.early_score ?? 0);
      const eb = Number(b.early ?? b.early_score ?? 0);
      if (eb !== ea) return eb - ea; // EARLY desc first

      const ta = Number(
        a.trend_score ??
          a.trend_strength ??
          a.trend_score_10 ??
          a.trendIndex ??
          0,
      );
      const tb = Number(
        b.trend_score ??
          b.trend_strength ??
          b.trend_score_10 ??
          b.trendIndex ??
          0,
      );
      if (tb !== ta) return tb - ta; // then trend strength desc

      const da = pr[(a.decision || "").toUpperCase()] ?? 9;
      const db = pr[(b.decision || "").toUpperCase()] ?? 9;
      if (da !== db) return da - db;

      const sa = Number(a.score || 0);
      const sb = Number(b.score || 0);
      return sb - sa;
    });
  };

  // ------------------------------------------------------------
  // 4. Summary fetcher (used by Summary/Upcoming/Analytics)
  // ------------------------------------------------------------
  C.fetchSummaryRows = async function (opts) {
    const interval = opts.interval || 15;
    const book = opts.book || "all";
    const symbols = C.ensureArray(opts.symbols || []);

    const url = new URL("/cockpit/api/summary", window.location.origin);
    url.searchParams.set("interval", String(interval));
    url.searchParams.set("book", book);
    symbols.forEach((s) => url.searchParams.append("symbols", s));

    const r = await C.noStore(url);
    const j = await r.json();
    const rows = Array.isArray(j.rows) ? j.rows : [];
    return rows;
  };
  C.renderTargets = function (row) {
    const targets = Array.isArray(row.targets) ? row.targets : [];
    if (!targets.length) return "";

    const state = row.targets_state || {};
    const zone = state.zone || "";

    const parts = targets.map((label, idx) => {
      const key = `t${idx + 1}`; // t1 / t2 / t3
      const st = state[key] || {};
      const hit = !!st.hit;
      const extended = !!st.extended;

      let cls = "t-normal";
      if (hit) cls = "t-hit";
      else if (extended) cls = "t-extended";

      const tick = hit ? " ✓" : "";
      return `<span class="${cls}">${C.htmlEscape(label)}${tick}</span>`;
    });

    if (zone) {
      // e.g. "Above T3 (Extended)"
      parts.unshift(`<span class="t-zone">${C.htmlEscape(zone)}</span>`);
    }

    return parts.join(" · ");
  };
  // ------------------------------------------------------------
  // 5. Single card / history card builders
  // ------------------------------------------------------------
  C.buildCardHtml = function (r) {
    const sym = r.symbol || "";
    const dec = (r.decision || "").toUpperCase();
    const cls =
      dec === "BUY" || dec === "ADD"
        ? "q-card row-bull"
        : dec === "EXIT" || dec === "AVOID"
          ? "q-card row-bear"
          : "q-card row-dim";

    const cmp = r.cmp ?? r.CMP;
    const targets = C.renderTargets(r);

    const heldTag = r.held ? `<span class="badge held ml-1">HELD</span>` : "";
    const pnl = C.pnlChip(sym, cmp);

    return `
      <div class="${cls}">
        <div class="q-card-top">
          <div>
            <span class="sym">${C.htmlEscape(sym)}</span>
            ${heldTag}
            ${pnl}
          </div>
          <div class="q-card-pills">
            ${C.decisionBadge(dec, r.score)}
          </div>
        </div>

        <div class="q-card-mid">
          <div class="metric">
            <label>CMP</label>
            <span class="mono">${C.fmtNum(cmp, 1)}</span>
          </div>
          <div class="metric">
            <label>SCORE</label>
            <span>${C.fmtNum(r.score, 1)}</span>
          </div>
          <div class="metric">
            <label>ENTRY</label>
            <span class="mono">${C.fmtNum(r.entry, 1)}</span>
          </div>
          <div class="metric">
            <label>SL</label>
            <span class="mono">${C.fmtNum(r.sl, 1)}</span>
          </div>
          <div class="metric">
            <label>EARLY</label>
            <span class="mono">${C.fmtNum(r.early ?? r.early_score ?? 0, 0)}</span>
          </div>
        </div>

        <div class="q-card-pills">
          ${C.cprBadge(r.cpr_ctx)}
          ${C.emaBadge(r.ema_bias)}
          ${C.trendBadge(
            r.trend_bias ||
              r.bible_trend_bias ||
              r.trend_context ||
              r.bible_trend ||
              r.trend,
          )}
          ${C.rsiBadge(r.rsi || r.RSI)}
        </div>

        <div class="q-card-targets">
          ${targets || "—"}
        </div>

        <div class="q-card-notes">
          ${C.htmlEscape(r.notes || "No notes")}
        </div>

        <div class="symbol-card-strip">
          <span>O ${C.fmtNum(r.open, 1)}</span>
          <span>H ${C.fmtNum(r.high, 1)}</span>
          <span>L ${C.fmtNum(r.low, 1)}</span>
          <span>Prev ${C.fmtNum(r.prev_close, 1)}</span>
          <span>Vol ${C.fmtKMB(r.volume)}</span>
          ${r.upper_circuit ? `<span>UC ${C.fmtNum(r.upper_circuit, 1)}</span>` : ""}
          ${r.lower_circuit ? `<span>LC ${C.fmtNum(r.lower_circuit, 1)}</span>` : ""}
          ${r.high_52w ? `<span>52W H ${C.fmtNum(r.high_52w, 1)}</span>` : ""}
          ${r.low_52w ? `<span>52W L ${C.fmtNum(r.low_52w, 1)}</span>` : ""}
        </div>

        <div class="q-card-bottom mt-1">
          ${C.tradeSummary(r)}
          ${C.dynLadderSummary(r)}
          ${C.range52wSummary(r)}
        </div>
      </div>
    `;
  };

  C.buildHistoryCard = function (row) {
    const dec = (row.decision || row.dec || "").toUpperCase();
    const ts = row.ts || row.time || row.timestamp || "—";
    return `
      <div class="q-card row-dim q-card-history">
        <div class="q-card-top">
          <span class="sym">${C.htmlEscape(row.symbol || row.sym || "")}</span>
          ${C.decisionBadge(dec, row.score)}
        </div>
        <div class="q-card-mid">
          <div class="metric">
            <label>SCORE</label>
            <span>${C.fmtNum(row.score, 1)}</span>
          </div>
          <div class="metric">
            <label>TIME</label>
            <span class="mono">${C.htmlEscape(ts)}</span>
          </div>
        </div>
        <div class="q-card-notes">
          ${C.htmlEscape(row.note || row.notes || "—")}
        </div>
      </div>
    `;
  };

  C.trendLabel = function (row) {
    const bias = (
      row.trend_basis ||
      row.trend_bias ||
      row.bible_trend ||
      ""
    ).toString();
    const score = Number(row.trend_score ?? row.trend_strength ?? 0);
    if (!bias && !score) return "";

    const b = bias || "Neutral";
    const s = score ? ` · ${C.fmtNum(score, 1)}/10` : "";
    let emoji = "⚖️";
    if (b.toLowerCase().includes("bull")) emoji = "📈";
    else if (b.toLowerCase().includes("bear")) emoji = "📉";

    return `${emoji} ${b}${s}`;
  };

  C.trendMeter = function (row) {
    const score = Number(row.trend_score ?? row.trend_strength ?? 0);
    if (!score || isNaN(score)) return "";
    const pct = Math.max(0, Math.min(100, (score / 10) * 100));
    let tone = "amber";
    if (score >= 7) tone = "green";
    else if (score <= 3) tone = "red";
    return `<span class="trend-meter trend-${tone}">
      <span class="trend-meter-bar" style="width:${pct}%"></span>
    </span>`;
  };

  C.tradeSummary = function (r) {
    const ts = r.targets_state || {};
    const label = ts.label || r.targets_label;
    if (!label) return "";
    const ref = ts.ref_interval || r.interval;
    const refStr = ref ? ` · ${ref}` : "";
    return `
      <div class="meta-line trade-line">
        <span class="meta-key">Trade</span>
        <span class="meta-val">
          ${C.htmlEscape(label)}${refStr}
        </span>
      </div>
    `;
  };

  C.dynLadderSummary = function (r) {
    const ts = r.targets_state || {};
    const dyn = ts.dynamic;
    if (!dyn) return "";

    const hits = ts.hits || {};
    const hitT1 = !!hits.T1;
    const hitT2 = !!hits.T2;
    const hitT3 = !!hits.T3;

    const fmt = (lvl, hit) => {
      if (lvl == null) return "—";
      const n = C.fmtNum(lvl, 1);
      return hit ? `${n} ✓` : n;
    };

    return `
      <div class="meta-line dyn-line">
        <span class="meta-key">Dyn</span>
        <span class="meta-val">
          T1 ${fmt(dyn.t1, hitT1)} ·
          T2 ${fmt(dyn.t2, hitT2)} ·
          T3 ${fmt(dyn.t3, hitT3)}
        </span>
      </div>
    `;
  };

  C.range52wSummary = function (r) {
    const hi = r.high_52w ?? r["52w_high"];
    const lo = r.low_52w ?? r["52w_low"];
    if (hi == null && lo == null) return "";

    if (hi != null && lo != null) {
      return `
        <div class="meta-line range52w-line">
          <span class="meta-key">52W</span>
          <span class="meta-val">${C.fmtNum(lo, 1)} – ${C.fmtNum(hi, 1)}</span>
        </div>
      `;
    }

    // only one side available
    const parts = [];
    if (lo != null) parts.push(`L ${C.fmtNum(lo, 1)}`);
    if (hi != null) parts.push(`H ${C.fmtNum(hi, 1)}`);
    return `
      <div class="meta-line range52w-line">
        <span class="meta-key">52W</span>
        <span class="meta-val">${parts.join(" · ")}</span>
      </div>
    `;
  }; // ------------------------------------------------------------
  // 6. Grid renderers
  // ------------------------------------------------------------
  function renderCard(row) {
    const C = window.Cockpit;
    const sym = row.symbol;
    const dec = row.decision;
    const score = row.score;

    // --- NEW meta fields ---
    const pos = row.position || {};
    const hasPos = pos && (pos.qty || pos.pnl);

    const posLine = hasPos
      ? `Qty ${pos.qty || 0} @ ₹${C.fmtNumGeneric(pos.avg, 1)} · PnL ₹${C.fmtNumGeneric(
          pos.pnl,
          0,
        )}`
      : "";

    const action = row.action_text || row.action || "";
    const conf = row.confidence != null ? `${row.confidence}/10` : "";
    const urg = row.urgency || row.bible_urgency || "";
    const urgNote = row.urgency_note || row.bible_urgency_note || "";

    // --- Trend helpers (label + mini-meter) ---
    const trendLabel = C.trendLabel ? C.trendLabel(row) : "";
    const trendMeter = C.trendMeter ? C.trendMeter(row) : "";

    // --- Dynamic trade ladder (from targets_state.dynamic) ---
    let dynamicLine = "";
    const ts = row.targets_state || {};
    const dyn = ts.dynamic || null;

    if (dyn && (dyn.t1 || dyn.t2 || dyn.t3)) {
      const dir = (ts.direction || "LONG").toUpperCase();

      const chip = (item, label) => {
        if (!item || item.level == null) return "";
        const lvl = C.fmtNum(item.level, 1);
        return item.hit ? `${label} ${lvl} ✓` : `${label} ${lvl}`;
      };

      const parts = [
        chip(dyn.t1, "T1"),
        chip(dyn.t2, "T2"),
        chip(dyn.t3, "T3"),
      ].filter(Boolean);

      if (parts.length) {
        dynamicLine = `${dir === "LONG" ? "Dyn" : "Dyn"}: ${parts.join(" · ")}`;
      }
    }

    // --- 52-week range (if present) ---
    const hi52 = row.high_52w;
    const lo52 = row.low_52w;
    const has52w = hi52 != null && lo52 != null;

    return `
      <div class="q-card ${
        C.rowClass
          ? C.rowClass(dec)
          : dec === "BUY" || dec === "ADD"
            ? "row-bull"
            : dec === "EXIT" || dec === "AVOID"
              ? "row-bear"
              : "row-dim"
      }">
        ${C.buildCardHtml ? C.buildCardHtml(row) : ""}

        <div class="card-meta mt-2">

          ${
            posLine
              ? `
          <div class="meta-line">
            <span class="meta-key">Position</span>
            <span class="meta-val">${posLine}</span>
          </div>`
              : ""
          }

          ${
            action || conf
              ? `
          <div class="meta-line">
            <span class="meta-key">Action</span>
            <span class="meta-val">
              ${C.htmlEscape(action)}${conf ? ` · Conf ${conf}` : ""}
            </span>
          </div>`
              : ""
          }

          ${
            urg || urgNote
              ? `
          <div class="meta-line">
            <span class="meta-key">Urgency</span>
            <span class="meta-val">
              ${C.htmlEscape(urg)}${
                urgNote ? ` · ${C.htmlEscape(urgNote)}` : ""
              }
            </span>
          </div>`
              : ""
          }

          ${
            trendLabel
              ? `
          <div class="meta-line meta-trend">
            <span class="meta-key">Trend</span>
            <span class="meta-val">
              ${trendLabel}${trendMeter ? ` ${trendMeter}` : ""}
            </span>
          </div>`
              : ""
          }

          ${
            dynamicLine
              ? `
          <div class="meta-line">
            <span class="meta-key">Trade</span>
            <span class="meta-val">
              ${dynamicLine}
            </span>
          </div>`
              : ""
          }

          ${
            has52w
              ? `
          <div class="meta-line">
            <span class="meta-key">52W</span>
            <span class="meta-val">
              ${C.fmtNum(lo52, 1)} – ${C.fmtNum(hi52, 1)}
            </span>
          </div>`
              : ""
          }

        </div>
      </div>
    `;
  }

  Cockpit.renderCards = function (containerId, rows) {
    const el = document.getElementById(containerId);
    if (!el) return;

    Cockpit.makeGrid(el);

    if (!rows || !rows.length) {
      el.innerHTML = `
        <div class="q-card row-dim">
          <div class="q-card-top">
            <span class="sym q-muted">No actionable symbols.</span>
          </div>
        </div>`;
      return;
    }

    const html = rows.map((r) => renderCard(r)).join("");
    el.innerHTML = html;
  };

  C.renderHistoryCards = function (containerId, rows) {
    const el = document.getElementById(containerId);
    if (!el) return;
    C.makeGrid(el);

    if (!rows || !rows.length) {
      el.innerHTML = `
        <div class="q-card row-dim">
          <div class="q-card-top">
            <span class="sym q-muted">No archived items yet.</span>
          </div>
        </div>`;
      return;
    }

    el.innerHTML = rows
      .slice()
      .reverse()
      .map((r) => C.buildHistoryCard(r))
      .join("");
  };

  // ------------------------------------------------------------
  // 7. Backwards-compat: expose helpers on window.qs as well
  // ------------------------------------------------------------
  qs.renderCards = C.renderCards;
  qs.spinGrid = C.spinGrid;
  qs.errorGrid = C.errorGrid;
  qs.sortByDecisionScore = C.sortByDecisionScore;
  qs.sortByEarly = C.sortByEarly;
  qs.fetchSummaryRows = C.fetchSummaryRows;
})(window.Cockpit, window.qs);
