import React,{useEffect,useState} from "react";
const money=n=>new Intl.NumberFormat("fr-GA").format(n)+" FCFA";
const statuses=[["all","Tous"],["overdue","Impayés"],["read_only","Lecture seule"],["trial","Essais actifs"],["no_contract","Sans contrat"],["review","À contrôler"]];
const methods={especes:"Espèces",mobile_money:"Mobile Money déclaré",virement:"Virement déclaré",autre:"Autres"};
export default function CommercialDashboard({api,onSelectSchool}){
  const [year,setYear]=useState(""),[status,setStatus]=useState("all"),[search,setSearch]=useState(""),[page,setPage]=useState(1),[reload,setReload]=useState(0);
  const [state,setState]=useState({loading:true});
  useEffect(()=>{
    let live=true,busy=false;
    const params=new URLSearchParams({status,q:search,page:String(page)});
    if(year)params.set("year",year);
    setState({loading:true});
    async function refresh(){
      if(!live||busy)return;
      busy=true;
      try{const data=await api("platform/commercial-dashboard?"+params.toString());if(live)setState({data});}
      catch(e){if(live)setState({error:e.message});}
      finally{busy=false;}
    }
    refresh();
    const poll=()=>{if(!document.hidden)refresh();};
    const timer=window.setInterval(poll,30000);
    window.addEventListener("focus",poll);
    return()=>{live=false;window.removeEventListener("focus",poll);window.clearInterval(timer);};
  },[api,year,status,search,page,reload]);
  const d=state.data,t=d?.totals;
  const cards=t?[["Montant contractuel cumulé",t.contracted_xaf],["Règlements déclarés nets",t.paid_xaf],["Solde à recouvrer",t.balance_xaf],["Impayés échus",t.overdue_xaf],["Échéances du jour",t.due_today_xaf],["Échéances futures",t.future_xaf],["Solde sans échéancier fiable",t.unscheduled_xaf],["Suppléments d’avenants inclus",t.amendments_xaf]]:[];
  return <section aria-label="Finances commerciales BWETEK">
    <div className="ya-box">
      <h2>Finances commerciales — BWETEK Informatyk</h2>
      <p className="hint">Registre commercial YEM uniquement. Ni frais scolaires, ni résultat comptable de BWETEK. Montants cumulés sur tous les contrats émis, établissements inactifs inclus. Règlements déclarés, hors écritures annulées.</p>
      <button className="ya-btn ya-btn-outline" type="button" onClick={()=>setReload(n=>n+1)}>Actualiser</button>
      {state.loading&&<p role="status">Chargement des finances…</p>}{state.error&&<p role="alert">{state.error}</p>}
      {d&&<>
        <p className="hint">Situation au {d.as_of} · Actualisation toutes les 30 secondes.</p>
        <div className="ya-stats">{cards.map(([label,value])=><div className="ya-box" key={label}><p>{label}</p><h3>{money(value)}</h3></div>)}</div>
        <p>Établissements : {t.schools} · Sous contrat : {t.contracted_schools} · Abonnés actifs : {t.active_schools} · Essais actifs : {t.active_trials} · En impayé : {t.overdue_schools} · Lecture seule : {t.read_only_schools}</p>
        {!!(t.review_count||t.overpaid_xaf)&&<p role="note">{t.review_count} contrat(s) à contrôler · Trop-perçu : {money(t.overpaid_xaf)}. Les échéances historiques incohérentes ne sont pas estimées.</p>}
      </>}
    </div>
    {d&&<div className="ya-box">
      <h3>Encaissements commerciaux par mois</h3>
      <label className="ya-field"><span>Année civile des règlements</span><select value={year||String(d.year)} onChange={e=>setYear(e.target.value)}>
        {Array.from({length:Number(d.as_of.slice(0,4))-1999},(_,i)=>Number(d.as_of.slice(0,4))-i).map(y=><option key={y}>{y}</option>)}
      </select></label>
      <p><strong>{money(d.year_received_xaf)}</strong> déclarés et non annulés en {d.year} · {money(d.year_voided_xaf)} d’écritures annulées (mois d’enregistrement initial).</p>
      <table><thead><tr><th>Mois</th><th>Règlements nets</th><th>Écritures annulées</th></tr></thead><tbody>{d.months.map(m=><tr key={m.month}><td>{m.month}</td><td>{money(m.received_xaf)}</td><td>{money(m.voided_xaf)}</td></tr>)}</tbody></table>
      <h4>Moyens de règlement déclarés</h4>{Object.entries(d.methods).map(([key,v])=><p key={key}>{methods[key]||key} : {money(v)}</p>)}
    </div>}
    <div className="ya-box">
      <h3>Recouvrement par établissement</h3>
      <p className="hint">Les filtres ci-dessous concernent uniquement la liste, pas les totaux globaux.</p>
      <label className="ya-field"><span>Rechercher un établissement</span><input value={search} maxLength={120} onChange={e=>{setSearch(e.target.value);setPage(1);}}/></label>
      <label className="ya-field"><span>État commercial</span><select value={status} onChange={e=>{setStatus(e.target.value);setPage(1);}}>{statuses.map(([k,l])=><option key={k} value={k}>{l}</option>)}</select></label>
      {d&&<>
        <p>{d.count} établissement(s)</p>
        {!d.schools.length&&<p>Aucun établissement correspondant.</p>}
        {d.schools.map(s=><div className="ya-info-row" key={s.school_id}>
          <div><strong>{s.school}</strong>{!s.enabled?" · Inactif":""}{s.read_only?" · Lecture seule":""}{s.trial==="active"?" · Essai actif":""}
            <p>Contrats : {s.contracts} · {money(s.contracted_xaf)} contractualisés · {money(s.paid_xaf)} réglés · {money(s.balance_xaf)} restants</p>
            <p>Impayés : {money(s.overdue_xaf)} · Retard ≥ 30 j : {money(s.late_30_xaf)}{s.review_count?" · Historique à contrôler":""}</p>
          </div>
          <button className="ya-btn ya-btn-outline" type="button" onClick={()=>onSelectSchool(s.school_id)}>Gérer l’abonnement</button>
        </div>)}
        {d.pages>1&&<p><button disabled={d.page===1} onClick={()=>setPage(d.page-1)}>Précédent</button> Page {d.page} / {d.pages} <button disabled={d.page===d.pages} onClick={()=>setPage(d.page+1)}>Suivant</button></p>}
      </>}
    </div>
  </section>;
}
