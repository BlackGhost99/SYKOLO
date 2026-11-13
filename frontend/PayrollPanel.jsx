import React,{useCallback,useEffect,useState} from "react";
import {Button,Card,Status,Table} from "./yem-ui.jsx";

const API="/api/v1/";
const METHODS=[["especes","Espèces déclarées"],["virement","Virement déclaré"],["mobile_money","Mobile Money déclaré"],["autre","Autre règlement déclaré"]];
const BASES=[["monthly","Mensuelle"],["hourly","Heures / vacations"],["session","Séances"],["fixed","Forfait / prime"]];
const today=()=>new Date().toLocaleDateString("en-CA");
const currentMonth=()=>today().slice(0,7);
const fmt=(amount,currency)=>new Intl.NumberFormat("fr-FR",{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(amount||0))+" "+currency;

async function request(path,method="GET",payload){
  if(method!=="GET"){
    const tokenReady=await fetch(API+"auth/csrf",{credentials:"same-origin"});
    if(!tokenReady.ok)throw Error("Session expirée.");
  }
  const token=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const res=await fetch(API+path,{
    method,credentials:"same-origin",
    headers:payload===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},
    body:payload===undefined?undefined:JSON.stringify(payload),
  });
  const data=await res.json().catch(()=>({error:"Réponse du service indisponible."}));
  if(!res.ok)throw Error(data.error||"Opération refusée.");
  return data;
}

export default function PayrollPanel({schoolId,workingYearId="",canManage=false,canApprove=false,canPay=false,canReverse=false}){
  const root="schools/"+schoolId+"/payroll/";
  const [staff,setStaff]=useState([]);
  const [runs,setRuns]=useState([]);
  const [selected,setSelected]=useState("");
  const [period,setPeriod]=useState(currentMonth());
  const [basis,setBasis]=useState("monthly");
  const [gross,setGross]=useState("");
  const [deductions,setDeductions]=useState("0");
  const [currency,setCurrency]=useState("XAF");
  const [note,setNote]=useState("");
  const [detail,setDetail]=useState(null);
  const [payment,setPayment]=useState({amount:"",method:"especes",reference:"",paid_on:today()});
  const [paymentKey,setPaymentKey]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");

  const refresh=useCallback(async()=>{
    const [users,payroll]=await Promise.all([
      request(root+"staff"),
      request(root+"runs"+(workingYearId?"?year="+encodeURIComponent(workingYearId):"")),
    ]);
    setStaff(users.staff||[]);
    setRuns(payroll.runs||[]);
  },[root,workingYearId]);
  useEffect(()=>{
    let active=true;
    setError("");setMessage("");setDetail(null);
    refresh().catch(err=>{if(active)setError(err.message);});
    return()=>{active=false;};
  },[refresh]);
  async function operation(action,success){
    if(busy)return;
    setBusy(true);setError("");setMessage("");
    try{
      const value=await action();
      await refresh();
      setMessage(success);
      return value;
    }catch(err){setError(err.message);return null;}
    finally{setBusy(false);}
  }
  async function prepare(event){
    event.preventDefault();
    if(!selected||!workingYearId){setError("Choisir un collaborateur et une année scolaire.");return;}
    const saved=await operation(()=>request(root+"runs","POST",{
      staff:selected,year:workingYearId,period:period+"-01",
      basis,gross_amount:gross,deductions,currency,note,
    }),"Rémunération préparée. Un autre compte doit la valider avant règlement.");
    if(saved){setGross("");setDeductions("0");setNote("");}
  }
  async function openRun(runId){
    setError("");setMessage("");
    try{setDetail(await request(root+"runs/"+runId));}
    catch(err){setError(err.message);}
  }
  async function approve(row){
    await operation(()=>request(root+"runs/"+row.id+"/approve","POST",{revision:row.revision}),
      "Rémunération validée par le contrôleur.");
    setDetail(null);
  }
  async function markPaid(event){
    event.preventDefault();
    if(!detail)return;
    const key=paymentKey || crypto.randomUUID();
    setPaymentKey(key);
    const saved=await operation(()=>request(root+"runs/"+detail.run.id+"/payments","POST",{
      ...payment,idempotency_key:key,
    }),"Versement déclaré et enregistré. Vérifier le justificatif physique.");
    if(saved){
      setPaymentKey("");setPayment({...payment,amount:"",reference:""});
      await openRun(detail.run.id);
    }
  }
  async function reverse(item){
    const reason=window.prompt("Motif de l'annulation (10 caractères minimum) :", "");
    if(!reason)return;
    const saved=await operation(()=>request(root+"payments/"+item.id+"/void","POST",{reason}),
      "Versement annulé sous contrôle indépendant.");
    if(saved&&detail)await openRun(detail.run.id);
  }
  const filtered=selected?runs.filter(x=>x.staff===selected):runs;
  const selectedName=staff.find(x=>x.id===selected)?.name;
  const grossTotal=filtered.reduce((sum,x)=>sum+Number(x.net_amount),0);
  const paidTotal=filtered.reduce((sum,x)=>sum+Number(x.paid),0);
  const balances=filtered.reduce((sum,x)=>sum+Number(x.balance),0);
  const statusTone=value=>value==="paid"?"green":value==="approved"?"blue":value==="partially_paid"?"orange":"gray";
  const statusText={draft:"À valider",approved:"Validée",partially_paid:"Partiellement réglée",paid:"Réglée"};

  return <section aria-label="Rémunérations du personnel">
    <Card title="Rémunérations du personnel — accès confidentiel" icon="shield"
      subtitle="Rémunérations déclarées dans YEM, distinctes des frais de scolarité et de la caisse d'inscription.">
      <p className="hint">Ces écritures ne réalisent aucun virement ou débit Mobile Money. Un versement ne devient déclaré payé qu'après un enregistrement justifié par la personne habilitée.</p>
      {error&&<p role="alert">{error}</p>}
      {message&&<p role="status">{message}</p>}
      <label className="field">Collaborateur
        <select value={selected} onChange={e=>{setSelected(e.target.value);setDetail(null);}}>
          <option value="">Tous les collaborateurs</option>
          {staff.map(x=><option value={x.id} key={x.id}>{x.name} · {x.position}{x.active?"":" (archivé)"}</option>)}
        </select>
      </label>
      <p><strong>Année scolaire :</strong> {workingYearId?"Année sélectionnée dans la barre supérieure":"Sélectionnez une année scolaire pour préparer une rémunération"}</p>
      <div className="two">
        <p><strong>Net prévu</strong><span style={{display:"block"}}>{fmt(grossTotal,currency)}*</span></p>
        <p><strong>Versé / Reste</strong><span style={{display:"block"}}>{fmt(paidTotal,currency)} / {fmt(balances,currency)}*</span></p>
      </div>
      <p className="hint">*Synthèse indicative dans la devise affichée ; en présence de plusieurs devises, consultez chaque ligne séparément.</p>
      {!filtered.length?<p>Aucune rémunération saisie pour ce filtre.</p>:<Table headers={["Collaborateur","Période","Net prévu","Déjà déclaré","Reste","Statut","Fiche"]} rows={filtered.map(run=>[
        run.staff_name,run.period.slice(0,7),fmt(run.net_amount,run.currency),fmt(run.paid,run.currency),
        fmt(run.balance,run.currency),
        <Status tone={statusTone(run.status)}>{statusText[run.status]||run.status}</Status>,
        <Button className="small" onClick={()=>openRun(run.id)}>Détail</Button>,
      ])}/>}
    </Card>

    {canManage&&<Card title="Préparer la rémunération" icon="idcard">
      <p className="hint">La paie sera créée comme brouillon. Une autre personne devra la valider.</p>
      <form onSubmit={prepare}>
        <div className="two">
          <label className="field">Mois de paie<input type="month" required value={period} onChange={e=>setPeriod(e.target.value)}/></label>
          <label className="field">Type de rémunération<select value={basis} onChange={e=>setBasis(e.target.value)}>
            {BASES.map(([v,label])=><option key={v} value={v}>{label}</option>)}
          </select></label>
          <label className="field">Montant brut<input required inputMode="decimal" pattern="[0-9]+(\\.[0-9]{1,2})?" value={gross} onChange={e=>setGross(e.target.value)}/></label>
          <label className="field">Retenues<input required inputMode="decimal" pattern="[0-9]+(\\.[0-9]{1,2})?" value={deductions} onChange={e=>setDeductions(e.target.value)}/></label>
          <label className="field">Devise<input required maxLength={3} value={currency} onChange={e=>setCurrency(e.target.value.toUpperCase())}/></label>
        </div>
        <label className="field">Observation (facultative)<input maxLength={240} value={note} onChange={e=>setNote(e.target.value)}/></label>
        <Button primary disabled={busy||!selected||!workingYearId}>Préparer la paie de {selectedName||"l'employé"}</Button>
      </form>
    </Card>}

    {detail&&<Card title={"Dossier de paie — "+detail.run.staff_name} icon="idcard">
      <div className="actions"><Button onClick={()=>setDetail(null)}>Fermer</Button></div>
      <p><strong>Échéance :</strong> {detail.run.period.slice(0,7)} · <strong>Statut :</strong> {statusText[detail.run.status]||detail.run.status}</p>
      <p>Brut : <strong>{fmt(detail.run.gross_amount,detail.run.currency)}</strong> · Retenues : {fmt(detail.run.deductions,detail.run.currency)}</p>
      <p>Net dû : <strong>{fmt(detail.run.net_amount,detail.run.currency)}</strong> · Déclaré réglé : {fmt(detail.run.paid,detail.run.currency)} · Reste : <strong>{fmt(detail.run.balance,detail.run.currency)}</strong></p>
      {canApprove&&detail.run.status==="draft"&&<Button disabled={busy} onClick={()=>approve(detail.run)}>Valider cette paie</Button>}
      {canPay&&["approved","partially_paid"].includes(detail.run.status)&&<form onSubmit={markPaid}>
        <p className="hint">Le caissier enregistre un versement déjà effectué. Conservez la preuve hors de la fiche professionnelle.</p>
        <div className="two">
          <label className="field">Montant<input required inputMode="decimal" value={payment.amount} onChange={e=>{setPayment({...payment,amount:e.target.value});setPaymentKey("");}}/></label>
          <label className="field">Méthode<select value={payment.method} onChange={e=>{setPayment({...payment,method:e.target.value});setPaymentKey("");}}>
            {METHODS.map(([v,l])=><option key={v} value={v}>{l}</option>)}
          </select></label>
          <label className="field">Référence justificatif<input required maxLength={120} value={payment.reference} onChange={e=>{setPayment({...payment,reference:e.target.value});setPaymentKey("");}}/></label>
          <label className="field">Date<input required type="date" max={today()} value={payment.paid_on} onChange={e=>{setPayment({...payment,paid_on:e.target.value});setPaymentKey("");}}/></label>
        </div>
        <Button disabled={busy} primary>Enregistrer le versement déclaré</Button>
      </form>}
      {detail.payments?.length>0&&<Table headers={["Date","Montant","Méthode","Justificatif","Statut","Contrôle"]} rows={detail.payments.map(p=>[
        p.paid_on,fmt(p.amount,detail.run.currency),METHODS.find(([k])=>k===p.method)?.[1]||p.method,
        p.reference,<Status tone={p.voided?"gray":"green"}>{p.voided?"Annulé":"Enregistré"}</Status>,
        canReverse&&!p.voided?<Button className="small" onClick={()=>reverse(p)}>Annuler sous contrôle</Button>:"—",
      ])}/>}
    </Card>}
  </section>;
}
