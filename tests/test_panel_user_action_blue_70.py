"""Blue required-user-action semantics; synthetic UI regressions for #70/#83/#155.

No supplier credentials, Home Assistant connection, Recorder or Energy writes.
FR/EN checks run against fictitious physical-meter identities only.
"""
from pathlib import Path
import shutil
import subprocess

import pytest


PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))


def _contrast(first: str, second: str) -> float:
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_required_action_has_separate_tokens_and_readable_pairs():
    src = PANEL.read_text(encoding="utf-8")
    for token in (
        "--trybatec-user-action-base:#3478D4",
        "--trybatec-user-action-fg:#2355A6",
        "--trybatec-user-action-bg:#EAF2FF",
        "--trybatec-user-action-fg:#A9C8FF",
        "--trybatec-user-action-bg:#172B49",
        "mdi:arrow-right-circle-outline",
        "readiness-row.user-action-needed>ha-icon",
        "status-indicator.required",
        "energy-action-needed",
    ):
        assert token in src, token
    assert _contrast("#2355A6", "#EAF2FF") >= 4.5
    assert _contrast("#A9C8FF", "#172B49") >= 4.5
    assert _contrast("#2355A6", "#FFFFFF") >= 4.5
    # These are semantic action colors, not fluid identity / brand colors.
    assert "#3478D4" != "#0A84D8"
    assert "#3478D4" != "#4E9E4A"


def test_required_action_is_not_relabelled_as_anomaly():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for executable, synthetic panel regression")
    js = r"""
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const code=fs.readFileSync(process.argv[1],"utf8");
const sandbox={HTMLElement:class {},customElements:{get:()=>false,define:()=>{}},
    window:{matchMedia:()=>({matches:true})}};
vm.runInNewContext(code+
  "\nglobalThis.__ui={p:TrybatecPanel.prototype,style:style};",
  sandbox,{timeout:4000});
const {p,style}=sandbox.__ui;
const current={physical_key:"a".repeat(24),status:"en_service",
  fluid:"EF",serial:"SYNTH-CURRENT",lot:"SYNTH-LOT",unit:"m³",
  unit_verified:false,last_index:10,
  first_observed_at:"2025-01-01",last_source_observed_at:"2026-01-01"};
const retired={physical_key:"b".repeat(24),status:"depose",
  fluid:"CET",serial:"SYNTH-RETIRED",lot:"SYNTH-LOT",unit:"kWh",
  unit_verified:true,last_index:null,
  first_observed_at:null,last_source_observed_at:null};
const account={entry_id:"SYNTH-ACCOUNT",data_loaded:true,meters:[current,retired],
  entities:[],ledger:{pending:0,series:[]},tariffs:{},meter_tariffs:{},
  meter_options:[{physical_key:current.physical_key,source_unit:"m³",allowed_units:["m³"]}]};
const f={_current:account,_data:{energy:{status:"available",sources:[]}},
  _t:(fr,en)=>fr,_meter:0,_meters:()=>account.meters,
  _meterName:m=>m.fluid,_tariffCoverage:new Map(),
  _meterActionState:p._meterActionState};
assert.equal(p._meterActionState.call(f,current).kind,"required");
const activeRow=p._meterRow.call(f,current,0,"detail");
assert.match(activeRow,/status-indicator required/);
assert.match(activeRow,/mdi:arrow-right-circle-outline/);
assert.doesNotMatch(activeRow,/status-indicator issue/);
let overview=p._readinessView.call(f,account);
assert.match(overview,/Historique des compteurs déposés/);
assert.match(overview,/Action pour qualifier l’historique/);
assert.match(overview,/readiness-row pending user-action-needed/);
assert.match(overview,/Non vérifié/);
assert.doesNotMatch(overview,/Anomalie détectée/);
assert.match(style,/readiness-row.user-action-needed>ha-icon/);
assert.match(style,/--trybatec-user-action-fg:#A9C8FF/);
assert.match(style,/--trybatec-user-action-fg:#2355A6/);
// Retired does not require current index; raw unqualified history is actionable.
assert.equal(p._meterActionState.call(f,retired).kind,"known");
retired.historical_last_index_raw=40;
assert.equal(p._meterActionState.call(f,retired).kind,"required");
// A source-unit conflict is NOT presented as a normal blue action.
account.meter_options[0].source_unit="conflict";
assert.notEqual(p._meterActionState.call(f,current).kind,"required");
const conflicted=p._readinessView.call(f,account);
assert.match(conflicted,/Anomalie détectée/);
assert.match(conflicted,/readiness-row issue/);
// Without a loaded inventory, no required action is inferred.
account.data_loaded=false;
overview=p._readinessView.call(f,account);
assert.doesNotMatch(overview,/user-action-needed/);
assert.match(overview,/Inventaire non chargé/);
account.data_loaded=true;
// Verified complete retrospective coverage removes the blue action from the retired row.
current.unit_verified=true;
account.meter_options[0].source_unit="m³";
retired.first_observed_at="2022-01-01";
retired.last_source_observed_at="2024-01-01";
f._tariffCoverage.set(account.entry_id,{status:"complete",meters:[{
 physical_key:retired.physical_key,first_observed_at:retired.first_observed_at,
 last_source_observed_at:retired.last_source_observed_at}]});
overview=p._readinessView.call(f,account);
assert.doesNotMatch(overview,/user-action-needed/);
assert.match(overview,/Conforme/);
// Separate guidance differentiates required operations from unverified history.
current.unit_verified=false; // eligible and explicitly required Energy setup action
const guidance=p._energySetupHelp.call(f);
assert.match(guidance,/energy-action-needed/);
assert.match(guidance,/mdi:arrow-right-circle-outline/);
assert.match(guidance,/mdi:help-circle-outline/);
f._t=(fr,en)=>en;
f._tariffCoverage.clear();
overview=p._readinessView.call(f,account);
assert.match(overview,/Action to qualify history/);
console.log("User-action blue / status separation: PASS");
"""
    result = subprocess.run(
        [node, "-e", js, str(PANEL)],
        capture_output=True, text=True, check=False, timeout=25,
    )
    assert result.returncode == 0, result.stderr
