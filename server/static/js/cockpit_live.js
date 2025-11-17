// queen/server/static/js/cockpit_live.js
// ============================================================
// Queen Cockpit — Live Page Orchestrator (v1.0)
// Uses qs.* helpers from cockpit_core / cockpit_cards / cockpit_ui
// ============================================================

(function (qs) {
  let es = null;
  let lastRows = [];

  function getControls(ids) {
    return {
      intervalEl: document.getElementById(ids.intervalId),
      bookEl: document.getElementById(ids.bookId),
      symbolsEl: document.getElementById(ids.symbolsId),
      sortEarlyEl: ids.sortEarlyId
        ? document.getElementById(ids.sortEarlyId)
        : null,
      startBtn: document.getElementById(ids.startBtnId),
      stopBtn: document.getElementById(ids.stopBtnId),
      gridId: ids.gridId,
      tickSec: ids.tickSec || 12,
    };
  }

  async function paintOnceLive(ctrl) {
    if (!qs || !qs.noStore) {
      console.warn("[live] qs helpers not ready yet");
      return;
    }

    const { intervalEl, bookEl, symbolsEl, gridId } = ctrl;
    if (!intervalEl || !bookEl || !symbolsEl) {
      console.warn("[live] controls missing", {
        intervalEl,
        bookEl,
        symbolsEl,
      });
      return;
    }

    qs.spinGrid(gridId);

    const iv = intervalEl.value || "15";
    const book = bookEl.value || "all";
    const raw = (symbolsEl.value || "").trim();

    const syms =
      raw && raw.toUpperCase() !== "ALL"
        ? raw
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [];

    await qs.loadPositions(book);

    const url = new URL("/cockpit/api/summary", window.location.origin);
    url.searchParams.set("interval", iv);
    url.searchParams.set("book", book);
    syms.forEach((s) => url.searchParams.append("symbols", s));

    try {
      const j = await qs.noStore(url).then((r) => r.json());
      const rows = Array.isArray(j.rows) ? j.rows : [];
      lastRows = rows;
      qs.renderCards(gridId, rows);
    } catch (e) {
      console.error("[live] paintOnceLive failed", e);
      qs.errorGrid(gridId, e);
    }
  }

  function stopStream() {
    if (es) {
      es.close();
      es = null;
    }
  }

  function startStream(ctrl) {
    stopStream();

    const { intervalEl, bookEl, symbolsEl, sortEarlyEl, gridId, tickSec } =
      ctrl;
    const iv = intervalEl.value || "15";
    const book = bookEl.value || "all";
    const raw = (symbolsEl.value || "").trim();

    const syms =
      raw && raw.toUpperCase() !== "ALL"
        ? raw
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [];

    const url = new URL("/monitor/stream_actionable", window.location.origin);
    url.searchParams.set("interval", iv);
    url.searchParams.set("book", book);
    url.searchParams.set("tick_sec", String(tickSec || 12));
    syms.forEach((s) => url.searchParams.append("symbols", s));

    es = new EventSource(url);

    es.onmessage = async (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        if (Array.isArray(payload.rows)) {
          lastRows = payload.rows;

          await qs.loadPositions(book);

          const sortEarly = !!(sortEarlyEl && sortEarlyEl.checked);
          const sorted = sortEarly
            ? qs.sortByEarly(lastRows)
            : qs.sortByDecisionScore(lastRows);

          qs.renderCards(gridId, sorted);
        }
      } catch (e) {
        console.warn("[live] SSE onmessage parse error", e);
      }
    };

    es.onerror = () => {
      console.warn("[live] SSE error, stopping stream");
      stopStream();
    };
  }

  // ----------------------------------------------------------
  // Public entrypoint
  // ----------------------------------------------------------
  qs.initLivePage = function (ids) {
    const ctrl = getControls(
      Object.assign(
        {
          gridId: "liveGrid",
          intervalId: "interval",
          bookId: "book",
          symbolsId: "symbols",
          sortEarlyId: "sortEarlyToggle",
          startBtnId: "startBtn",
          stopBtnId: "stopBtn",
          tickSec: 12,
        },
        ids || {},
      ),
    );

    if (!ctrl.startBtn || !ctrl.stopBtn) {
      console.warn("[live] start/stop buttons missing", ctrl);
      return;
    }

    ctrl.startBtn.onclick = () => {
      paintOnceLive(ctrl).then(() => startStream(ctrl));
    };
    ctrl.stopBtn.onclick = () => {
      stopStream();
    };

    // Initial load: books → first paint
    if (qs.loadBooks) {
      qs.loadBooks(ctrl.bookEl.id).then(() => paintOnceLive(ctrl));
    } else {
      console.warn("[live] qs.loadBooks missing");
      paintOnceLive(ctrl);
    }

    if (qs.initSessionBadge) {
      qs.initSessionBadge("sessionBadge");
    }
  };
})(window.qs || (window.qs = {}));
