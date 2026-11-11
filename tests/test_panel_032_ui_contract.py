"""Synthetic tests for the 0.3.2b1 panel changes, with no live HA or vendor access."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "custom_components/trybatec/panel/trybatec-panel.js"
COVERAGE = ROOT / "custom_components/trybatec/panel_tariff_years.py"


def test_original_history_and_energy_safety_controls_are_preserved():
    js = PANEL.read_text(encoding="utf-8")
    assert 'include_heating:true};' in js
    assert 'data-version-field="heating"' not in js
    assert 'confirm:true,backup_confirmed:true' in js
    assert 'plan_fingerprint:plan.plan_fingerprint' in js
    assert 'before_fingerprint:p.before_fingerprint' in js
    assert 'canReplaceVersion=hasVerifiedVersion && hasCurrentSource' in js
    assert 'disabled aria-disabled="true"' in js
    assert 'pour une première activation' in js
    assert 'prerequisite-locked' in js
    assert 'data-toggle-menu' in js
    assert '"hass-toggle-menu",{bubbles:true,composed:true}' in js
    assert 'data-nav-next' in js
    assert 'data-historical-scan' in js
    assert 'this._readinessView(a)' in js


def test_display_only_archived_index_is_not_written_to_source_or_recorder():
    js = PANEL.read_text(encoding="utf-8")
    py = COVERAGE.read_text(encoding="utf-8")
    assert 'historical_last_index_raw' in js
    assert 'last_source_index_raw' in py
    assert 'source": "verified_supplier_history"' in py
    assert '"recorder_writes": False' in py
    assert '"energy_writes": False' in py
    assert 'new["historical_last_index_raw"]' in py


def test_formatters_and_duration_validation_are_executed_with_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not available; frontend CI must run the JS checks")
    script = r'''
const fs=require("node:fs"),vm=require("node:vm");
const assert=require("node:assert/strict");
const js=fs.readFileSync(process.argv[1],"utf8");
const ctx={HTMLElement:class {},customElements:{get:()=>false,define:()=>{}}};
vm.runInNewContext(js+
  "\n globalThis.__check={format:trybatecDisplayNumber,date:trybatecDisplayDate,parts:trybatecDurationParts,minutes:trybatecDurationMinutes,Panel:TrybatecPanel};",
  ctx,{timeout:2000});
const {format,date,parts,minutes}=ctx.__check;
assert.equal(format("1234567.8900","fr-FR"),"1\u202f234\u202f567,8900");
assert.equal(format("1234567.8900","en-US"),"1,234,567.8900");
assert.equal(format("90.958","fr-FR"),"90,958");
assert.equal(date("2026-01-30T00:00:00+01:00","fr-FR","Europe/Paris"),"vendredi 30 janvier 2026");
assert.equal(date("2026-01-30T14:25:00+01:00","fr-FR","Europe/Paris",true),"vendredi 30 janvier 2026 à 14:25");
assert.equal(date("2026-01-30T00:00:00+01:00","fr-FR","Europe/Paris",true),"vendredi 30 janvier 2026");
assert.equal(date("2026-01-30","en-US","America/New_York"),"Friday, January 30, 2026");
assert.equal(minutes(parts(720)),720);
assert.equal(minutes({days:"0",hours:"1",minutes:"0"}),60);
assert.equal(minutes({days:"7",hours:"0",minutes:"0"}),10080);
assert.equal(minutes({days:"0",hours:"0",minutes:"59"}),NaN);
assert.equal(minutes({days:"0",hours:"1",minutes:"60"}),NaN);
assert.equal(minutes({days:"8",hours:"0",minutes:"0"}),NaN);
function versionPanel(hasNew,hasOld) {
  const fixture={
    _current:{ledger:{status:"no_import",pending:0,series:hasNew?
      [{logical_id:"synthetic",versions:[{state:"verified",number:1,statistic_id:"trybatec:synthetic_new"}]}]:[]}},
    _data:{energy:{sources:hasOld?[{type:"water",statistic_id:"trybatec:synthetic_old"}]:[]}},
    _t:(fr,en)=>fr,_date:x=>x,_historyStart:"2025-01-01",_historyEnd:"2025-12-31",
    _versionBusy:false,_versionImportBackup:false,_versionRevision:false,
    _versionRetry:false,_versionVerify:null,_versionEnergyPlan:null,
    _versionEnergyBackup:false,_versionRollback:false
  };
  return ctx.__check.Panel.prototype._recorderVersionWorkflow.call(fixture);
}
const noPreconditions=versionPanel(false,false);
assert.match(noPreconditions,/disabled aria-disabled="true"/);
assert.match(noPreconditions,/Parcours indisponible/);
assert.match(noPreconditions,/data-openEnergy/);
const ready=versionPanel(true,true);
assert.doesNotMatch(ready,/disabled aria-disabled="true"/);
assert.match(ready,/trybatec:synthetic_new/);
assert.match(ready,/trybatec:synthetic_old/);
'''
    outcome = subprocess.run(
        [node, "-e", script, str(PANEL)],
        capture_output=True, text=True, check=False, timeout=20,
    )
    assert outcome.returncode == 0, outcome.stderr
