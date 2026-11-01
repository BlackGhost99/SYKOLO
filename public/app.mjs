import { validatePolicy, evaluate } from "/domain/policy.mjs";
import { presets } from "/domain/presets.mjs";
const $ = (id) => document.getElementById(id),
  clone = (x) => structuredClone(x);
const storageKey = "sykolo.policies.v1";
let policy = clone(presets.find((p) => p.id === "numeric-20").policy),
  entries = [],
  profiles = [],
  selectedId = null,
  dirty = false;
const feedback = (message, error = false) => {
  $("feedback").className = error ? "error" : "success";
  $("feedback").textContent = message;
};
const input = (type, value, label) => {
  const el = document.createElement("input");
  el.type = type;
  el.value = value;
  el.setAttribute("aria-label", label);
  if (type === "number") el.step = "any";
  return el;
};
const option = (value, label) => {
  const el = document.createElement("option");
  el.value = value;
  el.textContent = label;
  return el;
};
function refreshSaved() {
  $("saved").replaceChildren(option("", "Choisir un profil…"));
  for (const p of profiles) $("saved").append(option(p.id, p.policy.name));
  $("saved").value = selectedId || "";
  $("profile-count").textContent =
    `${profiles.length} profil${profiles.length > 1 ? "s" : ""}`;
}
try {
  const data = JSON.parse(localStorage.getItem(storageKey) || "[]");
  if (!Array.isArray(data) || data.length > 100) throw Error();
  data.forEach((p) => {
    if (typeof p.id !== "string") throw Error();
    validatePolicy(p.policy);
  });
  profiles = data;
} catch {
  feedback(
    "La sauvegarde locale est indisponible ou invalide. Vous pouvez utiliser les exports JSON.",
    true,
  );
}
function newEntries() {
  const symbolic = !["numeric", "percentage"].includes(policy.scale.kind);
  const max = policy.scale.kind === "percentage" ? 100 : policy.scale.max;
  entries = [
    {
      score: symbolic
        ? policy.bands.at(-2)?.label || policy.bands[0].label
        : max * 0.7,
      weight: 1,
    },
    { score: symbolic ? policy.bands.at(-1).label : max * 0.8, weight: 2 },
  ];
}
function renderBands() {
  $("bands").replaceChildren();
  policy.bands.forEach((b, i) => {
    const row = document.createElement("tr");
    for (const [key, label] of [
      ["min", "Seuil"],
      ["label", "Libellé"],
      ["value", "Équivalence"],
    ]) {
      const td = document.createElement("td"),
        el = input(
          key === "label" ? "text" : "number",
          b[key],
          `${label} du niveau ${i + 1}`,
        );
      if (key === "label") el.maxLength = 120;
      el.addEventListener("input", () => {
        const before = b.label;
        b[key] =
          key === "label" ? el.value : el.value === "" ? NaN : Number(el.value);
        if (key === "label") {
          entries.forEach((e) => {
            if (e.score === before) e.score = el.value;
          });
          renderEntries();
        }
        changed();
      });
      td.append(el);
      row.append(td);
    }
    const td = document.createElement("td"),
      remove = document.createElement("button");
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Supprimer le niveau ${i + 1}`);
    remove.disabled = policy.bands.length === 1;
    remove.onclick = () => {
      policy.bands.splice(i, 1);
      entries.forEach((e) => {
        if (e.score === b.label) e.score = null;
      });
      renderBands();
      renderEntries();
      changed();
    };
    td.append(remove);
    row.append(td);
    $("bands").append(row);
  });
}
function renderEntries() {
  $("entries").replaceChildren();
  const numeric = ["numeric", "percentage"].includes(policy.scale.kind);
  entries.forEach((e, i) => {
    const row = document.createElement("div");
    row.className = "entry";
    const group = document.createElement("div"),
      label = document.createElement("label");
    label.textContent = `Évaluation ${i + 1}`;
    label.htmlFor = `score-${i}`;
    let score;
    if (numeric) {
      score = input("number", e.score ?? "", `Note évaluation ${i + 1}`);
      score.min = 0;
      score.max = policy.scale.kind === "percentage" ? 100 : policy.scale.max;
    } else {
      score = document.createElement("select");
      score.setAttribute("aria-label", `Niveau évaluation ${i + 1}`);
      score.append(option("", "Absente"));
      policy.bands.forEach((b) => score.append(option(b.label, b.label)));
      score.value = e.score ?? "";
    }
    score.id = `score-${i}`;
    score.addEventListener("input", () => {
      e.score =
        score.value === "" ? null : numeric ? Number(score.value) : score.value;
      updateResult();
    });
    group.append(label, score);
    const wg = document.createElement("div"),
      wl = document.createElement("label");
    wl.textContent = "Coefficient";
    wl.htmlFor = `weight-${i}`;
    const weight = input("number", e.weight, `Coefficient évaluation ${i + 1}`);
    weight.id = `weight-${i}`;
    weight.min = 0.01;
    weight.max = 1000;
    weight.addEventListener("input", () => {
      e.weight = weight.value === "" ? NaN : Number(weight.value);
      updateResult();
    });
    wg.append(wl, weight);
    const remove = document.createElement("button");
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Supprimer l’évaluation ${i + 1}`);
    remove.disabled = entries.length === 1;
    remove.onclick = () => {
      entries.splice(i, 1);
      renderEntries();
      updateResult();
    };
    row.append(group, wg, remove);
    $("entries").append(row);
  });
}
function updateResult() {
  $("report-name").textContent = policy.name;
  $("result").replaceChildren();
  try {
    const result = evaluate(policy, entries);
    if (result.status === "empty") {
      $("result").textContent =
        "Aucun résultat : toutes les notes sont absentes.";
      return;
    }
    if (policy.report.showScore) {
      const score = document.createElement("div");
      score.className = "score";
      score.textContent = result.score.toLocaleString("fr-FR", {
        maximumFractionDigits: policy.precision,
      });
      const max = document.createElement("small");
      max.textContent =
        policy.scale.kind === "percentage" ? " %" : ` / ${policy.scale.max}`;
      score.append(max);
      $("result").append(score);
    }
    if (policy.report.showLabel) {
      const label = document.createElement("div");
      label.className = "result-label";
      label.textContent = result.label;
      $("result").append(label);
    }
    if (result.notification) {
      const message = document.createElement("p");
      message.className = "alert-preview";
      message.textContent = `Alerte à prévoir : ${result.notification}`;
      $("result").append(message);
    }
  } catch (e) {
    const error = document.createElement("p");
    error.textContent = e.message;
    error.className = "alert-preview";
    $("result").append(error);
  }
}
function changed() {
  dirty = true;
  $("save-status").textContent = "Modifications à enregistrer";
  updateResult();
}
function render() {
  for (const [id, value] of Object.entries({
    name: policy.name,
    kind: policy.scale.kind,
    maximum: policy.scale.max,
    precision: policy.precision,
    missing: policy.missing,
    below: policy.notification.below,
    message: policy.notification.message,
  }))
    $(id).value = value;
  $("maximum").disabled = policy.scale.kind !== "numeric";
  $("show-score").checked = policy.report.showScore;
  $("show-label").checked = policy.report.showLabel;
  $("notify").checked = policy.notification.enabled;
  renderBands();
  renderEntries();
  refreshSaved();
  updateResult();
}
for (const preset of presets)
  $("preset").append(option(preset.id, preset.title));
$("preset").value = "numeric-20";
$("preset").onchange = () => {
  policy = clone(presets.find((p) => p.id === $("preset").value).policy);
  selectedId = null;
  newEntries();
  render();
  changed();
};
$("kind").onchange = () => {
  policy.scale.kind = $("kind").value;
  if (policy.scale.kind !== "numeric") policy.scale.max = 100;
  newEntries();
  render();
  changed();
};
for (const [id, set] of Object.entries({
  name: (v) => (policy.name = v),
  maximum: (v) => (policy.scale.max = v === "" ? NaN : Number(v)),
  precision: (v) => (policy.precision = Number(v)),
  missing: (v) => (policy.missing = v),
  below: (v) => (policy.notification.below = v === "" ? NaN : Number(v)),
  message: (v) => (policy.notification.message = v),
}))
  $(id).addEventListener("input", () => {
    set($(id).value);
    if (id === "maximum") renderEntries();
    changed();
  });
for (const [id, set] of Object.entries({
  "show-score": (v) => (policy.report.showScore = v),
  "show-label": (v) => (policy.report.showLabel = v),
  notify: (v) => (policy.notification.enabled = v),
}))
  $(id).onchange = () => {
    set($(id).checked);
    changed();
  };
$("add-band").onclick = () => {
  if (policy.bands.length >= 30) return feedback("Maximum : 30 niveaux.", true);
  policy.bands.push({
    min: 100,
    label: `Niveau ${policy.bands.length + 1}`,
    value: 100,
  });
  renderBands();
  renderEntries();
  changed();
};
$("add-entry").onclick = () => {
  if (entries.length >= 100) return;
  entries.push({ score: null, weight: 1 });
  renderEntries();
  updateResult();
};
$("save").onclick = () => {
  try {
    validatePolicy(policy);
    if (!selectedId && profiles.length >= 100)
      throw Error("Maximum : 100 profils.");
    const id = selectedId || crypto.randomUUID();
    const next = profiles.filter((p) => p.id !== id);
    next.push({
      id,
      policy: clone(policy),
      updatedAt: new Date().toISOString(),
    });
    localStorage.setItem(storageKey, JSON.stringify(next));
    profiles = next;
    selectedId = id;
    dirty = false;
    refreshSaved();
    $("save-status").textContent = "Profil enregistré dans ce navigateur";
    feedback(
      "Profil enregistré. Exportez une copie pour le conserver ailleurs.",
    );
  } catch (e) {
    feedback(
      e.message || "Sauvegarde impossible. Exportez votre profil.",
      true,
    );
  }
};
$("saved").onchange = () => {
  const saved = profiles.find((p) => p.id === $("saved").value);
  if (!saved) return;
  policy = clone(saved.policy);
  selectedId = saved.id;
  newEntries();
  render();
  dirty = false;
  $("save-status").textContent = "Profil enregistré chargé";
};
$("export").onclick = () => {
  try {
    validatePolicy(policy);
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(policy, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "sykolo-profil.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    feedback("Profil exporté au format JSON.");
  } catch (e) {
    feedback(e.message, true);
  }
};
$("import").onchange = async () => {
  const file = $("import").files[0];
  if (!file) return;
  try {
    if (file.size > 65536)
      throw Error("Fichier trop volumineux (maximum 64 Ko).");
    const candidate = JSON.parse(await file.text());
    validatePolicy(candidate);
    policy = clone(candidate);
    selectedId = null;
    newEntries();
    render();
    changed();
    feedback("Profil importé et validé. Enregistrez-le pour le retrouver.");
  } catch (e) {
    feedback(`Import refusé : ${e.message}`, true);
  } finally {
    $("import").value = "";
  }
};
window.addEventListener("beforeunload", (e) => {
  if (dirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
newEntries();
render();
fetch("/healthz")
  .then((r) => r.json())
  .then((v) => {
    $("version").textContent = `v${v.version} · ${v.commit.slice(0, 7)}`;
  })
  .catch(() => {});
