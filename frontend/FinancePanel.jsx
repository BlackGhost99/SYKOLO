import React, {useEffect, useState} from "react";
import AdmissionCashDesk from "./AdmissionCashDesk.jsx";

async function financeApi(url, body, method) {
  if (body !== undefined) await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
  const token = document.cookie.split("; ").find(x => x.startsWith("csrftoken="))?.split("=")[1] || "";
  const r = await fetch("/api/v1/" + url, {
    method: method || (body === undefined ? "GET" : "POST"),
    credentials: "same-origin",
    headers: body === undefined ? {} : {"Content-Type": "application/json", "X-CSRFToken": token},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.headers.get("content-type")?.includes("application/json")) throw Error("Serveur financier indisponible.");
  const data = await r.json();
  if (!r.ok) throw Error(data.error || "Opération refusée.");
  return data;
}

export default function FinancePanel({schoolId, mode = "all", workingYearId="", onWorkingYearChange}) {
  const settings = mode === "settings";
  const root = "schools/" + schoolId + "/";
  const finance = root + "finance/";
  const [years, setYears] = useState([]);
  const [classes, setClasses] = useState([]);
  const [enrollments, setEnrollments] = useState([]);
  const [students, setStudents] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [charges, setCharges] = useState([]);
  const [payments, setPayments] = useState([]);
  const [statement, setStatement] = useState(null);
  const [onlineAdmissions,setOnlineAdmissions] = useState([]);
  const [financeQuality,setFinanceQuality] = useState(null);
  const [qualityRevision,setQualityRevision] = useState(0);
  const [selectedYear, setSelectedYear] = useState(workingYearId);
  useEffect(()=>{setSelectedYear(workingYearId);setSelectedClass("");setSelectedSchedule("");setSelectedCharge("");},[workingYearId,schoolId]);
  const [selectedClass, setSelectedClass] = useState("");
  const [feeCode, setFeeCode] = useState("");
  const [feeLabel, setFeeLabel] = useState("");
  const [feeAmount, setFeeAmount] = useState("");
  const [currency, setCurrency] = useState("XAF");
  const [dueDate, setDueDate] = useState("");
  const [selectedStudent, setSelectedStudent] = useState("");
  const [selectedSchedule, setSelectedSchedule] = useState("");
  const [selectedCharge, setSelectedCharge] = useState("");
  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState("especes");
  const [payReference, setPayReference] = useState("");
  const [payDate, setPayDate] = useState("");
  const [paymentKey, setPaymentKey] = useState(() => crypto.randomUUID());
  const [cancelReason, setCancelReason] = useState("");
  const [cancelPayment, setCancelPayment] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [allowed, setAllowed] = useState(true);
  const [permissions, setPermissions] = useState([]);
  const canManage = permissions.includes("school.finance.manage");
  const canReceive = permissions.includes("school.finance.receive");
  const canReverse = permissions.includes("school.finance.reverse");
  useEffect(()=>{
    if (settings) {setFinanceQuality(null);return;}
    let active=true;
    const param=workingYearId ? "?year="+encodeURIComponent(workingYearId) : "";
    setFinanceQuality(null);
    financeApi(finance+"quality"+param).then(report=>{if(active)setFinanceQuality(report);})
      .catch(()=>{if(active)setFinanceQuality(null);});
    return ()=>{active=false;};
  },[finance,settings,workingYearId,qualityRevision]);
  useEffect(()=>{
    if(settings)return;
    let live=true;
    financeApi(root+"admission-payments").then(r=>{if(live)setOnlineAdmissions(r.payments||[]);})
      .catch(()=>{if(live)setOnlineAdmissions([]);});
    return()=>{live=false};
  },[root,settings]);
  useEffect(() => {
    let active = true;
    setPermissions([]);
    financeApi(root+"my-access").then(access => {
      if (active) setPermissions(access.permissions || []);
    }).catch(() => { if (active) setPermissions([]); });
    return () => { active = false; };
  }, [schoolId]);

  async function refresh() {
    setQualityRevision(value=>value+1);
    if (settings) {
      setSchedules((await financeApi(finance+"schedules")).schedules || []);
      return;
    }
    const [ys, cs, roster, fs, ch] = await Promise.all([
      financeApi(root+"academic/years"), financeApi(root+"academic/classes"),
      financeApi(finance+"roster"),
      financeApi(finance+"schedules"), financeApi(finance+"charges"),
    ]);
    setYears(ys.years || []);setClasses(cs.classes || []);
    setEnrollments(roster.enrollments || []);setStudents(roster.students || []);
    setSchedules(fs.schedules || []);setCharges(ch.charges || []);
  }

  useEffect(() => {
    let mounted = true;
    if (settings) {
      financeApi(finance+"schedules?choices=1").then(data => {
        if (!mounted) return;
        setYears(data.years || []);setClasses(data.classes || []);setSchedules(data.schedules || []);
      }).catch(error => {if(mounted){setAllowed(false);setMessage(error.message);}});
      return () => {mounted=false;};
    }
    Promise.all([
      financeApi(root+"academic/years"),financeApi(root+"academic/classes"),
      financeApi(finance+"roster"),
      financeApi(finance+"schedules"),financeApi(finance+"charges"),
    ]).then(([ys,cs,roster,fs,ch])=>{
      if(!mounted)return;
      setYears(ys.years||[]);setClasses(cs.classes||[]);
      setEnrollments(roster.enrollments||[]);setStudents(roster.students||[]);
      setSchedules(fs.schedules||[]);setCharges(ch.charges||[]);
    }).catch(error=>{if(mounted){setAllowed(false);setMessage(error.message);}});
    return()=>{mounted=false;};
  },[schoolId]);

  useEffect(() => {
    let alive=true;
    if(!selectedStudent){setStatement(null);return;}
    financeApi(finance+"enrollments/"+selectedStudent+"/statement")
      .then(v=>{if(alive)setStatement(v);})
      .catch(()=>{if(alive)setStatement(null);});
    return()=>{alive=false;};
  },[schoolId,selectedStudent,charges]);

  useEffect(() => {
    let alive=true;
    if(!selectedCharge){setPayments([]);return;}
    financeApi(finance+"payments?charge="+encodeURIComponent(selectedCharge))
      .then(v=>{if(alive)setPayments(v.payments||[]);})
      .catch(()=>{if(alive)setPayments([]);});
    return()=>{alive=false;};
  },[schoolId,selectedCharge,charges]);

  async function run(action) {
    setBusy(true);setMessage("");
    try {await action();await refresh();}
    catch(e){setMessage(e.message);}
    finally {setBusy(false);}
  }
  if(!allowed)return <p role="alert">{message}</p>;

  const current = charges.find(c=>c.id===selectedCharge);
  const selectedEnrollment = enrollments.find(e=>e.id===selectedStudent);
  const candidates=schedules.filter(s=>s.active && selectedEnrollment && s.year===selectedEnrollment.year &&
    (!s.classroom || s.classroom===selectedEnrollment.classroom));
  const visibleCharges=charges.filter(c=>!selectedStudent||c.enrollment===selectedStudent);

  return <section className="card" aria-label="Frais scolaires et caisse" style={{marginTop:"1rem"}}>
    <h2>{settings ? "Tarifs et échéances" : "Frais scolaires et caisse"}</h2>
    {canManage && mode !== "daily" && <>
    <h3>Configurer les frais d'une année</h3>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      await financeApi(finance+"schedules",{
        year:selectedYear, classroom:selectedClass||null, code:feeCode, label:feeLabel,
        amount:feeAmount, currency, due_date:dueDate||null,
      });
      setFeeCode("");setFeeLabel("");setFeeAmount("");setDueDate("");
      setMessage("Frais créé pour l'année scolaire choisie.");
    });}}>
      <div className="two">
        <label className="field">Année scolaire
          <select required value={selectedYear} onChange={e=>{setSelectedYear(e.target.value);onWorkingYearChange?.(e.target.value);setSelectedClass("");}}>
            <option value="">Sélectionner…</option>
            {years.filter(x=>x.active).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label className="field">Classe (facultative)
          <select value={selectedClass} onChange={e=>setSelectedClass(e.target.value)}>
            <option value="">Toutes les classes de cette année</option>
            {classes.filter(x=>x.active&&x.year===selectedYear).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label className="field">Code du frais
          <input required pattern="[a-z0-9][a-z0-9_-]*" maxLength={48} value={feeCode} onChange={e=>setFeeCode(e.target.value)} placeholder="scolarite-1" />
        </label>
        <label className="field">Libellé
          <input required maxLength={160} value={feeLabel} onChange={e=>setFeeLabel(e.target.value)} placeholder="Scolarité — échéance 1" />
        </label>
        <label className="field">Montant
          <input required inputMode="decimal" pattern="[0-9]+([.][0-9]{1,2})?" value={feeAmount} onChange={e=>setFeeAmount(e.target.value)} placeholder="25000" />
        </label>
        <label className="field">Devise (ISO)
          <input required pattern="[A-Z]{3}" maxLength={3} value={currency} onChange={e=>setCurrency(e.target.value.toUpperCase())} />
        </label>
        <label className="field">Date d'échéance facultative
          <input type="date" value={dueDate} onChange={e=>setDueDate(e.target.value)} />
        </label>
      </div>
      <button disabled={busy||!selectedYear} type="submit">Créer le tarif</button>
    </form>
    </>}
    {settings ? <div>
      <h3>Tarifs enregistrés</h3>
      {schedules.length === 0 && <p>Aucun tarif configuré.</p>}
      {schedules.map(item => <p key={item.id}><strong>{item.label}</strong> · {item.amount} {item.currency} · {
        years.find(year => year.id === item.year)?.name
      } · {classes.find(room => room.id === item.classroom)?.name || "Toutes les classes"}</p>)}
    </div> : <>
    {financeQuality && <aside className="hint" aria-label="Contrôle de qualité des écritures financières" style={{marginBottom:"1rem"}}>
      <strong>Contrôle des écritures — rapprochement requis</strong>
      <p>Les sommes affichées dans les états historiques sont des écritures enregistrées, pas une certification d'argent réellement reçu. Les simulations restent conservées pour audit.</p>
      {Object.entries(financeQuality.currencies||{}).map(([unit,categories])=>{
        const legacy=categories.legacy_cash_unverified;
        const simulated=categories.explicit_demo_payments;
        const demos=categories.explicit_demo_charges;
        return <p key={unit}>
          {unit} : {legacy?.count||0} paiement(s) sous code ancien « cash » à vérifier ({legacy?.amount||"0.00"} {unit}) ;
          {" "}{simulated?.count||0} paiement(s) explicitement fictif(s) ({simulated?.amount||"0.00"} {unit}) ;
          {" "}{demos?.count||0} ligne(s) de frais marquée(s) DÉMO ({demos?.net_amount||"0.00"} {unit}).
        </p>;
      })}
    </aside>}
    <h3>1. Admissions acceptées — relais de paiement</h3>
    <p className="hint">La candidature est examinée dans Admissions ; ici, la caisse confirme les espèces nettes après bourse. Une inscription officielle ne sera possible qu’après validation des conditions financières.</p>
    <AdmissionCashDesk schoolId={schoolId} canReceive={canReceive} onUpdated={refresh}/>
    <h4>Paiements Mobile Money des dossiers parents</h4>
    {onlineAdmissions.length===0?<p className="hint">Aucune tentative de paiement en ligne à rapprocher.</p>:
      onlineAdmissions.slice(0,20).map(p=><p key={p.id}>
        <strong>{p.amount_xaf} FCFA</strong> · {p.channel} · {p.state==="success"&&p.paid_confirmed?"Confirmé par le prestataire":p.state}
        <small> · Candidature {p.application.slice(0,8)}</small>
      </p>)}
    <h3>2. Frais scolaires après inscription définitive</h3>
    <h3>Consulter les frais d’un élève</h3>
    <label className="field">Inscription de l'élève
      <select value={selectedStudent} onChange={e=>{setSelectedStudent(e.target.value);setSelectedSchedule("");setSelectedCharge("");}}>
        <option value="">Choisir une inscription…</option>
        {enrollments.filter(e=>e.active).map(e=><option key={e.id} value={e.id}>{students.find(s=>s.id===e.student)?.last_name||"Élève"} · {classes.find(c=>c.id===e.classroom)?.name||"Classe"}</option>)}
      </select>
    </label>
    {canManage && <form onSubmit={e=>{e.preventDefault();run(async()=>{
      await financeApi(finance+"charges",{enrollment:selectedStudent,schedule:selectedSchedule});
      setSelectedSchedule("");setMessage("Frais affecté à l'inscription.");
    });}}>
      <label className="field">Tarif de l'année / classe
        <select required value={selectedSchedule} onChange={e=>setSelectedSchedule(e.target.value)}>
          <option value="">Sélectionner…</option>
          {candidates.map(s=><option key={s.id} value={s.id}>{s.label} · {s.amount} {s.currency}</option>)}
        </select>
      </label>
      <button type="submit" disabled={busy||!selectedStudent||!selectedSchedule}>Affecter ce frais</button>
    </form>
    }
    {statement&&<div>
      <h3>Relevé de situation</h3>
      {Object.entries(statement.totals).map(([currency,total])=><p key={currency}>
        {currency} — Facturé : <strong>{total.billed}</strong> · Encaissé : <strong>{total.paid}</strong> · Restant : <strong>{total.balance}</strong>
      </p>)}
    </div>}
    <h3>Frais et encaissements</h3>
    <label className="field">Frais dû
      <select value={selectedCharge} onChange={e=>{setSelectedCharge(e.target.value);setPaymentKey(crypto.randomUUID());}}>
        <option value="">Choisir un frais…</option>
        {visibleCharges.map(c=><option key={c.id} value={c.id}>{c.label} · Solde {c.balance} {c.currency}</option>)}
      </select>
    </label>
    {canReceive&&current&&<form onSubmit={e=>{e.preventDefault();run(async()=>{
      const payment=await financeApi(finance+"payments",{
        charge:selectedCharge,amount:payAmount,method:payMethod,
        reference:payReference,paid_on:payDate,idempotency_key:paymentKey,
      });
      setPaymentKey(crypto.randomUUID());setPayAmount("");setPayReference("");
      setMessage("Encaissement n° "+payment.id.slice(0,8)+" enregistré. Le reçu PDF est disponible.");
    });}}>
      <p>Solde du frais : <strong>{current.balance} {current.currency}</strong></p>
      <div className="two">
        <label className="field">Montant encaissé
          <input required inputMode="decimal" pattern="[0-9]+([.][0-9]{1,2})?" value={payAmount} onChange={e=>setPayAmount(e.target.value)} />
        </label>
        <label className="field">Méthode déclarée
          <select value={payMethod} onChange={e=>setPayMethod(e.target.value)}>
            <option value="especes">Espèces</option>
            <option value="mobile_money">Mobile Money (déjà reçu)</option>
            <option value="virement">Virement (déjà confirmé)</option>
            <option value="autre">Autre</option>
          </select>
        </label>
        <label className="field">Référence de transaction facultative
          <input maxLength={100} value={payReference} onChange={e=>setPayReference(e.target.value)} />
        </label>
        <label className="field">Date réelle de réception
          <input required type="date" value={payDate} onChange={e=>setPayDate(e.target.value)} />
        </label>
      </div>
      <button type="submit" disabled={busy||!payAmount||!payDate||current.balance==="0.00"}>Enregistrer le paiement constaté</button>
    </form>}
    {current&&<>
      <h3>Historique des encaissements</h3>
      {payments.length===0?<p className="hint">Aucun encaissement pour ce frais.</p>:payments.map(p=><p key={p.id}>
        <strong>{p.amount} {p.currency}</strong> · {p.paid_on} · {p.method} · {p.voided?"Annulé":p.evidence_class==="simulation"?"SIMULATION — aucune recette":p.evidence_class==="legacy_unverified"?"À rapprocher — paiement historique non vérifié":"Enregistré (déclaratif)"} ·
        {" "}<a href={"/api/v1/"+finance+"payments/"+p.id+"/receipt"}>Reçu PDF</a>
        {canReverse&&!p.voided&&<button type="button" disabled={busy} style={{marginLeft:"0.5rem"}} onClick={()=>{setCancelPayment(p.id);setCancelReason("");}}>Demander une annulation</button>}
      </p>)}
      {canReverse && cancelPayment && <form onSubmit={e=>{e.preventDefault();run(async()=>{
        await financeApi(finance+"payments/"+cancelPayment+"/void",{reason:cancelReason});
        setCancelPayment("");setCancelReason("");setMessage("Encaissement annulé avec trace d'audit.");
      });}}>
        <p>Une annulation comptable ne rembourse pas automatiquement de l'argent.</p>
        <label className="field">Motif précis de l'annulation
          <textarea required minLength={10} maxLength={1000} value={cancelReason} onChange={e=>setCancelReason(e.target.value)} />
        </label>
        <button disabled={busy} type="submit">Confirmer l'annulation</button>
        <button type="button" onClick={()=>setCancelPayment("")}>Ne pas annuler</button>
      </form>}
    </>}
    </>}
    {message&&<p role="status" aria-live="polite">{message}</p>}
  </section>;
}
