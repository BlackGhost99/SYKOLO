import React,{useEffect,useState,useRef} from "react";
const groups=[["prescolaire","Crèche et préprimaire"],["primaire","Primaire"],["college","Collège et lycée"]];
export default function PlatformTariffPolicy({api,onSaved}){
  const [policy,setPolicy]=useState(null);
  const [reason,setReason]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const pending=useRef(false);
  useEffect(()=>{let live=true;api("platform/subscription-pricing").then(p=>{if(live)setPolicy(p)}).catch(e=>{if(live)setMessage(e.message)});return()=>{live=false};},[api]);
  function edit(group,key,value){setPolicy(p=>({...p,[group]:{...p[group],...Object.fromEntries((key==="college"?["college","lycee_general","lycee_technique"]:[key]).map(k=>[k,value]))}}));}
  const valid=policy&&["rates","minimums"].every(g=>Object.values(policy[g]).every(v=>String(v)!==""&&Number.isSafeInteger(Number(v))&&Number(v)>=0&&Number(v)<=10000000));
  async function save(e){
    e.preventDefault();if(!valid||pending.current||!reason.trim())return;
    pending.current=true;setBusy(true);setMessage("");
    try{
      const body=Object.fromEntries(["rates","minimums"].map(g=>[g,Object.fromEntries(Object.entries(policy[g]).map(([k,v])=>[k,Number(v)]))]));
      const saved=await api("platform/subscription-pricing",{...body,revision:policy.revision,reason:reason.trim()});
      setPolicy(saved);setReason("");setMessage("Grille enregistrée. Les contrats existants restent inchangés.");onSaved?.();
    }catch(e){setMessage(e.message);}finally{pending.current=false;setBusy(false);}
  }
  return <section className="ya-box ya-form-box yem-commercial-panel"><h2>Grille tarifaire YEM</h2><p>Tarif annuel par élève et minimum unique selon le cycle le plus élevé. Les nouveaux devis utilisent cette grille.</p>
    {policy&&<form onSubmit={save}>
      <p>Révision {policy.revision}</p>
      {groups.map(([key,label])=><div key={key}><h3>{label}</h3><div className="ya-form-grid">
        <label className="ya-field"><span>Tarif annuel par élève (FCFA)</span><input type="number" min="0" max="10000000" step="1" required value={policy.rates[key]} disabled={busy} onChange={e=>edit("rates",key,e.target.value)}/></label>
        <label className="ya-field"><span>Minimum annuel (FCFA)</span><input type="number" min="0" max="10000000" step="1" required value={policy.minimums[key]} disabled={busy} onChange={e=>edit("minimums",key,e.target.value)}/></label>
      </div></div>)}
      <label className="ya-field"><span>Motif du changement</span><textarea required maxLength={240} value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <button className="ya-btn ya-btn-primary" disabled={!valid||!reason.trim()||busy}>Enregistrer la grille</button>
    </form>}{message&&<p role="status">{message}</p>}
  </section>;
}
