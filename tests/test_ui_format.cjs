const { test } = require("node:test");
const assert = require("node:assert/strict");
const {
  formatExactDecimal,
  inlineTokens,
  formatCompactDecimal,
} = require("../src/settlement_recon/workspace_format.js");

test("compact risk values explicitly truncate without losing integer precision", () => {
  assert.equal(
    formatCompactDecimal("20275170000000001.23456789"),
    "20,275,170,000,000,001.234567…",
  );
  assert.equal(formatCompactDecimal("-0.0000000001"), "-0.000000…");
  assert.equal(formatCompactDecimal("106084.000"), "106,084");
});

test("large financial results retain all digits, including values beyond Number precision", () => {
  assert.equal(
    formatExactDecimal("20275170000000001.234567890123456789"),
    "20,275,170,000,000,001.234567890123456789",
  );
  assert.equal(formatExactDecimal("106084.000"), "106,084");
  assert.equal(
    formatExactDecimal("0.000000000000000001"),
    "0.000000000000000001",
  );
  assert.equal(formatExactDecimal("-1234.50"), "-1,234.5");
  assert.equal(formatExactDecimal("0.000"), "0");
});

test("bold source identifiers retain their nested code formatting", () => {
  assert.deepEqual(inlineTokens("Read **`EUR/USD`** evidence"), [
    { type: "text", value: "Read " },
    { type: "strong", children: [{ type: "code", value: "EUR/USD" }] },
    { type: "text", value: " evidence" },
  ]);
});

test("untrusted markup and javascript links stay inert text tokens", () => {
  const text = "<img src=x onerror=alert(1)> [source](javascript:alert(1))";
  assert.deepEqual(inlineTokens(text), [{ type: "text", value: text }]);
});
