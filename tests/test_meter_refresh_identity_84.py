"""Synthetic #84 tests: preserve exact physical meter and account after refresh.

No Home Assistant, vendor or network access; fake snapshots only.
"""
from pathlib import Path
import shutil
import subprocess

import pytest

PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"


def test_refresh_preserves_exact_physical_selection_and_fails_closed():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for executable UI behavior")
    script = r'''
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync(process.argv[1],"utf8");
const sandbox={HTMLElement:class{},customElements:{get:()=>false,define:()=>{}}};
vm.runInNewContext(source+";globalThis.__Panel=TrybatecPanel;",sandbox,{timeout:3000});
const Panel=sandbox.__Panel;
const meter=key=>({physical_key:key,serial:"SYNTH-"+key,fluid:"EF",status:"en_service"});
const account=(id,keys)=>({entry_id:id,meters:keys.map(meter)});
async function run(previous,next,accountIndex,meterIndex){
  const p=Object.create(Panel.prototype);
  p._data={accounts:previous};p._account=accountIndex;p._meter=meterIndex;
  p._tab="meters";p._loading=false;p._started=false;
  p._render=()=>{};p._loadTariffYearCoverage=()=>{};
  let calls=0;
  p._hass={callWS:async request=>{
    assert.equal(request.type,"trybatec/panel_snapshot");calls++;
    return {accounts:next};
  }};
  await p._fetch();
  assert.equal(calls,1);
  assert.equal(p._loading,false);
  assert.equal(p._error,"");
  return p;
}
(async()=>{
  const original=[account("SYNTH-A",["A","B","C"]),account("SYNTH-B",["D"])];
  const reversed=[account("SYNTH-B",["D"]),account("SYNTH-A",["C","A","B"])];
  const reordered=await run(original,reversed,0,1);
  assert.equal(reordered._current.entry_id,"SYNTH-A");
  assert.equal(reordered._current.meters[reordered._meter].physical_key,"B");
  assert.equal(reordered._account,1);
  const removed=await run(original,[account("SYNTH-A",["A","C"])],0,1);
  assert.equal(removed._current.entry_id,"SYNTH-A");
  assert.equal(removed._meter,-1,"Missing meter cannot select a neighbor");
  const lostAccount=await run(original,[account("SYNTH-B",["B","D"])],0,1);
  assert.equal(lostAccount._current.entry_id,"SYNTH-B");
  assert.equal(lostAccount._meter,-1,
    "Do not show a matching physical key belonging to a different account");
  const initial=await run([], [account("SYNTH-A",["A"])],0,0);
  assert.equal(initial._account,0);
  assert.equal(initial._meter,0);
  const stale=await run([account("SYNTH-A",["A"])],
    [account("SYNTH-A",["A"])],0,-1);
  assert.equal(stale._meter,-1,"Cleared selection stays cleared");
  const ambiguous=await run(original,[account("SYNTH-A",["B","B"])],0,1);
  assert.equal(ambiguous._meter,-1,
    "Duplicate physical keys must not select a random device");
  const keyless=await run(
    [{entry_id:"SYNTH-A",meters:[{serial:"SYNTH-LEGACY"}]}],
    [account("SYNTH-A",["A","B"])],0,0);
  assert.equal(keyless._meter,-1,
    "A previously selected meter without a physical key is unresolvable");
  console.log("Exact-meter refresh and safe fallback: PASS");
})().catch(err=>{console.error(err);process.exitCode=1;});
'''
    result = subprocess.run(
        [node, "-e", script, str(PANEL)],
        capture_output=True, text=True, check=False, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
