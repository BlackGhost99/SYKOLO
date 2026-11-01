import React, { useEffect, useState, useRef } from "react";
const KEY = "sykolo.policies.v1";
const clone = (x) => structuredClone(x);
const csrf = () =>
  document.cookie
    .split("; ")
    .find((c) => c.startsWith("csrftoken="))
    ?.split("=")[1] || "";
export async function api(path, data, signal) {
  const response = await fetch(path, {
    method: data === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers:
      data === undefined
        ? {}
        : { "Content-Type": "application/json", "X-CSRFToken": csrf() },
    body: data === undefined ? undefined : JSON.stringify(data),
    signal,
  });
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw Error("Le service est indisponible. Réessayez.");
  const body = await response.json();
  if (!response.ok) throw Error(body.error || "Requête refusée.");
  return body;
}
function examples(p) {
  const numeric = ["numeric", "percentage"].includes(p.scale.kind),
    max = p.scale.kind === "percentage" ? 100 : p.scale.max;
  return [
    {
      score: numeric ? max * 0.7 : p.bands.at(-2)?.label || p.bands[0].label,
      weight: 1,
    },
    { score: numeric ? max * 0.8 : p.bands.at(-1).label, weight: 2 },
  ];
}
function readProfiles() {
  try {
    const p = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(p) && p.length <= 100
      ? p.filter(
          (x) =>
            typeof x.id === "string" &&
            x.policy &&
            typeof x.policy.name === "string",
        )
      : [];
  } catch {
    return [];
  }
}
function Field({ label, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}
function Check({ label, checked, onChange }) {
  return (
    <label className="check">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  );
}
export default function App() {
  const [presets, setPresets] = useState([]),
    [policy, setPolicy] = useState(null),
    [entries, setEntries] = useState([]),
    [result, setResult] = useState(null),
    [calculationError, setCalculationError] = useState(""),
    [profiles, setProfiles] = useState(readProfiles),
    [selected, setSelected] = useState(""),
    [preset, setPreset] = useState("numeric-20"),
    [notice, setNotice] = useState(null),
    [dirty, setDirty] = useState(false),
    [version, setVersion] = useState(null),
    [busy, setBusy] = useState(false);
  const importRef = useRef(null),
    policyRef = useRef(policy);
  policyRef.current = policy;
  useEffect(() => {
    api("/api/v1/presets")
      .then((data) => {
        setPresets(data);
        const p = clone(data.find((x) => x.id === "numeric-20").policy);
        setPolicy(p);
        setEntries(examples(p));
      })
      .catch((e) => setNotice({ error: true, message: e.message }));
    api("/healthz")
      .then(setVersion)
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (!policy) return;
    const controller = new AbortController();
    setResult(null);
    setCalculationError("");
    const timer = setTimeout(
      () =>
        api("/api/v1/evaluate", { policy, entries }, controller.signal)
          .then(setResult)
          .catch((e) => {
            if (e.name !== "AbortError") setCalculationError(e.message);
          }),
      150,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [policy, entries]);
  useEffect(() => {
    const warn = (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const change = (fn) => {
    setPolicy((p) => {
      const next = clone(p);
      fn(next);
      return next;
    });
    setDirty(true);
  };
  const load = (p, id = "", presetId = "") => {
    setPolicy(clone(p));
    setEntries(examples(p));
    setSelected(id);
    setPreset(presetId);
    setDirty(false);
  };
  const notify = (message, error = false) => setNotice({ message, error });
  async function save() {
    const snapshot = clone(policy);
    setBusy(true);
    try {
      await api("/api/v1/policies/validate", snapshot);
      if (!selected && profiles.length >= 100)
        throw Error("Maximum : 100 profils.");
      const id = selected || crypto.randomUUID(),
        next = [
          ...profiles.filter((x) => x.id !== id),
          { id, policy: snapshot, updatedAt: new Date().toISOString() },
        ];
      localStorage.setItem(KEY, JSON.stringify(next));
      setProfiles(next);
      setSelected(id);
      if (JSON.stringify(policyRef.current) === JSON.stringify(snapshot))
        setDirty(false);
      notify(
        "Profil enregistré dans ce navigateur. Exportez une copie pour le conserver.",
      );
    } catch (e) {
      notify(e.message, true);
    } finally {
      setBusy(false);
    }
  }
  async function exportPolicy() {
    try {
      await api("/api/v1/policies/validate", policy);
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(policy, null, 2)], {
          type: "application/json",
        }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = "sykolo-profil.json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      notify("Profil exporté.");
    } catch (e) {
      notify(e.message, true);
    }
  }
  async function importPolicy(e) {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    try {
      if (file.size > 65536) throw Error("Maximum : 64 Ko.");
      const p = JSON.parse(await file.text());
      await api("/api/v1/policies/validate", p);
      load(p);
      setDirty(true);
      notify("Profil importé et validé. Enregistrez-le pour le retrouver.");
    } catch (error) {
      notify(`Import refusé : ${error.message}`, true);
    }
  }
  async function openSaved(id) {
    const p = profiles.find((x) => x.id === id);
    if (!p) return;
    try {
      await api("/api/v1/policies/validate", p.policy);
      load(p.policy, id);
    } catch (e) {
      notify(e.message, true);
    }
  }
  const numeric =
    policy && ["numeric", "percentage"].includes(policy.scale.kind);
  const setEntry = (i, key, value) =>
    setEntries((es) =>
      es.map((e, j) => (i === j ? { ...e, [key]: value } : e)),
    );
  return (
    <>
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="SYKOLO accueil">
          <span className="brand-icon">S</span>SYKOLO
          <span className="brand-dot">.</span>
        </a>
        <p className="side-label">PHASE 1 · FONDATIONS</p>
        <a className="nav active" href="#configuration">
          <span>◈</span>01 · Architecture & déploiement
        </a>
        <a className="nav" href="#roadmap">
          <span>◎</span>02 · Authentification & sécurité
        </a>
        <a className="nav" href="#roadmap">
          <span>▦</span>03 · Multi-établissements
        </a>
        <div className="sidebar-bottom">
          <span className="avatar">SY</span>
          <div>
            Atelier SYKOLO<small>Fondations · v0.2.0</small>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header>
          <span>
            Fondations <span className="separator">/</span>Laboratoire
            pédagogique
          </span>
          <span className="badge">
            <i />
            Module 01 · Démonstrateur
          </span>
        </header>
        <main>
          <div className="heading">
            <div>
              <p className="eyebrow">VOTRE ÉCOLE, VOS RÈGLES</p>
              <h1>Une pédagogie à votre mesure.</h1>
              <p className="intro">
                Configurez vos barèmes. Ajustez vos règles. Voyez le résultat.
              </p>
            </div>
            <button
              className="primary"
              onClick={save}
              disabled={!policy || busy}
            >
              Enregistrer le profil <span>↗</span>
            </button>
          </div>
          <div className="notice">
            <span>ⓘ</span>
            <p>
              Atelier de démonstration. Les profils restent dans ce navigateur
              et sont exportables. Utilisez uniquement des données fictives. Les
              comptes et l’isolation des écoles seront traités aux modules 02 et
              03.
            </p>
          </div>
          {notice && (
            <div role="status" className={notice.error ? "error" : "success"}>
              {notice.message}
            </div>
          )}
          <section className="summary">
            <div>
              <small>01 / SOCLE TECHNIQUE</small>
              <strong>Django/API · React · PostgreSQL</strong>
              <span>Déploiement Docker et contrôles automatisés</span>
            </div>
            <div>
              <small>BARÈMES DISPONIBLES</small>
              <strong>{presets.length} points de départ</strong>
              <span>Tous entièrement personnalisables</span>
            </div>
            <div>
              <small>PROFILS ENREGISTRÉS</small>
              <strong>
                {profiles.length} profil{profiles.length > 1 ? "s" : ""}
              </strong>
              <span>
                {dirty
                  ? "Modifications à enregistrer"
                  : "Sauvegarde locale au navigateur"}
              </span>
            </div>
          </section>
          {!policy ? (
            <p role="status">Chargement de l’atelier…</p>
          ) : (
            <div className="columns">
              <section className="card" id="configuration">
                <div className="section-title">
                  <div>
                    <span className="step">01</span>
                    <h2>Construire votre profil</h2>
                  </div>
                  <span className="tag">Personnalisable</span>
                </div>
                <Field label="Partir d’un modèle">
                  <select
                    value={preset}
                    onChange={(e) => {
                      const p = presets.find((x) => x.id === e.target.value);
                      if (p) {
                        load(p.policy, "", p.id);
                        setDirty(true);
                      }
                    }}
                  >
                    <option value="">Profil personnalisé</option>
                    {presets.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title}
                      </option>
                    ))}
                  </select>
                </Field>
                <div className="two">
                  <Field label="Nom du profil">
                    <input
                      value={policy.name}
                      maxLength={120}
                      onChange={(e) => change((p) => (p.name = e.target.value))}
                    />
                  </Field>
                  <Field label="Mode d’évaluation">
                    <select
                      value={policy.scale.kind}
                      onChange={(e) => {
                        const kind = e.target.value;
                        const p = clone(policy);
                        p.scale.kind = kind;
                        if (kind !== "numeric") p.scale.max = 100;
                        setPolicy(p);
                        setEntries(examples(p));
                        setDirty(true);
                      }}
                    >
                      {[
                        ["numeric", "Notes numériques"],
                        ["percentage", "Pourcentages"],
                        ["letters", "Lettres"],
                        ["appreciation", "Appréciations"],
                        ["competency", "Compétences"],
                      ].map(([v, label]) => (
                        <option key={v} value={v}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>
                <div className="three">
                  <Field label="Note maximale">
                    <input
                      type="number"
                      min="0.01"
                      step="any"
                      max="100000"
                      disabled={policy.scale.kind !== "numeric"}
                      value={policy.scale.max}
                      onChange={(e) =>
                        change((p) => (p.scale.max = Number(e.target.value)))
                      }
                    />
                  </Field>
                  <Field label="Décimales">
                    <select
                      value={policy.precision}
                      onChange={(e) =>
                        change((p) => (p.precision = Number(e.target.value)))
                      }
                    >
                      {[0, 1, 2, 3, 4].map((n) => (
                        <option key={n}>{n}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Note absente">
                    <select
                      value={policy.missing}
                      onChange={(e) =>
                        change((p) => (p.missing = e.target.value))
                      }
                    >
                      <option value="exclude">Exclure du calcul</option>
                      <option value="zero">Compter comme zéro</option>
                    </select>
                  </Field>
                </div>
                <div className="subheading">
                  <h3>Niveaux & appréciations</h3>
                  <button
                    className="text-button"
                    disabled={policy.bands.length >= 30}
                    onClick={() =>
                      change((p) =>
                        p.bands.push({
                          min: 100,
                          label: `Niveau ${p.bands.length + 1}`,
                          value: 100,
                        }),
                      )
                    }
                  >
                    + Ajouter un niveau
                  </button>
                </div>
                <p className="hint">
                  Seuil inférieur inclus, jusqu’au seuil suivant. Les
                  équivalences servent au calcul des lettres et compétences.
                </p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>À partir de (%)</th>
                        <th>Libellé</th>
                        <th>Équivalence (%)</th>
                        <th>
                          <span className="sr-only">Actions</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {policy.bands.map((b, i) => (
                        <tr key={i}>
                          {[
                            ["min", "Seuil"],
                            ["label", "Libellé"],
                            ["value", "Équivalence"],
                          ].map(([key, label]) => (
                            <td key={key}>
                              <input
                                aria-label={`${label} du niveau ${i + 1}`}
                                type={key === "label" ? "text" : "number"}
                                step="any"
                                value={b[key]}
                                maxLength={120}
                                onChange={(e) => {
                                  const value =
                                    key === "label"
                                      ? e.target.value
                                      : Number(e.target.value);
                                  change((p) => (p.bands[i][key] = value));
                                  if (key === "label")
                                    setEntries((es) =>
                                      es.map((entry) =>
                                        entry.score === b.label
                                          ? { ...entry, score: value }
                                          : entry,
                                      ),
                                    );
                                }}
                              />
                            </td>
                          ))}
                          <td>
                            <button
                              aria-label={`Supprimer le niveau ${i + 1}`}
                              disabled={policy.bands.length === 1}
                              onClick={() => {
                                change((p) => p.bands.splice(i, 1));
                                setEntries((es) =>
                                  es.map((entry) =>
                                    entry.score === b.label
                                      ? { ...entry, score: null }
                                      : entry,
                                  ),
                                );
                              }}
                            >
                              ×
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="options">
                  <h3>Affichage du bulletin</h3>
                  <Check
                    label="Afficher le résultat chiffré"
                    checked={policy.report.showScore}
                    onChange={(v) => change((p) => (p.report.showScore = v))}
                  />
                  <Check
                    label="Afficher le niveau / l’appréciation"
                    checked={policy.report.showLabel}
                    onChange={(v) => change((p) => (p.report.showLabel = v))}
                  />
                </div>
                <div className="options">
                  <h3>Règle de notification</h3>
                  <Check
                    label="Préparer une alerte sous un seuil"
                    checked={policy.notification.enabled}
                    onChange={(v) =>
                      change((p) => (p.notification.enabled = v))
                    }
                  />
                  <Field label="Seuil de déclenchement (%)">
                    <input
                      type="number"
                      step="any"
                      min="0"
                      max="100"
                      value={policy.notification.below}
                      onChange={(e) =>
                        change(
                          (p) =>
                            (p.notification.below = Number(e.target.value)),
                        )
                      }
                    />
                  </Field>
                  <Field label="Message">
                    <input
                      maxLength={120}
                      value={policy.notification.message}
                      onChange={(e) =>
                        change((p) => (p.notification.message = e.target.value))
                      }
                    />
                  </Field>
                  <p className="hint">
                    Prévisualisation uniquement. Aucun SMS ni e-mail n’est
                    envoyé.
                  </p>
                </div>
                <div className="actions">
                  <button onClick={exportPolicy}>↓ Exporter JSON</button>
                  <button onClick={() => importRef.current.click()}>
                    ↑ Importer JSON
                  </button>
                  <input
                    ref={importRef}
                    type="file"
                    accept="application/json,.json"
                    hidden
                    onChange={importPolicy}
                  />
                </div>
                <Field label="Ouvrir un profil enregistré">
                  <select
                    value={selected}
                    onChange={(e) => openSaved(e.target.value)}
                  >
                    <option value="">Choisir un profil…</option>
                    {profiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.policy.name}
                      </option>
                    ))}
                  </select>
                </Field>
              </section>
              <div className="right-column">
                <section className="card" id="simulation">
                  <div className="section-title">
                    <div>
                      <span className="step">02</span>
                      <h2>Tester les règles</h2>
                    </div>
                    <span className="live-dot">Calcul par l’API Django</span>
                  </div>
                  <p className="hint">
                    Évaluations fictives avec coefficients. Une note vide est
                    considérée absente.
                  </p>
                  {entries.map((entry, i) => (
                    <div className="entry" key={i}>
                      <Field label={`Évaluation ${i + 1}`}>
                        {numeric ? (
                          <input
                            aria-label={`Note évaluation ${i + 1}`}
                            type="number"
                            step="any"
                            min="0"
                            max={
                              policy.scale.kind === "percentage"
                                ? 100
                                : policy.scale.max
                            }
                            value={entry.score ?? ""}
                            onChange={(e) =>
                              setEntry(
                                i,
                                "score",
                                e.target.value === ""
                                  ? null
                                  : Number(e.target.value),
                              )
                            }
                          />
                        ) : (
                          <select
                            aria-label={`Niveau évaluation ${i + 1}`}
                            value={entry.score ?? ""}
                            onChange={(e) =>
                              setEntry(i, "score", e.target.value || null)
                            }
                          >
                            <option value="">Absente</option>
                            {policy.bands.map((b, j) => (
                              <option key={j} value={b.label}>
                                {b.label}
                              </option>
                            ))}
                          </select>
                        )}
                      </Field>
                      <Field label="Coefficient">
                        <input
                          aria-label={`Coefficient évaluation ${i + 1}`}
                          type="number"
                          step="any"
                          min="0.01"
                          max="1000"
                          value={entry.weight}
                          onChange={(e) =>
                            setEntry(i, "weight", Number(e.target.value))
                          }
                        />
                      </Field>
                      <button
                        aria-label={`Supprimer l’évaluation ${i + 1}`}
                        disabled={entries.length === 1}
                        onClick={() =>
                          setEntries((es) => es.filter((_, j) => i !== j))
                        }
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  <button
                    className="text-button"
                    disabled={entries.length >= 100}
                    onClick={() =>
                      setEntries((es) => [...es, { score: null, weight: 1 }])
                    }
                  >
                    + Ajouter une évaluation
                  </button>
                  <div className="formula">
                    Moyenne pondérée · seuils appliqués avant l’arrondi
                  </div>
                </section>
                <section className="report-card">
                  <div className="report-top">
                    <span>SYKOLO / BULLETIN</span>
                    <span>APERÇU</span>
                  </div>
                  <p className="eyebrow">RÉSULTAT SIMULÉ</p>
                  <h2>{policy.name}</h2>
                  <div id="result" aria-live="polite">
                    {calculationError ? (
                      <p className="alert-preview">{calculationError}</p>
                    ) : !result ? (
                      <p>Calcul en cours…</p>
                    ) : result.status === "empty" ? (
                      <p>Aucun résultat : toutes les notes sont absentes.</p>
                    ) : (
                      <>
                        {policy.report.showScore && (
                          <div className="score">
                            {result.score.toLocaleString("fr-FR", {
                              maximumFractionDigits: policy.precision,
                            })}
                            <small>
                              {policy.scale.kind === "percentage"
                                ? " %"
                                : ` / ${policy.scale.max}`}
                            </small>
                          </div>
                        )}
                        {policy.report.showLabel && (
                          <div className="result-label">{result.label}</div>
                        )}
                        {result.notification && (
                          <p className="alert-preview">
                            Alerte à prévoir : {result.notification}
                          </p>
                        )}
                      </>
                    )}
                  </div>
                  <div className="report-foot">
                    Document de démonstration · aucune donnée élève
                  </div>
                </section>
                <section className="card roadmap" id="roadmap">
                  <p className="eyebrow">PHASE 1 · ORDRE DE DÉVELOPPEMENT</p>
                  <h2>Des fondations, puis les usages.</h2>
                  <ul>
                    <li>
                      <span>01</span>Architecture & déploiement{" "}
                      <em>En validation</em>
                    </li>
                    <li>
                      <span>02</span>Authentification & sécurité{" "}
                      <em>À développer</em>
                    </li>
                    <li>
                      <span>03</span>Multi-établissements & configuration{" "}
                      <em>À développer</em>
                    </li>
                  </ul>
                  <p>
                    Le laboratoire pédagogique prépare les futurs modules. Il ne
                    gère pas encore d’établissement réel.
                  </p>
                </section>
              </div>
            </div>
          )}
          <footer>
            SYKOLO <span>Une école singulière. Un système qui s’adapte.</span>
            <span>
              {version
                ? `v${version.version} · ${version.commit.slice(0, 7)}`
                : "v0.2.0"}
            </span>
          </footer>
        </main>
      </div>
    </>
  );
}
