"""C5-C10 FR/EN UI regression checks for issue #155.

All fixtures are fictitious. Runs client-side JavaScript under Node only;
never connects to Home Assistant, Trybatec, Recorder or Energy.
"""
from pathlib import Path
import shutil
import subprocess

import pytest


PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"


def test_c5_c10_static_safety_contract():
    source = PANEL.read_text(encoding="utf-8")
    assert 'this._historyReason="undetermined"' in source
    assert '"manual_periodic","telemetry_failure","other"' in source
    assert 'data-history-reset-dates' in source
    assert 'data-history-today' in source
    assert "trybatecHistoricalBounds" in source
    assert "trybatecFluidTag" in source
    assert "this._historyDatesEdited" in source
    assert "Ancienne IHM de révision" not in source
    assert "Existing review interface" not in source
    assert "data-open-options>Options natives de secours" in source
    assert "data-history-approve" in source
    assert "this._historyReason===" in source
    assert "recorder_writes!==false" in source
    assert "energy_writes!==false" in source
    assert 'role="status"' in source
    assert 'data-meter-detail tabindex="-1"' in source
    assert "--trybatec-cet-fg:" in source
    assert ':host([data-trybatec-theme="dark"])' in source or (
        'data-trybatec-theme=\\"dark\\"' in source
    )


def test_c5_c10_behavior_with_fictitious_meters():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js needed for executable panel fixtures")
    script = r"""
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync(process.argv[1],"utf8");
const sandbox={HTMLElement:class {},customElements:{get:()=>false,define:()=>{}},
  window:{matchMedia:()=>({matches:true})}};
vm.runInNewContext(source+
  "\nglobalThis.__test={P:TrybatecPanel.prototype,bounds:trybatecHistoricalBounds,"+
  "fluid:trybatecFluidTag,localize:localizeTrybatecText,style:style};",
  sandbox,{timeout:4000});
const {P,bounds,fluid,localize,style}=sandbox.__test;
const meter=(key,serial,kind,fluidName,first,last,index)=>({
  physical_key:key.repeat(24),serial,lot:"SYNTH-LOT",status:kind,fluid:fluidName,
  unit:fluidName==="CET"?"kWh":"m³",unit_verified:true,
  first_observed_at:first,last_source_observed_at:last,last_index:index,
  last_observed_at:last,source:"synthetic"});
const cold=meter("a","SYNTH-EF","en_service","EF","2022-03-05","2026-10-02",19);
const hot=meter("b","SYNTH-ECS","en_service","ECS","2023-01-01","2025-07-09",8);
const retired=meter("c","SYNTH-CET","depose","CET",null,null,null);
retired.last_observed_at=null;
const account={entry_id:"SYNTH-ACCOUNT",data_loaded:true,
  meters:[cold,hot,retired],entities:[],meter_options:[],tariffs:{},meter_tariffs:{}};
const f={
  _current:account,_data:{energy:{sources:[]}},_meter:0,_query:"",
  _t:(fr,en)=>fr,_number:x=>String(x),_date:x=>x||"",
  _meterName: m=>m.fluid,_badge:()=>"<span>Retired</span>",
  _meters:()=>account.meters,
  _historyContextKey:null,_historyDatesEdited:{start:false,end:false},
  _historyStart:"",_historyEnd:"",_historyEndExtended:false,
  _tariffCoverage:new Map(),_historyBusy:false,
  _historyReason:"undetermined",_historyMode:"linear",
  _historySelected:"",_originMeter:null,_historyPreview:null,_historyMessage:"",
  _historyError:"",_historyJobStatus:null,_historyJobId:null,
  _heading:()=>"",_historySummary:()=>"",_readingReview:()=>"",_originView:()=>"",
  _historyDayBars:()=>"",_historyComparison:()=>"",
  _syncHistoryDates:P._syncHistoryDates,_historyDatesHelp:P._historyDatesHelp,
  _meterActionState:P._meterActionState,_meterField:P._meterField,
  _statusIndicator:P._statusIndicator,_auditDetails:()=>"",
  _meterHistoricalMetrics:()=>"",_meterOptionsEditor:()=>"",
  _render:()=>{},_confirm:()=>true,_finishFieldChange:()=>{},
  shadowRoot:{querySelector:()=>null},
};
// C9: account vs exact physical meter bounds and conservative coverage labels.
assert.equal(bounds(account,null,null).start,"2022-03-05");
assert.equal(bounds(account,null,null).end,"2026-10-02");
assert.equal(bounds(account,null,null).complete,false);
assert.equal(bounds(account,hot.physical_key,null).start,"2023-01-01");
assert.equal(bounds(account,hot.physical_key,null).end,"2025-07-09");
assert.equal(bounds(account,retired.physical_key,null).start,"");
P._syncHistoryDates.call(f);
assert.equal(f._historyStart,"2022-03-05");
assert.equal(f._historyEnd,"2026-10-02");
assert.match(P._historyDatesHelp.call(f),/couverture partielle ou non vérifiée/);
f._historyContextKey=hot.physical_key;
P._syncHistoryDates.call(f);
assert.equal(f._historyStart,"2023-01-01");
assert.equal(f._historyEnd,"2025-07-09");
// Editing dates in either History or Recorder locks out automatic overwrite.
P._change.call(f,{target:{dataset:{historyField:"end_date"},value:"2026-11-01"}});
f._historyContextKey=cold.physical_key;
P._syncHistoryDates.call(f);
assert.equal(f._historyStart,"2022-03-05");
assert.equal(f._historyEnd,"2026-11-01");
assert.match(P._historyDatesHelp.call(f),/Période personnalisée/);
assert.match(P._history.call(f),/data-history-today/);
assert.match(P._history.call(f),/data-history-reset-dates/);
f._historyDatesEdited={start:false,end:false};
f._historyContextKey=retired.physical_key;
P._syncHistoryDates.call(f);
assert.equal(f._historyStart,"");
assert.equal(f._historyEnd,"");
assert.match(P._history.call(f),/Borne inconnue/);
assert.match(P._history.call(f),/data-history-preview disabled/);
const full={status:"complete",meters:[
  {physical_key:cold.physical_key,first_observed_at:"2022-03-05",
    last_source_observed_at:"2026-10-02"},
  {physical_key:hot.physical_key,first_observed_at:"2023-01-01",
    last_source_observed_at:"2025-07-09"},
  {physical_key:retired.physical_key}]};
assert.equal(bounds(account,null,full).complete,true);
assert.equal(bounds(account,hot.physical_key,full).complete,true);
assert.equal(bounds(account,"z".repeat(24),full).complete,false);
// C5: only an eligible action may be flagged, unrelated unknown is not an error.
assert.match(P._meterRow.call(f,cold,0,"detail"),/Configuration complète/);
assert.match(P._meterRow.call(f,retired,2,"detail"),/Historique facultatif/);
cold.unit_verified=false;
account.meter_options.push({physical_key:cold.physical_key,source_unit:"m³",
  selected_unit:"unverified",allowed_units:["m³"]});
assert.match(P._meterRow.call(f,cold,0,"detail"),/Action possible/);
account.meter_options[0].source_unit="conflict";
assert.match(P._meterRow.call(f,cold,0,"detail"),/Vérification nécessaire/);
assert.doesNotMatch(P._meterRow.call(f,cold,0,"detail"),/Configuration complète/);
// C6: retired has no current index, but the historical raw reading remains unqualified.
retired.historical_last_index_raw=100;
assert.match(P._meterRow.call(f,retired,2,"detail"),/Index historique source à qualifier/);
f._meter=2;f._historyContextKey=null;
const detail=P._meterDetail.call(f,retired);
assert.match(detail,/aucun index courant n’est attendu/);
assert.match(detail,/status-indicator na/);
assert.match(detail,/Un état HA « unknown » seul/);
assert.doesNotMatch(detail,/Anomalie détectée/);
// C7/C8: a single panel path remains and each fluid retains its own marker.
for(const code of ["EF","ECS","CET"]){
  const html=fluid(code);
  assert.match(html,/fluid-token/);
  assert.match(html,new RegExp("fluid-"+code.toLowerCase()));
  assert.match(html,/ha-icon/);
}
assert.match(fluid("CET"),/Chauffage/);
f._historyContextKey=hot.physical_key;
const history=P._history.call(f);
assert.match(history,/fluid-ecs/);
assert.match(history,/mdi:water-thermometer/);
assert.doesNotMatch(history,/Ancienne IHM de révision/);
assert.match(history,/Pourquoi cet intervalle est-il espacé/);
assert.equal(localize("Origine indéterminée","en-US"),"Undetermined origin");
assert.match(style,/max-width:1050px/);
assert.match(style,/trybatec-cet-fg/);
// C10: undetermined cannot call the persistence endpoint or be relabeled manual.
const interval={interval_key:"SYNTH-INTERVAL",fluid:"ECS",lot:"SYNTH-LOT",status:
  "linear_available_after_explicit_confirmation",meter_serial:"SYNTH-ECS",
  start_date:"2024-01-01",end_date:"2024-04-01",choice:{mode:"none",reason:"other"}};
f._historySelected=interval.interval_key;
f._historyPreview={proposals:{intervals:[interval]}};
const selectedHistory=P._history.call(f);
assert.match(selectedHistory,/Origine indéterminée/);
assert.match(selectedHistory,/value="undetermined" selected/);
let calls=[];
f._hass={callWS:async payload=>{calls.push(payload);return {status:"saved"}}};
(async()=>{
  await P._approveHistory.call(f);
  assert.equal(calls.length,0);
  assert.match(f._historyError,/Sélectionnez un motif qualifié/);
  assert.equal(interval.choice.reason,"other");
  f._historyReason="telemetry_failure";
  await P._approveHistory.call(f);
  assert.equal(calls.length,1);
  assert.equal(calls[0].reason,"telemetry_failure");
  assert.equal(calls[0].type,"trybatec/panel_smoothing_choice");
  assert.equal(calls[0].entry_id,account.entry_id);
  assert.equal(interval.choice.reason,"telemetry_failure");
  assert.ok(!source.includes("Ancienne IHM de révision"));
  console.log("C5-C10 synthetic fixture PASS");
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(PANEL)],
        capture_output=True, text=True, check=False, timeout=25,
    )
    assert result.returncode == 0, result.stderr
