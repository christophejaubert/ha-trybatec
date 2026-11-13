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
    const before=await page.evaluate(()=>globalThis.__crossCalls.length);
    await locator('nav button[data-tab="tariffs"]').click();
    assert.equal(await page.evaluate(()=>globalThis.__crossCalls.length),before,
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
    const callTypes=await page.evaluate(()=>globalThis.__crossCalls.map(c=>c.type));
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
    const callsBefore=await page.evaluate(()=>globalThis.__crossCalls.length);
    await locator('nav button[data-tab="meters"]').click();
    await locator('nav button[data-tab="history"]').click();
    await locator('nav button[data-tab="tariffs"]').click();
    const calls=await page.evaluate(()=>globalThis.__crossCalls);
    assert.equal(calls.length,callsBefore,
      "Navigation must reuse completed account scan rather than start it again");
    assert.equal(calls.filter(c=>c.type==="trybatec/panel_history_job_start").length,2);
    assert.ok(calls.every(c=>[
      "trybatec/panel_history_job_start","trybatec/panel_history_job_status",
      "trybatec/panel_history_job_cancel"
    ].includes(c.type)),"No Recorder/Energy/tariff/HA mutation permitted");
    assert.ok(calls.every(c=>!c.entry_id||c.entry_id==="SYNTHETIC-ENTRY-NO-SECRETS"),
      "Supplier history must remain account-isolated");
    assert.equal(await locator("#tariff-rate").isEnabled(),true);
  });

  const failures=checks.filter(c=>c.result==="FAIL");
  process.stdout.write(JSON.stringify({qualification:"C1-C11-cross-synthetic",
    matrix:prefix,results:checks,failed:failures.length})+"\n");
  if (failures.length) throw new Error("Independent #155 assertions failed on "+
    prefix+": "+failures.map(x=>x.id+": "+x.detail).join(" | "));
  return {passed:checks.length,failed:0};
}
module.exports={runCrossQualification};
