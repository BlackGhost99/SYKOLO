import React, {useEffect,useState} from "react";
import {Button,Card,Status,Table} from "./yem-ui.jsx";

const PROFILE_FIELDS = [
  ["qualification","Diplôme / qualification"],
  ["specialty","Spécialité ou discipline"],
  ["employment_status","Statut professionnel"],
  ["workload","Volume de service / quotité"],
  ["professional_email","Email professionnel"],
  ["professional_phone","Téléphone professionnel"],
];

export default function StaffProfessionalDossier({schoolId,staffId="",own=false,onClose}) {
  const [data,setData]=useState(null);
  const [draft,setDraft]=useState({});
  const [editing,setEditing]=useState(false);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const route=schoolId
    ? `/api/v1/schools/${schoolId}/staff/${own?"me/dossier":staffId+"/dossier"}`
    : "";

  useEffect(()=>{
    if(!route){setLoading(false);setData(null);return;}
    let active=true;
    setData(null);setEditing(false);setError("");setNotice("");setLoading(true);
    fetch(route,{credentials:"same-origin"}).then(async response=>{
      const payload=await response.json();
      if(!response.ok){
        const err=new Error(payload.error||"Accès au dossier refusé.");
        err.status=response.status;
        throw err;
      }
      if(active){setData(payload);setDraft(payload.professional||{});}
    }).catch(err=>{
      if(active)setError(own && err.status===404 ? "" : err.message);
    }).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[route,own]);

  async function save(event){
    event.preventDefault();
    if(!data?.can_edit||busy)return;
    setBusy(true);setError("");setNotice("");
    try {
      const csrf=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
      if(!csrf.ok)throw Error("Votre session a expiré.");
      const token=document.cookie.split("; ").find(item=>item.startsWith("csrftoken="))?.split("=")[1]||"";
      const payload={revision:data.professional.revision};
      PROFILE_FIELDS.forEach(([key])=>{payload[key]=draft[key]||"";});
      const response=await fetch(route,{
        method:"PATCH",credentials:"same-origin",
        headers:{"Content-Type":"application/json","X-CSRFToken":token},
        body:JSON.stringify(payload),
      });
      const result=await response.json();
      if(!response.ok)throw Error(result.error||"Modification refusée.");
      setData(result);setDraft(result.professional);setEditing(false);
      setNotice("Fiche professionnelle actualisée.");
    }catch(err){setError(err.message);}
    finally{setBusy(false);}
  }

  if(!route || (!loading && own && !data && !error))return null;
  if(loading)return <Card title={own?"Ma fiche professionnelle":"Fiche professionnelle du personnel"} icon="idcard"><p role="status">Chargement de la fiche…</p></Card>;
  if(error&&!data)return <Card title="Fiche professionnelle" icon="idcard">
    <p role="alert">{error}</p>
    {onClose&&<Button onClick={onClose}>Retour à l’annuaire</Button>}
  </Card>;
  if(!data)return null;
  const s=data.staff,p=data.professional;
  const formDate=value=>value||"—";

  return <section aria-label={own?"Ma fiche professionnelle":"Fiche professionnelle du personnel"}>
    <Card title={own?"Ma fiche professionnelle":`Fiche professionnelle · ${s.last_name} ${s.first_name}`} icon="idcard">
      <div className="actions">
        {onClose&&<Button onClick={onClose}>Retour à l’annuaire</Button>}
        {data.can_edit&&!editing&&<Button onClick={()=>{setDraft({...p});setEditing(true);setNotice("");}}>Modifier les informations professionnelles</Button>}
      </div>
      <p className="hint">Cette fiche présente les informations professionnelles, les nominations et les affectations. Elle ne contient ni salaire, ni adresse privée, ni documents RH confidentiels.</p>
      {s.photo_url&&<img className="yd-staff-avatar" src={s.photo_url}
        alt={"Photo de "+s.first_name+" "+s.last_name} loading="lazy"/>}
      <div className="two" style={{marginBottom:"1rem"}}>
        <p><strong>Nom et prénom</strong><span style={{display:"block"}}>{s.last_name} {s.first_name}</span></p>
        <p><strong>Matricule du personnel</strong><span style={{display:"block"}}>{s.staff_code}</span></p>
        <p><strong>Poste déclaré</strong><span style={{display:"block"}}>{s.position||"—"}</span></p>
        <p><strong>Date d’entrée</strong><span style={{display:"block"}}>{formDate(s.hired_on)}</span></p>
        <p><strong>Statut de la fiche</strong><span style={{display:"block"}}><Status tone={s.active?"green":"gray"}>{s.active?"Actif":"Archivé"}</Status></span></p>
        <p><strong>Compte YEM</strong><span style={{display:"block"}}>{s.has_account?"Compte lié":"Aucun compte — fiche consultable par l’administration"}</span></p>
      </div>
      {!editing ? <div className="two">
        {PROFILE_FIELDS.map(([key,label])=><p key={key}><strong>{label}</strong><span style={{display:"block"}}>{p[key]||"Non renseigné"}</span></p>)}
      </div> : <form onSubmit={save}>
        <div className="two">
          {PROFILE_FIELDS.map(([key,label])=><label key={key} className="field">{label}
            <input type={key==="professional_email"?"email":key==="professional_phone"?"tel":"text"}
              maxLength={key==="professional_email"?254:key==="professional_phone"?45:key==="qualification"||key==="specialty"?180:100}
              value={draft[key]||""} onChange={event=>setDraft(current=>({...current,[key]:event.target.value}))}/>
          </label>)}
        </div>
        <div className="actions">
          <Button onClick={()=>{setEditing(false);setDraft({...p});}}>Annuler</Button>
          <button type="submit" disabled={busy}>{busy?"Enregistrement…":"Enregistrer la fiche"}</button>
        </div>
      </form>}
      {notice&&<p role="status">{notice}</p>}
      {error&&<p role="alert">{error}</p>}
    </Card>
    <Card title="Fonctions et nominations" icon="layers">
      {data.functions.length?<Table
        headers={["Fonction","Cycle / périmètre","Début","Fin","Statut"]}
        rows={data.functions.map(f=>[
          f.label,f.cycle_label,formDate(f.starts_on),formDate(f.ends_on),
          <Status tone={f.effective?"green":"gray"}>{f.effective?"Exercée":f.active?"Hors période":"Inactive"}</Status>,
        ])}/>:<p className="hint">Aucune fonction officielle enregistrée dans l’organigramme.</p>}
    </Card>
    <Card title="Affectations aux classes" icon="school">
      {data.class_assignments.length?<Table
        headers={["Année","Cycle","Classe","Responsabilité","Statut"]}
        rows={data.class_assignments.map(a=>[
          a.year,a.cycle,a.classroom,a.duty,
          <Status tone={a.active?"green":"gray"}>{a.active?"Active":"Archivée"}</Status>,
        ])}/>:<p className="hint">Aucune affectation à une classe enregistrée.</p>}
    </Card>
  </section>;
}
