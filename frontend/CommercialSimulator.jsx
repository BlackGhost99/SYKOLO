import React,{useEffect,useState} from "react";
import "./commercial-estimate.css";

const money=n=>new Intl.NumberFormat("fr-GA").format(n)+" FCFA";
const labels={annuel:"Annuel",semestriel:"Semestriel",trimestriel:"Trimestriel",mensuel:"Mensuel"};
const cycles={prescolaire:"Petite enfance",primaire:"Primaire",college:"Collège",lycee_general:"Lycée général",lycee_technique:"Lycée technique"};
const dateLabel=value=>value?value.split("-").reverse().join("/"):"—";

export default function CommercialSimulator(props){
  return <Estimate key={JSON.stringify([props.schoolId,props.yearId])} {...props}/>;
}

function Estimate({schoolId,yearId,platform=false,api,tariffRevision=0,refreshKey=0}){
  const [state,setState]=useState({loading:true}),[year,setYear]=useState(""),[period,setPeriod]=useState("mensuel"),[reload,setReload]=useState(0);
  useEffect(()=>{
    let live=true,busy=false;
    setState({loading:true});
    const path=(platform?"platform/schools/":"schools/")+schoolId+(platform?"/subscription-simulation":"/owner/subscription-simulation");
    const selected=yearId||year;
    const url=path+(selected?"?year_id="+encodeURIComponent(selected):"");
    async function refresh(force=false){
      if(!live||busy||(!force&&document.hidden))return;
      busy=true;
      try{
        let data;
        if(platform)data=await api(url);
        else{
          const response=await fetch("/api/v1/"+url,{credentials:"same-origin",cache:"no-store"});
          data=await response.json();
          if(!response.ok)throw Error(data.error||"Effectifs indisponibles.");
        }
        if(!data?.school||!Array.isArray(data.years))throw Error("Effectifs indisponibles.");
        if(live)setState({data});
      }catch(error){if(live)setState({error:error.message});}
      finally{busy=false;}
    }
    const poll=()=>refresh();
    refresh(true);
    const timer=window.setInterval(poll,30000);
    window.addEventListener("focus",poll);document.addEventListener("visibilitychange",poll);
    return()=>{live=false;window.clearInterval(timer);window.removeEventListener("focus",poll);document.removeEventListener("visibilitychange",poll);};
  },[schoolId,yearId,year,platform,api,tariffRevision,reload,refreshKey]);
  const d=state.data,terms=d?.simulation?.options[period];
  return <section aria-label="Effectifs et tarification YEM" className="yem-commercial-estimate">
    <header className="yem-estimate-head"><h3>Effectifs et coût annuel</h3><button type="button" aria-label="Actualiser les effectifs" onClick={()=>setReload(n=>n+1)}>Actualiser</button></header>
    {state.loading&&<p role="status">Calcul des effectifs réels…</p>}
    {state.error&&<p role="alert">{state.error}</p>}
    {d&&<>
      {!yearId&&!!d.years.length&&<label className="field">Année scolaire<select value={d.year_id||""} onChange={e=>setYear(e.target.value)}>{d.years.map(y=><option key={y.id} value={y.id}>{y.name}</option>)}</select></label>}
      {!d.years.length&&<p>Aucune année scolaire disponible.</p>}
      {d.error&&<p role="alert">{d.error}</p>}
      <div className="yem-estimate-state"><strong>{d.contracted?"Service payant activé":"Service gratuit · facturation inactive"}</strong>
        {d.contracted&&d.billing_activated_on&&<small>Activation : {dateLabel(d.billing_activated_on)}{d.first_contract_due?" · Première échéance : "+dateLabel(d.first_contract_due):""}</small>}
        {!d.contracted&&<small>Aucune échéance avant l’activation par BWETEK.</small>}
      </div>
      {terms&&<>
        <div className="yem-estimate-totals"><div><small>Élèves inscrits</small><strong>{new Intl.NumberFormat("fr-GA").format(terms.student_count)}</strong></div><div><small>Coût annuel actuel (estimé)</small><strong>{money(terms.annual_xaf)}</strong></div></div>
        <div className="yem-estimate-cycles">{d.simulation.lines.map(l=><div className="yem-estimate-cycle" key={l.cycle}><div><strong>{cycles[l.cycle]||l.label}</strong><small>{l.students} élève(s) × {money(l.rate_xaf)}</small></div><b>{money(l.amount_xaf)}</b></div>)}</div>
        {!!terms.minimum_adjustment_xaf&&<p className="hint">Complément minimum unique : {money(terms.minimum_adjustment_xaf)}</p>}
        <label className="field">Modalité indicative<select value={period} onChange={e=>setPeriod(e.target.value)}>{Object.entries(labels).map(([k,l])=><option key={k} value={k}>{l}</option>)}</select></label>
        <p className="yem-estimate-installment"><strong>{money(terms.schedule[0]?.amount_xaf||0)}</strong> / versement · {terms.schedule.length} versement(s){terms.schedule.some(s=>s.amount_xaf!==terms.schedule[0]?.amount_xaf)?" (arrondi ajusté)":""}</p>
        <small className="hint">{d.contracted?"Effectifs et estimation actualisés. Les montants contractuels et leurs dates restent dans le contrat.":"Estimation uniquement, sans dette ni facture."} Actualisation automatique toutes les 30 secondes et au retour sur la page.</small>
      </>}
    </>}
  </section>;
}
