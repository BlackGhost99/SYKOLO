import React, { useEffect, useMemo, useState } from "react";
import {TableScroll,  Icon, Button, Status, Metric, Card, Table, InfoRow, SearchBox, Check, Donut, PageHeader } from "./yem-ui.jsx";

/* Parcours du secrétariat branchés sur l'API : fiche de renseignement modulable, dossier élève,
   inscriptions par classe, création des classes et suivi des paiements. */

export async function req(path, body, method) {
  const write = body !== undefined || (method && method !== "GET");
  if (write) await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
  const csrf = document.cookie.split("; ").find(x => x.startsWith("csrftoken="))?.split("=")[1] || "";
  const r = await fetch("/api/v1/" + path, {
    method: method || (body === undefined ? "GET" : "POST"), credentials: "same-origin",
    headers: write ? { "Content-Type": "application/json", "X-CSRFToken": csrf } : {},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.headers.get("content-type")?.includes("application/json")) throw Error("Serveur indisponible.");
  const data = await r.json();
  if (!r.ok) { const e = Error(data.error || "Requête refusée."); e.status = r.status; throw e; }
  return data;
}
function useLoad(path) {
  const [state, setState] = useState({ data: null, error: "", loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) { setState({ data: null, error: "", loading: false }); return; }
    let live = true;
    setState(s => ({ ...s, loading: true }));
    req(path).then(data => live && setState({ data, error: "", loading: false })).catch(e => live && setState({ data: null, error: e.message, loading: false }));
    return () => { live = false; };
  }, [path, tick]);
  return { ...state, reload: () => setTick(t => t + 1) };
}

const nf = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const num = v => nf.format(Math.round(Number(v) || 0)).replace(/ | /g, " ");
const cur = c => (!c || c === "XAF" || c === "XOF") ? "FCFA" : c;
const money = (v, c) => `${num(v)} ${cur(c)}`;
const fmtDate = iso => iso ? new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" }) : "—";
const today = () => new Date().toISOString().slice(0, 10);
export const METHODS = [["airtel_money", "Airtel Money", "mobile"], ["moov_money", "Moov Money", "mobile"], ["especes", "Espèces", "cash"], ["virement", "Virement", "transfer"], ["cheque", "Chèque", "file"]];
export const methodLabel = m => METHODS.find(x => x[0] === m)?.[1] || (m === "mobile_money" ? "Mobile money" : m === "autre" ? "Autre" : m);
const FIN = { a_jour: ["green", "Payé"], partiel: ["yellow", "Partiel"], impaye: ["red", "Impayé"], sans_frais: ["gray", "Sans frais"] };
const slug = s => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").replace(/^(\d)/, "q_$1").slice(0, 40) || "champ";
const uniqueKey = (label, taken) => { let k = slug(label), n = 2; while (taken.includes(k)) k = `${slug(label).slice(0, 36)}_${n++}`; return k; };

function Msg({ text, error }) { return text ? <p role={error ? "alert" : "status"} className={error ? "pc-alert" : "yd-form-msg"}>{text}</p> : null; }
function Empty({ children }) { return <p className="yd-card-sub yd-empty">{children}</p>; }
function Loading({ state, children }) {
  if (state.loading && !state.data) return <Card title="Chargement…" icon="clock"/>;
  if (state.error) return <p role="alert" className="pc-alert">{state.error}</p>;
  return children;
}
function Field({ label, required, children, wide, hint }) {
  return <label className={`yf-field ${wide ? "wide" : ""}`}><span>{label}{required && <i> *</i>}</span>{children}{hint && <small>{hint}</small>}</label>;
}
function downloadCsv(name, lines) {
  const blob = new Blob(["﻿" + lines.map(l => l.map(v => `"${String(v ?? "").replace(/"/g, '""')}"`).join(";")).join("\n")], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = name; link.click(); URL.revokeObjectURL(link.href);
}

/* ---------- Questions de l'école (formulaire modulable) ---------- */
function CustomInput({ q, value, onChange }) {
  if (q.type === "textarea") return <textarea rows={3} value={value ?? ""} onChange={e => onChange(e.target.value)} required={q.required}/>;
  if (q.type === "date") return <input type="date" value={value ?? ""} onChange={e => onChange(e.target.value)} required={q.required}/>;
  if (q.type === "number") return <input type="number" value={value ?? ""} onChange={e => onChange(e.target.value === "" ? "" : Number(e.target.value))} required={q.required}/>;
  if (q.type === "select") return <select value={value ?? ""} onChange={e => onChange(e.target.value)} required={q.required}><option value="">Choisir…</option>{q.options.map(o => <option key={o}>{o}</option>)}</select>;
  if (q.type === "yesno") return <span className="yf-yesno">{[[true, "Oui"], [false, "Non"]].map(([v, l]) => <button type="button" key={l} className={value === v ? "active" : ""} onClick={() => onChange(v)}>{l}</button>)}</span>;
  return <input value={value ?? ""} onChange={e => onChange(e.target.value)} required={q.required} maxLength={255}/>;
}
function shown(config, key) { return config?.fields?.[key]?.visible !== false; }
function needed(config, key) { return !!config?.fields?.[key]?.required && shown(config, key); }

/* ---------- Nouvel élève : fiche de renseignement complète ---------- */
const emptyGuardian = { full_name: "", relationship: "", phone: "", email: "", profession: "", address: "" };
export function StudentForm({ schoolId, params, onNavigate, tabs }) {
  const form = useLoad(`schools/${schoolId}/enrollment-form`);
  const [year, setYear] = useState("");
  const classes = useLoad(`schools/${schoolId}/overview/classes${year ? `?year=${year}` : ""}`);
  const [student, setStudent] = useState({ last_name: "", first_name: "", student_code: "", date_of_birth: "", gender: "", place_of_birth: "", nationality: "", address: "", previous_school: "" });
  const [extra, setExtra] = useState({});
  const [docs, setDocs] = useState({});
  const [guardians, setGuardians] = useState([{ ...emptyGuardian, relationship: "Mère" }]);
  const [classroom, setClassroom] = useState(params?.classroom || "");
  const [enrolledOn, setEnrolledOn] = useState(today());
  const [fees, setFees] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState({ text: "", error: false });
  useEffect(() => { req(`schools/${schoolId}/students/next-code`).then(r => setStudent(s => s.student_code ? s : { ...s, student_code: r.student_code })).catch(() => {}); }, [schoolId]);
  const config = form.data?.config;
  const cd = classes.data;
  const set = (k, v) => setStudent(s => ({ ...s, [k]: v }));
  const setG = (i, k, v) => setGuardians(gs => gs.map((g, j) => j === i ? { ...g, [k]: v } : g));
  const questions = section => (config?.custom_fields || []).filter(q => q.section === section);
  async function submit(e) {
    e.preventDefault(); setBusy(true); setMessage({ text: "" });
    try {
      const clean = Object.fromEntries(Object.entries(student).filter(([, v]) => v !== ""));
      const body = {
        student: { ...clean, extra_fields: Object.fromEntries(Object.entries(extra).filter(([, v]) => v !== "" && v !== undefined)), documents: docs },
        guardians: guardians.filter(g => g.full_name.trim()).map(g => Object.fromEntries(Object.entries(g).filter(([, v]) => v !== ""))),
        enrollment: classroom ? { classroom, enrolled_on: enrolledOn || undefined } : null,
        apply_fees: fees,
      };
      const r = await req(`schools/${schoolId}/students/register`, body);
      const parts = [`Dossier de ${r.student.last_name} ${r.student.first_name} créé (matricule ${r.student.student_code}).`];
      if (r.enrollment) parts.push("Élève inscrit dans sa classe.");
      if (r.charges_created) parts.push(`${r.charges_created} frais affecté(s).`);
      if (r.fees_skipped) parts.push("Les frais seront affectés par la comptabilité.");
      onNavigate("students", "fiche", { student: r.student.id, notice: parts.join(" ") });
    } catch (err) { setMessage({ text: err.message, error: true }); window.scrollTo?.(0, 0); } finally { setBusy(false); }
  }
  const optional = (key, label, input) => shown(config, key) && <Field label={label} required={needed(config, key)}>{input}</Field>;
  return <>
    <PageHeader title="Nouvel élève" subtitle="Fiche de renseignement, responsables, pièces fournies et inscription en classe" banner={false}
      actions={<Button icon="back" onClick={() => onNavigate("students", "live")}>Retour à la liste</Button>}/>
    {tabs}
    <Loading state={form}>{config && <form className="yf-form" onSubmit={submit}>
      <Msg {...message}/>
      <Card title="Identité de l’élève" icon="user">
        <div className="yf-grid">
          <Field label="Nom" required><input required maxLength={120} value={student.last_name} onChange={e => set("last_name", e.target.value.toUpperCase())}/></Field>
          <Field label="Prénom(s)" required><input required maxLength={120} value={student.first_name} onChange={e => set("first_name", e.target.value)}/></Field>
          <Field label="Matricule" hint="Proposé automatiquement, modifiable."><input maxLength={50} pattern="[a-zA-Z0-9][a-zA-Z0-9_\-]*" value={student.student_code} onChange={e => set("student_code", e.target.value)}/></Field>
          {optional("date_of_birth", "Date de naissance", <input type="date" required={needed(config, "date_of_birth")} value={student.date_of_birth} onChange={e => set("date_of_birth", e.target.value)}/>)}
          {optional("gender", "Sexe", <select required={needed(config, "gender")} value={student.gender} onChange={e => set("gender", e.target.value)}><option value="">—</option><option value="F">Féminin</option><option value="M">Masculin</option></select>)}
          {optional("place_of_birth", "Lieu de naissance", <input maxLength={120} required={needed(config, "place_of_birth")} value={student.place_of_birth} onChange={e => set("place_of_birth", e.target.value)}/>)}
          {optional("nationality", "Nationalité", <input maxLength={80} required={needed(config, "nationality")} value={student.nationality} onChange={e => set("nationality", e.target.value)}/>)}
          {optional("address", "Adresse / quartier", <input maxLength={255} required={needed(config, "address")} value={student.address} onChange={e => set("address", e.target.value)}/>)}
          {optional("previous_school", "Établissement précédent", <input maxLength={180} required={needed(config, "previous_school")} value={student.previous_school} onChange={e => set("previous_school", e.target.value)}/>)}
          {questions("eleve").map(q => <Field key={q.key} label={q.label} required={q.required && q.type !== "yesno"} wide={q.type === "textarea"}><CustomInput q={q} value={extra[q.key]} onChange={v => setExtra(x => ({ ...x, [q.key]: v }))}/></Field>)}
        </div>
      </Card>
      <Card title="Responsables légaux" icon="users" right={shown(config, "second_guardian") && guardians.length < 2 && <Button className="small" icon="plus" onClick={() => setGuardians(g => [...g, { ...emptyGuardian, relationship: "Père" }])}>Second responsable</Button>}>
        {guardians.map((g, i) => <div key={i} className="yf-guardian">
          <h3>{i === 0 ? "Responsable principal" : "Second responsable"}{i > 0 && <button type="button" className="yf-link" onClick={() => setGuardians(gs => gs.filter((_, j) => j !== i))}>Retirer</button>}</h3>
          <div className="yf-grid">
            <Field label="Nom complet" required={i === 0}><input required={i === 0} maxLength={180} value={g.full_name} onChange={e => setG(i, "full_name", e.target.value)}/></Field>
            <Field label="Lien avec l’élève"><select value={g.relationship} onChange={e => setG(i, "relationship", e.target.value)}>{["Mère", "Père", "Tuteur", "Tutrice", "Grand-parent", "Oncle", "Tante", "Autre"].map(x => <option key={x}>{x}</option>)}</select></Field>
            {shown(config, "guardian_phone") && <Field label="Téléphone (WhatsApp)" required={i === 0 && needed(config, "guardian_phone")}><input type="tel" maxLength={45} placeholder="+241 …" required={i === 0 && needed(config, "guardian_phone")} value={g.phone} onChange={e => setG(i, "phone", e.target.value)}/></Field>}
            {shown(config, "guardian_email") && <Field label="Email" required={i === 0 && needed(config, "guardian_email")}><input type="email" maxLength={254} required={i === 0 && needed(config, "guardian_email")} value={g.email} onChange={e => setG(i, "email", e.target.value)}/></Field>}
            {shown(config, "guardian_profession") && <Field label="Profession" required={i === 0 && needed(config, "guardian_profession")}><input maxLength={120} required={i === 0 && needed(config, "guardian_profession")} value={g.profession} onChange={e => setG(i, "profession", e.target.value)}/></Field>}
            {shown(config, "guardian_address") && <Field label="Adresse" required={i === 0 && needed(config, "guardian_address")}><input maxLength={255} required={i === 0 && needed(config, "guardian_address")} value={g.address} onChange={e => setG(i, "address", e.target.value)}/></Field>}
          </div>
        </div>)}
        {questions("responsable").length > 0 && <div className="yf-grid">{questions("responsable").map(q => <Field key={q.key} label={q.label} required={q.required && q.type !== "yesno"} wide={q.type === "textarea"}><CustomInput q={q} value={extra[q.key]} onChange={v => setExtra(x => ({ ...x, [q.key]: v }))}/></Field>)}</div>}
      </Card>
      <div className="yd-grid yf-two">
        <Card title="Pièces fournies" icon="paperclip" subtitle="Cochez les pièces remises au secrétariat. Le dossier reste modifiable ensuite.">
          {config.documents.length === 0 ? <Empty>Aucune pièce demandée par l’établissement.</Empty> :
            <div className="yf-checks">{config.documents.map(d => <button type="button" key={d.key} className={docs[d.key] ? "active" : ""} onClick={() => setDocs(x => ({ ...x, [d.key]: !x[d.key] }))}><Check on={!!docs[d.key]}/><span>{d.label}{d.required && <i> *</i>}</span></button>)}</div>}
        </Card>
        <Card title="Inscription en classe" icon="cap">
          <Loading state={classes}>{cd && <>
            <div className="yf-grid">
              <Field label="Année scolaire"><select value={year || cd.year?.id || ""} onChange={e => { setYear(e.target.value); setClassroom(""); }}>{cd.years.length === 0 && <option value="">Aucune année créée</option>}{cd.years.map(y => <option key={y.id} value={y.id}>{y.name}</option>)}</select></Field>
              <Field label="Classe" hint={cd.classes.length ? "" : "Aucune classe pour cette année : créez-les dans Paramètres › Classes."}>
                <select value={classroom} onChange={e => setClassroom(e.target.value)}><option value="">Ne pas inscrire maintenant</option>
                  {cd.classes.filter(c => c.active).map(c => <option key={c.id} value={c.id} disabled={c.remaining === 0}>{c.name}{c.remaining == null ? "" : c.remaining === 0 ? " — complète" : ` — ${c.remaining} place(s)`}</option>)}</select></Field>
              {classroom && <Field label="Date d’inscription"><input type="date" value={enrolledOn} onChange={e => setEnrolledOn(e.target.value)} min={cd.year?.start_date} max={cd.year?.end_date}/></Field>}
            </div>
            {classroom && cd.can_manage_finance && <button type="button" className="yd-toggle-btn yf-inline" aria-pressed={fees} onClick={() => setFees(f => !f)}><Check on={fees}/>Affecter automatiquement les frais de la classe ({cd.classes.find(c => c.id === classroom)?.fee_schedules || 0} tarif(s))</button>}
          </>}</Loading>
        </Card>
      </div>
      <div className="yf-actions"><Button onClick={() => onNavigate("students", "live")}>Annuler</Button><Button primary type="submit" icon="check" disabled={busy}>{busy ? "Enregistrement…" : "Enregistrer le dossier"}</Button></div>
    </form>}</Loading>
  </>;
}

/* ---------- Dossier élève ---------- */
export function StudentFile({ schoolId, params, canManage, canReceive, onNavigate, tabs }) {
  const id = params?.student;
  const dossier = useLoad(id ? `schools/${schoolId}/students/${id}/dossier` : "");
  const classes = useLoad(canManage ? `schools/${schoolId}/overview/classes` : "");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [newGuardian, setNewGuardian] = useState(null);
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState({ text: params?.notice || "", error: false });
  const d = dossier.data;
  async function run(fn, ok) {
    setBusy(true); setMessage({ text: "" });
    try { await fn(); setMessage({ text: ok }); dossier.reload(); classes.reload?.(); }
    catch (e) { setMessage({ text: e.status === 409 ? "La fiche a été modifiée entre-temps : rechargée, recommencez." : e.message, error: true }); dossier.reload(); }
    finally { setBusy(false); }
  }
  if (!id) return <Empty>Aucun élève sélectionné.</Empty>;
  const s = d?.student, form = d?.form;
  const current = d?.enrollments.find(e => e.year === classes.data?.year?.id) || d?.enrollments[0];
  const curYear = classes.data?.year;
  const enrolledThisYear = d?.enrollments.some(e => e.year === curYear?.id);
  function startEdit() { setDraft({ first_name: s.first_name, last_name: s.last_name, date_of_birth: s.date_of_birth || "", gender: s.gender, place_of_birth: s.place_of_birth, nationality: s.nationality, address: s.address, previous_school: s.previous_school, extra_fields: { ...s.extra_fields } }); setEditing(true); }
  function saveEdit() {
    run(async () => {
      const { extra_fields, ...rest } = draft;
      await req(`schools/${schoolId}/students/${s.id}`, { revision: s.revision, ...rest, date_of_birth: rest.date_of_birth || null, extra_fields }, "PATCH");
      setEditing(false);
    }, "Fiche mise à jour.");
  }
  const info = [["date_of_birth", "Date de naissance", v => fmtDate(v)], ["gender", "Sexe", v => ({ F: "Féminin", M: "Masculin" }[v] || "—")], ["place_of_birth", "Lieu de naissance"], ["nationality", "Nationalité"], ["address", "Adresse / quartier"], ["previous_school", "Établissement précédent"]];
  const f = current?.finance;
  return <>
    <PageHeader title={s ? `${s.last_name} ${s.first_name}` : "Fiche élève"} subtitle={s ? `Matricule ${s.student_code}${current ? ` · ${current.classroom_name} (${current.year_name})` : " · non inscrit"}` : "Dossier administratif"} banner={false}
      actions={<>
        <Button icon="back" onClick={() => onNavigate("students", "live")}>Liste des élèves</Button>
        <Button icon="printer" onClick={() => window.print()}>Imprimer la fiche</Button>
        {canReceive && current && Number(f?.balance) > 0 && <Button primary icon="coins" onClick={() => onNavigate("payments", "live", { enrollment: current.id })}>Encaisser</Button>}
      </>}/>
    {tabs}
    <Msg {...message}/>
    <Loading state={dossier}>{d && <div className="yd-grid yf-file">
      <div className="yd-stack">
        <Card title="Renseignements" icon="idcard" right={canManage && !editing && <Button className="small" icon="edit" onClick={startEdit}>Modifier</Button>}>
          {!editing ? <div className="yd-info-list">
            {info.filter(([k]) => shown(form, k) || s[k]).map(([k, l, fmt]) => <InfoRow key={k} k={l} v={(fmt ? fmt(s[k]) : s[k]) || "—"}/>)}
            {form.custom_fields.map(q => <InfoRow key={q.key} k={q.label} v={q.type === "yesno" ? (s.extra_fields[q.key] === true ? "Oui" : s.extra_fields[q.key] === false ? "Non" : "—") : q.type === "date" ? fmtDate(s.extra_fields[q.key]) : String(s.extra_fields[q.key] ?? "—")}/>)}
          </div> : <form onSubmit={e => { e.preventDefault(); saveEdit(); }}>
            <div className="yf-grid">
              <Field label="Nom" required><input required value={draft.last_name} onChange={e => setDraft(x => ({ ...x, last_name: e.target.value }))}/></Field>
              <Field label="Prénom(s)" required><input required value={draft.first_name} onChange={e => setDraft(x => ({ ...x, first_name: e.target.value }))}/></Field>
              <Field label="Date de naissance"><input type="date" value={draft.date_of_birth} onChange={e => setDraft(x => ({ ...x, date_of_birth: e.target.value }))}/></Field>
              <Field label="Sexe"><select value={draft.gender} onChange={e => setDraft(x => ({ ...x, gender: e.target.value }))}><option value="">—</option><option value="F">Féminin</option><option value="M">Masculin</option></select></Field>
              {["place_of_birth", "nationality", "address", "previous_school"].map(k => <Field key={k} label={info.find(i => i[0] === k)[1]}><input value={draft[k]} onChange={e => setDraft(x => ({ ...x, [k]: e.target.value }))}/></Field>)}
              {form.custom_fields.map(q => <Field key={q.key} label={q.label} wide={q.type === "textarea"}><CustomInput q={{ ...q, required: false }} value={draft.extra_fields[q.key]} onChange={v => setDraft(x => ({ ...x, extra_fields: { ...x.extra_fields, [q.key]: v } }))}/></Field>)}
            </div>
            <div className="yf-actions"><Button onClick={() => setEditing(false)}>Annuler</Button><Button primary type="submit" icon="check" disabled={busy}>Enregistrer</Button></div>
          </form>}
        </Card>
        <Card title="Responsables légaux" icon="users" right={canManage && !newGuardian && <Button className="small" icon="plus" onClick={() => setNewGuardian({ ...emptyGuardian, relationship: "Père" })}>Ajouter</Button>}>
          {d.guardians.filter(g => g.active).length === 0 && <Empty>Aucun responsable enregistré : le dossier est incomplet.</Empty>}
          {d.guardians.filter(g => g.active).map(g => <div key={g.id} className="yf-person">
            <div><b>{g.full_name}</b>{g.is_primary && <Status>Principal</Status>}<small>{[g.relationship, g.profession].filter(Boolean).join(" · ")}</small></div>
            <div className="yf-contact">{g.phone && <a href={`https://wa.me/${g.phone.replace(/[^\d]/g, "")}`} target="_blank" rel="noreferrer"><Icon name="whatsapp" size={18}/>{g.phone}</a>}{g.email && <a href={`mailto:${g.email}`}><Icon name="mail" size={18}/>{g.email}</a>}{g.address && <span>{g.address}</span>}</div>
            {canManage && <div className="yf-row-actions">
              {!g.is_primary && <button type="button" className="yf-link" disabled={busy} onClick={() => run(async () => { for (const o of d.guardians.filter(x => x.is_primary && x.active)) await req(`schools/${schoolId}/students/${s.id}/guardians/${o.id}`, { revision: o.revision, is_primary: false }, "PATCH"); await req(`schools/${schoolId}/students/${s.id}/guardians/${g.id}`, { revision: g.revision, is_primary: true }, "PATCH"); }, "Responsable principal modifié.")}>Définir principal</button>}
              <button type="button" className="yf-link danger" disabled={busy} onClick={() => run(() => req(`schools/${schoolId}/students/${s.id}/guardians/${g.id}`, { revision: g.revision, active: false }, "PATCH"), "Responsable retiré du dossier.")}>Retirer</button>
            </div>}
          </div>)}
          {newGuardian && <form onSubmit={e => { e.preventDefault(); run(async () => { await req(`schools/${schoolId}/students/${s.id}/guardians`, { ...Object.fromEntries(Object.entries(newGuardian).filter(([, v]) => v !== "")), is_primary: !d.guardians.some(g => g.active && g.is_primary) }); setNewGuardian(null); }, "Responsable ajouté."); }}>
            <div className="yf-grid">
              <Field label="Nom complet" required><input required value={newGuardian.full_name} onChange={e => setNewGuardian(x => ({ ...x, full_name: e.target.value }))}/></Field>
              <Field label="Lien"><select value={newGuardian.relationship} onChange={e => setNewGuardian(x => ({ ...x, relationship: e.target.value }))}>{["Mère", "Père", "Tuteur", "Tutrice", "Grand-parent", "Oncle", "Tante", "Autre"].map(x => <option key={x}>{x}</option>)}</select></Field>
              <Field label="Téléphone"><input type="tel" value={newGuardian.phone} onChange={e => setNewGuardian(x => ({ ...x, phone: e.target.value }))}/></Field>
              <Field label="Email"><input type="email" value={newGuardian.email} onChange={e => setNewGuardian(x => ({ ...x, email: e.target.value }))}/></Field>
              <Field label="Profession"><input value={newGuardian.profession} onChange={e => setNewGuardian(x => ({ ...x, profession: e.target.value }))}/></Field>
              <Field label="Adresse"><input value={newGuardian.address} onChange={e => setNewGuardian(x => ({ ...x, address: e.target.value }))}/></Field>
            </div>
            <div className="yf-actions"><Button onClick={() => setNewGuardian(null)}>Annuler</Button><Button primary type="submit" icon="check" disabled={busy}>Ajouter le responsable</Button></div>
          </form>}
        </Card>
        <Card title="Pièces du dossier" icon="paperclip" subtitle={d.missing_documents.length ? `Manquant : ${d.missing_documents.join(", ")}` : "Toutes les pièces obligatoires sont fournies."}>
          {form.documents.length === 0 ? <Empty>Aucune pièce demandée par l’établissement.</Empty> :
            <div className="yf-checks">{form.documents.map(doc => { const on = !!s.documents[doc.key]; return <button type="button" key={doc.key} disabled={!canManage || busy} className={on ? "active" : ""}
              onClick={() => run(() => req(`schools/${schoolId}/students/${s.id}`, { revision: s.revision, documents: { ...s.documents, [doc.key]: !on } }, "PATCH"), on ? "Pièce retirée." : "Pièce enregistrée comme fournie.")}><Check on={on}/><span>{doc.label}{doc.required && <i> *</i>}</span></button>; })}</div>}
        </Card>
      </div>
      <div className="yd-stack">
        <Card title="Scolarité" icon="cap">
          {d.enrollments.length === 0 ? <Empty>Pas encore inscrit dans une classe.</Empty> :
            <Table className="xs" headers={["Année", "Classe", "Inscrit le", "Statut"]} rows={d.enrollments.map(e => [e.year_name, <b>{e.classroom_name}</b>, fmtDate(e.enrolled_on), <Status tone={e.active ? "green" : "gray"}>{e.active ? "Inscrit" : "Clôturé"}</Status>])}/>}
          {canManage && classes.data && curYear && <div className="yf-inline-form">
            {enrolledThisYear ? (() => { const e = d.enrollments.find(x => x.year === curYear.id); return <>
              <select aria-label="Nouvelle classe" value={target} onChange={ev => setTarget(ev.target.value)}><option value="">Changer de classe…</option>{classes.data.classes.filter(c => c.active && c.id !== e.classroom).map(c => <option key={c.id} value={c.id} disabled={c.remaining === 0}>{c.name}{c.remaining === 0 ? " (complète)" : ""}</option>)}</select>
              <Button className="small" icon="transfer" disabled={!target || busy} onClick={() => run(async () => { await req(`schools/${schoolId}/enrollments/${e.id}`, { revision: e.revision, classroom: target }, "PATCH"); setTarget(""); }, "Changement de classe enregistré (historisé).")}>Transférer</Button>
            </>; })() : <>
              <select aria-label="Classe" value={target} onChange={ev => setTarget(ev.target.value)}><option value="">Inscrire en {curYear.name} dans…</option>{classes.data.classes.filter(c => c.active).map(c => <option key={c.id} value={c.id} disabled={c.remaining === 0}>{c.name}{c.remaining == null ? "" : ` — ${c.remaining} place(s)`}</option>)}</select>
              <Button className="small" primary icon="adduser" disabled={!target || busy} onClick={() => run(async () => { const r = await req(`schools/${schoolId}/classes/${target}/enroll`, { students: [s.id] }); if (r.failed?.length) throw Error(r.failed[0].error); setTarget(""); }, "Élève inscrit.")}>Inscrire</Button>
            </>}
          </div>}
        </Card>
        {d.finance_visible && <Card title="Paiements" icon="wallet" subtitle={current ? `${current.classroom_name} · ${current.year_name}` : ""}>
          {!f ? <Empty>Aucune inscription, donc aucun frais.</Empty> : <>
            <div className="yd-info-list">
              <InfoRow icon="coins" k="Total dû" v={money(f.billed, f.currency)}/>
              <InfoRow icon="wallet" k="Montant payé" v={money(f.paid, f.currency)}/>
              <InfoRow icon="scale" k="Reste à payer" v={money(f.balance, f.currency)} highlight/>
              <InfoRow icon="info" k="Situation" v={<Status tone={FIN[f.status][0]}>{FIN[f.status][1]}</Status>}/>
            </div>
            <h3 className="yf-sub">Frais affectés</h3>
            {f.charges.length === 0 ? <Empty>Aucun frais affecté. Utilisez « Affecter les frais » dans Inscriptions par classe.</Empty> :
              <Table className="xs" headers={["Frais", "Échéance", "Montant", "Payé", "Reste"]} rows={f.charges.map(c => [c.label, fmtDate(c.due_date), money(c.amount, c.currency), money(c.paid, c.currency), <b>{money(c.balance, c.currency)}</b>])}/>}
            <h3 className="yf-sub">Historique des paiements</h3>
            {f.payments.length === 0 ? <Empty>Aucun paiement enregistré.</Empty> :
              <Table className="xs" headers={["Date", "Frais", "Montant", "Moyen", "Reçu"]} rows={f.payments.map(p => [fmtDate(p.paid_on), p.label, p.voided ? <s>{money(p.amount, p.currency)}</s> : money(p.amount, p.currency), <>{methodLabel(p.method)}{p.reference && <small className="yf-ref"> · {p.reference}</small>}</>, p.voided ? <Status tone="gray">Annulé</Status> : <a className="yd-link" href={`/api/v1/schools/${schoolId}/finance/payments/${p.id}/receipt`} target="_blank" rel="noreferrer">R-{p.id.slice(0, 8).toUpperCase()}</a>])}/>}
          </>}
        </Card>}
      </div>
    </div>}</Loading>
  </>;
}

/* ---------- Inscriptions par classe ---------- */
export function ClassEnrollments({ schoolId, canManage, canReceive, onNavigate, tabs }) {
  const [year, setYear] = useState("");
  const overview = useLoad(`schools/${schoolId}/overview/classes${year ? `?year=${year}` : ""}`);
  const roster = useLoad(`schools/${schoolId}/overview/students${year ? `?year=${year}` : ""}`);
  const [selected, setSelected] = useState("");
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState({});
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState({ text: "" });
  const o = overview.data;
  const klass = o?.classes.find(c => c.id === selected) || o?.classes.find(c => c.active);
  const students = roster.data?.students || [];
  const members = students.filter(s => s.enrollment?.classroom.id === klass?.id);
  const unassigned = students.filter(s => s.active && !s.enrollment && `${s.last_name} ${s.first_name} ${s.student_code}`.toLowerCase().includes(query.toLowerCase()));
  async function run(fn) {
    setBusy(true); setMessage({ text: "" });
    try { setMessage({ text: await fn() }); overview.reload(); roster.reload(); }
    catch (e) { setMessage({ text: e.message, error: true }); } finally { setBusy(false); }
  }
  const enrollPicked = () => run(async () => {
    const ids = Object.keys(picked).filter(k => picked[k]);
    const r = await req(`schools/${schoolId}/classes/${klass.id}/enroll`, { students: ids });
    setPicked({}); setPicking(false);
    return [`${r.enrolled.length} élève(s) inscrit(s) en ${klass.name}.`, r.charges_created ? `${r.charges_created} frais affecté(s).` : "", r.failed.length ? `${r.failed.length} refus : ${r.failed[0].error}` : ""].filter(Boolean).join(" ");
  });
  const fin = c => c.finance;
  return <>
    <PageHeader title="Inscriptions par classe" subtitle="Effectifs, places restantes, élèves inscrits et situation des paiements par classe"
      actions={o && <label className="yd-select plain"><select aria-label="Année scolaire" value={year || o.year?.id || ""} onChange={e => { setYear(e.target.value); setSelected(""); }}>{o.years.map(y => <option key={y.id} value={y.id}>{y.name}</option>)}</select><Icon name="chevron" size={18} className="chev"/></label>}/>
    {tabs}
    <Msg {...message}/>
    <Loading state={overview}>{o && (!o.year || o.classes.length === 0 ? <Card title={o.year ? `Aucune classe en ${o.year.name}` : "Aucune année scolaire"} icon="school">
      <Empty>Créez d’abord {o.year ? "les classes" : "l’année scolaire puis les classes"} de l’établissement.</Empty>
      {(o.can_manage_classes ?? o.can_manage_academic) && <Button primary icon="plus" onClick={() => onNavigate("settings", "classes")}>Créer les classes</Button>}
    </Card> : <>
      <div className="yd-metrics four">
        <Metric icon="school" label="Classes" value={num(o.classes.filter(c => c.active).length)} trend="none" trendLabel={o.year.name}/>
        <Metric icon="users" label="Élèves inscrits" value={num(o.classes.reduce((a, c) => a + c.enrolled, 0))} trend="none" trendLabel={`${num(o.classes.reduce((a, c) => a + (c.remaining || 0), 0))} places restantes`}/>
        <Metric icon="alert" label="Élèves sans classe" value={num(o.unassigned_students)} trend="none" trendLabel="dossiers actifs non inscrits"/>
        {o.finance_visible ? <Metric icon="scale" label="Reste à payer" value={money(o.classes.reduce((a, c) => a + Number(c.finance?.balance || 0), 0), o.currency)} trend="none" trendLabel="toutes classes"/> : <Metric icon="cap" label="Classes complètes" value={num(o.classes.filter(c => c.remaining === 0).length)} trend="none" trendLabel="capacité atteinte"/>}
      </div>
      <div className="yc-cards">{o.classes.filter(c => c.active).map(c => <button type="button" key={c.id} className={`yc-card ${klass?.id === c.id ? "active" : ""}`} onClick={() => { setSelected(c.id); setPicking(false); }}>
        <span className="yc-head"><b>{c.name}</b><small>{c.level.name}</small></span>
        <span className="yc-count"><strong>{c.enrolled}</strong>{c.capacity ? ` / ${c.capacity}` : " inscrits"}</span>
        {c.capacity ? <span className="yc-bar"><i style={{ width: `${Math.min(100, c.enrolled / c.capacity * 100)}%` }}/></span> : null}
        <small>{c.remaining == null ? "Capacité libre" : c.remaining === 0 ? "Classe complète" : `${c.remaining} place(s) restante(s)`}</small>
        {fin(c) && c.enrolled > 0 && <span className="yc-fin">{fin(c).a_jour > 0 && <em className="ok">{fin(c).a_jour} payé</em>}{fin(c).partiel > 0 && <em className="mid">{fin(c).partiel} partiel</em>}{fin(c).impaye > 0 && <em className="ko">{fin(c).impaye} impayé</em>}{fin(c).sans_frais > 0 && <em>{fin(c).sans_frais} sans frais</em>}</span>}
      </button>)}</div>
      {klass && <Card title={`Élèves de ${klass.name}`} count={`(${members.length})`} icon="users" right={<div className="yf-head-actions">
        {canManage && <Button className="small" icon="adduser" primary onClick={() => onNavigate("students", "new", { classroom: klass.id })}>Nouvel élève</Button>}
        {canManage && <Button className="small" icon="users" onClick={() => setPicking(p => !p)}>Inscrire des élèves existants</Button>}
        {o.can_manage_finance && <Button className="small" icon="coins" disabled={busy || !members.length} onClick={() => run(async () => { const r = await req(`schools/${schoolId}/classes/${klass.id}/apply-fees`, {}); return r.charges_created ? `${r.charges_created} frais affecté(s) aux élèves de ${klass.name}.` : "Tous les élèves ont déjà leurs frais."; })}>Affecter les frais ({klass.fee_schedules})</Button>}
        <Button className="small" icon="download" disabled={!members.length} onClick={() => downloadCsv(`classe-${klass.code}.csv`, [["Matricule", "Nom", "Prénom", "Responsable", "Téléphone", "Total", "Payé", "Reste", "Situation", "Moyens"], ...members.map(s => [s.student_code, s.last_name, s.first_name, s.guardian?.full_name, s.guardian?.phone, s.finance?.billed, s.finance?.paid, s.finance?.balance, s.finance ? FIN[s.finance.status][1] : "", (s.finance?.methods || []).map(methodLabel).join(", ")])])}>Exporter</Button>
      </div>}>
        {picking && <div className="yc-picker">
          <div className="yf-inline-form"><SearchBox placeholder="Rechercher un élève sans classe" value={query} onChange={e => setQuery(e.target.value)}/><Button primary icon="check" disabled={busy || !Object.values(picked).some(Boolean)} onClick={enrollPicked}>Inscrire la sélection ({Object.values(picked).filter(Boolean).length})</Button></div>
          {unassigned.length === 0 ? <Empty>Aucun élève sans classe pour cette année. Créez une fiche avec « Nouvel élève ».</Empty> :
            <div className="yf-checks list">{unassigned.slice(0, 200).map(s => <button type="button" key={s.id} className={picked[s.id] ? "active" : ""} onClick={() => setPicked(p => ({ ...p, [s.id]: !p[s.id] }))}><Check on={!!picked[s.id]}/><span>{s.last_name} {s.first_name} <small>· {s.student_code}</small></span></button>)}</div>}
        </div>}
        <Loading state={roster}>{members.length === 0 ? <Empty>Aucun élève inscrit dans cette classe.</Empty> :
          <TableScroll label="Élèves de la classe"><table className="xs nowrap clickable"><thead><tr>{["#", "Élève", "Responsable", "Téléphone", ...(o.finance_visible ? ["Payé", "Reste", "Situation", "Moyens"] : []), "Pièces", ""].map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
            <tbody>{members.map((s, i) => <tr key={s.id} onClick={() => onNavigate("students", "fiche", { student: s.id })}>
              <td>{i + 1}</td><td><b>{s.last_name} {s.first_name}</b></td><td>{s.guardian?.full_name || "—"}</td><td>{s.guardian?.phone || "—"}</td>
              {o.finance_visible && <><td>{money(s.finance?.paid, roster.data.currency)}</td><td><b>{money(s.finance?.balance, roster.data.currency)}</b></td><td>{s.finance && <Status tone={FIN[s.finance.status][0]}>{FIN[s.finance.status][1]}</Status>}</td><td>{(s.finance?.methods || []).map(methodLabel).join(", ") || "—"}</td></>}
              <td>{s.missing_documents ? <Status tone="yellow">{s.missing_documents} manquante(s)</Status> : <Status>Complet</Status>}</td>
              <td>{canReceive && Number(s.finance?.balance) > 0 ? <button type="button" className="yf-link" onClick={e => { e.stopPropagation(); onNavigate("payments", "live", { enrollment: s.enrollment.id }); }}>Encaisser</button> : <Icon name="chevronright" size={18}/>}</td>
            </tr>)}</tbody></table></TableScroll>}</Loading>
      </Card>}
    </>)}</Loading>
  </>;
}

/* ---------- Paramètres : classes ---------- */
export function ClassSetup({ schoolId, tabs }) {
  const [year, setYear] = useState("");
  const o = useLoad(`schools/${schoolId}/overview/classes${year ? `?year=${year}` : ""}`);
  const y0 = new Date().getMonth() >= 6 ? new Date().getFullYear() : new Date().getFullYear() - 1;
  const [newYear, setNewYear] = useState({ name: `${y0}-${y0 + 1}`, start_date: `${y0}-09-01`, end_date: `${y0 + 1}-07-31` });
  const [level, setLevel] = useState("");
  const [levelName, setLevelName] = useState("");
  const [cycleName, setCycleName] = useState("");
  const [names, setNames] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [suffix, setSuffix] = useState("letters");
  const [preview, setPreview] = useState([]);
  const [editing, setEditing] = useState(null);
  const [manual, setManual] = useState(false);
  const [capacity, setCapacity] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState({ text: "" });
  const d = o.data;
  async function run(fn) {
    setBusy(true); setMessage({ text: "" });
    try { setMessage({ text: await fn() }); o.reload(); } catch (e) { setMessage({ text: e.message, error: true }); } finally { setBusy(false); }
  }
  const yearForm = <form className="yf-inline-form wrap" onSubmit={e => { e.preventDefault(); run(async () => { const r = await req(`schools/${schoolId}/academic/years`, { ...newYear, code: newYear.name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "annee" }); setYear(r.id); return `Année ${r.name} créée.`; }); }}>
    <Field label="Nom de l’année"><input required value={newYear.name} onChange={e => setNewYear(x => ({ ...x, name: e.target.value }))}/></Field>
    <Field label="Début"><input type="date" required value={newYear.start_date} onChange={e => setNewYear(x => ({ ...x, start_date: e.target.value }))}/></Field>
    <Field label="Fin"><input type="date" required value={newYear.end_date} onChange={e => setNewYear(x => ({ ...x, end_date: e.target.value }))}/></Field>
    <Button primary type="submit" icon="plus" disabled={busy}>Créer l’année</Button>
  </form>;
  const cycleAllowed = code => !d?.class_management_cycles || d.class_management_cycles.includes(code);
  const presets = Object.entries(d?.class_level_options || {}).filter(([, option]) =>
    cycleAllowed(option.cycle) && !d.levels.some(l => l.cycle_code === option.cycle && l.code === option.code));
  const preset = d?.class_level_options?.[level];
  const selectedLevelName = preset?.name || d?.levels.find(l => l.id === level)?.name || levelName.trim();
  const canManageClasses = d?.can_manage_classes ?? d?.can_manage_academic;
  const count = preview.length || names.split(/[,;\n]/).map(x => x.trim()).filter(Boolean).length;
  function proposeNames() {
    const used = new Set(d.classes.map(c => c.name.toLowerCase()));
    const proposed = [];
    for (let i = 1; proposed.length < Number(quantity); i++) {
      const label = suffix === "letters" ? (i <= 26 ? String.fromCharCode(64 + i)
        : String.fromCharCode(64 + Math.floor((i - 1) / 26), 65 + (i - 1) % 26)) : String(i);
      const name = `${selectedLevelName.slice(0, 120 - label.length - 1).trimEnd()} ${label}`;
      if (!used.has(name.toLowerCase())) proposed.push(name);
    }
    setPreview(proposed);
  }
  return <>
    <PageHeader title="Classes de l’établissement" subtitle="Créez les classes de l’année en quelques secondes, réglez leur capacité d’accueil" banner={false}
      actions={d?.years.length > 0 && <label className="yd-select plain"><select aria-label="Année scolaire" value={year || d.year?.id || ""} onChange={e => { setYear(e.target.value); setPreview([]); setEditing(null); }}>{d.years.map(y => <option key={y.id} value={y.id}>{y.name}</option>)}</select><Icon name="chevron" size={18} className="chev"/></label>}/>
    {tabs}
    {!editing && <Msg {...message}/>}
    <Loading state={o}>{d && (year && year !== d.year?.id ? <p role="status">Chargement de l’année…</p> : <>
      {!d.year ? <Card title="Commencez par l’année scolaire" icon="calendar">{d.can_manage_academic ? yearForm : <Empty>La direction doit créer l’année scolaire.</Empty>}</Card> : <div className="yd-grid yf-two">
        {canManageClasses && d.year.active !== false && <Card title={`Ajouter des classes en ${d.year.name}`} icon="plus" subtitle="Choisissez le niveau et le nombre de classes.">
          <form onSubmit={e => { e.preventDefault(); if (!(manual || preview.length)) return; run(async () => {
            const target = preset ? { preset: level } : level === "new" ? { level_name: levelName, cycle_name: cycleName } : { level };
            const r = await req(`schools/${schoolId}/academic/quick-classes`, {
              year: d.year.id, names: preview.length ? preview : names,
              capacity: capacity === "" ? null : Number(capacity), ...target,
            });
            setNames(""); setPreview([]); setManual(false); setLevel(r.level.id);
            return `${r.classes.length} classe(s) créée(s) : ${r.classes.map(c => c.name).join(", ")}.`;
          }); }}>
            <div className="yf-grid">
              <Field label="Niveau" required><select required value={level} onChange={e => { setLevel(e.target.value); setPreview([]); }}>
                <option value="">Choisir…</option>
                {d.levels.filter(l => l.active && cycleAllowed(l.cycle_code)).map(l => <option key={l.id} value={l.id}>{l.name} ({l.cycle})</option>)}
                {presets.map(([key, option]) => <option key={key} value={key}>{option.name} ({option.cycle_name})</option>)}
                {d.can_manage_academic && <option value="new">+ Nouveau niveau…</option>}
              </select></Field>
              {level === "new" && <><Field label="Nom du niveau" required hint="Ex. : CP, 6e, Terminale"><input required maxLength={120} value={levelName} onChange={e => { setLevelName(e.target.value); setPreview([]); }}/></Field>
                <Field label="Cycle" hint="Ex. : Primaire, Collège."><input maxLength={120} value={cycleName} onChange={e => { setCycleName(e.target.value); setPreview([]); }} list="yc-cycles"/><datalist id="yc-cycles">{[...new Set(d.levels.map(l => l.cycle))].map(c => <option key={c} value={c}/>)}</datalist></Field></>}
              {!manual && <Field label="Nombre de classes"><input type="number" value={quantity} onChange={e => { setQuantity(e.target.value); setPreview([]); }}/></Field>}
            </div>
            {!manual && <details className="yf-details"><summary>Options de génération</summary>
              <div className="yf-grid">
                <Field label="Format des noms"><select value={suffix} onChange={e => { setSuffix(e.target.value); setPreview([]); }}>
                  <option value="letters">Lettres (A, B, C…)</option>
                  <option value="numbers">Chiffres (1, 2, 3…)</option>
                </select></Field>
                <Field label="Capacité par classe"><input type="number" min={1} max={5000} value={capacity} onChange={e => setCapacity(e.target.value)}/></Field>
              </div>
            </details>}
            {manual ? <Field label="Nom(s) des classes" required hint="Séparez les noms par des virgules.">
              <input required value={names} onChange={e => setNames(e.target.value)} placeholder="6e Horizon, 6e 13"/>
            </Field> : preview.length > 0 && <div className="yf-grid">
              {preview.map((name, index) => <Field key={index} label={`Nom de la classe ${index + 1}`} required>
                <input required maxLength={120} value={name} onChange={e => setPreview(items => items.map((item, i) => i === index ? e.target.value : item))}/>
              </Field>)}
            </div>}
            <div className="yf-inline-form">
              {manual || preview.length > 0
                ? <Button key="save" primary type="submit" icon="check" disabled={busy || !count}>Créer {count > 1 ? `les ${count} classes` : "la classe"}</Button>
                : <Button key="generate" primary type="button" icon="plus" disabled={busy || !selectedLevelName || !Number.isInteger(Number(quantity)) || Number(quantity) < 1 || Number(quantity) > 30} onClick={proposeNames}>Générer les classes</Button>}
              <button type="button" className="yf-link" disabled={busy} onClick={() => { setManual(x => !x); setPreview([]); setNames(""); }}>
                {manual ? "Revenir à la génération" : "Saisir les noms manuellement"}
              </button>
            </div>
          </form>
        </Card>}
        <Card title={`Classes ${d.year.name}`} count={`(${d.classes.length})`} icon="school">
          {editing && <><Msg {...message}/><form className="yf-form" onSubmit={e => { e.preventDefault(); run(async () => {
            const saved = await req(`schools/${schoolId}/academic/classes/${editing.id}`, {
              revision: editing.revision, name: editing.name, active: editing.active,
              capacity: editing.capacity === "" ? null : Number(editing.capacity),
            }, "PATCH");
            setEditing(null);
            return `${saved.name} enregistrée.`;
          }); }}>
            <div className="yf-grid">
              <Field label="Nom de la classe" required><input autoFocus required maxLength={120} value={editing.name} onChange={e => setEditing({...editing, name: e.target.value})}/></Field>
              <Field label="Capacité"><input type="number" min={Math.max(1, editing.enrolled)} max={5000} value={editing.capacity} onChange={e => setEditing({...editing, capacity: e.target.value})}/></Field>
              <Field label="Statut"><select value={editing.active ? "active" : "archived"} onChange={e => setEditing({...editing, active: e.target.value === "active"})}><option value="active">Active</option><option value="archived">Archivée</option></select></Field>
            </div>
            <div className="yf-inline-form">
              <Button primary type="submit" disabled={busy}>Enregistrer</Button>
              <Button type="button" disabled={busy} onClick={() => setEditing(null)}>Annuler</Button>
              <button type="button" className="yf-link danger" disabled={busy} onClick={() => {
                if (!window.confirm(`Supprimer définitivement la classe « ${editing.originalName} » ?`)) return;
                run(async () => {
                  await req(`schools/${schoolId}/academic/classes/${editing.id}`, { revision: editing.revision }, "DELETE");
                  setEditing(null);
                  return "Classe supprimée.";
                });
              }}>Supprimer la classe</button>
            </div>
          </form></>}
          {d.classes.length === 0 ? <Empty>Aucune classe pour cette année.</Empty> :
            <TableScroll label="Classes de l’année"><table className="xs"><thead><tr>{["Classe", "Inscrits", "Capacité", "Statut", "Actions"].map(h => <th key={h}>{h}</th>)}</tr></thead>
              <tbody>{d.classes.map(c => <tr key={c.id}>
                <td><b>{c.name}</b><br/><small>{c.level.name}</small></td><td>{c.enrolled}</td><td>{c.capacity ?? "—"}</td>
                <td><Status tone={c.active ? "green" : "gray"}>{c.active ? "Active" : "Archivée"}</Status></td>
                <td>{canManageClasses && cycleAllowed(c.level.cycle_code) && <button type="button" className="yf-link" aria-label={`Modifier ${c.name}`} disabled={busy} onClick={() => { setMessage({text: ""}); setEditing({ ...c, capacity: c.capacity ?? "", originalName: c.name }); }}>Modifier</button>}</td>
              </tr>)}</tbody></table></TableScroll>}
          {d.can_manage_academic && <details className="yf-details"><summary>Créer une autre année scolaire</summary>{yearForm}</details>}
        </Card>
      </div>}
    </>)}</Loading>
  </>;
}

/* ---------- Paramètres : formulaire d'inscription modulable ---------- */
const TYPE_LABELS = { text: "Texte court", textarea: "Texte long", date: "Date", number: "Nombre", select: "Liste de choix", yesno: "Oui / Non" };
export function FormSettings({ schoolId, canEdit, tabs }) {
  const state = useLoad(`schools/${schoolId}/enrollment-form`);
  const [config, setConfig] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState({ text: "" });
  const [q, setQ] = useState({ label: "", type: "text", options: "", required: false, section: "eleve" });
  const [doc, setDoc] = useState({ label: "", required: true });
  useEffect(() => { if (state.data) setConfig(structuredClone(state.data.config)); }, [state.data]);
  const dirty = config && state.data && JSON.stringify(config) !== JSON.stringify(state.data.config);
  const taken = config ? [...(state.data?.base_fields || []).map(b => b.key), ...config.custom_fields.map(x => x.key)] : [];
  async function save() {
    setBusy(true); setMessage({ text: "" });
    try { await req(`schools/${schoolId}/enrollment-form`, { config, revision: state.data.revision }, "PUT"); setMessage({ text: "Fiche d’inscription enregistrée. Elle s’applique dès maintenant aux nouveaux dossiers." }); state.reload(); }
    catch (e) { setMessage({ text: e.message, error: true }); } finally { setBusy(false); }
  }
  const setRule = (key, patch) => setConfig(c => ({ ...c, fields: { ...c.fields, [key]: { ...c.fields[key], ...patch, ...(patch.visible === false ? { required: false } : {}) } } }));
  const move = (list, i, delta) => setConfig(c => { const arr = [...c[list]]; const j = i + delta; if (j < 0 || j >= arr.length) return c; [arr[i], arr[j]] = [arr[j], arr[i]]; return { ...c, [list]: arr }; });
  return <>
    <PageHeader title="Fiche d’inscription de l’établissement" subtitle="Choisissez les renseignements demandés, ajoutez vos propres questions et la liste des pièces à fournir" banner={false}
      actions={canEdit && <Button primary icon="check" disabled={!dirty || busy} onClick={save}>{dirty ? "Enregistrer les modifications" : "Enregistré"}</Button>}/>
    {tabs}
    <Msg {...message}/>
    <Loading state={state}>{config && <div className="yd-grid yf-two">
      <div className="yd-stack">
        <Card title="Renseignements de base" icon="idcard" subtitle="Nom, prénom et responsable principal sont toujours demandés. Réglez les autres champs.">
          <TableScroll label="Champs d’inscription"><table className="xs"><thead><tr><th>Champ</th><th>Section</th><th>Demandé</th><th>Obligatoire</th></tr></thead>
            <tbody>{state.data.base_fields.map(b => { const r = config.fields[b.key] || {}; return <tr key={b.key}>
              <td>{b.label}</td><td>{b.section === "eleve" ? "Élève" : "Responsable"}</td>
              <td><button type="button" className="yf-switch" disabled={!canEdit} aria-pressed={r.visible !== false} onClick={() => setRule(b.key, { visible: r.visible === false })}><Check on={r.visible !== false}/></button></td>
              <td>{b.key !== "second_guardian" && <button type="button" className="yf-switch" disabled={!canEdit || r.visible === false} aria-pressed={!!r.required} onClick={() => setRule(b.key, { required: !r.required })}><Check on={!!r.required}/></button>}</td>
            </tr>; })}</tbody></table></TableScroll>
        </Card>
        <Card title="Pièces à fournir" icon="paperclip" count={`(${config.documents.length})`}>
          {config.documents.map((d, i) => <div key={d.key} className="yf-listrow">
            <input aria-label="Libellé de la pièce" disabled={!canEdit} value={d.label} onChange={e => setConfig(c => ({ ...c, documents: c.documents.map((x, j) => j === i ? { ...x, label: e.target.value } : x) }))}/>
            <button type="button" className="yd-toggle-btn" disabled={!canEdit} aria-pressed={d.required} onClick={() => setConfig(c => ({ ...c, documents: c.documents.map((x, j) => j === i ? { ...x, required: !x.required } : x) }))}><Check on={d.required}/>Obligatoire</button>
            {canEdit && <><button type="button" className="yf-icon" aria-label="Monter" onClick={() => move("documents", i, -1)}>↑</button><button type="button" className="yf-icon" aria-label="Retirer" onClick={() => setConfig(c => ({ ...c, documents: c.documents.filter((_, j) => j !== i) }))}><Icon name="trash" size={18}/></button></>}
          </div>)}
          {canEdit && <form className="yf-listrow add" onSubmit={e => { e.preventDefault(); if (!doc.label.trim()) return; setConfig(c => ({ ...c, documents: [...c.documents, { key: uniqueKey(doc.label, c.documents.map(x => x.key)), label: doc.label.trim(), required: doc.required }] })); setDoc({ label: "", required: true }); }}>
            <input placeholder="Ex. : Certificat de vaccination, Certificat de radiation…" value={doc.label} onChange={e => setDoc(x => ({ ...x, label: e.target.value }))}/>
            <button type="button" className="yd-toggle-btn" aria-pressed={doc.required} onClick={() => setDoc(x => ({ ...x, required: !x.required }))}><Check on={doc.required}/>Obligatoire</button>
            <Button type="submit" icon="plus" className="small">Ajouter</Button>
          </form>}
        </Card>
      </div>
      <Card title="Questions propres à l’établissement" icon="list" count={`(${config.custom_fields.length})`} subtitle="Ces questions apparaissent dans la fiche « Nouvel élève » et dans le dossier de chaque élève.">
        {config.custom_fields.length === 0 && <Empty>Aucune question personnalisée pour l’instant.</Empty>}
        {config.custom_fields.map((f, i) => <div key={f.key} className="yf-question">
          <div><b>{f.label}</b>{f.required && <Status tone="yellow">Obligatoire</Status>}<small>{TYPE_LABELS[f.type]} · {f.section === "eleve" ? "Élève" : "Responsable"}{f.options?.length ? ` · ${f.options.join(", ")}` : ""}</small></div>
          {canEdit && <span><button type="button" className="yf-icon" aria-label="Monter" onClick={() => move("custom_fields", i, -1)}>↑</button><button type="button" className="yf-icon" aria-label="Descendre" onClick={() => move("custom_fields", i, 1)}>↓</button><button type="button" className="yf-icon" aria-label="Retirer" onClick={() => setConfig(c => ({ ...c, custom_fields: c.custom_fields.filter((_, j) => j !== i) }))}><Icon name="trash" size={18}/></button></span>}
        </div>)}
        {canEdit && <form className="yf-newq" onSubmit={e => { e.preventDefault(); if (!q.label.trim()) return;
          const options = q.type === "select" ? q.options.split(/[,;\n]/).map(x => x.trim()).filter(Boolean) : [];
          if (q.type === "select" && !options.length) { setMessage({ text: "Indiquez les choix possibles, séparés par des virgules.", error: true }); return; }
          setConfig(c => ({ ...c, custom_fields: [...c.custom_fields, { key: uniqueKey(q.label, taken), label: q.label.trim(), type: q.type, options, required: q.required, section: q.section }] }));
          setQ({ label: "", type: "text", options: "", required: false, section: "eleve" }); setMessage({ text: "" }); }}>
          <h3>Ajouter une question</h3>
          <div className="yf-grid">
            <Field label="Question" required wide><input required maxLength={120} placeholder="Ex. : Groupe de transport, Langue parlée à la maison…" value={q.label} onChange={e => setQ(x => ({ ...x, label: e.target.value }))}/></Field>
            <Field label="Type de réponse"><select value={q.type} onChange={e => setQ(x => ({ ...x, type: e.target.value }))}>{Object.entries(TYPE_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            <Field label="Section"><select value={q.section} onChange={e => setQ(x => ({ ...x, section: e.target.value }))}><option value="eleve">Élève</option><option value="responsable">Responsable</option></select></Field>
            {q.type === "select" && <Field label="Choix possibles" required wide hint="Séparés par des virgules."><input value={q.options} onChange={e => setQ(x => ({ ...x, options: e.target.value }))}/></Field>}
          </div>
          <div className="yf-inline-form"><button type="button" className="yd-toggle-btn" aria-pressed={q.required} onClick={() => setQ(x => ({ ...x, required: !x.required }))}><Check on={q.required}/>Réponse obligatoire</button><Button type="submit" icon="plus">Ajouter la question</Button></div>
        </form>}
        {!canEdit && <Empty>Seul le secrétariat ou la direction peut modifier la fiche.</Empty>}
        {dirty && <p className="yd-form-msg">Modifications non enregistrées : cliquez sur « Enregistrer les modifications » en haut de la page.</p>}
      </Card>
    </div>}</Loading>
  </>;
}

/* ---------- Suivi des paiements ---------- */
export function PaymentTracking({ schoolId, canReceive, onNavigate, tabs }) {
  const roster = useLoad(`schools/${schoolId}/overview/students`);
  const fin = useLoad(`schools/${schoolId}/overview/finance`);
  const [query, setQuery] = useState("");
  const [klass, setKlass] = useState("");
  const [status, setStatus] = useState("");
  const [method, setMethod] = useState("");
  const d = roster.data;
  const enrolled = useMemo(() => (d?.students || []).filter(s => s.active && s.enrollment && s.finance), [d]);
  const rows = enrolled.filter(s => `${s.last_name} ${s.first_name} ${s.student_code} ${s.guardian?.full_name || ""}`.toLowerCase().includes(query.toLowerCase())
    && (!klass || s.enrollment.classroom.id === klass) && (!status || s.finance.status === status) && (!method || s.finance.methods.includes(method)));
  const sum = (list, k) => list.reduce((a, s) => a + Number(s.finance[k] || 0), 0);
  const by = st => enrolled.filter(s => s.finance.status === st);
  const usedMethods = [...new Set(enrolled.flatMap(s => s.finance.methods))];
  const yearMethods = Object.entries(fin.data?.year_by_method || {}).map(([k, v]) => [methodLabel(k), Number(v)]).sort((a, b) => b[1] - a[1]);
  const yearTotal = Number(fin.data?.year_total || 0);
  const currency = d?.currency || fin.data?.currency;
  return <>
    <PageHeader title="Suivi des paiements" subtitle="Qui a payé, qui reste à payer et par quel moyen, élève par élève" badge="Économe" badgeIcon="coins"/>
    {tabs}
    <Loading state={roster}>{d && (!d.finance_visible ? <Empty>Votre rôle ne donne pas accès aux informations financières.</Empty> : <>
      <div className="yd-metrics four">
        <Metric icon="checkcircle" label="Ont tout payé" value={num(by("a_jour").length)} trend="none" trendLabel={`${money(sum(by("a_jour"), "paid"), currency)} encaissés`}/>
        <Metric icon="hourglass" label="Paiement partiel" value={num(by("partiel").length)} trend="none" trendLabel={`${money(sum(by("partiel"), "balance"), currency)} restants`}/>
        <Metric icon="alert" label="Aucun paiement" value={num(by("impaye").length)} trend="none" trendLabel={`${money(sum(by("impaye"), "balance"), currency)} dus`}/>
        <Metric icon="scale" label="Reste à payer" value={money(sum(enrolled, "balance"), currency)} trend="none" trendLabel={`sur ${money(sum(enrolled, "billed"), currency)} facturés`}/>
      </div>
      <div className="yd-toolbar students">
        <SearchBox placeholder="Rechercher un élève, un parent, un matricule…" value={query} onChange={e => setQuery(e.target.value)}/>
        <label className="yd-select plain"><select aria-label="Classe" value={klass} onChange={e => setKlass(e.target.value)}><option value="">Toutes les classes</option>{d.classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select><Icon name="chevron" size={18} className="chev"/></label>
        <label className="yd-select plain"><select aria-label="Situation" value={status} onChange={e => setStatus(e.target.value)}><option value="">Toutes les situations</option>{Object.entries(FIN).map(([k, v]) => <option key={k} value={k}>{v[1]}</option>)}</select><Icon name="chevron" size={18} className="chev"/></label>
        <label className="yd-select plain"><select aria-label="Moyen de paiement" value={method} onChange={e => setMethod(e.target.value)}><option value="">Tous les moyens</option>{usedMethods.map(m => <option key={m} value={m}>{methodLabel(m)}</option>)}</select><Icon name="chevron" size={18} className="chev"/></label>
        <Button icon="download" disabled={!rows.length} onClick={() => downloadCsv("suivi-paiements.csv", [["Matricule", "Élève", "Classe", "Responsable", "Téléphone", "Total dû", "Payé", "Reste", "Situation", "Moyens utilisés", "Dernier paiement"], ...rows.map(s => [s.student_code, `${s.last_name} ${s.first_name}`, s.enrollment.classroom.name, s.guardian?.full_name, s.guardian?.phone, s.finance.billed, s.finance.paid, s.finance.balance, FIN[s.finance.status][1], s.finance.methods.map(methodLabel).join(", "), s.finance.last_payment || ""])])}>Exporter</Button>
      </div>
      <div className="yd-grid yf-track">
        <Card title="Situation par élève" count={`(${rows.length})`} icon="users">
          {rows.length === 0 ? <Empty>Aucun élève ne correspond aux filtres.</Empty> :
            <TableScroll label="Suivi des paiements"><table className="xs nowrap clickable"><thead><tr>{["Élève", "Classe", "Total dû", "Payé", "Reste", "Situation", "Moyens utilisés", "Dernier paiement", ""].map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
              <tbody>{rows.map(s => <tr key={s.id} onClick={() => onNavigate("students", "fiche", { student: s.id })}>
                <td><b>{s.last_name} {s.first_name}</b><br/><small>{s.guardian?.full_name || "—"}</small></td><td>{s.enrollment.classroom.name}</td>
                <td>{money(s.finance.billed, currency)}</td><td>{money(s.finance.paid, currency)}</td><td><b>{money(s.finance.balance, currency)}</b></td>
                <td><Status tone={FIN[s.finance.status][0]}>{FIN[s.finance.status][1]}</Status></td>
                <td>{s.finance.methods.length ? s.finance.methods.map(m => <span key={m} className="yf-chip">{methodLabel(m)}</span>) : "—"}</td>
                <td>{fmtDate(s.finance.last_payment)}</td>
                <td>{canReceive && Number(s.finance.balance) > 0 ? <button type="button" className="yf-link" onClick={e => { e.stopPropagation(); onNavigate("payments", "live", { enrollment: s.enrollment.id }); }}>Encaisser</button> : <Icon name="chevronright" size={18}/>}</td>
              </tr>)}</tbody></table></TableScroll>}
        </Card>
        <div className="yd-stack">
          <Card title="Encaissé par moyen de paiement" icon="wallet" subtitle={fin.data?.year ? `Année ${fin.data.year.name}` : ""}>
            {yearTotal === 0 ? <Empty>Aucun paiement enregistré pour cette année.</Empty> :
              <Donut size={170} values={yearMethods.map(m => m[1])} centerTop={num(yearTotal)} centerBottom={`${cur(currency)}\nencaissés`} legend={yearMethods.map(([l, v]) => [`${l} : ${money(v, currency)}`, `(${Math.round(v / yearTotal * 100)} %)`])}/>}
          </Card>
          <Card title="Par classe" icon="barchart">
            {d.classes.length === 0 ? <Empty>Aucune classe.</Empty> : <Table className="xs nowrap" headers={["Classe", "Payé", "Reste", "Impayés"]} rows={d.classes.map(c => { const l = enrolled.filter(s => s.enrollment.classroom.id === c.id); return [c.name, money(sum(l, "paid"), currency), <b>{money(sum(l, "balance"), currency)}</b>, l.filter(s => s.finance.status === "impaye").length]; })}/>}
          </Card>
        </div>
      </div>
    </>)}</Loading>
  </>;
}

/* ---------- Import Excel / CSV adaptatif (aucune écriture avant confirmation) ---------- */
const IMPORT_COLUMNS = ["Nom", "Prénoms", "DDN", "Classe", "Nom parent", "Téléphone parent"];
export function ImportStudents({ schoolId, onNavigate, tabs }) {
  const profiles = useLoad("schools/" + schoolId + "/imports/students/profiles");
  const [file, setFile] = useState(null);
  const [meta, setMeta] = useState(null);
  const [mapping, setMapping] = useState({});
  const [year, setYear] = useState("");
  const [sheet, setSheet] = useState("");
  const [headerRow, setHeaderRow] = useState(1);
  const [profileName, setProfileName] = useState("");
  const [preview, setPreview] = useState(null);
  const [finished, setFinished] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function transfer(action, selectedFile, values = {}) {
    if (!selectedFile) throw Error("Choisissez un fichier Excel ou CSV.");
    const data = new FormData();
    data.append("file", selectedFile);
    data.append("sheet", values.sheet === undefined ? sheet : values.sheet);
    data.append("header_row", String(values.headerRow === undefined ? headerRow : values.headerRow));
    if (action !== "inspect") {
      data.append("mapping", JSON.stringify(values.mapping === undefined ? mapping : values.mapping));
      data.append("year", values.year === undefined ? year : values.year);
      if (action === "commit") {
        data.append("token", values.token || "");
        if (profileName.trim()) data.append("template_name", profileName.trim());
      }
    }
    await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
    const csrf = document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1] || "";
    const response = await fetch("/api/v1/schools/" + schoolId + "/imports/students/" + action, {
      method: "POST", credentials: "same-origin", headers: {"X-CSRFToken": csrf}, body: data,
    });
    const result = await response.json();
    if (!response.ok) {
      const err = Error(result.error || "L'import a été refusé.");
      err.rows = result.rows;
      throw err;
    }
    return result;
  }
  async function analyze(selectedFile = file, newSheet = sheet, newHeader = headerRow) {
    if (!selectedFile) return;
    setBusy("inspect"); setError(""); setPreview(null); setFinished(null);
    try {
      const data = await transfer("inspect", selectedFile, {sheet:newSheet,headerRow:newHeader});
      const saved = (profiles.data?.profiles || []).find(p=>JSON.stringify(p.headers)===JSON.stringify(data.headers));
      setMeta(data);
      setSheet(data.sheet);
      setHeaderRow(data.header_row);
      setMapping(saved?.mapping || data.suggested_mapping);
      if (saved) setProfileName(saved.name);
      setYear(current => data.years.some(y=>y.id===current) ? current : (data.years[0]?.id || ""));
    } catch (e) { setError(e.message); setMeta(null); }
    finally { setBusy(""); }
  }
  async function exportData() {
    setBusy("export");setError("");
    try {
      await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
      const csrf = document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1] || "";
      const response = await fetch("/api/v1/schools/" + schoolId + "/imports/students/export", {
        method:"POST", credentials:"same-origin",
        headers:{"Content-Type":"application/json","X-CSRFToken":csrf},
        body:JSON.stringify({year:year || ""}),
      });
      if(!response.ok) {
        const result = await response.json();
        throw Error(result.error || "Export refusé.");
      }
      const download = URL.createObjectURL(await response.blob());
      const a = document.createElement("a");
      a.href = download; a.download = "yem-eleves-" + (year ? "annee" : "tous") + ".csv";
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(download);
    } catch(e) {setError(e.message);}
    finally {setBusy("");}
  }
  async function dryRun() {
    setBusy("preview"); setError(""); setPreview(null); setFinished(null);
    try { setPreview(await transfer("preview", file)); }
    catch(e) { setError(e.message); if(e.rows) setPreview({errors:e.rows.length,rows:e.rows,valid:0}); }
    finally { setBusy(""); }
  }
  async function confirm() {
    if (!preview?.token || preview.errors) return;
    setBusy("commit"); setError("");
    try {
      const result = await transfer("commit", file, {token:preview.token});
      setFinished(result); profiles.reload();
    } catch(e) { setError(e.message); if (e.rows) setPreview({...preview,errors:e.rows.filter(r=>!r.valid).length,rows:e.rows}); }
    finally { setBusy(""); }
  }
  function mapped(i, value) {
    setMapping(old => { const next = {...old}; if(value) next[String(i)]=value; else delete next[String(i)]; return next; });
    setPreview(null);setFinished(null);
  }
  const columns = meta?.headers || [];
  const bad = preview?.rows?.filter(r=>!r.valid) || [];
  const seenTargets = Object.values(mapping);
  return <>
    <PageHeader title="Importer des élèves" subtitle="Vos fichiers Excel et CSV, même avec des colonnes différentes" banner={false}
      actions={<Button icon="back" onClick={()=>onNavigate("students","live")}>Retour à la liste</Button>}/>
    {tabs}
    <div className="yd-grid yf-two">
      <Card title="1. Analyser le fichier" icon="excel">
        <p className="yd-card-sub">Jusqu'à 500 élèves et 3 Mio par import. Votre fichier reste privé : il n'est pas enregistré pour préparer l'aperçu.</p>
        <label>Fichier de l'établissement (.xlsx ou .csv)
          <input type="file" accept=".xlsx,.csv" disabled={!!busy}
            onChange={e=>{const f=e.target.files?.[0];setFile(f||null);setSheet("");setHeaderRow(1);setProfileName("");setMeta(null);setPreview(null);if(f)analyze(f,"",1);}}/>
        </label>
        {file && <p className="yd-card-sub">{file.name}</p>}
        {meta && <>
          <p className="yd-card-sub">{meta.row_count} ligne(s) détectée(s), {meta.headers.length} colonne(s).</p>
          {meta.sheets.length>1 && <label>Feuille Excel
            <select value={sheet} onChange={e=>{setSheet(e.target.value);analyze(file,e.target.value,headerRow);}} disabled={!!busy}>
              {meta.sheets.map(name=><option key={name} value={name}>{name}</option>)}
            </select>
          </label>}
          <label>Ligne contenant les titres
            <select value={headerRow} disabled={!!busy}
              onChange={e=>{const v=Number(e.target.value);setHeaderRow(v);analyze(file,sheet,v);}}>
              {Array.from({length:10},(_,i)=><option key={i+1} value={i+1}>Ligne {i+1}</option>)}
            </select>
          </label>
          <label>Année scolaire pour les inscriptions
            <select value={year} onChange={e=>{setYear(e.target.value);setPreview(null);setFinished(null);}}>
              <option value="">Sans année (élèves non affectés à une classe)</option>
              {meta.years.map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
            </select>
          </label>
          <label>Réutiliser une configuration d'import
            <select value="" onChange={e=>{
              const p=(profiles.data?.profiles||[]).find(x=>x.id===e.target.value);
              if(p){
                if(JSON.stringify(p.headers)===JSON.stringify(columns)){setMapping(p.mapping);setProfileName(p.name);setPreview(null);setFinished(null);setError("");}
                else setError("Ce modèle concerne des colonnes différentes : réajustez les correspondances manuellement.");
              }
            }}>
              <option value="">Choisir un modèle enregistré…</option>
              {(profiles.data?.profiles||[]).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
        </>}
        <Button icon="download" onClick={()=>downloadCsv("exemple-import-eleves.csv",[IMPORT_COLUMNS,["NZE","Aaron","02/03/2015","6e A","NZE Sylvie","077432108"]])}>Télécharger un exemple CSV (facultatif)</Button>
        <div style={{marginTop:16,borderTop:"1px solid #ddd",paddingTop:14}}>
          <p className="yd-card-sub"><b>Exporter vos élèves</b> : CSV privé, téléchargement autorisé aux gestionnaires de dossiers. Ne partagez pas ce fichier publiquement.</p>
          <Button icon="download" disabled={!!busy} onClick={exportData}>
            {busy==="export"?"Préparation du fichier…":"Exporter la liste des élèves en CSV"}
          </Button>
          <p className="yd-card-sub">Si une année scolaire est sélectionnée, seules ses inscriptions sont exportées ; sinon, tous les élèves de l'école.</p>
        </div>
      </Card>
      <Card title="2. Associer vos colonnes à YEM" icon="settings">
        {!meta?<p className="yd-card-sub">Sélectionnez votre fichier pour détecter automatiquement les en-têtes et proposer les correspondances.</p>:<>
          <p className="yd-card-sub">Vérifiez les suggestions. Nom et Prénom(s) sont indispensables. Sans responsable légal, le dossier sera créé comme incomplet et devra être régularisé avant tout accès parent.</p>
          <div style={{maxHeight:500,overflowY:"auto"}}>
            {columns.map((label,i)=><label key={i} style={{display:"block",marginBottom:12}}>
              <span>{label || "(Colonne sans titre)"} </span>
              <small style={{opacity:.7}}>Exemple : {meta.samples[0]?.[i] || "—"}</small>
              <select style={{display:"block",width:"100%"}} value={mapping[String(i)]||""} onChange={e=>mapped(i,e.target.value)}>
                <option value="">— Ne pas importer cette colonne —</option>
                {meta.choices.map(x=><option key={x.value} value={x.value}
                  disabled={seenTargets.includes(x.value)&&mapping[String(i)]!==x.value}>{x.label}</option>)}
              </select>
            </label>)}
          </div>
          <label>Enregistrer cette correspondance pour les prochaines années (facultatif)
            <input value={profileName} maxLength={80} placeholder="Ex. Registre des inscriptions 2026"
              onChange={e=>setProfileName(e.target.value)}/>
          </label>
          <Button primary icon="check" disabled={!!busy||!file} onClick={dryRun}>
            {busy==="preview"?"Vérification en cours…":"Vérifier les données avant import"}
          </Button>
        </>}
      </Card>
    </div>
    {!!error && <p role="alert" className="yd-form-msg" style={{color:"#b42318"}}>{error}</p>}
    {preview && <Card title="3. Prévisualisation de l'import" icon="check">
      <p className="yd-card-sub">{preview.valid || 0} ligne(s) valides, {preview.errors || 0} erreur(s), {preview.warnings || 0} dossier(s) à compléter. Aucun dossier n'a été créé.</p>
      {bad.length>0 && <p role="alert" className="yd-card-sub">Corrigez les erreurs dans le fichier, puis relancez l'analyse. L'import est entièrement bloqué tant qu'une ligne est invalide.</p>}
      <Table className="xs" headers={["Ligne","Élève","Résultat","Détail"]}
        rows={(preview.rows||[]).slice(0,80).map(r=>[r.line||"—",r.name,
          <Status tone={r.valid?"green":"red"}>{r.valid?"Prêt":"À corriger"}</Status>,
          r.error || r.warning || r.class || "Affectation sans classe"])}/>
      {(preview.rows||[]).length>80 && <p className="yd-card-sub">80 premières lignes affichées sur {preview.rows.length} ; les {bad.length} erreur(s) sont prises en compte même hors affichage.</p>}
      {!preview.errors && !finished && <Button primary icon="check" disabled={!!busy} onClick={confirm}>
        {busy==="commit"?"Enregistrement en cours…":"Confirmer l'import des "+preview.valid+" élèves"}
      </Button>}
      <p className="yd-card-sub">Les frais et paiements ne sont jamais créés automatiquement. Un réimport du même fichier validé ne crée pas de doublon.</p>
    </Card>}
    {finished && <Card title="Importation terminée" icon="check">
      <p role="status">{finished.already_imported?"Ce lot était déjà enregistré.":finished.imported+" dossier(s) créé(s) avec succès."}</p>
      <p className="yd-card-sub">{finished.notice}</p>
      <Button primary icon="users" onClick={()=>onNavigate("students","live")}>Voir la liste des élèves</Button>
    </Card>}
  </>;
}
