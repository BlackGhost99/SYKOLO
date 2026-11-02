import React, { useEffect, useMemo, useState } from "react";
import { Icon, Button, Status, Metric, Card, Table, InfoRow, SearchBox, Toggle, Check, Donut, LineChart, BarList, PageHeader } from "./yem-ui.jsx";

/* Écrans réels branchés sur l'API, avec la présentation des maquettes (docs/maquettes). */

async function api(path, body) {
  if (body !== undefined) await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
  const csrf = document.cookie.split("; ").find(x => x.startsWith("csrftoken="))?.split("=")[1] || "";
  const r = await fetch("/api/v1/" + path, {
    method: body === undefined ? "GET" : "POST", credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.headers.get("content-type")?.includes("application/json")) throw Error("Serveur indisponible.");
  const data = await r.json();
  if (!r.ok) throw Error(data.error || "Requête refusée.");
  return data;
}
function useData(path, deps = []) {
  const [state, setState] = useState({ data: null, error: "", loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setState(s => ({ ...s, loading: true }));
    api(path).then(data => live && setState({ data, error: "", loading: false })).catch(e => live && setState({ data: null, error: e.message, loading: false }));
    return () => { live = false; };
  }, [path, tick, ...deps]);
  return { ...state, reload: () => setTick(t => t + 1) };
}

const nf = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const num = v => nf.format(Math.round(Number(v) || 0)).replace(/ | /g, " ");
const cur = c => (!c || c === "XAF" || c === "XOF") ? "FCFA" : c;
export const fmtMoney = (v, c) => `${num(v)} ${cur(c)}`;
const pct = (now, before) => { const a = Number(now) || 0, b = Number(before) || 0; if (!b) return null; const p = (a - b) / b * 100; return `${p >= 0 ? "+" : "−"}${Math.abs(p).toFixed(1).replace(".", ",")} %`; };
const fmtDate = iso => iso ? new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" }) : "—";
const fmtTime = iso => iso ? new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : "";
const METHODS = [["airtel_money", "Airtel Money", "mobile"], ["moov_money", "Moov Money", "mobile"], ["especes", "Espèces", "cash"], ["virement", "Virement", "transfer"]];
const methodLabel = m => METHODS.find(x => x[0] === m)?.[1] || (m === "mobile_money" ? "Mobile money" : m === "autre" ? "Autre" : m);
const methodIcon = m => METHODS.find(x => x[0] === m)?.[2] || (m === "mobile_money" ? "mobile" : "coins");
const isMobileMoney = m => m === "airtel_money" || m === "moov_money" || m === "mobile_money";
const FIN = { a_jour: ["green", "À jour"], partiel: ["yellow", "Partiel"], impaye: ["red", "Impayé"], sans_frais: ["gray", "Sans frais"] };
const waLink = phone => { const d = (phone || "").replace(/[^\d]/g, ""); return d ? `https://wa.me/${d}` : ""; };
const monthLabel = ym => { const [y, m] = ym.split("-").map(Number); return new Date(y, m - 1, 1).toLocaleDateString("fr-FR", { month: "short", year: "numeric" }); };

function Loading({ state, children }) {
  if (state.loading && !state.data) return <Card title="Chargement…" icon="clock"/>;
  if (state.error) return <p role="alert" className="pc-alert">{state.error}</p>;
  return children;
}
function scale(values) {
  const max = Math.max(...values, 0);
  if (max <= 0) return { min: 0, max: 100000, step: 25000 };
  const raw = max / 4, pow = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map(f => f * pow).find(s => s >= raw);
  return { min: 0, max: Math.ceil(max / step) * step, step };
}
function Empty({ children }) { return <p className="yd-card-sub yd-empty">{children}</p>; }

/* ---------- Élèves ---------- */
export function LiveStudents({ schoolId, canManage, canReceive, onNavigate, tabs }) {
  const state = useData(`schools/${schoolId}/overview/students`);
  const [query, setQuery] = useState("");
  const [klass, setKlass] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState(null);
  const d = state.data;
  const rows = useMemo(() => (d?.students || []).filter(s => s.active).filter(s => {
    const text = `${s.last_name} ${s.first_name} ${s.student_code} ${s.guardian?.full_name || ""}`.toLowerCase();
    return text.includes(query.toLowerCase()) && (!klass || s.enrollment?.classroom.id === klass)
      && (!status || (status === "non_inscrit" ? !s.enrollment : s.finance?.status === status));
  }), [d, query, klass, status]);
  const current = rows.find(r => r.id === selected) || rows[0];
  const m = d?.metrics;
  return <>
    <PageHeader title="Gestion des élèves" subtitle="Inscriptions, classes, responsables et suivi administratif"/>
    {tabs}
    <Loading state={state}>{d && <>
      <div className="yd-toolbar students">
        <SearchBox placeholder="Rechercher un élève (nom, prénom, matricule...)" value={query} onChange={e => setQuery(e.target.value)}/>
        <label className="yd-select plain"><select aria-label="Classe" value={klass} onChange={e => setKlass(e.target.value)}><option value="">Toutes les classes</option>{d.classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select><Icon name="chevron" size={18} className="chev"/></label>
        <label className="yd-select plain"><select aria-label="Statut" value={status} onChange={e => setStatus(e.target.value)}><option value="">Tous les statuts</option>{d.finance_visible && Object.entries(FIN).map(([k, v]) => <option key={k} value={k}>{v[1]}</option>)}<option value="non_inscrit">Non inscrit cette année</option></select><Icon name="chevron" size={18} className="chev"/></label>
        {canManage && <Button primary icon="adduser" onClick={() => onNavigate("students", "students")}>Nouvel élève</Button>}
      </div>
      <div className="yd-metrics four">
        <Metric icon="users" label="Élèves actifs" value={num(m.active)} trend="none" trendValue={num(m.enrolled)} trendLabel={`inscrits en ${d.year?.name || "cours"}`}/>
        <Metric icon="cap" label="Nouveaux inscrits" value={num(m.new_30d)} trend={m.new_30d >= m.new_prev_30d ? "up" : "down"} trendValue={pct(m.new_30d, m.new_prev_30d) || `${m.new_prev_30d}`} trendLabel="vs. 30 jours précédents"/>
        <Metric icon="alert" label="Dossiers incomplets" value={num(m.incomplete)} trend="none" trendLabel="sans responsable ou sans classe"/>
        <Metric icon="whatsapp" label="Parents sans numéro WhatsApp" value={num(m.missing_phone)} trend="none" trendLabel="responsables sans téléphone"/>
      </div>
      <div className="yd-grid students-grid">
        <Card title="Liste des élèves" count={`(${rows.length})`} icon="users">
          {rows.length === 0 ? <Empty>Aucun élève ne correspond. Créez une fiche depuis « Nouvel élève ».</Empty> :
            <div className="yd-table-wrap"><table className="clickable nowrap dense"><thead><tr>{["#", "Élève", "Classe", "Parent / Tuteur", "Téléphone", <>Situation<br/>financière</>, "Statut", "Actions"].map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
              <tbody>{rows.map((s, i) => { const f = s.finance && FIN[s.finance.status]; return <tr key={s.id} className={current?.id === s.id ? "selected" : ""} onClick={() => setSelected(s.id)}>
                <td>{i + 1}</td><td><b>{s.last_name} {s.first_name}</b></td><td>{s.enrollment?.classroom.name || "—"}</td><td>{s.guardian?.full_name || "—"}</td><td>{s.guardian?.phone || "—"}</td>
                <td>{f ? f[1] : "—"}</td><td>{s.enrollment ? (f ? <Status tone={f[0]}>{f[1]}</Status> : <Status>Inscrit</Status>) : <Status tone="gray">Non inscrit</Status>}</td>
                <td><button type="button" className="yd-dots" aria-label="Ouvrir la fiche" onClick={e => { e.stopPropagation(); onNavigate("students", "students"); }}><Icon name="dots" size={22}/></button></td></tr>; })}</tbody></table></div>}
        </Card>
        {current ? <Card title="Aperçu de l’élève" icon="user" className="student-preview">
          <div className="yd-person"><div className="yd-avatar big"><Icon name="user" size={46} strokeWidth={0} className="filled"/></div><div><h3>{current.last_name} {current.first_name}</h3><span>Classe : {current.enrollment?.classroom.name || "non inscrit"}</span><span>Matricule : {current.student_code}</span></div></div>
          <div className="yd-info-list">
            <InfoRow icon="user" k="Parent / Tuteur" v={current.guardian?.full_name || "—"}/>
            <InfoRow icon="whatsapp" k="Téléphone" v={current.guardian?.phone || "—"} vIcon={current.guardian?.phone ? "whatsapp" : undefined}/>
            {current.finance && <><InfoRow icon="coins" k="Total annuel" v={fmtMoney(current.finance.billed, d.currency)}/>
              <InfoRow icon="wallet" k="Montant payé" v={fmtMoney(current.finance.paid, d.currency)}/>
              <InfoRow icon="scale" k="Reste à payer" v={fmtMoney(current.finance.balance, d.currency)} highlight/></>}
          </div>
          <div className="yd-btn-stack">
            <Button primary icon="file" onClick={() => onNavigate("students", "students")}>Voir la fiche</Button>
            {canReceive && current.enrollment && <Button icon="coins" onClick={() => onNavigate("payments", "live", { enrollment: current.enrollment.id })}>Encaisser</Button>}
            {waLink(current.guardian?.phone) ? <a className="yd-btn" href={waLink(current.guardian.phone)} target="_blank" rel="noreferrer"><Icon name="whatsapp" size={20}/><span>Contacter le parent</span></a> : <Button icon="whatsapp" disabled>Contacter le parent</Button>}
          </div>
        </Card> : <Card title="Aperçu de l’élève" icon="user"><Empty>Sélectionnez un élève dans la liste.</Empty></Card>}
      </div>
    </>}</Loading>
  </>;
}

/* ---------- Paiements ---------- */
function newKey() { return (crypto.randomUUID && crypto.randomUUID()) || "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c => (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)); }

export function LivePayments({ schoolId, canReceive, params, tabs }) {
  const fin = useData(`schools/${schoolId}/overview/finance`);
  const roster = useData(`schools/${schoolId}/overview/students`);
  const [enrollment, setEnrollment] = useState(params?.enrollment || "");
  const [charges, setCharges] = useState([]);
  const [picked, setPicked] = useState({});
  const [method, setMethod] = useState("airtel_money");
  const [partial, setPartial] = useState(false);
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const enrolled = (roster.data?.students || []).filter(s => s.active && s.enrollment);
  const student = enrolled.find(s => s.enrollment.id === enrollment);
  useEffect(() => {
    if (!enrollment) { setCharges([]); return; }
    let live = true;
    api(`schools/${schoolId}/finance/charges?enrollment=${enrollment}`).then(r => { if (!live) return; const open = r.charges.filter(c => Number(c.balance) > 0); setCharges(open); setPicked(open.length ? { [open[0].id]: true } : {}); }).catch(e => live && setMessage(e.message));
    return () => { live = false; };
  }, [schoolId, enrollment, fin.data]);
  const selected = charges.filter(c => picked[c.id]);
  const due = selected.reduce((a, c) => a + Number(c.balance), 0);
  const entered = partial ? Number(String(amount).replace(/\s/g, "").replace(",", ".")) || 0 : due;
  const remaining = charges.reduce((a, c) => a + Number(c.balance), 0) - entered;
  const currency = charges[0]?.currency || fin.data?.currency;
  async function submit() {
    if (!entered || entered <= 0 || entered > due + 0.001) { setMessage("Montant invalide : il doit être positif et ne pas dépasser le total sélectionné."); return; }
    setBusy(true); setMessage("");
    try {
      let left = entered;
      const paidOn = fin.data?.today.date || new Date().toISOString().slice(0, 10);
      for (const c of selected) {
        if (left <= 0) break;
        const part = Math.min(left, Number(c.balance));
        await api(`schools/${schoolId}/finance/payments`, { charge: c.id, amount: part.toFixed(2), method, reference: "", paid_on: paidOn, idempotency_key: newKey() });
        left -= part;
      }
      setMessage(`Paiement de ${fmtMoney(entered, currency)} enregistré.`);
      setAmount(""); setPartial(false); fin.reload();
    } catch (e) { setMessage(e.message); } finally { setBusy(false); }
  }
  const d = fin.data;
  const byMethod = d?.today.by_method || {};
  const cash = Number(byMethod.especes || 0), mobile = Object.entries(byMethod).filter(([k]) => isMobileMoney(k)).reduce((a, [, v]) => a + Number(v), 0);
  const total = Number(d?.today.total || 0);
  const share = v => total ? `${(v / total * 100).toFixed(1).replace(".", ",")} %` : "0,0 %";
  const donutRows = METHODS.map(([k, l]) => [l, Number(byMethod[k] || 0)]);
  return <>
    <PageHeader title="Encaissements et caisse journalière" subtitle="Suivi des paiements, reçus et méthodes d’encaissement" badge="Économe" badgeIcon="coins"/>
    {tabs}
    <Loading state={fin}>{d && <>
      <div className="yd-metrics four">
        <Metric icon="coins" label="Encaissé aujourd’hui" value={fmtMoney(d.today.total, d.currency)} trend={total >= Number(d.yesterday.total) ? "up" : "down"} trendValue={pct(d.today.total, d.yesterday.total) || ""} trendLabel={`vs. hier (${fmtMoney(d.yesterday.total, d.currency)})`}/>
        <Metric icon="file" label="Nombre de paiements" value={num(d.today.count)} trend={d.today.count >= d.yesterday.count ? "up" : "down"} trendValue={pct(d.today.count, d.yesterday.count) || ""} trendLabel={`vs. hier (${d.yesterday.count})`}/>
        <Metric icon="cash" label="Espèces" value={fmtMoney(cash, d.currency)} trend="none" trendValue={share(cash)} trendLabel="du total"/>
        <Metric icon="mobile" label="Mobile money" value={fmtMoney(mobile, d.currency)} trend="none" trendValue={share(mobile)} trendLabel="du total"/>
      </div>
      <div className="yd-grid payments-grid">
        <Card title="Nouvel encaissement" icon="card" className="payment-form">
          {!canReceive ? <Empty>Votre rôle ne permet pas d’enregistrer des encaissements.</Empty> : <>
            <label className="yd-label" htmlFor="pay-student">Élève <i>*</i></label>
            <div className="yd-input"><Icon name="user" size={20}/><select id="pay-student" value={enrollment} onChange={e => { setEnrollment(e.target.value); setMessage(""); }}><option value="">Choisir un élève…</option>{enrolled.map(s => <option key={s.enrollment.id} value={s.enrollment.id}>{s.last_name} {s.first_name} — {s.enrollment.classroom.name}</option>)}</select></div>
            <label className="yd-label">Parent <i>*</i></label>
            <div className="yd-input"><Icon name="users" size={20}/><span>{student?.guardian ? `${student.guardian.full_name}${student.guardian.relationship ? ` (${student.guardian.relationship})` : ""}` : "—"}</span>{student?.guardian?.phone && <em><Icon name="phone" size={16}/>{student.guardian.phone}</em>}</div>
            <label className="yd-label">Impayés sélectionnés <i>*</i></label>
            <div className="yd-debts">{charges.length === 0 ? <p className="yd-card-sub yd-empty">{enrollment ? "Aucun frais restant dû pour cet élève." : "Choisissez d’abord un élève."}</p> : charges.map(c => <button type="button" key={c.id} className={picked[c.id] ? "active" : ""} onClick={() => setPicked(p => ({ ...p, [c.id]: !p[c.id] }))}><Check on={!!picked[c.id]}/><span>{c.label}{c.due_date ? ` · échéance ${fmtDate(c.due_date)}` : ""}</span><b>{fmtMoney(c.balance, c.currency)}</b></button>)}</div>
            <label className="yd-label">Mode de paiement <i>*</i></label>
            <div className="yd-paymodes">{METHODS.map(([k, l, ic]) => <Button key={k} primary={method === k} icon={ic} onClick={() => setMethod(k)}>{l}</Button>)}</div>
            <label className="yd-label" htmlFor="pay-amount">Montant saisi <i>*</i></label>
            <div className="yd-amount-row"><div className="yd-amount"><input id="pay-amount" inputMode="decimal" disabled={!partial} value={partial ? amount : num(due)} onChange={e => setAmount(e.target.value)}/><em>{cur(currency)}</em></div><button type="button" className="yd-toggle-btn" aria-pressed={partial} onClick={() => { setPartial(p => !p); setAmount(""); }}><Toggle on={partial}/>Paiement partiel</button></div>
            <div className="yd-balance"><span><Icon name="coins" size={22}/>Solde après paiement</span><strong>{fmtMoney(Math.max(remaining, 0), currency)}</strong></div>
            {message && <p role="status" className="yd-form-msg">{message}</p>}
            <Button primary icon="check" className="wide" disabled={busy || !selected.length || entered <= 0} onClick={submit}>Valider le paiement</Button>
          </>}
        </Card>
        <div className="yd-stack">
          <Card title="Derniers paiements du jour" icon="receipt">
            {d.today.payments.length === 0 ? <Empty>Aucun paiement enregistré aujourd’hui.</Empty> :
              <Table className="nowrap xs" headers={["# Reçu", "Élève", "Classe", "Montant", "Mode", "Heure"]} rows={d.today.payments.map(p => [<a href={`/api/v1/schools/${schoolId}/finance/payments/${p.id}/receipt`} target="_blank" rel="noreferrer" className="yd-link">R-{p.id.slice(0, 8).toUpperCase()}</a>, p.student, p.classroom, fmtMoney(p.amount, d.currency), <span className="yd-mode"><Icon name={methodIcon(p.method)} size={18}/>{methodLabel(p.method)}</span>, fmtTime(p.recorded_at)])}/>}
          </Card>
          <Card title="Caisse du jour" icon="layers">
            <div className="cash-row">
              <Donut size={180} values={donutRows.map(r => r[1])} centerTop={num(total)} centerBottom={`${cur(d.currency)}\nencaissés`} legend={donutRows.map(([l, v]) => [`${l} : ${fmtMoney(v, d.currency)}`, `(${share(v)})`])}/>
              <div className="cash-total"><div><span>Total encaissé</span><strong>{fmtMoney(total, d.currency)}</strong></div></div>
            </div>
          </Card>
        </div>
      </div>
    </>}</Loading>
  </>;
}

/* ---------- Impayés & relances ---------- */
export function LiveArrears({ schoolId, schoolName, tabs }) {
  const fin = useData(`schools/${schoolId}/overview/finance`);
  const [selected, setSelected] = useState(0);
  const [channel, setChannel] = useState("WhatsApp");
  const d = fin.data;
  const a = d?.arrears[selected] || d?.arrears[0];
  const text = a ? `Bonjour ${a.guardian || "Madame, Monsieur"},\n\nNous vous rappelons que les frais de scolarité de votre enfant ${a.student} (${a.classroom}) s’élèvent à ${fmtMoney(a.amount_due, d.currency)}, échus le ${fmtDate(a.due_date)}.\n\nNous vous invitons à régulariser cette situation dans les meilleurs délais.\n\n${schoolName} vous remercie pour votre diligence.` : "";
  const digits = (a?.phone || "").replace(/[^\d+]/g, "");
  const sendHref = !a ? "" : channel === "WhatsApp" ? (waLink(a.phone) ? `${waLink(a.phone)}?text=${encodeURIComponent(text)}` : "") : channel === "SMS" ? (digits ? `sms:${digits}?body=${encodeURIComponent(text)}` : "") : `mailto:?subject=${encodeURIComponent("Rappel de frais de scolarité")}&body=${encodeURIComponent(text)}`;
  function exportCsv() {
    const lines = [["Élève", "Classe", "Responsable", "Téléphone", "Échéance", "Montant dû", "Dernier paiement"], ...d.arrears.map(x => [x.student, x.classroom, x.guardian, x.phone, x.due_date || "", x.amount_due, x.last_payment || ""])];
    const blob = new Blob(["﻿" + lines.map(l => l.map(v => `"${String(v).replace(/"/g, '""')}"`).join(";")).join("\n")], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "impayes.csv"; link.click(); URL.revokeObjectURL(link.href);
  }
  return <>
    <PageHeader banner={false} title="Impayés & relances" subtitle="Suivi des échéances, retards et messages aux familles" actions={d && <>
      {sendHref ? <a className="yd-btn primary" href={sendHref} target="_blank" rel="noreferrer"><Icon name="send" size={20}/><span>Envoyer la relance</span></a> : <Button primary icon="send" disabled>Envoyer la relance</Button>}
      <Button icon="whatsapp" onClick={() => setChannel("WhatsApp")}>WhatsApp</Button><Button icon="message" onClick={() => setChannel("SMS")}>SMS</Button><Button icon="download" disabled={!d.arrears.length} onClick={exportCsv}>Exporter</Button></>}/>
    {tabs}
    <Loading state={fin}>{d && <div className="yd-grid arrears-layout">
      <div className="yd-stack">
        <div className="yd-metrics four">
          <Metric icon="coins" label="Total restant dû" value={fmtMoney(d.outstanding, d.currency)} trend="none" trendLabel="toutes échéances"/>
          <Metric icon="alert" label="Familles en retard" value={num(d.families_late)} trend="none" trendLabel="échéance dépassée"/>
          <Metric icon="hourglass" label="Montant échu" value={fmtMoney(d.overdue_total, d.currency)} trend="none" trendLabel="à recouvrer"/>
          <Metric icon="card" label="Encaissé ce mois" value={fmtMoney(d.month.total, d.currency)} trend={Number(d.month.total) >= Number(d.month.previous) ? "up" : "down"} trendValue={pct(d.month.total, d.month.previous) || ""} trendLabel="vs. mois précédent"/>
        </div>
        <Card title="Liste des familles en impayé" count={`(${d.families_late})`} icon="users">
          {d.arrears.length === 0 ? <Empty>Aucune famille en retard de paiement.</Empty> :
            <div className="yd-table-wrap"><table className="xs clickable"><thead><tr>{["", "Élève", "Classe", "Responsable", "Échéance", "Montant dû", <>Dernier<br/>paiement</>, "Canal", "Statut"].map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
              <tbody>{d.arrears.map((x, i) => <tr key={x.enrollment} className={a === x ? "selected" : ""} onClick={() => setSelected(i)}><td>{i + 1}</td><td className="nowrap"><b>{x.student}</b></td><td>{x.classroom}</td><td>{x.guardian || "—"}</td><td className="nowrap">{fmtDate(x.due_date)}</td><td className="nowrap"><b>{fmtMoney(x.amount_due, d.currency)}</b></td><td className="nowrap">{fmtDate(x.last_payment)}</td>
                <td>{waLink(x.phone) ? <Icon name="whatsapp" size={22} className="channel"/> : "—"}</td><td><Status tone={x.last_payment ? "yellow" : "red"}>{x.last_payment ? "À relancer" : "En retard"}</Status></td></tr>)}</tbody></table></div>}
        </Card>
      </div>
      <div className="yd-stack">
        <Card title="Aperçu du message" icon="message">
          <div className="yd-channel-tabs" role="tablist">{[["WhatsApp", "whatsapp"], ["SMS", "message"], ["Email", "mail"]].map(([c, ic]) => <button type="button" role="tab" aria-selected={channel === c} key={c} className={channel === c ? "active" : ""} onClick={() => setChannel(c)}><Icon name={ic} size={18}/>{c}</button>)}</div>
          {a ? <div className="yd-message-preview">{text.split("\n\n").map((p, i) => <p key={i}>{p}</p>)}<small>{a.phone || "Aucun numéro enregistré"}</small></div> : <Empty>Aucune relance à préparer.</Empty>}
        </Card>
        <Card title="Répartition des impayés par classe" icon="barchart">
          {d.arrears_by_class.length ? <BarList items={d.arrears_by_class.map(c => [c.classroom, c.families])}/> : <Empty>Aucun impayé.</Empty>}
        </Card>
      </div>
    </div>}</Loading>
  </>;
}

/* ---------- Tableau de bord ---------- */
export function LiveDashboard({ schoolId, schoolName, roleLabel, onNavigate, canReceive, tabs }) {
  const fin = useData(`schools/${schoolId}/overview/finance`);
  const d = fin.data;
  const monthly = d?.monthly.map(m => Number(m.total)) || [];
  const sc = scale(monthly);
  const byMethod = d?.month.by_method || {};
  const methods = METHODS.map(([k, l]) => [l, Number(byMethod[k] || 0)]);
  const monthTotal = Number(d?.month.total || 0);
  const share = v => monthTotal ? `${Math.round(v / monthTotal * 100)} %` : "0 %";
  return <>
    <PageHeader title="Tableau de bord" subtitle={`Vue de pilotage de ${schoolName} — ${new Date().toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}`} badge={roleLabel || "Membre"} badgeIcon="crown"/>
    {tabs}
    <Loading state={fin}>{d && <>
      <div className="yd-metrics five">
        <Metric icon="coins" label="Encaissé ce mois" value={fmtMoney(d.month.total, d.currency)} trend={monthTotal >= Number(d.month.previous) ? "up" : "down"} trendValue={pct(d.month.total, d.month.previous) || ""} trendLabel="vs. mois précédent"/>
        <Metric icon="file" label="Restant dû" value={fmtMoney(d.outstanding, d.currency)} trend="none" trendLabel="toutes échéances"/>
        <Metric icon="users" label="Élèves actifs" value={num(d.active_students)} trend="none" trendLabel={d.year?.name || ""}/>
        <Metric icon="alert" label="Familles en retard" value={num(d.families_late)} trend="none" trendLabel={`${fmtMoney(d.overdue_total, d.currency)} échus`}/>
        <Metric icon="receipt" label="Paiements aujourd’hui" value={num(d.today.count)} trend="none" trendLabel={fmtMoney(d.today.total, d.currency)}/>
      </div>
      <div className="yd-grid dash-main">
        <Card title="Évolution des encaissements" icon="barchart" subtitle={`Montants encaissés (${cur(d.currency)}) sur les 6 derniers mois`}>
          <LineChart points={monthly} labels={d.monthly.map(m => monthLabel(m.month))} min={sc.min} max={sc.max} step={sc.step}/>
        </Card>
        <Card title="Répartition des moyens de paiement" icon="wallet">
          <Donut size={160} values={methods.map(m => m[1])} centerTop={num(monthTotal)} centerBottom={`${cur(d.currency)}\nencaissés`} legend={methods.map(([l, v]) => [`${l} : ${share(v)}`, `(${fmtMoney(v, d.currency)})`])}/>
        </Card>
        <Card title="Actions rapides" icon="bolt" className="quick">
          {canReceive && <Button primary icon="card" onClick={() => onNavigate("payments", "live")}>Nouvel encaissement</Button>}
          <Button icon="mail" onClick={() => onNavigate("arrears")}>Préparer les relances</Button>
          <Button icon="users" onClick={() => onNavigate("students")}>Voir les élèves</Button>
          <Button icon="file" onClick={() => onNavigate("bulletins")}>Générer les bulletins</Button>
        </Card>
      </div>
      <div className="yd-grid dash-bottom">
        <Card title="Retardataires prioritaires" icon="users">
          {d.arrears.length ? <Table align={{ 1: "nowrap", 3: "nowrap" }} headers={["#", "Élève", "Classe", "Montant dû", "Statut"]} rows={d.arrears.slice(0, 5).map((a, i) => [i + 1, a.student, a.classroom, fmtMoney(a.amount_due, d.currency), <Status tone={a.last_payment ? "yellow" : "red"}>{a.last_payment ? "À relancer" : "En retard"}</Status>])}/> : <Empty>Aucune famille en retard.</Empty>}
        </Card>
        <Card title="Derniers paiements du jour" icon="receipt">
          {d.today.payments.length ? <Table className="nowrap" headers={["Élève", "Classe", "Montant", "Mode", "Heure"]} rows={d.today.payments.slice(0, 5).map(p => [p.student, p.classroom, fmtMoney(p.amount, d.currency), methodLabel(p.method), fmtTime(p.recorded_at)])}/> : <Empty>Aucun paiement enregistré aujourd’hui.</Empty>}
        </Card>
      </div>
    </>}</Loading>
  </>;
}
