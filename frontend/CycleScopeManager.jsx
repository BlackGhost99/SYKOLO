import React,{useEffect,useState} from "react";

async function request(path,body){
  if(body!==undefined){
    const c=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
    if(!c.ok)throw Error("Session expirée.");
  }
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const r=await fetch("/api/v1/"+path,{
    method:body===undefined?"GET":"PATCH",credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:body===undefined?undefined:JSON.stringify(body)
  });
  const d=await r.json();
  if(!r.ok)throw Error(d.error||"Opération refusée.");
  return d;
}

export default function CycleScopeManager({schoolId,cycles,accounts,onSaved}){
  const [member,setMember]=useState("");
  const [globalAccess,setGlobalAccess]=useState(false);
  const [selected,setSelected]=useState([]);
  const [reason,setReason]=useState("");
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  useEffect(()=>{setMember("");setReason("");setSelected([]);setGlobalAccess(false);},[schoolId]);
  const chosen=accounts.find(a=>a.member_id===member);
  const multipleCycles=cycles.length>1;
  const globalAccounts=accounts.filter(a=>a.access_cycle_ids===null);
  const choose=id=>{
    const item=accounts.find(a=>a.member_id===id);
    setMember(id);setGlobalAccess(item?.access_cycle_ids===null);
    setSelected(item?.access_cycle_ids||[]);setMessage("");setReason("");
  };
  async function submit(e){
    e.preventDefault();
    setBusy(true);setMessage("");
    try{
      await request("schools/"+schoolId+"/members/"+member+"/cycle-access",{
        access_cycle_ids:globalAccess?null:selected,
        reason:reason.trim(),
      });
      setMessage("Restrictions enregistrées. Elles s'appliquent dès la prochaine requête.");
      setReason("");
      await onSaved?.();
    }catch(err){setMessage(err.message);}
    finally{setBusy(false);}
  }
  return <section className="card" aria-label="Modifier les cycles d'accès du personnel">
    <h3>Cycles d'accès des comptes existants</h3>
    <p className="hint">Réservé au propriétaire de l'organisation. Le changement de périmètre est immédiat et conserve le motif dans l'audit. Un poste dans l'organigramme ne remplace pas ces autorisations.</p>
    {multipleCycles&&<p className="hint" role="status">{globalAccounts.length} compte(s) non propriétaires sur {accounts.length} disposent actuellement d’un accès global à tous les cycles. Vérifiez chaque situation avant de restreindre : une fonction ou un poste ne prouve pas à lui seul le périmètre autorisé.</p>}
    <form onSubmit={submit}>
      <label className="field">Compte existant
        <select required value={member} onChange={e=>choose(e.target.value)}>
          <option value="">Choisir un compte…</option>
          {accounts.map(a=><option key={a.member_id} value={a.member_id}>{a.name||a.username} ({a.username}){multipleCycles&&a.access_cycle_ids===null?" — Accès global à vérifier":""}</option>)}
        </select>
      </label>
      {chosen&&<fieldset><legend>Périmètre de {chosen.username}</legend>
        {multipleCycles&&chosen.access_cycle_ids===null&&<p className="hint">Ce compte possède actuellement un accès global aux cycles de l’établissement. Le limiter peut rendre certaines fonctions indisponibles jusqu’à leur adaptation aux accès par cycle.</p>}
        <label style={{display:"flex",gap:8}}>
          <input type="radio" name="existing-cycle-scope" checked={globalAccess} onChange={()=>setGlobalAccess(true)}/>
          <span>Accès global à l'établissement</span>
        </label>
        <label style={{display:"flex",gap:8}}>
          <input type="radio" name="existing-cycle-scope" checked={!globalAccess} onChange={()=>setGlobalAccess(false)}/>
          <span>Limiter aux cycles suivants</span>
        </label>
        {!globalAccess&&cycles.map(c=><label key={c.id} style={{display:"flex",gap:8,marginLeft:16}}>
          <input type="checkbox" checked={selected.includes(c.id)} onChange={e=>setSelected(old=>e.target.checked?[...old,c.id]:old.filter(x=>x!==c.id))}/><span>{c.name}</span>
        </label>)}
      </fieldset>}
      <label className="field">Motif obligatoire (8 caractères minimum)
        <input required minLength={8} maxLength={240} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Ex. Affectation à la direction du primaire"/>
      </label>
      <button type="submit" disabled={busy||!member||(!globalAccess&&!selected.length)||reason.trim().length<8}>{busy?"Enregistrement…":"Enregistrer les cycles autorisés"}</button>
    </form>
    {message&&<p role="status">{message}</p>}
  </section>;
}
