/* FR/EN: no actual HA data or live network for these validator tests. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {validate} = require("./validate_a11y_report.cjs");

function sample() {
  const tabs = ["overview", "meters", "history", "tariffs", "energy", "diagnostics", "settings"];
  return {
    mode: "synthetic-only",
    summary: {syntheticCases: 56, realHomeAssistantRecettes: 0},
    results: ["fr-FR", "en-US"].flatMap(language =>
      ["desktop", "mobile"].flatMap(device =>
        ["light", "dark"].map(theme => ({
          config: {language, device, theme}, humanHA: false,
          voiceOverTalkBack: "NOT_TESTED", wcagAA: "NOT_ASSERTED",
          errors: [], prohibited: [], results: tabs.map(tab => ({tab}))
        }))))
  };
}
test("FR/EN: valid synthetic matrix", () => {
  assert.equal(validate(sample()).syntheticCases, 56);
});
test("FR/EN: reject real HA evidence", () => {
  const data = sample();
  data.summary.realHomeAssistantRecettes = 1;
  assert.throws(() => validate(data));
});
test("FR/EN: reject duplicate synthetic configurations", () => {
  const data = sample();
  data.results[1].config = data.results[0].config;
  assert.throws(() => validate(data));
});
test("FR/EN: reject secret-shaped keys and external destinations", () => {
  const data = sample();
  data.results[0].access_token = "SYNTHETIC-NOT-A-TOKEN";
  assert.throws(() => validate(data));
  delete data.results[0].access_token;
  data.results[0].results[0].label = "https://invalid.example/identifier";
  assert.throws(() => validate(data));
});
