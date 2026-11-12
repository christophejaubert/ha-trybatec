"""Issue #42: executable tariff-panel regression tests without a live HA instance.

All keys, prices, fluids and years are synthetic. Node runs the distributed panel
helpers, not a reimplementation of the same functions.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"

_NODE = r'''
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync(process.argv[1],"utf8");
const context={HTMLElement:class{},customElements:{get:()=>true}};
vm.runInNewContext(source+"\nglobalThis.__tariffs42={Panel:TrybatecPanel,resolve:trybatecSavedEffectiveTariff,translate:localizeTrybatecText,years:trybatecTariffYears};",context,{timeout:5000});
const {Panel,resolve,translate,years}=context.__tariffs42;
const p=Panel.prototype;
const key="a".repeat(24), other="b".repeat(24);
const account={
  entry_id:"fake-entry",title:"Synthetic apartment",
  meters:[
    {physical_key:key,fluid:"EF",lot:"FAKE",serial:"M1",status:"en_service",first_observed_at:"2022-01-01",last_source_observed_at:"2026-01-01"},
    {physical_key:other,fluid:"ECS",lot:"FAKE",serial:"M2",status:"depose",first_observed_at:"2020-01-01",last_source_observed_at:"2023-01-01"}
  ],
  tariffs:{"2024":{"EF":{rate:1.2345,status:"approved"}}},
  meter_tariffs:{"2024":{[key]:{rate:2.5,status:"provisional"}}},
  tariff_fingerprint:"f".repeat(64)
};
function fixture(language="fr-FR") {
  return {
    _current:account,_data:{accounts:[account]},
    _tab:"tariffs",
    _tariffInput:{year:2024,fluid:"EF",physical_key:"",rate:"1.2345",status:"approved"},
    _tariffBusy:false,_tariffError:"",_tariffMessage:"",
    _tariffCoverage:new Map(),_tariffJobStatus:null,_tariffJobId:null,
    _error:"",_message:"",_unsavedInput:false,
    _heading:()=>"",_annualCostsView:()=>"",_number:n=>String(n),
    _t:(fr,en)=>language.startsWith("en")?en:fr,
    _locale:()=>language,
    _existingTariff:p._existingTariff,
    _render:()=>{},
    shadowRoot:{querySelector:()=>({focus:()=>{}})},
    _confirm:()=>true,
  };
}
assert.equal(resolve(account,2024,"EF",key).rate,2.5);
assert.equal(resolve(account,2024,"EF",key).origin,"meter_override");
assert.equal(resolve(account,2024,"EF").rate,1.2345);
assert.equal(resolve(account,2024,"EF").origin,"fluid_default");
assert.equal(resolve(account,2024,"EF",other).rate,1.2345);
assert.equal(resolve(account,2025,"EF",key),null,"no cross-year fallback");
assert.equal(resolve(account,2024,"CET",key),null,"no cross-fluid fallback");
assert.equal(resolve(account,2024,"EF").source_year,2024);
const suggestions=years(account,2026).years;
assert.ok(suggestions.includes(2024));
assert.ok(!suggestions.includes(2040),"future exercise must be selectable even without historical evidence");

const fr=fixture(),en=fixture("en-US");
fr._tariffInput.year=2040;
const rendered=p._tariffs.call(fr);
assert.match(rendered,/type="number" min="2000" max="2100"/);
assert.match(rendered,/list="tariff-year-options" value="2040"/);
assert.match(rendered,/data-tariff-reset/);
assert.match(rendered,/data-tariff-edit-year="2024"/);
assert.match(rendered,/data-tariff-edit-meter="/);
assert.match(rendered,/Annuler la saisie/);
assert.match(rendered,/Aucun tarif enregistré pour cet exercice/);
assert.doesNotMatch(rendered,/type="text"[^>]*annual_tariffs/);
fr._tariffInput.year=2024;
fr._tariffInput.physical_key=key;
assert.match(p._tariffs.call(fr),/Tarif effectif enregistré: 2.5 EUR\/m³/);
assert.match(p._tariffs.call(fr),/Spécifique au compteur/);
assert.match(p._tariffs.call(en),/Saved effective rate: 1.2345 EUR\/m³/);
assert.match(p._tariffs.call(en),/Default fluid rate/);
assert.equal(translate("Annuler la saisie","en-US"),"Discard edits");
assert.equal(translate("Exercice invalide : choisissez une année entre 2000 et 2100.","en-US"),"Invalid year: choose a year between 2000 and 2100.");

const clickFixture=fixture();
clickFixture._tariffInput.rate="9";
p._click.call(clickFixture,{target:{closest:()=>({dataset:{tariffReset:""}})}});
assert.equal(clickFixture._tariffInput.rate,"1.2345","cancel restores saved amount");
assert.equal(clickFixture._tariffInput.status,"approved");
assert.equal(clickFixture._unsavedInput,false);
p._click.call(clickFixture,{target:{closest:()=>({dataset:{
  tariffEditYear:"2024",tariffEditFluid:"EF",tariffEditMeter:key
}})}});
assert.equal(clickFixture._tariffInput.rate,"2.5");
assert.equal(clickFixture._tariffInput.status,"provisional");
assert.equal(clickFixture._tariffInput.physical_key,key);

async function run(){
  const bad=["","-1","NaN","Infinity","0.0000001","1.2345678","1000001","1e-2","abc"];
  for(const amount of bad){
    const f=fixture();
    f._tariffInput.rate=amount;
    let calls=0;
    f._hass={callWS:async()=>{calls++;return {status:"saved"};}};
    await p._sendTariff.call(f,false);
    assert.equal(calls,0,"invalid amount: "+amount);
    assert.ok(f._tariffError,"visible error: "+amount);
    assert.equal(f._error,"","tariff errors must not replace entire panel");
  }
  for(const year of [1999,2101,2024.5]){
    const f=fixture();f._tariffInput.year=year;
    let calls=0;
    f._hass={callWS:async()=>{calls++;return {status:"saved"};}};
    await p._sendTariff.call(f,false);
    assert.equal(calls,0);
    assert.match(f._tariffError,/Exercice invalide/);
  }
  const f=fixture();
  f._tariffInput.year=2040;
  f._tariffInput.rate="1.234567";
  const sent=[];
  f._hass={callWS:async(req)=>{
    sent.push(req);
    return req.type==="trybatec/panel_tariff_change"?{status:"saved"}:{accounts:[account]};
  }};
  await p._sendTariff.call(f,false);
  assert.equal(sent.length,2);
  assert.equal(sent[0].year,2040);
  assert.equal(sent[0].rate,1.234567);
  assert.equal(sent[0].confirmed,true);
  assert.equal(sent[0].expected_fingerprint,"f".repeat(64));
  assert.equal(f._tariffError,"");
  assert.equal(f._unsavedInput,false);
  const g=fixture();
  g._hass={callWS:async(req)=>{
    if(req.type==="trybatec/panel_tariff_change")return {status:"saved"};
    throw new Error("network");
  }};
  await p._sendTariff.call(g,false);
  assert.match(g._tariffMessage,/Tarif enregistré, mais actualisation impossible/);
  assert.equal(g._tariffError,"","no false claim of save rejection");
}
run().then(()=>process.stdout.write("tariff UI #42 OK\n")).catch(e=>{
  console.error(e);process.exitCode=1;
});
'''


def test_tariff_editor_years_scopes_validation_and_fr_en() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable; dedicated frontend CI must execute this test")
    outcome = subprocess.run(
        [node, "-e", _NODE, str(PANEL)],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert outcome.returncode == 0, outcome.stdout + outcome.stderr
    assert "tariff UI #42 OK" in outcome.stdout


def test_tariff_editor_does_not_change_other_owners_files() -> None:
    text = PANEL.read_text(encoding="utf-8")
    assert 'type:"trybatec/panel_tariff_change"' in text
    assert 'expected_fingerprint:this._current.tariff_fingerprint' in text
    assert 'type:"trybatec/panel_snapshot"' in text
    assert 'data-tariff-edit-year' in text
    assert 'data-tariff-reset' in text
