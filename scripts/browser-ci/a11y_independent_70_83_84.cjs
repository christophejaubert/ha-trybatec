/* FR/EN: synthetic-only audit of seven Trybatec views; no live HA.
 * This independent probe never loads credentials, vendor services or production.
 * It reports potential accessibility gaps; it does NOT certify WCAG AA or HA.
 */
"use strict";
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const crypto = require("node:crypto");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "../..");
const panelJS = path.join(root, "custom_components/trybatec/panel/trybatec-panel.js");
const reportFile = path.join(root, "ui-a11y-synthetic-report.json");
const tabs = ["overview", "meters", "history", "tariffs", "energy", "diagnostics", "settings"];
const cases = ["fr-FR", "en-US"].flatMap(language =>
  ["desktop", "mobile"].flatMap(device =>
    ["light", "dark"].map(theme => ({language, device, theme}))));

const key = s => crypto.createHash("sha256").update(s).digest("hex").slice(0, 24);
const meters = [
  {physical_key:key("SYNTH-EF"),serial:"SYNTH-EF",lot:"SYNTH-LOT",fluid:"EF",
    status:"en_service",unit:"m³",unit_verified:true,source:"live_api",last_index:42,
    first_observed_at:"2022-01-01",last_source_observed_at:"2026-01-01",
    last_observed_at:"2026-01-01"},
  {physical_key:key("SYNTH-OLD"),serial:"SYNTH-OLD",lot:"SYNTH-LOT",fluid:"EF",
    status:"depose",unit:"m³",unit_verified:true,source:"archived_verified_inventory",
    last_index:null,first_observed_at:null,last_source_observed_at:null,
    last_observed_at:null},
  {physical_key:key("SYNTH-CET"),serial:"SYNTH-CET",lot:"SYNTH-LOT",fluid:"CET",
    status:"inconnu",unit:null,unit_verified:false,source:"live_api",last_index:null,
    first_observed_at:null,last_source_observed_at:null,last_observed_at:null},
];
const snapshot = {
  domain:"trybatec",panel:"Trybatec",version:"0.3.4b1-SYNTHETIC",mode:"administrator_read_only",
  accounts:[{
    entry_id:"SYNTHETIC-NO-IDENTIFIERS",title:"SYNTHETIC",data_loaded:true,meters,
    meter_options:meters.map(m=>({
      physical_key:m.physical_key,serial:m.serial,lot:m.lot,fluid:m.fluid,
      source_unit:m.unit||"unverified",chart_unit:m.fluid==="CET"?"kWh":"m³",
      confirmed_unit:m.unit,saved_unit:null,selected_unit:m.unit||"unverified",
      selection_origin:m.unit?"api":"unverified",
      allowed_units:m.fluid==="CET"?["kWh","MWh","GJ"]:["m³","L"],device_uuid:"",
    })),
    physical_meter_timeline:[{
      lot:"SYNTH-LOT",fluid:"EF",count:2,meters:[meters[1],meters[0]],
      date_policy:"source_observations_only_no_inferred_replacement",
    }],
    entities:[],
    technical_entity_audit:{
      status:"partial_read_only_dependency_audit",potential_legacy_entries:0,
      energy_referenced_entities:0,no_deletion_permitted:true,
      recorder_automations_dashboards_exhaustively_checked:false,
    },
    tariffs:{},meter_tariffs:{},tariff_fingerprint:"SYNTHETIC-NO-WRITES",
    settings:{poll_minutes:720,sparse_hours:27,zero_review_days:1,log_level:"WARNING"},
    ledger:{status:"no_import",series:[],pending:0},
    communication_diagnostics:{active:[],recent:[],max_operations:20,retention_hours:24,persisted:false},
    archived_inventory_count:1,warnings:[],
  }],
  energy:{status:"available",sources:[]},
  technical_limits:{read_only:true,effective:{
    index_max_bytes:16777216,metadata_max_bytes:65536,max_history_received_bytes:67108864,
    max_index_lines:20000,max_index_points:120000,
    timeouts_seconds:{indexes:60,authentication:30,housing:25,device:20},
    transient_max_attempts:3,max_index_iterations_with_reauth:5,
    transient_backoff_base_ms:250,transient_backoff_max_ms:30000,
    history_pause_ms:200,history_serialized_per_account:true,
    max_global_duration_seconds:1800,max_global_http_requests:512,
  },proposed:{enforced:false,standard:{duration_seconds:120,http_requests:24},
    exhaustive:{duration_seconds:600,http_requests:80},proposed_pause_ms:500,
    max_concurrent_historical_scans_per_account:1}},
  no_automatic_cleanup:true,no_automatic_recorder_or_energy_changes:true,
};

function contrast(foreground, background) {
  const rgb = color => (color.match(/[0-9]+(?:\.[0-9]+)?/g)||[]).slice(0, 3)
    .map(Number).map(n=>{const x=n/255;return x<=0.04045?x/12.92:((x+0.055)/1.055)**2.4;});
  const a=rgb(foreground),b=rgb(background);
  if(a.length!==3||b.length!==3)return null;
  const lum=v=>v[0]*0.2126+v[1]*0.7152+v[2]*0.0722;
  const x=lum(a),y=lum(b);
  return Math.round(1000*(Math.max(x,y)+0.05)/(Math.min(x,y)+0.05))/1000;
}

async function one(browser, config) {
  const {language,device,theme}=config;
  const viewport=device==="mobile"?{width:390,height:844}:{width:1440,height:900};
  const context=await browser.newContext({viewport,locale:language,
    reducedMotion:"reduce",deviceScaleFactor:1});
  const page=await context.newPage(),errors=[];
  page.on("pageerror",e=>errors.push(e.message));
  await page.route("**/*",route=>route.fulfill({status:200,body:"",contentType:"image/png"}));
  try{
    await page.goto("about:blank");
    await page.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0"><div id="root"></div></body></html>');
    await page.addScriptTag({path:panelJS});
    await page.evaluate(({snapshot,language,dark})=>{
      globalThis.__syntheticCalls=[];
      const host=document.createElement("trybatec-panel");
      document.querySelector("#root").appendChild(host);
      host.hass={language,themes:{darkMode:dark},config:{time_zone:"Europe/Paris"},
        callWS:async call=>{
          globalThis.__syntheticCalls.push(call.type);
          if(call.type==="trybatec/panel_snapshot")return structuredClone(snapshot);
          if(call.type==="trybatec/panel_history_job_start")
            return {id:"SYNTHETIC-JOB",kind:call.kind,status:"running"};
          if(call.type==="trybatec/panel_history_job_status")
            return {id:"SYNTHETIC-JOB",status:"complete",complete:true,
              recorder_writes:false,energy_writes:false,
              result:{status:"complete",meters:[],recorder_writes:false,energy_writes:false}};
          throw new Error("Unsafe synthetic operation blocked");
        }};
    },{snapshot,language,dark:theme==="dark"});
    await page.waitForFunction(()=>Boolean(document.querySelector("trybatec-panel")?._data?.accounts?.length),
      null,{timeout:15000});
    const results=[];
    for(const tab of tabs){
      await page.locator('trybatec-panel nav button[data-tab="'+tab+'"]').click();
      await page.waitForFunction(name=>document.querySelector("trybatec-panel")?._tab===name,
        tab,{timeout:15000});
      await page.setViewportSize({width:320,height:760});
      const observation=await page.evaluate(()=>{
        const host=document.querySelector("trybatec-panel");
        const root=host.shadowRoot;
        const controls=[...root.querySelectorAll("button,input,select,textarea,a[href]")]
          .filter(el=>!el.matches(":disabled") && el.getClientRects().length);
        return {
          viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
          hostWidth:Math.ceil(host.getBoundingClientRect().width),
          hasHeading:Boolean(root.querySelector("main h2")),focusableCount:controls.length,
          undersizedTargets:controls.filter(el=>{
            const r=el.getBoundingClientRect();return r.width<24||r.height<24;
          }).map(el=>(el.getAttribute("aria-label")||el.innerText||el.tagName).slice(0,72)),
          buttons:[...root.querySelectorAll("button.primary,button.secondary")]
            .filter(el=>el.getClientRects().length&&!el.matches(":disabled")).slice(0,6)
            .map(el=>{
              const style=getComputedStyle(el);
              return {label:(el.getAttribute("aria-label")||el.innerText||"").slice(0,64),
                foreground:style.color,background:style.backgroundColor};
            }),
          statusIndicators:root.querySelectorAll(".status-indicator").length,
        };
      });
      await page.keyboard.press("Tab");
      const target=page.locator('trybatec-panel nav button[data-tab="'+tab+'"]');
      await target.focus();
      const focus=await target.evaluate(el=>{
        const s=getComputedStyle(el),r=el.getBoundingClientRect();
        return {outlineStyle:s.outlineStyle,outlineWidth:s.outlineWidth,
          inViewport:r.top>=0&&r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight};
      });
      results.push({
        tab, reflow320synthetic:observation.documentWidth<=322,
        ...observation,focus,
        sampledButtonContrast:observation.buttons.map(x=>({...x,ratio:contrast(x.foreground,x.background)})),
      });
      await page.setViewportSize(viewport);
    }
    const hotTheme=await page.evaluate(()=>{
      const host=document.querySelector("trybatec-panel"),hass=host._hass;
      const initial=host.dataset.trybatecTheme;
      host.hass={...hass,themes:{darkMode:initial!=="dark"}};
      const switched=host.dataset.trybatecTheme;
      host.hass={...hass,themes:{darkMode:initial==="dark"}};
      return {initial,switched,restored:host.dataset.trybatecTheme};
    });
    const calls=await page.evaluate(()=>globalThis.__syntheticCalls);
    const prohibited=calls.filter(x=>![
      "trybatec/panel_snapshot","trybatec/panel_history_job_start",
      "trybatec/panel_history_job_status"].includes(x));
    assert.deepEqual(prohibited,[],"No write call permitted in synthetic probe");
    assert.deepEqual(errors,[],"No unhandled page errors permitted");
    assert.equal(results.length,7);
    return {config,results,hotTheme,errors,prohibited,
      humanHA:false,voiceOverTalkBack:"NOT_TESTED",textZoom200:"NOT_TESTED",
      textSpacing:"NOT_TESTED",wcagAA:"NOT_ASSERTED"};
  }finally{await context.close();}
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  try{
    const results=[];
    for(const config of cases)results.push(await one(browser,config));
    const viewed=results.flatMap(v=>v.results);
    assert.equal(viewed.length,56);
    const summary={
      syntheticCases:viewed.length,
      reflowFailures:viewed.filter(x=>!x.reflow320synthetic).length,
      focusNotVisible:viewed.filter(x=>x.focus.outlineStyle==="none"||parseFloat(x.focus.outlineWidth)<2).length,
      focusOutsideViewport:viewed.filter(x=>!x.focus.inViewport).length,
      undersizedTargetObservations:viewed.reduce((n,x)=>n+x.undersizedTargets.length,0),
      realHomeAssistantRecettes:0,
    };
    const candidates=results.flatMap(record=>record.results.map(row=>({
      language:record.config.language,device:record.config.device,
      theme:record.config.theme,tab:row.tab,
      scrollWidth:row.documentWidth,viewport:row.viewport,
      reflowFailure:!row.reflow320synthetic,
      focusOutside:!row.focus.inViewport,
      undersizedTargetSample:row.undersizedTargets.slice(0,5),
    })));
    const detailed={
      reflow:candidates.filter(x=>x.reflowFailure),
      focusOutside:candidates.filter(x=>x.focusOutside).slice(0,12),
      undersizedTargets:candidates.filter(x=>x.undersizedTargetSample.length).slice(0,12),
    };
    fs.writeFileSync(reportFile,JSON.stringify({mode:"synthetic-only",summary,detailed,results},null,2)+"\n");
    process.stdout.write(JSON.stringify({report:reportFile,summary,detailed})+"\n");
    // Findings stay diagnostic: UI fixes require coordination with tariff PR #118.
    // A successful run proves the probe executed, NOT all WCAG checks passed.
  }finally{await browser.close();}
})().catch(err=>{console.error(err);process.exitCode=1;});
