// queen/server/static/js/cockpit_session.js
// ============================================================
// cockpit_session.js — v11.1
// Shared Market Session Engine + Header Strip helpers
//  - Session badge (LIVE / PREOPEN / REGULAR / POST / WEEKEND / HOLIDAY)
//  - Header clock (qTickClock)
//  - Universe count chip (updateUniverseCount)
//  - Footer timestamp helper (qFillFooterNow)
// ============================================================

window.qs = window.qs || {};
window.Cockpit = window.Cockpit || {};

/* -----------------------------
   1. Fetch market session state
   ----------------------------- */
qs.fetchSessionState = async function () {
  try {
    const r = await fetch("/market/state", { cache: "no-store" });
    const j = await r.json();

    // Expecting: { session: "LIVE" | "PREOPEN" | "REGULAR" | "POST" | "WEEKEND" | "HOLIDAY" }
    if (!j || !j.session) return { session: "UNKNOWN" };
    return j;
  } catch (_) {
    return { session: "UNKNOWN" };
  }
};

/* -----------------------------
   2. Build session badge pill
   ----------------------------- */
qs.sessionBadge = function (session) {
  if (!session) session = "UNKNOWN";
  const key = String(session).toUpperCase();

  const map = {
    LIVE: { cls: "pill session session-live", text: "LIVE" },
    PREOPEN: { cls: "pill session session-preopen", text: "PRE-OPEN" },
    REGULAR: { cls: "pill session session-live", text: "REGULAR" },
    POST: { cls: "pill session session-post", text: "POST-MARKET" },
    CLOSED: { cls: "pill session session-post", text: "CLOSED" },
    WEEKEND: { cls: "pill session session-weekend", text: "WEEKEND" },
    HOLIDAY: { cls: "pill session session-holiday", text: "HOLIDAY" },
    UNKNOWN: { cls: "pill session session-post", text: "UNKNOWN" },
  };

  const m = map[key] || map.UNKNOWN;
  return `<span class="${m.cls}">${m.text}</span>`;
};

/* ----------------------------------------------------------
   3. Attach session badge to a specific element dynamically
   ---------------------------------------------------------- */
qs.initSessionBadge = function (elementId) {
  const el = document.getElementById(elementId);
  if (!el) {
    console.warn("[qs.initSessionBadge] element not found:", elementId);
    return;
  }

  async function update() {
    const j = await qs.fetchSessionState();
    el.innerHTML = qs.sessionBadge(j.session);
  }

  // First paint
  update();

  // Refresh every 60 seconds
  if (el._sessionTimer) clearInterval(el._sessionTimer);
  el._sessionTimer = setInterval(update, 60_000);
};

/* ----------------------------------------------------------
   4. Backwards compatibility for old updateSessionBadge()
   ---------------------------------------------------------- */
window.updateSessionBadge = function () {
  // Uses the header pill: <span id="sessionBadge">
  qs.initSessionBadge("sessionBadge");
};

/* ----------------------------------------------------------
   5. Header clock — qTickClock()
   ---------------------------------------------------------- */
window.qTickClock =
  window.qTickClock ||
  function () {
    const el = document.getElementById("q-clock");
    if (!el) {
      // No clock slot on this page — silently skip
      return;
    }

    function tick() {
      const now = new Date();
      try {
        const t = now.toLocaleTimeString("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
          timeZone: "Asia/Kolkata",
        });
        el.textContent = t + " IST";
      } catch (_) {
        el.textContent = now.toLocaleTimeString();
      }
    }

    tick();
    if (el._clockTimer) clearInterval(el._clockTimer);
    el._clockTimer = setInterval(tick, 1_000);
  };

/* ----------------------------------------------------------
   6. Universe chip — updateUniverseCount()
   ---------------------------------------------------------- */
window.updateUniverseCount =
  window.updateUniverseCount ||
  async function () {
    const el = document.getElementById("q-universe");
    if (!el) {
      // No universe slot on this page — silently skip
      return;
    }

    // Prefer qs.noStore if Cockpit/qs core is loaded
    const noStore =
      (window.qs && qs.noStore) ||
      (window.Cockpit && Cockpit.noStore) ||
      ((url) => fetch(url, { cache: "no-store" }));

    try {
      const url = new URL("/cockpit/api/summary", window.location.origin);
      url.searchParams.set("interval", "15");
      url.searchParams.set("book", "all");

      const j = await noStore(url).then((r) => r.json());
      const rows = Array.isArray(j.rows) ? j.rows : [];
      const n = j.count != null ? j.count : rows.length;

      el.textContent = `${n || "--"} SYMS`;
    } catch (e) {
      // On failure, just show placeholder
      el.textContent = "-- SYMS";
    }
  };

/* ----------------------------------------------------------
   7. Footer timestamp helper — qFillFooterNow()
   ---------------------------------------------------------- */
window.qFillFooterNow =
  window.qFillFooterNow ||
  function () {
    const el = document.getElementById("q-footer-time");
    if (!el) return;

    const now = new Date();
    const ts = now.toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });

    el.textContent = ts + " IST";
  };

/* ----------------------------------------------------------
   8. Auto bootstrap when DOM is ready
   ---------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  try {
    // Session pill
    if (document.getElementById("sessionBadge")) {
      qs.initSessionBadge("sessionBadge");
    }

    // Header clock
    if (document.getElementById("q-clock")) {
      qTickClock();
    }

    // Universe chip
    if (document.getElementById("q-universe")) {
      updateUniverseCount();
    }

    // Footer timestamp
    if (document.getElementById("q-footer-time")) {
      qFillFooterNow();
    }
  } catch (e) {
    console.warn("[cockpit_session bootstrap] error:", e);
  }
});
