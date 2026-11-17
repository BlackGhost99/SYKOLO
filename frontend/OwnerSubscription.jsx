import React,{useEffect,useState} from "react";
import {Card} from "./yem-ui.jsx";
import SubscriptionDocuments from "./SubscriptionDocuments.jsx";
import CommercialReminders from "./CommercialReminders.jsx";
import {TrialStatus} from "./CommercialAdjustments.jsx";
const money=v=>new Intl.NumberFormat("fr-FR").format(v)+" FCFA";
export default function OwnerSubscription({schoolId,yearId}){
  const [state,setState]=useState({loading:true,records:[],error:""});
  useEffect(()=>{
    let live=true,busy=false;setState({loading:true,records:[],error:""});
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
  },[schoolId]);
  const sub=state.records.find(r=>r.year_id===yearId);
  return <Card title="Abonnement YEM — BWETEK Informatyk" icon="receipt">
    <p className="hint">Abonnement de l’établissement, distinct des frais de scolarité des familles. Consultation seule.</p>
    <CommercialReminders key={schoolId} schoolId={schoolId}/>
    <TrialStatus trial={state.trial}/>
    {state.loading?<p role="status">Chargement…</p>:state.error?<p role="alert">{state.error}</p>:!sub?<p>Aucun contrat émis pour cette année scolaire.</p>:<>
      <p><strong>{sub.year}</strong> · Total contractuel : {money(sub.total_xaf)} · Réglé : {money(sub.paid_xaf)} · Solde : {money(sub.balance_xaf)}</p>
      <SubscriptionDocuments documents={sub.documents}/>
      {!!sub.amendments?.length&&<><p>Contrat initial : {money(sub.original_total_xaf)}</p>{sub.amendments.map(a=><p key={a.id}>Avenant n° {a.revision} — {a.effective_on} — {money(a.amount_xaf)}</p>)}</>}
      {sub.lines.map(l=><p key={l.cycle}>{l.label} — {l.students} × {money(l.rate_xaf)} = {money(l.amount_xaf)}</p>)}
      {sub.terms?.period&&<>
        <p>Minimum unique : {money(sub.terms.minimum_xaf)} · Remise : {money(sub.terms.discount_xaf)} · Mise en service : {money(sub.terms.setup_xaf)}</p>
        <h3>Échéancier {({annuel:"annuel",semestriel:"semestriel",trimestriel:"trimestriel",mensuel:"mensuel"})[sub.terms.period]||""}</h3>
        {sub.schedule.map(s=><p key={s.kind+s.number}>{s.kind==="mise_en_service"?"Mise en service":s.kind==="avenant"?"Avenant "+s.number:"Versement "+s.number} — {s.due_date} — {money(s.amount_xaf)} · reste : {money(s.balance_xaf)} {s.days_overdue>0?" · "+s.days_overdue+" j de retard":""}</p>)}
      </>}
    </>}
  </Card>;
}
