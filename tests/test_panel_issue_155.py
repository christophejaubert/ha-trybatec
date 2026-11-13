"""#155 — FR : régressions du panneau / EN: panel UI regression tests.

Only local JavaScript and synthetic fixtures are executed. No Home Assistant,
Trybatec portal, Recorder or Energy endpoint is accessed.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "custom_components/trybatec/panel/trybatec-panel.js"
EN = ROOT / "custom_components/trybatec/translations/en.json"
STRINGS = ROOT / "custom_components/trybatec/strings.json"
GLOBAL_COVERAGE = ROOT / "custom_components/trybatec/panel_tariff_years.py"


def test_global_scan_and_copy_remain_read_only():
    source = PANEL.read_text(encoding="utf-8")
    coverage = GLOBAL_COVERAGE.read_text(encoding="utf-8")
    assert 'kind:"tariff_year_coverage"' in source
    assert "Rechercher les relevés de tous les compteurs" in source
    assert "Recherche globale achevée" in source
    assert "data-tariff-years-cancel" in source
    assert "history_windows(_EARLIEST_SUPPORTED_DATE, today)" in coverage
    assert "coordinator._history_lock" in coverage
    assert '"recorder_writes": False' in coverage
    assert '"energy_writes": False' in coverage
    for text in (
        source,
        EN.read_text(encoding="utf-8"),
        STRINGS.read_text(encoding="utf-8"),
    ):
        for unwanted in (
            "Aucun historique fictif",
            "Aucun coût fictif",
            "aucun relevé inventé",
            "n’est inventée",
            "valeur supposée",
            "No fictitious",
            "never fabricates measured indexes",
        ):
            assert unwanted.casefold() not in text.casefold(), unwanted
    # Provenance and estimation safeguards remain meaningful.
    assert "Hypothèse approuvée" in source
    assert "Consommation réellement mesurée" in source
    assert "Consommation estimée" in source


def test_status_card_global_scan_and_meter_reveal_execute_in_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for executable panel behavior checks")
    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const source = fs.readFileSync(process.argv[1], "utf8");
const sandbox = {
  HTMLElement: class {},
  customElements: {get:()=>false, define:()=>{}},
  window: {matchMedia:()=>({matches:true})},
};
vm.runInNewContext(source+"\nglobalThis.__panel = TrybatecPanel.prototype;", sandbox, {timeout:4000});
const panel=sandbox.__panel;
const meters=[
  {physical_key:"a".repeat(24),serial:"SYNTH-1",lot:"SYNTH-LOT",fluid:"EF",status:"en_service"},
  {physical_key:"b".repeat(24),serial:"SYNTH-2",lot:"SYNTH-LOT",fluid:"ECS",status:"depose"},
];
const account={
  entry_id:"SYNTH-ENTRY",data_loaded:true,meters,
  entities:[],tariffs:{},meter_tariffs:{},
};
const fixture={
  _current:account, _data:{energy:{sources:[]}},_meter:0,_query:"",
  _tariffCoverage:new Map(),_tariffJobId:null,
  _meters:()=>meters,_counts:()=>({en_service:1,depose:1}),
  _stat:panel._stat,_heading:()=>"",_readinessView:()=>"",
  _meterRow:()=>"",_meterDetail:()=>"<p>details</p>",_meterTimeline:()=>"",
};
let html=panel._overview.call(fixture);
assert.match(html,/stat stat-success/);
assert.match(html,/mdi:check-circle-outline/);
assert.doesNotMatch(html,/stat stat-warning/);
account.entities=[{entity_id:"sensor.synthetic",state:"unavailable"}];
html=panel._overview.call(fixture);
assert.match(html,/stat stat-warning/);
assert.match(html,/mdi:alert-circle-outline/);
account.data_loaded=false;
html=panel._overview.call(fixture);
assert.match(html,/stat stat-unknown/);
assert.match(html,/mdi:help-circle-outline/);
account.data_loaded=true;
account.entities=[];
html=panel._metersPage.call(fixture);
assert.match(html,/Rechercher les relevés de tous les compteurs/);
assert.doesNotMatch(html,/data-tariff-years-cancel/);
fixture._tariffCoverage.set(account.entry_id,{
  status:"complete",meters:[{physical_key:meters[0].physical_key}],
});
html=panel._metersPage.call(fixture);
assert.match(html,/1 compteur\(s\) avec relevés datés sur 2/);
fixture._tariffCoverage.set(account.entry_id,{status:"loading"});
fixture._tariffJobId="SYNTHETIC-JOB";
html=panel._metersPage.call(fixture);
assert.match(html,/Recherche globale en cours/);
assert.match(html,/data-tariff-years-cancel/);
let focuses=0,scrolls=0,selectedFocuses=0;
const detail={focus:()=>{focuses++},scrollIntoView:()=>{scrolls++}};
const selected={focus:()=>{selectedFocuses++}};
const ui={_meter:1,shadowRoot:{querySelector:selector=>
 selector==="[data-meter-detail]"?detail:selected}};
panel._revealSelectedMeterDetail.call(ui);
assert.equal(focuses,1);
assert.equal(scrolls,1);
sandbox.window.matchMedia=()=>({matches:false});
panel._revealSelectedMeterDetail.call(ui);
assert.equal(selectedFocuses,1);
assert.equal(scrolls,1);
assert.match(source,/data-meter-detail tabindex="-1"/);
assert.match(source,/this\._render\(\);this\._revealSelectedMeterDetail\(\);return/);
"""
    completed = subprocess.run(
        [node, "-e", script, str(PANEL)],
        capture_output=True, text=True, timeout=25, check=False,
    )
    assert completed.returncode == 0, completed.stderr
