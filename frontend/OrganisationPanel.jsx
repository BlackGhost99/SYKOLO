import React, {useEffect, useState} from "react";

const TYPES = {
  maternelle:"Maternelle", primaire:"École primaire", college:"Collège",
  lycee_general:"Lycée général", lycee_technique:"Lycée technique ou professionnel",
  groupe_scolaire:"Groupe scolaire",
};
async function request(path, body, method) {
  if (body !== undefined) {
    const csrfReady = await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
    if (!csrfReady.ok) throw Error("Session de sécurité indisponible.");
  }
  const csrf = document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1] || "";
  const result = await fetch("/api/v1/" + path, {
    credentials:"same-origin",
    method:method || (body===undefined?"GET":"POST"),
    headers:body===undefined?{}:{"Content-Type":"application/json", "X-CSRFToken":csrf},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  if (!result.headers.get("content-type")?.includes("application/json")) {
    throw Error("Réponse inattendue du serveur YEM.");
  }
  const data = await result.json();
  if (!result.ok) throw Error(data.error || "Opération refusée.");
  return data;
}
const endpoint = id=>"schools/"+id+"/organization/";

export default function OrganisationPanel({schoolId,canManage=false}) {
  const [catalog,setCatalog]=useState(null);
  const [rows,setRows]=useState([]);
  const [staff,setStaff]=useState([]);
  const [selectedStaff,setSelectedStaff]=useState("");
  const [functionCode,setFunctionCode]=useState("");
  const [cycleCode,setCycleCode]=useState("");
  const [start,setStart]=useState("");
  const [end,setEnd]=useState("");
  const [editing,setEditing]=useState(null);
  const [editStart,setEditStart]=useState("");
  const [editEnd,setEditEnd]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [failure,setFailure]=useState("");
  const base=endpoint(schoolId);
  const chosen=(catalog?.positions||[]).find(p=>p.code===functionCode);
  const grouped=(catalog?.positions||[]).reduce((out,p)=>{
    (out[p.family] ||= []).push(p);
    return out;
  },{});

  async function refresh() {
    const [a,b]=await Promise.all([
      request(base+"positions"),request(base+"appointments"),
    ]);
    setCatalog(a);setRows(b.appointments||[]);setStaff(b.staff_options||[]);
  }
  useEffect(()=>{
    let alive=true;
    setCatalog(null);setRows([]);setStaff([]);setSelectedStaff("");setFunctionCode("");setCycleCode("");setFailure("");setMessage("");
    Promise.all([request(base+"positions"),request(base+"appointments")]).then(([a,b])=>{
      if (!alive) return;
      setCatalog(a);setRows(b.appointments||[]);setStaff(b.staff_options||[]);
    }).catch(err=>{if(alive)setFailure(err.message);});
    return()=>{alive=false;};
  },[schoolId]);

  async function run(action,success) {
    setBusy(true);setMessage("");setFailure("");
    try {await action();await refresh();setMessage(success);}
    catch(err){setFailure(err.message);}
    finally {setBusy(false);}
  }
  const qualified=staff.filter(p=>p.active);
  const cycleNames=catalog?.cycle_labels||{};

  if (!catalog) return <section className="card" style={{marginTop:"1rem"}}>
    <h2>Organigramme et fonctions</h2>
    <p role="status">{failure||"Chargement de l'organisation…"}</p>
  </section>;

  return <section className="card" aria-label="Organigramme de l'établissement" style={{marginTop:"1rem"}}>
    <h2>Organigramme et fonctions</h2>
    <p className="hint">Type : <strong>{TYPES[catalog.school_type]||"Établissement à classifier"}</strong>.
      {" "}Cycles : {(catalog.education_cycles||[]).map(c=>cycleNames[c]||c).join(" · ")||"Aucun renseigné"}.
    </p>
    <p className="hint">Les postes proposés dépendent des cycles enseignés. Plusieurs fonctions peuvent être attribuées à une même personne, dans différents cycles.</p>
    {!catalog.positions.length&&<p role="status">Il faut d'abord classifier l'établissement et ses cycles dans la console super-administrateur.</p>}

    {canManage&&catalog.positions.length>0&&<form onSubmit={e=>{
      e.preventDefault();
      run(async()=>{
        await request(base+"appointments",{
          staff:selectedStaff,function_code:functionCode,cycle_code:chosen?.scope==="cycle"?cycleCode:"",
          starts_on:start||null,ends_on:end||null,
        });
        setFunctionCode("");setCycleCode("");setStart("");setEnd("");
      },"Fonction attribuée et enregistrée dans l'audit.");
    }}>
      <h3>Attribuer une fonction au personnel</h3>
      <div className="two">
        <label className="field">Personnel
          <select required value={selectedStaff} onChange={e=>setSelectedStaff(e.target.value)}>
            <option value="">Sélectionner une fiche du personnel…</option>
            {qualified.map(p=><option key={p.id} value={p.id}>{p.name} ({p.staff_code}){!p.has_account?" — sans compte":""}</option>)}
          </select>
        </label>
        <label className="field">Poste administratif ou pédagogique
          <select required value={functionCode} onChange={e=>{setFunctionCode(e.target.value);setCycleCode("");}}>
            <option value="">Sélectionner une fonction…</option>
            {Object.entries(grouped).map(([family,functions])=><optgroup key={family} label={family}>
              {functions.map(p=><option key={p.code} value={p.code}>{p.label}</option>)}
            </optgroup>)}
          </select>
        </label>
        {chosen?.scope==="cycle"&&<label className="field">Cycle de responsabilité
          <select required value={cycleCode} onChange={e=>setCycleCode(e.target.value)}>
            <option value="">Choisir le cycle…</option>
            {chosen.allowed_cycles.map(c=><option key={c} value={c}>{cycleNames[c]||c}</option>)}
          </select>
        </label>}
        {chosen?.scope==="school"&&<p className="hint">Périmètre : établissement entier.</p>}
        <label className="field">Début de fonction (facultatif)
          <input type="date" value={start} onChange={e=>setStart(e.target.value)}/>
        </label>
        <label className="field">Fin de fonction (facultatif)
          <input type="date" min={start||undefined} value={end} onChange={e=>setEnd(e.target.value)}/>
        </label>
      </div>
      <button type="submit" disabled={busy||!selectedStaff||!functionCode||(chosen?.scope==="cycle"&&!cycleCode)}>Enregistrer la nomination</button>
      {!qualified.length&&<p className="hint">Aucune fiche active du personnel. Créez d'abord une fiche dans « Personnel et enseignants ».</p>}
    </form>}

    <h3>Fonctions enregistrées ({rows.length})</h3>
    {rows.length===0?<p className="hint">Aucune nomination. Les responsables existants conservent leurs droits actuels.</p>:
      <div style={{display:"grid",gap:"0.8rem"}}>
        {rows.map(row=><div key={row.id} style={{border:"1px solid var(--border, #dce2e4)",borderRadius:12,padding:"0.9rem"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:12,flexWrap:"wrap"}}>
            <div>
              <strong>{row.staff_name}</strong> <small>({row.staff_code})</small>
              <div>{catalog.positions.find(p=>p.code===row.function_code)?.label||row.function_code}</div>
              <small>{row.cycle_label} · {row.effective?"En fonction":row.active?"En attente / hors période":"Fonction suspendue"}</small>
              {!row.has_account&&<div className="hint">Aucun compte YEM lié à cette fiche.</div>}
              <div className="hint">Du {row.starts_on||"début non défini"} au {row.ends_on||"terme non défini"}</div>
            </div>
            {canManage&&<div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
              <button type="button" disabled={busy} onClick={()=>{setEditing(row.id);setEditStart(row.starts_on||"");setEditEnd(row.ends_on||"");}}>Modifier les dates</button>
              <button type="button" disabled={busy} onClick={()=>run(
                ()=>request(base+"appointments/"+row.id,{revision:row.revision,active:!row.active},"PATCH"),
                row.active?"Nomination suspendue.":"Nomination réactivée."
              )}>{row.active?"Suspendre":"Réactiver"}</button>
            </div>}
          </div>
          {editing===row.id&&<form onSubmit={e=>{
            e.preventDefault();
            run(async()=>{
              await request(base+"appointments/"+row.id,{revision:row.revision,starts_on:editStart||null,ends_on:editEnd||null},"PATCH");
              setEditing(null);
            },"Dates de nomination mises à jour.");
          }} style={{marginTop:"0.8rem"}}>
            <div className="two">
              <label className="field">Début<input type="date" value={editStart} onChange={e=>setEditStart(e.target.value)}/></label>
              <label className="field">Fin<input type="date" min={editStart||undefined} value={editEnd} onChange={e=>setEditEnd(e.target.value)}/></label>
            </div>
            <button disabled={busy} type="submit">Enregistrer les dates</button>{" "}
            <button type="button" disabled={busy} onClick={()=>setEditing(null)}>Annuler</button>
          </form>}
        </div>)}
      </div>
    }
    <p className="hint" style={{marginTop:"1rem"}}>
      Sécurité : une nomination indique le poste et son périmètre, mais n'ajoute aucun droit d'accès aux élèves, notes ou finances.
      Les permissions YEM restent attribuées séparément, et les délégations réellement limitées par cycle seront activées après contrôle de chaque API métier.
    </p>
    {message&&<p role="status" aria-live="polite">{message}</p>}
    {failure&&<p role="alert">{failure}</p>}
  </section>;
}

export function MySchoolFunctions({schoolId}) {
  const [functions,setFunctions]=useState([]);
  useEffect(()=>{
    let active=true;setFunctions([]);
    request(endpoint(schoolId)+"my-appointments").then(x=>{
      if(active)setFunctions(x.appointments||[]);
    }).catch(()=>{if(active)setFunctions([]);});
    return()=>{active=false;};
  },[schoolId]);
  if(!functions.length) return null;
  return <div className="yd-real-body" aria-label="Mes fonctions scolaires">
    <div className="card">
      <h3>Mes fonctions dans cet établissement</h3>
      {functions.map(f=><p key={f.id}><strong>{f.function_label||f.function_code.replaceAll("_"," ")}</strong> · {f.cycle_label}</p>)}
      <p className="hint">Vos fonctions ne remplacent pas les permissions de votre compte YEM.</p>
    </div>
  </div>;
}
