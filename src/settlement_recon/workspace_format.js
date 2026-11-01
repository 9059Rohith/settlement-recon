/* Financial presentation must not coerce exact decimal strings into IEEE-754 Numbers. */
(function (root) {
  "use strict";
  function formatExactDecimal(value) {
    const text = String(value);
    if (!/^-?\d+(\.\d+)?$/.test(text)) return text;
    const [whole, fraction = ""] = text.split(".");
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    const trimmed = fraction.replace(/0+$/, "");
    return grouped + (trimmed ? "." + trimmed : "");
  }
  const api = Object.freeze({ formatExactDecimal });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReconFormat = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
