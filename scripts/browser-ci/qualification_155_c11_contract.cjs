/* #155 C11 independent frontend/backend contract probe — FR/EN.
 * Read-only synthetic browser: explicit status observation is mandatory.
 * Never calls the real vendor or Home Assistant and never converts failures to passes.
 */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const root=path.resolve(__dirname,"../..");
const backendJobs=path.join(root,"custom_components/trybatec/panel_history_jobs.py");
const backendCoverage=path.join(root,"custom_components/trybatec/panel_history_coverage.py");
const frontend=path.join(root,"custom_components/trybatec/panel/trybatec-panel.js");
const checks=["not_started","running","incomplete","complete","error","interrupted","invalidated"];

function checkSourceContract(){
  const jobs=fs.readFileSync(backendJobs,"utf8");
  const coverage=fs.readFileSync(backendCoverage,"utf8");
  const panel=fs.readFileSync(frontend,"utf8");
  assert.match(jobs,/vol\.Required\("type"\): "trybatec\/panel_history_discovery_status"/,
    "C11 backend discovery status must be registered");
  assert.match(jobs,/@websocket_api\.require_admin[\s\S]*?def ws_panel_history_discovery_status\(/,
    "C11 status must be admin-only");
  assert.match(jobs,/coverage_view\(/,"C11 backend must expose its validated scope");
  assert.match(jobs,/"retry_mode": "restart_from_zero"/);
  assert.match(coverage,/"bounded_period_only"/);
  assert.match(coverage,/"cache_invalidation_reason"/);
  assert.match(coverage,/"suggested_years_basis"/);
  return {
    backendContract:true,
    frontendStatusCommand:panel.includes("trybatec/panel_history_discovery_status"),
  };
}
function isoParis(){return new Date().toLocaleDateString("sv-SE",{timeZone:"Europe/Paris"});}
function backDays(ymd,days){const dt=new Date(ymd+"T12:00:00Z");dt.setUTCDate(dt.getUTCDate()-days);return dt.toISOString().slice(0,10);}
function fakeResponse(kind,snapshot){
  const today=isoParis(),start92=backDays(today,91);
  const old=snapshot.accounts[0].meters[1].physical_key;
  const recent=snapshot.accounts[0].meters[0].physical_key;
  const complete=kind==="complete",bounded=kind==="incomplete";
  const coverageState=complete?"complete":bounded?"incomplete":"not_started";
  const coverage={
    status:coverageState,
    completeness:complete?"account_full":bounded?"bounded_period_only":"unknown",
    coverage_start:complete?"2000-01-01":bounded?start92:null,
    coverage_end:complete||bounded?today:null,
    first_observed_at:complete?"2021-12-21T00:00:00+01:00":bounded?start92+"T12:00:00+02:00":null,
    last_observed_at:complete?"2026-08-01T00:00:00+02:00":bounded?today+"T00:00:00+01:00":null,
    meters:complete||bounded?[
      {physical_key:old,fluid:"EF",first_observed_at:bounded?start92+"T12:00:00+02:00":"2021-12-21T00:00:00+01:00",
        last_observed_at:bounded?today+"T00:00:00+01:00":"2024-12-30T00:00:00+01:00",
        last_source_observed_at:bounded?today+"T00:00:00+01:00":"2024-12-30T00:00:00+01:00",
        observed_years:bounded?[Number(start92.slice(0,4)),Number(today.slice(0,4))]:[2021,2024],
        covered_start:complete?"2000-01-01":start92,covered_end:today,
        provenance:"verified_supplier_observation"},
      {physical_key:recent,fluid:"EF",first_observed_at:bounded?start92+"T12:00:00+02:00":"2025-01-01T00:00:00+01:00",
        last_observed_at:bounded?today+"T00:00:00+01:00":"2026-08-01T00:00:00+02:00",
        last_source_observed_at:bounded?today+"T00:00:00+01:00":"2026-08-01T00:00:00+02:00",
        observed_years:bounded?[Number(start92.slice(0,4)),Number(today.slice(0,4))]:[2025,2026],
        covered_start:complete?"2000-01-01":start92,covered_end:today,
        provenance:"verified_supplier_observation"},
    ]:[],
    suggested_years:complete?[2021,2022,2023,2024,2025,2026]:bounded?[Number(start92.slice(0,4)),Number(today.slice(0,4))]:[],
    observed_years:complete?[2021,2024,2025,2026]:bounded?[Number(start92.slice(0,4)),Number(today.slice(0,4))]:[],
    suggested_years_basis:"observed_first_last_range_not_yearly_proof",
    periods_verified:complete?350:bounded?4:0,
    api_requests:0,cache_reused:complete,
    verified_at:complete||bounded?new Date().toISOString():null,
    cache_expires_at:complete||bounded?new Date(Date.now()+3600000).toISOString():null,
    cache_invalidation_reason:kind==="invalidated"?"identity_changed":null,
    retry_mode:"restart_from_zero",retry_reason:"no_atomic_window_checkpoints",
  };
  const jobStatus=kind==="running"?"running":kind==="interrupted"?"cancelled":
    kind==="error"?"failed":complete||bounded?"complete":"not_started";
  const status=kind==="invalidated"?"not_started":kind;
  return {
    id:kind==="not_started"||kind==="invalidated"?null:"a".repeat(24),
    kind:jobStatus==="not_started"?null:kind==="running"?"historical_preview":"tariff_year_coverage",
    status:jobStatus,discovery_status:status,coverage,
    verified_coverage:coverage,
    progress:kind==="running"?{periods_verified:3,http_requests:5}:null,
    failure_type:kind==="error"?"TrybatecConnectionError":null,
    failure_category:kind==="error"?"network":null,
    // Canary is deliberately synthetic. It may never appear in rendered UI.
    vendor_raw_error:"SYNTH_PRIVATE_NEVER_RENDER_C11",
    periods_verified:kind==="running"?3:coverage.periods_verified,
    api_requests:kind==="running"?5:0,cache_reused:complete,
    retry_mode:"restart_from_zero",retry_reason:"no_atomic_window_checkpoints",
    recorder_writes:false,energy_writes:false,complete:jobStatus==="complete",
  };
}
async function one(browser,snapshot,config,kind) {
  const locale=config.locale,small=config.device==="mobile";
  const context=await browser.newContext({locale,viewport:small?
    {width:390,height:844}:{width:1440,height:900},reducedMotion:"reduce"});
  try {
    const page=await context.newPage();
    await page.route("**/*",route=>route.fulfill({status:200,body:"",contentType:"image/png"}));
    await page.goto("about:blank");
    await page.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body><main id="fixture"></main></body></html>');
    await page.addScriptTag({path:frontend});
    await page.evaluate(({snapshot,status,locale,dark})=>{
      globalThis.__c11Calls=[];
      const host=document.createElement("trybatec-panel");
      document.querySelector("#fixture").appendChild(host);
      host.hass={language:locale,themes:{darkMode:dark},config:{time_zone:"Europe/Paris"},
        user:{is_admin:true},
        callWS:async command=>{
          globalThis.__c11Calls.push(structuredClone(command));
          if(command.type==="trybatec/panel_snapshot")return structuredClone(snapshot);
          if(command.type==="trybatec/panel_history_discovery_status"){
            if(command.entry_id!==snapshot.accounts[0].entry_id)
              throw new Error("C11 status queried for another account");
            return structuredClone(status);
          }
          // Only an explicit user retry may reach this synthetic job boundary.
          if(command.type==="trybatec/panel_history_job_start")
            return {id:"SYNTH-C11-RETRY",kind:command.kind,status:"running"};
          if(command.type==="trybatec/panel_history_job_status")
            return {id:"SYNTH-C11-RETRY",status:"failed",complete:false,
              failure_category:"network",recorder_writes:false,energy_writes:false};
          throw new Error("Synthetic harness blocks all writes and vendor calls");
        }};
    },{snapshot,status:fakeResponse(kind,snapshot),locale,dark:config.theme==="dark"});
    await page.waitForFunction(()=>Boolean(
      document.querySelector("trybatec-panel")?._data?.accounts?.length
    ),null,{timeout:12000});
    const viewed=[];
    for(const tab of ["meters","history","tariffs"]){
      await page.locator('trybatec-panel nav button[data-tab="'+tab+'"]').click();
      await page.waitForTimeout(25);
      viewed.push({tab,text:await page.locator("trybatec-panel main").innerText()});
    }
    // The captured status must be visible on each cross-module view, not
    // merely cached in the harness or present in a source-code string.
    const collected=await page.evaluate(()=>{
      const host=document.querySelector("trybatec-panel"),root=host.shadowRoot;
      return {allText:root.querySelector("main")?.textContent||"",
        calls:globalThis.__c11Calls,
        editableYear:root.querySelector("#tariff-year")?.disabled===false,
        editableRate:root.querySelector("#tariff-rate")?.disabled===false,
        active:host._tariffCoverage?.get(host._current.entry_id)||null};
    });
    const statusCalls=collected.calls.filter(c=>c.type==="trybatec/panel_history_discovery_status");
    assert.ok(statusCalls.length>=1,
      "Frontend never requests the registered C11 discovery-status command");
    assert.equal(collected.active?.status==="complete" && kind==="incomplete",false,
      "A 92-day bounded scan may not hydrate a complete historical tariff projection");
    assert.ok(collected.calls.every(c=>[
      "trybatec/panel_snapshot","trybatec/panel_history_discovery_status"
    ].includes(c.type)),"Page navigation must not start an expensive scan or write");
    assert.ok(statusCalls.every(c=>c.entry_id===snapshot.accounts[0].entry_id),
      "All status reads must be isolated to selected account");
    assert.equal(collected.editableYear,true,"Tariff year must remain editable");
    assert.equal(collected.editableRate,true,"Tariff rate must remain editable");
    assert.doesNotMatch(collected.allText,/SYNTH_PRIVATE_NEVER_RENDER_C11/,
      "A private supplier diagnostic was rendered to the administrator");
    const text=viewed.map(x=>x.text).join(" | ");
    const matches={
      not_started:/aucune recherche historique vérifiée|no verified historical scan|non lancée|not started/i,
      running:/en cours|running|progress/i,
      incomplete:/incomplète|partielle|incomplete|partial|bounded/i,
      complete:/fenêtre historique globale vérifiée|full historical window verified|complète|achevée|complete|completed/i,
      error:/erreur|échec|échouée|error|failed/i,
      interrupted:/interrompue|annulée|interrupted|cancelled/i,
      invalidated:/invalidé|changement d.identité|identity changed|invalidated|cache invalid/i,
    };
    for(const view of viewed)
      assert.match(view.text,matches[kind],
        "C11 state not visible in "+view.tab+" ("+kind+")");
    if(kind==="running"){
      assert.match(text,/3/,"Verified-period counter must be visible");
      assert.match(text,/5/,"Read-only HTTP request count must be visible");
    }
    if(kind==="incomplete"){
      assert.match(text,/couverture partielle|partial coverage/i,
        "A bounded 92-day period must be labeled as partial");
      assert.ok(text.includes(backDays(isoParis(),91)) && text.includes(isoParis()),
        "Both exact 92-calendar-day period boundaries must be visible");
      assert.doesNotMatch(text,/couverture historique complète du compte|full account coverage/i);
    }
    if(kind==="complete"){
      assert.match(text,/cache|réutilis|reus/i);
      assert.match(text,/2021|2024|2025/,"Physical meter historical dates should be visible");
    }
    if(kind==="error"){
      assert.match(text,/réseau|network|erreur de communication|communication error/i,"Redacted error category must be visible");
      assert.match(text,/restart_from_zero|redémarrage intégral|full restart|zéro|zero|début|beginning|recommenc/i,
        "Restart from zero must be explained when no safe checkpoints exist");
    }
    if(kind==="interrupted")
      assert.match(text,/restart_from_zero|redémarrage intégral|full restart|zéro|zero|début|beginning|recommenc/i);
    if(kind==="invalidated")
      assert.doesNotMatch(text,/couverture historique complète du compte|full account coverage/i);
    // A user-requested status refresh is read-only. It must query only the
    // currently selected account, never start even a single supplier scan.
    const refresh=page.locator("trybatec-panel main button[data-discovery-refresh]").first();
    assert.equal(await refresh.count(),1,"Read-only status refresh control missing");
    const statusBefore=await page.evaluate(()=>globalThis.__c11Calls.filter(
      c=>c.type==="trybatec/panel_history_discovery_status").length);
    await refresh.click();
    await page.waitForFunction(count=>globalThis.__c11Calls.filter(
      c=>c.type==="trybatec/panel_history_discovery_status").length>count,
      statusBefore,{timeout:4000});
    const refreshed=await page.evaluate(()=>globalThis.__c11Calls);
    assert.equal(refreshed.filter(c=>c.type==="trybatec/panel_history_job_start").length,0,
      "Manual C11 status refresh must never launch a supplier scan");
    assert.ok(refreshed.every(c=>["trybatec/panel_snapshot",
      "trybatec/panel_history_discovery_status"].includes(c.type)),
      "Status refresh is limited to the read-only discovery endpoint");
    if(kind==="invalidated"){
      // Reintroduce a stale locally complete projection, then force an
      // explicit status check. The backend invalidation must evict it.
      const evicted=await page.evaluate(async()=>{
        const host=document.querySelector("trybatec-panel");
        const id=host._current.entry_id;
        host._tariffCoverage.set(id,{status:"complete",cache_hit:true,
          meters:[{physical_key:host._current.meters[0].physical_key}]});
        await host._readHistoryDiscovery(id);
        return !host._tariffCoverage.has(id);
      });
      assert.equal(evicted,true,
        "An invalidated C11 source must purge stale tariff projections");
    }
    if(kind==="error"||kind==="interrupted"){
      const retry=page.locator("trybatec-panel main button[data-tariff-years-retry]").first();
      assert.equal(await retry.count(),1,"One explicit tariff scan action is required");
      assert.equal(await retry.isEnabled(),true,
        "Explicit restart must remain available after failure/interruption");
      assert.match(await retry.innerText(),locale.startsWith("fr")?
        /Rechercher les relevés de tous les compteurs/i:
        /Search historical readings for all meters/i,
        "Accessible retry label must describe the global supplier scan");
      await retry.click();
      await page.waitForFunction(()=>
        globalThis.__c11Calls.some(c=>c.type==="trybatec/panel_history_job_start"),
        null,{timeout:4000});
      const after=await page.evaluate(()=>globalThis.__c11Calls);
      const started=after.filter(c=>c.type==="trybatec/panel_history_job_start");
      assert.equal(started.length,1,"Exactly one explicit restart is permitted");
      assert.equal(started[0].entry_id,snapshot.accounts[0].entry_id);
      assert.equal(started[0].kind,"tariff_year_coverage");
      assert.ok(after.every(c=>[
        "trybatec/panel_snapshot","trybatec/panel_history_discovery_status",
        "trybatec/panel_history_job_start","trybatec/panel_history_job_status"
      ].includes(c.type)),"No implicit Recorder/Energy/other write on retry");
    }
    return {kind,locale,device:config.device,theme:config.theme,readCalls:statusCalls.length};
  }finally{await context.close();}
}
async function runC11Contract(browser,snapshot){
  const results=[];
  let source;
  try{source=checkSourceContract();results.push({id:"backend-schema",result:"PASS",
    detail:"Admin status command, coverage semantics, retry and cache fields exist"});}
  catch(e){
    // The backend contract and the frontend status command are independent gates.
    let frontendStatusCommand=false;
    try{frontendStatusCommand=fs.readFileSync(frontend,"utf8")
      .includes("trybatec/panel_history_discovery_status");}
    catch(_){/* Missing frontend fails its dedicated gate. */}
    source={backendContract:false,frontendStatusCommand};
    results.push({id:"backend-schema",result:"FAIL",detail:String(e.message).slice(0,240)});
  }
  if(!source.frontendStatusCommand)
    results.push({id:"frontend-wiring",result:"FAIL",
      detail:"Panel source has no call to trybatec/panel_history_discovery_status"});
  else results.push({id:"frontend-wiring",result:"PASS"});
  for(const locale of ["fr-FR","en-US"]){
    for(const device of ["desktop","mobile"]){
      for(const theme of ["light","dark"]){
        for(const kind of checks){
          const id=[locale,device,theme,kind].join("/");
          try{const detail=await one(browser,snapshot,{locale,device,theme},kind);
            results.push({id,result:"PASS",readCalls:detail.readCalls});}
          catch(error){results.push({id,result:"FAIL",detail:String(error.message).slice(0,280)});}
        }
      }
    }
  }
  const failures=results.filter(r=>r.result==="FAIL");
  const report={mode:"independent-synthetic-C11-frontend-backend",caseCount:results.length,
    passed:results.length-failures.length,failed:failures.length,
    results,productionWrites:0,vendorRequests:0,liveHA:false};
  process.stdout.write(JSON.stringify(report)+"\n");
  return {passed:report.passed,failed:report.failed,
    failures:failures.map(f=>({id:f.id,detail:f.detail}))};
}
module.exports={runC11Contract};
