import React, {useEffect, useState} from "react";
import {Button, Card, Icon, PageHeader} from "./yem-ui.jsx";

export async function schoolRequest(path, values) {
  if (values !== undefined) {
    const csrf = await fetch("/api/v1/auth/csrf", {credentials: "same-origin"});
    if (!csrf.ok) throw Error("Session indisponible. Reconnectez-vous.");
  }
  const token = document.cookie.split("; ").find(value => value.startsWith("csrftoken="))?.slice(10) || "";
  const response = await fetch("/api/v1/" + path, {
    credentials: "same-origin",
    ...(values === undefined ? {} : {
      method: "POST", headers: {"Content-Type": "application/json", "X-CSRFToken": token},
      body: JSON.stringify(values),
    }),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) throw Error("Service indisponible.");
  const data = await response.json();
  if (!response.ok) throw Error(data.error || "Opération refusée.");
  return data;
}

export function useSchoolData(root, resources) {
  const [state, setState] = useState({data: null, error: ""});
  useEffect(() => {
    if (!resources) return;
    let active = true;
    setState({data: null, error: ""});
    Promise.all(resources.split(" ").map(path => schoolRequest(root + path))).then(results => {
      if (active) setState({data: Object.assign({}, ...results), error: ""});
    }).catch(error => {
      if (active) setState({data: null, error: error.message});
    });
    return () => {active = false;};
  }, [root, resources]);
  return state;
}

export function SchoolSettings({sections, selection, onSelect, render, isOwner, onReturn}) {
  const current = sections.find(section => section.id === selection?.section);
  const active = current?.items.find(item => item.id === selection?.item) || current?.items[0];
  return <>
    <PageHeader title="Paramètres" actions={onReturn && <Button icon="back" onClick={onReturn}>Retour au module</Button>} subtitle={isOwner
      ? "Espace propriétaire · comptes de l’établissement et accès autorisés"
      : "Réglages de l’établissement · choisissez la rubrique à configurer"}/>
    <div className="yd-real-body">
      {current ? <>
        <button type="button" className="yd-btn" onClick={() => onSelect(null)}>← Toutes les rubriques</button>
        <h2>{current.title}</h2>
        {current.items.length > 1 && <div className="yd-real-tabs" aria-label={current.title}>
          {current.items.map(item => <button type="button" key={item.id}
            aria-pressed={active.id === item.id} className={active.id === item.id ? "active" : ""}
            onClick={() => onSelect({section: current.id, item: item.id})}>{item.label}</button>)}
        </div>}
        {render(active.id)}
      </> : <div className="pc-module-grid" role="group" aria-label="Rubriques des paramètres">{sections.map(section => <button type="button"
        key={section.id} aria-label={section.title} onClick={() => onSelect({section: section.id})}>
        <Icon name={section.icon} size={26}/><b>{section.title}</b>
        <small>{section.items.map(item => item.label).join(" · ")}</small>
      </button>)}</div>}
    </div>
  </>;
}

export function ClassField({classes, years = [], value, onChange, required = false, disabled = false}) {
  return <label className="field">Classe
    <select value={value} onChange={event => onChange(event.target.value)} required={required} disabled={disabled}>
      <option value="">Choisir une classe…</option>
      {classes.map(room => {
        const year = years.find(item => item.id === room.year);
        return <option key={room.id} value={room.id}>{room.name}{year ? " · " + year.name : ""}</option>;
      })}
    </select>
  </label>;
}

const settingNames = {
  bulletin: "Barèmes et présentation du bulletin",
  deliberation: "Décisions du conseil de classe",
  attendance: "Statuts des absences et retards",
};
const attendanceGroups = {present: "Présence", absent: "Absence", late: "Retard", other: "Autre"};
const defaultStatuses = [
  {code: "p", label: "Présent", group: "present"},
  {code: "a", label: "Absent", group: "absent"},
  {code: "r", label: "Retard", group: "late"},
];
const codeFrom = (label, min = 1) => (label.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
  .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").replace(/^[^a-z]+/, "") || "choix").slice(0, 40).padEnd(min, "0");

function SettingsList({rows, onChange, attendance, disabled}) {
  const [newLabel, setNewLabel] = useState("");
  function add() {
    const label = newLabel.trim();
    if (!label || rows.length >= 30) return;
    const base = codeFrom(label, attendance ? 1 : 2);
    let code = base;
    for (let i = 2; rows.some(row => row.code === code); i++) code = base + "-" + i;
    onChange([...rows, {code, label, ...(attendance ? {group: "other"} : {})}]);
    setNewLabel("");
  }
  return <>
    {rows.map((row, index) => <div key={row.code} className="two">
      <label className="field">Libellé
        <input required maxLength={120} disabled={disabled} value={row.label} onChange={event => {
          onChange(rows.map((item, i) => i === index ? {...item, label: event.target.value} : item));
        }}/>
      </label>
      {attendance && <label className="field">Catégorie
        <select value={row.group} disabled={disabled} onChange={event => {
          onChange(rows.map((item, i) => i === index ? {...item, group: event.target.value} : item));
        }}>
          {Object.entries(attendanceGroups).map(([group, label]) => <option value={group} key={group}>{label}</option>)}
        </select>
      </label>}
      <div><button type="button" disabled={disabled} onClick={() => onChange(rows.filter((_, i) => i !== index))}>Retirer {row.label}</button></div>
    </div>)}
    <div className="actions">
      <label className="field">{attendance ? "Nouveau statut" : "Nouvelle décision"}
        <input maxLength={120} value={newLabel} onChange={event => setNewLabel(event.target.value)}
          onKeyDown={event => {if (event.key === "Enter") {event.preventDefault(); add();}}} disabled={disabled}/>
      </label>
      <button type="button" disabled={disabled || !newLabel.trim() || rows.length >= 30} onClick={add}>Ajouter</button>
    </div>
  </>;
}

function GradingFields({grading, setGrading, presets}) {
  return <>
    <label className="field">Modèle de barème
      <select value="" onChange={event => {
        const preset = presets.find(item => item.id === event.target.value);
        if (preset) setGrading(preset.policy);
      }}>
        <option value="">{grading?.name || "Choisir un modèle…"}</option>
        {presets.map(preset => <option key={preset.id} value={preset.id}>{preset.title}</option>)}
      </select>
    </label>
    {grading && <>
      <div className="two">
        <label className="field">Nom du barème
          <input required maxLength={120} value={grading.name}
            onChange={event => setGrading({...grading, name: event.target.value})}/>
        </label>
        {grading.scale.kind === "numeric" && <label className="field">Note maximale
          <input type="number" required min="0.01" max="100000" step="any" value={grading.scale.max}
            onChange={event => setGrading({...grading, scale: {...grading.scale, max: event.target.value}})}/>
        </label>}
        <label className="field">Évaluation sans note
          <select value={grading.missing} onChange={event => setGrading({...grading, missing: event.target.value})}>
            <option value="exclude">Écarter du calcul</option><option value="zero">Compter comme zéro</option>
          </select>
        </label>
      </div>
      <details>
        <summary>Appréciations et seuils du barème</summary>
        {grading.bands.map((band, index) => {
          const change = (key, value) => setGrading({...grading,
            bands: grading.bands.map((item, i) => i === index ? {...item, [key]: value} : item)});
          return <div className="two" key={index}>
            <label className="field">Appréciation<input required maxLength={120} value={band.label} onChange={e => change("label", e.target.value)}/></label>
            <label className="field">À partir de (%)<input type="number" required min="0" max="100" step="any" value={band.min} onChange={e => change("min", e.target.value)}/></label>
            <label className="field">Équivalence (%)<input type="number" required min="0" max="100" step="any" value={band.value} onChange={e => change("value", e.target.value)}/></label>
            <div><button type="button" disabled={grading.bands.length <= 1} onClick={() => setGrading({...grading,
              bands: grading.bands.filter((_, i) => i !== index)})}>Retirer l’appréciation</button></div>
          </div>;
        })}
        <button type="button" disabled={grading.bands.length >= 30} onClick={() => setGrading({...grading,
          bands: [...grading.bands, {label: "", min: "", value: ""}]})}>Ajouter une appréciation</button>
      </details>
    </>}
  </>;
}

export function TeachingSettings({schoolId, kind, canEdit, canReadAcademic}) {
  const root = "schools/" + schoolId + "/";
  const catalog = useSchoolData(root, canReadAcademic ? "academic/years academic/cycles academic/levels academic/classes" : "");
  const [year, setYear] = useState("");
  const [cycle, setCycle] = useState("");
  const [level, setLevel] = useState("");
  const [room, setRoom] = useState("");
  const [presets, setPresets] = useState([]);
  const [presetError, setPresetError] = useState("");
  const [version, setVersion] = useState(0);
  const {years = [], cycles = [], levels = [], classes = []} = catalog.data || {};
  const scope = {
    ...(year ? {year: years.find(item => item.id === year)?.code} : {}),
    ...(cycle ? {cycle: cycles.find(item => item.id === cycle)?.code} : {}),
    ...(level ? {level: levels.find(item => item.id === level)?.code} : {}),
    ...(room ? {class: classes.find(item => item.id === room)?.code} : {}),
  };
  const query = new URLSearchParams(scope).toString();

  useEffect(() => {
    if (kind !== "bulletin") return;
    let active = true;
    schoolRequest("presets").then(value => {if (active) setPresets(value);})
      .catch(error => {if (active) setPresetError(error.message);});
    return () => {active = false;};
  }, [kind]);
  return <Card title={settingNames[kind]} icon="settings">
    <p className="hint">Sans sélection, les réglages s’appliquent à l’établissement. Une classe peut hériter des réglages de son niveau, de son cycle ou de son année.</p>
    {canReadAcademic && <div className="two">
      <label className="field">Année scolaire<select value={year} onChange={e => {setYear(e.target.value); setRoom("");}}>
        <option value="">Toutes les années</option>
        {years.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
      <label className="field">Cycle<select value={cycle} onChange={e => {setCycle(e.target.value); setLevel(""); setRoom("");}}>
        <option value="">Tous les cycles</option>
        {cycles.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>
      {cycle && <label className="field">Niveau<select value={level} onChange={e => {setLevel(e.target.value); setRoom("");}}>
        <option value="">Tous les niveaux du cycle</option>
        {levels.filter(item => item.cycle === cycle).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select></label>}
      {year && level && <ClassField classes={classes.filter(item => item.level === level && item.year === year)} value={room} onChange={setRoom}/>}
    </div>}
    {catalog.error && <p role="alert">{catalog.error}</p>}
    {presetError && <p role="alert">{presetError}</p>}
    <TeachingSettingsForm key={query + ":" + version} root={root} query={query} scope={scope} kind={kind}
      canEdit={canEdit} presets={presets} onReload={() => setVersion(value => value + 1)}/>
  </Card>;
}

function TeachingSettingsForm({root, query, scope, kind, canEdit, presets, onReload}) {
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState({});
  const [grading, setGrading] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    schoolRequest(root + "settings?" + query).then(data => {
      if (!active) return;
      setSettings(data);
      setDraft(data.effective[kind] || {});
      setGrading(data.effective.grading || null);
    }).catch(error => {if (active) setMessage(error.message);});
    return () => {active = false;};
  }, [root, query, kind]);
  const set = (key, value) => setDraft(current => ({...current, [key]: value}));
  const rows = kind === "attendance" ? draft.statuses || defaultStatuses : draft.decisions || [];
  const changed = JSON.stringify(draft) !== JSON.stringify(settings?.effective[kind] || {}) ||
    (kind === "bulletin" && JSON.stringify(grading) !== JSON.stringify(settings?.effective.grading || null)) ||
    (kind === "attendance" && !settings?.effective.attendance?.statuses);
  return <>
    {!settings ? <p role="status">{message || "Chargement des réglages…"}</p> :
      <form onSubmit={async event => {
        event.preventDefault();
        setBusy(true);
        setMessage("");
        const values = {...settings.local?.values};
        const overrides = {...values[kind]};
        for (const [key, value] of Object.entries(draft)) {
          if (JSON.stringify(value) !== JSON.stringify(settings.effective[kind]?.[key])) {
            overrides[key] = key === "precision" ? Number(value) : value;
          }
        }
        if (kind === "attendance" && !settings.effective.attendance?.statuses) overrides.statuses = rows;
        if (Object.keys(overrides).length) values[kind] = overrides;
        if (kind === "bulletin" && grading && JSON.stringify(grading) !== JSON.stringify(settings.effective.grading)) {
          values.grading = {...grading, scale: {...grading.scale, max: Number(grading.scale.max)},
            bands: grading.bands.map(band => ({...band, min: Number(band.min), value: Number(band.value)}))};
        }
        try {
          const saved = await schoolRequest(root + "settings", {scope, values, revision: settings.local?.revision || 0});
          setSettings({effective: saved.effective, local: {values, revision: saved.revision}});
          setDraft(saved.effective[kind] || {});
          setGrading(saved.effective.grading || null);
          setMessage("Réglages enregistrés.");
        } catch (error) {setMessage(error.message);}
        finally {setBusy(false);}
      }}>
        <fieldset disabled={!canEdit || busy}>
          {kind === "bulletin" ? <>
            <GradingFields grading={grading} setGrading={setGrading} presets={presets}/>
            <div className="two">
              <label className="field">Titre du bulletin<input maxLength={120} required value={draft.title ?? "Bulletin scolaire"}
                onChange={e => set("title", e.target.value)}/></label>
              <label className="field">Décimales affichées<input type="number" required min="0" max="4" value={draft.precision ?? grading?.precision ?? 2}
                onChange={e => set("precision", e.target.value)}/></label>
              {[["show_score", "Afficher le résultat", grading?.report?.showScore ?? true],
                ["show_label", "Afficher l’appréciation", grading?.report?.showLabel ?? true]].map(([key, label, fallback]) => <label key={key}>
                <input type="checkbox" checked={draft[key] ?? fallback} onChange={e => set(key, e.target.checked)}/> {label}
              </label>)}
              <label className="field">Matière sans résultat
                <select value={draft.missing_entry || "exclude"} onChange={e => set("missing_entry", e.target.value)}>
                  <option value="exclude">Écarter du calcul</option><option value="zero">Compter comme zéro</option>
                </select>
              </label>
            </div>
          </> : <SettingsList rows={rows} attendance={kind === "attendance"} disabled={!canEdit || busy}
            onChange={next => set(kind === "attendance" ? "statuses" : "decisions", next)}/>}
        </fieldset>
        {canEdit && <div className="actions">
          <button type="submit" disabled={busy || !changed || (kind === "attendance" && !rows.length) ||
            (kind === "bulletin" && (!grading || (!(draft.show_score ?? grading.report.showScore) && !(draft.show_label ?? grading.report.showLabel))))}>Enregistrer les réglages</button>
          <button type="button" disabled={busy} onClick={onReload}>Recharger les valeurs enregistrées</button>
        </div>}
        {message && <p role="status">{message}</p>}
      </form>}
  </>;
}
