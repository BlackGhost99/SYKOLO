import React,{useEffect,useState} from "react";
import {Card} from "./yem-ui.jsx";
const money=v=>new Intl.NumberFormat("fr-FR").format(v)+" FCFA";
export default function OwnerSubscription({schoolId,yearId}){
  const [state,setState]=useState({loading:true,records:[],error:""});
  useEffect(()=>{
    let live=true;setState({loading:true,records:[],error:""});
    fetch("/api/v1/schools/"+schoolId+"/owner/subscriptions",{credentials:"same-origin"})
      .then(async r=>{const body=await r.json();if(!r.ok)throw Error(body.error||"Abonnements indisponibles.");if(live)setState({loading:false,records:body.subscriptions||[],error:""});})
      .catch(e=>{if(live)setState({loading:false,records:[],error:e.message});});
    return()=>{live=false};
  },[schoolId]);
  const sub=state.records.find(r=>r.year_id===yearId);
  return <Card title="Abonnement YEM — BWETEK Informatyk" icon="receipt">
    <p className="hint">Abonnement de l’établissement, distinct des frais de scolarité des familles. Consultation seule.</p>
    {state.loading?<p role="status">Chargement…</p>:state.error?<p role="alert">{state.error}</p>:!sub?<p>Aucun contrat émis pour cette année scolaire.</p>:<>
      <p><strong>{sub.year}</strong> · Total contractuel : {money(sub.total_xaf)} · Réglé : {money(sub.paid_xaf)} · Solde : {money(sub.balance_xaf)}</p>
      {sub.lines.map(l=><p key={l.cycle}>{l.label} — {l.students} × {money(l.rate_xaf)} = {money(l.amount_xaf)}</p>)}
      {sub.terms?.period&&<>
        <p>Minimum unique : {money(sub.terms.minimum_xaf)} · Remise : {money(sub.terms.discount_xaf)} · Mise en service : {money(sub.terms.setup_xaf)}</p>
        <h3>Échéancier</h3>
        {sub.schedule.map(s=><p key={s.kind+s.number}>{s.kind==="mise_en_service"?"Mise en service":"Versement "+s.number} — {s.due_date} — {money(s.amount_xaf)} · reste : {money(s.balance_xaf)} {s.days_overdue>0?" · "+s.days_overdue+" j de retard":""}</p>)}
      </>}
    </>}
  </Card>;
}
