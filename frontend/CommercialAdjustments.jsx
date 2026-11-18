import React,{useRef,useState} from "react";
const money=value=>new Intl.NumberFormat("fr-GA").format(value)+" FCFA";
export function TrialStatus({trial}){
  if(!trial)return null;
  return <p className="hint"><strong>Essai gratuit : {({active:"en cours",scheduled:"programmé",expired:"expiré",converted:"converti en abonnement"})[trial.status]}</strong> — du {trial.starts_on} au {trial.ends_before} (fin exclue). Aucune échéance ni sanction liée à l’essai gratuit avant activation du service payant.</p>;
}
export default function CommercialAdjustments({api,path,year,sub,trial,canTrial,disabled,onSaved}){
  const [days,setDays]=useState("30"),[reason,setReason]=useState(""),[quote,setQuote]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const pending=useRef(false);
  async function run(action,extra){
    if(pending.current||disabled)return;
    pending.current=true;setBusy(true);setError("");
    try{
      const result=await api(path,{action,year_id:year,...extra});
      if(action==="amendment_quote")setQuote(result.amendment);
      else{setQuote(null);setReason("");onSaved();}
    }catch(e){setError(e.message);}
    finally{pending.current=false;setBusy(false);}
  }
  const hasReason=reason.trim().length>0&&reason.trim().length<=240;
  const validDays=Number.isInteger(Number(days))&&Number(days)>=1&&Number(days)<=90;
  return <section aria-label="Avenants et essai gratuit">
    <TrialStatus trial={trial}/>
    {!sub&&canTrial&&<form onSubmit={e=>{e.preventDefault();run("trial_start",{days:Number(days),reason:reason.trim()});}}>
      <h3>Accorder un essai gratuit</h3>
      <p>Un seul essai par établissement, sans création de contrat ni frais. L’expiration de l’essai ne déclenche pas la facturation. La conversion nécessite une activation explicite.</p>
      <label className="ya-field"><span>Durée d’essai en jours</span><input type="number" min="1" max="90" required value={days} onChange={e=>setDays(e.target.value)}/></label>
      <label className="ya-field"><span>Motif de l’essai</span><textarea maxLength={240} required value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <button className="ya-btn ya-btn-outline" disabled={busy||disabled||!hasReason||!validDays}>Accorder l’essai</button>
    </form>}
    {sub&&<div>
      <h3>Avenants commerciaux</h3>
      <p>Le contrat initial reste inchangé. Les effectifs supplémentaires sur les cycles existants sont calculés au prorata des jours restants, après absorption par le complément minimum disponible. Le supplément éventuel est exigible à la date d'émission.</p>
      <p>Total initial : {money(sub.original_total_xaf??sub.total_xaf)} · Total actualisé : {money(sub.total_xaf)}</p>
      {(sub.amendments||[]).map(a=><p key={a.id}>Avenant n° {a.revision} — {a.effective_on} — {money(a.amount_xaf)}</p>)}
      <button type="button" className="ya-btn ya-btn-outline" disabled={busy||disabled} onClick={()=>run("amendment_quote",{})}>Calculer un avenant</button>
      {quote&&<form onSubmit={e=>{e.preventDefault();run("amendment_issue",{expected:quote,reason:reason.trim()});}}>
        {quote.additions.map(a=><p key={a.cycle}>{a.label} : +{a.students} élève(s) × {money(a.rate_xaf)} / an</p>)}
        <p>Prorata : {quote.remaining_days} / {quote.duration_days} jours · Supplément brut : {money(quote.gross_prorata_xaf)} · Couvert par le minimum : {money(quote.minimum_absorbed_xaf)}</p>
        <p><strong>Montant de l’avenant : {money(quote.amount_xaf)}</strong></p>
        {!quote.additions.length&&<p>Aucun effectif supplémentaire.</p>}
        <label className="ya-field"><span>Motif de l’avenant</span><textarea required maxLength={240} value={reason} onChange={e=>setReason(e.target.value)}/></label>
        <button className="ya-btn ya-btn-primary" disabled={busy||disabled||!hasReason||!quote.additions.length}>Émettre l’avenant</button>
      </form>}
    </div>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
