export class ValidationError extends Error {}
const fail = (message) => {
  throw new ValidationError(message);
};
const number = (n, label, min, max) => {
  if (typeof n !== "number" || !Number.isFinite(n) || n < min || n > max)
    fail(`${label} : nombre attendu entre ${min} et ${max}.`);
};
const text = (s, label) => {
  if (typeof s !== "string" || !s.trim() || s.length > 120)
    fail(`${label} : texte de 1 à 120 caractères attendu.`);
};
export function validatePolicy(p) {
  if (!p || p.schemaVersion !== 1)
    fail("Version de configuration non prise en charge.");
  text(p.name, "Nom du profil");
  if (
    ![
      "numeric",
      "percentage",
      "letters",
      "appreciation",
      "competency",
    ].includes(p.scale?.kind)
  )
    fail("Type de barème inconnu.");
  number(p.scale.max, "Maximum", 0.01, 100000);
  number(p.precision, "Décimales", 0, 4);
  if (!Number.isInteger(p.precision))
    fail("Le nombre de décimales doit être entier.");
  if (!["exclude", "zero"].includes(p.missing))
    fail("Gestion des absences inconnue.");
  if (!Array.isArray(p.bands) || !p.bands.length || p.bands.length > 30)
    fail("Prévoir de 1 à 30 niveaux.");
  if (p.bands.some((b) => !b || typeof b !== "object"))
    fail("Niveau invalide.");
  const sorted = [...p.bands].sort((a, b) => a.min - b.min);
  const labels = new Set();
  sorted.forEach((b, i) => {
    number(b.min, "Seuil (%)", 0, 100);
    text(b.label, "Libellé");
    if (i === 0 && b.min !== 0) fail("Le premier seuil doit commencer à 0 %.");
    if (i && b.min === sorted[i - 1].min)
      fail("Les seuils doivent être distincts.");
    if (labels.has(b.label.trim()))
      fail("Les libellés doivent être distincts.");
    labels.add(b.label.trim());
    number(
      b.value,
      "Équivalence (%)",
      b.min,
      i + 1 < sorted.length ? sorted[i + 1].min : 100,
    );
    if (i + 1 < sorted.length && b.value === sorted[i + 1].min)
      fail("Une équivalence doit rester dans son niveau.");
  });
  if (
    !p.report ||
    typeof p.report.showScore !== "boolean" ||
    typeof p.report.showLabel !== "boolean"
  )
    fail("Options de bulletin invalides.");
  if (!p.report.showScore && !p.report.showLabel)
    fail("Le bulletin doit afficher au moins un résultat.");
  if (!p.notification || typeof p.notification.enabled !== "boolean")
    fail("Règle de notification invalide.");
  number(p.notification.below, "Seuil de notification (%)", 0, 100);
  text(p.notification.message, "Message de notification");
  return p;
}
export function evaluate(policy, entries) {
  validatePolicy(policy);
  if (!Array.isArray(entries) || !entries.length || entries.length > 100)
    fail("Prévoir de 1 à 100 évaluations.");
  let total = 0,
    weights = 0;
  for (const e of entries) {
    if (!e || typeof e !== "object") fail("Évaluation invalide.");
    number(e.weight, "Coefficient", 0.01, 1000);
    if (e.score === null && policy.missing === "exclude") continue;
    let percent = 0;
    if (e.score !== null) {
      if (["numeric", "percentage"].includes(policy.scale.kind)) {
        const maximum =
          policy.scale.kind === "percentage" ? 100 : policy.scale.max;
        number(e.score, "Note", 0, maximum);
        percent = (e.score / maximum) * 100;
      } else {
        const band = policy.bands.find((b) => b.label === e.score);
        if (!band) fail("Niveau inconnu dans une évaluation.");
        percent = band.value;
      }
    }
    total += percent * e.weight;
    weights += e.weight;
  }
  if (!weights)
    return {
      status: "empty",
      score: null,
      percent: null,
      label: null,
      notification: null,
    };
  const rawPercent = total / weights;
  const label = [...policy.bands]
    .sort((a, b) => b.min - a.min)
    .find((b) => rawPercent >= b.min).label;
  const maximum = policy.scale.kind === "percentage" ? 100 : policy.scale.max;
  const score = Number(
    ((rawPercent / 100) * maximum).toFixed(policy.precision),
  );
  return {
    status: "calculated",
    score,
    percent: Number(rawPercent.toFixed(6)),
    label,
    notification:
      policy.notification.enabled && rawPercent < policy.notification.below
        ? policy.notification.message
        : null,
  };
}
