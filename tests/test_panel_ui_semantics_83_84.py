"""Synthetic UI state and contextual-navigation regression checks for #83/#84.

Runs against local frontend source with fake account/meter data only. Never
contacts Home Assistant, the supplier, Recorder or Energy.
"""
from pathlib import Path
import shutil
import subprocess

import pytest


PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"


def test_ui_semantic_contracts_are_distinct():
    js = PANEL.read_text(encoding="utf-8")
    assert "data-meter-context" in js
    assert "data-history-context-clear" in js
    assert "this._openMeterContext(btn.dataset.meterContext)" in js
    assert "data-historical-scan" in js
    assert "this._loadTariffYearCoverage(true)" in js
    assert "this._historyContextKey=meter.physical_key" in js
    assert "this._originMeter=meter.physical_key" in js
    assert "const sourceStatus=" in js
    assert 'check(sourceStatus,' in js
    assert 'check(retiredStatus,' in js
    assert 'feature(t("Tarifs annuels (facultatifs)"' in js
    assert "readiness-optional" in js
    assert ".secondary{background:var(--trybatec-neutral-bg)" in js
    assert ".primary{background:var(--trybatec-action-bg)" in js
    assert "button:disabled{cursor:not-allowed;" in js
    assert "data-version-energy-apply" in js
    assert "confirm:true,backup_confirmed:true" in js


def test_ui_semantics_and_actions_execute_with_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for executable frontend contract checks")
    script = r'''
const fs=require("node:fs"),vm=require("node:vm");
const assert=require("node:assert/strict");
const code=fs.readFileSync(process.argv[1],"utf8");
const sandbox={HTMLElement:class {},customElements:{get:()=>false,define:()=>{}}};
vm.runInNewContext(code+
  "\nglobalThis.__test={Panel:TrybatecPanel,localize:localizeTrybatecText};",
  sandbox,{timeout:4000});
const {Panel,localize}=sandbox.__test;
const p=Panel.prototype;
const tr=(fr,en)=>fr;
const meter={physical_key:"a".repeat(24),status:"depose",source:"archived_verified_inventory",
  serial:"SYNTH-OLD",lot:"SYNTH-LOT",fluid:"CET",unit:"kWh",unit_verified:true,
  last_index:null,first_observed_at:null,last_source_observed_at:null,last_observed_at:null};
const account={entry_id:"SYNTH-ENTRY",meters:[meter],entities:[],meter_options:[{
  physical_key:meter.physical_key,selection_origin:"manual",source_unit:"kWh"}],
  tariffs:{},meter_tariffs:{},ledger:{pending:0,series:[]}};
const fixture={
  _current:account,_data:{energy:{sources:[]}},
  _t:tr,_number:x=>String(x),_date:x=>x||"",
  _meterName:()=> "Chauffage",_badge:()=>"<span>Déposé</span>",
  _meterField:p._meterField,_statusIndicator:p._statusIndicator,
  _auditDetails:()=>"",_meterHistoricalMetrics:()=>"",
  _meterOptionsEditor:()=>"",_tariffCoverage:new Map(),
  _meter:0,_meters:()=>[meter],_tab:"meters",
  shadowRoot:{querySelector:()=>({focus:()=>{},scrollIntoView:()=>{}})},
  _render:()=>{},_originMeter:null,_historyContextKey:null,
};
const detail=p._meterDetail.call(fixture,meter);
assert.match(detail,/Sans index courant/);
assert.match(detail,/status-indicator na/);
assert.match(detail,/data-meter-context="scan"/);
assert.match(detail,/data-meter-context="history"/);
assert.match(detail,/data-meter-context="unit"/);
assert.match(detail,/Origine : unité enregistrée manuellement/);
assert.match(detail,/status-indicator passed/);
assert.doesNotMatch(detail,/Anomalie détectée/);

let calls=0;
fixture._hass={callWS:()=>{calls++;throw Error("Unexpected supplier access");}};
p._openMeterContext.call(fixture,"scan");
assert.equal(calls,0);
assert.equal(fixture._tab,"meters");
p._openMeterContext.call(fixture,"history");
assert.equal(calls,0);
assert.equal(fixture._historyContextKey,meter.physical_key);
assert.equal(fixture._originMeter,meter.physical_key);
assert.equal(fixture._tab,"history");
p._openMeterContext.call(fixture,"unit");
assert.equal(calls,0);

const overview=p._readinessView.call(fixture,account);
assert.match(overview,/Non applicable/);
assert.match(overview,/Tarifs annuels \(facultatifs\)/);
assert.match(overview,/Parcours disponibles selon vos besoins/);
assert.doesNotMatch(overview,/readiness-row issue/);
assert.doesNotMatch(overview,/mdi:alert-circle-outline/);
account.meters.push({...meter,status:"en_service",unit_verified:false,
  physical_key:"b".repeat(24),serial:"SYNTH-NEW"});
account.meter_options.push({physical_key:"b".repeat(24),source_unit:"conflict"});
const conflict=p._readinessView.call(fixture,account);
assert.match(conflict,/Anomalie détectée/);
assert.match(conflict,/readiness-row issue/);

// Dates in a snapshot are not a passed exhaustive historical check.
account.meters.length=1;
account.meter_options.length=1;
meter.first_observed_at="2023-01-01";
meter.last_source_observed_at="2025-01-01";
const snapshotDates=p._readinessView.call(fixture,account);
assert.match(snapshotDates,/readiness-row pending/);
assert.doesNotMatch(snapshotDates,/Bornes vérifiées par une analyse historique complète/);
fixture._tariffCoverage.set(account.entry_id,{status:"complete",meters:[{
  physical_key:meter.physical_key,first_observed_at:meter.first_observed_at,
  last_source_observed_at:meter.last_source_observed_at
}]});
const scanned=p._readinessView.call(fixture,account);
assert.match(scanned,/Bornes vérifiées par une analyse historique complète/);

// Contextual summary must not leak aggregated rows for other physical meters.
fixture._historyContextKey=meter.physical_key;
fixture._historyPreview={start_date:"2023-01-01",end_date:"2025-01-01",
  history_summary:{meters:2,readings_to_review:1,
    by_fluid:{CET:{meters:2,gaps:5,conflicts:1}},
    by_meter:[
      {physical_key:meter.physical_key,fluid:"CET",lot:meter.lot,
        serial:meter.serial,first_observed_at:"2023-01-01",
        last_observed_at:"2025-01-01",gaps:1,decreases:0,conflicts:0},
      {physical_key:"z".repeat(24),fluid:"CET",lot:meter.lot,
        serial:"SYNTH-OTHER",first_observed_at:"2023-01-01",
        last_observed_at:"2025-01-01",gaps:4,decreases:2,conflicts:1}
    ]}};
const contextSummary=p._historySummary.call(fixture);
assert.match(contextSummary,/SYNTH-OLD/);
assert.doesNotMatch(contextSummary,/SYNTH-OTHER/);
assert.match(contextSummary,/Synthèse du compteur sélectionné/);
fixture._historyContextKey=null;
const allSummary=p._historySummary.call(fixture);
assert.match(allSummary,/SYNTH-OTHER/);

assert.equal(localize("Sans index courant","en-US"),"No current index");
assert.equal(localize("Consulter l’unité","en-US"),"View unit");
assert.equal(localize("Rechercher les relevés","en-US"),"Search readings");
assert.equal(localize("Non vérifié","en-US"),"Not verified");
console.log("UI state and contextual navigation: PASS");
'''
    run = subprocess.run(
        [node, "-e", script, str(PANEL)],
        text=True, capture_output=True, check=False, timeout=15,
    )
    assert run.returncode == 0, run.stderr
