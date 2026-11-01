const { test } = require("node:test");
const assert = require("node:assert/strict");
const {
  formatExactDecimal,
} = require("../src/settlement_recon/workspace_format.js");

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
