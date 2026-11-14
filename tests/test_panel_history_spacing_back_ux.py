"""History layout and contextual back button regression tests (issue #155).

All fixtures are synthetic and executed in Node's isolated VM; no real HA,
Trybatec account, supplier requests, Recorder or Energy writes.
"""
from pathlib import Path
import shutil
import subprocess

import pytest


PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"


def test_history_spacing_and_read_only_refresh_contract():
    source = PANEL.read_text(encoding="utf-8")
    assert ".history-discovery{margin-bottom:16px}" in source
    assert ".meter-history-context{margin:0 0 16px;" in source
    assert "meter-return-button" in source
    assert "mdi:arrow-left-circle-outline" in source
    assert "data-discovery-refresh" in source
    assert "trybatec/panel_history_discovery_status" in source
    # The refresh click is a passive status read, while the scan is a distinct explicit action.
    assert "if (btn.dataset.discoveryRefresh!==undefined) {this._readHistoryDiscovery?.();return;}" in source
    assert "if (btn.dataset.historicalScan!==undefined) {this._loadTariffYearCoverage(true);return;}" in source


def test_history_layout_in_french_and_english_with_and_without_meter():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for executable synthetic UI checks")
    js = r"""
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync(process.argv[1],"utf8");
const sandbox={HTMLElement:class {},customElements:{get:()=>false,define:()=>{}},
  window:{matchMedia:()=>({matches:true})}};
vm.runInNewContext(source+
  "\nglobalThis.__historyUI={Panel:TrybatecPanel.prototype,style};",
  sandbox,{timeout:4000});
const {Panel:p,style}=sandbox.__historyUI;
assert.ok(style.includes(".history-discovery{margin-bottom:16px}"));
assert.ok(style.includes(".meter-history-context{margin:0 0 16px;"));
assert.ok(style.includes(".meter-return-button{display:inline-flex;align-items:center;gap:7px}"));

const meter={physical_key:"a".repeat(24),fluid:"CET",lot:"SYNTH-LOT",
  serial:"SYNTH-123",status:"depose",unit:"kWh",
  first_observed_at:"2021-01-01",last_source_observed_at:"2024-01-01"};
const account={entry_id:"SYNTH-ACCOUNT",meters:[meter]};
const f={_current:account,_historyDiscovery:new Map(),_historyContextKey:meter.physical_key,
  _historyPreview:null,_historySelected:"",_historyBusy:false,
  _historyStart:"2021-01-01",_historyEnd:"2024-01-01",
  _historyJobId:null,_historyJobStatus:null,_historyError:"",_historyMessage:"",
  _historyMode:"linear",_historyReason:"undetermined",_t:(fr,en)=>fr,
  _meters:()=>account.meters,_heading:()=>"<header>History</header>",
  _historyDiscoveryView:p._historyDiscoveryView,
  _historySummary:()=>'<section class="card">Summary</section>',
  _historyDatesHelp:()=>"",_syncHistoryDates:()=>{},
  _readingReview:()=>"",_originView:()=>"",_date:x=>x||""};
function verify(meterChosen,english){
  f._historyContextKey=meterChosen?meter.physical_key:null;
  f._t=(fr,en)=>english?en:fr;
  const html=p._history.call(f);
  const first=html.indexOf('class="notice history-discovery"');
  const context=html.indexOf('class="meter-history-context');
  const period=html.indexOf('<section class="card"><div class="panel-title">');
  assert.ok(first>=0,"History discovery has its own scoped margin in both modes");
  assert.ok(period>first,"Discovery notice precedes period card");
  if(meterChosen){
    assert.ok(context>first&&context<period,"Meter context appears between two cards");
    const button=html.match(/<button[^>]+data-tab="meters"[^>]*>[^<]*<ha-icon[^>]+><\/ha-icon>[^<]*<\/button>/);
    assert.ok(button,"Back button includes icon preceding text");
    assert.match(button[0],/mdi:arrow-left-circle-outline/);
    assert.match(button[0],english?/Back to meter/:/Retour au compteur/);
    assert.match(button[0],/aria-hidden="true"/);
  } else {
    assert.equal(context,-1,"No meter-context card without selected physical meter");
    assert.ok(!html.includes("meter-return-button"),"No back-to-meter button when no selection");
  }
  assert.match(html,/data-discovery-refresh/);
  assert.match(html,/data-historical-scan/);
}
for(const english of [false,true]){
  verify(true,english);verify(false,english);
  f._historyDiscovery.set(account.entry_id,{
    discovery_status:"complete",periods_verified:1,cache_reused:true,
    coverage:{status:"complete",completeness:"account_full",meters:[]}
  });
  verify(true,english);verify(false,english);
  f._historyDiscovery.clear();
}
console.log("History layout and back icon FR/EN selected/unselected: PASS");
"""
    result = subprocess.run(
        [node, "-e", js, str(PANEL)],
        capture_output=True, text=True, check=False, timeout=25,
    )
    assert result.returncode == 0, result.stderr
