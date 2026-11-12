"""FR/EN: executable synthetic coverage for unknown vs unavailable Energy status.

No Home Assistant instance, vendor requests or mutating operations.
"""
from pathlib import Path
import shutil
import subprocess

import pytest

PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"


def test_energy_unknown_status_is_not_mistaken_for_missing_implementation():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for executable JS status tests")
    code = r'''
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync(process.argv[1],"utf8");
const context={HTMLElement:class{},customElements:{get:()=>false,define:()=>{}}};
vm.runInNewContext(source+";globalThis.__guide=trybatecEnergySetupGuidance;globalThis.__Panel=TrybatecPanel;",context,{timeout:3000});
const account={meters:[{status:"en_service",unit_verified:true,last_index:10,physical_key:"SYNTH-ONE"}],
  ledger:{pending:0,series:[]},tariffs:{},meter_tariffs:{}};
const guide=context.__guide;
assert.equal(guide(account,undefined).mode,"status_unknown");
assert.equal(guide(account,{}).mode,"status_unknown");
assert.equal(guide(account,{status:"unexpected",sources:[]}).mode,"status_unknown");
assert.equal(guide(account,{status:"not_loaded",sources:[]}).mode,"technical_unavailable");
assert.equal(guide(account,{status:"unconfigured",sources:[]}).mode,"configuration_incomplete");
assert.equal(guide(account,{status:"available",sources:[]}).mode,"not_implemented");
assert.equal(guide(account,{status:"available",sources:[{statistic_id:"trybatec:SYNTH"}]}).mode,"coverage_unverified");
// Optional rates must never create a missing-prerequisite anomaly.
assert.equal(guide(account,{status:"available",sources:[]}).optionalTariffsMissing,true);
const fixture={_current:account,_data:{energy:{}},_t:(fr,en)=>fr};
const html=context.__Panel.prototype._energySetupHelp.call(fixture);
assert.match(html,/État du module Énergie inconnu/);
assert.doesNotMatch(html,/data-bulk-energy-apply/);
assert.doesNotMatch(html,/call_service/);
'''
    result = subprocess.run(
        [node, "-e", code, str(PANEL)],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_guidance_is_read_only():
    source = PANEL.read_text(encoding="utf-8")
    guidance = source.split("function trybatecEnergySetupGuidance(", 1)[1].split(
        "/* Scoped annual tariffs:", 1
    )[0]
    assert "callWS(" not in guidance
    assert "callService(" not in guidance
    assert "data-bulk-energy-apply" not in guidance
    assert '"status_unknown"' in guidance
