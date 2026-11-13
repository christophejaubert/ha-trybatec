/* #155, #36, #37, #88 — FR/EN independent synthetic business assertions.
 * Runs inside the existing disposable Playwright Chromium session.
 * No vendor network, production identifiers, Recorder/Energy or HA writes.
 * Deliberately fails when an approved feature is absent: never "green by omission".
 */
"use strict";
const assert = require("node:assert/strict");

async function runCrossQualification(page, {locale, device, dark, snapshot}) {
  const checks = [], prefix = [locale, device, dark?"dark":"light"].join("/");
  async function check(id, action) {
    try {
      await action();
      checks.push({id, result:"PASS"});
    } catch (error) {
      checks.push({id, result:"FAIL", detail:String(error.message).slice(0,350)});
    }
  }
  const locator = selector => page.locator("trybatec-panel "+selector);
  await page.evaluate(data => {
    const host=document.querySelector("trybatec-panel");
    host._data=structuredClone(data); host._account=0; host._meter=0;
    const a=host._current, old=a.meters[1];
    // Two real-looking but entirely synthetic successive physical generations.
    old.first_observed_at="2020-04-03T00:00:00+02:00";
    old.last_source_observed_at="2024-06-09T00:00:00+02:00";
    old.last_index=null;
    old.historical_last_index_raw=321.5;
    a.meters.push({...a.meters[0],
      physical_key:"c".repeat(24),serial:"SYNTH-ECS-NEW",
      fluid:"ECS",first_observed_at:"2023-02-01T00:00:00+01:00",
      last_source_observed_at:"2026-08-15T00:00:00+02:00"});
    host._query="";host._historyContextKey=null;
    host._historyDatesEdited={start:false,end:false};
    host._historyStart="";host._historyEnd="";
    host._tariffCoverage=new Map();host._historyPreview=null;
    host._historySelected="";host._historyReason="undetermined";
    host._tab="meters";host._render();
    globalThis.__crossCalls=[];
  }, snapshot);

  await check("C1 verified zero / positive / unknown unavailable entities", async () => {
    const states=await page.evaluate(() => {
      const host=document.querySelector("trybatec-panel"),a=host._current;
      const previous={entities:a.entities,loaded:a.data_loaded};
      const capture=()=>{
        host._tab="overview";host._render();
        const card=[...host.shadowRoot.querySelectorAll(".stat")]
          .find(el=>/Entités indisponibles|Unavailable entities/i.test(el.getAttribute("aria-label")||""));
        return {state:card?.className,icon:card?.querySelector("ha-icon")?.getAttribute("icon"),
          accessible:card?.getAttribute("aria-label")};
      };
      a.entities=[];a.data_loaded=true;const zero=capture();
      a.entities=[{entity_id:"sensor.synthetic_unavailable",state:"unavailable"}];
      const positive=capture();
      a.data_loaded=false;const unknown=capture();
      a.entities=previous.entities;a.data_loaded=previous.loaded;
      host._tab="meters";host._render();
      return {zero,positive,unknown};
    });
    assert.match(states.zero.state||"",/stat-success/);
    assert.equal(states.zero.icon,"mdi:check-circle-outline");
    assert.match(states.positive.state||"",/stat-warning/);
    assert.equal(states.positive.icon,"mdi:alert-circle-outline");
    assert.match(states.unknown.state||"",/stat-unknown/);
    assert.equal(states.unknown.icon,"mdi:help-circle-outline");
    assert.ok(states.zero.accessible&&states.unknown.accessible);
  });

  await check("C3 immediate selected physical detail after keyboard selection", async () => {
    const old=locator('button[data-meter="1"]');
    await old.focus();await page.keyboard.press("Enter");
    const observed=await page.evaluate(()=>{
      const host=document.querySelector("trybatec-panel"),root=host.shadowRoot;
      return {selected:host._current.meters[host._meter]?.serial,
        title:root.querySelector(".meter-title")?.textContent,
        detail:root.querySelector("[data-meter-detail]")?.getAttribute("tabindex"),
        focused:root.activeElement?.dataset?.meterDetail!==undefined||
          root.activeElement?.dataset?.meter==="1"};
    });
    assert.equal(observed.selected,"SYNTH-EF-OLD");
    assert.match(observed.title||"",/SYNTH-EF-OLD/);
    assert.equal(observed.detail,"-1");
    assert.equal(observed.focused,true);
  });

  await check("C5-C6 meter action states and distinct retired raw index", async () => {
    const result=await page.evaluate(() => {
      const host=document.querySelector("trybatec-panel"),a=host._current;
      const old=a.meters[1],active=a.meters[0],unknown=a.meters[2];
      const rows=[...host.shadowRoot.querySelectorAll("button[data-meter]")];
      return {
        active:host._meterActionState(active),retired:host._meterActionState(old),
        unknown:host._meterActionState(unknown),
        noCurrentIndex:old.last_index===null,hasUnqualifiedRaw:old.historical_last_index_raw===321.5,
        unique: new Set(a.meters.map(m=>m.physical_key)).size===a.meters.length,
        rowLabels:rows.map(b=>b.textContent),
        rowStates:rows.map(b=>({
          state:b.querySelector(".status-indicator")?.textContent,
          icon:b.querySelector(".status-indicator ha-icon")?.getAttribute("icon"),
          fluid:b.querySelector(".fluid-icon")?.getAttribute("icon")
        }))
      };
    });
    assert.equal(result.unique,true);
    assert.equal(result.active.kind,"passed");
    assert.equal(result.noCurrentIndex,true);
    assert.equal(result.hasUnqualifiedRaw,true);
    assert.equal(result.retired.kind,"unverified",
      "A retired raw historical index cannot become qualified automatically");
    assert.notEqual(result.unknown.kind,"passed");
    assert.notEqual(result.retired.kind,"issue",
      "No current index on a retired meter is not a confirmed anomaly");
    assert.ok(result.rowLabels.some(s=>s.includes("SYNTH-EF-OLD")));
    assert.ok(result.rowStates.every(s=>s.state&&s.icon&&s.fluid),
      "Actions need text+status pictogram distinct from the fluid pictogram");
  });

  await check("C7 no links to obsolete review UI across seven tabs", async () => {
    for (const tab of ["overview","meters","history","tariffs","energy","diagnostics","settings"]) {
      await locator('nav button[data-tab="'+tab+'"]').click();
      const old=await page.evaluate(() => {
        const root=document.querySelector("trybatec-panel").shadowRoot;
        return [...root.querySelectorAll("button,a[href]")].filter(n=>
          /ancienne ihm de révision|existing review interface|legacy review (ui|interface)/i.test(
            (n.textContent||"")+" "+(n.getAttribute("href")||"")
          )).map(n=>n.outerHTML.slice(0,180));
      });
      assert.deepEqual(old,[],"Obsolete review access in "+tab);
      const visible=await locator("main").innerText();
      assert.doesNotMatch(visible,/aucun relevé inventé|aucun coût fictif|no fictitious|never fabricates measured indexes/i,
        "C4 obsolete invented-data boilerplate in "+tab);
    }
  });

  await check("C8 fluid context, physical lineage and icon distinction", async () => {
    const visual=await page.evaluate(() => {
      const host=document.querySelector("trybatec-panel");
      host._historyContextKey=host._current.meters[1].physical_key;
      host._tab="history";host._render();
      const root=host.shadowRoot;
      return {text:root.querySelector(".meter-history-context")?.textContent,
        contextClass:root.querySelector(".meter-history-context")?.className,
        fluidClass:root.querySelector(".meter-history-context .fluid-token")?.className,
        icon:root.querySelector(".meter-history-context .fluid-token ha-icon")?.getAttribute("icon"),
        otherIdentity:host._current.meters[0].physical_key!==host._current.meters[1].physical_key};
    });
    assert.match(visual.text||"",/SYNTH-EF-OLD/);
    assert.match(visual.contextClass||"",/fluid-surface/);
    assert.match(visual.fluidClass||"",/fluid-/);
    assert.ok(visual.icon?.startsWith("mdi:"));
    assert.equal(visual.otherIdentity,true);
  });

  await check("C9 account/meter evidence bounds, unknowns, custom preservation", async () => {
    const state=await page.evaluate(() => {
      const host=document.querySelector("trybatec-panel");
      host._historyContextKey=null;host._historyDatesEdited={start:false,end:false};
      host._historyStart="";host._historyEnd="";
      host._syncHistoryDates();
      const account={start:host._historyStart,end:host._historyEnd,help:host._historyDatesHelp()};
      host._historyContextKey=host._current.meters[1].physical_key;
      host._syncHistoryDates();
      const meter={start:host._historyStart,end:host._historyEnd,help:host._historyDatesHelp()};
      host._historyStart="2019-01-15";host._historyDatesEdited.start=true;
      host._historyContextKey=host._current.meters[0].physical_key;
      host._syncHistoryDates();
      const custom={start:host._historyStart,help:host._historyDatesHelp()};
      const previous=host._current.meters.map(m=>[m.first_observed_at,m.last_source_observed_at]);
      for(const m of host._current.meters){m.first_observed_at=null;m.last_source_observed_at=null;}
      host._tariffCoverage.clear();
      host._historyContextKey=null;host._historyDatesEdited={start:false,end:false};
      host._historyStart="";host._historyEnd="";host._syncHistoryDates();
      const unknown={start:host._historyStart,end:host._historyEnd,help:host._historyDatesHelp()};
      host._current.meters.forEach((m,i)=>{
        [m.first_observed_at,m.last_source_observed_at]=previous[i];
      });
      host._historyContextKey=null;host._historyDatesEdited={start:false,end:false};
      host._historyStart="";host._historyEnd="";host._syncHistoryDates();
      host._tab="history";host._render();
      return {account,meter,custom,unknown};
    });
    assert.equal(state.account.start,"2020-04-03");
    assert.equal(state.account.end,"2026-10-10");
    assert.equal(state.meter.start,"2020-04-03");
    assert.equal(state.meter.end,"2024-06-09");
    assert.notEqual(state.account.end,state.meter.end);
    assert.match(state.account.help,/partielle|partial/i);
    assert.match(state.meter.help,/compteur|physical meter/i);
    assert.equal(state.custom.start,"2019-01-15");
    assert.match(state.custom.help,/personnalisée|custom/i);
    assert.equal(state.unknown.start,"");
    assert.equal(state.unknown.end,"");
    assert.match(state.unknown.help,/inconnue|unknown/i);
    assert.equal(await locator("#hist-start").inputValue(),"2020-04-03");
    assert.equal(await locator("#hist-end").inputValue(),"2026-10-10");
    await locator("[data-history-today]").click();
    const extended=await locator(".history-date-help").innerText();
    assert.match(extended,/aujourd’hui|today/i);
    const calls=await page.evaluate(()=>globalThis.__crossCalls);
    assert.equal(calls.length,0,"Changing history dates must never launch an API scan");
  });

  await check("C10 unknown origin blocks unapproved smoothing", async () => {
    const result=await page.evaluate(() => {
      const host=document.querySelector("trybatec-panel");
      host._tab="history";host._historyContextKey=null;
      host._historyPreview={
        history_summary:{meters:2,readings_to_review:0,by_meter:[],by_fluid:{}},
        review_candidates:[],
        proposals:{intervals:[{interval_key:"SYNTH-INTERVAL",lot:"SYNTH-LOT",
          fluid:"EF",meter_serial:"SYNTH-EF-NEW",start_date:"2022-01-01",
          end_date:"2022-02-01",status:"linear_available_after_explicit_confirmation",
          source_start_index:1,source_end_index:4,bounded_consumption:3,
          unit:"m³",days:31,daily_preview:[]}]},
        start_date:"2022-01-01",end_date:"2022-02-01",
      };
      host._historySelected="SYNTH-INTERVAL";
      host._historyReason="undetermined";host._render();
      const root=host.shadowRoot;
      return {selected:root.querySelector("#h-reason")?.value,
        approvalDisabled:root.querySelector("[data-history-approve]")?.disabled,
        explanation:root.querySelector('main')?.textContent||"",
        selection:host._historyReason};
    });
    assert.equal(result.selection,"undetermined");
    assert.equal(result.selected,"undetermined");
    assert.equal(result.approvalDisabled,true);
    assert.match(result.explanation,/Pourquoi cet intervalle|Why are these readings/i);
    assert.match(result.explanation,/Choisissez un motif|Choose a reason/i);
    assert.deepEqual(await page.evaluate(()=>globalThis.__crossCalls),[]);
  });

  await check("C11 failed global scan does not block manual tariff editing", async () => {
    await page.evaluate(() => {
      const host=document.querySelector("trybatec-panel");
      host._historyPreview=null;host._historyContextKey=null;
      host._tariffCoverage.clear();host._tab="meters";
      const original=host._hass.callWS;
      globalThis.__crossMode="failed";
      host._hass.callWS=async cmd=>{
        globalThis.__crossCalls.push({type:cmd.type,entry_id:cmd.entry_id||""});
        if(cmd.type==="trybatec/panel_history_job_start")
          return {id:"SYNTH-CROSS-READ",status:"running",kind:cmd.kind};
        if(cmd.type==="trybatec/panel_history_job_status") {
          if(globalThis.__crossMode==="failed")
            return {id:"SYNTH-CROSS-READ",status:"failed",complete:false};
          return {id:"SYNTH-CROSS-READ",status:"complete",complete:true,
            recorder_writes:false,energy_writes:false,
            result:{status:"complete",recorder_writes:false,energy_writes:false,
              cache_hit:true,meters:host._current.meters.map(m=>({
                physical_key:m.physical_key,
                first_observed_at:m.first_observed_at,
                last_source_observed_at:m.last_source_observed_at
              }))}};
        }
        if(cmd.type==="trybatec/panel_history_job_cancel")
          return {status:"cancel_requested"};
        return original(cmd);
      };
      host._render();
    });
    const before=await page.evaluate(()=>globalThis.__crossCalls.filter(
      c=>c.type!=="trybatec/panel_history_discovery_status").length);
    await locator('nav button[data-tab="tariffs"]').click();
    assert.equal(await page.evaluate(()=>globalThis.__crossCalls.filter(
      c=>c.type!=="trybatec/panel_history_discovery_status").length),before,
      "Opening tariff view must not initiate a supplier scan");
    await locator('nav button[data-tab="meters"]').click();
    await locator("[data-historical-scan]").click();
    await page.waitForFunction(()=>
      document.querySelector("trybatec-panel")._tariffCoverage
        .get("SYNTHETIC-ENTRY-NO-SECRETS")?.status==="error");
    await locator('nav button[data-tab="tariffs"]').click();
    assert.equal(await locator("#tariff-rate").isEnabled(),true);
    assert.equal(await locator("#tariff-year").isEnabled(),true);
    await locator("#tariff-year").fill("2040");
    assert.equal(await locator("#tariff-year").inputValue(),"2040");
    await locator("#tariff-year").fill("2026");
    assert.equal(await locator("#tariff-rate").inputValue(),"2.25");
    const callTypes=await page.evaluate(()=>globalThis.__crossCalls.map(c=>c.type).filter(
      type=>type!=="trybatec/panel_history_discovery_status"));
    assert.deepEqual(callTypes,[
      "trybatec/panel_history_job_start","trybatec/panel_history_job_status"
    ]);
  });

  await check("C11 explicit retry, cached data and no duplicate/unsafe commands", async () => {
    await page.evaluate(()=>{globalThis.__crossMode="complete";});
    await locator("[data-tariff-years-retry]").click();
    await page.waitForFunction(()=>
      document.querySelector("trybatec-panel")._tariffCoverage
        .get("SYNTHETIC-ENTRY-NO-SECRETS")?.status==="complete");
    const callsBefore=await page.evaluate(()=>globalThis.__crossCalls.filter(
      c=>c.type!=="trybatec/panel_history_discovery_status").length);
    await locator('nav button[data-tab="meters"]').click();
    await locator('nav button[data-tab="history"]').click();
    await locator('nav button[data-tab="tariffs"]').click();
    const calls=await page.evaluate(()=>globalThis.__crossCalls);
    assert.equal(calls.filter(c=>c.type!=="trybatec/panel_history_discovery_status").length,
      callsBefore,"Navigation must not start a new supplier history job");
    assert.equal(calls.filter(c=>c.type==="trybatec/panel_history_job_start").length,2);
    assert.ok(calls.every(c=>[
      "trybatec/panel_history_job_start","trybatec/panel_history_job_status",
      "trybatec/panel_history_job_cancel",
      "trybatec/panel_history_discovery_status"
    ].includes(c.type)),"No Recorder/Energy/tariff/HA mutation permitted");
    assert.ok(calls.every(c=>!c.entry_id||c.entry_id==="SYNTHETIC-ENTRY-NO-SECRETS"),
      "Supplier history must remain account-isolated");
    assert.equal(await locator("#tariff-rate").isEnabled(),true);
    await locator('nav button[data-tab="meters"]').click();
    assert.match(await locator("main").innerText(),
      /Résultats de recherche déjà disponibles réutilisés|Existing cached search results reused/i);
  });

  await check("C11 explicit cancellation remains read-only", async () => {
    const observed=await page.evaluate(async()=>{
      const host=document.querySelector("trybatec-panel");
      const previousConfirm=host._confirm;
      host._confirm=()=>true;
      host._tariffJobId="SYNTHETIC-CANCEL-REQUEST";
      try{await host._cancelHistoryJob("tariff_year_coverage");}
      finally{host._confirm=previousConfirm;host._tariffJobId=null;}
      return {call:globalThis.__crossCalls.at(-1),
        status:host._tariffCoverage.get(host._current.entry_id)?.status};
    });
    assert.equal(observed.call.type,"trybatec/panel_history_job_cancel");
    assert.equal(observed.call.entry_id,"SYNTHETIC-ENTRY-NO-SECRETS");
    assert.equal(observed.status,"complete",
      "A cancelled action must not fabricate another successful scan");
  });

  await page.evaluate(data=>{globalThis.__c11Snapshot=structuredClone(data);},snapshot);

  await check("C11 actual WebSocket status states, cache evidence and fail-closed UI", async () => {
    const observed=await page.evaluate(async data=>{
      const host=document.querySelector("trybatec-panel");
      const original=host._hass.callWS;
      const key=data.accounts[0].meters[1].physical_key;
      const account="SYNTHETIC-ENTRY-NO-SECRETS";
      const rows=[{physical_key:key,
        first_observed_at:"2021-12-21T00:00:00+01:00",
        last_observed_at:"2024-12-30T00:00:00+01:00"}];
      const full={status:"complete",completeness:"account_full",
        coverage_start:"2000-01-01",coverage_end:"2026-11-13",
        meters:rows,cache_reused:true,cache_expires_at:"2026-11-13T23:00:00+00:00"};
      const partial={...full,status:"incomplete",completeness:"bounded_period_only",
        coverage_start:"2023-01-01"};
      const fixtures=[
        ["none",{discovery_status:"not_started",coverage:{status:"not_started"}}],
        ["running",{discovery_status:"running",status:"running",
          progress:{periods_verified:4,http_requests:7}}],
        ["partial",{discovery_status:"incomplete",coverage:partial,
          retry_mode:"restart_from_zero"}],
        ["interrupted",{discovery_status:"interrupted",status:"cancelled",
          failure_category:"cancelled",retry_mode:"restart_from_zero"}],
        ["error",{discovery_status:"error",status:"failed",failure_category:"network",
          retry_mode:"restart_from_zero",failure_type:"PRIVATE_ERROR_SHOULD_NOT_APPEAR"}],
        ["full",{discovery_status:"complete",coverage:full,cache_reused:true}],
        ["invalidated",{discovery_status:"not_started",
          coverage:{status:"not_started",cache_invalidation_reason:"identity_changed"}}],
        ["unsafe",{discovery_status:"complete",coverage:full,recorder_writes:true}],
      ];
      const calls=[],results=[];
      try {
        host._tab="meters";
        for(const [name,payload] of fixtures) {
          if(name!=="invalidated") {
            host._data=structuredClone(data);host._account=0;host._meter=0;
            host._tariffCoverage.clear();
          }
          host._discoveryStates.clear();
          host._hass.callWS=async cmd=>{
            calls.push(cmd);
            if(cmd.type!=="trybatec/panel_history_discovery_status")
              throw new Error("Unexpected mutation or supplier read");
            return {...payload,recorder_writes:payload.recorder_writes??false,
              energy_writes:false};
          };
          await host._refreshDiscoveryStatus(account);
          host._render();
          results.push({name,view:host.shadowRoot.querySelector(
            "[data-discovery-status]")?.textContent||"",
            cached:host._tariffCoverage.get(account)?.status||"none",
            meterCount:host._tariffCoverage.get(account)?.meters?.length||0,
            state:host._discoveryStates.get(account)?.discovery_status});
        }
      } finally {
        host._hass.callWS=original;host._data=structuredClone(data);
        host._tariffCoverage.clear();host._discoveryStates.clear();
        host._tab="meters";host._render();
      }
      return {calls,results};
    },snapshot);
    const find=name=>observed.results.find(r=>r.name===name);
    assert.equal(observed.calls.length,8);
    assert.ok(observed.calls.every(c=>
      c.type==="trybatec/panel_history_discovery_status" &&
      c.entry_id==="SYNTHETIC-ENTRY-NO-SECRETS"));
    assert.match(find("none").view,/Aucune recherche historique|No verified historical/);
    assert.match(find("running").view,/4.*7/);
    assert.equal(find("partial").cached,"none","Bounded read cannot become complete");
    assert.match(find("partial").view,/partielle|Partial coverage/);
    assert.match(find("interrupted").view,/recherche complète|Full restart/);
    assert.match(find("error").view,/réseau|Network error|communication/i);
    assert.doesNotMatch(find("error").view,/PRIVATE_ERROR/);
    assert.equal(find("full").cached,"complete");
    assert.equal(find("full").meterCount,1);
    assert.match(find("full").view,/Cache mémoire|In-memory cache/);
    assert.equal(find("invalidated").cached,"none");
    assert.match(find("invalidated").view,/Cache invalidé|Cache invalidated/);
    assert.equal(find("unsafe").state,"unavailable");
    assert.equal(find("unsafe").cached,"none");
  });

  await check("C11 read-only refresh button uses status command, never supplier scan", async () => {
    const before=await page.evaluate(()=>{
      const host=document.querySelector("trybatec-panel");
      host._data=structuredClone(globalThis.__c11Snapshot);
      host._tab="meters";host._render();
      const previous=host._hass.callWS;
      const calls=[];
      host._hass.callWS=async cmd=>{
        calls.push({type:cmd.type,entry_id:cmd.entry_id});
        if(cmd.type!=="trybatec/panel_history_discovery_status")
          throw new Error("Unexpected supplier read");
        return {discovery_status:"not_started",status:"not_started",
          coverage:{status:"not_started",completeness:"unknown"},
          recorder_writes:false,energy_writes:false};
      };
      globalThis.__c11Refresh={previous,calls};
      return calls.length;
    });
    await locator("[data-discovery-refresh]").click();
    await page.waitForFunction(()=>globalThis.__c11Refresh.calls.length===1);
    const calls=await page.evaluate(()=>{
      const state=globalThis.__c11Refresh;
      document.querySelector("trybatec-panel")._hass.callWS=state.previous;
      delete globalThis.__c11Refresh;
      return state.calls;
    });
    assert.equal(before,0);
    assert.deepEqual(calls,[{type:"trybatec/panel_history_discovery_status",
      entry_id:"SYNTHETIC-ENTRY-NO-SECRETS"}]);
  });

  const failures=checks.filter(c=>c.result==="FAIL");
  process.stdout.write(JSON.stringify({qualification:"C1-C11-cross-synthetic",
    matrix:prefix,results:checks,failed:failures.length})+"\n");
  // FR/EN: preserve every failure but continue all eight browser matrices.
  // The acceptance runner exits nonzero after its final summary.
  return {passed:checks.length-failures.length,failed:failures.length,
    findings:failures.map(x=>({id:x.id,detail:x.detail}))};
}
module.exports={runCrossQualification};
