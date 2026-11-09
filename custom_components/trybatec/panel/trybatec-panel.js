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
    if (btn.dataset.meter !== undefined) {this._meter=Number(btn.dataset.meter);this._render();return;}
    if (btn.dataset.account !== undefined) {this._account=Number(btn.dataset.account);this._meter=0;this._render();return;}
    if (btn.dataset.refresh !== undefined) {this._fetch();return;}
    if (btn.dataset.openOptions !== undefined) {window.location.assign("/config/integrations/integration/trybatec");return;}
    if (btn.dataset.openActions !== undefined) {window.location.assign("/developer-tools/action");return;}
    if (btn.dataset.openEnergy !== undefined) {window.location.assign("/energy");return;}
    if (btn.dataset.openMeter !== undefined) {this._tab="meters";this._meter=Number(btn.dataset.openMeter);this._render();return;}
    if (btn.dataset.tariffDelete !== undefined) {this._sendTariff(true);return;}
    if (btn.dataset.historyPreview !== undefined) {this._fetchHistory();return;}
    if (btn.dataset.historySelect !== undefined) {
      this._historySelected=btn.dataset.historySelect;this._render();return;
    }
    if (btn.dataset.historyApprove !== undefined) {this._approveHistory();return;}
  }
  _change(event) {
    if (event.target.dataset.query !== undefined) {
      this._query=event.target.value.trim().toLowerCase();this._render();return;
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
    return '<header class="heading"><div class="mark"><ha-icon icon="mdi:water-thermometer"></ha-icon></div>' +
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
      '<div><span class="smallhead">Dernière observation</span><strong>'+safe(m.last_observed_at||"Non vérifiée")+'</strong></div>'+
      '<div><span class="smallhead">Statut de l’unité</span><strong>'+safe(m.unit_verified?"Vérifiée":"À vérifier")+'</strong></div>'+
      '</div><h3>Relations techniques Home Assistant</h3>'+
      '<p class="muted">Les identités techniques ne doivent pas être supprimées tant que leurs références sont inconnues.</p>'+
      (related.length?related.map(e=>'<div class="entity"><span class="mono">'+safe(e.entity_id)+'</span> '+
      '<span class="pill '+(e.state==="unavailable"?"audit":"on")+'">'+safe(e.state)+'</span></div>').join(""):
      '<div class="empty">Aucune association vérifiée par identifiant technique. Consultez l’audit des entités.</div>')+
      '<div class="actions"><button type="button" class="secondary" data-tab="history">Historique & lissage</button>'+
      '<button type="button" class="secondary" data-tab="diagnostics">Auditer les identifiants</button></div></div>';
  }
  _metersPage() {
    const meters=this._meters();
    const indexed=meters.map((m,i)=>({m,i})).filter(x=>!this._query||[
      x.m.serial,x.m.lot,FLUID[x.m.fluid],x.m.status].some(v=>String(v||"").toLowerCase().includes(this._query)));
    return this._heading("Compteurs","Inventaire physique : en service, déposés, ou statut non confirmé.")+
      '<div class="split"><section class="card"><input class="search" data-query placeholder="Rechercher un compteur (numéro, lot, fluide…)" value="'+safe(this._query)+'" aria-label="Rechercher un compteur">'+
      '<div class="scroll">'+indexed.map(x=>this._meterRow(x.m,x.i,"detail")).join("")+'</div>'+
      (!indexed.length?'<div class="empty">Aucun compteur correspondant. L’inventaire historique peut nécessiter une prévisualisation préalable.</div>':"")+
      '</section>'+this._meterDetail(meters[this._meter])+'</div>';
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
      (ready?'<h3>Aperçu après lissage linéaire</h3>'+this._historyDayBars(proposal):
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
      '</section></div><div class="notice"><strong>Source préservée.</strong> Les décisions servent à préparer les séries historisées. Elles ne créent aucune mesure réelle, ne lancent aucun import Recorder et n’activent aucune source dans Énergie.</div>';
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
      '</section></div><div class="notice">Une seule série consolidée par logement et fluide doit être active dans Énergie. Les migrations et basculements exigent un aperçu, une sauvegarde et une confirmation distincte.</div>';
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
  _settings() {
    return this._heading("Réglages","Conservation de tous les écrans et options existants.")+
      '<div class="card"><h3>Configuration Trybatec actuelle</h3>'+
      '<p>Les réglages, diagnostics, unités, révision des relevés et lissage des intervalles restent accessibles dans le parcours Home Assistant d’origine.</p>'+
      '<div class="actions"><button class="primary" type="button" data-openOptions>Ouvrir Options Trybatec</button></div>'+
      '<div class="notice">Le nouveau panneau s’ajoute aux écrans actuels. Il ne modifie, ne supprime et ne déplace aucun parcours existant.</div></div>';
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
