import {permissionLabel} from "./RoleManager.jsx";
import React,{useEffect,useState} from "react";
async function api(path,body,method="POST") {
  if(body!==undefined) await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const token=document.cookie.split("; ").find(c=>c.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{credentials:"same-origin",method:body===undefined?"GET":method,headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json(); if(!response.ok)throw Error(data.error||"Opération refusée.");return data;
}
export default function DelegationManager({schoolId,onFunctions}) {
  const [options,setOptions]=useState([]),[enabled,setEnabled]=useState([]),[members,setMembers]=useState([]);
  const [grants,setGrants]=useState([]),[permissions,setPermissions]=useState([]),[selected,setSelected]=useState([]);
  const [user,setUser]=useState(""),[reason,setReason]=useState(""),[source,setSource]=useState(""),[expires,setExpires]=useState("");
  const [classCycle,setClassCycle]=useState(""),[classCycles,setClassCycles]=useState({});
  const managesClasses=selected.includes("school.classes.manage");
  const mixedScope=managesClasses&&classCycle&&selected.length>1;
  const [message,setMessage]=useState(""),[revokeReason,setRevokeReason]=useState(""),[busy,setBusy]=useState(false);
  const base="schools/"+schoolId;
  async function refresh(){
    const f=await api(base+"/functions");setOptions(f.options);setEnabled(f.functions.map(x=>x.code));onFunctions(f.functions);
    const m=await api(base+"/members");setMembers(m.members);
    const d=await api(base+"/delegations");setGrants(d.delegations);setPermissions(d.available_permissions);setClassCycles(d.class_cycles||{});
  }
  useEffect(()=>{refresh().catch(e=>setMessage(e.message));},[schoolId]);
  async function run(fn){setBusy(true);setMessage("");try{await fn();await refresh();setMessage("Enregistré.");}catch(e){setMessage(e.message);}finally{setBusy(false);}}
  return <section aria-label="Organisation et délégations">
    <h3>Fonctions proposées dans cet établissement</h3>
    <p>Aucun poste n'est obligatoire. Une personne peut cumuler plusieurs fonctions. Les droits sont accordés séparément.</p>
    <p>Code de connexion de l'établissement : <strong>{schoolId}</strong></p>
    <form onSubmit={e=>{e.preventDefault();run(()=>api(base+"/functions",{enabled_functions:enabled},"PATCH"));}}>
      <fieldset><legend>Fonctions disponibles à la création des comptes</legend>{options.map(f=><label key={f.code}><input type="checkbox" checked={enabled.includes(f.code)} onChange={e=>setEnabled(old=>e.target.checked?[...old,f.code]:old.filter(c=>c!==f.code))}/>{f.label}</label>)}</fieldset>
      <button disabled={busy}>Enregistrer les fonctions proposées</button>
    </form>
    <h3>Déléguer des attributions</h3>
    <p>Une délégation peut couvrir un poste vacant. Chaque droit s'applique à cet établissement et peut être retiré immédiatement.</p>
    <form onSubmit={e=>{e.preventDefault();run(()=>api(base+"/delegations",{user_id:user,permissions:selected,reason,source_function:source,class_cycle:managesClasses?classCycle:"",expires_at:expires?new Date(expires).toISOString():null}));}}>
      <label>Compte bénéficiaire<select required value={user} onChange={e=>setUser(e.target.value)}><option value="">Choisir…</option>{members.map(m=><option key={m.user_id} value={m.user_id}>{m.username}</option>)}</select></label>
      <label>Attributions d'une fonction (facultatif)<select value={source} onChange={e=>setSource(e.target.value)}><option value="">Délégation directe</option>{options.map(f=><option key={f.code} value={f.code}>{f.label}</option>)}</select></label>
      <label>Motif<input required maxLength={240} value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <label>Fin de délégation (facultative)<input type="datetime-local" value={expires} onChange={e=>setExpires(e.target.value)}/></label>
      <fieldset><legend>Permissions explicites</legend>{permissions.map(p=><label key={p}><input type="checkbox" checked={selected.includes(p)} onChange={e=>setSelected(old=>e.target.checked?[...old,p]:old.filter(x=>x!==p))}/>{permissionLabel(p)}</label>)}</fieldset>
      {managesClasses&&<label>Périmètre des classes<select value={classCycle} onChange={e=>setClassCycle(e.target.value)}>
        <option value="">Tout l’établissement</option>
        {Object.entries(classCycles).map(([code,label])=><option key={code} value={code}>{label}</option>)}
      </select></label>}
      {mixedScope&&<p>Accordez séparément la gestion des classes si elle doit être limitée à un cycle.</p>}
      <button disabled={busy||!selected.length||!!mixedScope}>Accorder la délégation</button>
    </form>
    <h3>Historique des délégations</h3>
    <label>Motif du retrait<input value={revokeReason} maxLength={240} onChange={e=>setRevokeReason(e.target.value)}/></label>
    {grants.map(g=><article key={g.id}><strong>{members.find(m=>m.user_id===g.user_id)?.username||g.user_id}</strong> · {g.reason}<p>{g.permissions.map(permissionLabel).join(", ")}{g.class_cycle&&` · ${classCycles[g.class_cycle]||g.class_cycle}`}</p><p>{g.revoked_at?"Retirée : "+g.revocation_reason:g.expires_at?"Échéance : "+new Date(g.expires_at).toLocaleString():"Sans échéance"}</p>{!g.revoked_at&&<button disabled={busy||!revokeReason.trim()} onClick={()=>run(()=>api(base+"/delegations/"+g.id,{reason:revokeReason},"DELETE"))}>Retirer la délégation</button>}</article>)}
    {message&&<p role="status">{message}</p>}
  </section>;
}
