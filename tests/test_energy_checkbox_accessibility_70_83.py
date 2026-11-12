"""Synthetic bilingual checkbox labels and touch target contracts (#70/#83).

Do not invoke Home Assistant, Recorder, Energy or supplier services.
"""
from pathlib import Path
import shutil
import subprocess

import pytest


PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"


def test_energy_confirmation_labels_are_bilingual_and_read_only():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for executable frontend tests")
    script = r'''
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync(process.argv[1],"utf8");
const context={HTMLElement:class{},customElements:{get:()=>false,define:()=>{}}};
vm.runInNewContext(source+";globalThis.__Panel=TrybatecPanel;",context,{timeout:3000});
const panel=context.__Panel.prototype;
const fixture={
  _current:{ledger:{series:[],pending:0},meters:[]},
  _data:{energy:{sources:[]}},
  _historyStart:"2026-01-01",_historyEnd:"2026-01-02",
  _versionPlan:null,_versionVerify:null,_versionEnergyPlan:null,
  _versionBusy:false,_versionOld:"",_versionNew:"",
  _versionError:"",_versionMessage:"",
  _date:x=>String(x),
};
const english=panel._recorderVersionWorkflow.call({
  ...fixture,_t:(fr,en)=>en
});
for(const label of [
  "A recoverable HA/Recorder backup is available",
  "I approve a new version",
  "Resume a pending import",
  "Energy backup confirmed",
  "I approve rollback to an archived version",
]){
  assert.ok(english.includes(label),"Missing English label: "+label);
}
for(const french of [
  "Une sauvegarde récupérable", "J’approuve", "Reprendre une importation",
  "Sauvegarde Énergie confirmée"
]){
  assert.ok(!english.includes(french),"Untranslated confirmation: "+french);
}
const french=panel._recorderVersionWorkflow.call({
  ...fixture,_t:(fr,en)=>fr
});
for(const label of [
  "Une sauvegarde récupérable de HA/Recorder existe",
  "J’approuve une nouvelle version",
  "Reprendre une importation en attente",
  "Sauvegarde Énergie confirmée",
  "J’approuve le retour vers une version archivée"
]){
  assert.ok(french.includes(label),"Missing French label: "+label);
}
assert.ok(english.includes("data-version-import"));
assert.ok(english.includes("data-version-energy-apply"));
console.log("Bilingual confirmations: PASS");
'''
    result = subprocess.run(
        [node, "-e", script, str(PANEL)],
        capture_output=True, text=True, check=False, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_checkbox_label_has_minimum_surface_height():
    source = PANEL.read_text(encoding="utf-8")
    assert ".actions>label{display:inline-flex;align-items:center;gap:8px;min-height:32px;max-width:100%}" in source
