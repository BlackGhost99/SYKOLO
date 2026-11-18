import {ContextTarget} from "./ContextMenu.jsx";
import React,{useEffect,useState} from "react";
const money=value=>new Intl.NumberFormat("fr-GA").format(value)+" FCFA";
function timing(item){
  const days=item.days_until_due;
  if(days>0)return "Dans "+days+" jour"+(days===1?"":"s");
  if(days===0)return "À régler aujourd’hui";
  return "Retard de "+(-days)+" jour"+(days===-1?"":"s");
}
export default function CommercialReminders({schoolId,platform=false,onSelectSchool}){
  const [page,setPage]=useState(1);
  const [state,setState]=useState({loading:true,data:null,error:""});
  const endpoint=platform?"/api/v1/platform/subscription-reminders":schoolId?"/api/v1/schools/"+schoolId+"/owner/subscription-reminders":"";
  useEffect(()=>{
    if(!endpoint)return;
    let live=true,busy=false;let controller;
    setState({loading:true,data:null,error:""});
    async function refresh(){
      if(!live||busy||document.hidden)return;
      busy=true;controller=new AbortController();
      try{
        const response=await fetch(endpoint+"?page="+page,{credentials:"same-origin",cache:"no-store",signal:controller.signal});
        const body=await response.json();
        if(!response.ok||!Array.isArray(body.reminders))throw Error(body.error||"Alertes indisponibles.");
        if(live)setState({loading:false,data:body,error:""});
      }catch(e){if(live)setState({loading:false,data:null,error:e.message});}
      finally{busy=false;}
    }
    refresh();
    const timer=window.setInterval(refresh,30000);
    window.addEventListener("focus",refresh);
    document.addEventListener("visibilitychange",refresh);
    return()=>{live=false;controller?.abort();window.clearInterval(timer);window.removeEventListener("focus",refresh);document.removeEventListener("visibilitychange",refresh);};
  },[endpoint,page]);
  const data=state.data;
  return <section className={platform?"ya-box":"card"} aria-label="Alertes commerciales YEM">
    <h3>Échéances et relances YEM</h3>
    <p className="hint">Abonnement BWETEK — distinct de la scolarité. Alertes automatiques dans YEM, actualisées toutes les 30 secondes lorsque la page est visible.</p>
    {state.loading?<p>Chargement des échéances…</p>:state.error?<p role="alert">{state.error}</p>:data&&<>
      <p><strong>{data.overdue_count}</strong> en retard · <strong>{data.due_count}</strong> aujourd’hui · <strong>{data.upcoming_count}</strong> dans les {data.window_days} prochains jours</p>
      {!!data.overdue_count&&<p>Solde échu : <strong>{money(data.overdue_xaf)}</strong></p>}
      {!!data.missing_schedule_count&&<p role="note">{data.missing_schedule_count} contrat(s) historique(s) sans échéancier : contrôle manuel nécessaire.</p>}
      {!data.count&&<p>Aucune échéance à relancer actuellement.</p>}
      {data.reminders.map(item=><ContextTarget className="ya-info-row" key={item.id} showTrigger actions={platform&&onSelectSchool?[{id:"school",label:"Voir l’établissement et son abonnement",run:()=>onSelectSchool(item.school_id)}]:[]}>
        <div><strong>{timing(item)}</strong> · {item.kind==="mise_en_service"?"Mise en service":item.kind==="avenant"?"Avenant "+item.number:"Versement "+item.number} — {item.due_date}<br/>
          {platform?item.school+" · ":""}{item.year} · {money(item.balance_xaf)} restant(s)
          {item.stage==="late_30"&&<strong> · Relance prioritaire (30 jours et plus)</strong>}
          {item.stage==="late_7"&&<strong> · Relance prolongée (7 jours et plus)</strong>}</div>
        {platform&&onSelectSchool&&<button type="button" className="ya-btn ya-btn-outline" onClick={()=>onSelectSchool(item.school_id)}>Voir l’établissement</button>}
      </ContextTarget>)}
      {data.pages>1&&<div>
        <button type="button" disabled={data.page<=1} onClick={()=>setPage(data.page-1)}>Précédent</button>{" "}
        Page {data.page} / {data.pages}{" "}
        <button type="button" disabled={data.page>=data.pages} onClick={()=>setPage(data.page+1)}>Suivant</button>
      </div>}
    </>}
  </section>;
}
