"""Read-only Energy fallback UI tests; no live HA, Recorder or supplier access."""
from pathlib import Path
import shutil
import subprocess

import pytest

PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"


def test_energy_fallback_never_activates_energy_or_recorder():
    script = PANEL.read_text(encoding="utf-8")
    assert "function trybatecEnergySetupGuidance(account, energy)" in script
    assert "this._energySetupHelp()" in script
    assert 'data-tab="overview"' in script
    view = script.split("  _energySetupHelp() {", 1)[1].split("  _energy() {", 1)[0]
    assert "callWS(" not in view
    assert "callService(" not in view
    assert "activate_b15_energy" not in view
    assert "data-version-energy-apply" not in view
    assert "data-open-energy" in view


def test_energy_fallback_states_and_actionable_navigation_in_real_js():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable; mandatory JS CI must validate the panel")
    js = r'''
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync(process.argv[1],"utf8");
const context={
  HTMLElement:class {},
  customElements:{get:()=>false,define:()=>{}},
};
vm.runInNewContext(source+
  " ; globalThis.__energy={guide:trybatecEnergySetupGuidance,Panel:TrybatecPanel};",
  context,{timeout:3000});
const {guide,Panel}=context.__energy;
const meter={status:"en_service",unit_verified:true,last_index:16};
const account={meters:[meter],ledger:{series:[],pending:0},tariffs:{},meter_tariffs:{}};
const available={status:"available",sources:[]};
assert.equal(guide(account,available).mode,"not_implemented");
assert.equal(guide(account,available).reasons.length,0);
assert.equal(guide(account,available).optionalTariffsMissing,true);
assert.equal(guide(account,{status:"unconfigured",sources:[]}).mode,"configuration_incomplete");
assert.equal(guide(account,{status:"not_loaded",sources:[]}).mode,"technical_unavailable");
assert.equal(guide(account,{
  status:"available",sources:[{type:"water",statistic_id:"trybatec:synthetic"}],
}).mode,"coverage_unverified");
const incomplete={...account,meters:[{status:"en_service",unit_verified:false,last_index:null}],
  ledger:{series:[],pending:1}};
const missing=guide(incomplete,available);
assert.equal(missing.mode,"configuration_incomplete");
assert.deepEqual(Array.from(missing.reasons.map(r=>r.code)),
  ["meter_units","meter_indexes","recorder_pending"]);
assert.ok(missing.reasons.every(r=>r.level==="required"));
const retired={...account,meters:[meter,{status:"depose",serial:"old"}]};
assert.equal(guide(retired,available).mode,"verification_needed");
assert.equal(guide(retired,available).reasons[0].level,"unverified");
const otherFluid={...account,meters:[meter,{
  status:"depose",lot:"synthetic",fluid:"EF",serial:"retired"
}],ledger:{pending:0,series:[{
  scope:{kind:"consolidated",lot:"synthetic",fluid:"CET"},
  versions:[{state:"verified"}]
}]}};
assert.equal(guide(otherFluid,available).mode,"verification_needed");
const matchingFluid={...otherFluid,ledger:{pending:0,series:[{
  scope:{kind:"consolidated",lot:"synthetic",fluid:"EF"},
  versions:[{state:"verified"}]
}]}};
assert.equal(guide(matchingFluid,available).mode,"verification_needed");
assert.equal(guide(matchingFluid,available).reasons[0].level,"unverified");
const fixture={_current:incomplete,_data:{energy:available},_t:(fr,en)=>fr};
const html=Panel.prototype._energySetupHelp.call(fixture);
assert.ok(html.includes("Assistant de configuration / Vue d’ensemble"));
assert.match(html,/data-tab="overview"/);
assert.match(html,/data-tab="meters"/);
assert.match(html,/data-tab="tariffs"/);
assert.match(html,/data-open-energy/);
assert.match(html,/À faire/);
assert.match(html,/Tarifs annuels facultatifs/);
assert.match(html,/planificateur groupé fonctionne en lecture seule/);
assert.doesNotMatch(html,/data-bulk-energy-apply/);
const single={...account,meters:[{...meter,physical_key:"meter-one",unit_verified:false,last_index:null}]};
const focused=Panel.prototype._energySetupHelp.call({...fixture,_current:single});
assert.match(focused,/data-energy-meter="meter-one"/);
assert.match(focused,/data-energy-history="meter-one"/);
let routeRenders=0;
const route={_current:single,_meters:()=>single.meters,_meter:0,_tab:"energy",
  _query:"old",_render:()=>{routeRenders++;}};
Panel.prototype._click.call(route,{target:{closest:()=>({dataset:{energyMeter:"meter-one"}})}});
assert.equal(route._tab,"meters");
assert.equal(route._meter,0);
assert.equal(route._query,"");
Panel.prototype._click.call(route,{target:{closest:()=>({dataset:{energyHistory:"meter-one"}})}});
assert.equal(route._tab,"history");
assert.equal(route._historyContextKey,"meter-one");
assert.equal(route._originMeter,"meter-one");
assert.equal(routeRenders,2);
const unknown={...route,_tab:"energy",_query:"old"};
Panel.prototype._click.call(unknown,{target:{closest:()=>({dataset:{energyHistory:"missing-key"}})}});
assert.equal(unknown._tab,"meters");
assert.equal(unknown._historyContextKey,null);

const english=Panel.prototype._energySetupHelp.call({...fixture,_t:(fr,en)=>en});
assert.ok(english.includes("Setup assistant / Overview"));
assert.match(english,/Action required/);
assert.doesNotMatch(english,/Aucune source Trybatec/);
let renders=0;
const navigation={_tab:"energy",_query:"initial",_render:()=>{renders++;}};
Panel.prototype._click.call(navigation,{
  target:{closest:()=>({dataset:{tab:"overview"}})},
});
assert.equal(navigation._tab,"overview");
assert.equal(navigation._query,"");
assert.equal(renders,1);
'''
    result = subprocess.run(
        [node, "-e", js, str(PANEL)], capture_output=True, text=True,
        check=False, timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_pr90_regression_contract_survives_pr91_merge():
    script = PANEL.read_text(encoding="utf-8")
    # Verify the combined source still contains the existing physical-meter controls.
    for required in (
        "_statusIndicator(kind, value)",
        "_openMeterContext(action)",
        "trybatecMergeHistoricalObservationDates(account, coverage)",
        "data-history-context-clear",
        "data-meter-context=",
        "selection_origin",
        'this._historyContextKey=meter.physical_key',
        "this._energySetupHelp()",
        "data-energy-history",
    ):
        assert required in script
    guidance = script.split("function trybatecEnergySetupGuidance(", 1)[1].split(
        "/* Scoped annual tariffs", 1
    )[0]
    # Never treat the mere existence of a ledger version as continuity evidence.
    assert 'row.versions.some' not in guidance
    assert 'retired[0].physical_key' in guidance
