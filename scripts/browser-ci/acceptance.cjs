/* Synthetic, disposable browser acceptance for the Trybatec web component.
 * This is NOT a test of the real HA login, Home Assistant shell, vendor API
 * or production installation. Only snapshot and tariff coverage reads are allowed.
 */
"use strict";

const {chromium} = require("playwright");
const {join, resolve} = require("node:path");
const {mkdirSync} = require("node:fs");
const {createHash} = require("node:crypto");
const assert = require("node:assert/strict");

const repository = resolve(__dirname, "../..");
const panelJS = join(repository, "custom_components/trybatec/panel/trybatec-panel.js");
const artifacts = join(repository, "browser-acceptance-artifacts");
mkdirSync(artifacts, {recursive: true});

const meter = (serial, fluid, status, unit, source, value) => ({
  serial, lot:"SYNTH-LOT", fluid, status, unit, source, unit_verified:unit!==null,
  physical_key: createHash("sha256").update(fluid+"|"+serial).digest("hex").slice(0,24),
  first_observed_at:"2022-01-01T12:00:00+01:00",
  last_source_observed_at:"2026-10-10T12:00:00+02:00",
  last_observed_at:"2026-10-10T12:00:00+02:00",
  last_index:value, replacement_date_verified:false,
});
const meters = [
  meter("SYNTH-EF-NEW","EF","en_service","m³","live_api",90.75),
  meter("SYNTH-EF-OLD","EF","depose","m³","archived_verified_inventory",220),
  meter("SYNTH-CET-UNK","CET","inconnu",null,"live_api",null),
];
// The current snapshot lacks old dates; a full read-only supplier scan supplies them.
meters[1].first_observed_at=null;
meters[1].last_source_observed_at=null;
const legacyEntity = {
  entity_id:"sensor.synth_ef_index",
  unique_id:"SYNTH-EF-NEW_index",
  device_id:"synthetic-same-physical-device",
  state:"unavailable",unit:"m³",deposed:false,
  technical_role:"legacy_same_device_candidate",
  same_device_successors:["sensor.synth_ef_index_2"],
  energy_references:[{section:"energy_sources",index:0,type:"water"}],
  energy_reference_check:"available",can_delete:false,
  eligible_for_automatic_cleanup:false,
};
const snapshot = {
  domain:"trybatec",panel:"Trybatec",mode:"administrator_read_only",
  accounts:[{
    entry_id:"SYNTHETIC-ENTRY-NO-SECRETS",
    title:"Synthetic fixture (no vendor access)",
    data_loaded:true,meters,
    meter_options:meters.map(m=>({
      physical_key:m.physical_key,serial:m.serial,fluid:m.fluid,lot:m.lot,
      source_unit:m.unit??"unverified",chart_unit:m.fluid==="CET"?"kWh":"m³",
      confirmed_unit:m.unit,saved_unit:null,
      selected_unit:m.unit||"unverified",
      selection_origin:m.unit?"api":"unverified",
      allowed_units:m.fluid==="CET"?["kWh","MWh","GJ"]:["m³","L"],
      device_uuid:"",
    })),
    physical_meter_timeline:[{
      lot:"SYNTH-LOT",fluid:"EF",count:2,
      meters:[meters[1],meters[0]],
      date_policy:"source_observations_only_no_inferred_replacement"
    }],
    entities:[legacyEntity],
    technical_entity_audit:{
      status:"partial_read_only_dependency_audit",
      potential_legacy_entries:1,energy_referenced_entities:1,
      no_deletion_permitted:true,
      recorder_automations_dashboards_exhaustively_checked:false,
    },
    tariffs:{
      "2025":{EF:{rate:2.12,status:"approved"},ECS:{rate:7.5,status:"provisional"}},
      "2026":{EF:{rate:2.25,status:"provisional"}},
    },
    meter_tariffs:{},tariff_fingerprint:"synthetic-no-write",
    settings:{poll_minutes:720,sparse_hours:27,zero_review_days:1,log_level:"WARNING"},
    ledger:{status:"no_import",series:[],pending:0},
    archived_inventory_count:1,warnings:[],
  }],
  energy:{status:"available",sources:[{
    index:0,type:"water",statistic_id:"sensor.synth_ef_index",
  }]},
  no_automatic_cleanup:true,no_automatic_recorder_or_energy_changes:true,
};
const tabs=["overview","meters","history","tariffs","energy","diagnostics","settings"];
const destinations = ["FR-desktop","EN-desktop","FR-mobile","EN-mobile"];

async function runCase(browser, locale, device) {
  const mobile=device==="mobile";
  const context=await browser.newContext({
    viewport:mobile?{width:390,height:844}:{width:1440,height:900},
    deviceScaleFactor:1,
    reducedMotion:"reduce",
    locale:locale==="FR"?"fr-FR":"en-US",
  });
  const page=await context.newPage();
  const errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  await page.addInitScript(()=>{globalThis.__calls=[]});
  // Browser-only harness. No real HA network endpoint, no browser credentials.
  await page.route("**/*",async route=>{
    // Loading the panel icon is irrelevant to layout acceptance.
    await route.fulfill({status:200,body:"",contentType:"image/png"});
  });
  await page.goto("about:blank");
  await page.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0"><main id="fixture"></main></body></html>');
  await page.addScriptTag({path:panelJS});
  await page.evaluate(({snapshot,language})=>{
    const element=document.createElement("trybatec-panel");
    document.querySelector("#fixture").appendChild(element);
    const host=element;
    host.hass={
      language,
      callWS:async command=>{
        globalThis.__calls.push(command.type);
        if (command.type==="trybatec/panel_snapshot") return structuredClone(snapshot);
        if (command.type==="trybatec/panel_tariff_years") return {
          status:"complete", recorder_writes:false, energy_writes:false,
          meters:[{
            physical_key:snapshot.accounts[0].meters[1].physical_key,
            first_observed_at:"2021-12-21T00:00:00+01:00",
            last_source_observed_at:"2024-12-30T00:00:00+01:00",
          }],
        };
        throw new Error("Network and writes disabled in synthetic browser harness");
      },
    };
  },{snapshot,language:locale==="FR"?"fr-FR":"en-US"});
  await page.waitForFunction(()=>{
    const root=document.querySelector("trybatec-panel")?.shadowRoot;
    return Boolean(root?.querySelector("nav button[data-tab='settings']") && root.querySelector(".stat"));
  });
  const nav=page.locator("trybatec-panel nav button[data-tab]");
  assert.equal(await nav.count(),7,"The original seven Trybatec sections must remain present");
  const first=await nav.first().innerText();
  assert.match(first,locale==="FR"?/Vue d’ensemble/:/Overview/);
  for(const tab of tabs){
    await page.locator('trybatec-panel nav button[data-tab="'+tab+'"]').click();
    await page.waitForFunction(tab=>{
      const root=document.querySelector("trybatec-panel")?.shadowRoot;
      return root?.querySelector('button[data-tab="'+tab+'"]')?.getAttribute("aria-current")==="page"
        && Boolean(root.querySelector("main h2"));
    },tab);
    const heading=await page.locator("trybatec-panel main h2").first().innerText();
    assert.ok(heading.length>0,"Missing heading: "+tab);
    const overflow=await page.evaluate(()=>{
      const host=document.querySelector("trybatec-panel");
      const documentWidth=document.documentElement.scrollWidth;
      const hostWidth=host?.getBoundingClientRect().width||0;
      return {windowWidth:innerWidth,documentWidth,hostWidth};
    });
    assert.ok(overflow.documentWidth<=overflow.windowWidth+2,
      "Horizontal page overflow at "+locale+" "+device+" "+tab+": "+JSON.stringify(overflow));
    if(tab==="overview"){
      const text=await page.locator("trybatec-panel main").innerText();
      assert.match(text,locale==="FR"?/État de la configuration/:/Configuration status/);
    }
    if(tab==="meters"){
      const header=page.locator("trybatec-panel .meter-title").first();
      assert.equal(await header.count(),1,"Meter title must use fluid styling");
      assert.equal(await header.locator("ha-icon").count(),1,"Meter title fluid pictogram missing");
      const dates=await page.locator("trybatec-panel main").innerText();
      assert.doesNotMatch(dates,/2022-01-01T12:00:00/,"Raw ISO date leaked into meter details");
      const editor=page.locator("trybatec-panel .meter-options-grid");
      assert.equal(await editor.count(),1,"Meter unit/UUID editor missing");
      assert.equal(await page.locator("trybatec-panel select[data-meter-option-field='unit']").inputValue(),"m³");
      assert.equal(await page.locator("trybatec-panel input[data-meter-option-field='device_uuid']").inputValue(),"");
      assert.equal(await page.locator("trybatec-panel button[data-meter-options-save]").count(),1);
    }
    if(tab==="energy"){
      const locked=page.locator("trybatec-panel fieldset.prerequisite-locked");
      assert.equal(await locked.count(),1,"The version handoff must be locked without verified versions");
      assert.equal(await locked.getAttribute("disabled"),"","The handoff controls must be disabled");
      const panelText=await page.locator("trybatec-panel main").innerText();
      assert.match(panelText,locale==="FR"?/Parcours indisponible/:/Unavailable: prerequisites/);
    }
    if(tab==="settings"){
      const days=page.locator("trybatec-panel input[data-duration-field='days']");
      const hours=page.locator("trybatec-panel input[data-duration-field='hours']");
      const minutes=page.locator("trybatec-panel input[data-duration-field='minutes']");
      assert.equal(await days.inputValue(),"0");
      assert.equal(await hours.inputValue(),"12");
      assert.equal(await minutes.inputValue(),"0");
      const panels=page.locator("trybatec-panel main section.card");
      assert.ok(await panels.count()>=3,"Settings, logging and fallback need separate cards");
      const firstCard=panels.first();
      assert.equal(await firstCard.locator("select[data-log-level]").count(),0,
        "Logging must not be in polling card");
      const logs=page.locator("trybatec-panel select[data-log-level]");
      assert.equal(await logs.inputValue(),"WARNING");
      assert.equal(await page.locator("trybatec-panel button[data-log-save]").count(),1);
      assert.equal(await page.locator("trybatec-panel button[data-settings-save]").count(),1);
    }
    if(mobile){
      const hamburger=page.locator("trybatec-panel .menu-toggle");
      assert.equal(await hamburger.isVisible(),true,"HA main menu access missing on mobile");
    }
    if(tab==="diagnostics"){
      const content=await page.locator("trybatec-panel main").innerText();
      assert.match(content,locale==="EN"?/Partial audit|Legacy technical generation/i:/Audit partiel|Ancienne génération technique/i);
      assert.match(content,/sensor\.synth_ef_index/);
      assert.doesNotMatch(content,/data-technical-delete/);
    }
    if(tab==="tariffs"){
      await page.waitForFunction(()=>{
        const root=document.querySelector("trybatec-panel")?.shadowRoot;
        return root?.querySelector('select#tariff-year option[value="2020"]');
      });
      const content=await page.locator("trybatec-panel main").innerText();
      assert.match(content,/2[.,]25/);
      assert.match(content,/EUR\/m³/);
    }
    await page.screenshot({
      path:join(artifacts,locale+"-"+device+"-"+tab+".png"),
      fullPage:true,
      animations:"disabled",
    });
  }
  assert.deepEqual(errors,[],"Browser JavaScript errors: "+errors.join("; "));
  const observed=await page.evaluate(()=>globalThis.__calls);
  assert.ok(observed.every(x=>["trybatec/panel_snapshot","trybatec/panel_tariff_years"].includes(x)),
    "Only read-only snapshots and historical tariff scans are allowed in visual acceptance");
  assert.ok(observed.includes("trybatec/panel_tariff_years"),
    "Opening tariffs must load verified historical year bounds");
  await context.close();
  return {locale,device,tabs:tabs.length,errors:errors.length};
}

(async()=>{
  const browser=await chromium.launch({headless:true});
  try{
    const results=[];
    for(const [locale,device] of [["FR","desktop"],["EN","desktop"],["FR","mobile"],["EN","mobile"]]){
      results.push(await runCase(browser,locale,device));
    }
    process.stdout.write(JSON.stringify({mode:"synthetic-browser-not-real-HA",
      cases:results,screenshots:destinations.length*tabs.length,
      productionWrites:0,vendorRequests:0},null,2)+"\n");
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
