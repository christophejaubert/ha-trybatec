/* FR : attestation de forme du rapport synthétique avant export public.
 * EN: validate synthetic-only report shape before uploading any public artifact.
 * Never print unexpected payload contents on failure.
 */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");

const TABS = ["overview", "meters", "history", "tariffs", "energy", "diagnostics", "settings"];
const CONFIGS = ["fr-FR", "en-US"].flatMap(language =>
  ["desktop", "mobile"].flatMap(device =>
    ["light", "dark"].map(theme => JSON.stringify({language, device, theme}))));

function validate(report) {
  assert.equal(report?.mode, "synthetic-only");
  assert.equal(report.summary?.syntheticCases, 56);
  assert.equal(report.summary?.realHomeAssistantRecettes, 0);
  assert.equal(Array.isArray(report.results), true);
  assert.equal(report.results.length, 8);
  const seen = new Set();
  for (const record of report.results) {
    assert.equal(record.humanHA, false);
    assert.equal(record.voiceOverTalkBack, "NOT_TESTED");
    assert.equal(record.wcagAA, "NOT_ASSERTED");
    assert.deepEqual(record.errors, []);
    assert.deepEqual(record.prohibited, []);
    const config = JSON.stringify(record.config);
    assert.ok(CONFIGS.includes(config), "Unknown synthetic viewport configuration");
    assert.ok(!seen.has(config), "Repeated viewport configuration");
    seen.add(config);
    assert.deepEqual(record.results.map(row => row.tab), TABS);
  }
  assert.equal(seen.size, 8);
  const raw = JSON.stringify(report);
  assert.ok(Buffer.byteLength(raw, "utf8") <= 1024 * 1024, "Oversized report");
  assert.ok(!/https?:\/\/|\bBearer\s+[\w.-]+|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/i.test(raw),
    "Unexpected identifier or external destination in synthetic report");
  assert.ok(!/"(?:access_token|refresh_token|api_key|secret|password|authorization|device_uuid|entry_id|serial)"\s*:/i.test(raw),
    "Potential private identifier key in synthetic report");
  return {syntheticCases: 56, realHomeAssistantRecettes: 0};
}

if (require.main === module) {
  try {
    assert.equal(process.argv.length, 3);
    const reportPath = process.argv[2];
    const metadata = fs.statSync(reportPath);
    assert.ok(metadata.isFile() && metadata.size <= 1024 * 1024);
    validate(JSON.parse(fs.readFileSync(reportPath, "utf8")));
    console.log("FR/EN: Synthetic report structure verified, no live HA evidence.");
  } catch {
    console.error("FR/EN: Synthetic report rejected; content withheld.");
    process.exitCode = 1;
  }
}
module.exports = {validate};
