/** L7 read-only UI fragment: never registers an activation command or HA endpoint.
 * FR: Vue préparatoire uniquement. EN: Preview only, not a live action.
 */
export function renderEnergyBulkDraft(report, language = "fr", setupAssistantHref = "#") {
  const fr = language !== "en";
  const labels = fr ? {
    heading: "Ajout groupé Énergie — prévisualisation",
    pending: "Activation indisponible : preuves et recette requises",
    fallback: "Ouvrir l’assistant de configuration",
    action: "Ajouter les consommations (désactivé)",
    blocked: "Bloqué", insufficient_evidence: "Preuves insuffisantes",
    already_configured: "Déjà configuré", admissible: "Admissible (non activable)",
    missing: "État indisponible",
  } : {
    heading: "Bulk Energy enrollment — preview",
    pending: "Activation unavailable: evidence and acceptance required",
    fallback: "Open configuration assistant",
    action: "Add consumption (disabled)",
    blocked: "Blocked", insufficient_evidence: "Insufficient evidence",
    already_configured: "Already configured", admissible: "Admissible (not activatable)",
    missing: "Status unavailable",
  };
  const section = document.createElement("section");
  section.setAttribute("aria-label", labels.heading);
  const title = document.createElement("h3");
  title.textContent = labels.heading;
  section.append(title);
  const status = document.createElement("p");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  status.textContent = labels.pending;
  section.append(status);
  const list = document.createElement("ul");
  const entries = report && typeof report === "object" && report.fluids &&
    typeof report.fluids === "object" ? report.fluids : {};
  for (const [fluid, display] of [["EF", fr ? "Eau froide" : "Cold water"],
                                  ["ECS", fr ? "Eau chaude" : "Hot water"],
                                  ["CET", fr ? "Chauffage" : "Heating"]]) {
    const item = document.createElement("li");
    const row = entries[fluid];
    const outcome = row && typeof row.status === "string" ? row.status : "missing";
    const reasons = row && Array.isArray(row.reasons) ?
      row.reasons.filter(reason => typeof reason === "string").slice(0, 10) : [];
    item.textContent = `${display} : ${labels[outcome] || labels.missing}`;
    if (reasons.length) {
      const note = document.createElement("small");
      note.textContent = " — " + reasons.join(", ");
      item.append(note);
    }
    list.append(item);
  }
  section.append(list);
  const link = document.createElement("a");
  link.setAttribute("href", typeof setupAssistantHref === "string" &&
                    /^\/[a-zA-Z0-9/_#?=&.%-]*$/.test(setupAssistantHref) &&
                    !setupAssistantHref.includes("//") ? setupAssistantHref : "#");
  link.textContent = labels.fallback;
  section.append(link);
  const disabled = document.createElement("button");
  disabled.setAttribute("type", "button");
  disabled.disabled = true;
  disabled.textContent = labels.action;
  section.append(disabled);
  return section;
}
