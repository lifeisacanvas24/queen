// queen/server/static/js/cockpit_ui.js
// ============================================================
// Queen Cockpit UI Helpers — v1.1 (globals, no ES modules)
// Exposes helpers via window.Cockpit and window.qs
// ============================================================

window.Cockpit = window.Cockpit || {};
window.qs = window.qs || {};

(function (C) {
  /* ---------- Number formatting ---------- */
  C.fmt = function (x) {
    if (x === null || x === undefined || x === "" || x === "--") return "—";
    if (typeof x === "number") {
      if (Math.abs(x) >= 1_000_000) {
        return (
          (x / 1_000_000).toLocaleString(undefined, {
            maximumFractionDigits: 2,
          }) + "M"
        );
      }
      if (Math.abs(x) >= 1_000) {
        return (
          (x / 1_000).toLocaleString(undefined, {
            maximumFractionDigits: 1,
          }) + "K"
        );
      }
      return x.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
    return x;
  };

  /* ---------- Pills + badges ---------- */
  C.pill = function (text, tone) {
    const t = tone || "gray";
    return `<span class="pill ${t}">${text}</span>`;
  };

  C.decisionBadge = function (dec) {
    const d = (dec || "").toUpperCase();
    const map = {
      BUY: "green",
      ADD: "green",
      HOLD: "amber",
      EXIT: "red",
      AVOID: "red",
    };
    const tone = map[d] || "amber";
    return `<span class="badge ${tone}">${d || ""}</span>`;
  };

  C.normalizeCtx = function (x) {
    if (!x) return "Unknown";
    const s = String(x);
    return s.includes("/") ? s.split("/")[0].trim() : s;
  };

  C.rsiBadge = function (v) {
    if (v == null || isNaN(v)) return C.pill("—", "gray");
    const n = Number(v);
    const tone = n >= 60 ? "green" : n >= 45 ? "amber" : "red";
    return C.pill(n.toFixed(1), tone);
  };

  C.cprBadge = function (ctxRaw) {
    const ctx = C.normalizeCtx(ctxRaw);
    const tone =
      ctx === "Above"
        ? "green"
        : ctx === "At"
          ? "gray"
          : ctx === "Below"
            ? "red"
            : "amber";
    return C.pill(ctx, tone);
  };

  C.emaBadge = function (bias) {
    const b = bias || "Neutral";
    const tone = b === "Bullish" ? "green" : b === "Bearish" ? "red" : "gray";
    return C.pill(b, tone);
  };

  /* ---------- PnL ---------- */
  C.computePnl = function (cmp, pos) {
    if (!pos || cmp == null) return null;
    const qty = Number(pos.qty || 0);
    const avg = Number(pos.avg_price || 0);
    if (!(qty > 0) || !(avg > 0)) return null;
    return { abs: (cmp - avg) * qty };
  };

  C.pnlChip = function (sym, cmp) {
    const posMap = C.posMap || {};
    const p = posMap[sym];
    if (!p) return "";
    const res = C.computePnl(cmp, p);
    if (!res) {
      return `<span class="pnl-chip pnl-flat"><span class="pnl-val">—</span></span>`;
    }
    const cls =
      res.abs > 1e-6 ? "pnl-up" : res.abs < -1e-6 ? "pnl-dn" : "pnl-flat";
    const abs = res.abs.toLocaleString(undefined, {
      maximumFractionDigits: 0,
    });
    return `<span class="pnl-chip ${cls}"><span class="pnl-val">₹${abs}</span></span>`;
  };

  /* ---------- Session badge + row class ---------- */
  C.sessionBadge = function (session) {
    const s = (session || "").toLowerCase();
    let tone = "session-post";
    let label = "Unknown";

    if (s === "live" || s === "regular" || s === "open") {
      tone = "session-live";
      label = "LIVE";
    } else if (s === "pre-open") {
      tone = "session-preopen";
      label = "PRE-OPEN";
    } else if (s === "post-market" || s === "closed") {
      tone = "session-post";
      label = "POST-MKT";
    } else if (s === "weekend") {
      tone = "session-weekend";
      label = "WEEKEND";
    } else if (s === "holiday") {
      tone = "session-holiday";
      label = "HOLIDAY";
    }

    return `<span class="pill session ${tone}">${label}</span>`;
  };

  C.rowClass = function (dec) {
    const d = (dec || "").toUpperCase();
    if (d === "BUY" || d === "ADD") return "row-bull";
    if (d === "EXIT" || d === "AVOID") return "row-bear";
    return "row-dim";
  };
})(window.Cockpit);

// Adapter to window.qs
window.qs = window.qs || {};
// adapter -> qs
(function (qs, C) {
  qs.fmt = qs.fmt || C.fmt;
  qs.pill = qs.pill || C.pill;
  qs.decisionBadge = qs.decisionBadge || C.decisionBadge;
  qs.rsiBadge = qs.rsiBadge || C.rsiBadge;
  qs.cprBadge = qs.cprBadge || C.cprBadge;
  qs.emaBadge = qs.emaBadge || C.emaBadge;
  qs.pnlChip = qs.pnlChip || C.pnlChip;
  qs.sessionBadge = qs.sessionBadge || C.sessionBadge;
  qs.rowClass = qs.rowClass || C.rowClass;

  // 🔴 Missing today — add these:
  qs.noStore = qs.noStore || C.noStore;
  qs.safeFetchJson = qs.safeFetchJson || C.safeFetchJson;
})(window.qs, window.Cockpit);
