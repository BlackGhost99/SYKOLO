import React,{useEffect,useState} from "react";
const money=n=>new Intl.NumberFormat("fr-GA").format(n)+" FCFA";
const labels={annuel:"Annuel",semestriel:"Semestriel",trimestriel:"Trimestriel",mensuel:"Mensuel"};
function ScenarioForm({lines, actual, onApply}){
  return <form onSubmit={event=>{
    event.preventDefault();
    const query=new URLSearchParams(new FormData(event.currentTarget));
    onApply(query.toString());
  }}>
    <fieldset><legend>Simuler un autre effectif</legend>
      {lines.map(line=><label className="field" key={line.cycle}>{line.label} · {actual[line.cycle]} inscrits
        <input name={"effectif_"+line.cycle} type="number" min="0" max="9999999" step="1" required defaultValue={line.students}/>
      </label>)}
      <button type="submit">Calculer la projection</button>
    </fieldset>
  </form>;
}
export default function CommercialSimulator(props){
  return <Simulator key={JSON.stringify([props.schoolId,props.yearId])} {...props}/>;
}
function Simulator({schoolId,yearId,platform=false,api,tariffRevision=0}){
  const [state,setState]=useState({loading:true}),[year,setYear]=useState(""),[period,setPeriod]=useState("mensuel"),[setup,setSetup]=useState(false),[reload,setReload]=useState(0);
  const [scenario,setScenario]=useState("");
  useEffect(()=>{
    let live=true,busy=false;
    setState({loading:true});
    const path=(platform?"platform/schools/":"schools/")+schoolId+(platform?"/subscription-simulation":"/owner/subscription-simulation");
    const selected=yearId||year;
    const parameters=new URLSearchParams(scenario);
    if(selected)parameters.set("year_id",selected);
    const url=path+(parameters.size?"?"+parameters:"");
    async function refresh(){
      if(busy||document.hidden)return;
      busy=true;
      try{
        let data;
        if(platform)data=await api(url);
        else{
          const response=await fetch("/api/v1/"+url,{credentials:"same-origin",cache:"no-store"});
          data=await response.json();
          if(!response.ok)throw Error(data.error||"Simulation indisponible.");
        }
        if(!data?.school||!Array.isArray(data.years))throw Error("Simulation indisponible dans cet environnement.");
        if(live)setState({data});
      }catch(error){if(live)setState({error:error.message});}
      finally{busy=false;}
    }
    refresh();
    const timer=window.setInterval(refresh,30000);
    window.addEventListener("focus",refresh);document.addEventListener("visibilitychange",refresh);
    return()=>{live=false;window.clearInterval(timer);window.removeEventListener("focus",refresh);document.removeEventListener("visibilitychange",refresh);};
  },[schoolId,yearId,year,platform,api,tariffRevision,reload,scenario]);
  const d=state.data,terms=d?.simulation?.options[period],fee=setup?(d?.simulation?.setup_suggested_xaf||0):0;
  return <section aria-label="Simulateur BWETEK" className="ya-box">
    <h3>Estimer l’abonnement BWETEK</h3>
    <p>Estimation selon les élèves actifs inscrits et les cycles ouverts. Ce calcul ne crée ni contrat, ni facture, ni somme exigible. Les contrats déjà signés conservent leurs conditions.</p>
    {state.loading&&<p role="status">Calcul des effectifs réels…</p>}
    {state.error&&<p role="alert">{state.error}</p>}
    {d&&<>
      <p>{d.school.name} · {d.school.type_label}</p>
      {!yearId&&!!d.years.length&&<label>Année de simulation<select value={d.year_id||""} onChange={e=>{setScenario("");setYear(e.target.value);}}>{d.years.map(y=><option key={y.id} value={y.id}>{y.name}</option>)}</select></label>}
      {!d.years.length&&<p>Aucune année scolaire disponible.</p>}
      {d.error&&<p role="alert">{d.error}</p>}
      {terms&&<>
        <p><strong>{scenario?"Projection sur effectifs simulés":"Estimation sur effectifs réels"}</strong></p>
        {d.actual_counts&&<ScenarioForm key={JSON.stringify([d.year_id,scenario,d.actual_counts])} lines={d.simulation.lines} actual={d.actual_counts} onApply={setScenario}/>}
        {scenario&&<button type="button" onClick={()=>setScenario("")}>Revenir aux effectifs réels</button>}
        <p>Grille n° {d.simulation.policy_revision} · Effectif total : {terms.student_count}</p>
        <table><thead><tr><th>Cycle</th><th>Élèves</th><th>Tarif annuel</th><th>Montant</th></tr></thead><tbody>{d.simulation.lines.map(l=><tr key={l.cycle}><td>{l.label}</td><td>{l.students}</td><td>{money(l.rate_xaf)}</td><td>{money(l.amount_xaf)}</td></tr>)}</tbody></table>
        <p>Calcul par élèves : {money(terms.gross_xaf)} · Minimum annuel unique : {money(terms.minimum_xaf)} · Complément minimum : {money(terms.minimum_adjustment_xaf)}</p>
        <p><strong>Abonnement annuel estimé : {money(terms.annual_xaf)}</strong></p>
        <label>Fractionnement de l’estimation<select value={period} onChange={e=>setPeriod(e.target.value)}>{Object.entries(labels).map(([k,l])=><option key={k} value={k}>{l} · {d.simulation.options[k].schedule.length} versement(s)</option>)}</select></label>
        <p>Aucune remise automatique. Les montants et dates ci-dessous sont indicatifs et recalculés avec la grille actuelle.</p>
        {!!d.simulation.setup_suggested_xaf&&<label><input type="checkbox" checked={setup} onChange={e=>setSetup(e.target.checked)}/> Inclure la mise en service facultative : {money(d.simulation.setup_suggested_xaf)}</label>}
        <p><strong>Total estimé avec les options choisies : {money(terms.annual_xaf+fee)}</strong></p>
        {fee>0&&<p>Mise en service distincte : {money(fee)} à la première échéance.</p>}
        <details><summary>Voir les {terms.schedule.length} échéances</summary><ol>{terms.schedule.map(s=><li key={s.number}>{s.due_date} : {money(s.amount_xaf)}</li>)}</ol></details>
        {d.contracted&&<p>Un contrat existe pour cette année. Le montant dû et les règlements figurent dans le registre contractuel, séparément de cette estimation.</p>}
      </>}
    </>}
    <button type="button" onClick={()=>setReload(n=>n+1)}>Actualiser la simulation</button>
  </section>;
}
