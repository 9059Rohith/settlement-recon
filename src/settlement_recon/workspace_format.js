/* Financial presentation must not coerce exact decimal strings into IEEE-754 Numbers. */
(function (root) {
  "use strict";
  function retryAfterSeconds(value, now = Date.now()) {
    if (typeof value !== "string") return 0;
    const header = value.trim();
    const seconds = /^\d+$/.test(header)
      ? Number(header)
      : (Date.parse(header) - now) / 1000;
    return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : 0;
  }
  function formatExactDecimal(value) {
    const text = String(value);
    if (!/^-?\d+(\.\d+)?$/.test(text)) return text;
    const [whole, fraction = ""] = text.split(".");
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    const trimmed = fraction.replace(/0+$/, "");
    return grouped + (trimmed ? "." + trimmed : "");
  }
  function inlineTokens(value) {
    const text = String(value).slice(0, 20000);
    const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https:\/\/[^\s)]+\))/g;
    const tokens = [];
    let last = 0;
    for (const match of text.matchAll(pattern)) {
      if (match.index > last)
        tokens.push({ type: "text", value: text.slice(last, match.index) });
      const token = match[0];
      if (token.startsWith("**"))
        tokens.push({
          type: "strong",
          children: inlineTokens(token.slice(2, -2)),
        });
      else if (token.startsWith("`"))
        tokens.push({ type: "code", value: token.slice(1, -1) });
      else {
        const split = token.indexOf("](");
        tokens.push({
          type: "link",
          value: token.slice(1, split),
          href: token.slice(split + 2, -1),
        });
      }
      last = match.index + token.length;
    }
    if (last < text.length)
      tokens.push({ type: "text", value: text.slice(last) });
    return tokens;
  }
  function formatCompactDecimal(value) {
    const formatted = formatExactDecimal(value);
    const [whole, fraction = ""] = formatted.split(".");
    return fraction.length > 6
      ? whole + "." + fraction.slice(0, 6) + "…"
      : formatted;
  }
  const api = Object.freeze({
    formatExactDecimal,
    inlineTokens,
    formatCompactDecimal,
    retryAfterSeconds,
  });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ReconFormat = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
