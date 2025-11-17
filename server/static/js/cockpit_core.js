// queen/server/static/js/cockpit_core.js
// ============================================================
// Queen Cockpit Core — v1.0
// Core helpers & shared mappings
// Global namespace: window.Cockpit
// ============================================================

window.Cockpit = window.Cockpit || {};

(function (C) {
  // ------------------------------------------------------------
  // 1. Fetch helpers
  // ------------------------------------------------------------
  C.noStore = function (url) {
    const u = url instanceof URL ? url : new URL(url, window.location.origin);
    u.searchParams.set("_", Date.now());
    return fetch(u, { cache: "no-store" });
  };

  C.safeFetchJson = async function (url) {
    try {
      const r = await C.noStore(url);
      return await r.json();
    } catch (e) {
      console.error("[Cockpit.safeFetchJson] error:", e);
      return null;
    }
  };

  // ------------------------------------------------------------
  // 2. Formatting helpers
  // ------------------------------------------------------------
  C.fmtNum = function (x, digits = 1) {
    if (x === null || x === undefined || x === "" || x === "—") return "—";
    if (typeof x !== "number") return x;
    return x.toLocaleString(undefined, { maximumFractionDigits: digits });
  };

  C.fmtInt = function (x) {
    if (x === null || x === undefined) return "—";
    if (typeof x !== "number") return x;
    return x.toLocaleString();
  };

  C.fmtKMB = function (x) {
    if (x == null) return "—";
    if (typeof x !== "number") return x;
    const abs = Math.abs(x);
    if (abs >= 1_000_000_000) return (x / 1_000_000_000).toFixed(2) + "B";
    if (abs >= 1_000_000) return (x / 1_000_000).toFixed(2) + "M";
    if (abs >= 1_000) return (x / 1_000).toFixed(1) + "K";
    return x.toString();
  };

  C.fmtNumGeneric = function (x, digits = 2) {
    if (x === null || x === undefined || x === "—" || x === "--") return "—";
    if (typeof x === "number") {
      return x.toLocaleString(undefined, { maximumFractionDigits: digits });
    }
    return String(x);
  };

  // ------------------------------------------------------------
  // 3. DOM & small utilities
  // ------------------------------------------------------------
  C.qs = function (sel) {
    return document.querySelector(sel);
  };

  C.qsa = function (sel) {
    return Array.from(document.querySelectorAll(sel));
  };

  C.htmlEscape = function (str) {
    if (str == null) return "—";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  };

  C.ensureArray = function (v) {
    if (Array.isArray(v)) return v;
    if (v == null) return [];
    return [v];
  };

  C.normCtx = function (x) {
    if (!x) return "Unknown";
    const s = String(x);
    return s.includes("/") ? s.split("/")[0].trim() : s;
  };

  // ------------------------------------------------------------
  // 4. Grid helper (base)
  // ------------------------------------------------------------
  C.makeGrid = function (containerSel) {
    const el =
      typeof containerSel === "string"
        ? document.getElementById(containerSel) || C.qs(containerSel)
        : containerSel;
    if (!el) return;
    el.classList.add("card-grid"); // unified grid class
  };

  // ------------------------------------------------------------
  // 5. Shared mappings
  // ------------------------------------------------------------
  C.PR_MAP = {
    BUY: 0,
    ADD: 0,
    HOLD: 1,
    EXIT: 2,
    AVOID: 3,
  };

  C.DECISION_COLOR = {
    BUY: "green",
    ADD: "green",
    HOLD: "amber",
    EXIT: "red",
    AVOID: "red",
  };
})(window.Cockpit);
