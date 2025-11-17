// queen/server/static/js/cockpit_compat.js
// ============================================================
// Queen Cockpit Compat — v1.0
// Thin adapter: window.qs → window.Cockpit
// Keeps existing templates working (qs.*)
// ============================================================

window.Cockpit = window.Cockpit || {};
window.qs = window.qs || {};

(function (qs, C) {
  // fetchers
  qs.noStore = C.noStore;
  qs.safeFetchJson = C.safeFetchJson;

  // formatting
  qs.fmtNum = C.fmtNum;
  qs.fmtInt = C.fmtInt;
  qs.fmtKMB = C.fmtKMB;

  // DOM
  qs.qs = C.qs;
  qs.qsa = C.qsa;

  // books + positions
  qs.loadBooksIntoSelect = C.loadBooksIntoSelect;
  qs.loadBooks = C.loadBooks;
  qs.loadPositions = C.loadPositions;
  qs.posMap = C.posMap;

  // PnL
  qs.pnlChip = C.pnlChip;

  // badges
  qs.cprBadge = C.cprBadge;
  qs.emaBadge = C.emaBadge;
  qs.rsiBadge = C.rsiBadge;
  qs.decisionBadge = C.decisionBadge;

  // summary fetch
  qs.fetchSummaryRows = C.fetchSummaryRows;

  // sorting
  qs.sortByEarly = C.sortByEarly;
  qs.sortByDecisionScore = C.sortByDecisionScore;

  // cards + grids
  qs.buildCardHtml = C.buildCardHtml;
  qs.buildHistoryCard = C.buildHistoryCard;
  qs.renderCards = C.renderCards;
  qs.renderHistoryCards = C.renderHistoryCards;
  qs.spinGrid = C.spinGrid;
  qs.errorGrid = C.errorGrid;
})(window.qs, window.Cockpit);
