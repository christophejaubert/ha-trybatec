// Isolated DOM simulation, no HA calls or live browser panel changes.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const js = readFileSync(new URL("../../custom_components/trybatec/panel/energy-bulk-draft-l7.js", import.meta.url), "utf8");
const { renderEnergyBulkDraft } = await import("data:text/javascript;charset=utf-8," + encodeURIComponent(js));

class Element {
  constructor(tag) { this.tag = tag; this.attributes = {}; this.children = []; this.textContent = ""; this.disabled = false; }
  setAttribute(key, value) { this.attributes[key] = value; }
  append(child) { this.children.push(child); }
}
globalThis.document = { createElement: (tag) => new Element(tag) };
const flatten = (node) => [node, ...node.children.flatMap(flatten)];

for (const lang of ["fr", "en"]) {
  const frag = renderEnergyBulkDraft({ fluids: {
    EF: { status:"blocked", reasons:["<script>unsafe markup</script>"] },
    ECS: { status:"already_configured", reasons:[] },
    CET: { status:"insufficient_evidence", reasons:["recorder_unverified"] },
  }}, lang, "/trybatec/overview");
  const children = flatten(frag);
  assert.equal(frag.tag, "section");
  assert.equal(children.filter(x => x.tag === "li").length, 3);
  const button = children.find(x => x.tag === "button");
  assert.equal(button.disabled, true);
  assert.equal(children.find(x => x.tag === "a").attributes.href, "/trybatec/overview");
  assert.equal(children.find(x => x.tag === "p").attributes["role"], "status");
  assert.equal(children.find(x => x.tag === "small").textContent.includes("<script>"), true);
  assert.equal(children.some(x => x.tag === "script"), false);
  assert.equal(JSON.stringify(children).includes("fetch("), false);
}
const rejectURL = renderEnergyBulkDraft(null, "en", "https://evil.invalid/");
assert.equal(flatten(rejectURL).find(x => x.tag === "a").attributes.href, "#");
assert.equal(flatten(rejectURL).find(x => x.tag === "button").disabled, true);
console.log("L7 standalone UI FR/EN, disabled control, fallback and DOM-safety tests passed");
