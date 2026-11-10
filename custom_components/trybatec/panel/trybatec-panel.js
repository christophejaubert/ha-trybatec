/* Trybatec standalone Home Assistant panel — additive to the existing options flow. */
const TABS = [
  ["overview", "Vue d’ensemble", "mdi:view-dashboard-outline"],
  ["meters", "Compteurs", "mdi:counter"],
  ["history", "Historique & lissage", "mdi:chart-timeline-variant"],
  ["tariffs", "Tarifs", "mdi:cash-multiple"],
  ["energy", "Énergie & versions", "mdi:chart-sankey-variant"],
  ["diagnostics", "Diagnostics", "mdi:heart-pulse"],
  ["settings", "Réglages", "mdi:cog-outline"]
];
const FLUID = {EF:"Eau froide", ECS:"Eau chaude", CET:"Chauffage", unknown:"Fluide non identifié"};
const UNIT = {EF:"m³", ECS:"m³", CET:"kWh"};
const escapeText = (value) => String(value === null || value === undefined ? "" : value)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;")
  .replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
const safe = escapeText;
const style = [
  ":host {display:block;min-height:100%;color:var(--primary-text-color,#18213f);",
  "background:var(--primary-background-color,#fbfbfd);font-family:var(--paper-font-body1_-_font-family,Arial,sans-serif);}",
  "*{box-sizing:border-box}button,input,select{font:inherit}",
  "button{cursor:pointer}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #4385f5;outline-offset:2px}",
  ".wrap{max-width:1580px;margin:0 auto;padding:24px 26px 48px}",
  ".heading{display:flex;gap:16px;align-items:center;margin:0 0 22px}",
  ".mark{display:grid;place-items:center;height:60px;width:60px;border-radius:18px;background:linear-gradient(135deg,#d9efff,#ecf5ff);color:#1273ca;font-size:27px}",
  ".mark img{width:100%;height:100%;max-width:58px;max-height:58px;object-fit:contain}",
  "h1{font-size:30px;line-height:1.2;letter-spacing:-.7px;margin:0;font-weight:760}",
  "h2{font-size:22px;line-height:1.25;margin:0 0 7px}h3{font-size:16px;margin:0 0 7px}",
  "p{margin:0;line-height:1.45}.muted{color:var(--secondary-text-color,#67728a);font-size:13px}",
  ".headline-sub{color:var(--secondary-text-color,#67728a);margin-top:5px;font-size:14px}",
  ".badge{display:inline-block;padding:5px 9px;background:#e9f1ff;border-radius:14px;color:#254a94;font-weight:650;font-size:12px}",
  ".pill{font-size:12px;font-weight:650;border-radius:16px;padding:5px 9px;white-space:nowrap}",
  ".pill.on{background:#e4f5e8;color:#1b7539}.pill.off{background:#eef1f5;color:#556379}",
  ".pill.audit{background:#fff0d5;color:#9d6207}.pill.unknown{background:#eef1f5;color:#4c5566}",
  ".shell{display:grid;grid-template-columns:210px minmax(0,1fr);gap:22px;align-items:start}",
  ".nav{position:sticky;top:12px;display:flex;flex-direction:column;gap:4px;padding:12px;border:1px solid var(--divider-color,#e1e5ef);",
  "border-radius:18px;background:var(--card-background-color,#fff)}",
  ".nav button{display:flex;align-items:center;gap:10px;text-align:left;border:0;border-radius:11px;background:transparent;color:inherit;padding:13px 10px;font-weight:600}",
  ".nav button ha-icon{--mdc-icon-size:20px;color:var(--secondary-text-color,#64748b)}",
  ".nav button.active{background:#e9f1ff;color:#174d99}.nav button.active ha-icon{color:#1766b7}",
  ".main{min-width:0}.intro{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:19px}",
  ".cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin-bottom:21px}",
  ".card{min-width:0;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#e2e5ed);border-radius:16px;padding:19px}",
  ".stat{display:flex;gap:12px;align-items:center}.stat ha-icon{color:var(--primary-color,#1176c7);--mdc-icon-size:26px}",
  ".stat strong{font-size:25px;display:block;line-height:1.15}.stat span{color:var(--secondary-text-color,#637188);font-size:12px}",
  ".columns{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}",
  ".panel-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}",
  ".panel-title h3{margin:0}.meter-row{border-top:1px solid var(--divider-color,#e9ebf0);padding:12px 0}",
  ".meter-row:first-of-type{border-top:none}.meter-row button{display:block;background:transparent;border:0;color:inherit;text-align:left;width:100%;padding:0}",
  ".meter-row button:hover,.link:hover{color:var(--primary-color,#1476b8)}",
  ".meter-name{font-weight:650;font-size:14px;display:block;margin-bottom:3px;overflow-wrap:anywhere}",
  ".meter-sub{font-size:12px;color:var(--secondary-text-color,#738091);display:block;overflow-wrap:anywhere}",
  ".actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}",
  ".primary,.secondary{border:1px solid #b5c9e8;border-radius:11px;padding:10px 14px;background:#e9f1ff;color:#174b95;font-weight:650}",
  ".primary{background:var(--primary-color,#2977c4);color:#fff;border-color:var(--primary-color,#2977c4)}",
  ".link{color:var(--primary-color,#1976bd);text-decoration:none;font-weight:650;font-size:13px}",
  ".notice{padding:15px 18px;border-radius:12px;background:rgba(42,127,211,.07);border:1px solid #abcdf6;line-height:1.5;font-size:13px;margin-top:15px}",
  ".warning{background:rgba(228,159,39,.07);border-color:#e1c184}",
  ".split{display:grid;grid-template-columns:minmax(250px,340px) minmax(0,1fr);gap:14px}",
  ".scroll{max-height:650px;overflow:auto}.selected{background:rgba(66,138,223,.1);border-radius:11px;padding:10px!important}",
  ".detail-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}",
  ".detail-grid>div{background:rgba(120,140,165,.06);padding:12px;border-radius:10px;overflow-wrap:anywhere}",
  ".detail-grid strong{font-size:14px;display:block;margin-top:5px}",
  ".smallhead{font-size:11px;color:var(--secondary-text-color,#70798a)}",
  ".entity{padding:10px 0;border-top:1px solid var(--divider-color,#e8eaf1);font-size:13px;overflow-wrap:anywhere}",
  ".mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;overflow-wrap:anywhere}",
  ".search{display:block;width:100%;border:1px solid var(--divider-color,#d9e0eb);padding:11px 13px;border-radius:11px;background:var(--card-background-color,#fff);color:inherit;margin:0 0 12px}",
  ".list{display:grid;gap:10px}.line{border:1px solid var(--divider-color,#e1e5eb);border-radius:12px;padding:13px}",
  "table{width:100%;border-collapse:collapse;text-align:left;font-size:14px}th,td{padding:12px 10px;border-bottom:1px solid var(--divider-color,#e4e9ef)}",
  "th{font-size:12px;color:var(--secondary-text-color,#667085)}",
  ".empty{padding:18px;color:var(--secondary-text-color,#68758b);font-size:13px;line-height:1.55}",
  ".grid-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}",
  ".form-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}",
  "label{display:block;font-size:12px;font-weight:600;margin-bottom:4px;color:var(--secondary-text-color,#606e82)}",
  ".form-grid input,.form-grid select{width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:9px;color:inherit;background:var(--card-background-color,#fff)}",
  ".footer{font-size:12px;color:var(--secondary-text-color,#667085);margin-top:22px}",
  "@media(max-width:1050px){.columns{grid-template-columns:1fr 1fr}.cards{grid-template-columns:repeat(2,1fr)}.split{grid-template-columns:1fr}}",
  "@media(max-width:740px){.wrap{padding:15px 13px 28px}.heading{gap:10px;margin-bottom:15px}.mark{width:46px;height:46px}h1{font-size:25px}",
  ".shell{grid-template-columns:1fr;gap:14px}.nav{position:static;display:flex;flex-direction:row;overflow-x:auto;border:0;padding:4px 0;white-space:nowrap}",
  ".nav button{padding:10px 12px}.nav button span{white-space:nowrap}.intro{display:block}.columns,.grid-two,.detail-grid,.form-grid{grid-template-columns:1fr}",
  ".card{padding:15px}.cards{grid-template-columns:repeat(2,1fr)}.stat strong{font-size:23px}}"
].join("");

class TrybatecPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this._tab = "overview";
    this._account = 0;
    this._meter = 0;
    this._query = "";
    this._data = null;
    this._loading = false;
    this._error = "";
    this._message = "";
    this._started = false;
    this._tariffInput = {year:2026,fluid:"EF",physical_key:"",rate:"",status:"provisional"};
    this._tariffBusy = false;
    this._historyStart="2021-01-01";
    this._historyEnd=new Date().toLocaleDateString("sv-SE",{timeZone:"Europe/Paris"});
    this._historyPreview=null;
    this._historyBusy=false;
    this._historySelected="";
    this._historyMode="linear";
    this._historyReason="manual_periodic";
    this._historyError="";
    this._historyMessage="";
    this._originMeter="";
    this._originDate="2021-01-01";
    this._originIndex="0";
    this._originPreview=null;
    this._originBusy=false;
    this._originError="";
    this._originReason="manual_periodic";
    this._originRevision=false;
    this._originSaved="";
    this._settingsInput=null;
    this._settingsBusy=false;
    this._settingsMessage="";
    this._settingsError="";
    this._versionBusy=false;
    this._versionError="";
    this._versionMessage="";
    this._versionPlan=null;
    this._versionVerify=null;
    this._versionImportBackup=false;
    this._versionRevision=false;
    this._versionRetry=false;
    this._versionHeating=false;
    this._versionOld="";
    this._versionNew="";
    this._versionEnergyPlan=null;
    this._versionEnergyBackup=false;
    this._versionRollback=false;
    this._readingSelected="";
    this._readingAction="accept";
    this._readingMode="accounting";
    this._readingDate="";
    this._readingTime="00:00:00";
    this._readingReason="";
    this._readingOutside=false;
    this._readingBusy=false;
    this._readingMessage="";
    this._meterAudit=null;
    this._meterAuditBusy=false;
    this._meterAuditError="";
    this._meterAuditEntity="";
    this._energyHandoffPreview=null;
    this._energyBackup=false;
    this._energyResult="";
    this.shadowRoot.addEventListener("click", (event) => this._click(event));
    this.shadowRoot.addEventListener("change", (event) => this._change(event));
    this.shadowRoot.addEventListener("submit", (event) => this._submit(event));
  }
  set hass(value) {
    this._hass = value;
    if (this.isConnected && !this._started) this._fetch();
  }
  set narrow(value) { this._narrow = value; }
  set panel(value) { this._panel = value; }
  connectedCallback() { this._render(); if (this._hass && !this._started) this._fetch(); }
  get _current() { return this._data && this._data.accounts ? this._data.accounts[this._account] : null; }
  async _fetch() {
    if (!this._hass || this._loading) return;
    this._started = true;
    this._loading = true;
    this._error = "";
    this._render();
    try {
      this._data = await this._hass.callWS({type:"trybatec/panel_snapshot"});
      this._account = Math.min(this._account, Math.max(0,this._data.accounts.length-1));
      this._message = "";
    } catch (err) {
      this._error = "Impossible de charger les informations Trybatec. Consultez les journaux et réessayez.";
    } finally {
      this._loading = false;
      this._render();
    }
  }
  _click(event) {
    const btn = event.target.closest("button");
    if (!btn) return;
    if (btn.dataset.tab) {this._tab=btn.dataset.tab;this._query="";this._render();return;}
    if (btn.dataset.meter !== undefined) {this._meter=Number(btn.dataset.meter);this._meterAudit=null;this._energyHandoffPreview=null;this._render();return;}
    if (btn.dataset.account !== undefined) {this._account=Number(btn.dataset.account);this._meter=0;this._settingsInput=null;this._render();return;}
    if (btn.dataset.refresh !== undefined) {this._fetch();return;}
    if (btn.dataset.openOptions !== undefined) {window.location.assign("/config/integrations/integration/trybatec");return;}
    if (btn.dataset.openActions !== undefined) {window.location.assign("/developer-tools/action");return;}
    if (btn.dataset.openEnergy !== undefined) {window.location.assign("/energy");return;}
    if (btn.dataset.openMeter !== undefined) {this._tab="meters";this._meter=Number(btn.dataset.openMeter);this._render();return;}
    if (btn.dataset.tariffDelete !== undefined) {this._sendTariff(true);return;}
    if (btn.dataset.settingsSave !== undefined) {this._saveSettings();return;}
    if (btn.dataset.settingsReset !== undefined) {this._settingsInput=null;this._settingsError="";this._render();return;}
    if (btn.dataset.historyPreview !== undefined) {this._fetchHistory();return;}
    if (btn.dataset.historySelect !== undefined) {
      this._historySelected=btn.dataset.historySelect;this._render();return;
    }
    if (btn.dataset.historyApprove !== undefined) {this._approveHistory();return;}
    if (btn.dataset.originPreview !== undefined) {this._previewOrigin();return;}
    if (btn.dataset.originSave !== undefined) {this._saveOrigin();return;}
    if (btn.dataset.readingSelect !== undefined) {
      this._readingSelected=btn.dataset.readingSelect;
      const item=(this._historyPreview?.review_candidates||[]).find(
        x=>x.key===this._readingSelected
      );
      if (item) {
        this._readingDate=item.source_date.slice(0,10);
        this._readingTime=item.source_date.slice(11,19);
      }
      this._readingReason="";this._readingAction="accept";
      this._readingOutside=false;
      this._render();return;
    }
    if (btn.dataset.readingApprove!==undefined) {this._approveReading();return;}
    if (btn.dataset.readingSmoothing!==undefined) {
      const item=(this._historyPreview?.review_candidates||[]).find(
        x=>x.key===this._readingSelected
      );
      const match=(this._historyPreview?.proposals?.intervals||[]).find(
        x=>x.interval_key===item?.preceding_interval_key
      );
      if (!match || match.lot!==item.lot || match.fluid!==item.fluid ||
          match.meter_serial!==item.meter_serial ||
          match.source_end_at!==item.source_date) {
        this._historyError="Aucun intervalle précédent vérifiable : actualisez l’analyse.";
        this._render();return;
      }
      this._historySelected=match.interval_key;
      this._historyMode="linear";
      this._historyMessage="Intervalle précédent sélectionné pour examen ; aucune décision enregistrée.";
      this._render();
      this.shadowRoot.querySelector('[data-history-approve]')?.scrollIntoView({
        behavior:"smooth",block:"center"
      });
      return;
    }
    if (btn.dataset.entityAudit !== undefined) {
      this._auditMeterEntity(btn.dataset.entityAudit);return;
    }
    if (btn.dataset.energyPreview !== undefined) {this._previewHandoff();return;}
    if (btn.dataset.energyApply !== undefined) {this._applyHandoff();return;}
    if (btn.dataset.versionPreview !== undefined) {this._previewRecorderVersion();return;}
    if (btn.dataset.versionImport !== undefined) {this._importRecorderVersion();return;}
    if (btn.dataset.versionVerify !== undefined) {this._verifyRecorderVersion();return;}
    if (btn.dataset.versionEnergyPreview !== undefined) {this._previewRecorderEnergy();return;}
    if (btn.dataset.versionEnergyApply !== undefined) {this._activateRecorderEnergy();return;}
  }
  _change(event) {
    if (event.target.dataset.query !== undefined) {
      this._query=event.target.value.trim().toLowerCase();this._render();return;
    }
    if (event.target.dataset.energyBackup!==undefined) {
      this._energyBackup=event.target.checked;this._render();return;
    }
    const readingField=event.target.dataset.readingField;
    if (readingField) {
      const value=readingField==="outside"?Boolean(event.target.checked):event.target.value;
      const fields={
        action:"_readingAction",mode:"_readingMode",date:"_readingDate",
        time:"_readingTime",reason:"_readingReason",outside:"_readingOutside"
      };
      if (fields[readingField]) this[fields[readingField]]=value;
      this._render();return;
    }
    const versionField=event.target.dataset.versionField;
    if (versionField) {
      const fields={
        importBackup:"_versionImportBackup",revision:"_versionRevision",
        retry:"_versionRetry",heating:"_versionHeating",
        old:"_versionOld",new:"_versionNew",
        energyBackup:"_versionEnergyBackup",rollback:"_versionRollback",
        start:"_historyStart",end:"_historyEnd"
      };
      if (fields[versionField]) this[fields[versionField]]=
        event.target.type==="checkbox"?Boolean(event.target.checked):event.target.value;
      if (["old","new"].includes(versionField)) this._versionEnergyPlan=null;
      if (["start","end","heating"].includes(versionField)) this._versionPlan=null;
      this._render();return;
    }
    const settingsField=event.target.dataset.settingsField;
    if (settingsField) {
      if (!this._settingsInput) this._settingsInput={...this._current.settings};
      this._settingsInput[settingsField]=event.target.value;
      this._render();return;
    }
    const originField=event.target.dataset.originField;
    if (originField) {
      if (originField==="meter") this._originMeter=event.target.value;
      if (originField==="date") this._originDate=event.target.value;
      if (originField==="index") this._originIndex=event.target.value;
      if (originField==="reason") this._originReason=event.target.value;
      if (originField==="revision") this._originRevision=Boolean(event.target.checked);
      if (["meter","date","index"].includes(originField)) this._originPreview=null;
      this._originSaved="";this._render();return;
    }
    const historyField=event.target.dataset.historyField;
    if (historyField) {
      if (historyField==="start_date") this._historyStart=event.target.value;
      if (historyField==="end_date") this._historyEnd=event.target.value;
      if (historyField==="mode") this._historyMode=event.target.value;
      if (historyField==="reason") this._historyReason=event.target.value;
      this._render();return;
    }
    const field=event.target.dataset.tariffField;
    if (field) {
      this._tariffInput[field]=event.target.value;
      if (["year","fluid","physical_key"].includes(field)) {
        const item=this._existingTariff();
        this._tariffInput.rate=item?String(item.rate):"";
        this._tariffInput.status=item?item.status:"provisional";
      }
      this._render();
    }
  }
  _existingTariff() {
    const a=this._current, f=this._tariffInput;
    if (!a) return null;
    const year=String(f.year);
    return f.physical_key ?
      ((a.meter_tariffs||{})[year]||{})[f.physical_key]||null :
      ((a.tariffs||{})[year]||{})[f.fluid]||null;
  }
  _submit(event) {
    if (event.target.dataset.tariffForm !== undefined) {
      event.preventDefault();this._sendTariff(false);
    }
  }
  async _sendTariff(remove) {
    if (this._tariffBusy || !this._current) return;
    const f=this._tariffInput;
    const rate=Number(f.rate);
    if (!remove && (f.rate==="" || !Number.isFinite(rate) || rate<0)) {
      this._error="Le tarif doit être un montant non négatif et valide.";this._render();return;
    }
    const message=remove?
      "Supprimer ce tarif ? Le tarif commun sera de nouveau applicable à ce compteur, si défini.":
      "Enregistrer ce tarif annuel ? Les historiques Recorder et les préférences Énergie resteront inchangés.";
    if (!window.confirm(message)) return;
    this._tariffBusy=true;this._error="";this._render();
    try {
      const request={
        type:"trybatec/panel_tariff_change",
        entry_id:this._current.entry_id,
        year:Number(f.year),fluid:f.fluid,status:f.status,
        remove:Boolean(remove),confirmed:true,
        expected_fingerprint:this._current.tariff_fingerprint,
      };
      if (f.physical_key) request.physical_key=f.physical_key;
      if (!remove) request.rate=rate;
      await this._hass.callWS(request);
      this._data=await this._hass.callWS({type:"trybatec/panel_snapshot"});
      this._message=remove?"Tarif retiré.":"Tarif enregistré.";
      this._tariffInput.rate="";
      this._tariffInput.status="provisional";
      const existing=this._existingTariff();
      if (existing) {
        this._tariffInput.rate=String(existing.rate);
        this._tariffInput.status=existing.status;
      }
    } catch (_) {
      this._error="Modification refusée : vérifiez les données et actualisez les tarifs avant de réessayer.";
    } finally {
      this._tariffBusy=false;this._render();
    }
  }
  _header() {
    return '<header class="heading"><div class="mark"><img src="/api/trybatec_panel/logo.png" alt="Trybatec" loading="eager"></div>' +
      '<div><h1>Trybatec <span class="badge">Bêta</span></h1>' +
      '<p class="headline-sub">Gestion des compteurs, historiques, tarifs et énergie</p></div></header>';
  }
  _nav() {
    return '<nav class="nav" aria-label="Navigation Trybatec">' +
      TABS.map(tab=>'<button type="button" data-tab="'+tab[0]+'" aria-current="'+(this._tab===tab[0]?'page':'false')+
        '" class="'+(this._tab===tab[0]?'active':'')+'"><ha-icon icon="'+tab[2]+'"></ha-icon><span>'+tab[1]+'</span></button>').join("")+
      '</nav>';
  }
  _heading(title,sub,button) {
    return '<div class="intro"><div><h2>'+safe(title)+'</h2><p class="muted">'+safe(sub)+'</p></div>'+(button||"")+'</div>';
  }
  _meterName(m) {return FLUID[m.fluid] || "Compteur"; }
  _stat(number,label,icon) {
    return '<article class="card stat"><ha-icon icon="'+icon+'"></ha-icon><div><strong>'+safe(number)+'</strong><span>'+safe(label)+'</span></div></article>';
  }
  _badge(m) {
    const labels={en_service:"En service",depose:"Déposé",inconnu:"Statut à vérifier"};
    return '<span class="pill '+(m.status==="en_service"?"on":m.status==="depose"?"off":"unknown")+'">'+labels[m.status]+'</span>';
  }
  _meters() {return this._current ? this._current.meters : [];}
  _counts() {
    const values={en_service:0,depose:0,inconnu:0};
    this._meters().forEach(m=>{if (values[m.status]!==undefined)values[m.status]++;});
    return values;
  }
  _meterRow(m,i,action) {
    const line='<span class="meter-name">'+safe(this._meterName(m))+' · '+safe(m.serial)+'</span>'+
      '<span class="meter-sub">'+safe(m.lot||"Lot non renseigné")+' · '+safe(m.unit||"Unité à vérifier")+
      ' · '+(m.status==="depose"?"Déposé":m.status==="en_service"?"En service":"Statut inconnu")+'</span>';
    if (action==="detail") return '<div class="meter-row"><button type="button" class="'+(i===this._meter?"selected":"")+
      '" data-meter="'+i+'">'+line+'</button></div>';
    return '<div class="meter-row"><button type="button" data-open-meter="'+i+'">'+line+'</button></div>';
  }
  _overview() {
    const a=this._current, meters=this._meters(), counts=this._counts();
    const suspects=a.entities.filter(e=>e.state==="unavailable"||e.state==="not_loaded");
    const groups=[["Compteurs en service",meters.filter(m=>m.status==="en_service")],
                  ["Compteurs déposés",meters.filter(m=>m.status==="depose")],
                  ["Entités à auditer",suspects]];
    return this._heading("Vue d’ensemble","Les compteurs physiques sont distincts des anciennes entités Home Assistant.")+
      '<section class="cards" aria-label="Synthèse">'+
      this._stat(counts.en_service,"Compteurs en service","mdi:check-circle-outline")+
      this._stat(counts.depose,"Compteurs déposés","mdi:archive-outline")+
      this._stat(suspects.length,"Entités à examiner","mdi:alert-circle-outline")+
      this._stat(Object.keys(a.tariffs).length,"Exercices tarifaires","mdi:calendar-check-outline")+
      '</section><div class="columns">'+groups.map((group,index)=>
      '<section class="card"><div class="panel-title"><h3>'+group[0]+'</h3><span class="badge">'+group[1].length+'</span></div>'+
      '<p class="muted">'+[
        "Compteurs physiques actuellement relevés.",
        "Compteurs retirés conservés pour leur historique.",
        "Anciennes entités ou entités indisponibles : aucune suppression automatique."
      ][index]+'</p>'+
      (group[1].length?group[1].slice(0,5).map(item=>index===2?
        '<div class="entity mono">'+safe(item.entity_id)+'<div class="muted">État : '+safe(item.state)+'</div></div>':
        this._meterRow(item,meters.indexOf(item))).join(""):'<div class="empty">Aucune donnée disponible.</div>')+
      '<div class="actions"><button class="secondary" data-tab="'+(index===2?"diagnostics":"meters")+'">'+
      (index===2?"Auditer les entités":"Voir les compteurs")+'</button></div></section>'
      ).join("")+'</div>'+
      '<div class="notice"><strong>Historique préservé.</strong> Un compteur déposé est un équipement physique historique, pas une entité technique à supprimer. Les identifiants anciens ne sont nettoyés qu’après audit des dépendances et sauvegarde.</div>';
  }
  async _auditMeterEntity(entityId) {
    const m=this._meters()[this._meter];
    if (this._meterAuditBusy||!m||!this._current) return;
    this._meterAuditBusy=true;
    this._meterAuditError="";
    this._meterAudit=null;
    this._energyHandoffPreview=null;
    this._energyResult="";
    this._meterAuditEntity=entityId;
    this._render();
    try {
      this._meterAudit=await this._hass.callWS({
        type:"trybatec/panel_entity_audit",
        entry_id:this._current.entry_id,
        entity_id:entityId,lot:m.lot,fluid:m.fluid,serial:m.serial,
      });
    } catch (_) {
      this._meterAuditError="Association non démontrée : ne supprimez pas cette entité. Vérifiez son identité et ses références.";
    } finally {this._meterAuditBusy=false;this._render();}
  }
  async _previewHandoff() {
    const m=this._meters()[this._meter],a=this._meterAudit;
    if (this._meterAuditBusy||!m||!a||!this._current) return;
    this._meterAuditBusy=true;
    this._meterAuditError="";
    this._energyHandoffPreview=null;
    this._energyBackup=false;
    this._render();
    try {
      this._energyHandoffPreview=await this._hass.callWS({
        type:"trybatec/panel_energy_handoff_preview",
        entry_id:this._current.entry_id,
        entity_id:a.legacy_entity_id,lot:m.lot,fluid:m.fluid,serial:m.serial,
      });
    } catch (_) {
      this._meterAuditError="Basculement impossible : Recorder ou Énergie ne valide pas les deux séries. Aucune modification effectuée.";
    } finally {this._meterAuditBusy=false;this._render();}
  }
  async _applyHandoff() {
    const m=this._meters()[this._meter],a=this._meterAudit,p=this._energyHandoffPreview;
    if (this._meterAuditBusy||!m||!a||!p||!this._energyBackup) return;
    if (!window.confirm(
      "Confirmer le remplacement de la référence Énergie suivante ?\n\n"+
      p.old_statistic_id+" → "+p.new_statistic_id+
      "\n\nLa sauvegarde complète (dont Recorder) doit déjà être disponible. Les autres préférences restent conservées."
    )) return;
    this._meterAuditBusy=true;this._meterAuditError="";this._render();
    try {
      const result=await this._hass.callWS({
        type:"trybatec/panel_energy_handoff_apply",
        entry_id:this._current.entry_id,
        entity_id:a.legacy_entity_id,lot:m.lot,fluid:m.fluid,serial:m.serial,
        before_fingerprint:p.before_fingerprint,
        backup_confirmed:true,confirm:true,
      });
      this._energyResult=result.status==="energy_handoff_persisted_and_verified"?
        "Référence Énergie enregistrée et vérifiée. Les deux historiques sont conservés.":
        "Le résultat nécessite une vérification.";
      this._energyHandoffPreview=null;
      this._meterAudit=null;
      this._data=await this._hass.callWS({type:"trybatec/panel_snapshot"});
    } catch (_) {
      this._meterAuditError="Opération interrompue ou refusée. Consultez les journaux et vérifiez Énergie avant toute nouvelle tentative.";
      this._energyHandoffPreview=null;
    } finally {this._meterAuditBusy=false;this._render();}
  }
  _auditDetails(m) {
    const audit=this._meterAudit,plan=this._energyHandoffPreview;
    if (!audit && !plan && !this._energyResult&&!this._meterAuditError) return "";
    return '<div class="notice" style="margin-top:14px"><h3>Audit des relations techniques</h3>'+
      (this._meterAuditError?'<p>'+safe(this._meterAuditError)+'</p>':"")+
      (this._energyResult?'<p>'+safe(this._energyResult)+'</p>':"")+
      (audit?'<div class="list">'+
       '<p><strong>Statut :</strong> '+safe(audit.status)+'</p>'+
       '<p><strong>Ancienne entité :</strong> <span class="mono">'+safe(audit.legacy_entity_id)+'</span></p>'+
       '<p><strong>Nouvelle entité :</strong> <span class="mono">'+safe(audit.active_entity_id||"Non identifiée")+'</span></p>'+
       '<p><strong>Statistiques Recorder :</strong> '+safe(audit.recorder_statistics.status)+'</p>'+
       Object.entries(audit.recorder_statistics.existing||{}).map(([id,record])=>
         '<p class="mono">'+safe(id)+' : '+safe(record.found?"présente":"absente")+
         " · "+safe(record.unit||"unité inconnue")+'</p>').join("")+
       '<p><strong>Références Énergie :</strong> '+safe(audit.energy_references.length)+'</p>'+
       '<p><strong>Tableaux de bord et automatisations :</strong> audit non exhaustif</p>'+
       '<p><strong>Nettoyage :</strong> aucune suppression autorisée automatiquement</p>'+
       (audit.energy_handoff_possible_only_after_separate_preview?
         '<div class="actions"><button type="button" class="secondary" data-energy-preview '+(this._meterAuditBusy?"disabled":"")+
         '>Prévisualiser le basculement Énergie</button></div>':"")+
       '</div>':"")+
      (plan?'<div class="notice warning"><p><strong>Aperçu vérifié :</strong> '+safe(plan.old_statistic_id)+
        " → "+safe(plan.new_statistic_id)+'</p>'+
        '<p>Emplacement : '+safe(plan.source_type)+' · '+safe(plan.unit)+
        ". Les statistiques d’origine resteront stockées.</p>"+
        '<label style="margin-top:12px"><input type="checkbox" data-energy-backup '+
        (this._energyBackup?"checked":"")+
        '> Je confirme disposer d’une sauvegarde récupérable incluant Recorder.</label>'+
        '<div class="actions"><button type="button" class="primary" data-energy-apply '+
        (!this._energyBackup||this._meterAuditBusy?"disabled":"")+
        '>Confirmer et vérifier le basculement</button></div></div>':"")+
      '</div>';
  }
  _meterDetail(m) {
    if(!m) return '<div class="card empty">Sélectionnez un compteur pour consulter ses informations.</div>';
    const account=this._current;
    const related=account.entities.filter(e=>
      e.unique_id && (e.unique_id.includes("_"+m.serial+"_")||e.unique_id.endsWith("_"+m.serial+"_index")));
    return '<div class="card"><div class="panel-title"><h2>'+safe(this._meterName(m))+' · '+safe(m.serial)+'</h2>'+
      this._badge(m)+'</div><p class="muted">Compteur physique · '+safe(m.source==="live_api"?"Relevé par l’API":"Archivé localement")+'</p>'+
      '<div class="detail-grid">'+
      '<div><span class="smallhead">Lot</span><strong>'+safe(m.lot||"Non renseigné")+'</strong></div>'+
      '<div><span class="smallhead">Fluide</span><strong>'+safe(FLUID[m.fluid]||"Inconnu")+'</strong></div>'+
      '<div><span class="smallhead">Unité</span><strong>'+safe(m.unit||"À vérifier")+'</strong></div>'+
      '<div><span class="smallhead">Dernier index disponible</span><strong>'+safe(m.last_index===null?"Indisponible":m.last_index)+'</strong></div>'+
      '<div><span class="smallhead">Première observation connue</span><strong>'+safe(m.first_observed_at||"Non disponible")+'</strong></div>'+
      '<div><span class="smallhead">Dernière observation source</span><strong>'+safe(m.last_source_observed_at||"Non disponible")+'</strong></div>'+
      '<div><span class="smallhead">Dernier index exploitable</span><strong>'+safe(m.last_observed_at||"Non vérifié")+'</strong></div>'+
      '<div><span class="smallhead">Statut de l’unité</span><strong>'+safe(m.unit_verified?"Vérifiée":"À vérifier")+'</strong></div>'+
      '</div><h3>Relations techniques Home Assistant</h3>'+
      '<p class="muted">Les identités techniques ne doivent pas être supprimées tant que leurs références sont inconnues.</p>'+
      (related.length?related.map(e=>'<div class="entity"><span class="mono">'+safe(e.entity_id)+'</span> '+
      '<span class="pill '+(e.state==="unavailable"?"audit":"on")+'">'+safe(e.state)+'</span> '+
      '<button type="button" class="secondary" data-entity-audit="'+safe(e.entity_id)+'" '+
      (this._meterAuditBusy?"disabled":"")+'>Auditer</button></div>').join(""):
      '<div class="empty">Aucune association vérifiée par identifiant technique. Consultez l’audit des entités.</div>')+
      '<div class="actions"><button type="button" class="secondary" data-tab="history">Historique & lissage</button>'+
      '<button type="button" class="secondary" data-tab="diagnostics">Auditer les identifiants</button></div>'+
      this._auditDetails(m)+'</div>';
  }
  _meterTimeline() {
    const groups=this._current?.physical_meter_timeline||[];
    if (!groups.length) return '';
    return '<section class="card" style="margin-top:16px"><h3>Chronologie des compteurs physiques</h3>'+
      '<p class="muted">Par logement et fluide, fondée uniquement sur les observations. Les dates exactes de remplacement ne sont pas déduites.</p>'+
      groups.map(g=>'<div class="line" style="margin-top:12px"><strong>'+
        safe(FLUID[g.fluid]||g.fluid)+' · '+safe(g.lot||'Lot inconnu')+'</strong> '+
        '<span class="badge">'+safe(g.count)+' compteur(s)</span>'+
        '<div class="list" style="margin-top:10px">'+g.meters.map(m=>
          '<div class="meter-row"><span class="meter-name">'+safe(m.serial)+'</span> '+
          '<span class="pill '+(m.status==='en_service'?'on':m.status==='depose'?'off':'unknown')+'">'+
          safe(m.status==='en_service'?'En service':m.status==='depose'?'Déposé':'Statut inconnu')+'</span>'+
          '<div class="muted">Première observation : '+safe(m.first_observed_at||'Non connue')+
          ' · Dernière observation source : '+safe(m.last_source_observed_at||'Non connue')+'</div></div>'
        ).join('')+'</div></div>').join('')+
      '<div class="notice">Un compteur déposé est un appareil historique. Une entité technique indisponible ne constitue pas un compteur supplémentaire. Aucune date de remplacement n’est inventée.</div></section>';
  }

  _metersPage() {
    const meters=this._meters();
    const indexed=meters.map((m,i)=>({m,i})).filter(x=>!this._query||[
      x.m.serial,x.m.lot,FLUID[x.m.fluid],x.m.status].some(v=>String(v||"").toLowerCase().includes(this._query)));
    return this._heading("Compteurs","Inventaire physique : en service, déposés, ou statut non confirmé.")+
      '<div class="split"><section class="card"><input class="search" data-query placeholder="Rechercher un compteur (numéro, lot, fluide…)" value="'+safe(this._query)+'" aria-label="Rechercher un compteur">'+
      '<div class="scroll">'+indexed.map(x=>this._meterRow(x.m,x.i,"detail")).join("")+'</div>'+
      (!indexed.length?'<div class="empty">Aucun compteur correspondant. L’inventaire historique peut nécessiter une prévisualisation préalable.</div>':"")+
      '</section>'+this._meterDetail(meters[this._meter])+'</div>'+this._meterTimeline();
  }
  async _fetchHistory() {
    if (this._historyBusy || !this._current) return;
    this._historyBusy=true;
    this._historyError="";this._historyMessage="";this._historyPreview=null;
    this._historySelected="";this._render();
    try {
      const result=await this._hass.callWS({
        type:"trybatec/panel_history_preview",
        entry_id:this._current.entry_id,
        start_date:this._historyStart,end_date:this._historyEnd
      });
      this._historyPreview=result;
      this._historyMessage="Aperçu de l’historique actualisé. Aucune série Recorder n’a été modifiée.";
    } catch (_) {
      this._historyError="Prévisualisation impossible : vérifiez la période, la connexion et les journaux Trybatec.";
    } finally {
      this._historyBusy=false;this._render();
    }
  }
  async _approveHistory() {
    if (this._historyBusy || !this._current || !this._historySelected) return;
    const proposal=(this._historyPreview?.proposals?.intervals||[]).find(
      item=>item.interval_key===this._historySelected
    );
    if (!proposal) return;
    const eligible=proposal.status==="linear_available_after_explicit_confirmation";
    if (this._historyMode==="linear" && !eligible) return;
    const summary=proposal.start_date+" → "+proposal.end_date+" · "+proposal.meter_serial;
    if (!window.confirm("Confirmer la décision pour "+summary+" ?\n\n"+
        (this._historyMode==="linear"?
          "Répartition linéaire du résiduel entre les index sources vérifiés.":
          "Aucun lissage : conserver l’intervalle sans répartition.")+
        "\n\nLes index, Recorder et Énergie ne seront pas modifiés.")) return;
    this._historyBusy=true;this._historyError="";this._render();
    try {
      await this._hass.callWS({
        type:"trybatec/panel_smoothing_choice",
        entry_id:this._current.entry_id,
        interval_key:proposal.interval_key,
        mode:this._historyMode,reason:this._historyReason,
        confirm:true,
      });
      const revised=(this._historyPreview.proposals.intervals||[]).find(
        item=>item.interval_key===proposal.interval_key
      );
      if (revised) revised.choice={
        mode:this._historyMode, reason:this._historyReason
      };
      this._historyMessage="Décision enregistrée. Les index sources et Énergie restent inchangés.";
    } catch (_) {
      this._historyError="Décision refusée : l’intervalle a changé ou doit être réexaminé. Actualisez l’aperçu.";
    } finally {
      this._historyBusy=false;this._render();
    }
  }
  async _previewOrigin() {
    if (!this._current || this._originBusy || !this._originMeter) return;
    const meters=this._meters();
    const m=meters.find(x=>x.physical_key===this._originMeter);
    if (!m) return;
    if (this._originIndex.trim()==="" || !Number.isFinite(Number(this._originIndex))
        || Number(this._originIndex)<0) {
      this._originError="L’index initial estimé doit être un nombre positif ou nul.";
      this._render();return;
    }
    if (!window.confirm(
      "Confirmer que la date et l’index initial sont des HYPOTHÈSES, pas des relevés mesurés ?"+
      "\\n\\nCet aperçu n’enregistre aucune décision et ne modifie ni Recorder ni Énergie."
    )) return;
    this._originBusy=true;this._originError="";this._originSaved="";this._originPreview=null;this._render();
    try {
      this._originPreview=await this._hass.callWS({
        type:"trybatec/panel_estimated_origin_preview",
        entry_id:this._current.entry_id,
        lot:m.lot,fluid:m.fluid,serial:m.serial,
        estimated_start_date:this._originDate,
        estimated_start_index:Number(this._originIndex),
        confirm:true
      });
    } catch (_) {
      this._originError="Aperçu refusé : vérifiez la date de départ, le premier relevé, l’unité et les anomalies. Rechargez un historique couvrant l’origine choisie.";
    } finally {
      this._originBusy=false;this._render();
    }
  }

  async _saveOrigin() {
    const preview=this._originPreview;
    if (!this._current || !preview || this._originBusy) return;
    const m=this._meters().find(x=>x.physical_key===this._originMeter);
    if (!m || !/^[a-f0-9]{64}$/.test(preview.approval_fingerprint||"")) {
      this._originError="Un nouvel aperçu vérifié est nécessaire avant l’enregistrement.";
      this._render();return;
    }
    if (!window.confirm(
      "Enregistrer cette origine comme HYPOTHÈSE APPROUVÉE ?"+
      "\n\nLa date et l’index estimés ne sont pas des relevés mesurés."+
      "\nCette décision ne modifie ni les index réels, ni Recorder, ni Énergie."
    )) return;
    if (this._originRevision && !window.confirm(
      "Autoriser explicitement le remplacement d’une hypothèse déjà approuvée pour ce compteur ?"
    )) return;
    this._originBusy=true;this._originError="";this._originSaved="";this._render();
    try {
      const saved=await this._hass.callWS({
        type:"trybatec/panel_estimated_origin_save",
        entry_id:this._current.entry_id,
        lot:m.lot,fluid:m.fluid,serial:m.serial,
        estimated_start_date:this._originDate,
        estimated_start_index:Number(this._originIndex),
        reason:this._originReason,
        expected_fingerprint:preview.approval_fingerprint,
        confirm:true,confirm_revision:this._originRevision
      });
      if (saved.status!=="estimated_origin_decision_saved" ||
          saved.source_indices_unchanged!==true ||
          saved.recorder_writes!==false || saved.energy_writes!==false) {
        throw new Error("Unverified estimated-origin response");
      }
      this._originSaved="Hypothèse approuvée enregistrée séparément des index réels. "+
        "Aucun import Recorder ni changement Énergie : ces opérations nécessitent leur propre validation.";
      this._originRevision=false;
    } catch (_) {
      this._originError="Enregistrement refusé : source ou paramètres modifiés, décision antérieure "+
        "non remplaçable sans confirmation, ou historique à actualiser.";
    } finally {
      this._originBusy=false;this._render();
    }
  }
  _originView() {
    const meterOptions=this._meters().map(m=>'<option value="'+safe(m.physical_key)+'" '+
      (this._originMeter===m.physical_key?"selected":"")+'>'+
      safe((FLUID[m.fluid]||m.fluid)+" · "+m.serial+" · "+m.lot)+'</option>').join("");
    const preview=this._originPreview;
    return '<section class="card" style="margin-top:16px">'+
      '<div class="panel-title"><h3>Aucune borne antérieure fiable : simuler une origine estimée</h3>'+
      '<span class="pill audit">Hypothèse non mesurée</span></div>'+
      '<p class="muted">Indiquez une date de début et un index initial estimé (0 par défaut, modifiable). Le premier index réellement observé servira de borne finale. La période analysée doit commencer avant la date estimée.</p>'+
      '<div class="form-grid" style="margin-top:15px">'+
      '<div><label for="origin-meter">Compteur physique</label><select id="origin-meter" data-origin-field="meter">'+
      '<option value="">Choisir un compteur</option>'+meterOptions+'</select></div>'+
      '<div><label for="origin-date">Début estimé</label><input id="origin-date" type="date" data-origin-field="date" value="'+safe(this._originDate)+'"></div>'+
      '<div><label for="origin-index">Index initial estimé</label><input id="origin-index" type="number" min="0" step="any" data-origin-field="index" value="'+safe(this._originIndex)+'"></div></div>'+
      '<div class="actions"><button type="button" class="secondary" data-origin-preview '+
      (this._originBusy||!this._historyPreview?"disabled":"")+'>Calculer l’aperçu hypothétique</button></div>'+
      (this._originError?'<div class="notice warning">'+safe(this._originError)+'</div>':"")+
      (preview?'<div class="notice"><strong>Simulation calculée.</strong> Du '+
      safe(preview.start_date)+' au '+safe(preview.end_date)+', quantité estimée : '+
      safe(preview.estimated_total)+' '+safe(preview.unit)+
      '. Premier index réellement observé : '+safe(preview.first_observed_index)+
      ' à '+safe(preview.first_observed_at)+
      '. L’index initial '+safe(preview.estimated_initial_index)+
      ' est une hypothèse, pas une mesure. Aucune donnée n’a été enregistrée.</div>'+
      (preview.daily_preview?this._historyDayBars({
        daily_preview:preview.daily_preview,unit:preview.unit
      }):'<p class="muted">Le détail journalier est tronqué pour cette longue période.</p>')+
      '<div class="form-grid" style="margin-top:14px"><div>'+
      '<label for="origin-reason">Motif déclaré pour cette hypothèse</label>'+
      '<select id="origin-reason" data-origin-field="reason">'+
      '<option value="manual_periodic" '+(this._originReason==="manual_periodic"?"selected":"")+'>Relève manuelle périodique</option>'+
      '<option value="telemetry_failure" '+(this._originReason==="telemetry_failure"?"selected":"")+'>Panne de télérelève</option>'+
      '<option value="other" '+(this._originReason==="other"?"selected":"")+'>Autre motif déclaré</option>'+
      '</select></div></div>'+
      '<label style="display:block;margin-top:12px"><input type="checkbox" data-origin-field="revision" '+
      (this._originRevision?"checked":"")+'>'+
      ' Autoriser le remplacement d’une hypothèse déjà approuvée (confirmation supplémentaire)</label>'+
      '<div class="actions"><button type="button" class="primary" data-origin-save '+
      (this._originBusy?"disabled":"")+
      '>Approuver et enregistrer l’hypothèse</button></div>':"")+
      (this._originSaved?'<div class="notice">'+safe(this._originSaved)+'</div>':"")+
      '<p class="muted" style="margin-top:13px">Une hypothèse enregistrée reste distincte d’un index mesuré. Son incorporation à une version Recorder nécessite une validation distincte.</p></section>';
  }
  _historyComparison(proposal) {
    const comparison=proposal.before_after;
    if (!comparison || comparison.status!=='comparison_preview_only') {
      return '<div class="notice warning">Comparaison journalière non disponible : les bornes ou le détail doivent être revérifiés.</div>';
    }
    const rows=comparison.rows||[];
    const format=(value)=>Number(value).toLocaleString('fr-FR',{maximumFractionDigits:6});
    return '<section aria-label="Comparaison journalière avant et après lissage">'+
      '<h3>Comparaison avant / après · consommation et cumul</h3>'+
      '<p class="muted">Avant : seules les consommations journalières effectivement connues sont affichées. Le tiret signifie « non déterminé », jamais zéro. Après : répartition estimée du résiduel, sans modifier les index réels.</p>'+
      '<div class="detail-grid">'+
      '<div><span class="smallhead">Total entre bornes</span><strong>'+safe(format(comparison.bounded_total))+' '+safe(proposal.unit)+'</strong></div>'+
      '<div><span class="smallhead">Consommation réellement mesurée</span><strong>'+safe(format(comparison.measured_total))+' '+safe(proposal.unit)+'</strong></div>'+
      '<div><span class="smallhead">Consommation estimée</span><strong>'+safe(format(comparison.estimated_total))+' '+safe(proposal.unit)+'</strong></div></div>'+
      '<div class="scroll" style="max-height:360px"><table><thead><tr><th>Jour</th><th>Avant · mesuré</th><th>Après · consommation</th><th>Cumul après</th><th>Nature</th></tr></thead><tbody>'+
      rows.slice(0,90).map(r=>'<tr><td>'+safe(r.date)+'</td>'+
        '<td>'+safe(r.before_observed_consumption===null?'—':format(r.before_observed_consumption))+'</td>'+
        '<td>'+safe(format(r.after_consumption))+'</td>'+
        '<td>'+safe(format(r.cumulative_after))+'</td>'+
        '<td>'+safe(r.provenance==='measured'?'Mesuré':'Estimé linéaire')+'</td></tr>'
      ).join('')+'</tbody></table></div>'+
      (rows.length>90?'<p class="muted">Aperçu limité aux 90 premiers jours. Total et validation calculés sur l’ensemble de la période.</p>':'')+
      '<p class="muted" style="margin-top:10px">Le cumul est une consommation depuis le début de l’intervalle, pas un nouvel index mesuré. Aucune mesure source ni statistique Recorder n’est modifiée.</p></section>';
  }
  _historyDayBars(proposal) {
    const rows=proposal.daily_preview;
    if (!Array.isArray(rows)||!rows.length)
      return '<div class="empty">Le détail journalier est indisponible pour cette période. Aucun historique fictif n’est généré.</div>';
    const max=Math.max(0.000001,...rows.map(x=>Number(x.quantity)||0));
    return '<div style="display:flex;align-items:end;gap:2px;height:130px;overflow-x:auto;padding:10px 4px 5px;border-bottom:1px solid #b0bcd0" role="img" aria-label="Aperçu de consommation quotidienne estimée">'+
      rows.slice(0,400).map(x=>{
        const fraction=Math.max(2,Math.round(100*(Number(x.quantity)||0)/max));
        const label=safe(x.date+" : "+x.quantity+" "+proposal.unit+" ("+x.provenance+")");
        return '<div title="'+label+'" style="flex:1 0 4px;min-width:4px;height:'+fraction+
          '%;background:'+(x.provenance==="measured"?"#4d9f73":"#457bd2")+
          ';border-radius:3px 3px 0 0"></div>';
      }).join("")+'</div>'+
      '<div class="muted" style="display:flex;justify-content:space-between;margin-top:8px">'+
      '<span>Mesuré : vert</span><span>Estimé : bleu</span></div>';
  }
  async _approveReading() {
    if (this._readingBusy||!this._current||!this._readingSelected) return;
    const item=(this._historyPreview?.review_candidates||[]).find(
      x=>x.key===this._readingSelected
    );
    if (!item) return;
    const corrected=this._readingAction==="correct";
    if (corrected && this._readingReason.trim().length<8) {
      this._historyError="La correction exige un justificatif explicite (au moins 8 caractères).";
      this._render();return;
    }
    const description=this._readingAction==="accept"?"Conserver ce relevé":
      this._readingAction==="correct"?"Corriger/imputer ce relevé":
      this._readingAction==="reject"?"Écarter ce relevé du calcul":
      "Reporter l’examen (le relevé sera temporairement écarté du calcul)";
    if (!window.confirm(description+" ?\n\n"+
        item.fluid+" · "+item.meter_serial+" · "+item.source_date+
        "\nIndex source : "+item.index+
        "\n\nLes données brutes ne seront jamais modifiées.")) return;
    this._readingBusy=true;this._historyError="";this._render();
    try {
      const request={
        type:"trybatec/panel_reading_decision",entry_id:this._current.entry_id,
        reading_key:item.key,action:this._readingAction,confirm:true,
      };
      if (corrected) {
        request.mode=this._readingMode;
        request.date=this._readingDate;
        request.time=this._readingTime;
        request.reason=this._readingReason;
        if (this._readingMode==="accounting"&&this._readingOutside)
          request.out_of_period_confirmed=true;
      }
      const answer=await this._hass.callWS(request);
      this._historyPreview.review_candidates=answer.review_candidates;
      this._readingMessage="Décision enregistrée ; index source, Recorder et Énergie inchangés.";
      this._historyMessage=this._readingMessage;
      this._readingSelected="";
    } catch (_) {
      this._historyError="Décision refusée : vérifiez la date, le motif ou l’imputation hors période, puis actualisez l’historique.";
    } finally {this._readingBusy=false;this._render();}
  }
  _readingReview() {
    const list=this._historyPreview?.review_candidates||[];
    const item=list.find(x=>x.key===this._readingSelected);
    const explanation={
      sparse_interval:"Intervalle espacé (pas une erreur avérée)",
      index_zero:"Index nul à qualifier",
      index_decrease:"Baisse d’index à vérifier",
      conflicting_source_reading:"Relevés sources contradictoires",
    };
    return '<section class="card" style="margin-top:17px"><h3>Revue des relevés signalés</h3>'+
    '<p class="muted">Une correction de date réelle exige une preuve ; une imputation comptable ne modifie pas la date de mesure.</p>'+
    '<div class="split" style="margin-top:16px"><div class="scroll">'+
    (list.length?list.map(c=>
      '<div class="meter-row"><button type="button" data-reading-select="'+safe(c.key)+'" class="'+
      (this._readingSelected===c.key?"selected":"")+'">'+
      '<span class="meter-name">'+safe(c.fluid+" · "+c.meter_serial+" · "+c.index)+'</span>'+
      '<span class="meter-sub">'+safe(c.source_date)+'</span>'+
      '<span class="meter-sub">'+safe(c.reasons.map(r=>explanation[r]||r).join(" · "))+
      " · Décision : "+safe(c.decision)+'</span></button></div>').join(""):'<div class="empty">Aucun relevé à examiner. Lancez l’analyse historique.</div>')+
    '</div><div>'+
    (item?'<h3>Décision sur le relevé</h3>'+
      '<p class="muted">Index réel : '+safe(item.index)+' · '+safe(item.source_date)+'</p>'+
      '<div class="form-grid" style="margin-top:12px">'+
      '<div><label>Traitement</label><select data-reading-field="action">'+
      [["accept","Conserver"],["correct","Corriger ou imputer"],["reject","Écarter"],["postpone","Reporter"]].map(([v,t])=>
        '<option value="'+v+'" '+(this._readingAction===v?"selected":"")+'>'+t+'</option>').join("")+
      '</select></div>'+
      (this._readingAction==="correct"?
        '<div><label>Type</label><select data-reading-field="mode">'+
        '<option value="measurement" '+(this._readingMode==="measurement"?"selected":"")+'>Date réelle vérifiée</option>'+
        '<option value="accounting" '+(this._readingMode==="accounting"?"selected":"")+'>Imputation comptable</option></select></div>'+
        '<div><label>Date</label><input type="date" data-reading-field="date" value="'+safe(this._readingDate)+'"></div>'+
        '<div><label>Heure</label><input type="time" step="1" data-reading-field="time" value="'+safe(this._readingTime)+'"></div>'+
        '<div style="grid-column:1/-1"><label>Justification obligatoire</label><input type="text" data-reading-field="reason" maxlength="500" value="'+safe(this._readingReason)+'" placeholder="Préciser le justificatif"></div>'+
        (this._readingMode==="accounting"?
          '<label style="grid-column:1/-1"><input type="checkbox" data-reading-field="outside" '+(this._readingOutside?"checked":"")+
          '> Je confirme explicitement une imputation en dehors de la période source, si applicable.</label>':""):
        "")+
      '</div>'+
      '<div class="actions"><button type="button" class="primary" data-reading-approve '+
        (this._readingBusy?"disabled":"")+'>Confirmer la décision</button>'+
      (item.preceding_interval_key?
        '<button type="button" class="secondary" data-reading-smoothing>'+
        'Examiner et éventuellement lisser les jours précédents</button>':
        '<span class="muted">Aucun intervalle précédent vérifié dans cet aperçu.</span>')+
      '</div>':
      '<div class="empty">Sélectionnez un relevé pour le qualifier ou corriger son attribution.</div>')+
    '</div></div></section>';
  }
  _history() {
    const proposal=(this._historyPreview?.proposals?.intervals||[]).find(
      x=>x.interval_key===this._historySelected
    );
    const ready=proposal&&proposal.status==="linear_available_after_explicit_confirmation";
    const list=this._historyPreview?.proposals?.intervals||[];
    const blockers={
      blocked_source_conflict:"Conflit d’index à examiner",
      blocked_unverified_unit:"Unité non vérifiée",
      blocked_unreviewed_zero:"Index nul non qualifié",
      blocked_needs_explicit_review:"Bornes à vérifier",
      linear_available_after_explicit_confirmation:"Lissage envisageable après confirmation"
    };
    return this._heading("Historique & lissage",
      "Répartition linéaire contrôlée, sans modification des relevés bruts.")+
      '<section class="card"><div class="panel-title"><h3>Charger une période</h3>'+
      '<span class="pill audit">Aperçu en lecture seule</span></div>'+
      '<div class="form-grid">'+
      '<div><label for="hist-start">Depuis le</label><input id="hist-start" type="date" data-history-field="start_date" value="'+safe(this._historyStart)+'"></div>'+
      '<div><label for="hist-end">Jusqu’au</label><input id="hist-end" type="date" data-history-field="end_date" value="'+safe(this._historyEnd)+'"></div></div>'+
      '<div class="actions"><button type="button" class="primary" data-history-preview '+(this._historyBusy?"disabled":"")+
      '>Analyser les relevés</button><button class="secondary" type="button" data-openOptions>Ancienne IHM de révision</button></div>'+
      (this._historyError?'<div class="notice warning">'+safe(this._historyError)+'</div>':"")+
      (this._historyMessage?'<div class="notice">'+safe(this._historyMessage)+'</div>':"")+
      '</section><div class="split" style="margin-top:16px"><section class="card"><h3>Intervalles entre relevés</h3>'+
      '<p class="muted">L’analyse ne déduit jamais une origine manuelle ou automatique.</p>'+
      (list.length?'<div class="scroll">'+list.map(item=>'<div class="meter-row">'+
        '<button type="button" data-history-select="'+safe(item.interval_key)+'" class="'+
        (this._historySelected===item.interval_key?"selected":"")+'">'+
        '<span class="meter-name">'+safe(item.fluid+" · "+item.meter_serial)+'</span>'+
        '<span class="meter-sub">'+safe(item.start_date+" → "+item.end_date+" · "+(blockers[item.status]||item.status))+
        '</span></button></div>').join("")+'</div>':
      '<div class="empty">'+(this._historyPreview?"Aucun intervalle à signaler sur cette période.":"Analysez une période pour afficher les intervalles concernés.")+'</div>')+
      '</section><section class="card">'+
      (proposal?'<h3>Reconstituer l’intervalle sélectionné</h3>'+
      '<p class="muted">'+safe(proposal.lot+" · "+proposal.meter_serial+" · "+proposal.start_date+" → "+proposal.end_date)+'</p>'+
      '<div class="detail-grid">'+
      '<div><span class="smallhead">Consommation bornée</span><strong>'+
      safe(proposal.bounded_consumption===undefined?"Non déterminée":proposal.bounded_consumption+" "+proposal.unit)+'</strong></div>'+
      '<div><span class="smallhead">Index avant → après</span><strong>'+safe(proposal.source_start_index+" → "+proposal.source_end_index)+'</strong></div>'+
      '<div><span class="smallhead">Jours</span><strong>'+safe(proposal.days||"À déterminer")+'</strong></div>'+
      '<div><span class="smallhead">État</span><strong>'+safe(blockers[proposal.status]||proposal.status)+'</strong></div></div>'+
      (ready?'<h3>Aperçu après lissage linéaire</h3>'+this._historyDayBars(proposal)+this._historyComparison(proposal):
        '<div class="notice warning">Le lissage est bloqué tant que les index ou les unités nécessaires ne sont pas qualifiés. La vue existante permet de réviser les anomalies.</div>')+
      '<div class="form-grid" style="margin-top:16px">'+
      '<div><label for="h-mode">Décision</label><select id="h-mode" data-history-field="mode">'+
      '<option value="linear" '+(this._historyMode==="linear"?"selected":"")+'>Lisser le résiduel</option>'+
      '<option value="none" '+(this._historyMode==="none"?"selected":"")+'>Ne pas lisser</option></select></div>'+
      '<div><label for="h-reason">Motif déclaré</label><select id="h-reason" data-history-field="reason">'+
      '<option value="manual_periodic" '+(this._historyReason==="manual_periodic"?"selected":"")+'>Relève périodique</option>'+
      '<option value="telemetry_failure" '+(this._historyReason==="telemetry_failure"?"selected":"")+'>Panne de télérelève</option>'+
      '<option value="other" '+(this._historyReason==="other"?"selected":"")+'>Autre motif</option></select></div></div>'+
      (proposal.choice?'<p class="muted" style="margin-top:13px">Décision actuelle : '+
        safe(proposal.choice.mode)+" · "+safe(proposal.choice.reason)+'</p>':"")+
      '<div class="actions"><button type="button" class="primary" data-history-approve '+(
        this._historyBusy||(this._historyMode==="linear"&&!ready)?"disabled":"")+
      '>Confirmer la décision</button></div>':
      '<h3>Avant / après</h3><div class="empty">Sélectionnez un intervalle pour comparer la période et éventuellement enregistrer une décision de lissage.</div>')+
      '</section></div>'+this._readingReview()+this._originView()+
      '<div class="notice"><strong>Source préservée.</strong> Les décisions servent à préparer les séries historisées. Elles ne créent aucune mesure réelle, ne lancent aucun import Recorder et n’activent aucune source dans Énergie.</div>';
  }
  _tariffs() {
    const a=this._current, f=this._tariffInput;
    const rows=Object.entries(a.tariffs).sort((a,b)=>Number(b[0])-Number(a[0])).flatMap(([year,fluids])=>
      Object.entries(fluids).map(([fluid,t])=>'<tr><td>'+safe(year)+'</td><td>'+safe(FLUID[fluid]||fluid)+
      '</td><td>'+safe(t.rate)+' '+safe(fluid==="CET"?"EUR/kWh":"EUR/m³")+'</td>'+
      '<td>'+safe(t.status==="approved"?"Approuvé":"Provisoire")+'</td></tr>'));
    const overrides=Object.entries(a.meter_tariffs||{}).sort((a,b)=>Number(b[0])-Number(a[0])).flatMap(([year,values])=>
      Object.entries(values).map(([key,t])=>{
        const m=a.meters.find(m=>m.physical_key===key);
        return '<tr><td>'+safe(year)+'</td><td>'+safe(m?(FLUID[m.fluid]+" · "+m.serial):"Compteur non identifié")+
          '</td><td>'+safe(t.rate)+' '+safe(m&&m.fluid==="CET"?"EUR/kWh":"EUR/m³")+'</td>'+
          '<td>'+safe(t.status==="approved"?"Approuvé":"Provisoire")+'</td></tr>';
      }));
    const yearOptions=Array.from({length:111},(_,i)=>2000+i).filter(y=>y<=2100).reverse().map(year=>
      '<option value="'+year+'" '+(Number(f.year)===year?"selected":"")+'>'+year+'</option>').join("");
    const current=a.meters.filter(m=>m.fluid===f.fluid);
    const meterOptions='<option value="">Tarif commun du fluide</option>'+
      current.map(m=>'<option value="'+safe(m.physical_key)+'" '+(f.physical_key===m.physical_key?"selected":"")+'>'+
      safe(FLUID[m.fluid]+" · "+m.serial+" · "+m.lot+(m.status==="depose"?" (déposé)":""))+'</option>').join("");
    return this._heading("Tarifs annuels","Montants en EUR par exercice, fluide et, facultativement, compteur physique.")+
      '<div class="card"><h3>Saisir ou modifier un tarif</h3>'+
      '<p class="muted">Choisissez l’année, le fluide et éventuellement un compteur. Les tarifs déjà saisis sont conservés.</p>'+
      (this._message?'<div class="notice">'+safe(this._message)+'</div>':"")+
      (this._error?'<div class="notice warning">'+safe(this._error)+'</div>':"")+
      '<form data-tariff-form><div class="form-grid" style="margin-top:16px">'+
      '<div><label for="tariff-year">Exercice annuel</label><select id="tariff-year" data-tariff-field="year">'+yearOptions+'</select></div>'+
      '<div><label for="tariff-fluid">Fluide</label><select id="tariff-fluid" data-tariff-field="fluid">'+
      Object.entries(FLUID).filter(([key])=>key!=="unknown").map(([key,label])=>
        '<option value="'+key+'" '+(f.fluid===key?"selected":"")+'>'+safe(label)+'</option>').join("")+'</select></div>'+
      '<div><label for="tariff-scope">Portée</label><select id="tariff-scope" data-tariff-field="physical_key">'+meterOptions+'</select></div>'+
      '<div><label for="tariff-rate">Tarif ('+safe(f.fluid==="CET"?"EUR/kWh":"EUR/m³")+')</label>'+
      '<input id="tariff-rate" type="number" min="0" max="1000000" step="any" value="'+safe(f.rate)+
      '" data-tariff-field="rate" placeholder="0,000000" required></div>'+
      '<div><label for="tariff-status">État</label><select id="tariff-status" data-tariff-field="status">'+
      '<option value="provisional" '+(f.status==="provisional"?"selected":"")+'>Provisoire</option>'+
      '<option value="approved" '+(f.status==="approved"?"selected":"")+'>Approuvé</option></select></div>'+
      '</div><div class="actions"><button class="primary" type="submit" '+(this._tariffBusy?"disabled":"")+'>Enregistrer ce tarif</button>'+
      '<button class="secondary" type="button" data-tariff-delete '+(!this._existingTariff()||this._tariffBusy?"disabled":"")+
      '>Retirer ce tarif</button></div></form>'+
      '<div class="notice">L’état « Approuvé » qualifie le tarif saisi, pas une facture validée. Modifier un tarif ne démarre aucun import Recorder et ne modifie pas Énergie.</div></div>'+
      '<div class="grid-two" style="margin-top:16px"><section class="card"><h3>Tarifs communs</h3>'+
      (rows.length?'<table><thead><tr><th>Année</th><th>Fluide</th><th>Tarif</th><th>État</th></tr></thead><tbody>'+rows.join("")+'</tbody></table>':
      '<div class="empty">Aucun tarif commun enregistré.</div>')+'</section>'+
      '<section class="card"><h3>Tarifs spécifiques aux compteurs</h3>'+
      (overrides.length?'<table><thead><tr><th>Année</th><th>Compteur</th><th>Tarif</th><th>État</th></tr></thead><tbody>'+overrides.join("")+'</tbody></table>':
      '<div class="empty">Aucune dérogation propre à un compteur. Le tarif commun reste applicable lorsqu’il existe pour l’exercice.</div>')+
      '</section></div>';
  }
  async _callVersionService(service, payload) {
    const result=await this._hass.callWS({
      type:"call_service",domain:"trybatec",service,
      service_data:{entry_id:this._current.entry_id,...payload},
      return_response:true
    });
    if (!result || !result.response) throw new Error("Missing verified service response");
    return result.response;
  }
  _versionDates() {
    return {start_date:this._historyStart,end_date:this._historyEnd,
      include_cold_water:true,include_hot_water:true,
      include_heating:this._versionHeating};
  }
  async _previewRecorderVersion() {
    if (!this._current||this._versionBusy) return;
    this._versionBusy=true;this._versionError="";this._versionMessage="";
    this._versionPlan=null;this._versionVerify=null;this._render();
    try {
      this._versionPlan=await this._callVersionService("preview_b15",this._versionDates());
      this._versionMessage="Aperçu Recorder obtenu. Aucun import n’a commencé.";
    } catch (_) {
      this._versionError="Plan impossible : vérifiez unités, zéros et décisions de lissage, puis recommencez l’aperçu.";
    } finally {this._versionBusy=false;this._render();}
  }
  async _importRecorderVersion() {
    const plan=this._versionPlan;
    if (!plan?.plan_fingerprint||this._versionBusy||!this._versionImportBackup) return;
    if (!window.confirm(
      "Importer les séries historiques dans Recorder ?"+
      "\\n\\nSauvegarde confirmée : "+String(this._versionImportBackup)+
      "\\nNombre de séries : "+String(plan.series?.length||0)+
      "\\n\\nCette action écrit des statistiques dans Home Assistant. La vérification de persistance est une étape distincte."
    )) return;
    this._versionBusy=true;this._versionError="";this._render();
    try {
      const result=await this._callVersionService("import_b15",{
        ...this._versionDates(),
        plan_fingerprint:plan.plan_fingerprint,
        confirm:true,backup_confirmed:true,
        confirm_revision:this._versionRevision,
        retry_pending:this._versionRetry
      });
      this._versionPlan=null;
      this._versionMessage="Import demandé ("+safe(result.status||"en cours")+
        "). La persistance Recorder n’est pas attestée avant vérification.";
      this._data=await this._hass.callWS({type:"trybatec/panel_snapshot"});
    } catch (_) {
      this._versionError="Import refusé : aperçu périmé, sauvegarde manquante ou série déjà présente. Aucune réussite n’est présumée.";
    } finally {this._versionBusy=false;this._render();}
  }
  async _verifyRecorderVersion() {
    if (!this._current||this._versionBusy) return;
    this._versionBusy=true;this._versionError="";this._versionVerify=null;this._render();
    try {
      this._versionVerify=await this._callVersionService("verify_b15",{});
      this._data=await this._hass.callWS({type:"trybatec/panel_snapshot"});
      this._versionMessage="Vérification Recorder exécutée. Consultez les états détaillés ci-dessous.";
    } catch (_) {
      this._versionError="Vérification Recorder impossible. N’activez aucune nouvelle série dans Énergie.";
    } finally {this._versionBusy=false;this._render();}
  }
  async _previewRecorderEnergy() {
    if (!this._current||this._versionBusy||!this._versionOld||!this._versionNew) return;
    this._versionBusy=true;this._versionError="";this._versionEnergyPlan=null;this._render();
    try {
      this._versionEnergyPlan=await this._callVersionService("preview_b15_energy",{
        old_statistic_id:this._versionOld,
        new_statistic_id:this._versionNew
      });
      this._versionMessage="Aperçu Énergie compatible, sans écriture.";
    } catch (_) {
      this._versionError="Basculement refusé : série non vérifiée, mauvaise unité, référence absente ou double comptage possible.";
    } finally {this._versionBusy=false;this._render();}
  }
  async _activateRecorderEnergy() {
    const p=this._versionEnergyPlan;
    if (!p||this._versionBusy||!this._versionEnergyBackup) return;
    if (p.old_statistic_id!==this._versionOld ||
        p.new_statistic_id!==this._versionNew) return;
    if (!window.confirm(
      "Confirmer le remplacement de la série dans Énergie ?"+
      "\\n\\nAncienne : "+p.old_statistic_id+
      "\\nNouvelle : "+p.new_statistic_id+
      "\\n\\nUne sauvegarde est obligatoire. Les préférences seront vérifiées après écriture."
    )) return;
    this._versionBusy=true;this._versionError="";this._render();
    try {
      const result=await this._callVersionService("activate_b15_energy",{
        old_statistic_id:p.old_statistic_id,
        new_statistic_id:p.new_statistic_id,
        before_fingerprint:p.before_fingerprint,
        confirm:true,backup_confirmed:true,
        confirm_rollback:this._versionRollback
      });
      this._versionEnergyPlan=null;
      this._data=await this._hass.callWS({type:"trybatec/panel_snapshot"});
      this._versionMessage="Activation traitée : "+safe(result.status||"contrôle terminé")+
        ". Vérifiez également les statistiques affichées dans Énergie.";
    } catch (_) {
      this._versionError="Activation refusée ou contrôle après écriture échoué. Consultez les diagnostics ; aucun succès n’est présumé.";
    } finally {this._versionBusy=false;this._render();}
  }
  _recorderVersionWorkflow() {
    const ledger=this._current.ledger||{series:[],status:"missing",pending:0};
    const opts=(ledger.series||[]).flatMap(row=>(row.versions||[]).filter(v=>
      ["verified","archived"].includes(v.state)).map(v=>
        '<option value="'+safe(v.statistic_id)+'" '+(this._versionNew===v.statistic_id?"selected":"")+'>'+
        safe(row.logical_id+" · V"+v.number+" · "+v.state)+'</option>'
      )).join("");
    const sourceOpts=(this._data.energy.sources||[]).filter(x=>
      typeof x.statistic_id==="string"&&x.statistic_id.startsWith("trybatec:")
    ).map(x=>'<option value="'+safe(x.statistic_id)+'" '+(this._versionOld===x.statistic_id?"selected":"")+'>'+
      safe(x.type+" · "+x.statistic_id)+'</option>').join("");
    const plan=this._versionPlan;
    const rows=plan?.series||[];
    return '<section class="card" style="margin-top:16px"><h3>Préparer une version historique Recorder</h3>'+
      '<p class="muted">Aperçu, import, contrôle de persistance et basculement Énergie sont quatre étapes distinctes. Aucune n’est lancée automatiquement.</p>'+
      '<div class="form-grid" style="margin-top:14px">'+
      '<div><label for="version-start">Début</label><input id="version-start" data-version-field="start" type="date" value="'+safe(this._historyStart)+'"></div>'+
      '<div><label for="version-end">Fin</label><input id="version-end" data-version-field="end" type="date" value="'+safe(this._historyEnd)+'"></div>'+
      '<div><label><input data-version-field="heating" type="checkbox" '+(this._versionHeating?"checked":"")+'> Inclure le chauffage</label></div>'+
      '</div><div class="actions"><button type="button" class="secondary" data-version-preview '+(this._versionBusy?"disabled":"")+'>1. Prévisualiser Recorder</button></div>'+
      (plan?'<div class="notice"><strong>Plan non importé</strong> · '+safe(rows.length)+
        ' séries, '+safe(plan.physical_meters?.length||"?")+' compteurs, période '+
        safe(plan.start_date)+" → "+safe(plan.end_date)+
        '. Aucun historique n’a encore été écrit.</div>'+
        '<div class="scroll">'+rows.slice(0,20).map(x=>'<div class="line">'+
        safe(x.fluid+" · "+x.variant+" · "+x.rows+" points · "+x.unit)+'</div>').join("")+'</div>':"")+
      '<div class="actions"><label><input type="checkbox" data-version-field="importBackup" '+
      (this._versionImportBackup?"checked":"")+'> Une sauvegarde récupérable de HA/Recorder existe</label>'+
      '<label><input type="checkbox" data-version-field="revision" '+(this._versionRevision?"checked":"")+'> J’approuve une nouvelle version</label>'+
      '<label><input type="checkbox" data-version-field="retry" '+(this._versionRetry?"checked":"")+'> Reprendre une importation en attente</label></div>'+
      '<div class="actions"><button class="primary" type="button" data-version-import '+
      (!plan||!this._versionImportBackup||this._versionBusy?"disabled":"")+'>2. Confirmer l’import Recorder</button>'+
      '<button class="secondary" type="button" data-version-verify '+(this._versionBusy?"disabled":"")+'>3. Vérifier la persistance Recorder</button></div>'+
      (this._versionVerify?'<pre class="mono" style="white-space:pre-wrap;max-height:240px;overflow:auto">'+safe(JSON.stringify(this._versionVerify,null,2))+'</pre>':"")+
      '</section><section class="card" style="margin-top:16px"><h3>Choisir une version vérifiée pour Énergie</h3>'+
      '<p class="muted">Sélectionnez une ancienne série Trybatec actuellement affichée, puis une version Recorder vérifiée. Un ancien capteur physique reste géré dans le parcours séparé d’audit.</p>'+
      '<div class="grid-two" style="margin-top:12px">'+
      '<div><label for="version-old">Série actuellement sélectionnée</label><select id="version-old" data-version-field="old">'+
      '<option value="">Sélectionner une source Trybatec versionnée</option>'+sourceOpts+'</select></div>'+
      '<div><label for="version-new">Nouvelle version Recorder</label><select id="version-new" data-version-field="new">'+
      '<option value="">Sélectionner une version vérifiée</option>'+opts+'</select></div></div>'+
      '<div class="actions"><button type="button" class="secondary" data-version-energy-preview '+
      (this._versionBusy||!this._versionOld||!this._versionNew?"disabled":"")+'>4. Prévisualiser le basculement</button></div>'+
      (this._versionEnergyPlan?'<div class="notice">Prévisualisation compatible : '+
      safe(this._versionEnergyPlan.old_statistic_id)+" → "+safe(this._versionEnergyPlan.new_statistic_id)+
      '. Une seule source sera remplacée.</div>':"")+
      '<div class="actions"><label><input type="checkbox" data-version-field="energyBackup" '+
      (this._versionEnergyBackup?"checked":"")+'> Sauvegarde Énergie confirmée</label>'+
      '<label><input type="checkbox" data-version-field="rollback" '+
      (this._versionRollback?"checked":"")+'> J’approuve le retour vers une version archivée</label></div>'+
      '<div class="actions"><button type="button" class="primary" data-version-energy-apply '+
      (!this._versionEnergyPlan||!this._versionEnergyBackup||this._versionBusy?"disabled":"")+
      '>5. Confirmer le basculement Énergie</button></div></section>'+
      (this._versionError?'<div class="notice warning">'+safe(this._versionError)+'</div>':"")+
      (this._versionMessage?'<div class="notice">'+safe(this._versionMessage)+'</div>':"");
  }
  _energy() {
    const data=this._data.energy;
    const a=this._current;
    const rows=a.ledger.series||[];
    return this._heading("Énergie & versions","Références configurées et versions historiques vérifiables.")+
      '<div class="grid-two"><section class="card"><h3>Sources Trybatec dans Énergie</h3>'+
      (data.sources.length?data.sources.map(x=>'<div class="line"><strong>'+safe(x.type)+'</strong> · <span class="mono">'+safe(x.statistic_id)+'</span></div>').join(""):
        '<div class="empty">Aucune source Trybatec identifiée dans la configuration Énergie actuellement disponible.</div>')+
      '<div class="actions"><button class="secondary" type="button" data-openEnergy>Ouvrir Énergie</button></div></section>'+
      '<section class="card"><h3>Séries historiques versionnées</h3><p class="muted">Registre Recorder b15 : '+safe(a.ledger.status)+
      ', imports à vérifier : '+safe(a.ledger.pending)+'</p>'+
      (rows.length?rows.map(row=>'<div class="line"><span class="mono">'+safe(row.logical_id)+'</span>'+
       '<div class="muted">'+safe((row.versions||[]).length)+' version(s) · '+safe(row.unit||"Unité inconnue")+'</div></div>').join(""):
       '<div class="empty">Aucune série versionnée enregistrée. Une importation historique ne sera pas démarrée automatiquement.</div>')+
      '</section></div>'+this._recorderVersionWorkflow()+'<div class="notice">Une seule série consolidée par logement et fluide doit être active dans Énergie. Les migrations et basculements exigent un aperçu, une sauvegarde et une confirmation distincte.</div>';
  }
  _diagnostics() {
    const a=this._current;
    return this._heading("Diagnostics","Lecture des entités, disponibilités et état des données.")+
      '<div class="grid-two"><section class="card"><h3>Statut</h3><div class="line">Synchronisation actuelle : <strong>'+
      (a.data_loaded?"Données chargées":"En attente de données")+'</strong></div>'+
      '<div class="line">Compteurs physiques connus : '+this._meters().length+'</div>'+
      '<div class="line">Inventaire archivé : '+a.archived_inventory_count+'</div>'+
      '<div class="line">Entités Trybatec recensées : '+a.entities.length+'</div>'+
      a.warnings.map(x=>'<div class="notice warning">'+safe(x)+'</div>').join("")+
      '<div class="actions"><button class="secondary" type="button" data-refresh>Actualiser</button></div></section>'+
      '<section class="card"><h3>Audit des entités techniques</h3>'+
      '<p class="muted">Une entité indisponible n’est pas nécessairement obsolète : elle peut avoir des historiques Recorder et des références actives.</p>'+
      '<div class="scroll">'+(a.entities.length?a.entities.map(e=>
      '<div class="entity"><span class="mono">'+safe(e.entity_id)+'</span>'+
      '<div class="muted">État : '+safe(e.state)+' · Unité : '+safe(e.unit||"N/A")+
      ' · Nettoyage : interdit sans audit</div></div>').join(""):'<div class="empty">Aucune entité recensée.</div>')+
      '</div></section></div>';
  }
  async _saveSettings() {
    if (!this._current || this._settingsBusy) return;
    const settings={...this._current.settings,...this._settingsInput};
    const poll=Number(settings.poll_minutes);
    const sparse=Number(settings.sparse_hours);
    const zeros=Number(settings.zero_review_days);
    if (!Number.isInteger(poll)||poll<60||poll>10080 ||
        !Number.isInteger(sparse)||sparse<1||sparse>87600 ||
        !Number.isInteger(zeros)||zeros<0||zeros>36500) {
      this._settingsError="Indiquez des nombres entiers dans les limites autorisées.";
      this._render();return;
    }
    const message="Confirmer les réglages Trybatec ?"+
      "\\n\\nCertains réglages peuvent recharger l’intégration, mais ne modifient ni Recorder ni Énergie.";
    if (!window.confirm(message)) return;
    this._settingsBusy=true;this._settingsError="";this._render();
    try {
      await this._hass.callWS({
        type:"trybatec/panel_settings_save",
        entry_id:this._current.entry_id,
        poll_minutes:poll,sparse_hours:sparse,
        zero_review_days:zeros,log_level:settings.log_level,
        expected_fingerprint:this._current.tariff_fingerprint,
        confirm:true
      });
      this._data=await this._hass.callWS({type:"trybatec/panel_snapshot"});
      this._settingsInput=null;
      this._settingsMessage="Réglages enregistrés dans la configuration Home Assistant partagée.";
    } catch (_) {
      this._settingsError="Modification refusée ou intégration en cours de rechargement. Actualisez et vérifiez les valeurs.";
    } finally {
      this._settingsBusy=false;this._render();
    }
  }
  _settings() {
    const settings={...this._current.settings,...this._settingsInput};
    const field=(key,label,min,max,description)=>
      '<div><label for="settings-'+key+'">'+label+'</label>'+
      '<input id="settings-'+key+'" data-settings-field="'+key+'" type="number" min="'+min+'" max="'+max+
      '" step="1" value="'+safe(settings[key])+'">'+
      '<div class="muted">'+description+'</div></div>';
    return this._heading("Réglages","Modifiez les paramètres existants sans supprimer l’ancienne interface.")+
      '<section class="card"><h3>Synchronisation et contrôle des relevés</h3>'+
      '<p class="muted">Ces valeurs sont partagées avec Options Trybatec et conservées lors des mises à jour.</p>'+
      '<div class="form-grid" style="margin-top:18px">'+
      field("poll_minutes","Synchronisation (minutes)",60,10080,
        "De 60 minutes à 7 jours. Une modification peut recharger l’intégration.")+
      field("sparse_hours","Intervalle à signaler (heures)",1,87600,
        "Par défaut : 27 h. Un intervalle strictement supérieur est considéré comme espacé.")+
      field("zero_review_days","Index nuls consécutifs (jours)",0,36500,
        "0 désactive la sollicitation ; 1 signale dès le premier jour avec un index nul.")+
      '<div><label for="settings-log">Journalisation</label><select id="settings-log" data-settings-field="log_level">'+
      ["ERROR","WARNING","INFO","DEBUG"].map(level=>
        '<option value="'+level+'" '+(settings.log_level===level?"selected":"")+'>'+level+'</option>'
      ).join("")+'</select><div class="muted">DEBUG peut produire davantage de journaux.</div></div>'+
      '</div>'+
      (this._settingsError?'<div class="notice warning">'+safe(this._settingsError)+'</div>':"")+
      (this._settingsMessage?'<div class="notice">'+safe(this._settingsMessage)+'</div>':"")+
      '<div class="actions"><button class="primary" type="button" data-settings-save '+(this._settingsBusy?"disabled":"")+'>Enregistrer les réglages</button>'+
      '<button class="secondary" type="button" data-settings-reset>Annuler les modifications</button></div>'+
      '<div class="notice">Aucune modification de relevé, aucune écriture Recorder ni changement du tableau Énergie. Les réglages existants restent accessibles dans le menu natif.</div>'+
      '</section>'+
      '<section class="card" style="margin-top:16px"><h3>Autres options Trybatec</h3>'+
      '<p>Les unités, les options de diagnostic et les parcours historiques sont conservés dans l’interface Home Assistant actuelle.</p>'+
      '<div class="actions"><button class="secondary" type="button" data-openOptions>Ouvrir Options Trybatec</button></div></section>';
  }
  _content() {
    if (this._loading) return '<div class="card empty">Chargement des données Trybatec…</div>';
    if (this._error) return '<div class="card"><h2>Chargement impossible</h2><p>'+safe(this._error)+'</p><div class="actions"><button data-refresh class="primary">Réessayer</button></div></div>';
    if (!this._data || !this._data.accounts || !this._data.accounts.length)
      return '<div class="card empty">Aucune entrée Trybatec actuellement chargée. Configurez l’intégration dans Paramètres → Appareils et services.</div>';
    const tabs={overview:()=>this._overview(),meters:()=>this._metersPage(),history:()=>this._history(),
      tariffs:()=>this._tariffs(),energy:()=>this._energy(),diagnostics:()=>this._diagnostics(),settings:()=>this._settings()};
    const selector=this._data.accounts.length>1?'<div class="actions">'+this._data.accounts.map((a,i)=>
      '<button type="button" class="secondary" data-account="'+i+'">'+safe(a.title)+'</button>').join("")+'</div>':"";
    return selector+tabs[this._tab]();
  }
  _render() {
    this.shadowRoot.innerHTML='<style>'+style+'</style><div class="wrap">'+this._header()+
      '<div class="shell">'+this._nav()+'<main class="main" id="main">'+this._content()+'</main></div>'+
      '<footer class="footer">Trybatec — Interface expérimentale · Aucune suppression ni écriture Recorder ou Énergie automatique.</footer></div>';
  }
}
if (!customElements.get("trybatec-panel")) customElements.define("trybatec-panel", TrybatecPanel);
