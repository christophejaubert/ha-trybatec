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
    // Check the real DOM event path on all editable fields visible in this tab.
    // Replacing the focused native input on any intermediate date digit is
    // precisely the regression that made entering four-digit years impossible.
    const focusChecks=await page.evaluate(()=>{
      const root=document.querySelector("trybatec-panel").shadowRoot;
      const fields=[...root.querySelectorAll(
        'input[type="date"],input[type="time"],input[type="number"],'+
        'input[type="text"]:not([data-query]),textarea'
      )].filter(el=>!el.disabled && !el.readOnly && el.getClientRects().length);
      const errors=[];
      for(const element of fields) {
        const original=element.value;
        const desired=element.type==="date"?"2021-12-31":
          element.type==="time"?"14:25:30":
          element.type==="number"?"1234":"test";
        element.focus();
        // Native date controls may emit incomplete values while the
        // day/month/year segments are being typed by a human.
        for (const candidate of (element.type==="date"
          ? ["", "2021-01-01", desired] : [desired])) {
          element.value=candidate;
          element.dispatchEvent(new Event("input",{bubbles:true}));
          element.dispatchEvent(new Event("change",{bubbles:true}));
          if (!element.isConnected || root.activeElement!==element) {
            errors.push("Input reconstructed / lost focus: "+
              (element.id||JSON.stringify(element.dataset)));
            break;
          }
        }
        if (!element.isConnected) break;
        element.value=original;
        element.dispatchEvent(new Event("input",{bubbles:true}));
        element.dispatchEvent(new Event("change",{bubbles:true}));
      }
      return {checked:fields.length,errors};
    });
    assert.deepEqual(focusChecks.errors,[],
      "Changing an editable field must not replace or blur it: "+tab);
    if(tab==="energy") {
      // Reproduce a stale Recorder plan: date edit must make import
      // impossible immediately, without destroying the date element.
      const safe=await page.evaluate(()=>{
        const host=document.querySelector("trybatec-panel");
        const root=host.shadowRoot;
        host._versionPlan={series:[],physical_meters:[]};
        host._versionImportBackup=true;
        host._render();
        const field=root.querySelector("#version-start");
        const button=root.querySelector("[data-version-import]");
        if(!field||!button) return {error:"missing Recorder controls"};
        field.focus();
        field.value="2021-01-01";
        field.dispatchEvent(new Event("input",{bubbles:true}));
        return {connected:field.isConnected,focused:root.activeElement===field,
          planInvalidated:host._versionPlan===null,buttonDisabled:button.disabled};
      });
      assert.deepEqual(safe,{
        connected:true,focused:true,planInvalidated:true,buttonDisabled:true,
      },"Recorder preview must be invalidated without losing the focused date");
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
  // Native browser keyboard test: type a full four-digit year as separate
  // key presses and verify the same date element retains focus each time.
  await page.locator('trybatec-panel nav button[data-tab="energy"]').click();
  const dateInput=page.locator('trybatec-panel #version-start');
  await dateInput.focus();
  await page.evaluate(()=>{
    globalThis.__yearInput=document.querySelector("trybatec-panel").shadowRoot
      .querySelector("#version-start");
  });
  for (const digit of ["2","0","2","1"]) {
    await page.keyboard.press(digit);
    const survives=await page.evaluate(()=>{
      const root=document.querySelector("trybatec-panel").shadowRoot;
      return globalThis.__yearInput?.isConnected&&root.activeElement===globalThis.__yearInput;
    });
    assert.equal(survives,true,"Typing a year digit must preserve the native date input");
  }
  // Simulate a new installed version while a user is editing. The panel
  // must offer a reload without silently discarding the unsaved form.
  const upgrade=await page.evaluate(async()=>{
    const host=document.querySelector("trybatec-panel");
    host._unsavedInput=true;
    host._data.version="0.3.1b1";
    const previous=host._hass.callWS;
    host._hass.callWS=async command=>command.type==="trybatec/panel_snapshot"
      ? {version:"0.3.1b2",accounts:[]} : previous(command);
    try {
      await host._checkServerVersion();
      const slot=host.shadowRoot.querySelector("[data-version-notice]");
      return {pending:host._serverVersionPending,notice:slot?.textContent||"",
        reloadButton:Boolean(slot?.querySelector("[data-reload-panel]"))};
    } finally {host._hass.callWS=previous;}
  });
  assert.equal(upgrade.pending,"0.3.1b2");
  assert.ok(upgrade.notice.includes("0.3.1b2"));
  assert.equal(upgrade.reloadButton,true,
    "Uncommitted user input must prevent automatic page reload");
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
