import React, {useEffect, useRef, useState} from "react";

const money = value => new Intl.NumberFormat("fr-GA").format(value) + " FCFA";
const methods = [["especes","Espèces"],["mobile_money","Mobile Money"],["virement","Virement déclaré"],["autre","Autre"]];
export default function PlatformSubscriptions({schoolId, api}) {
  const [years,setYears]=useState([]);
  const [year,setYear]=useState("");
  const [data,setData]=useState(null);
  const [rates,setRates]=useState({});
  const [reason,setReason]=useState("");
  const [reference,setReference]=useState("");
  const [amount,setAmount]=useState("");
  const [method,setMethod]=useState("especes");
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const pending=useRef(false);
  const path="platform/schools/"+schoolId+"/subscriptions";
  function assign(value) {
    setData(value);
    if(value.rates) setRates(Object.fromEntries(Object.entries(value.rates).map(([k,v])=>[k,v==null?"":String(v)])));
  }
  useEffect(()=>{
    let alive=true;
    api(path).then(value=>{
      if(!alive)return;
      setYears(value.years);
      setYear(value.suggested_year||value.years[0]?.id||"");
      if(!value.years.length)setLoading(false);
    }).catch(err=>{if(alive){setMessage(err.message);setLoading(false);}});
    return()=>{alive=false;};
  },[path,api]);
  useEffect(()=>{
    let alive=true;
    setData(null);setReason("");setReference("");setAmount("");setMessage("");
    if(!year)return;
    setLoading(true);
    api(path,{action:"quote",year_id:year}).then(value=>{if(alive)assign(value);})
      .catch(err=>{if(alive)setMessage(err.message);})
      .finally(()=>{if(alive)setLoading(false);});
    return()=>{alive=false;};
  },[path,year,api]);
  async function submit(action,values) {
    if(pending.current)return;
    pending.current=true;setBusy(true);setMessage("");
    try {
      assign(await api(path,{action,year_id:year,reason:reason.trim(),...values}));
      setReason("");setReference("");setAmount("");setMessage("Opération commerciale enregistrée.");
    } catch(err){setMessage(err.message);}
    finally{pending.current=false;setBusy(false);}
  }
  const sub=data?.subscription;
  const validRates=data?.counts&&Object.keys(data.counts).every(k=>rates[k]!==""&&rates[k]!==undefined
    &&Number.isSafeInteger(Number(rates[k]))&&Number(rates[k])>=0&&Number(rates[k])<=10000000);
  const total=validRates?Object.entries(data.counts).reduce((sum,[k,n])=>sum+n*Number(rates[k]),0):null;
  const validReason=reason.trim().length>0&&reason.trim().length<=240;
  return <section className="ya-box ya-form-box" aria-label="Abonnement commercial YEM">
    <h2>Abonnement annuel YEM</h2>
    <p>Facturation de la plateforme, distincte des frais de scolarité. Un seul contrat par établissement et année, ventilé par cycle. Aucun prélèvement ni suspension automatique.</p>
    <label className="ya-field"><span>Année scolaire</span><select value={year} disabled={busy} onChange={e=>setYear(e.target.value)}>
      <option value="">Choisir une année…</option>{years.map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
    </select></label>
    {loading&&<p role="status">Chargement des effectifs…</p>}
    {!loading&&!years.length&&<p>Créez une année scolaire pour préparer un abonnement.</p>}
    {data?.counts&&<form onSubmit={e=>{e.preventDefault();submit("issue",{expected_counts:data.counts,rates:Object.fromEntries(Object.entries(rates).map(([k,v])=>[k,Number(v)]))});}}>
      <h3>Devis par cycle — tarifs modifiables</h3>
      {Object.entries(data.counts).map(([k,n])=><div key={k} className="ya-form-grid">
        <label className="ya-field"><span>{data.labels[k]} · {n} élève(s) actif(s)</span>
          <input required type="number" min="0" max="10000000" step="1" value={rates[k]??""} disabled={busy} onChange={e=>setRates(old=>({...old,[k]:e.target.value}))}/></label>
        <p>{rates[k]!==""&&rates[k]!=null?money(n*Number(rates[k])):"Tarif à renseigner"}</p>
      </div>)}
      <p><strong>Total annuel : {total==null?"—":money(total)}</strong></p>
      <label className="ya-field"><span>Motif / référence du contrat</span><textarea value={reason} required rows={2} maxLength={240} onChange={e=>setReason(e.target.value)}/></label>
      <p>Les effectifs et tarifs sont figés à la création. Aucun changement des données scolaires. Vérifiez le devis avant enregistrement.</p>
      <button className="ya-btn ya-btn-primary" disabled={busy||!data.can_issue||!validRates||!validReason||!Object.keys(data.counts).length}>Enregistrer l’abonnement annuel</button>
    </form>}
    {sub&&<div>
      <h3>Contrat annuel enregistré</h3>
      {sub.lines.map(line=><p key={line.cycle}>{line.label} : {line.students} × {money(line.rate_xaf)} = <strong>{money(line.amount_xaf)}</strong></p>)}
      <p>Total : <b>{money(sub.total_xaf)}</b> · Réglé : <b>{money(sub.paid_xaf)}</b> · Solde : <b>{money(sub.balance_xaf)}</b></p>
      <label className="ya-field"><span>Motif / justificatif de l’opération</span><textarea value={reason} rows={2} maxLength={240} onChange={e=>setReason(e.target.value)}/></label>
      {sub.balance_xaf>0&&<form onSubmit={e=>{e.preventDefault();submit("payment",{reference,amount_xaf:Number(amount),method});}}>
        <div className="ya-form-grid">
          <label className="ya-field"><span>Référence de règlement</span><input required maxLength={100} value={reference} onChange={e=>setReference(e.target.value)}/></label>
          <label className="ya-field"><span>Montant reçu (FCFA)</span><input required type="number" min="1" max={sub.balance_xaf} step="1" value={amount} onChange={e=>setAmount(e.target.value)}/></label>
          <label className="ya-field"><span>Moyen de règlement déclaré</span><select value={method} onChange={e=>setMethod(e.target.value)}>{methods.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
        </div>
        <button className="ya-btn ya-btn-primary" disabled={busy||!validReason||!reference.trim()||!Number.isSafeInteger(Number(amount))||Number(amount)<=0||Number(amount)>sub.balance_xaf}>Enregistrer un règlement déjà reçu</button>
      </form>}
      <h3>Historique des règlements</h3>
      {!sub.payments.length&&<p>Aucun règlement déclaré.</p>}
      {sub.payments.map(p=><div key={p.id} className="ya-info-row"><span>{p.reference} · {money(p.amount_xaf)} · {methods.find(m=>m[0]===p.method)?.[1]||p.method}</span>
        {p.voided?<small>Annulé : {p.void_reason}</small>:<button type="button" className="ya-btn ya-btn-outline" disabled={busy||!validReason} onClick={()=>submit("void",{payment_id:p.id})}>Annuler l’écriture</button>}
      </div>)}
    </div>}
    {message&&<p role="status">{message}</p>}
  </section>;
}
