import React, {useEffect,useState} from "react";

const DOMAIN_LABELS = {
  view:"Accès", members:"Utilisateurs", roles:"Rôles", settings:"Paramètres",
  audit:"Audit", organization:"Organigramme", academic:"Structure académique", classes:"Classes",
  admissions:"Admissions", parents:"Accès parents", students:"Élèves",
  staff:"Personnel", curriculum:"Matières et programmes", assessments:"Évaluations",
  reports:"Bulletins", deliberations:"Conseils", timetable:"Emplois du temps",
  attendance:"Présences et absences", finance:"Finances",
};
const ACTION_LABELS = {
  read:"Consulter", manage:"Administrer", write:"Modifier / enregistrer",
  view:"Accéder", publish:"Publier", decide:"Décider", enroll:"Inscrire",
  finalize:"Clôturer", amend:"Rectifier", receive:"Encaisser",
  reverse:"Annuler un encaissement", approve:"Contrôler / approuver", deposit:"Déposer les fonds",
};

async function api(path,payload,method){
  if(payload!==undefined){
    const csrfReady=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
    if(!csrfReady.ok) throw Error("Session expirée ou non sécurisée.");
  }
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const r=await fetch("/api/v1/"+path,{
    credentials:"same-origin",method:method||(payload===undefined?"GET":"POST"),
    headers:payload===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:payload===undefined?undefined:JSON.stringify(payload)
  });
  if(!r.headers.get("content-type")?.includes("application/json"))throw Error("Service de rôles indisponible.");
  const data=await r.json();
  if(!r.ok)throw Error(data.error||"Opération refusée.");
  return data;
}
export function permissionLabel(value){
  if(value==="school.staff.dossier.read")return "Personnel — Consulter les fiches professionnelles";
  if(value==="school.staff.dossier.manage")return "Personnel — Modifier les fiches professionnelles";
  const parts=value.split(".");
  const domain=DOMAIN_LABELS[parts[1]]||parts[1];
  const action=ACTION_LABELS[parts[2]]||parts[2]||"";
  return domain+" — "+action;
}

export default function RoleManager({schoolId,canManageRoles=false}){
  const [roles,setRoles]=useState([]);
  const [available,setAvailable]=useState([]);
  const [selected,setSelected]=useState("new");
  const [code,setCode]=useState("");
  const [label,setLabel]=useState("");
  const [permissions,setPermissions]=useState(["school.view"]);
  const [busy,setBusy]=useState(false);
  const [status,setStatus]=useState("");
  const [failure,setFailure]=useState("");
  const base="schools/"+schoolId+"/roles";
  const chosen=roles.find(r=>r.id===selected);
  const grouped=available.reduce((acc,p)=>{
    const group=p.split(".")[1]||"autres";
    (acc[group] ||= []).push(p);
    return acc;
  },{});

  function selectRole(id,collection=roles){
    setSelected(id);
    const role=collection.find(r=>r.id===id);
    setCode(role?.code||"");
    setLabel(role?.label||"");
    setPermissions(role?[...role.permissions]:["school.view"]);
  }
  async function reload(){
    const value=await api(base);
    setRoles(value.roles||[]);
    setAvailable(value.available_permissions||[]);
    if(selected!=="new") selectRole(selected,value.roles||[]);
  }
  useEffect(()=>{
    let alive=true;
    setSelected("new");setCode("");setLabel("");setPermissions(["school.view"]);setRoles([]);setAvailable([]);setFailure("");setStatus("");
    api(base).then(d=>{
      if(!alive)return;
      setRoles(d.roles||[]);setAvailable(d.available_permissions||[]);
    }).catch(e=>{if(alive)setFailure(e.message);});
    return()=>{alive=false;};
  },[schoolId]);
  function toggle(item){setPermissions(old=>old.includes(item)?old.filter(x=>x!==item):[...old,item]);}

  async function submit(e){
    e.preventDefault();
    if(!canManageRoles)return;
    setBusy(true);setFailure("");setStatus("");
    try{
      const data={label:label.trim(),permissions:[...new Set(permissions)].sort()};
      if(selected==="new"){
        await api(base,{...data,code:code.trim().toLowerCase()});
      }else{
        await api(base+"/"+selected,{...data,revision:chosen.revision},"PATCH");
      }
      await reload();
      setStatus(selected==="new"?"Nouveau rôle créé. Vous pouvez ensuite le choisir lors de la création d'un compte.":"Permissions du rôle enregistrées.");
      if(selected==="new") selectRole("new",[]);
    }catch(err){setFailure(err.message);}
    finally{setBusy(false);}
  }
  return <section className="card" aria-label="Gestion des rôles applicatifs" style={{marginTop:"1rem"}}>
    <h2>Rôles et droits d'accès</h2>
    <p className="hint">Le poste dans l'organigramme décrit la fonction d'une personne ; le rôle YEM détermine les opérations qu'elle peut effectuer.</p>
    <p role="status" className="hint"><strong>Attention :</strong> ces permissions s'appliquent aujourd'hui à l'établissement entier. N'accordez pas de droit aux notes, aux élèves ou aux finances pour limiter un responsable à un seul cycle tant que les contrôles métiers par cycle ne sont pas activés.</p>
    <label className="field">Rôle à afficher ou modifier
      <select value={selected} onChange={e=>selectRole(e.target.value)}>
        <option value="new">Créer un nouveau rôle</option>
        {roles.map(r=><option key={r.id} value={r.id}>{r.label} ({r.code})</option>)}
      </select>
    </label>
    <form onSubmit={submit}>
      <div className="two">
        <label className="field">Code du rôle
          <input required disabled={!canManageRoles||selected!=="new"} maxLength={48} pattern="[a-z][a-z0-9_-]{1,47}"
            value={code} onChange={e=>setCode(e.target.value)} placeholder="ex : responsable_etudes"/>
        </label>
        <label className="field">Intitulé
          <input required disabled={!canManageRoles} maxLength={100} value={label}
            onChange={e=>setLabel(e.target.value)} placeholder="Ex. Responsable pédagogique"/>
        </label>
      </div>
      <h3>Permissions attribuées ({permissions.length})</h3>
      <p className="hint">Chaque permission est distincte. Les nouvelles autorisations sont vérifiées côté serveur et ne peuvent pas dépasser les droits du responsable qui crée le rôle.</p>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(230px,1fr))",gap:12,marginBottom:"1rem"}}>
        {Object.entries(grouped).map(([group,entries])=><details key={group} style={{border:"1px solid #dfe4e4",padding:"0.7rem",borderRadius:10}}>
          <summary style={{cursor:"pointer",fontWeight:600}}>{DOMAIN_LABELS[group]||group} · {entries.filter(x=>permissions.includes(x)).length}/{entries.length}</summary>
          <div style={{display:"grid",gap:8,marginTop:10}}>
            {entries.map(p=><label key={p} style={{display:"flex",gap:8,alignItems:"flex-start"}}>
              <input disabled={!canManageRoles} type="checkbox" checked={permissions.includes(p)} onChange={()=>toggle(p)}/>
              <span><span style={{display:"block"}}>{permissionLabel(p)}</span><small>{p}</small></span>
            </label>)}
          </div>
        </details>)}
      </div>
      {canManageRoles&&<button type="submit" disabled={busy||!code||!label}>{busy?"Enregistrement…":selected==="new"?"Créer le rôle":"Mettre à jour les droits"}</button>}
      {!canManageRoles&&<p className="hint">Consultation seule : demandez à la direction de modifier les droits.</p>}
    </form>
    {status&&<p role="status" aria-live="polite">{status}</p>}
    {failure&&<p role="alert">{failure}</p>}
  </section>;
}
