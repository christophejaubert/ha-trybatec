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
const FLUID_ICON = {EF:"mdi:water", ECS:"mdi:water-thermometer", CET:"mdi:fire"};
const FLUID_CLASS = {EF:"fluid-ef", ECS:"fluid-ecs", CET:"fluid-cet"};

// Safe, read-only presentation of prerequisites visible in the panel snapshot.
// This is NOT an Energy API readiness check and must not enable bulk writes.
function trybatecEnergySetupGuidance(account, energy) {
  const a=account||{}, meters=Array.isArray(a.meters)?a.meters:[];
  const active=meters.filter(m=>m.status==="en_service");
  const retired=meters.filter(m=>m.status==="depose");
  const ledger=a.ledger||{}, reasons=[];
  const add=(code,level,tab,fr,en,physical_key=null)=>reasons.push({code,level,tab,fr,en,physical_key});
  if (energy?.status==="unconfigured")
    add("energy_initial_setup","required","overview",
      "Initialiser la configuration du tableau Énergie.",
      "Complete the initial Energy dashboard setup.");
  if (!active.length)
    add("active_meter_inventory","unverified","meters",
      "Aucun compteur en service vérifiable dans cet aperçu : contrôler l’inventaire.",
      "No active meter verified in this view: review the meter inventory.");
  else {
    const units=active.filter(m=>m.unit_verified!==true).length;
    const missing=active.filter(m=>m.last_index===null||m.last_index===undefined).length;
    if (units) add("meter_units","required","meters",
      units+" compteur(s) en service avec une unité non vérifiée.",
      units+" active meter(s) with an unverified unit.",
      units===1?active.find(m=>m.unit_verified!==true)?.physical_key:null);
    if (missing) add("meter_indexes","required","meters",
      missing+" compteur(s) en service sans dernier index exploitable dans cet aperçu.",
      missing+" active meter(s) without a usable latest index in this view.",
      missing===1?active.find(m=>m.last_index===null||m.last_index===undefined)?.physical_key:null);
  }
  if (Number(ledger.pending)>0)
    add("recorder_pending","required","energy",
      "Des imports Recorder restent en attente de vérification.",
      "Recorder imports are pending verification.");
  // The read-only ledger is not independent proof of physical-meter continuity.
  // Even a matching, "verified" consolidated revision cannot authorize bulk Energy insertion.
  if (retired.length)
    add("retired_history","unverified","history",
      "La continuité historique de "+retired.length+" compteur(s) déposé(s) n’est pas démontrée par cet aperçu.",
      "Historical continuity for "+retired.length+" retired meter(s) is not proven by this view.",
      retired.length===1?retired[0].physical_key:null);
  const hasSources=Array.isArray(energy?.sources)&&energy.sources.length>0;
  // FR/EN: unknown/missing status is not proof of missing implementation.
  // The snapshot backend currently exposes only not_loaded/unconfigured/available.
  const energyState=energy?.status;
  const mode=!["not_loaded","unconfigured","available"].includes(energyState)?"status_unknown":
    energyState==="not_loaded"?"technical_unavailable":
    reasons.some(r=>r.level==="required")?"configuration_incomplete":
    reasons.length?"verification_needed":
    hasSources?"coverage_unverified":"not_implemented";
  return {
    mode, reasons, hasSources,
    optionalTariffsMissing:
      !Object.keys(a.tariffs||{}).length&&!Object.keys(a.meter_tariffs||{}).length,
  };
}

/* Scoped annual tariffs: observed years per account/housing + individually
 * stored common and physical-meter tariff years. No synthetic readings.
 */
function trybatecTariffYears(account, currentYear) {
  const allowable = year => Number.isInteger(year) && year >= 2000 && year <= 2100;
  const years = new Set();
  const observed = [];
  for (const meter of (account?.meters || [])) {
    for (const date of [meter.first_observed_at, meter.last_source_observed_at]) {
      if (typeof date !== "string") continue;
      const m = /^([0-9]{4})-[0-9]{2}-[0-9]{2}/.exec(date);
      if (m && allowable(Number(m[1]))) observed.push(Number(m[1]));
    }
  }
  const fallback = observed.length === 0;
  const today = allowable(currentYear) ? currentYear : new Date().getFullYear();
  const start = fallback ? today - 1 : Math.min(...observed) - 1;
  const end = fallback ? today + 1 : Math.max(...observed) + 1;
  for (let year = Math.max(2000,start); year <= Math.min(2100,end); year++) years.add(year);
  for (const source of [account?.tariffs, account?.meter_tariffs]) {
    for (const key of Object.keys(source || {})) {
      if (!/^[0-9]{4}$/.test(key)) continue;
      const year=Number(key);
      if (allowable(year)) years.add(year);
    }
  }
  return {years:[...years].sort((a,b)=>b-a), fallback};
}

/** Resolve only the tariff saved for the exact exercise, fluid and physical meter. */
function trybatecSavedEffectiveTariff(account, year, fluid, physicalKey="") {
  const y=String(year);
  if (physicalKey) {
    const meter=(account?.meters||[]).find(m=>m.physical_key===physicalKey);
    if (!meter || meter.fluid!==fluid) return null;
  }
  const specific=physicalKey ? account?.meter_tariffs?.[y]?.[physicalKey] : null;
  const common=account?.tariffs?.[y]?.[fluid];
  const record=specific ?? common;
  if (!record) return null;
  return {rate:record.rate,status:record.status,
    origin:specific ? "meter_override" : "fluid_default", source_year:Number(y)};
}

/** Merge dated historical supplier observations by exact physical meter key only. */
function trybatecMergeHistoricalObservationDates(account, coverage) {
  if (!account || coverage?.status !== "complete" || !Array.isArray(coverage.meters))
    throw new Error("Verified historical coverage is required");
  const bounds=new Map();
  for (const item of coverage.meters) {
    if (typeof item?.physical_key==="string" && item.physical_key.length===24)
      bounds.set(item.physical_key,item);
  }
  const pick=(existing,incoming,earliest) => {
    if (typeof incoming!=="string" || !Number.isFinite(Date.parse(incoming))) return existing;
    if (typeof existing!=="string" || !Number.isFinite(Date.parse(existing))) return incoming;
    return (earliest ? Date.parse(incoming)<Date.parse(existing) :
      Date.parse(incoming)>Date.parse(existing)) ? incoming : existing;
  };
  for (const meter of (account.meters||[])) {
    const item=bounds.get(meter.physical_key);
    if (!item) continue;
    meter.first_observed_at=pick(meter.first_observed_at,item.first_observed_at,true);
    meter.last_source_observed_at=pick(meter.last_source_observed_at,item.last_source_observed_at,false);
    if (meter.status==="depose" && typeof item.last_source_index_raw==="number" &&
        Number.isFinite(item.last_source_index_raw)) {
      meter.historical_last_index_raw=item.last_source_index_raw;
      meter.historical_last_index_at=item.last_source_observed_at;
      meter.historical_index_conflict=Boolean(item.has_conflicts);
    }
  }
  // The timeline is a separate presentation projection: update only exact identities.
  for (const group of (account.physical_meter_timeline||[])) {
    for (const row of (group.meters||[])) {
      const meter=(account.meters||[]).find(m=>m.lot===group.lot &&
        m.fluid===group.fluid && m.serial===row.serial);
      if (meter) {
        row.first_observed_at=meter.first_observed_at;
        row.last_source_observed_at=meter.last_source_observed_at;
      }
    }
  }
  account.historical_years_scan_complete=true;
}

/* English is a local presentation layer; measurement and decision records stay unchanged. */
const TRYBATEC_EN_LABELS = new Map([
  ["Unité et identifiant du compteur","Meter unit and device identifier"],
  ["Ce compteur ne dispose pas encore d’une identité source éligible à une modification. Lancez une analyse historique ou utilisez le menu natif de secours.","This meter does not yet have an eligible source identity. Run a history preview or use the native fallback options."],
  ["Analyser l’historique","Analyze history"],
  ["Options natives de secours","Native fallback options"],
  ["Paramètres propres à ce compteur physique. Le graphique ne prouve pas l’unité des index sources.","Settings for this exact physical meter. The chart does not establish source index units."],
  ["Unité explicitement fournie par l’API","Unit explicitly reported by the API"],
  ["Unité de référence du graphique","Chart reference unit"],
  ["Origine de la présélection","Preselection source"],
  ["Unité enregistrée manuellement","Manually saved unit"],
  ["Unité déterminée par l’API","Unit provided by the API"],
  ["Proposition issue du graphique, à confirmer","Chart-based suggestion; confirmation required"],
  ["Unité source du compteur","Source index unit"],
  ["Inconnue / non vérifiée","Unknown / unverified"],
  ["UUID du dispositif Trybatec (facultatif)","Trybatec device UUID (optional)"],
  ["L’API signale une unité conflictuelle ou inconnue : seule la sélection « Inconnue » est autorisée tant que la source n’est pas clarifiée.","The API reports a conflicting or unknown unit: only Unknown is allowed until the source is clarified."],
  ["Enregistrer ce compteur","Save this meter"],
  ["Aucun index source, historique Recorder ou tableau Énergie n’est modifié. Un choix confirmé est associé uniquement à ce compteur.","Source indexes, Recorder and Energy remain unchanged. A confirmed choice belongs only to this physical meter."],
  ["Contrôles historiques de ce compteur","Historical checks for this meter"],
  ["Indicateurs issus du dernier aperçu ; un écart ou conflit n’est pas nécessairement une erreur de mesure.","Indicators from the latest preview; a gap or conflict is not necessarily a measurement error."],
  ["Intervalles lacunaires","Gaps"],
  ["Baisses d’index","Index decreases"],
  ["Conflits de relevés","Conflicting readings"],
  ["Première observation","First observation"],
  ["Dernière observation","Last observation"],
  ["Unité de l’index source","Source index unit"],
  ["Non confirmée","Unconfirmed"],
  ["Synthèse historique par fluide","Historical summary by utility"],
  ["Aucune prévisualisation actuelle. Utilisez « Analyser les relevés » pour calculer les indicateurs à partir des observations source.","No current preview. Select Analyze readings to calculate metrics from source observations."],
  ["Synthèse historique par fluide et compteur","Historical summary by utility and meter"],
  ["Voir les indicateurs par compteur physique","View metrics per physical meter"],
  ["Fluide","Utility"],
  ["Compteur","Meter"],
  ["Lacunes","Gaps"],
  ["Baisses","Decreases"],
  ["Conflits","Conflicts"],
  ["Journalisation et diagnostics","Logging and diagnostics"],
  ["Niveau de journalisation","Logging level"],
  ["Enregistrer la journalisation","Save logging level"],
  ["Annuler la modification","Cancel change"],
  ["Afficher les diagnostics","View diagnostics"],
  ["Accès de secours aux options natives","Native options fallback"],
  ["Ouvrir les options natives de secours","Open native fallback options"],
  ["Enregistrer ces réglages","Save these settings"],
  ["Réglages","Settings"],
  ["Options partagées avec Home Assistant : synchronisation, contrôles et diagnostics.","Shared Home Assistant options: synchronization, checks and diagnostics."],
  ["Ces valeurs sont partagées avec les options natives Trybatec et conservées lors des mises à jour.","These settings are shared with the native Trybatec options and preserved during upgrades."],
  ["Aucune modification des index source, de Recorder ou du tableau Énergie.","No changes to source indexes, Recorder or Energy."],
  ["Le niveau le plus détaillé prévaut.","The most verbose level takes precedence."],
  ["WARNING est recommandé en usage courant. DEBUG augmente la quantité de messages de diagnostic.","WARNING is recommended for daily use. DEBUG produces more diagnostic logs."],
  ["Unité et UUID enregistrés dans les options Home Assistant existantes.","Unit and UUID saved to the existing Home Assistant options."],
  ["Journalisation mise à jour pour Trybatec.","Trybatec logging settings updated."],
  ["Date du dernier index exploitable","Date of latest usable meter index"],
  ["Fréquence de synchronisation","Synchronization interval"],
  ["Jours","Days"],
  ["Heures","Hours"],
  ["Minutes","Minutes"],
  ["Rechercher les relevés historiques","Find historical readings"],
  ["Aucune source Trybatec identifiée dans la configuration Énergie actuellement disponible.","No Trybatec source found in current Energy configuration."],
  ["Dernier index historique source (non qualifié)","Latest historical source index (unqualified)"],
  ["Entités indisponibles détectées","Unavailable entities detected"],
  ["Compteur(s) déposé(s) sans dates historiques confirmées dans l’inventaire actuel.","Retired meters without confirmed historical dates in the current inventory."],
  ["Vue d’ensemble","Overview"],
  ["Compteurs","Meters"],
  ["Historique & lissage","History & smoothing"],
  ["Tarifs","Tariffs"],
  ["Énergie & versions","Energy & versions"],
  ["Diagnostics","Diagnostics"],
  ["Réglages","Settings"],
  ["Bêta","Beta"],
  ["Gestion des compteurs, historiques, tarifs et énergie","Meters, history, tariffs and energy"],
  ["Compteurs en service","Meters in service"],
  ["Compteurs déposés","Retired meters"],
  ["Statut inconnu","Status unknown"],
  ["En service","In service"],
  ["Déposé","Retired"],
  ["Statut à vérifier","Status to verify"],
  ["Aucune donnée disponible.","No data available."],
  ["Historique préservé.","History preserved."],
  ["Voir les compteurs","View meters"],
  ["Auditer les entités","Audit entities"],
  ["Audit des relations techniques","Technical relationships audit"],
  ["Ancienne entité :","Legacy entity:"],
  ["Nouvelle entité :","New entity:"],
  ["Statistiques Recorder :","Recorder statistics:"],
  ["Références Énergie :","Energy references:"],
  ["Tableaux de bord et automatisations :","Dashboards and automations:"],
  ["Nettoyage :","Cleanup:"],
  ["aucune suppression autorisée automatiquement","no automatic deletion allowed"],
  ["audit non exhaustif","non-exhaustive audit"],
  ["Non identifiée","Not identified"],
  ["présente","present"],
  ["absente","absent"],
  ["unité inconnue","unknown unit"],
  ["Relations techniques Home Assistant","Home Assistant technical relationships"],
  ["Sélectionnez un compteur pour consulter ses informations.","Select a meter to view its details."],
  ["Compteur physique","Physical meter"],
  ["Lot","Unit / apartment"],
  ["Fluide","Utility"],
  ["Unité","Unit"],
  ["Dernier index disponible","Latest available meter index"],
  ["Dernière observation source","Latest source observation"],
  ["Dernier index exploitable","Latest usable meter index"],
  ["Statut de l’unité","Unit verification status"],
  ["Sans index courant","No current index"],
  ["Consulter l'historique","Review history"],
  ["Rechercher les relevés","Search readings"],
  ["Analyser les index","Analyze indices"],
  ["Consulter l’unité","View unit"],
  ["Vérifier l’unité","Verify unit"],
  ["Conflit d’unité","Unit conflict"],
  ["Date non établie dans les données consultées","Date not established from consulted data"],
  ["Compteur déposé : vérifier séparément les éventuels index historiques.","Retired meter: review historical indices separately."],
  ["Analyse historique effectuée : aucune date retrouvée dans le périmètre consulté.","History scan completed: no date found in the reviewed scope."],
  ["Origine : unité enregistrée manuellement","Source: unit saved manually"],
  ["Origine : unité explicitement fournie par l’API","Source: unit explicitly provided by API"],
  ["Origine : proposition du graphique, à confirmer","Source: chart suggestion, awaiting confirmation"],
  ["Origine de l’unité non vérifiée","Unit source not verified"],
  ["Vérifiée","Verified"],
  ["À vérifier","To verify"],
  ["Non renseigné","Not provided"],
  ["Non disponible","Not available"],
  ["Non vérifié","Unverified"],
  ["Inconnu","Unknown"],
  ["Auditer","Audit"],
  ["Chronologie des compteurs physiques","Physical meter timeline"],
  ["Aucun compteur correspondant. L’inventaire historique peut nécessiter une prévisualisation préalable.","No matching meter. A historical preview may be required first."],
  ["Historique & lissage","History & smoothing"],
  ["Auditer les identifiants","Audit identifiers"],
  ["Revue des relevés signalés","Review flagged readings"],
  ["Décision sur le relevé","Reading decision"],
  ["Traitement","Handling"],
  ["Type","Type"],
  ["Date réelle vérifiée","Verified actual date"],
  ["Imputation comptable","Accounting allocation"],
  ["Date","Date"],
  ["Heure","Time"],
  ["Justification obligatoire","Reason required"],
  ["Confirmer la décision","Confirm decision"],
  ["Aucun relevé à examiner. Lancez l’analyse historique.","No readings to review. Run a history analysis."],
  ["Aucun intervalle précédent vérifié dans cet aperçu.","No verified preceding interval in this preview."],
  ["Examiner et éventuellement lisser les jours précédents","Review and optionally smooth preceding days"],
  ["Sélectionnez un relevé pour le qualifier ou corriger son attribution.","Select a reading to review or correct its attribution."],
  ["Charger une période","Load a period"],
  ["Aperçu en lecture seule","Read-only preview"],
  ["Depuis le","From"],
  ["Jusqu’au","Through"],
  ["Analyser les relevés","Analyze readings"],
  ["Ancienne IHM de révision","Existing review interface"],
  ["Intervalles entre relevés","Intervals between readings"],
  ["L’analyse ne déduit jamais une origine manuelle ou automatique.","The analysis never infers whether readings are manual or automatic."],
  ["Reconstituer l’intervalle sélectionné","Reconstruct the selected interval"],
  ["Consommation bornée","Bounded consumption"],
  ["Index avant → après","Index before → after"],
  ["Jours","Days"],
  ["État","Status"],
  ["Aperçu après lissage linéaire","Preview after linear smoothing"],
  ["Décision","Decision"],
  ["Lisser le résiduel","Smooth the residual"],
  ["Ne pas lisser","Do not smooth"],
  ["Motif déclaré","Declared reason"],
  ["Relève périodique","Periodic reading"],
  ["Autre motif","Other reason"],
  ["Avant / après","Before / after"],
  ["Source préservée.","Source preserved."],
  ["Aucune borne antérieure fiable : simuler une origine estimée","No reliable earlier baseline: simulate an estimated origin"],
  ["Hypothèse non mesurée","Unmeasured assumption"],
  ["Choisir un compteur","Choose a meter"],
  ["Début estimé","Estimated start"],
  ["Index initial estimé","Estimated initial index"],
  ["Calculer l’aperçu hypothétique","Calculate hypothetical preview"],
  ["Simulation calculée.","Simulation calculated."],
  ["Motif déclaré pour cette hypothèse","Declared reason for this assumption"],
  ["Relève manuelle périodique","Periodic manual reading"],
  ["Autre motif déclaré","Other declared reason"],
  ["Approuver et enregistrer l’hypothèse","Approve and save assumption"],
  ["Comparaison avant / après · consommation et cumul","Before / after · consumption and cumulative total"],
  ["Total entre bornes","Bounded total"],
  ["Consommation réellement mesurée","Actually measured consumption"],
  ["Consommation estimée","Estimated consumption"],
  ["Jour","Day"],
  ["Avant · mesuré","Before · measured"],
  ["Après · consommation","After · consumption"],
  ["Cumul après","Cumulative after"],
  ["Nature","Type"],
  ["Mesuré","Measured"],
  ["Estimé linéaire","Linearly estimated"],
  ["Année","Year"],
  ["Origine","Origin"],
  ["Consommation","Consumption"],
  ["Tarif","Rate"],
  ["Coût estimé","Estimated cost"],
  ["Fiabilité","Reliability"],
  ["Tarif commun du fluide","Default fluid rate"],
  ["Saisir ou modifier un tarif","Enter or edit a rate"],
  ["Exercice annuel","Annual period"],
  ["Enregistrer ce tarif","Save this rate"],
  ["Retirer ce tarif","Remove this rate"],
  ["Tarifs communs","Default rates"],
  ["Tarifs spécifiques aux compteurs","Meter-specific rates"],
  ["Tarifs par compteur","Rates per meter"],
  ["Consommations et coûts estimés par exercice","Estimated annual consumption and costs"],
  ["Aucune consommation justifiable pour cet exercice. Aucun coût fictif n’est produit.","No verifiable consumption for this year. No fictitious cost is calculated."],
  ["Aucun tarif commun enregistré.","No default rate saved."],
  ["Aucune dérogation propre à un compteur. Le tarif commun reste applicable lorsqu’il existe pour l’exercice.","No meter-specific override. The default rate still applies where available for the year."],
  ["Tarif approuvé","Approved rate"],
  ["Tarif provisoire","Provisional rate"],
  ["Tarif absent","Missing rate"],
  ["Tarifs hétérogènes","Mixed rates"],
  ["Spécifique au compteur","Meter-specific"],
  ["Commun au fluide","Default fluid rate"],
  ["Relevés journaliers","Daily readings"],
  ["Imputation approuvée","Approved accounting allocation"],
  ["Non qualifié","Unreviewed"],
  ["Indisponible","Unavailable"],
  ["Approuvé","Approved"],
  ["Provisoire","Provisional"],
  ["Aperçu, import, contrôle de persistance et basculement Énergie sont quatre étapes distinctes. Aucune n’est lancée automatiquement.","Preview, import, persistence verification and Energy activation are four separate steps. None runs automatically."],
  ["Début","Start"],
  ["Fin","End"],
  ["1. Prévisualiser Recorder","1. Preview Recorder"],
  ["Sources Trybatec dans Énergie","Trybatec sources in Energy"],
  ["Séries historiques versionnées","Versioned historical statistics"],
  ["Ouvrir Énergie","Open Energy"],
  ["Diagnostics","Diagnostics"],
  ["Statut","Status"],
  ["Audit des entités techniques","Technical entity audit"],
  ["Actualiser","Refresh"],
  ["Réglages","Settings"],
  ["Gestion des compteurs, historiques, tarifs et énergie","Meter management, history, rates and energy"],
  ["Trybatec — Interface expérimentale · Aucune suppression ni écriture Recorder ou Énergie automatique.","Trybatec — Experimental interface · No automatic deletion or Recorder or Energy writes."],
  ["Impossible de charger les informations Trybatec. Consultez les journaux et réessayez.","Unable to load Trybatec. Check the logs and try again."],
  ["Aucun intervalle précédent vérifiable : actualisez l’analyse.","No verifiable preceding interval; refresh the analysis."],
  ["Intervalle précédent sélectionné pour examen ; aucune décision enregistrée.","Previous interval selected for review; no decision has been saved."],
  ["Le tarif doit être un montant non négatif et valide.","Enter a valid nonnegative rate."],
  ["Supprimer ce tarif ? Le tarif commun sera de nouveau applicable à ce compteur, si défini.","Remove this rate? The default rate will apply again to this meter, if configured."],
  ["Enregistrer ce tarif annuel ? Les historiques Recorder et les préférences Énergie resteront inchangés.","Save this annual rate? Recorder history and Energy preferences will not change."],
  ["Tarif retiré.","Rate removed."],
  ["Tarif enregistré.","Rate saved."],
  ["Modification refusée : vérifiez les données et actualisez les tarifs avant de réessayer.","Change refused: check the data and refresh rates before trying again."],
  ["Lot non renseigné","Unit not provided"],
  ["Unité à vérifier","Unit needs verification"],
  ["Entités à auditer","Entities requiring audit"],
  ["Les compteurs physiques sont distincts des anciennes entités Home Assistant.","Physical meters are distinct from legacy Home Assistant entities."],
  ["Entités à examiner","Entities to review"],
  ["Compteurs physiques actuellement relevés.","Physical meters currently reporting."],
  ["Compteurs retirés conservés pour leur historique.","Retired meters retained for their history."],
  ["Anciennes entités ou entités indisponibles : aucune suppression automatique.","Legacy or unavailable entities: no automatic deletion."],
  ["Association non démontrée : ne supprimez pas cette entité. Vérifiez son identité et ses références.","Association unverified: do not delete this entity. Check identity and references."],
  ["Basculement impossible : Recorder ou Énergie ne valide pas les deux séries. Aucune modification effectuée.","Handoff blocked: Recorder or Energy cannot validate the two series. No changes made."],
  ["Référence Énergie enregistrée et vérifiée. Les deux historiques sont conservés.","Energy reference saved and verified. Both histories are preserved."],
  ["Le résultat nécessite une vérification.","The result needs verification."],
  ["Opération interrompue ou refusée. Consultez les journaux et vérifiez Énergie avant toute nouvelle tentative.","Operation interrupted or refused. Check logs and Energy before retrying."],
  ["Relevé par l’API","Reported by API"],
  ["Archivé localement","Locally archived"],
  ["Inventaire physique : en service, déposés, ou statut non confirmé.","Physical inventory: in service, retired or unverified status."],
  ["Aperçu de l’historique actualisé. Aucune série Recorder n’a été modifiée.","Historical preview refreshed. No Recorder series were changed."],
  ["Prévisualisation impossible : vérifiez la période, la connexion et les journaux Trybatec.","Unable to preview: check dates, connection and Trybatec logs."],
  ["Répartition linéaire du résiduel entre les index sources vérifiés.","Linear allocation of the residual between verified source indexes."],
  ["Aucun lissage : conserver l’intervalle sans répartition.","No smoothing: preserve the interval without allocation."],
  ["Décision enregistrée. Les index sources et Énergie restent inchangés.","Decision saved. Source indexes and Energy remain unchanged."],
  ["Décision refusée : l’intervalle a changé ou doit être réexaminé. Actualisez l’aperçu.","Decision refused: the interval changed or needs review. Refresh the preview."],
  ["L’index initial estimé doit être un nombre positif ou nul.","The estimated initial index must be nonnegative."],
  ["Confirmer que la date et l’index initial sont des HYPOTHÈSES, pas des relevés mesurés ?","Confirm that the date and initial index are ASSUMPTIONS, not measured readings?"],
  ["Aperçu refusé : vérifiez la date de départ, le premier relevé, l’unité et les anomalies. Rechargez un historique couvrant l’origine choisie.","Preview refused: check start date, first reading, unit and anomalies. Reload history covering the chosen origin."],
  ["Un nouvel aperçu vérifié est nécessaire avant l’enregistrement.","A fresh verified preview is required before saving."],
  ["Enregistrer cette origine comme HYPOTHÈSE APPROUVÉE ?","Save this origin as an APPROVED ASSUMPTION?"],
  ["Autoriser explicitement le remplacement d’une hypothèse déjà approuvée pour ce compteur ?","Explicitly authorize replacing a previously approved assumption for this meter?"],
  ["Hypothèse approuvée enregistrée séparément des index réels. ","Approved assumption saved separately from real indexes. "],
  ["Aucun import Recorder ni changement Énergie : ces opérations nécessitent leur propre validation.","No Recorder import or Energy change: each requires its own approval."],
  ["Enregistrement refusé : source ou paramètres modifiés, décision antérieure non remplaçable sans confirmation, ou historique à actualiser.","Save refused: source or parameters changed, prior decision requires revision approval, or history needs refreshing."],
  ["La correction exige un justificatif explicite (au moins 8 caractères).","The correction requires an explicit reason of at least 8 characters."],
  ["Conserver ce relevé","Keep this reading"],
  ["Corriger/imputer ce relevé","Correct/allocate this reading"],
  ["Écarter ce relevé du calcul","Exclude this reading from calculations"],
  ["Reporter l’examen (le relevé sera temporairement écarté du calcul)","Postpone review (temporarily exclude this reading)"],
  ["Décision enregistrée ; index source, Recorder et Énergie inchangés.","Decision saved; source indexes, Recorder and Energy unchanged."],
  ["Décision refusée : vérifiez la date, le motif ou l’imputation hors période, puis actualisez l’historique.","Decision refused: check date, reason or out-of-period allocation, then refresh history."],
  ["Intervalle espacé (pas une erreur avérée)","Sparse interval (not necessarily an error)"],
  ["Index nul à qualifier","Zero index requires review"],
  ["Baisse d’index à vérifier","Index decrease requires review"],
  ["Relevés sources contradictoires","Conflicting source readings"],
  ["Conflit d’index à examiner","Index conflict requires review"],
  ["Unité non vérifiée","Unverified unit"],
  ["Index nul non qualifié","Unreviewed zero index"],
  ["Bornes à vérifier","Boundaries require review"],
  ["Lissage envisageable après confirmation","Smoothing available after confirmation"],
  ["Répartition linéaire contrôlée, sans modification des relevés bruts.","Controlled linear allocation without modifying raw readings."],
  ["Aucun intervalle à signaler sur cette période.","No flagged intervals in this period."],
  ["Analysez une période pour afficher les intervalles concernés.","Analyze a period to view its intervals."],
  ["Non déterminée","Undetermined"],
  ["À déterminer","To be determined"],
  ["Choisissez un exercice commencé, entre 2000 et l’année courante.","Choose a year between 2000 and the current year."],
  ["Coûts indisponibles : vérifiez la connexion, les unités et les relevés source. Aucun coût manquant n’est remplacé par une valeur supposée.","Costs unavailable: check connection, units and source readings. Missing costs are never inferred."],
  ["coût indisponible","cost unavailable"],
  ["spécifique","meter-specific"],
  ["Aperçu Recorder obtenu. Aucun import n’a commencé.","Recorder preview obtained. No import has started."],
  ["Plan impossible : vérifiez unités, zéros et décisions de lissage, puis recommencez l’aperçu.","Plan unavailable: verify units, zero readings and smoothing decisions, then retry preview."],
  ["Importer les séries historiques dans Recorder ?","Import historical series into Recorder?"],
  ["Import refusé : aperçu périmé, sauvegarde manquante ou série déjà présente. Aucune réussite n’est présumée.","Import refused: stale preview, missing backup or existing series. No success is assumed."],
  ["Vérification Recorder exécutée. Consultez les états détaillés ci-dessous.","Recorder verification executed. See detailed statuses below."],
  ["Vérification Recorder impossible. N’activez aucune nouvelle série dans Énergie.","Unable to verify Recorder. Do not activate any new Energy series."],
  ["Aperçu Énergie compatible, sans écriture.","Energy preview is compatible; no writes performed."],
  ["Basculement refusé : série non vérifiée, mauvaise unité, référence absente ou double comptage possible.","Energy switch refused: unverified series, incompatible unit, missing reference or possible double counting."],
  ["Confirmer le remplacement de la série dans Énergie ?","Confirm replacing the series in Energy?"],
  ["Activation refusée ou contrôle après écriture échoué. Consultez les diagnostics ; aucun succès n’est présumé.","Activation refused or post-write verification failed. Check diagnostics; success is not assumed."],
  ["Références configurées et versions historiques vérifiables.","Configured references and verifiable historical versions."],
  ["Unité inconnue","Unknown unit"],
  ["Lecture des entités, disponibilités et état des données.","Read entities, availability and data status."],
  ["Données chargées","Data loaded"],
  ["En attente de données","Awaiting data"],
  ["Indiquez des nombres entiers dans les limites autorisées.","Enter whole numbers within the permitted ranges."],
  ["Confirmer les réglages Trybatec ?","Confirm Trybatec settings?"],
  ["Réglages enregistrés dans la configuration Home Assistant partagée.","Settings saved in the shared Home Assistant configuration."],
  ["Modification refusée ou intégration en cours de rechargement. Actualisez et vérifiez les valeurs.","Change refused or integration reloading. Refresh and verify the values."],
  ["Modifiez les paramètres existants sans supprimer l’ancienne interface.","Edit existing parameters without removing the previous interface."],
  ["De 60 minutes à 7 jours. Une modification peut recharger l’intégration.","From 60 minutes to 7 days. Changing this may reload the integration."],
  ["Intervalle à signaler (heures)","Flag intervals longer than (hours)"],
  ["Par défaut : 27 h. Un intervalle strictement supérieur est considéré comme espacé.","Default: 27 h. Only intervals strictly above this limit are flagged."],
  ["Index nuls consécutifs (jours)","Consecutive zero-index days"],
  ["0 désactive la sollicitation ; 1 signale dès le premier jour avec un index nul.","0 disables prompts; 1 flags the first day containing a zero index."],

  ["Anciennes générations techniques à examiner :","Legacy technical generations to review:"],
  ["Entités encore référencées dans Énergie :","Entities still referenced in Energy:"],
  ["Audit partiel, aucune suppression autorisée.","Partial audit; no deletion permitted."],
  ["Ancienne génération technique à auditer","Legacy technical generation requiring audit"],
  ["Entité technique non classée","Unclassified technical entity"],
  ["Autre génération du même appareil :","Another generation of this device:"],
  ["Références Énergie confirmées :","Confirmed Energy references:"],
  ["Identité technique et vérifications manquantes","Technical identity and unverified dependencies"],
  ["Identifiant technique :","Technical identifier:"],
  ["Appareil :","Device:"],
  ["Recorder, automatisations et tableaux de bord : non vérifiés exhaustivement.","Recorder, automations and dashboards: not exhaustively checked."],
  ["Nettoyage : interdit sans audit complet, sauvegarde et confirmation distincte.","Cleanup prohibited without a complete audit, backup and separate confirmation."],
  ["Non vérifié","Not verified"],

  ["Prévisualiser le basculement Énergie","Preview Energy switch"],
  ["Aperçu vérifié :","Verified preview:"],
  ["Je confirme disposer d’une sauvegarde récupérable incluant Recorder.","I confirm that a recoverable backup including Recorder is available."],
  ["Confirmer et vérifier le basculement","Confirm and verify switch"],
  ["Première observation connue","First known observation"],
  ["Les identités techniques ne doivent pas être supprimées tant que leurs références sont inconnues.","Technical identities must not be deleted while their references remain unknown."],
  ["Aucune association vérifiée par identifiant technique. Consultez l’audit des entités.","No verified technical-identity association. Check the entity audit."],
  ["Par logement et fluide, fondée uniquement sur les observations. Les dates exactes de remplacement ne sont pas déduites.","Grouped by dwelling and utility from observations only; actual replacement dates are not inferred."],
  ["Le détail journalier est tronqué pour cette longue période.","Daily details are truncated for this long interval."],
  ["Panne de télérelève","Remote-reading failure"],
  ["Comparaison journalière non disponible : les bornes ou le détail doivent être revérifiés.","Daily comparison unavailable; recheck boundaries and details."],
  ["Aperçu limité aux 90 premiers jours. Total et validation calculés sur l’ensemble de la période.","Preview limited to the first 90 days. Totals and validation cover the entire period."],
  ["Le détail journalier est indisponible pour cette période. Aucun historique fictif n’est généré.","Daily details unavailable for this interval. No fictitious history is generated."],
  ["Estimé : bleu","Estimated: blue"],
  ["Une correction de date réelle exige une preuve ; une imputation comptable ne modifie pas la date de mesure.","Changing the actual reading date requires evidence; accounting allocation does not change the measurement timestamp."],
  ["Je confirme explicitement une imputation en dehors de la période source, si applicable.","I explicitly confirm allocation outside the source period, if applicable."],
  ["Sélectionnez un intervalle pour comparer la période et éventuellement enregistrer une décision de lissage.","Select an interval to compare before/after and optionally record a smoothing decision."],
  ["Période incomplète","Incomplete period"],
  ["Lecture des relevés et calcul en cours.","Reading source data and calculating."],
  ["Choisissez l’année, le fluide et éventuellement un compteur. Les tarifs déjà saisis sont conservés.","Choose the year, utility and optionally a meter. Existing rates are preserved."],
  ["Tarifs annuels","Annual rates"],
  ["Montants en EUR par exercice, fluide et, facultativement, compteur physique.","Rates in EUR by year, utility and optionally physical meter."],
  ["Compteur non identifié","Unidentified meter"],
  ["(déposé)","(retired)"],
  ["Annuler la saisie","Discard edits"],
  ["Modifier","Edit"],
  ["Action","Action"],
  ["Exercice invalide : choisissez une année entre 2000 et 2100.","Invalid year: choose a year between 2000 and 2100."],
  ["Le tarif doit être compris entre 0 et 1 000 000, avec six décimales au maximum.","Enter a rate between 0 and 1,000,000 with no more than six decimal places."],
  ["Tarif enregistré, mais actualisation impossible : actualisez le panneau pour vérifier la valeur.","Rate saved, but the panel could not refresh: reload to verify the value."],
  ["Aucun tarif enregistré pour cet exercice.","No rate saved for this year."],
  ["Tarif effectif enregistré","Saved effective rate"],
  ["Exercices suggérés ci-dessous ; toute année entre 2000 et 2100 peut être saisie.","Suggested years are shown; you can enter any year from 2000 to 2100."],
  ["Portée","Scope"],
  ["Préparer une version historique Recorder","Prepare a Recorder history version"],
  ["Plan non importé","Plan not imported"],
  ["Une sauvegarde récupérable de HA/Recorder existe","A recoverable HA/Recorder backup is available"],
  ["3. Vérifier la persistance Recorder","3. Verify Recorder persistence"],
  ["Choisir une version vérifiée pour Énergie","Choose a verified Energy version"],
  ["Série actuellement sélectionnée","Currently selected series"],
  ["Sélectionner une source Trybatec versionnée","Select a versioned Trybatec source"],
  ["Sélectionner une version vérifiée","Select a verified version"],
  ["4. Prévisualiser le basculement","4. Preview switch"],
  ["Sauvegarde Énergie confirmée","Energy backup confirmed"],
  ["J’approuve le retour vers une version archivée","I approve switching back to an archived version"],
  ["5. Confirmer le basculement Énergie","5. Confirm Energy switch"],
  ["Aucune source Trybatec identifiée dans la configuration Énergie actuellement disponible.","No Trybatec source is identified in the currently available Energy configuration."],
  ["Aucune série versionnée enregistrée. Une importation historique ne sera pas démarrée automatiquement.","No versioned series recorded. Historical imports are never started automatically."],
  ["Inventaire archivé :","Archived inventory:"],
  ["Entités Trybatec recensées :","Trybatec entities found:"],
  ["Compteurs physiques connus :","Known physical meters:"],
  ["Synchronisation actuelle :","Current synchronization:"],
  ["Aucune entité recensée.","No entities found."],
  ["Synchronisation et contrôle des relevés","Reading synchronization and verification"],
  ["Ces valeurs sont partagées avec Options Trybatec et conservées lors des mises à jour.","These values are shared with Trybatec Options and preserved across updates."],
  ["Enregistrer les réglages","Save settings"],
  ["Les unités, les options de diagnostic et les parcours historiques sont conservés dans l’interface Home Assistant actuelle.","Units, diagnostic options and historical flows remain available in the existing Home Assistant interface."],
  ["Chargement des données Trybatec…","Loading Trybatec data…"],
  ["Réessayer","Try again"],
  ["Aucune entrée Trybatec actuellement chargée. Configurez l’intégration dans Paramètres → Appareils et services.","No Trybatec entry is currently loaded. Configure the integration under Settings → Devices & services."],
  ["Une entité indisponible n’est pas nécessairement obsolète : elle peut avoir des historiques Recorder et des références actives. Une génération technique n’est pas un compteur physique déposé.","An unavailable entity is not necessarily obsolete: it may have Recorder history and active references. A technical generation is not a retired physical meter."],
  ["Les références aux tableaux de bord, automatisations et statistiques Recorder ne sont pas vérifiées exhaustivement. Un résultat vide dans Énergie ne prouve pas qu’une entité est inutilisée.","Dashboard, automation and Recorder statistics references have not been comprehensively checked. An empty Energy result does not establish that an entity is unused."],

]);

function localizeTrybatecText(value, language) {
  const raw=String(value);
  if (!/^en(?:$|[-_])/i.test(String(language||""))) return raw;
  const trimmed=raw.trim();
  const translated=TRYBATEC_EN_LABELS.get(trimmed);
  if (translated) return raw.replace(trimmed,translated);
  // Only punctuated static labels may prefix dynamic values (counts, IDs).
  // Never translate arbitrary source readings, serial numbers or user text.
  for (const [label, english] of TRYBATEC_EN_LABELS) {
    if ((label.endsWith(":") || label.endsWith(" :") || label.endsWith("?"))
        && trimmed.startsWith(label) && trimmed.length>label.length
        && /\s/.test(trimmed.charAt(label.length))) {
      return raw.replace(label,english);
    }
  }
  return raw;
}
function localizeTrybatecPanel(root, language) {
  if (!/^en(?:$|[-_])/i.test(String(language||""))) return;
  const translate = (value) => localizeTrybatecText(value,language);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const tag = node.parentElement?.tagName;
    if (tag!=="STYLE" && tag!=="SCRIPT") textNodes.push(node);
  }
  for (const node of textNodes) node.nodeValue=translate(node.nodeValue);
  for (const element of root.querySelectorAll("[placeholder],[aria-label],[title]")) {
    for (const attr of ["placeholder","aria-label","title"]) {
      if (element.hasAttribute(attr)) {
        element.setAttribute(attr, translate(element.getAttribute(attr)));
      }
    }
  }
}

const escapeText = (value) => String(value === null || value === undefined ? "" : value)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;")
  .replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
const safe = escapeText;
/** Presentation only: grouping and decimal symbols follow the HA language; no numeric rounding. */
function trybatecDisplayNumber(value, language) {
  if (value===null || value===undefined) return "";
  const raw=String(value).trim();
  if (!/^-?\d+(?:\.\d+)?$/.test(raw)) return raw;
  let group="\u202f", decimal=",";
  try {
    const parts=new Intl.NumberFormat(language||"fr-FR").formatToParts(1234.5);
    group=parts.find(p=>p.type==="group")?.value||group;
    decimal=parts.find(p=>p.type==="decimal")?.value||decimal;
  } catch (_) { /* Safe fallback for an invalid locale. */ }
  const negative=raw.startsWith("-");
  const [integer,fraction]= (negative?raw.slice(1):raw).split(".");
  return (negative?"-":"")+integer.replace(/\B(?=(\d{3})+(?!\d))/g,group)+
    (fraction===undefined?"":decimal+fraction);
}
/** ISO dates are kept intact in storage; calendar-only values never shift day. */
function trybatecDisplayDate(value, language, zone, includeTime=false) {
  if (typeof value!=="string" || !value) return "";
  const calendarOnly=/^\d{4}-\d{2}-\d{2}$/.test(value);
  const parsed=new Date(calendarOnly?value+"T12:00:00Z":value);
  if (!Number.isFinite(parsed.getTime())) return value;
  try {
    const locale=language||"fr-FR";
    const timeZone=calendarOnly?"UTC":(zone||"UTC");
    const day=new Intl.DateTimeFormat(locale,{
      weekday:"long",day:"numeric",month:"long",year:"numeric",timeZone
    }).format(parsed);
    if (!includeTime || calendarOnly) return day;
    const clock=new Intl.DateTimeFormat(locale,{
      hour:"2-digit",minute:"2-digit",hourCycle:"h23",timeZone
    }).format(parsed);
    // Source midnight can represent a daily reading, not a measured clock time.
    return clock==="00:00"?day:day+(locale.toLowerCase().startsWith("fr")?" à ":" ")+clock;
  } catch (_) {return value;}
}

function trybatecDurationParts(value) {
  const total=Math.max(0,Number(value)||0);
  return {days:String(Math.floor(total/1440)),
    hours:String(Math.floor(total%1440/60)),minutes:String(total%60)};
}
function trybatecDurationMinutes(parts) {
  const fields=["days","hours","minutes"];
  if (!fields.every(f=>/^(?:0|[1-9]\d*)$/.test(String(parts?.[f]??""))))
    return NaN;
  const days=Number(parts.days),hours=Number(parts.hours),minutes=Number(parts.minutes);
  if (days>7 || hours>23 || minutes>59) return NaN;
  const total=days*1440+hours*60+minutes;
  return total>=60 && total<=10080?total:NaN;
}
const style = [
  ":host{--trybatec-ef-brand:#0A84D8;--trybatec-ecs-brand:#C73A5C;--trybatec-cet-brand:#E0A126;--trybatec-brand-green:#4E9E4A;--trybatec-ef-fg:#075A9B;--trybatec-ef-bg:#E8F3FC;--trybatec-ecs-fg:#A9234A;--trybatec-ecs-bg:#FCE9F0;--trybatec-cet-fg:#805500;--trybatec-cet-bg:#FBF3DE;--trybatec-green-fg:#286C32;--trybatec-green-bg:#EBF7EC;--trybatec-card-border:#C7D3E0;--trybatec-section-border:#BBCAD8}",
  ":host([data-trybatec-theme=\"dark\"]){--trybatec-ef-fg:#65B8FA;--trybatec-ef-bg:#18334B;--trybatec-ecs-fg:#FF7897;--trybatec-ecs-bg:#43232F;--trybatec-cet-fg:#FFD166;--trybatec-cet-bg:#3F3218;--trybatec-green-fg:#8ADD8F;--trybatec-green-bg:#203A29;--trybatec-card-border:#526171;--trybatec-section-border:#617487}",
  ".fluid-ef{--fluid-fg:var(--trybatec-ef-fg);--fluid-bg:var(--trybatec-ef-bg)}",
  ".fluid-ecs{--fluid-fg:var(--trybatec-ecs-fg);--fluid-bg:var(--trybatec-ecs-bg)}",
  ".fluid-cet{--fluid-fg:var(--trybatec-cet-fg);--fluid-bg:var(--trybatec-cet-bg)}",
  ".fluid-surface{border-top:4px solid var(--fluid-fg,var(--trybatec-section-border))}",
  ".meter-row button.selected{background:var(--fluid-bg,#e9f1ff);border-inline-start-color:var(--fluid-fg,#075A9B)}",
  ".meter-row button.selected .meter-name{color:var(--fluid-fg,#075A9B)}",
  ".meter-row button:focus-visible{outline:3px solid var(--fluid-fg,#4385f5);outline-offset:2px}",
  ".fluid-icon{color:var(--fluid-fg);--mdc-icon-size:18px;vertical-align:middle;margin-inline-end:5px}",
  ".selected-indicator{float:inline-end;color:var(--fluid-fg);--mdc-icon-size:18px}",
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
  ".badge{display:inline-block;padding:5px 9px;background:var(--trybatec-ef-bg,#e9f1ff);border-radius:14px;color:var(--trybatec-ef-fg,#254a94);font-weight:650;font-size:12px}",
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
  ".card{min-width:0;background:var(--card-background-color,#fff);border:1px solid var(--trybatec-card-border,#c7d3e0);border-radius:16px;padding:19px}",
  ".stat{display:flex;gap:12px;align-items:center}.stat ha-icon{color:var(--primary-color,#1176c7);--mdc-icon-size:26px}",
  ".stat strong{font-size:25px;display:block;line-height:1.15}.stat span{color:var(--secondary-text-color,#637188);font-size:12px}",
  ".columns{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}",
  ".panel-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}",
  ".panel-title h3{margin:0}.meter-row{border-top:1px solid var(--divider-color,#e9ebf0);padding:12px 0}",
  ".meter-row:first-of-type{border-top:none}.meter-row button{display:block;background:transparent;border:0;border-inline-start:4px solid transparent;border-radius:11px;color:inherit;text-align:left;width:100%;padding:10px!important}",
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
  ".scroll{max-height:650px;overflow:auto}.selected{border-radius:11px}",
  ".detail-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}",
  ".detail-grid>div{background:var(--secondary-background-color,rgba(120,140,165,.13));border:1px solid var(--trybatec-section-border);padding:12px;border-radius:10px;overflow-wrap:anywhere}",
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
  // FR/EN: a native select's intrinsic min-content width must not widen a 320 CSS px page.
  // Preserve keyboard selection and readable labels; do not hide overflow on the page.
  ".grid-two>div{min-width:0}.grid-two select,.grid-two input{box-sizing:border-box;min-width:0;max-width:100%;width:100%}",
  ".form-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}",
  "label{display:block;font-size:12px;font-weight:600;margin-bottom:4px;color:var(--secondary-text-color,#606e82)}",
  ".form-grid input,.form-grid select{width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:9px;color:inherit;background:var(--card-background-color,#fff)}",
  ".footer{font-size:12px;color:var(--secondary-text-color,#667085);margin-top:22px}",
  "@media(max-width:1050px){.columns{grid-template-columns:1fr 1fr}.cards{grid-template-columns:repeat(2,1fr)}.split{grid-template-columns:1fr}}",
  "@media(max-width:740px){.wrap{padding:15px 13px 28px}.heading{gap:10px;margin-bottom:15px}.mark{width:46px;height:46px}h1{font-size:25px}",
  ".shell{grid-template-columns:1fr;gap:14px}.nav{position:static;display:flex;flex-direction:row;overflow-x:auto;border:0;padding:4px 0;white-space:nowrap}",
  ".nav button{padding:10px 12px}.nav button span{white-space:nowrap}.intro{display:block}.columns,.grid-two,.detail-grid,.form-grid{grid-template-columns:1fr}",
  ".card{padding:15px}.cards{grid-template-columns:repeat(2,1fr)}.stat strong{font-size:23px}}",
  ":host{--trybatec-action-bg:#25364A;--trybatec-action-text:#FFFFFF;--trybatec-action-border:#25364A;--trybatec-neutral-bg:#F8FAFC;--trybatec-neutral-fg:#1D2939;--trybatec-neutral-border:#64748B;--trybatec-status-success:#286C32;--trybatec-status-warning:#865100;--trybatec-status-neutral:#475569;--trybatec-status-na:#59687A}",
  ":host([data-trybatec-theme=\"dark\"]){--trybatec-action-bg:#DAE5F0;--trybatec-action-text:#172334;--trybatec-action-border:#DAE5F0;--trybatec-neutral-bg:#213244;--trybatec-neutral-fg:#F1F5F9;--trybatec-neutral-border:#9FB2C7;--trybatec-status-success:#8ADD8F;--trybatec-status-warning:#FFD166;--trybatec-status-neutral:#CBD5E1;--trybatec-status-na:#AAB7C4}",
  ".nav-wrap{position:relative;min-width:0}.nav-forward{display:none}.menu-toggle{display:none}",
  ".primary{background:var(--trybatec-action-bg);color:var(--trybatec-action-text);border-color:var(--trybatec-action-border)}",
  ".secondary{background:var(--trybatec-neutral-bg);color:var(--trybatec-neutral-fg);border-color:var(--trybatec-neutral-border)}",
  ".nav button.active{background:var(--trybatec-neutral-bg);color:var(--trybatec-neutral-fg);box-shadow:inset 3px 0 var(--trybatec-neutral-border)}.nav button.active ha-icon{color:var(--trybatec-neutral-fg)}",
  ".stat ha-icon{color:var(--trybatec-neutral-fg)}.link{color:var(--trybatec-neutral-fg);text-decoration:underline}.badge{background:var(--trybatec-neutral-bg);color:var(--trybatec-neutral-fg);border:1px solid var(--trybatec-neutral-border)}",
  ".meter-title{color:var(--fluid-fg,var(--primary-text-color));display:flex;align-items:center;gap:8px;overflow-wrap:anywhere}",
  ".meter-title ha-icon{color:var(--fluid-fg);--mdc-icon-size:25px;flex-shrink:0}",
  ".poll-duration{grid-column:span 2;min-width:0}.duration-inputs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.duration-inputs label{margin-bottom:5px}",
  ".meter-options-grid>div,.logging-field{grid-column:span 2;min-width:0}.meter-options-grid input,.meter-options-grid select,.logging-field select{width:100%;padding:10px;border:1px solid var(--divider-color,#cbd5e1);border-radius:9px;color:inherit;background:var(--card-background-color,#fff)}",
  ".prerequisite-locked{opacity:.53;filter:grayscale(.5);border:0;padding:0;margin:0;width:100%;min-width:0}",
  ".prerequisite-ready{border:0;padding:0;margin:0;width:100%;min-width:0}",
  ".readiness-list{display:grid;gap:12px}.readiness-row{display:flex;align-items:flex-start;gap:12px;border-top:1px solid var(--divider-color,#ddd);padding-top:12px}",
  ".readiness-row:first-child{border-top:0;padding-top:0}.readiness-row ha-icon{--mdc-icon-size:23px;flex-shrink:0}",
  ".readiness-row.ok ha-icon{color:var(--trybatec-green-fg)}.readiness-row.pending ha-icon{color:var(--warning-color,#A46A0C)}",
  ".readiness-row p{font-size:13px;color:var(--secondary-text-color);margin-top:4px}.readiness-row .actions{margin-top:8px}",

  ".primary:hover:not(:disabled),.secondary:hover:not(:disabled){box-shadow:0 0 0 1px var(--trybatec-neutral-border)}",
  "button:disabled{cursor:not-allowed;opacity:.40;filter:grayscale(.45);box-shadow:none}",
  ".readiness-row.ok ha-icon{color:var(--trybatec-status-success)}.readiness-row.pending ha-icon{color:var(--trybatec-status-neutral)}",
  ".readiness-row.issue ha-icon{color:var(--trybatec-status-warning)}.readiness-row.na ha-icon{color:var(--trybatec-status-na)}",
  ".readiness-optional{border-top:1px solid var(--divider-color,#ddd);margin-top:12px;padding-top:12px}",
  ".readiness-optional h4{font-size:14px;margin:4px 0 10px}.readiness-optional .readiness-row{border:0;padding:8px 0}",
  ".status-indicator{display:inline-flex;align-items:center;gap:7px;vertical-align:middle;font-weight:650}",
  ".status-indicator ha-icon{--mdc-icon-size:18px;flex-shrink:0}",
  ".status-indicator.passed ha-icon{color:var(--trybatec-status-success)}",
  ".status-indicator.issue ha-icon{color:var(--trybatec-status-warning)}",
  ".status-indicator.unverified ha-icon{color:var(--trybatec-status-neutral)}",
  ".status-indicator.na ha-icon{color:var(--trybatec-status-na)}",
  ".status-indicator.known ha-icon{color:var(--trybatec-status-neutral)}",
  ".meter-detail-field .field-context{margin-top:7px;color:var(--secondary-text-color);font-size:12px;line-height:1.4}",
  ".meter-detail-field .context-button{display:inline-flex;align-items:center;gap:6px;margin-top:9px;padding:7px 10px;font-size:12px;max-width:100%}",
  ".meter-detail-field .context-button ha-icon{--mdc-icon-size:17px}",
  ".meter-history-context{margin:0 0 15px;padding:12px;border:1px solid var(--trybatec-section-border);border-radius:10px}",
  "button[data-tariff-delete]{color:var(--error-color,#AF263A);background:transparent;border-color:currentColor}",
  "@media(max-width:740px){.menu-toggle{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;flex-shrink:0;border:0;border-radius:10px;background:var(--trybatec-neutral-bg);color:var(--trybatec-neutral-fg);border:1px solid var(--trybatec-neutral-border)}",
  ".nav-wrap{padding-inline-end:34px}.nav{scrollbar-width:none;scroll-behavior:smooth}.nav::-webkit-scrollbar{display:none}",
  ".nav-forward{display:flex;align-items:center;justify-content:center;position:absolute;inset-inline-end:0;top:0;bottom:0;min-width:38px;border:0;color:var(--trybatec-neutral-fg);background:linear-gradient(to right,transparent,var(--card-background-color,#fff) 35%)}",
  ".nav-forward[hidden]{display:none}.nav-forward ha-icon{--mdc-icon-size:24px}.poll-duration,.meter-options-grid>div,.logging-field{grid-column:1/-1}.duration-inputs{grid-template-columns:repeat(3,minmax(0,1fr))}}",
].join("");

class TrybatecPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this._tab = "overview";
    this._account = 0;
    this._meter = 0;
    this._historyContextKey=null;
    this._query = "";
    this._data = null;
    this._loading = false;
    this._error = "";
    this._message = "";
    this._started = false;
    this._tariffInput = {year:new Date().getFullYear(),fluid:"EF",physical_key:"",rate:"",status:"provisional"};
    this._tariffHydrated = false;
    this._tariffBusy = false;
    this._tariffError = "";
    this._tariffMessage = "";
    this._tariffCoverage = new Map();
    this._costPreview=null;
    this._costBusy=false;
    this._costError="";
    this._costYear=null;
    this._historyStart="2021-01-01";
    this._historyEnd=new Date().toLocaleDateString("sv-SE",{timeZone:"Europe/Paris"});
    this._historyPreview=null;
    this._historyBusy=false;
    this._historySelected="";
    this._historyMode="linear";
    this._historyReason="manual_periodic";
    this._historyError="";
    this._historyMessage="";
    this._historyJobId=null;
    this._historyJobStatus=null;
    this._tariffJobId=null;
    this._tariffJobStatus=null;
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
    this._unsavedInput=false;
    this._serverVersionPending=null;
    this._versionCheckBusy=false;
    this._versionPoll=null;
    this._visibilityCheck=()=>{if (document.visibilityState==="visible") this._checkServerVersion();};

    this._navScrollLeft=0;
    this._durationInput=null;
    this._loggingInput=null;
    this._loggingBusy=false;
    this._loggingError="";
    this._loggingMessage="";
    this._meterOptionDraft=null;
    this._meterOptionBusy=false;
    this._meterOptionError="";
    this._meterOptionMessage="";
    this.shadowRoot.addEventListener("click", (event) => this._click(event));
    this.shadowRoot.addEventListener("change", (event) => this._change(event));
    this.shadowRoot.addEventListener("input", (event) => this._input(event));
    this.shadowRoot.addEventListener("submit", (event) => this._submit(event));
  }
  set hass(value) {
    const previousLanguage=this._hass?.language;
    const previousDark=this._hass?.themes?.darkMode;
    this._hass = value;
    this.dataset.trybatecTheme=value?.themes?.darkMode===true?"dark":"light";
    if (this.isConnected && !this._started) this._fetch();
    else if (this.isConnected &&
      (previousLanguage!==value?.language || previousDark!==value?.themes?.darkMode)) this._render();
  }
  set narrow(value) { const changed=this._narrow!==value;this._narrow=value;if(changed&&this.isConnected)this._render(); }
  set panel(value) { this._panel = value; }
  connectedCallback() {
    this._render();
    if (this._hass && !this._started) this._fetch();
    if (!this._versionPoll) {
      this._versionPoll=window.setInterval(()=>this._checkServerVersion(),90000);
      document.addEventListener("visibilitychange",this._visibilityCheck);
      window.addEventListener("focus",this._visibilityCheck);
    }
  }
  disconnectedCallback() {
    if (this._versionPoll) window.clearInterval(this._versionPoll);
    this._versionPoll=null;
    document.removeEventListener("visibilitychange",this._visibilityCheck);
    window.removeEventListener("focus",this._visibilityCheck);
  }
  async _checkServerVersion() {
    if (this._versionCheckBusy || this._loading || !this._hass || !this.isConnected ||
        document.visibilityState!=="visible" || !this._data?.version) return;
    this._versionCheckBusy=true;
    try {
      // Read-only snapshot: no change to Recorder, Energy, tariffs or vendor data.
      const snapshot=await this._hass.callWS({type:"trybatec/panel_snapshot"});
      if (typeof snapshot?.version==="string" && snapshot.version!==this._data.version) {
        this._serverVersionPending=snapshot.version;
        if (!this._unsavedInput && !this._isEditingForm()) {
          window.location.reload();
        } else {
          this._renderVersionNotice();
        }
      }
    } catch (_) {
      // Never reload a page when server-side compatibility cannot be confirmed.
    } finally {
      this._versionCheckBusy=false;
    }
  }
  _isEditingForm() {
    const current=this.shadowRoot.activeElement;
    return Boolean(current && this._isEditableInput(current));
  }
  _renderVersionNotice() {
    const slot=this.shadowRoot.querySelector("[data-version-notice]");
    if (!slot) return;
    slot.textContent="";
    slot.hidden=!this._serverVersionPending;
    slot.style.display=this._serverVersionPending?"":"none";
    if (!this._serverVersionPending) return;
    const message=document.createElement("span");
    message.textContent="Nouvelle version Trybatec disponible : "+this._serverVersionPending+
      ". Saisie en cours conservée ; actualisation reportée.";
    const button=document.createElement("button");
    button.type="button";
    button.dataset.reloadPanel="";
    button.textContent="Actualiser la page";
    slot.append(message,button);
  }
  _t(fr, en) {
    return /^en(?:$|[-_])/i.test(String(this._hass?.language || "")) ? en : fr;
  }
  _number(value) {
    return new Intl.NumberFormat(this._hass?.language || "fr-FR", {
      maximumFractionDigits: 3,
    }).format(value);
  }
  get _current() { return this._data && this._data.accounts ? this._data.accounts[this._account] : null; }
  async _fetch() {
    if (!this._hass || this._loading) return;
    this._started = true;
    this._loading = true;
    this._error = "";
    this._render();
    try {
      // FR/EN: preserve the physical meter across inventory reordering.
      // Never silently show a different meter if the previous one disappeared.
      const priorEntryId=this._current?.entry_id;
      const priorPhysicalKey=this._current?.meters?.[this._meter]?.physical_key;
      const snapshot=await this._hass.callWS({type:"trybatec/panel_snapshot"});
      if (!Array.isArray(snapshot?.accounts)) throw new Error("Invalid panel snapshot");
      this._data=snapshot;
      const accountIndex=priorEntryId?
        snapshot.accounts.findIndex(a=>a.entry_id===priorEntryId):-1;
      this._account=accountIndex>=0?accountIndex:
        Math.min(this._account,Math.max(0,snapshot.accounts.length-1));
      if (priorPhysicalKey) {
        const newIndex=accountIndex>=0?
          (this._current?.meters||[]).findIndex(m=>m.physical_key===priorPhysicalKey):-1;
        this._meter=newIndex; // -1 means missing; never select another account's meter.
      } else if (this._meter<0) {
        this._meter=-1;
      }
      this._message = "";
    } catch (err) {
      this._error = "Impossible de charger les informations Trybatec. Consultez les journaux et réessayez.";
    } finally {
      this._loading = false;
      this._render();
      if (this._tab==="tariffs" && this._current) this._loadTariffYearCoverage();
    }
  }
  async _loadTariffYearCoverage(force=false) {
    // Scanning from year 2000 can be expensive. Never initiate it simply
    // because the administrator navigates to the Tariffs page.
    if (!force || !this._current || !this._hass) return;
    const id=this._current.entry_id;
    const prior=this._tariffCoverage.get(id);
    if (prior?.status==="loading") return;
    if (!force && prior?.status==="complete" && Array.isArray(prior.meters)) {
      const account=(this._data?.accounts||[]).find(item=>item.entry_id===id);
      if (account) trybatecMergeHistoricalObservationDates(account,prior);
      this._render();return;
    }
    this._tariffCoverage.set(id,{status:"loading"});
    this._tariffJobStatus=null;this._tariffJobId=null;
    if (!this._isEditingForm()) this._render();
    try {
      const job=await this._hass.callWS({
        type:"trybatec/panel_history_job_start",
        entry_id:id,kind:"tariff_year_coverage",
      });
      this._tariffJobId=job.id;
      const coverage=await this._waitForHistoryJob(id,job,"tariff_year_coverage");
      if (coverage?.status!=="complete" || coverage?.recorder_writes!==false ||
          coverage?.energy_writes!==false) throw new Error("Incomplete history");
      const account=(this._data?.accounts||[]).find(item=>item.entry_id===id);
      if (account) trybatecMergeHistoricalObservationDates(account,coverage);
      this._tariffCoverage.set(id,{...coverage,status:"complete"});
    } catch (_) {
      this._tariffCoverage.set(id,{status:"error"});
    } finally {
      this._tariffJobId=null;this._tariffJobStatus=null;
      if (!this._isEditingForm()) this._render();
    }
  }
  _confirm(message) {
    return window.confirm(localizeTrybatecText(message,this._hass?.language));
  }
  _locale() {return this._hass?.locale?.language||this._hass?.language||"fr-FR";}
  _timeZone() {return this._hass?.config?.time_zone||"UTC";}
  _date(value,includeTime=false) {
    return trybatecDisplayDate(value,this._locale(),this._timeZone(),includeTime);
  }
  _number(value) {return trybatecDisplayNumber(value,this._locale());}
  _t(fr,en) {return /^en(?:$|[-_])/i.test(this._locale())?en:fr;}
  _syncNav() {
    const nav=this.shadowRoot.querySelector(".nav");
    const next=this.shadowRoot.querySelector(".nav-forward");
    if (!nav || !next) return;
    nav.scrollLeft=this._navScrollLeft||0;
    const active=nav.querySelector("button.active");
    if (active && active.offsetLeft+active.offsetWidth > nav.scrollLeft+nav.clientWidth)
      nav.scrollLeft=Math.max(0,active.offsetLeft+active.offsetWidth-nav.clientWidth+16);
    const update=()=>{
      this._navScrollLeft=nav.scrollLeft;
      next.hidden=nav.scrollWidth<=nav.clientWidth+3||
        nav.scrollLeft+nav.clientWidth>=nav.scrollWidth-3;
    };
    nav.addEventListener("scroll",update,{passive:true});
    update();
    if (typeof requestAnimationFrame==="function") requestAnimationFrame(update);
  }
  _click(event) {
    const btn = event.target.closest("button");
    if (!btn) return;
    if (btn.dataset.toggleMenu!==undefined) {
      this.dispatchEvent(new Event("hass-toggle-menu",{bubbles:true,composed:true}));return;
    }
    if (btn.dataset.navNext!==undefined) {
      const nav=this.shadowRoot.querySelector(".nav");
      if (nav) nav.scrollBy({left:Math.max(140,nav.clientWidth*0.75),behavior:"smooth"});
      return;
    }
    if (btn.dataset.energyMeter!==undefined || btn.dataset.energyHistory!==undefined) {
      const key=btn.dataset.energyMeter??btn.dataset.energyHistory;
      const index=this._meters().findIndex(m=>m.physical_key===key);
      if (index<0) {this._historyContextKey=null;this._tab="meters";this._query="";this._render();return;}
      this._meter=index;this._query="";
      if (btn.dataset.energyHistory!==undefined) {
        this._historyContextKey=key;this._originMeter=key;
        this._historySelected="";this._readingSelected="";this._tab="history";
      } else {
        this._historyContextKey=null;this._tab="meters";
      }
      this._render();return;
    }
    if (btn.dataset.meterContext!==undefined) {this._openMeterContext(btn.dataset.meterContext);return;}
    if (btn.dataset.historyContextClear!==undefined) {this._historyContextKey=null;this._render();return;}
    if (btn.dataset.historicalScan!==undefined) {this._loadTariffYearCoverage(true);return;}
    if (btn.dataset.tab) {this._tab=btn.dataset.tab;this._query="";this._render();if(this._tab==="tariffs")this._loadTariffYearCoverage();return;}
    if (btn.dataset.meter !== undefined) {
      this._meter=Number(btn.dataset.meter);this._historyContextKey=null;this._meterAudit=null;
      this._meterOptionDraft=null;this._meterOptionError="";this._meterOptionMessage="";
      this._energyHandoffPreview=null;this._render();return;
    }
    if (btn.dataset.account !== undefined) {
      this._account=Number(btn.dataset.account);this._meter=0;this._historyContextKey=null;this._settingsInput=null;this._durationInput=null;
      this._loggingInput=null;this._meterOptionDraft=null;this._meterOptionError="";this._meterOptionMessage="";
      this._historyPreview=null;this._historySelected="";
      this._tariffInput={year:new Date().getFullYear(),fluid:"EF",physical_key:"",rate:"",status:"provisional"};
      this._tariffHydrated=false;
      this._tariffError="";this._tariffMessage="";
      this._costPreview=null;this._costYear=null;this._costError="";
      this._render();if(this._tab==="tariffs")this._loadTariffYearCoverage();return;
    }
    if (btn.dataset.reloadPanel !== undefined) {
      if (this._unsavedInput && !this._confirm(
        "Les saisies non enregistrées seront perdues. Actualiser le panneau ?"
      )) return;
      window.location.reload();
      return;
    }
    if (btn.dataset.refresh !== undefined) {this._fetch();return;}
    if (btn.dataset.openOptions !== undefined) {window.location.assign("/config/integrations/integration/trybatec");return;}
    if (btn.dataset.openActions !== undefined) {window.location.assign("/developer-tools/action");return;}
    if (btn.dataset.openEnergy !== undefined) {window.location.assign("/energy");return;}
    if (btn.dataset.openMeter !== undefined) {this._tab="meters";this._meter=Number(btn.dataset.openMeter);this._historyContextKey=null;this._render();return;}
    if (btn.dataset.tariffYearsRetry !== undefined) {this._loadTariffYearCoverage(true);return;}
    if (btn.dataset.tariffReset !== undefined) {
      const saved=this._existingTariff();
      this._tariffInput.rate=saved?String(saved.rate):"";
      this._tariffInput.status=saved?saved.status:"provisional";
      this._tariffError="";this._tariffMessage="";
      this._unsavedInput=false;
      this._render();return;
    }
    if (btn.dataset.tariffEditYear !== undefined) {
      const year=Number(btn.dataset.tariffEditYear);
      const fluid=btn.dataset.tariffEditFluid;
      const physical_key=btn.dataset.tariffEditMeter||"";
      if (!Number.isInteger(year)||year<2000||year>2100||!["EF","ECS","CET"].includes(fluid)) return;
      this._tariffInput={year,fluid,physical_key,rate:"",status:"provisional"};
      const saved=this._existingTariff();
      if (saved) {this._tariffInput.rate=String(saved.rate);this._tariffInput.status=saved.status;}
      this._tariffError="";this._tariffMessage="";
      this._render();this.shadowRoot.querySelector("#tariff-rate")?.focus();return;
    }
    if (btn.dataset.tariffDelete !== undefined) {this._sendTariff(true);return;}
    if (btn.dataset.costPreview !== undefined) {this._previewAnnualCosts();return;}
    if (btn.dataset.meterOptionsSave !== undefined) {this._saveMeterOptions();return;}
    if (btn.dataset.meterOptionsReset !== undefined) {
      this._meterOptionDraft=null;this._meterOptionError="";this._render();return;
    }
    if (btn.dataset.logSave !== undefined) {this._saveLogLevel();return;}
    if (btn.dataset.logReset !== undefined) {
      this._loggingInput=null;this._loggingError="";this._render();return;
    }
    if (btn.dataset.settingsSave !== undefined) {this._saveSettings();return;}
    if (btn.dataset.settingsReset !== undefined) {this._settingsInput=null;this._durationInput=null;this._settingsError="";this._render();return;}
    if (btn.dataset.copyDiagnostic !== undefined) {this._copyDiagnostics();return;}
    if (btn.dataset.historyPreview !== undefined) {this._fetchHistory();return;}
    if (btn.dataset.historyCancel !== undefined) {this._cancelHistoryJob("historical_preview");return;}
    if (btn.dataset.tariffYearsCancel !== undefined) {this._cancelHistoryJob("tariff_year_coverage");return;}
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
  _isEditableInput(target) {
    return Boolean(target?.matches?.(
      'input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]), textarea'
    ));
  }
  _input(event) {
    // Native date/time inputs emit intermediate events while a segment is edited.
    // Updating the state without rebuilding their DOM node preserves all segments.
    if (this._isEditableInput(event.target)) this._change(event);
  }
  _finishFieldChange(event) {
    this._unsavedInput=true;
    if (this._isEditableInput(event.target)) {
      this._unsavedInput=true;
      // Invalidate stale previews *and* their visible confirmation controls
      // immediately, without replacing a focused date/number/text input.
      for (const [selector, stale] of [
        ["[data-version-import]", !this._versionPlan],
        ["[data-version-energy-apply]", !this._versionEnergyPlan],
        ["[data-origin-save]", !this._originPreview],
        ["[data-history-approve]", !this._historyPreview],
        ["[data-reading-approve]", !this._historyPreview],
      ]) {
        if (stale) this.shadowRoot.querySelectorAll(selector).forEach(b=>b.disabled=true);
      }
      return;
    }
    this._render();
  }
  _change(event) {
    if (event.target.dataset.query !== undefined) {
      this._query=event.target.value.trim().toLowerCase();this._render();return;
    }
    if (event.target.dataset.energyBackup!==undefined) {
      this._energyBackup=event.target.checked;this._finishFieldChange(event);return;
    }
    const readingField=event.target.dataset.readingField;
    if (readingField) {
      const value=readingField==="outside"?Boolean(event.target.checked):event.target.value;
      const fields={
        action:"_readingAction",mode:"_readingMode",date:"_readingDate",
        time:"_readingTime",reason:"_readingReason",outside:"_readingOutside"
      };
      if (fields[readingField]) this[fields[readingField]]=value;
      this._finishFieldChange(event);return;
    }
    const versionField=event.target.dataset.versionField;
    if (versionField) {
      const fields={
        importBackup:"_versionImportBackup",revision:"_versionRevision",
        retry:"_versionRetry",
        old:"_versionOld",new:"_versionNew",
        energyBackup:"_versionEnergyBackup",rollback:"_versionRollback",
        start:"_historyStart",end:"_historyEnd"
      };
      if (fields[versionField]) this[fields[versionField]]=
        event.target.type==="checkbox"?Boolean(event.target.checked):event.target.value;
      if (["old","new"].includes(versionField)) this._versionEnergyPlan=null;
      if (["start","end"].includes(versionField)) {
        this._versionPlan=null;
        this._versionVerify=null;
      }
      this._finishFieldChange(event);return;
    }
    const durationField=event.target.dataset.durationField;
    if (durationField && ["days","hours","minutes"].includes(durationField)) {
      if (!this._settingsInput) this._settingsInput={...this._current.settings};
      if (!this._durationInput)
        this._durationInput=trybatecDurationParts(this._settingsInput.poll_minutes);
      this._durationInput[durationField]=event.target.value;
      const converted=trybatecDurationMinutes(this._durationInput);
      this._settingsInput.poll_minutes=converted;
      this._finishFieldChange(event);return;
    }
    const meterOptionField=event.target.dataset.meterOptionField;
    if (meterOptionField) {
      const meter=this._meters()[this._meter];
      const row=(this._current?.meter_options||[]).find(x=>x.physical_key===meter?.physical_key);
      if (!row || !["unit","device_uuid"].includes(meterOptionField)) return;
      if (!this._meterOptionDraft || this._meterOptionDraft.physical_key!==row.physical_key)
        this._meterOptionDraft={physical_key:row.physical_key,unit:row.selected_unit,device_uuid:row.device_uuid};
      this._meterOptionDraft[meterOptionField]=event.target.value;
      this._meterOptionError="";this._finishFieldChange(event);return;
    }
    if (event.target.dataset.logLevel!==undefined) {
      this._loggingInput=event.target.value;this._loggingError="";this._finishFieldChange(event);return;
    }
    const settingsField=event.target.dataset.settingsField;
    if (settingsField) {
      if (!this._settingsInput) this._settingsInput={...this._current.settings};
      this._settingsInput[settingsField]=event.target.value;
      this._finishFieldChange(event);return;
    }
    const originField=event.target.dataset.originField;
    if (originField) {
      if (originField==="meter") this._originMeter=event.target.value;
      if (originField==="date") this._originDate=event.target.value;
      if (originField==="index") this._originIndex=event.target.value;
      if (originField==="reason") this._originReason=event.target.value;
      if (originField==="revision") this._originRevision=Boolean(event.target.checked);
      if (["meter","date","index"].includes(originField)) this._originPreview=null;
      this._originSaved="";this._finishFieldChange(event);return;
    }
    const historyField=event.target.dataset.historyField;
    if (historyField) {
      if (historyField==="start_date") this._historyStart=event.target.value;
      if (historyField==="end_date") this._historyEnd=event.target.value;
      if (["start_date","end_date"].includes(historyField)) {
        this._historyPreview=null;
        this._historySelected="";
        this._readingSelected="";
      }
      if (historyField==="mode") this._historyMode=event.target.value;
      if (historyField==="reason") this._historyReason=event.target.value;
      this._finishFieldChange(event);return;
    }
    const field=event.target.dataset.tariffField;
    if (field) {
      this._tariffInput[field]=event.target.value;
      this._tariffError="";this._tariffMessage="";
      if (field==="fluid") this._tariffInput.physical_key="";
      if (field==="year") {this._costPreview=null;this._costYear=null;this._costError="";}
      if (["year","fluid","physical_key"].includes(field)) {
        const item=this._existingTariff();
        this._tariffInput.rate=item?String(item.rate):"";
        this._tariffInput.status=item?item.status:"provisional";
      }
      if (["year","rate","fluid","physical_key","status"].includes(field)) {
        this._costPreview=null;this._costYear=null;
      }
      // A typed year must refresh saved values and hints without replacing
      // the focused native number element (keyboard and mobile safety).
      if (field==="year") this._syncTariffSelection();
      this._finishFieldChange(event);
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
  _tariffEffectiveText() {
    const a=this._current, f=this._tariffInput;
    if (!a) return "";
    const effective=trybatecSavedEffectiveTariff(a,f.year,f.fluid,f.physical_key);
    const unit=f.fluid==="CET"?"EUR/kWh":"EUR/m³";
    return effective ?
      this._t("Tarif effectif enregistré","Saved effective rate")+": "+
        this._number(effective.rate)+" "+unit+" · "+
        this._t(effective.origin==="meter_override"?"Spécifique au compteur":"Commun au fluide",
          effective.origin==="meter_override"?"Meter-specific":"Default fluid rate")+" · "+
        this._t(effective.status==="approved"?"Approuvé":"Provisoire",
          effective.status==="approved"?"Approved":"Provisional"):
      this._t("Aucun tarif enregistré pour cet exercice.","No rate saved for this year.");
  }
  _syncTariffSelection() {
    const root=this.shadowRoot;
    const rate=root.querySelector("#tariff-rate");
    if (rate) rate.value=this._tariffInput.rate;
    const status=root.querySelector("#tariff-status");
    if (status) status.value=this._tariffInput.status;
    const deletion=root.querySelector("[data-tariff-delete]");
    if (deletion) deletion.disabled=!this._existingTariff()||this._tariffBusy;
    const effective=root.querySelector("[data-tariff-effective]");
    if (effective) effective.textContent=this._tariffEffectiveText();
  }
  _submit(event) {
    if (event.target.dataset.tariffForm !== undefined) {
      event.preventDefault();this._sendTariff(false);
    }
  }
  async _sendTariff(remove) {
    if (this._tariffBusy || !this._current) return;
    const f=this._tariffInput;
    const year=Number(f.year);
    if (!Number.isInteger(year) || year<2000 || year>2100) {
      this._tariffError="Exercice invalide : choisissez une année entre 2000 et 2100.";
      this._render();return;
    }
    const raw=String(f.rate).trim();
    const rate=Number(raw);
    if (!remove && (!/^[0-9]+(?:\.[0-9]{1,6})?$/.test(raw) ||
        !Number.isFinite(rate) || rate<0 || rate>1000000)) {
      this._tariffError="Le tarif doit être compris entre 0 et 1 000 000, avec six décimales au maximum.";
      this._render();return;
    }
    const message=remove?
      "Supprimer ce tarif ? Le tarif commun sera de nouveau applicable à ce compteur, si défini.":
      "Enregistrer ce tarif annuel ? Les historiques Recorder et les préférences Énergie resteront inchangés.";
    if (!this._confirm(message)) return;
    this._tariffBusy=true;this._tariffError="";this._tariffMessage="";this._render();
    let confirmedSaved=false;
    try {
      const request={
        type:"trybatec/panel_tariff_change",
        entry_id:this._current.entry_id,
        year,fluid:f.fluid,status:f.status,
        remove:Boolean(remove),confirmed:true,
        expected_fingerprint:this._current.tariff_fingerprint,
      };
      if (f.physical_key) request.physical_key=f.physical_key;
      if (!remove) request.rate=rate;
      const result=await this._hass.callWS(request);
      if (result?.status!=="saved") throw new Error("Tariff write not confirmed");
      confirmedSaved=true;
      this._data=await this._hass.callWS({type:"trybatec/panel_snapshot"});
      this._tariffMessage=remove?"Tarif retiré.":"Tarif enregistré.";
      this._costPreview=null;this._costYear=null;
      this._tariffInput.rate="";
      this._tariffInput.status="provisional";
      const existing=this._existingTariff();
      if (existing) {
        this._tariffInput.rate=String(existing.rate);
        this._tariffInput.status=existing.status;
      }
      this._unsavedInput=false;
    } catch (_) {
      if (confirmedSaved) {
        this._tariffMessage="Tarif enregistré, mais actualisation impossible : actualisez le panneau pour vérifier la valeur.";
        this._costPreview=null;this._costYear=null;
        this._unsavedInput=false;
      } else {
        this._tariffError="Modification refusée : vérifiez les données et actualisez les tarifs avant de réessayer.";
      }
    } finally {
      this._tariffBusy=false;this._render();
    }
  }
  _header() {
    const version=this._data?.version;
    const label=typeof version==="string" && /^[0-9][0-9A-Za-z.+-]{0,31}$/.test(version)?
      '<span class="badge" title="Version installée">v'+safe(version)+'</span>':
      '<span class="badge">Bêta</span>';
    const cache=typeof version==="string"?("?v="+encodeURIComponent(version)):"";
    return '<header class="heading"><button type="button" class="menu-toggle" data-toggle-menu aria-label="Ouvrir le menu Home Assistant"><ha-icon icon="mdi:menu" aria-hidden="true"></ha-icon></button><div class="mark"><img src="/api/trybatec_panel/logo.png'+cache+'" alt="Trybatec" loading="eager"></div>' +
      '<div><h1>Trybatec '+label+'</h1>' +
      '<p class="headline-sub">Gestion des compteurs, historiques, tarifs et énergie</p></div></header>';
  }
  _nav() {
    return '<div class="nav-wrap"><nav class="nav" aria-label="Navigation Trybatec">' +
      TABS.map(tab=>'<button type="button" data-tab="'+tab[0]+'" aria-current="'+(this._tab===tab[0]?'page':'false')+
        '" class="'+(this._tab===tab[0]?'active':'')+'"><ha-icon icon="'+tab[2]+'" aria-hidden="true"></ha-icon><span>'+tab[1]+'</span></button>').join("")+
      '</nav><button type="button" class="nav-forward" data-nav-next aria-label="Afficher les autres onglets"><ha-icon icon="mdi:chevron-right" aria-hidden="true"></ha-icon></button></div>';
  }
  _heading(title,sub,button) {
    return '<div class="intro"><div><h2>'+safe(title)+'</h2><p class="muted">'+safe(sub)+'</p></div>'+(button||"")+'</div>';
  }
  _meterName(m) {return FLUID[m.fluid] || "Compteur"; }
  _stat(number,label,icon) {
    return '<article class="card stat"><ha-icon icon="'+icon+'"></ha-icon><div><strong>'+safe(number)+'</strong><span>'+safe(label)+'</span></div></article>';
  }
  _badge(m) {
    const labels={en_service:this._t("En service","Active"),
      depose:this._t("Déposé","Retired"),
      inconnu:this._t("Statut à vérifier","Status to verify")};
    return '<span class="pill '+(m.status==="en_service"?"on":m.status==="depose"?"off":"unknown")+'">'+labels[m.status]+'</span>';
  }
  _meters() {return this._current ? this._current.meters : [];}
  _counts() {
    const values={en_service:0,depose:0,inconnu:0};
    this._meters().forEach(m=>{if (values[m.status]!==undefined)values[m.status]++;});
    return values;
  }
  _meterRow(m,i,action) {
    const fluidClass=FLUID_CLASS[m.fluid]||"";
    const fluidIcon=FLUID_ICON[m.fluid]?
      '<ha-icon class="fluid-icon" icon="'+FLUID_ICON[m.fluid]+'" aria-hidden="true"></ha-icon>':"";
    const line='<span class="meter-name">'+fluidIcon+safe(this._meterName(m))+' · '+safe(m.serial)+'</span>'+
      '<span class="meter-sub">'+safe(m.lot||"Lot non renseigné")+' · '+safe(m.unit||"Unité à vérifier")+
      ' · '+(m.status==="depose"?this._t("Déposé","Retired"):
        m.status==="en_service"?this._t("En service","Active"):
          this._t("Statut inconnu","Unknown status"))+'</span>';
    if (action==="detail") {
      const selected=i===this._meter;
      return '<div class="meter-row"><button type="button" class="'+safe(fluidClass)+(selected?" selected":"")+
        '" aria-pressed="'+(selected?"true":"false")+'" data-meter="'+i+'">'+line+
        (selected?'<ha-icon class="selected-indicator" icon="mdi:check-circle" aria-hidden="true"></ha-icon>':"")+
        '</button></div>';
    }
    return '<div class="meter-row"><button type="button" class="'+safe(fluidClass)+
      '" data-open-meter="'+i+'">'+line+'</button></div>';
  }
  _readinessView(a) {
    const t=(fr,en)=>this._t(fr,en);
    const meters=Array.isArray(a.meters)?a.meters:[];
    const active=meters.filter(m=>m.status==="en_service");
    const retired=meters.filter(m=>m.status==="depose");
    const missingDates=retired.filter(m=>!m.first_observed_at||!m.last_source_observed_at);
    const ledger=a.ledger||{};
    const verified=(ledger.series||[]).flatMap(row=>
      (row.versions||[]).filter(v=>v.state==="verified"||v.state==="archived"));
    const energySources=(this._data?.energy?.sources||[]).filter(src=>
      typeof src.statistic_id==="string"&&src.statistic_id.startsWith("trybatec:"));
    const tariffsConfigured=Object.keys(a.tariffs||{}).length+
      Object.keys(a.meter_tariffs||{}).length>0;
    const activeReady=a.data_loaded===true && active.length>0 && active.every(m=>
      m.last_index!==null && m.last_index!==undefined && m.unit_verified);
    const conflict=(a.meter_options||[]).some(o=>
      o.source_unit==="conflict" &&
      active.some(m=>m.physical_key===o.physical_key));
    const check=(kind,title,description,tab,action)=>{
      const className=kind==="passed"?"ok":kind==="issue"?"issue":kind==="na"?"na":"pending";
      const icon={passed:"mdi:check-circle-outline",issue:"mdi:alert-outline",
        unverified:"mdi:help-circle-outline",na:"mdi:minus-circle-outline"}[kind];
      const label={passed:t("Conforme","Passed"),issue:t("Anomalie détectée","Issue detected"),
        unverified:t("Non vérifié","Not verified"),na:t("Non applicable","Not applicable")}[kind];
      return '<div class="readiness-row '+className+'"><ha-icon icon="'+icon+
        '" aria-hidden="true"></ha-icon><div><strong>'+safe(title)+'</strong>'+
        '<p class="muted">'+safe(label)+'</p><p>'+safe(description)+'</p>'+
        (action?'<div class="actions"><button type="button" class="secondary" data-tab="'+
          safe(tab)+'">'+safe(action)+'</button></div>':"")+'</div></div>';
    };
    const feature=(title,description,tab,action)=>
      '<div class="readiness-row"><ha-icon icon="mdi:information-outline" aria-hidden="true"></ha-icon>'+
      '<div><strong>'+safe(title)+'</strong><p>'+safe(description)+'</p>'+
      '<div class="actions"><button type="button" class="secondary" data-tab="'+
      safe(tab)+'">'+safe(action)+'</button></div></div></div>';
    const sourceStatus=active.length===0?"na":conflict?"issue":activeReady?"passed":"unverified";
    const retiredCoverage=this._tariffCoverage?.get(a.entry_id);
    // An account-wide scan does not prove a particular retired meter was observed.
    // Require exact physical identity and two verified supplier bounds for each.
    const retiredBoundsVerified=retiredCoverage?.status==="complete" &&
      Array.isArray(retiredCoverage.meters) && retired.every(m=>{
        const bound=retiredCoverage.meters.find(row=>
          row.physical_key===m.physical_key);
        return Boolean(bound?.first_observed_at && bound?.last_source_observed_at);
      });
    const retiredStatus=retired.length===0?"na":
      retiredBoundsVerified && missingDates.length===0?"passed":"unverified";
    const sourceText=active.length===0?t("Aucun compteur en service dans cet inventaire.",
      "No active meters in this inventory."):
      conflict?t("Une contradiction d’unité source a été signalée pour un compteur en service.",
      "A source-unit contradiction was reported for an active meter."):
      activeReady?t("Relevés courants présents et unités renseignées ; ce contrôle n’est pas un audit exhaustif.",
      "Current readings and units are present; this is not an exhaustive audit."):
      t("Un ou plusieurs relevés courants ou unités restent à vérifier.",
      "One or more current readings or units require verification.");
    const retiredText=retired.length===0?t("Aucun compteur déposé connu.",
      "No known retired meter."):missingDates.length===0?
      (retiredStatus==="passed"?t(
        "Bornes vérifiées par une analyse historique complète ; la continuité des relevés demeure un contrôle distinct.",
        "Boundaries verified by a complete historical scan; reading continuity is a separate check."
      ):t(
        "Bornes connues dans l’aperçu, mais recherche historique complète non vérifiée.",
        "Dates exist in the snapshot, but a complete historical scan has not been verified."
      )):
      String(missingDates.length)+t(" compteur(s) déposé(s) sans bornes complètes dans cet aperçu. Cela ne prouve pas la perte de relevés.",
        " retired meter(s) lack complete boundaries in this snapshot. This does not prove loss of readings.");
    return '<section class="card" style="margin-bottom:20px" aria-label="'+
      safe(t("État de la configuration","Configuration status"))+'">'+
      '<h3>'+safe(t("État de la configuration","Configuration status"))+'</h3>'+
      '<p class="muted" style="margin-bottom:16px">'+safe(t(
        "Les contrôles constatés sont séparés des fonctionnalités facultatives et des diagnostics avancés.",
        "Verified checks are separate from optional workflows and advanced diagnostics."))+'</p>'+
      '<div class="readiness-list">'+
      check(sourceStatus,t("Synchronisation des compteurs","Meter synchronization"),
        sourceText,"meters",activeReady?"":t("Vérifier les compteurs","Review meters"))+
      check(retiredStatus,t("Historique des compteurs déposés","Retired-meter history"),
        retiredText,"meters",retiredStatus==="na"||retiredStatus==="passed"?"":t(
          "Rechercher les relevés historiques","Search historical readings"))+
      '</div><div class="readiness-optional"><h4>'+safe(t(
        "Parcours disponibles selon vos besoins","Workflows available when needed"))+'</h4>'+
      feature(t("Versions historiques Recorder","Recorder history versions"),
        verified.length?String(verified.length)+t(" version(s) historisée(s) vérifiée(s). Import(s) à vérifier : ",
          " verified historical version(s). Pending imports: ")+String(ledger.pending||0)+"."
          :t("Aucune version Recorder vérifiée. La préparation et l’importation sont facultatives.",
             "No verified Recorder version. Preparing and importing one is optional."),
        "energy",t("Examiner Recorder","Review Recorder"))+
      feature(t("Sources Trybatec dans Énergie","Trybatec Energy sources"),
        energySources.length?String(energySources.length)+t(
          " source(s) identifiée(s), sans validation exhaustive du double comptage.",
          " source(s) found, without an exhaustive double-counting audit.") :
          t("Aucune source Trybatec configurée. La première activation utilise un parcours distinct.",
            "No Trybatec source configured. First activation uses a separate workflow."),
        "energy",t("Consulter Énergie","Review Energy"))+
      feature(t("Tarifs annuels (facultatifs)","Annual tariffs (optional)"),
        tariffsConfigured?t("Tarifs présents ; leur couverture reste à examiner.",
          "Tariffs are present; their coverage still needs review."):
          t("Aucun tarif : seules les estimations de coûts correspondantes sont indisponibles.",
            "No tariffs: only the corresponding cost estimates are unavailable."),
        "tariffs",t("Consulter les tarifs","Review tariffs"))+
      '</div><div class="readiness-optional"><h4>'+safe(t(
        "Diagnostics avancés","Advanced diagnostics"))+'</h4>'+
      feature(t("Audit des identités techniques","Technical identity audit"),
        t("Audit non exhaustif. Les anciennes entités ne sont jamais déclarées supprimables sur ce seul constat.",
          "The audit is not exhaustive. Old entities are never considered safe to delete on this evidence alone."),
        "diagnostics",t("Consulter les diagnostics","Review diagnostics"))+
      '</div></section>';
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
      this._stat(suspects.length,"Entités indisponibles détectées","mdi:alert-circle-outline")+
      this._stat(Object.keys(a.tariffs).length,"Exercices tarifaires","mdi:calendar-check-outline")+
      '</section>'+this._readinessView(a)+'<div class="columns">'+groups.map((group,index)=>
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
    if (!this._confirm(
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
  _meterOptionsEditor(m) {
    const option=(this._current?.meter_options||[]).find(row=>
      row.physical_key===m.physical_key);
    if (!option) return '<section class="line" style="margin-top:16px">'+
      '<h3>Unité et identifiant du compteur</h3>'+
      '<p class="muted">Ce compteur ne dispose pas encore d’une identité source éligible à une modification. Lancez une analyse historique ou utilisez le menu natif de secours.</p>'+
      '<div class="actions"><button type="button" class="secondary" data-tab="history">Analyser l’historique</button>'+
      '<button type="button" class="secondary" data-open-options>Options natives de secours</button></div></section>';
    const draft=this._meterOptionDraft?.physical_key===option.physical_key?
      this._meterOptionDraft:{unit:option.selected_unit,device_uuid:option.device_uuid};
    const source=option.source_unit;
    const conflicting=source==="conflict"||source==="unverified";
    const origin={
      manual:"Unité enregistrée manuellement",
      api:"Unité déterminée par l’API",
      chart_proposal:"Proposition issue du graphique, à confirmer",
      unverified:"Unité non vérifiée"
    }[option.selection_origin]||"Origine à vérifier";
    return '<section class="line" style="margin-top:16px" aria-label="Unité et identifiant du compteur">'+
      '<h3>Unité et identifiant du compteur</h3>'+
      '<p class="muted">Paramètres propres à ce compteur physique. Le graphique ne prouve pas l’unité des index sources.</p>'+
      '<div class="detail-grid">'+
      '<div><span class="smallhead">Unité explicitement fournie par l’API</span><strong>'+safe(source||"Non détectée")+'</strong></div>'+
      '<div><span class="smallhead">Unité de référence du graphique</span><strong>'+safe(option.chart_unit||"Non disponible")+'</strong></div>'+
      '<div><span class="smallhead">Origine de la présélection</span><strong>'+safe(origin)+'</strong></div></div>'+
      '<div class="form-grid meter-options-grid">'+
      '<div><label for="meter-unit-choice">Unité source du compteur</label>'+
      '<select id="meter-unit-choice" data-meter-option-field="unit">'+
      '<option value="unverified" '+(draft.unit==="unverified"?"selected":"")+'>Inconnue / non vérifiée</option>'+
      (option.allowed_units||[]).map(unit=>
        '<option value="'+safe(unit)+'" '+(draft.unit===unit?"selected":"")+
        (conflicting?" disabled":"")+'>'+safe(unit)+'</option>').join("")+'</select></div>'+
      '<div><label for="meter-device-uuid">UUID du dispositif Trybatec (facultatif)</label>'+
      '<input id="meter-device-uuid" type="text" maxlength="36" spellcheck="false" data-meter-option-field="device_uuid" value="'+
      safe(draft.device_uuid||"")+'" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"></div></div>'+
      (conflicting?'<div class="notice warning">L’API signale une unité conflictuelle ou inconnue : seule la sélection « Inconnue » est autorisée tant que la source n’est pas clarifiée.</div>':"")+
      (this._meterOptionError?'<div role="alert" class="notice warning">'+safe(this._meterOptionError)+'</div>':"")+
      (this._meterOptionMessage?'<div role="status" class="notice">'+safe(this._meterOptionMessage)+'</div>':"")+
      '<div class="actions"><button type="button" class="primary" data-meter-options-save '+
      (this._meterOptionBusy?"disabled":"")+'>Enregistrer ce compteur</button>'+
      '<button type="button" class="secondary" data-meter-options-reset>Annuler les modifications</button></div>'+
      '<p class="muted">Aucun index source, historique Recorder ou tableau Énergie n’est modifié. Un choix confirmé est associé uniquement à ce compteur.</p></section>';
  }
  async _saveMeterOptions() {
    if (!this._current || this._meterOptionBusy) return;
    const meter=this._meters()[this._meter];
    const option=(this._current.meter_options||[]).find(x=>
      x.physical_key===meter?.physical_key);
    if (!option) return;
    const draft=this._meterOptionDraft?.physical_key===option.physical_key?
      this._meterOptionDraft:{unit:option.selected_unit,device_uuid:option.device_uuid};
    if (!this._confirm(
      "Enregistrer l’unité et l’UUID pour ce compteur physique uniquement ?"+
      "\n\n"+meter.fluid+" · "+meter.serial+
      "\nUnité choisie : "+draft.unit+
      "\n\nUne unité proposée d’après un graphique ne prouve pas l’échelle des index."+
      "\nNi les relevés source, ni Recorder, ni Énergie ne seront modifiés."
    )) return;
    this._meterOptionBusy=true;this._meterOptionError="";this._meterOptionMessage="";this._render();
    try {
      const response=await this._hass.callWS({
        type:"trybatec/panel_meter_options_save",
        entry_id:this._current.entry_id,
        physical_key:option.physical_key,
        unit:draft.unit,device_uuid:draft.device_uuid||"",
        expected_fingerprint:this._current.tariff_fingerprint,confirm:true
      });
      if (response.source_indices_unchanged!==true || response.recorder_writes!==false ||
          response.energy_writes!==false) throw new Error("Unverified save result");
      this._data=await this._hass.callWS({type:"trybatec/panel_snapshot"});
      this._meterOptionDraft=null;
      this._meterOptionMessage="Unité et UUID enregistrés dans les options Home Assistant existantes.";
    } catch (_) {
      this._meterOptionError="Enregistrement refusé ou recharge en cours. Actualisez les données et vérifiez l’unité source et l’UUID.";
    } finally {this._meterOptionBusy=false;this._render();}
  }

  _statusIndicator(kind, value) {
    const icons={
      passed:"mdi:check-circle-outline",issue:"mdi:alert-outline",
      unverified:"mdi:help-circle-outline",na:"mdi:minus-circle-outline",
      known:"mdi:information-outline"
    };
    const choice=Object.hasOwn(icons,kind)?kind:"unverified";
    return '<span class="status-indicator '+choice+'"><ha-icon icon="'+
      icons[choice]+'" aria-hidden="true"></ha-icon><span>'+safe(value)+
      '</span></span>';
  }
  _meterField(label, value, kind="known", context="", action="", explanation="") {
    return '<div class="meter-detail-field"><span class="smallhead">'+safe(label)+'</span>'+
      '<strong>'+this._statusIndicator(kind,value)+'</strong>'+
      (explanation?'<p class="field-context">'+safe(explanation)+'</p>':"")+
      (context?'<button type="button" class="secondary context-button" data-meter-context="'+
        safe(context)+'"><ha-icon icon="mdi:arrow-right-circle-outline" aria-hidden="true"></ha-icon>'+
        safe(action)+'</button>':"")+'</div>';
  }
  _openMeterContext(action) {
    const meter=this._meters()[this._meter];
    if (!meter) return;
    if (action==="history") {
      this._historyContextKey=meter.physical_key;
      this._originMeter=meter.physical_key;
      this._historySelected="";this._readingSelected="";
      this._tab="history";this._query="";
      this._render();
      this.shadowRoot.querySelector("[data-history-preview]")?.focus();
      return;
    }
    // Focus the scan button, but do not start supplier traffic on navigation.
    if (action==="scan") {
      this._tab="meters";this._render();
      const button=this.shadowRoot.querySelector("[data-historical-scan]");
      button?.focus();button?.scrollIntoView?.({block:"nearest"});
      return;
    }
    if (action==="unit") {
      this._tab="meters";this._render();
      const input=this.shadowRoot.querySelector("[data-meter-option-field='unit']");
      const fallback=this.shadowRoot.querySelector("[data-open-options]");
      (input||fallback)?.focus();
      (input||fallback)?.scrollIntoView?.({block:"nearest"});
    }
  }

  _meterDetail(m) {
    if(!m) return '<div class="card empty">Sélectionnez un compteur pour consulter ses informations.</div>';
    const account=this._current;
    const related=account.entities.filter(e=>
      e.unique_id && (e.unique_id.includes("_"+m.serial+"_")||e.unique_id.endsWith("_"+m.serial+"_index")));
    const option=(account.meter_options||[]).find(row=>row.physical_key===m.physical_key);
    const coverage=this._tariffCoverage.get(account.entry_id);
    // A complete account-level query is not evidence for every physical meter.
    const meterCoverage=coverage?.status==="complete" && Array.isArray(coverage.meters)?
      coverage.meters.find(row=>row.physical_key===m.physical_key):null;
    const checkedHistory=Boolean(meterCoverage);
    const unmatchedAccountScan=coverage?.status==="complete" && !checkedHistory;
    const unavailableObservation=checkedHistory?
      this._t("Date non établie dans les données consultées",
        "Date not established from consulted data"):
      this._t("Non vérifié","Not verified");
    const historyExplanation=unmatchedAccountScan?
      this._t("Analyse globale terminée, sans preuve attribuable à ce compteur physique.",
        "Account-wide scan finished without evidence linked to this physical meter."):
      this._t("Analyse historique effectuée : aucune date retrouvée pour ce compteur dans le périmètre consulté.",
        "Historical scan complete: no date found for this meter in the queried scope.");
    const unitOrigin=option?.selection_origin==="manual"?
      this._t("Origine : unité enregistrée manuellement","Source: manually recorded unit"):
      option?.selection_origin==="api"?
      this._t("Origine : unité explicitement fournie par l’API","Source: unit explicitly supplied by API"):
      option?.selection_origin==="chart_proposal"?
      this._t("Origine : proposition du graphique, à confirmer","Source: chart proposal, pending confirmation"):
      this._t("Origine de l’unité non vérifiée","Unit provenance not verified");
    const conflict=option?.source_unit==="conflict";
    return '<div class="card fluid-surface '+safe(FLUID_CLASS[m.fluid]||"")+'"><div class="panel-title"><h2 class="meter-title">'+
      (FLUID_ICON[m.fluid]?'<ha-icon icon="'+FLUID_ICON[m.fluid]+'" aria-hidden="true"></ha-icon>':'')+
      safe(this._meterName(m))+' · '+safe(m.serial)+'</h2>'+
      this._badge(m)+'</div><p class="muted">Compteur physique · '+safe(m.source==="live_api"?"Relevé par l’API":"Archivé localement")+'</p>'+
      '<div class="detail-grid">'+
      '<div><span class="smallhead">Lot</span><strong>'+safe(m.lot||"Non renseigné")+'</strong></div>'+
      '<div><span class="smallhead">Fluide</span><strong>'+safe(FLUID[m.fluid]||"Inconnu")+'</strong></div>'+
      '<div><span class="smallhead">Unité</span><strong>'+safe(m.unit||"À vérifier")+'</strong></div>'+
      this._meterField(this._t("Dernier index disponible","Latest available index"),
        m.last_index===null||m.last_index===undefined?
          (m.status==="depose"?this._t("Sans index courant","No current index"):
            this._t("Non vérifié","Not verified")):this._number(m.last_index),
        m.last_index!==null&&m.last_index!==undefined?"known":m.status==="depose"?"na":"unverified",
        "history",this._t("Consulter l'historique","Review history"),
        m.status==="depose"?this._t(
          "Compteur déposé : vérifier séparément les éventuels index historiques.",
          "Retired meter: check historical readings separately."):"")+
      this._meterField(this._t("Première observation connue","First known observation"),
        this._date(m.first_observed_at)||unavailableObservation,
        m.first_observed_at?"known":"unverified",
        m.first_observed_at?"":"scan",m.first_observed_at?"":this._t(
          "Rechercher les relevés","Search readings"),
        !m.first_observed_at&&(checkedHistory||unmatchedAccountScan)?historyExplanation:"")+
      this._meterField(this._t("Dernière observation source","Last source observation"),
        this._date(m.last_source_observed_at)||unavailableObservation,
        m.last_source_observed_at?"known":"unverified",
        m.last_source_observed_at?"":"scan",m.last_source_observed_at?"":this._t(
          "Rechercher les relevés","Search readings"),
        !m.last_source_observed_at&&(checkedHistory||unmatchedAccountScan)?historyExplanation:"")+
      this._meterField(this._t("Date du dernier index exploitable","Date of latest usable index"),
        this._date(m.last_observed_at)||this._t("Non vérifié","Not verified"),
        m.last_observed_at?"known":"unverified",
        m.last_observed_at?"":"history",m.last_observed_at?"":this._t(
          "Analyser les index","Review readings"))+
      (m.status==="depose" && m.historical_last_index_raw!==undefined?
        '<div><span class="smallhead">Dernier index historique source (non qualifié)</span><strong>'+
        safe(this._number(m.historical_last_index_raw))+
        '</strong><span class="muted">'+safe(this._date(m.historical_last_index_at))+
        (m.historical_index_conflict?" · conflit de relevés à vérifier":" · relevé historique à qualifier")+
        '</span></div>':"")+
      this._meterField(this._t("Statut de l’unité","Unit status"),
        m.unit_verified?this._t("Vérifiée","Verified"):
          conflict?this._t("Conflit d’unité","Unit conflict"):
          this._t("À vérifier","Not verified"),
        m.unit_verified?"passed":conflict?"issue":"unverified",
        "unit",m.unit_verified?this._t("Consulter l’unité","View unit"):
          this._t("Vérifier l’unité","Verify unit"),unitOrigin)+
      '</div><h3>Relations techniques Home Assistant</h3>'+
      '<p class="muted">Les identités techniques ne doivent pas être supprimées tant que leurs références sont inconnues.</p>'+
      (related.length?related.map(e=>'<div class="entity"><span class="mono">'+safe(e.entity_id)+'</span> '+
      '<span class="pill '+(e.state==="unavailable"?"audit":"on")+'">'+safe(e.state)+'</span> '+
      '<button type="button" class="secondary" data-entity-audit="'+safe(e.entity_id)+'" '+
      (this._meterAuditBusy?"disabled":"")+'>Auditer</button></div>').join(""):
      '<div class="empty">Aucune association vérifiée par identifiant technique. Consultez l’audit des entités.</div>')+
      '<div class="actions"><button type="button" class="secondary" data-meter-context="history">'+
      safe(this._t("Historique & lissage","History & smoothing"))+'</button>'+
      '<button type="button" class="secondary" data-tab="diagnostics">Auditer les identifiants</button></div>'+
      this._auditDetails(m)+this._meterHistoricalMetrics(m)+this._meterOptionsEditor(m)+'</div>';
  }
  _meterHistoricalMetrics(m) {
    const item=(this._historyPreview?.history_summary?.by_meter||[]).find(row=>
      row.physical_key===m.physical_key);
    if (!item) return "";
    return '<section class="line" style="margin-top:16px"><h3>Contrôles historiques de ce compteur</h3>'+
      '<p class="muted">Indicateurs issus du dernier aperçu ; un écart ou conflit n’est pas nécessairement une erreur de mesure.</p>'+
      '<div class="detail-grid">'+
      '<div><span class="smallhead">Intervalles lacunaires</span><strong>'+safe(item.gaps)+'</strong></div>'+
      '<div><span class="smallhead">Baisses d’index</span><strong>'+safe(item.decreases)+'</strong></div>'+
      '<div><span class="smallhead">Conflits de relevés</span><strong>'+safe(item.conflicts)+'</strong></div>'+
      '<div><span class="smallhead">Première observation</span><strong>'+safe(this._date(item.first_observed_at))+'</strong></div>'+
      '<div><span class="smallhead">Dernière observation</span><strong>'+safe(this._date(item.last_observed_at))+'</strong></div>'+
      '<div><span class="smallhead">Unité de l’index source</span><strong>'+safe(item.source_unit||"Non confirmée")+'</strong></div></div></section>';
  }
  _meterTimeline() {
    const groups=this._current?.physical_meter_timeline||[];
    if (!groups.length) return '';
    return '<section class="card" style="margin-top:16px"><h3>Chronologie des compteurs physiques</h3>'+
      '<p class="muted">Par logement et fluide, fondée uniquement sur les observations. Les dates exactes de remplacement ne sont pas déduites.</p>'+
      groups.map(g=>'<div class="line '+safe(FLUID_CLASS[g.fluid]||"")+'" style="margin-top:12px;border-inline-start:4px solid var(--fluid-fg,var(--trybatec-section-border))"><strong>'+
        safe(FLUID[g.fluid]||g.fluid)+' · '+safe(g.lot||'Lot inconnu')+'</strong> '+
        '<span class="badge">'+safe(g.count)+' compteur(s)</span>'+
        '<div class="list" style="margin-top:10px">'+g.meters.map(m=>
          '<div class="meter-row"><span class="meter-name">'+safe(m.serial)+'</span> '+
          '<span class="pill '+(m.status==='en_service'?'on':m.status==='depose'?'off':'unknown')+'">'+
          safe(m.status==='en_service'?'En service':m.status==='depose'?'Déposé':'Statut inconnu')+'</span>'+
          '<div class="muted">Première observation : '+safe(this._date(m.first_observed_at)||'Non connue')+
          ' · Dernière observation source : '+safe(this._date(m.last_source_observed_at)||'Non connue')+'</div></div>'
        ).join('')+'</div></div>').join('')+
      '<div class="notice">Un compteur déposé est un appareil historique. Une entité technique indisponible ne constitue pas un compteur supplémentaire. Aucune date de remplacement n’est inventée.</div></section>';
  }

  _metersPage() {
    const meters=this._meters();
    const indexed=meters.map((m,i)=>({m,i})).filter(x=>!this._query||[
      x.m.serial,x.m.lot,FLUID[x.m.fluid],x.m.status].some(v=>String(v||"").toLowerCase().includes(this._query)));
    const missing=meters.filter(m=>m.status==="depose" &&
      (!m.first_observed_at || !m.last_source_observed_at));
    const coverage=this._tariffCoverage.get(this._current.entry_id);
    // Missing dates are unverified, not a proven anomaly or warning.
    const historyHelp='<div class="notice" role="status">'+
      (coverage?.status==="loading"?"Lecture en cours des relevés historiques du fournisseur…":
       coverage?.status==="error"?"Vérification historique incomplète : aucun relevé inventé.":
       coverage?.status==="complete"?(missing.length?String(missing.length)+
         " compteur(s) déposé(s) restent sans observations vérifiées.":"Bornes historiques issues des relevés du fournisseur."):
       String(missing.length)+" compteur(s) déposé(s) sans dates historiques confirmées dans l’inventaire actuel.")+
      (coverage?.status!=="loading"?'<div class="actions"><button type="button" class="secondary" data-historical-scan>'+
       'Rechercher les relevés historiques</button></div>':"")+'</div>';
    return this._heading("Compteurs","Inventaire physique : en service, déposés, ou statut non confirmé.")+
      historyHelp+'<div class="split" style="margin-top:16px"><section class="card"><input class="search" data-query placeholder="Rechercher un compteur (numéro, lot, fluide…)" value="'+safe(this._query)+'" aria-label="Rechercher un compteur">'+
      '<div class="scroll">'+indexed.map(x=>this._meterRow(x.m,x.i,"detail")).join("")+'</div>'+
      (!indexed.length?'<div class="empty">Aucun compteur correspondant. L’inventaire historique peut nécessiter une prévisualisation préalable.</div>':"")+
      '</section>'+this._meterDetail(meters[this._meter])+'</div>'+this._meterTimeline();
  }
  async _waitForHistoryJob(entryId, job, kind) {
    if (!job?.id || job.status!=="running") throw new Error("Unverified history job");
    while (true) {
      const state=await this._hass.callWS({
        type:"trybatec/panel_history_job_status",entry_id:entryId,job_id:job.id,
      });
      if (!state || state.id!==job.id) throw new Error("Unknown history job");
      if (state.status==="complete") {
        if (state.complete!==true || state.recorder_writes!==false ||
            state.energy_writes!==false || !state.result)
          throw new Error("Incomplete history job");
        return state.result;
      }
      if (state.status!=="running") throw new Error("History job interrupted");
      if (kind==="historical_preview") this._historyJobStatus=state;
      else this._tariffJobStatus=state;
      if (!this._isEditingForm()) this._render();
      await new Promise(resolve=>window.setTimeout(resolve,1500));
    }
  }
  async _cancelHistoryJob(kind) {
    const jobId=kind==="historical_preview"?this._historyJobId:this._tariffJobId;
    if (!jobId || !this._current || !this._confirm(
      this._t("Interrompre la lecture historique en cours ?",
        "Cancel the current historical read?")
    )) return;
    try {
      await this._hass.callWS({
        type:"trybatec/panel_history_job_cancel",
        entry_id:this._current.entry_id,job_id:jobId,confirm:true,
      });
    } catch (_) {
      if (kind==="historical_preview")
        this._historyError=this._t("Annulation non confirmée par Home Assistant.",
          "Cancellation not confirmed by Home Assistant.");
    }
    if (!this._isEditingForm()) this._render();
  }
  async _fetchHistory() {
    if (this._historyBusy || !this._current) return;
    const entryId=this._current.entry_id;
    this._historyBusy=true;
    this._historyError="";this._historyMessage="";this._historyPreview=null;
    this._historySelected="";this._historyJobStatus=null;this._render();
    try {
      const job=await this._hass.callWS({
        type:"trybatec/panel_history_job_start",
        entry_id:entryId,kind:"historical_preview",
        start_date:this._historyStart,end_date:this._historyEnd,
      });
      this._historyJobId=job.id;
      const result=await this._waitForHistoryJob(entryId,job,"historical_preview");
      if (result.recorder_writes!==false || result.energy_writes!==false ||
          !result.proposals || !Array.isArray(result.review_candidates))
        throw new Error("Unverified historical preview");
      this._historyPreview=result;
      this._historyMessage=this._t(
        "Aperçu complet validé. Aucune donnée Recorder modifiée.",
        "Complete preview verified. Recorder data unchanged.");
      this._unsavedInput=false;
    } catch (_) {
      this._historyError=this._t(
        "Analyse interrompue : aucun historique partiel n’est validé. Relancer « Analyser les relevés » recommence la lecture complète depuis le début. Consultez Diagnostics.",
        "History interrupted: no partial history accepted. Selecting Analyze readings again restarts the entire read from the beginning. See Diagnostics.");
    } finally {
      this._historyBusy=false;this._historyJobId=null;this._historyJobStatus=null;
      if (!this._isEditingForm()) this._render();
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
    if (!this._confirm("Confirmer la décision pour "+summary+" ?\n\n"+
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
    if (!this._confirm(
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
    if (!this._confirm(
      "Enregistrer cette origine comme HYPOTHÈSE APPROUVÉE ?"+
      "\n\nLa date et l’index estimés ne sont pas des relevés mesurés."+
      "\nCette décision ne modifie ni les index réels, ni Recorder, ni Énergie."
    )) return;
    if (this._originRevision && !this._confirm(
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
      '<p class="muted">Indiquez une date de début et un index initial estimé (0 par défaut, modifiable), exprimé dans l’unité de l’index source (m³, L, kWh, MWh ou GJ selon le compteur). Le premier index réellement observé servira de borne finale. La période analysée doit commencer avant la date estimée.</p>'+
      '<div class="form-grid" style="margin-top:15px">'+
      '<div><label for="origin-meter">Compteur physique</label><select id="origin-meter" data-origin-field="meter">'+
      '<option value="">Choisir un compteur</option>'+meterOptions+'</select></div>'+
      '<div><label for="origin-date">Début estimé</label><input id="origin-date" type="date" data-origin-field="date" value="'+safe(this._originDate)+'"></div>'+
      '<div><label for="origin-index">Index initial estimé</label><input id="origin-index" type="number" min="0" step="any" data-origin-field="index" value="'+safe(this._originIndex)+'"></div></div>'+
      '<div class="actions"><button type="button" class="secondary" data-origin-preview '+
      (this._originBusy||!this._historyPreview?"disabled":"")+'>Calculer l’aperçu hypothétique</button></div>'+
      (this._originError?'<div class="notice warning">'+safe(this._originError)+'</div>':"")+
      (preview?'<div class="notice"><strong>Simulation calculée.</strong> Du '+
      safe(this._date(preview.start_date))+' au '+safe(this._date(preview.end_date))+', quantité estimée : '+
      safe(this._number(preview.estimated_total))+' '+safe(preview.unit)+
      '. Premier index réellement observé : '+safe(this._number(preview.first_observed_index))+
      ' '+safe(preview.source_index_unit||"unité à vérifier")+' à '+safe(this._date(preview.first_observed_at,true))+
      '. L’index initial '+safe(this._number(preview.estimated_initial_index))+' '+safe(preview.source_index_unit||"")+
      ' est une hypothèse, pas une mesure. Cet aperçu ne crée aucune mesure source.</div>'+
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
    const format=(value)=>this._number(value);
    return '<section aria-label="Comparaison journalière avant et après lissage">'+
      '<h3>Comparaison avant / après · consommation et cumul</h3>'+
      '<p class="muted">Avant : seules les consommations journalières effectivement connues sont affichées. Le tiret signifie « non déterminé », jamais zéro. Après : répartition estimée du résiduel, sans modifier les index réels.</p>'+
      '<div class="detail-grid">'+
      '<div><span class="smallhead">Total entre bornes</span><strong>'+safe(format(comparison.bounded_total))+' '+safe(proposal.unit)+'</strong></div>'+
      '<div><span class="smallhead">Consommation réellement mesurée</span><strong>'+safe(format(comparison.measured_total))+' '+safe(proposal.unit)+'</strong></div>'+
      '<div><span class="smallhead">Consommation estimée</span><strong>'+safe(format(comparison.estimated_total))+' '+safe(proposal.unit)+'</strong></div></div>'+
      '<div class="scroll" style="max-height:360px"><table><thead><tr><th>Jour</th><th>Avant · mesuré</th><th>Après · consommation</th><th>Cumul après</th><th>Nature</th></tr></thead><tbody>'+
      rows.slice(0,90).map(r=>'<tr><td>'+safe(this._date(r.date))+'</td>'+
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
        const label=safe(this._date(x.date)+" : "+this._number(x.quantity)+" "+proposal.unit+" ("+x.provenance+")");
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
    if (!this._confirm(description+" ?\n\n"+
        item.fluid+" · "+item.meter_serial+" · "+this._date(item.source_date,true)+
        "\nIndex source : "+this._number(item.index)+
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
    const meter=this._meters().find(m=>m.physical_key===this._historyContextKey);
    const list=(this._historyPreview?.review_candidates||[]).filter(c=>
      !meter || (c.fluid===meter.fluid && c.meter_serial===meter.serial && c.lot===meter.lot));
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
      '<span class="meter-name">'+safe(c.fluid+" · "+c.meter_serial+" · "+this._number(c.index))+'</span>'+
      '<span class="meter-sub">'+safe(this._date(c.source_date,true))+'</span>'+
      '<span class="meter-sub">'+safe(c.reasons.map(r=>explanation[r]||r).join(" · "))+
      " · Décision : "+safe(c.decision)+'</span></button></div>').join(""):'<div class="empty">Aucun relevé à examiner. Lancez l’analyse historique.</div>')+
    '</div><div>'+
    (item?'<h3>Décision sur le relevé</h3>'+
      '<p class="muted">Index réel : '+safe(this._number(item.index))+' · '+safe(this._date(item.source_date,true))+'</p>'+
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
  _historySummary() {
    const summary=this._historyPreview?.history_summary;
    if (!summary) return '<section class="card" style="margin-top:16px">'+
      '<h3>Synthèse historique par fluide</h3>'+
      '<div class="empty">Aucune prévisualisation actuelle. Utilisez « Analyser les relevés » pour calculer les indicateurs à partir des observations source.</div></section>';
    const rows=(summary.by_meter||[]);
    const selected=this._historyContextKey?
      this._meters().find(m=>m.physical_key===this._historyContextKey):null;
    if (this._historyContextKey && !selected) {
      return '<section class="card" style="margin-top:16px" role="status"><h3>'+
        safe(this._t("Compteur introuvable","Meter not found"))+'</h3><p>'+
        safe(this._t("Le contexte du compteur sélectionné ne correspond plus à cet inventaire. Aucun résultat global n’est affiché.",
          "The selected meter no longer belongs to this inventory. Account-wide results are hidden."))+
        '</p></section>';
    }
    if (selected) {
      const rowsForMeter=rows.filter(row=>row.physical_key===selected.physical_key &&
        row.fluid===selected.fluid && row.lot===selected.lot &&
        row.serial===selected.serial);
      return '<section class="card" style="margin-top:16px"><h3>'+
        safe(this._t("Synthèse du compteur sélectionné","Selected meter summary"))+
        '</h3><p class="muted">'+safe(
          this._t("Période analysée (compte) : ","Analyzed period (account): "))+
          this._date(this._historyPreview.start_date)+" → "+
          this._date(this._historyPreview.end_date)+'</p>'+
        (rowsForMeter.length?'<div class="detail-grid">'+
          rowsForMeter.map(row=>[
            [this._t("Compteur","Meter"),row.serial],
            [this._t("Première observation","First observation"),this._date(row.first_observed_at)],
            [this._t("Dernière observation","Last observation"),this._date(row.last_observed_at)],
            [this._t("Lacunes","Gaps"),this._number(row.gaps)],
            [this._t("Baisses","Decreases"),this._number(row.decreases)],
            [this._t("Conflits","Conflicts"),this._number(row.conflicts)],
          ].map(([label,value])=>
            '<div><span class="smallhead">'+safe(label)+'</span><strong>'+
            safe(value)+'</strong></div>').join("")).join("")+
          '</div>':'<div class="empty">'+safe(this._t(
          "Aucun résultat pour ce compteur dans la période analysée.",
          "No results for this meter in the analyzed period."))+'</div>')+
        '</section>';
    }
    return '<section class="card" style="margin-top:16px"><h3>Synthèse historique par fluide et compteur</h3>'+
      '<p class="muted">Période : '+safe(this._date(this._historyPreview.start_date))+
      ' → '+safe(this._date(this._historyPreview.end_date))+
      '. '+safe(this._number(summary.meters))+' compteur(s) physique(s) et '+
      safe(this._number(summary.readings_to_review))+' relevé(s) à examiner. Les compteurs successifs ne sont pas fusionnés.</p>'+
      '<div class="grid-two">'+["EF","ECS","CET"].map(fluid=>{
        const item=summary.by_fluid?.[fluid]||{};
        return '<div class="line '+safe(FLUID_CLASS[fluid]||"")+'" style="border-inline-start:4px solid var(--fluid-fg)">'+
          '<strong>'+safe(FLUID[fluid])+'</strong><div class="muted">'+
          safe(this._number(item.meters??0))+' compteur(s) · '+
          safe(this._number(item.gaps??0))+' intervalle(s) lacunaire(s) · '+
          safe(this._number(item.conflicts??0))+' conflit(s)</div></div>';
      }).join("")+'</div>'+
      (rows.length?'<details style="margin-top:16px"><summary>Voir les indicateurs par compteur physique</summary>'+
        '<div class="scroll"><table><thead><tr><th>Fluide</th><th>Compteur</th><th>Première observation</th>'+
        '<th>Dernière observation</th><th>Lacunes</th><th>Baisses</th><th>Conflits</th></tr></thead><tbody>'+
        rows.map(m=>'<tr><td>'+safe(m.fluid)+'</td><td class="mono">'+safe(m.serial)+
          '</td><td>'+safe(this._date(m.first_observed_at))+'</td><td>'+
          safe(this._date(m.last_observed_at))+'</td><td>'+safe(this._number(m.gaps))+
          '</td><td>'+safe(this._number(m.decreases))+'</td><td>'+
          safe(this._number(m.conflicts))+'</td></tr>').join("")+
        '</tbody></table></div></details>':"")+'</section>';
  }
  _history() {
    const meter=this._meters().find(m=>m.physical_key===this._historyContextKey);
    if (this._historyContextKey && !meter) {
      return this._heading(this._t("Historique & lissage","History & smoothing"),
        this._t("Contexte de compteur non disponible","Meter context unavailable"))+
        '<section class="card" role="status"><p>'+safe(this._t(
          "Le compteur sélectionné ne figure plus dans ce logement. Aucun résultat d’un autre compteur n’est présenté.",
          "The selected physical meter no longer belongs to this dwelling. No other meter results are shown."))+
        '</p><div class="actions"><button type="button" class="secondary" data-history-context-clear>'+
        safe(this._t("Afficher tous les compteurs","Show all meters"))+
        '</button></div></section>';
    }
    const proposal=(this._historyPreview?.proposals?.intervals||[]).find(
      x=>x.interval_key===this._historySelected
    );
    const ready=proposal&&proposal.status==="linear_available_after_explicit_confirmation";
    const list=(this._historyPreview?.proposals?.intervals||[]).filter(x=>
      !meter || (x.fluid===meter.fluid && x.meter_serial===meter.serial && x.lot===meter.lot));
    const blockers={
      blocked_source_conflict:"Conflit d’index à examiner",
      blocked_unverified_unit:"Unité non vérifiée",
      blocked_unreviewed_zero:"Index nul non qualifié",
      blocked_needs_explicit_review:"Bornes à vérifier",
      linear_available_after_explicit_confirmation:"Lissage envisageable après confirmation"
    };
    return this._heading("Historique & lissage",
      "Répartition linéaire contrôlée, sans modification des relevés bruts.")+
      (meter?'<section class="meter-history-context"><strong>'+
        safe(this._t("Compteur sélectionné : ","Selected meter: ")+
          (FLUID[meter.fluid]||meter.fluid)+" · "+meter.serial+" · "+meter.lot)+'</strong>'+
        '<p class="muted">'+safe(this._t(
          "L’analyse est lancée séparément et couvre le compte ; seuls les résultats de ce compteur sont affichés ici.",
          "The analysis must be started separately and covers the account; only this meter's results are displayed here."))+
        '</p><div class="actions"><button type="button" class="secondary" data-tab="meters">'+
        safe(this._t("Retour au compteur","Back to meter"))+'</button>'+
        '<button type="button" class="secondary" data-history-context-clear>'+
        safe(this._t("Afficher tous les compteurs","Show all meters"))+'</button></div></section>':"")+
      '<section class="card"><div class="panel-title"><h3>Charger une période</h3>'+
      '<span class="pill audit">Aperçu en lecture seule</span></div>'+
      '<div class="form-grid">'+
      '<div><label for="hist-start">Depuis le</label><input id="hist-start" type="date" data-history-field="start_date" value="'+safe(this._historyStart)+'"></div>'+
      '<div><label for="hist-end">Jusqu’au</label><input id="hist-end" type="date" data-history-field="end_date" value="'+safe(this._historyEnd)+'"></div></div>'+
      '<div class="actions"><button type="button" class="primary" data-history-preview '+(this._historyBusy?"disabled":"")+
      '>Analyser les relevés</button><button class="secondary" type="button" data-open-options>Ancienne IHM de révision</button>'+ 
      (this._historyBusy&&this._historyJobId?
        '<button type="button" class="secondary" data-history-cancel>'+
        this._t("Annuler l’analyse","Cancel analysis")+'</button>':"")+'</div>'+
      (this._historyJobStatus?.status==="running"?
        '<p class="notice" role="status">'+this._t("Lecture en cours : ","Reading history: ")+
        safe(this._historyJobStatus.progress?.http_requests??"—")+
        this._t(" requête(s), "," requests, ")+
        safe(this._historyJobStatus.progress?.periods_verified??"—")+
        this._t(" période(s) vérifiée(s)."," verified periods.")+
        '</p>':"")+
      (this._historyError?'<div class="notice warning">'+safe(this._historyError)+'</div>':"")+
      (this._historyMessage?'<div class="notice">'+safe(this._historyMessage)+'</div>':"")+
      '</section>'+this._historySummary()+'<div class="split" style="margin-top:16px"><section class="card"><h3>Intervalles entre relevés</h3>'+
      '<p class="muted">L’analyse ne déduit jamais une origine manuelle ou automatique.</p>'+
      (list.length?'<div class="scroll">'+list.map(item=>'<div class="meter-row">'+
        '<button type="button" data-history-select="'+safe(item.interval_key)+'" class="'+
        (this._historySelected===item.interval_key?"selected":"")+'">'+
        '<span class="meter-name">'+safe(item.fluid+" · "+item.meter_serial)+'</span>'+
        '<span class="meter-sub">'+safe(this._date(item.start_date)+" → "+this._date(item.end_date)+" · "+(blockers[item.status]||item.status))+
        '</span></button></div>').join("")+'</div>':
      '<div class="empty">'+(this._historyPreview?"Aucun intervalle à signaler sur cette période.":"Analysez une période pour afficher les intervalles concernés.")+'</div>')+
      '</section><section class="card">'+
      (proposal?'<h3>Reconstituer l’intervalle sélectionné</h3>'+
      '<p class="muted">'+safe(proposal.lot+" · "+proposal.meter_serial+" · "+this._date(proposal.start_date)+" → "+this._date(proposal.end_date))+'</p>'+
      '<div class="detail-grid">'+
      '<div><span class="smallhead">Consommation bornée</span><strong>'+
      safe(proposal.bounded_consumption===undefined?"Non déterminée":proposal.bounded_consumption+" "+proposal.unit)+'</strong></div>'+
      '<div><span class="smallhead">Index avant → après</span><strong>'+safe(this._number(proposal.source_start_index)+" → "+this._number(proposal.source_end_index))+'</strong></div>'+
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

  async _previewAnnualCosts() {
    if (!this._current||this._costBusy||this._tariffBusy) return;
    const year=Number(this._tariffInput.year);
    const today=new Date().toLocaleDateString("sv-SE",{timeZone:"Europe/Paris"});
    const currentYear=Number(today.slice(0,4));
    if (!Number.isInteger(year)||year<2000||year>currentYear) {
      this._costError="Choisissez un exercice commencé, entre 2000 et l’année courante.";
      this._render();return;
    }
    const start_date=String(year)+"-01-01";
    const end_date=String(year)===String(currentYear)?today:String(year)+"-12-31";
    this._costPreview=null;this._costBusy=true;this._costError="";this._render();
    try {
      const response=await this._hass.callWS({
        type:"call_service",domain:"trybatec",service:"preview_costs",
        service_data:{entry_id:this._current.entry_id,start_date,end_date,
          include_cold_water:true,include_hot_water:true,include_heating:true},
        return_response:true
      });
      const result=response?.response;
      if (result?.mode!=="read_only_historical_cost_estimates" ||
          result.currency!=="EUR" || result.persisted!==false ||
          !Array.isArray(result.annual) || !Array.isArray(result.withheld) ||
          result.start_date!==start_date || result.end_date!==end_date) {
        throw new Error("Unverified annual-cost response");
      }
      this._costPreview=result;this._costYear=year;
    } catch (_) {
      this._costError="Coûts indisponibles : vérifiez la connexion, les unités et les relevés source. "+
        "Aucun coût manquant n’est remplacé par une valeur supposée.";
    } finally {this._costBusy=false;this._render();}
  }
  _annualCostsView() {
    const p=this._costPreview;
    const rows=(p?.annual||[]).slice(0,100);
    const fmt=n=>this._number(n);
    const table=rows.map(x=>{
      const unit=x.unit==="kWh"?"kWh":"m³";
      const evidence=x.evidence_type==="measured_daily"?"Relevés journaliers":
        x.evidence_type==="accounting_allocation"?"Imputation approuvée":"Non qualifié";
      const status=x.tariff_status==="approved"?"Tarif approuvé":
        x.tariff_status==="provisional"?"Tarif provisoire":
        x.tariff_status==="missing"?"Tarif absent":"Tarifs hétérogènes";
      const origin=x.rate_origin==="meter_override"?"Spécifique au compteur":
        x.rate_origin==="fluid_default"?"Commun au fluide":
        x.rate_origin==="missing"?"Aucun":"Mixte";
      const costs=x.estimated_cost===null?"Indisponible":fmt(x.estimated_cost)+" EUR";
      const rate=x.rate===null?(x.tariff_status==="missing"?"Manquant":"Multiple"):
        fmt(x.rate)+" "+(unit==="kWh"?"EUR/kWh":"EUR/m³");
      const meterDetails=(x.meter_rates||[]).slice(0,30).map(m=>
        '<li>'+safe(m.meter_serial)+" · "+safe(m.lot)+" · "+
        safe(fmt(m.quantity))+" "+safe(unit)+" · "+
        safe(m.rate===null?"tarif absent":fmt(m.rate)+" "+(unit==="kWh"?"EUR/kWh":"EUR/m³"))+
        ' · '+safe(m.estimated_cost===null?"coût indisponible":fmt(m.estimated_cost)+" EUR")+
        ' · '+safe(m.origin==="meter_override"?"spécifique":m.origin==="fluid_default"?"commun":"aucun")+
        (m.coverage==="partial_or_uncertain"?" · période incomplète":"")+
        '</li>').join("");
      return '<tr><td>'+safe(x.year)+'</td><td>'+safe(FLUID[x.fluid]||x.fluid)+'</td>'+
        '<td>'+safe(evidence)+'</td><td>'+safe(fmt(x.quantity))+' '+safe(unit)+'</td>'+
        '<td>'+safe(rate)+'<div class="muted">'+safe(origin)+'</div></td>'+
        '<td>'+safe(costs)+'</td><td>'+safe(status)+
        (x.coverage==="partial_or_uncertain"?'<div class="muted">Période incomplète</div>':'')+
        (meterDetails?'<details><summary>Tarifs par compteur</summary><ul>'+meterDetails+'</ul></details>':'')+
        '</td></tr>';
    }).join("");
    return '<section class="card" style="margin-top:16px">'+
      '<h3>Consommations et coûts estimés par exercice</h3>'+
      '<p class="muted">Aperçu en lecture seule pour l’exercice sélectionné. Les quantités vérifiées au pas journalier et les imputations comptables explicites sont séparées. Les intervalles inconnus, hypothèses initiales et lissages non incorporés restent exclus : ce ne sont pas des charges facturées.</p>'+
      '<div class="actions"><button type="button" class="secondary" data-cost-preview '+
      (this._costBusy?"disabled":"")+'>Calculer les coûts de '+safe(this._tariffInput.year)+'</button></div>'+
      (this._costBusy?'<p class="muted">Lecture des relevés et calcul en cours.</p>':"")+
      (this._costError?'<div class="notice warning">'+safe(this._costError)+'</div>':"")+
      (p?'<p class="muted">Exercice '+safe(this._costYear)+' · '+safe(this._date(p.start_date))+
      ' au '+safe(this._date(p.end_date))+' · '+safe(p.withheld_total||0)+
      ' compteur(s) exclu(s) faute de justification suffisante.</p>'+
      (rows.length?'<div class="scroll"><table><thead><tr><th>Année</th><th>Fluide</th>'+
      '<th>Origine</th><th>Consommation</th><th>Tarif</th><th>Coût estimé</th>'+
      '<th>Fiabilité</th></tr></thead><tbody>'+table+'</tbody></table></div>':
      '<div class="empty">Aucune consommation justifiable pour cet exercice. Aucun coût fictif n’est produit.</div>')+
      (p.withheld_total?'<div class="notice warning">Certains compteurs sont exclus du calcul : unité non vérifiée, conflit ou historique invalide. Consultez les diagnostics avant toute interprétation.</div>':"")+
      '<p class="muted">Coûts uniquement estimés, en EUR ; un tarif « approuvé » ne vaut pas validation des charges. Aucun autre exercice n’est utilisé pour remplacer un tarif manquant.</p>':"")+
      '</section>';
  }
  _tariffs() {
    const a=this._current, f=this._tariffInput;
    // Initial navigation must show the persisted rate, not a blank draft.
    // Hydration happens once per account, never over unsaved user input.
    if (!this._tariffHydrated) {
      const saved=this._existingTariff();
      f.rate=saved?String(saved.rate):"";
      f.status=saved?saved.status:"provisional";
      this._tariffHydrated=true;
    }
    const editButton=(year,fluid,physicalKey="")=>
      '<button type="button" class="secondary" data-tariff-edit-year="'+safe(year)+
      '" data-tariff-edit-fluid="'+safe(fluid)+'" data-tariff-edit-meter="'+safe(physicalKey)+
      '">'+safe(this._t("Modifier","Edit"))+'</button>';
    const rows=Object.entries(a.tariffs||{}).sort((a,b)=>Number(b[0])-Number(a[0])).flatMap(([year,fluids])=>
      Object.entries(fluids).map(([fluid,t])=>'<tr><td>'+safe(year)+'</td><td>'+safe(FLUID[fluid]||fluid)+
      '</td><td>'+safe(this._number(t.rate))+' '+safe(fluid==="CET"?"EUR/kWh":"EUR/m³")+'</td>'+
      '<td>'+safe(t.status==="approved"?"Approuvé":"Provisoire")+'</td><td>'+
      editButton(year,fluid)+'</td></tr>'));
    const overrides=Object.entries(a.meter_tariffs||{}).sort((a,b)=>Number(b[0])-Number(a[0])).flatMap(([year,values])=>
      Object.entries(values).map(([key,t])=>{
        const m=a.meters.find(m=>m.physical_key===key);
        return '<tr><td>'+safe(year)+'</td><td>'+safe(m?(FLUID[m.fluid]+" · "+m.serial):"Compteur non identifié")+
          '</td><td>'+safe(this._number(t.rate))+' '+safe(m&&m.fluid==="CET"?"EUR/kWh":"EUR/m³")+'</td>'+
          '<td>'+safe(t.status==="approved"?"Approuvé":"Provisoire")+'</td><td>'+
          (m?editButton(year,m.fluid,key):'<span class="muted">'+safe(this._t("Non vérifié","Not verified"))+'</span>')+
          '</td></tr>';
      }));
    const range=trybatecTariffYears(a,new Date().getFullYear());
    const coverage=this._tariffCoverage.get(a.entry_id);
    const coverageNotice=coverage?.status==="loading" ?
      '<p class="notice" role="status">Recherche en lecture seule des années de relevés historiques… '+
      (this._tariffJobStatus?.progress?
        safe(this._tariffJobStatus.progress.http_requests)+
        ' requête(s) effectuée(s). ':"")+
      (this._tariffJobId?'<button type="button" data-tariff-years-cancel>Annuler</button>':"")+
      '</p>' :
      coverage?.status==="error" ?
      '<p class="notice warning" role="alert">Années historiques non vérifiées : la liste peut être incomplète. '+
      '<button type="button" data-tariff-years-retry>Réessayer</button></p>' :
      coverage?.status==="complete" ?
      '<p class="notice" role="status">Exercices fondés sur les relevés historiques datés du compte.</p>' :
      '<p class="notice" role="status">Analyse historique exhaustive non lancée : '+
      'elle peut solliciter plusieurs années de relevés fournisseur. '+
      '<button type="button" data-tariff-years-retry>'+
      'Rechercher les exercices historiques</button></p>';
    // Historical years are suggestions, never a restriction on new exercises.
    const yearOptions=range.years.map(year=>
      '<option value="'+year+'"></option>').join("");
    const current=a.meters.filter(m=>m.fluid===f.fluid);
    const meterOptions='<option value="">Tarif commun du fluide</option>'+
      current.map(m=>'<option value="'+safe(m.physical_key)+'" '+(f.physical_key===m.physical_key?"selected":"")+'>'+
      safe(FLUID[m.fluid]+" · "+m.serial+" · "+m.lot+(m.status==="depose"?this._t(" (déposé)"," (retired)"):""))+'</option>').join("");
    const unit=f.fluid==="CET"?"EUR/kWh":"EUR/m³";
    const effectiveText=this._tariffEffectiveText();
    return this._heading("Tarifs annuels","Montants en EUR par exercice, fluide et, facultativement, compteur physique.")+
      '<div class="card"><h3>Saisir ou modifier un tarif</h3>'+
      '<p class="muted">Choisissez l’année, le fluide et éventuellement un compteur. Les tarifs déjà saisis sont conservés.</p>'+
      coverageNotice+
      (range.fallback?'<p class="notice">Aucun relevé daté : exercices proposés autour de l’année courante, avec les années déjà tarifées.</p>':"")+
      (this._tariffMessage?'<div class="notice" role="status">'+safe(localizeTrybatecText(this._tariffMessage,this._locale()))+'</div>':"")+
      (this._tariffError?'<div class="notice warning" role="alert">'+safe(localizeTrybatecText(this._tariffError,this._locale()))+'</div>':"")+
      '<form data-tariff-form><div class="form-grid" style="margin-top:16px">'+
      '<div><label for="tariff-year">Exercice annuel</label>'+
      '<input id="tariff-year" type="number" min="2000" max="2100" step="1" required data-tariff-field="year" list="tariff-year-options" value="'+safe(f.year)+'">'+
      '<datalist id="tariff-year-options">'+yearOptions+'</datalist>'+
      '<div class="muted">Exercices suggérés ci-dessous ; toute année entre 2000 et 2100 peut être saisie.</div></div>'+
      '<div><label for="tariff-fluid">Fluide</label><select id="tariff-fluid" data-tariff-field="fluid">'+
      Object.entries(FLUID).filter(([key])=>key!=="unknown").map(([key,label])=>
        '<option value="'+key+'" '+(f.fluid===key?"selected":"")+'>'+safe(label)+'</option>').join("")+'</select></div>'+
      '<div><label for="tariff-scope">Portée</label><select id="tariff-scope" data-tariff-field="physical_key">'+meterOptions+'</select></div>'+
      '<div><label for="tariff-rate">'+safe(this._t("Tarif","Rate"))+' ('+safe(unit)+')</label>'+
      '<input id="tariff-rate" type="number" min="0" max="1000000" step="0.000001" value="'+safe(f.rate)+
      '" data-tariff-field="rate" placeholder="0.000000" required></div>'+
      '<div><label for="tariff-status">État</label><select id="tariff-status" data-tariff-field="status">'+
      '<option value="provisional" '+(f.status==="provisional"?"selected":"")+'>Provisoire</option>'+
      '<option value="approved" '+(f.status==="approved"?"selected":"")+'>Approuvé</option></select></div>'+
      '</div><p class="muted" role="status" data-tariff-effective>'+safe(effectiveText)+'</p>'+
      '<div class="actions"><button class="primary" type="submit" '+(this._tariffBusy?"disabled":"")+'>Enregistrer ce tarif</button>'+
      '<button class="secondary" type="button" data-tariff-reset '+(this._tariffBusy?"disabled":"")+'>Annuler la saisie</button>'+
      '<button class="secondary" type="button" data-tariff-delete '+(!this._existingTariff()||this._tariffBusy?"disabled":"")+
      '>Retirer ce tarif</button></div></form>'+
      '<div class="notice">L’état « Approuvé » qualifie le tarif saisi, pas une facture validée. Modifier un tarif ne démarre aucun import Recorder et ne modifie pas Énergie.</div></div>'+
      '<div class="grid-two" style="margin-top:16px"><section class="card"><h3>Tarifs communs</h3>'+
      (rows.length?'<div class="scroll"><table><thead><tr><th>Année</th><th>Fluide</th><th>Tarif</th><th>État</th><th>Action</th></tr></thead><tbody>'+rows.join("")+'</tbody></table></div>':
      '<div class="empty">Aucun tarif commun enregistré.</div>')+'</section>'+
      '<section class="card"><h3>Tarifs spécifiques aux compteurs</h3>'+
      (overrides.length?'<div class="scroll"><table><thead><tr><th>Année</th><th>Compteur</th><th>Tarif</th><th>État</th><th>Action</th></tr></thead><tbody>'+overrides.join("")+'</tbody></table></div>':
      '<div class="empty">Aucune dérogation propre à un compteur. Le tarif commun reste applicable lorsqu’il existe pour l’exercice.</div>')+
      '</section></div>'+this._annualCostsView();
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
      include_heating:true};
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
    if (!this._confirm(
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
    if (!this._confirm(
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
    const verifiedVersions=(ledger.series||[]).flatMap(row=>(row.versions||[]).filter(v=>
      ["verified","archived"].includes(v.state)));
    const configuredTrybatec=(this._data.energy.sources||[]).filter(x=>
      typeof x.statistic_id==="string" && x.statistic_id.startsWith("trybatec:"));
    const hasVerifiedVersion=verifiedVersions.length>0;
    const hasCurrentSource=configuredTrybatec.length>0;
    const canReplaceVersion=hasVerifiedVersion && hasCurrentSource;
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

      '</div><p class="muted">'+safe(this._t(
        "Eau froide, eau chaude et chauffage sont inclus dans l’aperçu sous réserve de contrôles d’unités et d’historique. Aucun import n’est automatique.",
        "Cold water, hot water and heating are included in previews subject to unit and history checks. No automatic import."
      ))+'</p><div class="actions"><button type="button" class="secondary" data-version-preview '+(this._versionBusy?"disabled":"")+'>1. Prévisualiser Recorder</button></div>'+
      (plan?'<div class="notice"><strong>Plan non importé</strong> · '+safe(rows.length)+
        ' séries, '+safe(plan.physical_meters?.length||"?")+' compteurs, période '+
        safe(this._date(plan.start_date))+" → "+safe(this._date(plan.end_date))+
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
      (canReplaceVersion?"":
        '<div class="notice warning" role="status"><strong>'+safe(this._t(
        "Parcours indisponible : prérequis manquants.","Unavailable: prerequisites are missing."))+'</strong> '+
        (!hasVerifiedVersion?safe(this._t(
        "Aucune version Recorder vérifiée : analyser les relevés, prévisualiser puis importer après sauvegarde, et contrôler la persistance. ",
        "No verified Recorder version: review readings, preview, import after backup, then verify persistence. ")):'')+
        (!hasCurrentSource?safe(this._t(
        "Aucune série Trybatec déjà utilisée dans Énergie : cette opération remplace une source existante ; pour une première activation, utiliser le parcours initial de configuration Énergie. ",
        "No Trybatec series in Energy: this operation replaces an existing source; first activation uses the separate initial Energy configuration. ")):'')+
        '<div class="actions"><button type="button" class="secondary" data-tab="history">'+safe(this._t("Examiner l’historique","Review history"))+'</button>'+
        (!hasCurrentSource?'<button type="button" class="secondary" data-open-energy>'+safe(this._t("Ouvrir la configuration Énergie","Open Energy settings"))+'</button>':"")+
        '</div></div>')+
      '<fieldset class="'+(canReplaceVersion?"prerequisite-ready":"prerequisite-locked")+'" '+
      (!canReplaceVersion?'disabled aria-disabled="true"':'')+'>'+
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
      '>5. Confirmer le basculement Énergie</button></div></fieldset></section>'+
      (this._versionError?'<div class="notice warning">'+safe(this._versionError)+'</div>':"")+
      (this._versionMessage?'<div class="notice">'+safe(this._versionMessage)+'</div>':"");
  }
  _energySetupHelp() {
    const t=(fr,en)=>this._t(fr,en);
    const guidance=trybatecEnergySetupGuidance(this._current,this._data?.energy);
    const explanation={
      status_unknown:t(
        "État du module Énergie inconnu : aucune configuration terminée n’est démontrée par cet aperçu.",
        "Energy module status is unknown: this view cannot establish completed configuration."),
      technical_unavailable:t(
        "Le module Énergie n’est pas chargé : l’intégration automatique ne peut pas être vérifiée.",
        "The Energy module is not loaded: automatic enrollment cannot be verified."),
      configuration_incomplete:t(
        "Des actions de configuration sont encore attendues. L’ajout groupé automatique n’est pas disponible dans cette version.",
        "Some setup actions are still required. Automatic bulk enrollment is not available in this version."),
      verification_needed:t(
        "Certaines vérifications restent à effectuer. L’ajout groupé automatique n’est pas disponible dans cette version.",
        "Some checks remain to be completed. Automatic bulk enrollment is not available in this version."),
      coverage_unverified:t(
        "Des sources Trybatec sont référencées, mais la couverture de tous les fluides et compteurs n’est pas vérifiée. L’ajout groupé n’est pas disponible dans cette version.",
        "Some Trybatec sources are referenced, but complete utility and meter coverage has not been verified. Bulk enrollment is not available in this version."),
      not_implemented:t(
        "L’ajout groupé automatique n’est pas encore disponible dans cette version. Aucun prérequis manquant supplémentaire n’est démontré par cet aperçu.",
        "Automatic bulk enrollment is not yet available in this version. This view does not demonstrate additional missing prerequisites."),
    };
    const reasonRows=guidance.reasons.map(reason=>
      '<div class="line"><ha-icon icon="'+(reason.level==="required"?
        'mdi:information-outline':'mdi:help-circle-outline')+
      '" aria-hidden="true"></ha-icon> <strong>'+safe(reason.level==="required"?
        t("À faire","Action required"):t("Non vérifié","Not verified"))+
      ' :</strong> '+safe(t(reason.fr,reason.en))+
      (typeof reason.physical_key==="string" && reason.physical_key?
        '<div class="actions"><button type="button" class="secondary" data-energy-meter="'+
          safe(reason.physical_key)+'">'+safe(t("Fiche du compteur","Meter details"))+'</button>'+
        '<button type="button" class="secondary" data-energy-history="'+safe(reason.physical_key)+
          '">'+safe(t("Historique du compteur","Meter history"))+'</button></div>':"")+
      '</div>').join("");
    const tabs=[...new Set(guidance.reasons.map(reason=>reason.tab)
      .filter(tab=>tab!=="overview"&&tab!=="energy"))];
    const tabLabel={
      meters:t("Vérifier les compteurs","Review meters"),
      history:t("Examiner l’historique","Review history"),
      tariffs:t("Configurer les tarifs","Configure tariffs"),
    };
    return '<div class="notice" role="status">'+
      '<strong>'+safe(t("Configuration du tableau Énergie","Energy dashboard setup"))+'</strong>'+
      '<p>'+safe(explanation[guidance.mode])+'</p>'+
      '<p class="muted">'+safe(t(
        "Le planificateur groupé fonctionne en lecture seule à partir d’assertions : sans diagnostic indépendant de Recorder et des registres, aucun ajout n’est autorisé.",
        "The bulk planner is read-only and relies on assertions: without independent Recorder and registry evidence, enrollment is not authorized."))+'</p>'+reasonRows+
      (guidance.optionalTariffsMissing?
        '<p class="muted">'+safe(t(
          "Tarifs annuels facultatifs non renseignés : seuls les coûts correspondants sont indisponibles, pas la configuration des consommations.",
          "Optional annual rates are not set: only related costs are unavailable, not consumption setup."))+'</p>':"")+
      '<div class="actions"><button type="button" class="secondary" data-tab="overview">'+
      safe(t("Assistant de configuration / Vue d’ensemble","Setup assistant / Overview"))+'</button>'+
      tabs.map(tab=>'<button type="button" class="secondary" data-tab="'+safe(tab)+'">'+
        safe(tabLabel[tab]||tab)+'</button>').join("")+
      (guidance.optionalTariffsMissing?
        '<button type="button" class="secondary" data-tab="tariffs">'+
        safe(t("Tarifs (facultatif)","Rates (optional)"))+'</button>':"")+
      '<button type="button" class="secondary" data-open-energy>'+
        safe(t("Ouvrir Énergie (configuration manuelle)","Open Energy (manual setup)"))+
      '</button></div></div>';
  }
  _energy() {
    const data=this._data.energy||{status:"not_loaded",sources:[]};
    const a=this._current;
    const rows=a.ledger.series||[];
    return this._heading("Énergie & versions","Références configurées et versions historiques vérifiables.")+
      '<div class="grid-two"><section class="card"><h3>Sources Trybatec dans Énergie</h3>'+
      ((data.sources||[]).length?data.sources.map(x=>'<div class="line"><strong>'+safe(x.type)+'</strong> · <span class="mono">'+safe(x.statistic_id)+'</span></div>').join(""):
        '<div class="empty">Aucune source Trybatec identifiée dans la configuration Énergie actuellement disponible.</div>')+
      this._energySetupHelp()+'</section>'+
      '<section class="card"><h3>Séries historiques versionnées</h3><p class="muted">Registre Recorder b15 : '+safe(a.ledger.status)+
      ', imports à vérifier : '+safe(a.ledger.pending)+'</p>'+
      (rows.length?rows.map(row=>'<div class="line"><span class="mono">'+safe(row.logical_id)+'</span>'+
       '<div class="muted">'+safe((row.versions||[]).length)+' version(s) · '+safe(row.unit||"Unité inconnue")+'</div></div>').join(""):
       '<div class="empty">Aucune série versionnée enregistrée. Une importation historique ne sera pas démarrée automatiquement.</div>')+
      '</section></div>'+this._recorderVersionWorkflow()+'<div class="notice">Une seule série consolidée par logement et fluide doit être active dans Énergie. Les migrations et basculements exigent un aperçu, une sauvegarde et une confirmation distincte.</div>';
  }
  _diagnostics() {
    const a=this._current;
    const audit=a.technical_entity_audit||{};
    return this._heading("Diagnostics","Lecture des entités, disponibilités et état des données.")+
      '<div class="grid-two"><section class="card"><h3>Statut</h3><div class="line">Synchronisation actuelle : <strong>'+
      (a.data_loaded?"Données chargées":"En attente de données")+'</strong></div>'+
      '<div class="line">Compteurs physiques connus : '+this._meters().length+'</div>'+
      '<div class="line">Inventaire archivé : '+a.archived_inventory_count+'</div>'+
      '<div class="line">Entités Trybatec recensées : '+a.entities.length+'</div>'+
      '<div class="line">Anciennes générations techniques à examiner : '+safe(audit.potential_legacy_entries??"Non vérifié")+'</div>'+
      '<div class="line">Entités encore référencées dans Énergie : '+safe(audit.energy_referenced_entities??"Non vérifié")+'</div>'+
      a.warnings.map(x=>'<div class="notice warning">'+safe(x)+'</div>').join("")+
      '<div class="actions"><button class="secondary" type="button" data-refresh>Actualiser</button></div></section>'+
      '<section class="card"><h3>Audit des entités techniques</h3>'+
      '<p class="muted">Une entité indisponible n’est pas nécessairement obsolète : elle peut avoir des historiques Recorder et des références actives. Une génération technique n’est pas un compteur physique déposé.</p>'+
      '<div class="notice warning"><strong>Audit partiel, aucune suppression autorisée.</strong> Les références aux tableaux de bord, automatisations et statistiques Recorder ne sont pas vérifiées exhaustivement. Un résultat vide dans Énergie ne prouve pas qu’une entité est inutilisée.</div>'+
      '<div class="scroll">'+(a.entities.length?a.entities.map(e=>{
      const candidate=e.technical_role==="legacy_same_device_candidate";
      const refs=Array.isArray(e.energy_references)?e.energy_references:[];
      const roles={
        active_physical_index:"Index d’un compteur physique en service",
        retired_physical_index:"Index historique d’un compteur déposé",
        physical_index_status_unknown:"Index physique · statut du compteur à vérifier",
        account_ytd_usage_estimate:"Indicateur annuel · consommation estimée",
        account_ytd_cost_estimate:"Indicateur annuel · coût estimé",
        account_annual_unit_price:"Indicateur annuel · tarif unitaire",
        legacy_same_device_candidate:"Ancienne génération technique à auditer",
        unclassified:"Entité technique non classée"
      };
      const label=roles[e.technical_role]||roles.unclassified;
      const successors=Array.isArray(e.same_device_successors)?e.same_device_successors:[];
      return '<div class="entity"><span class="mono">'+safe(e.entity_id)+'</span>'+
      '<div class="muted">'+safe(label)+' · État : '+safe(e.state)+' · Unité : '+safe(e.unit||"N/A")+'</div>'+
      (successors.length?'<div class="muted">Autre génération du même appareil : '+successors.map(safe).join(", ")+'</div>':"")+
      '<div class="muted">Références Énergie confirmées : '+safe(refs.length)+
      (refs.length?' ('+refs.map(x=>safe(x.type||"?")+" #"+safe(x.index)).join(", ")+')':"")+'</div>'+
      '<details><summary>Identité technique et vérifications manquantes</summary>'+
      '<div class="muted">Identifiant technique : <span class="mono">'+safe(e.unique_id||"Inconnu")+'</span></div>'+
      '<div class="muted">Appareil : <span class="mono">'+safe(e.device_id||"Non vérifié")+'</span></div>'+
      '<div class="muted">Recorder, automatisations et tableaux de bord : non vérifiés exhaustivement.</div></details>'+
      '<div class="muted">Nettoyage : interdit sans audit complet, sauvegarde et confirmation distincte.</div></div>';
      }).join(""):'<div class="empty">Aucune entité recensée.</div>')+
      '</div></section></div>'+this._communicationDiagnostics();
  }
  async _saveSettings() {
    if (!this._current || this._settingsBusy) return;
    const settings={...this._current.settings,...this._settingsInput};
    const poll=this._durationInput?
      trybatecDurationMinutes(this._durationInput):Number(settings.poll_minutes);
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
    if (!this._confirm(message)) return;
    this._settingsBusy=true;this._settingsError="";this._render();
    try {
      await this._hass.callWS({
        type:"trybatec/panel_settings_save",
        entry_id:this._current.entry_id,
        poll_minutes:poll,sparse_hours:sparse,
        zero_review_days:zeros,log_level:this._current.settings.log_level,
        expected_fingerprint:this._current.tariff_fingerprint,
        confirm:true
      });
      this._data=await this._hass.callWS({type:"trybatec/panel_snapshot"});
      this._settingsInput=null;
      this._durationInput=null;
      this._settingsMessage="Réglages enregistrés dans la configuration Home Assistant partagée.";
    } catch (_) {
      this._settingsError="Modification refusée ou intégration en cours de rechargement. Actualisez et vérifiez les valeurs.";
    } finally {
      this._settingsBusy=false;this._render();
    }
  }
  async _saveLogLevel() {
    if (!this._current || this._loggingBusy) return;
    const level=this._loggingInput??this._current.settings.log_level;
    if (!["ERROR","WARNING","INFO","DEBUG"].includes(level)) {
      this._loggingError="Niveau de journalisation invalide.";this._render();return;
    }
    if (!this._confirm(
      "Enregistrer le niveau de journalisation de ce compte ?"+
      "\\n\\nIl définit le journaliseur commun Trybatec. Le niveau le plus détaillé configuré parmi tous les comptes prévaut."
    )) return;
    this._loggingBusy=true;this._loggingError="";this._loggingMessage="";this._render();
    try {
      const result=await this._hass.callWS({
        type:"trybatec/panel_log_level_save",
        entry_id:this._current.entry_id,log_level:level,
        expected_fingerprint:this._current.tariff_fingerprint,
        confirm:true
      });
      if (result.recorder_writes!==false||result.energy_writes!==false)
        throw new Error("Unverified logger save");
      this._data=await this._hass.callWS({type:"trybatec/panel_snapshot"});
      this._loggingInput=null;
      this._loggingMessage="Journalisation mise à jour pour Trybatec.";
    } catch (_) {
      this._loggingError="Modification refusée ou paramètres modifiés entre-temps. Actualisez puis réessayez.";
    } finally {this._loggingBusy=false;this._render();}
  }
  _technicalLimits() {
    const details=this._data?.technical_limits;
    if (!details?.read_only) return '<p class="muted">'+this._t(
      'Limites techniques non disponibles.',
      'Technical limits unavailable.')+'</p>';
    const effective=details.effective||{},proposed=details.proposed||{};
    const number=value=>Number.isFinite(value)?safe(this._number(value)):this._t(
      'Non défini','Not defined');
    const bytes=(value,unit)=>Number.isFinite(value)?
      number(value/(unit==="Mio"?1048576:1024))+' '+unit:
      this._t('Non défini','Not defined');
    const line=(fr,en,value)=>
      '<div class="line">'+safe(this._t(fr,en))+': <strong>'+value+'</strong></div>';
    const timeout=effective.timeouts_seconds||{};
    return '<details class="technical-limits"><summary>'+
      this._t('Limites et protections (lecture seule)',
        'Limits and safeguards (read-only)')+'</summary>'+
      '<p class="muted">'+this._t(
        'Valeurs effectives issues de l’intégration, non modifiables.',
        'Active limits reported by the integration; not editable.')+'</p>'+
      line('Taille maximale des réponses d’index','Maximum index response',
        bytes(effective.index_max_bytes,'Mio'))+
      line('Taille maximale des métadonnées','Maximum metadata response',
        bytes(effective.metadata_max_bytes,'Kio'))+
      line('Volume historique reçu au total','Aggregate received history limit',
        bytes(effective.max_history_received_bytes,'Mio'))+
      line('Lignes par réponse','Rows per response',number(effective.max_index_lines))+
      line('Points par réponse','Points per response',number(effective.max_index_points))+
      line('Délai HTTP des index','Index HTTP timeout',number(timeout.indexes)+' s')+
      line('Délai HTTP d’authentification','Authentication HTTP timeout',
        number(timeout.authentication)+' s')+
      line('Délai HTTP de découverte','Discovery HTTP timeout',number(timeout.housing)+' s')+
      line('Délai HTTP des appareils','Device HTTP timeout',number(timeout.device)+' s')+
      line('Tentatives transitoires','Transient attempts',number(effective.transient_max_attempts))+
      line('Itérations index (réauthentification comprise)','Index iterations (including reauth)',
        number(effective.max_index_iterations_with_reauth))+
      line('Temporisations transitoires','Transient retry delays',
        this._t('Base ','Base ')+number(effective.transient_backoff_base_ms)+
        ' ms + '+this._t('jitter ; plafond ','jitter; cap ')+
        number(effective.transient_backoff_max_ms)+' ms')+
      line('Pause entre sous-périodes historiques','Pause between history subwindows',
        number(effective.history_pause_ms)+' ms')+
      line('Lectures historiques simultanées par compte','Concurrent historical scans per account',
        effective.history_serialized_per_account?'1':this._t('Non vérifié','Unverified'))+
      line('Durée globale actuellement appliquée','Current overall duration limit',
        effective.max_global_duration_seconds===null?this._t('Non définie','Not defined'):
          number(effective.max_global_duration_seconds)+' s')+
      line('Appels HTTP actuellement plafonnés par opération','Current HTTP requests per operation',
        number(effective.max_global_http_requests))+
      '<h4>'+this._t('Budgets proposés — non actifs',
        'Proposed budgets — not yet active')+'</h4>'+
      '<p class="muted">'+this._t(
        'Valeurs candidates à confirmer après tests représentatifs.',
        'Candidate thresholds pending representative load tests.')+'</p>'+
      line('Analyse standard (durée / requêtes)','Standard (duration / requests)',
        number(proposed.standard?.duration_seconds)+' s / '+
        number(proposed.standard?.http_requests))+
      line('Analyse exhaustive (durée / requêtes)','Exhaustive (duration / requests)',
        number(proposed.exhaustive?.duration_seconds)+' s / '+
        number(proposed.exhaustive?.http_requests))+
      line('Temporisation historique proposée','Proposed history pause',
        number(proposed.proposed_pause_ms)+' ms')+
      line('Concurrence cible par compte','Target concurrency per account',
        number(proposed.max_concurrent_historical_scans_per_account))+
      '</details>';
  }
  _communicationDiagnostics() {
    const diagnostics=this._current?.communication_diagnostics||{};
    const recent=Array.isArray(diagnostics.recent)?diagnostics.recent:[];
    const active=Array.isArray(diagnostics.active)?diagnostics.active:[];
    const view=(operation)=>{
      const info=[operation.kind,operation.status,operation.started_at,
        operation.elapsed_seconds+' s',
        operation.http_requests+' '+this._t('requêtes','requests'),
        operation.retries+' '+this._t('tentatives supplémentaires','retries'),
        operation.subdivisions+' '+this._t('subdivisions','splits')].join(' · ');
      const details=this._t('Volume reçu','Received bytes')+': '+
        safe(operation.bytes_received??'—')+' octets · '+
        this._t('Plus grande réponse','Largest response')+': '+
        safe(operation.largest_response_bytes??'—')+' octets';
      return '<li><div>'+safe(info)+'</div><div class="muted">'+details+'</div>'+
        (operation.error_type?'<div class="muted">'+this._t('Cause','Cause')+
          ': '+safe(operation.error_type)+'</div>':"")+'</li>';
    };
    return '<section class="card" style="margin-top:16px">'+
      '<h3>'+this._t('Diagnostic des communications Trybatec',
        'Trybatec communications diagnostics')+'</h3>'+
      '<p class="muted">'+this._t(
        'Au plus 20 opérations conservées en mémoire pendant 24 heures ; aucun relevé ni identifiant de compte.',
        'At most 20 in-memory operations for 24 hours; no readings or account identifiers.')+'</p>'+
      (active.length?'<div class="notice">'+this._t('Opération(s) en cours',
        'Running operations')+': '+safe(active.length)+'</div>':"")+
      '<details><summary>'+this._t('Consulter les dernières opérations',
        'Inspect recent operations')+'</summary>'+
      (recent.length?'<ul>'+recent.slice(0,20).map(view).join('')+'</ul>':
        '<p class="muted">'+this._t('Aucun diagnostic disponible.',
        'No diagnostics available.')+'</p>')+'</details>'+
      '<div class="actions"><button type="button" class="secondary" data-copy-diagnostic>'+
      this._t('Copier le rapport expurgé','Copy redacted report')+'</button></div>'+
      '<div class="muted">'+this._t(
        'Copie locale uniquement ; aucun envoi automatique.',
        'Local copy only; no automatic transmission.')+'</div></section>';
  }
  async _copyDiagnostics() {
    if (!this._current || !this._data?.technical_limits || !navigator.clipboard?.writeText)
      return;
    const report={
      version:this._data.version,
      technical_limits:this._data.technical_limits,
      operations:this._current.communication_diagnostics,
    };
    // The backend deliberately provides only safe metrics and opaque job IDs.
    await navigator.clipboard.writeText(JSON.stringify(report,null,2));
  }
  _settings() {
    const settings={...this._current.settings,...this._settingsInput};
    const duration=this._durationInput||trybatecDurationParts(settings.poll_minutes);
    const durationField=(name,label,max)=>
      '<div><label for="duration-'+name+'">'+label+'</label>'+
      '<input id="duration-'+name+'" data-duration-field="'+name+'" type="number" min="0" max="'+max+
      '" step="1" value="'+safe(duration[name])+'"></div>';
    const durationMinutes=trybatecDurationMinutes(duration);
    const field=(key,label,min,max,description)=>
      '<div><label for="settings-'+key+'">'+label+'</label>'+
      '<input id="settings-'+key+'" data-settings-field="'+key+'" type="number" min="'+min+'" max="'+max+
      '" step="1" value="'+safe(settings[key])+'">'+
      '<div class="muted">'+description+'</div></div>';
    const logLevel=this._loggingInput??this._current.settings.log_level;
    return this._heading("Réglages","Options partagées avec Home Assistant : synchronisation, contrôles et diagnostics.")+
      '<section class="card"><h3>Synchronisation et contrôle des relevés</h3>'+
      '<p class="muted">Ces valeurs sont partagées avec les options natives Trybatec et conservées lors des mises à jour.</p>'+
      '<div class="form-grid" style="margin-top:18px">'+
      '<div class="poll-duration"><label>Fréquence de synchronisation</label>'+
      '<div class="duration-inputs">'+durationField("days","Jours",7)+
      durationField("hours","Heures",23)+durationField("minutes","Minutes",59)+'</div>'+
      '<div class="muted">'+(Number.isFinite(durationMinutes)?
      'Durée totale : '+safe(this._number(durationMinutes))+' minutes. ':
      'Durée invalide : choisissez entre 1 heure et 7 jours. ')+
      'La modification peut recharger l’intégration.</div></div>'+
      field("sparse_hours","Intervalle à signaler (heures)",1,87600,
        "Par défaut : 27 h. Un intervalle strictement supérieur est considéré comme espacé.")+
      field("zero_review_days","Index nuls consécutifs (jours)",0,36500,
        "0 désactive la sollicitation ; 1 signale dès le premier jour avec un index nul.")+
      '</div>'+
      (this._settingsError?'<div role="alert" class="notice warning">'+safe(this._settingsError)+'</div>':"")+
      (this._settingsMessage?'<div role="status" class="notice">'+safe(this._settingsMessage)+'</div>':"")+
      '<div class="actions"><button class="primary" type="button" data-settings-save '+(this._settingsBusy?"disabled":"")+'>Enregistrer ces réglages</button>'+
      '<button class="secondary" type="button" data-settings-reset>Annuler les modifications</button></div>'+
      '<div class="notice">Aucune modification des index source, de Recorder ou du tableau Énergie.</div>'+
      '</section>'+
      '<section class="card" style="margin-top:16px"><h3>Journalisation et diagnostics</h3>'+
      '<p class="muted">Le niveau est enregistré pour ce compte, mais concerne <strong>tous les modules Trybatec</strong> : synchronisation, communication avec le portail, historiques, services et diagnostics. En présence de plusieurs comptes Trybatec, le niveau le plus détaillé prévaut. Les autres intégrations et le journal global restent inchangés.</p>'+
      '<div class="form-grid" style="margin-top:18px"><div class="logging-field">'+
      '<label for="settings-log">Niveau de journalisation</label>'+
      '<select id="settings-log" data-log-level>'+
      ["ERROR","WARNING","INFO","DEBUG"].map(level=>
        '<option value="'+level+'" '+(logLevel===level?"selected":"")+'>'+level+'</option>'
      ).join("")+'</select><div class="muted">WARNING est recommandé en usage courant. DEBUG augmente la quantité de messages de diagnostic.</div></div></div>'+
      (this._loggingError?'<div role="alert" class="notice warning">'+safe(this._loggingError)+'</div>':"")+
      (this._loggingMessage?'<div role="status" class="notice">'+safe(this._loggingMessage)+'</div>':"")+
      '<div class="actions"><button type="button" class="primary" data-log-save '+
      (this._loggingBusy?"disabled":"")+'>Enregistrer la journalisation</button>'+
      '<button type="button" class="secondary" data-log-reset>Annuler la modification</button>'+
      '<button type="button" class="secondary" data-tab="diagnostics">Afficher les diagnostics</button></div>'+
      this._technicalLimits()+
      '</section>'+
      '<section class="card" style="margin-top:16px"><h3>Accès de secours aux options natives</h3>'+
      '<p class="muted">Les unités, UUID, paramètres de diagnostic et parcours historiques sont disponibles dans ce panneau. Le menu natif reste accessible en secours tant que la recette de parité fonctionnelle n’est pas achevée.</p>'+
      '<div class="actions"><button class="secondary" type="button" data-open-options>Ouvrir les options natives de secours</button></div></section>';
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
    // Search is the only text input that requires an immediate list redraw.
    // For dates/times/numbers _change deliberately avoids this DOM replacement.
    const active=this.shadowRoot.activeElement;
    const searchFocused=active?.hasAttribute?.("data-query");
    const start=searchFocused ? active.selectionStart : null;
    const end=searchFocused ? active.selectionEnd : null;
    this.shadowRoot.innerHTML='<style>'+style+'</style><div class="wrap">'+this._header()+
      '<div data-version-notice class="notice warning" role="status" aria-live="polite" hidden style="display:none"></div>'+
      '<div class="shell">'+this._nav()+'<main class="main" id="main">'+this._content()+'</main></div>'+
      '<footer class="footer">Trybatec — Interface expérimentale · Aucune suppression ni écriture Recorder ou Énergie automatique.</footer></div>';
    localizeTrybatecPanel(this.shadowRoot,this._hass?.language);
    if (searchFocused) {
      const search=this.shadowRoot.querySelector("[data-query]");
      search?.focus();
      if (search && start!==null && end!==null) search.setSelectionRange(start,end);
    }
    this._renderVersionNotice();
    this._syncNav();
  }
}
if (!customElements.get("trybatec-panel")) customElements.define("trybatec-panel", TrybatecPanel);
