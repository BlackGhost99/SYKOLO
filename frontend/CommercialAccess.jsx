import React,{useEffect,useRef,useState} from "react";
const labels={active:"Abonnement actif",trial_active:"Essai actif",scheduled:"Abonnement à venir",expired:"Abonnement ou essai expiré",review:"Contrat historique à vérifier",unconfigured:"Service gratuit"};
const money=value=>new Intl.NumberFormat("fr-GA").format(value)+" FCFA";
export default function CommercialAccess({schoolId,api=null}){
  const [state,setState]=useState(null),[reason,setReason]=useState(""),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const [override,setOverride]=useState(false);
  const pending=useRef(false),generation=useRef(0);
  const route=api?"platform/schools/"+schoolId+"/commercial-access":"schools/"+schoolId+"/owner/commercial-access";
  useEffect(()=>{
    let live=true;let reading=false;
    setState(null);setReason("");setError("");setOverride(false);
    async function refresh(){
      if(!live||reading||pending.current||document.hidden)return;
      reading=true;const version=generation.current;
      try{
        let result;
        if(api)result=await api(route);
        else{
          const response=await fetch("/api/v1/"+route,{credentials:"same-origin",cache:"no-store"});
          result=await response.json();if(!response.ok)throw Error(result.error||"État commercial indisponible.");
        }
        if(!result||typeof result.revision!=="number")throw Error("État commercial indisponible.");
        if(live&&version===generation.current){setState(result);setError("");}
      }catch(e){if(live&&version===generation.current){setState(null);setError(e.message);}}
      finally{reading=false;}
    }
    refresh();const timer=window.setInterval(refresh,30000);
    window.addEventListener("focus",refresh);document.addEventListener("visibilitychange",refresh);
    return()=>{live=false;window.clearInterval(timer);window.removeEventListener("focus",refresh);document.removeEventListener("visibilitychange",refresh);};
  },[route,api]);
  async function change(event){
    event.preventDefault();
    if(!api||!state||pending.current||!reason.trim()||(!state.restricted&&!state.can_restrict&&!override))return;
    pending.current=true;generation.current++;setBusy(true);setError("");
    try{const result=await api(route,{restricted:!state.restricted,revision:state.revision,reason:reason.trim(),...(!state.restricted&&!state.can_restrict?{override_grace:true}:{})});setState(result);setReason("");setOverride(false);}
    catch(e){setError(e.message);}
    finally{pending.current=false;setBusy(false);}
  }
  return <section className={api?"ya-box yem-commercial-panel":"card"} aria-label="État commercial et accès">
    <h3>État commercial YEM</h3>
    {state?<><p><strong>{labels[state.lifecycle]||state.lifecycle}</strong>{state.service_ends_before?" · Fin de service (exclue) : "+state.service_ends_before:""}</p>
      {state.billing_started===false?<p>Facturation inactive : aucun décompte commercial avant activation par BWETEK.</p>:<p>Échu : {money(state.overdue_xaf)} · Retard de 30 jours ou plus : {money(state.late_30_xaf)}</p>}
      <p role="status">{state.restricted?"Établissement en lecture seule":"Accès établissement normal"}</p>
      {state.restriction_eligible_on&&<p>Fin de grâce : {state.restriction_eligible_on} · {state.grace_days_remaining} jour(s) restant(s)</p>}
      <p className="hint">Après 30 jours de grâce, le passage manuel en lecture seule bloque toutes les modifications scolaires. La consultation et la régularisation commerciale restent possibles. Aucun blocage automatique.</p>
      {api&&<form onSubmit={change}>
        {!state.restricted&&!state.can_restrict&&<label className="ya-field"><span><input type="checkbox" checked={override} onChange={e=>setOverride(e.target.checked)} disabled={busy}/> Dérogation administrative : appliquer la lecture seule avant la fin de grâce ou sans abonnement.</span><small>Restriction réelle, sans création de contrat ni dette. Réactivation possible à tout moment.</small></label>}
        <label className="ya-field"><span>Motif de la décision commerciale</span><textarea maxLength={240} required value={reason} onChange={e=>setReason(e.target.value)}/></label>
        <button className="ya-btn ya-btn-outline" disabled={busy||!reason.trim()||(!state.restricted&&!state.can_restrict&&!override)}>{state.restricted?"Rétablir l’accès normal":state.can_restrict?"Passer en lecture seule":"Appliquer la restriction manuelle"}</button>
      </form>}
    </>:!error&&<p>Chargement de l’état commercial…</p>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
