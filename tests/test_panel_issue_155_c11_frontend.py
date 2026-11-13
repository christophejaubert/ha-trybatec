"""FR/EN: executable read-only C11 frontend handoff regressions for #155.

Uses the documented PR #162 WebSocket fields with fictitious account and meter
identifiers. Neither vendor APIs, live HA, Recorder nor Energy are contacted.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"


def test_c11_real_command_and_contract_are_wired():
    source = PANEL.read_text(encoding="utf-8")
    for term in (
        "trybatec/panel_history_discovery_status",
        "trybatec/panel_history_job_status",
        "trybatec/panel_history_job_cancel",
        'kind:"tariff_year_coverage"',
        "discovery_status",
        "completeness",
        "account_full",
        "bounded_period_only",
        "suggested_years_basis",
        "periods_verified",
        "failure_category",
        "cache_invalidation_reason",
        "retry_mode",
        "restart_from_zero",
        "no_atomic_window_checkpoints",
        "_historyDateDrafts",
    ):
        assert term in source
    # Only the legacy explicit user action may launch the costly global scan.
    assert "if (!force || !this._current || !this._hass) return;" in source
    assert "async _readHistoryDiscovery(" in source
    assert "async _loadTariffYearCoverage(force=false)" in source
    assert "manual_periodic" in source
    assert 'this._historyReason="undetermined"' in source


def test_c11_mocked_backend_payloads_and_ui_paths_run_under_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for executable mocked C11 contract checks")
    script = r"""
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync(process.argv[1],"utf8");
const sandbox={HTMLElement:class{},customElements:{get:()=>false,define:()=>{}},
  window:{setTimeout:cb=>cb()}};
vm.runInNewContext(source+"\nglobalThis.__c11={Panel:TrybatecPanel.prototype,"+
  "view:trybatecC11Presentation,bounds:trybatecHistoricalBounds,fluid:trybatecFluidTag};",
  sandbox,{timeout:4000});
const {Panel:P,view,bounds,fluid}=sandbox.__c11;
const key1="a".repeat(24),key2="b".repeat(24),other="c".repeat(24);
const meters=[
  {physical_key:key1,fluid:"EF",lot:"SYNTH-A",serial:"SYNTH-COLD",
    status:"en_service",unit:"m³",unit_verified:true,
    first_observed_at:"2022-01-02",last_source_observed_at:"2026-10-05",last_index:100},
  {physical_key:key2,fluid:"CET",lot:"SYNTH-A",serial:"SYNTH-HEAT",
    status:"depose",unit:"kWh",unit_verified:true,
    first_observed_at:null,last_source_observed_at:null,last_index:null},
];
const account={entry_id:"SYNTH-C11-A",data_loaded:true,meters,
  entities:[],tariffs:{"2022":{EF:{rate:3.25,status:"approved"}}},
  meter_tariffs:{},ledger:{pending:0,series:[]}};
const fullCoverage={
  status:"complete",completeness:"account_full",
  coverage_start:"2000-01-01",coverage_end:"2026-11-13",
  first_observed_at:"2021-12-21T12:00:00+01:00",
  last_observed_at:"2026-11-01T10:00:00+01:00",
  meters:[
    {physical_key:key1,first_observed_at:"2021-12-21T12:00:00+01:00",
      last_observed_at:"2026-11-01T10:00:00+01:00",
      covered_start:"2000-01-01",covered_end:"2026-11-13",
      provenance:"verified_supplier_observation"},
    {physical_key:key2,first_observed_at:"2023-02-01T10:00:00+01:00",
      last_observed_at:"2024-04-01T11:00:00+02:00",
      provenance:"verified_supplier_observation"},
  ],
  suggested_years:[2021,2022,2023,2024,2025,2026],
  suggested_years_basis:"observed_first_last_range_not_yearly_proof",
  cache_reused:true,periods_verified:34,api_requests:0,
  cache_expires_at:"2026-11-13T15:00:00Z",verified_at:"2026-11-13T14:00:00Z",
  cache_invalidation_reason:null,retry_mode:"restart_from_zero",
  retry_reason:"no_atomic_window_checkpoints",
  provenance:"verified_supplier_history"
};
const base={
  id:null,kind:null,status:"complete",discovery_status:"complete",
  coverage:fullCoverage,progress:null,periods_verified:34,api_requests:0,
  cache_reused:true,failure_category:null,retry_mode:"restart_from_zero",
  retry_reason:"no_atomic_window_checkpoints",
  recorder_writes:false,energy_writes:false
};
const complete=view(base);
assert.equal(complete.discovery_status,"complete");
assert.equal(complete.coverage.completeness,"account_full");
assert.equal(complete.coverage.suggested_years.length,6);
assert.equal(complete.cache_reused,true);
// A successful *bounded job* is not complete account discovery.
const partialCoverage={...fullCoverage,status:"incomplete",
  completeness:"bounded_period_only",coverage_start:"2023-01-01",
  coverage_end:"2023-12-31",suggested_years:[2023]};
const partial=view({...base,status:"complete",discovery_status:"incomplete",
  coverage:partialCoverage,cache_reused:false});
assert.equal(partial.discovery_status,"incomplete");
assert.equal(partial.coverage.completeness,"bounded_period_only");
assert.equal(view({...base,coverage:partialCoverage,
  discovery_status:"complete"}).discovery_status,"unverified");
// Failed/cancelled windows are not resumable and must not leak raw errors.
const failed=view({...base,status:"failed",discovery_status:"error",coverage:null,
  failure_category:"network",failure_type:"Authorization: private-body"});
assert.equal(failed.discovery_status,"error");
assert.equal(failed.failure_category,"network");
assert.equal(JSON.stringify(failed).includes("private-body"),false);
const interrupted=view({...base,status:"cancelled",
  discovery_status:"interrupted",failure_category:"cancelled",coverage:null});
assert.equal(interrupted.discovery_status,"interrupted");
const running=view({...base,id:"a".repeat(24),kind:"tariff_year_coverage",
  status:"running",discovery_status:"running",coverage:null,
  progress:{http_requests:12,periods_verified:7},cache_reused:false});
assert.equal(running.progress.http_requests,12);
assert.equal(running.progress.periods_verified,7);
assert.equal(view({...base,recorder_writes:true}).discovery_status,"unverified");
assert.equal(view({...base,discovery_status:"not_started",coverage:{
  ...fullCoverage,status:"not_started",completeness:"unknown",
  cache_invalidation_reason:"cache_expired"
}}).coverage.cache_invalidation_reason,"cache_expired");
// C9: full discovery uses *backend* observation dates for physical-meter matches.
assert.equal(bounds(account,null,complete.coverage).start,"2021-12-21");
assert.equal(bounds(account,null,complete.coverage).end,"2026-11-01");
assert.equal(bounds(account,key2,complete.coverage).start,"2023-02-01");
assert.equal(bounds(account,key2,complete.coverage).end,"2024-04-01");
assert.equal(bounds(account,other,complete.coverage).start,"");
assert.equal(bounds(account,key1,partial.coverage).complete,false);
assert.equal(bounds(account,key1,partial.coverage).basis,"bounded_period_only");
// Source timestamps can cross a Europe/Paris day boundary.
const dayCoverage={...fullCoverage,first_observed_at:"2025-03-01T23:30:00Z"};
assert.equal(bounds(account,null,dayCoverage).start,"2025-03-02");
// C8 remains readable to screen readers: adjacent fluid text, decorative icon.
assert.match(fluid("EF"),/Eau froide/);
assert.match(fluid("EF"),/aria-hidden="true"/);
assert.match(fluid("CET"),/Chauffage/);
const fake={
  _current:account,_data:{accounts:[account],energy:{sources:[]}},
  _historyDiscovery:new Map(),_historyDiscoveryInflight:new Set(),
  _historyDiscoveryWatch:new Set(),_historyDateDrafts:new Map(),
  _historyDateEntryId:null,_historyDateScope:null,
  _historyDatesEdited:{start:false,end:false},_historyEndExtended:false,
  _historyContextKey:null,_historyStart:"",_historyEnd:"",
  _historyBusy:false,_tariffBusy:false,_costBusy:false,_tariffHydrated:true,
  _tariffCoverage:new Map(),_tariffInput:{year:2022,fluid:"EF",
    physical_key:"",rate:"3.25",status:"approved"},
  _t:(fr,en)=>fr,_date:x=>x||"",_number:x=>String(x),
  _historyDiscoveryView:P._historyDiscoveryView,
  _historyDatesHelp:P._historyDatesHelp,
  _syncHistoryDates:P._syncHistoryDates,
  _isEditingForm:()=>false,_render:()=>{},
  _heading:()=>"",_annualCostsView:()=>"",_tariffEffectiveText:()=>"3.25 EUR/m³",
  _existingTariff:()=>account.tariffs["2022"].EF,
};
let calls=[],attached=0;
fake._watchHistoryDiscovery=()=>{attached++};
fake._hass={user:{is_admin:true},callWS:async req=>{
  calls.push(req);
  assert.equal(req.type,"trybatec/panel_history_discovery_status");
  assert.equal(req.entry_id,account.entry_id);
  return base;
}};
(async()=>{
  await P._readHistoryDiscovery.call(fake);
  assert.equal(calls.length,1);
  assert.equal(calls[0].type,"trybatec/panel_history_discovery_status");
  assert.equal(attached,0);
  assert.equal(fake._historyDiscovery.get(account.entry_id).discovery_status,"complete");
  const notice=P._historyDiscoveryView.call(fake,"history");
  assert.match(notice,/Découverte historique : Complète/);
  assert.match(notice,/Période source vérifiée/);
  assert.match(notice,/Résultats déjà vérifiés réutilisés/);
  assert.match(notice,/data-discovery-refresh/);
  P._syncHistoryDates.call(fake);
  assert.equal(fake._historyStart,"2021-12-21");
  assert.equal(fake._historyEnd,"2026-11-01");
  // Per-account custom input never bleeds to a different account.
  fake._historyDatesEdited.end=true;
  fake._historyEnd="2026-11-13";
  const second={...account,entry_id:"SYNTH-C11-B",
    meters:[{...meters[0],first_observed_at:"2024-01-01",
      last_source_observed_at:"2024-12-01"}],tariffs:{}};
  fake._data.accounts.push(second);
  fake._current=second;
  P._syncHistoryDates.call(fake);
  assert.equal(fake._historyEnd,"2024-12-01");
  fake._current=account;
  P._syncHistoryDates.call(fake);
  assert.equal(fake._historyEnd,"2026-11-13");
  assert.match(P._historyDatesHelp.call(fake),/Période personnalisée/);
  // Real C11 failure: tariff form + saved year must stay editable.
  fake._historyDiscovery.set(account.entry_id,failed);
  fake._tariffHydrated=true;
  const tariff=P._tariffs.call(fake);
  assert.match(tariff,/data-tariff-form/);
  assert.match(tariff,/data-tariff-field="year"/);
  assert.match(tariff,/value="2022"/);
  assert.match(tariff,/data-tariff-field="rate"/);
  assert.match(tariff,/Failure category|Échec catégorisé/);
  assert.match(tariff,/restart_from_zero/);
  assert.doesNotMatch(tariff,/private-body/);
  fake._historyDiscovery.set(account.entry_id,interrupted);
  const stopped=P._historyDiscoveryView.call(fake,"meters");
  assert.match(stopped,/Découverte historique : Interrompue/);
  assert.match(stopped,/restart_from_zero/);
  fake._historyDiscovery.set(account.entry_id,running);
  fake._tariffJobId=running.id;
  const progress=P._historyDiscoveryView.call(fake,"meters");
  assert.match(progress,/Périodes vérifiées : 7/);
  assert.match(progress,/Requêtes HTTP : 12/);
  assert.match(progress,/data-tariff-years-cancel/);
  // Status polling uses existing job id and never starts a supplier job.
  let polls=0;
  fake._hass.callWS=async req=>{
    assert.equal(req.type,"trybatec/panel_history_job_status");
    assert.equal(req.job_id,running.id);
    polls++;
    return polls===1?{...running,discovery_status:"running",
      recorder_writes:false,energy_writes:false}:
      {...base,id:running.id,kind:"tariff_year_coverage",status:"complete",
        complete:true,result:{status:"complete",coverage:fullCoverage,
          recorder_writes:false,energy_writes:false}};
  };
  const result=await P._waitForHistoryJob.call(fake,account.entry_id,
    {id:running.id,status:"running"},"tariff_year_coverage");
  assert.equal(polls,2);
  assert.equal(result.status,"complete");
  assert.equal(fake._historyDiscovery.get(account.entry_id).discovery_status,"complete");
  console.log("C11 WebSocket and UI integration: PASS");
})().catch(err=>{console.error(err);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", script, str(PANEL)], text=True, capture_output=True,
        check=False, timeout=30,
    )
    assert result.returncode == 0, result.stderr
