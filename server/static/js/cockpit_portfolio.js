// queen/server/static/js/cockpit_portfolio.js
// ============================================================
// Queen Cockpit Portfolio — v1.0
// Books, positions & PnL chip
// Requires: cockpit_core.js
// ============================================================

window.Cockpit = window.Cockpit || {};

(function (C) {
  // ------------------------------------------------------------
  // 1. Books loader
  // ------------------------------------------------------------
  C.loadBooks = async function (selOrId) {
    const el =
      typeof selOrId === "string" ? document.getElementById(selOrId) : selOrId;
    if (!el) return;

    try {
      const r = await fetch("/portfolio/books", { cache: "no-store" });
      const j = await r.json();
      const list = j.books || ["all"];
      el.innerHTML = "";
      list.forEach((b) => {
        const o = document.createElement("option");
        o.value = b;
        o.textContent = b;
        el.appendChild(o);
      });
    } catch (e) {
      el.innerHTML = `<option value="all">all</option>`;
    }
  };

  C.loadBooksIntoSelect = function (id) {
    return C.loadBooks(id);
  };

  // ------------------------------------------------------------
  // 2. Positions + PnL chip
  // ------------------------------------------------------------
  C.posMap = C.posMap || {}; // { SYM: {qty, avg_price} }

  C.loadPositions = async function (book) {
    try {
      const r = await fetch(
        `/portfolio/positions?book=${encodeURIComponent(book)}`,
        { cache: "no-store" },
      );
      const j = await r.json();
      C.posMap = j && j.positions ? j.positions : {};
    } catch (_) {
      C.posMap = {};
    }
  };

  C.computePnl = function (cmp, p) {
    if (!p || cmp == null) return null;
    const qty = Number(p.qty || 0);
    const avg = Number(p.avg_price || 0);
    if (!(qty > 0) || !(avg > 0)) return null;
    const abs = (cmp - avg) * qty;
    return { abs };
  };

  C.pnlChip = function (sym, cmp) {
    const p = C.posMap && C.posMap[sym];
    if (!p) return "";
    const res = C.computePnl(Number(cmp), p);
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
})(window.Cockpit);
