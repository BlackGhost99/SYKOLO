import SubscriptionSingPay from "./SubscriptionSingPay.jsx";
import CommercialSimulator from "./CommercialSimulator.jsx";
import React,{useEffect,useState} from "react";
import {Card} from "./yem-ui.jsx";
import SubscriptionDocuments from "./SubscriptionDocuments.jsx";
import CommercialReminders from "./CommercialReminders.jsx";
import {TrialStatus} from "./CommercialAdjustments.jsx";
import CommercialAccess from "./CommercialAccess.jsx";
const money=v=>new Intl.NumberFormat("fr-FR").format(v)+" FCFA";
export default function OwnerSubscription({schoolId,yearId}){
  const [state,setState]=useState({loading:true,records:[],error:""});
  const [refreshVersion,setRefreshVersion]=useState(0);
  useEffect(()=>{setState({loading:true,records:[],error:""});},[schoolId]);
  useEffect(()=>{
    let live=true,busy=false;
    async function refresh(){
      if(busy||document.hidden)return;
      busy=true;
      try{
        const r=await fetch("/api/v1/schools/"+schoolId+"/owner/subscriptions",{credentials:"same-origin",cache:"no-store"});
        const body=await r.json();
        if(!r.ok)throw Error(body.error||"Abonnements indisponibles.");
        if(live)setState({loading:false,records:body.subscriptions||[],trial:body.trial,error:""});
      }catch(e){if(live)setState({loading:false,records:[],error:e.message});}
      finally{busy=false;}
    }
    refresh();
    const timer=window.setInterval(refresh,30000);
    window.addEventListener("focus",refresh);
    document.addEventListener("visibilitychange",refresh);
    return()=>{live=false;window.clearInterval(timer);window.removeEventListener("focus",refresh);document.removeEventListener("visibilitychange",refresh);};
  },[schoolId,refreshVersion]);
  const [selectedYear,setSelectedYear]=useState("");
  const [view,setView]=useState("summary");
  const sub=yearId?state.records.find(r=>r.year_id===yearId):state.records.find(r=>r.year_id===selectedYear)||state.records[0];
  return <Card title="Abonnement YEM — BWETEK Informatyk" icon="receipt">
    <p className="hint">Abonnement de l’établissement, distinct des frais de scolarité des familles. Le paiement Mobile Money est disponible lorsque le compte marchand BWETEK est validé et activé.</p>
    <div className="yd-dashboard-views yd-subscription-views" role="group" aria-label="Rubriques de l’abonnement">{[["summary","Situation"],["contract","Contrat et documents"],["reminders","Échéances et relances"]].map(([id,label])=><button type="button" key={id} aria-pressed={view===id} onClick={()=>setView(id)}>{label}</button>)}</div>
    {view==="summary"&&<><CommercialSimulator schoolId={schoolId} yearId={yearId||sub?.year_id||undefined}/><CommercialAccess key={"commercial:"+schoolId} schoolId={schoolId}/><TrialStatus trial={state.trial}/></>}
    <div hidden={view!=="reminders"}><CommercialReminders key={schoolId} schoolId={schoolId}/></div>
    {!yearId&&state.records.length>1&&<label className="field">Année du contrat<select value={sub?.year_id||""} onChange={e=>setSelectedYear(e.target.value)}>{state.records.map(r=><option key={r.id} value={r.year_id}>{r.year}</option>)}</select></label>}
    {state.loading?<p role="status">Chargement…</p>:state.error?<p role="alert">{state.error}</p>:!sub?<p>Aucun contrat émis pour cette année scolaire : aucune somme exigible pour cette année.</p>:<>
      <div className="yd-subscription-totals" aria-label="Synthèse contractuelle"><div><small>Total contractuel · {sub.year}</small><strong>{money(sub.total_xaf)}</strong></div><div><small>Réglé</small><strong>{money(sub.paid_xaf)}</strong></div><div><small>Solde</small><strong>{money(sub.balance_xaf)}</strong></div></div>
      {sub.pending_adjustment?.status==="pending"&&<div className="hint" role="status"><strong>Régularisation en attente : {sub.pending_adjustment.students} élève(s) supplémentaire(s).</strong> Estimation au prorata au {sub.pending_adjustment.effective_on} : {money(sub.pending_adjustment.amount_xaf)}. Ce montant ne sera exigible qu’après émission de l’avenant par BWETEK.</div>}
      {sub.pending_adjustment?.status==="review"&&<p className="hint" role="status">Situation contractuelle à contrôler : {sub.pending_adjustment.reason}</p>}
      {view==="summary"&&<SubscriptionSingPay key={sub.id} schoolId={schoolId} subscriptionId={sub.id} onRefresh={()=>setRefreshVersion(v=>v+1)}/>}
      {view==="contract"&&<><SubscriptionDocuments documents={sub.documents}/>
      {!!sub.amendments?.length&&<><p>Contrat initial : {money(sub.original_total_xaf)}</p>{sub.amendments.map(a=><p key={a.id}>Avenant n° {a.revision} — {a.effective_on} — {money(a.amount_xaf)}</p>)}</>}
      {sub.lines.map(l=><p key={l.cycle}>{l.label} — {l.students} × {money(l.rate_xaf)} = {money(l.amount_xaf)}</p>)}
      </>}
      {view==="reminders"&&sub.terms?.period&&<>
        <p>Minimum unique : {money(sub.terms.minimum_xaf)} · Remise : {money(sub.terms.discount_xaf)} · Mise en service : {money(sub.terms.setup_xaf)}</p>
        <h3>Échéancier {({annuel:"annuel",semestriel:"semestriel",trimestriel:"trimestriel",mensuel:"mensuel"})[sub.terms.period]||""}</h3>
        {sub.schedule.map(s=><p key={s.kind+s.number}>{s.kind==="mise_en_service"?"Mise en service":s.kind==="avenant"?"Avenant "+s.number:"Versement "+s.number} — {s.due_date} — {money(s.amount_xaf)} · reste : {money(s.balance_xaf)} {s.days_overdue>0?" · "+s.days_overdue+" j de retard":""}</p>)}
      </>}
    </>}
  </Card>;
}
