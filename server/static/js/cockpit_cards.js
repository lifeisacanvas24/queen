// queen/server/static/js/cockpit_cards.js
// ============================================================
// Queen Cockpit Cards — v1.0
// Pills, cards, grids, sorting, history
// Requires: cockpit_core.js, cockpit_portfolio.js
// ============================================================

window.Cockpit = window.Cockpit || {};

(function (C) {
  // ------------------------------------------------------------
  // 1. Pills & badges
  // ------------------------------------------------------------
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
      if (eb !== ea) return eb - ea; // early desc
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
    const targets = (r.targets || []).join(" · ");

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

  // ------------------------------------------------------------
  // 6. Grid renderers
  // ------------------------------------------------------------
  C.renderCards = function (containerId, rows) {
    const el = document.getElementById(containerId);
    if (!el) return;
    C.makeGrid(el);

    if (!rows || !rows.length) {
      el.innerHTML = `
        <div class="q-card row-dim">
          <div class="q-card-top">
            <span class="sym q-muted">No items.</span>
          </div>
        </div>`;
      return;
    }

    el.innerHTML = rows.map(C.buildCardHtml).join("");
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
})(window.Cockpit);
