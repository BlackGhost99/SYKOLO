import React, {useEffect, useState} from "react";

export function SchoolRequirements({schema, child, fields, onFields, answers, onAnswers, loading, error}) {
  if (loading) return <p role="status" className="yp-school-form-loading">Chargement de la fiche exigée par l'établissement…</p>;
  if (error) return <p role="alert" className="yp-error">{error}</p>;
  if (!schema) return <p className="yp-muted">Choisissez une classe pour afficher le dossier demandé par l'établissement.</p>;
  function valueFor(item) {
    if (Object.prototype.hasOwnProperty.call(fields, item.key)) return fields[item.key];
    if (item.key === "date_of_birth") return child?.date_of_birth || "";
    return child?.profile?.[item.key] || "";
  }
  return <section className="yp-school-form">
    <h4>Fiche demandée par {schema.school_name}</h4>
    <p>Ces questions et justificatifs sont propres à l'établissement et à la voie d'admission sélectionnée.</p>
    {!schema.configured && <p className="yp-muted">L'école n'a pas encore personnalisé sa liste de pièces. Les documents proposés restent indicatifs, sauf pièces exigées par la voie d'admission.</p>}
    <div className="yp-two">
      {(schema.fields || []).map(item=><label className="yp-field" key={item.key}>
        {item.label} {item.required&&<span className="yp-required">Obligatoire</span>}
        {item.type==="select" ? <select required={item.required} value={valueFor(item)}
          onChange={e=>onFields({...fields,[item.key]:e.target.value})}>
          <option value="">Sélectionner</option>
          {(item.options || []).map(option=><option key={option} value={option}>{option==="F"?"Féminin":option==="M"?"Masculin":option}</option>)}
        </select> :
        <input type={item.type==="date"?"date":"text"} required={item.required}
          maxLength={item.max_length||120} value={valueFor(item)}
          onChange={e=>onFields({...fields,[item.key]:e.target.value})}/>}
      </label>)}
    </div>
    {(schema.custom_fields||[]).length>0 && <div className="yp-custom-fields">
      <h4>Questions complémentaires de l'établissement</h4>
      <div className="yp-two">{schema.custom_fields.map(item=><label key={item.key} className="yp-field">
        {item.label} {item.required&&<span className="yp-required">Obligatoire</span>}
        {item.type==="select"||item.type==="yesno" ? <select required={item.required}
          value={item.type==="yesno" ? (answers[item.key]===true?"yes":answers[item.key]===false?"no":"") : answers[item.key]||""}
          onChange={e=>onAnswers({...answers,[item.key]:item.type==="yesno"?e.target.value==="yes":e.target.value})}>
            <option value="">Sélectionner</option>
            {(item.type==="yesno" ? [["yes","Oui"],["no","Non"]] : (item.options||[]).map(v=>[v,v]))
              .map(([key,label])=><option key={key} value={key}>{label}</option>)}
          </select> : item.type==="textarea" ? <textarea required={item.required} maxLength={1000}
            value={answers[item.key]||""} onChange={e=>onAnswers({...answers,[item.key]:e.target.value})}/> :
          <input required={item.required}
            type={item.type==="date"?"date":item.type==="number"?"number":"text"}
            value={answers[item.key]??""} maxLength={item.type==="text"?255:undefined}
            onChange={e=>onAnswers({...answers,[item.key]:item.type==="number"?(e.target.value===""?"":Number(e.target.value)):e.target.value})}/>}
      </label>)}</div>
    </div>}
    <div className="yp-required-documents">
      <h4>Pièces demandées pour cette candidature</h4>
      {(schema.documents||[]).length?schema.documents.map(d=><div className="yp-required-doc" key={d.key}>
        <span aria-hidden="true">▤</span><span>{d.label}</span>
        <b className={d.required?"required":"optional"}>{d.required?"Obligatoire":"Facultatif"}</b>
      </div>):<p className="yp-muted">Aucune pièce supplémentaire demandée pour cette classe.</p>}
      <p className="yp-muted">Après le dépôt de la demande, vous pourrez transmettre les fichiers PDF ou photos directement depuis « Mes demandes ». L'école devra les vérifier avant de les accepter.</p>
    </div>
  </section>;
}

async function compressPhoto(file) {
  if (!file || !["image/jpeg","image/png"].includes(file.type) || file.size>8_000_000)
    throw Error("Choisissez une photo JPG ou PNG de 8 Mo maximum.");
  if (typeof window === "undefined") throw Error("Téléversement non disponible.");
  const bitmap = await new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onerror=()=>reject(Error("Impossible de lire la photo."));
    reader.onload=()=>{const picture=new Image();picture.onload=()=>resolve(picture);picture.onerror=()=>reject(Error("Photo illisible."));picture.src=reader.result;};
    reader.readAsDataURL(file);
  });
  const scale=Math.min(1,512/Math.max(bitmap.width,bitmap.height));
  const canvas=document.createElement("canvas");
  canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));
  const ctx=canvas.getContext("2d");
  if (!ctx) throw Error("Impossible de préparer la photo sur cet appareil.");
  ctx.fillStyle="#ffffff";ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
  for (const quality of [0.82,0.68,0.5]) {
    const content=canvas.toDataURL("image/jpeg",quality);
    if(content.length<465000)return content;
  }
  throw Error("Photo trop volumineuse. Choisissez une photo plus petite.");
}

export function FamilyProfileEditor({child, api, onUpdated}) {
  const [open,setOpen]=useState(false);
  const [saving,setSaving]=useState(false);
  const [error,setError]=useState("");
  const [success,setSuccess]=useState("");
  const [form,setForm]=useState(null);
  useEffect(()=>{setForm(null);setOpen(false);setError("");},[child.id,child.revision]);
  const start=()=>{setForm({first_name:child.first_name,last_name:child.last_name,
    date_of_birth:child.date_of_birth||"",profile:{...child.profile}});setOpen(v=>!v);};
  const fields=[["place_of_birth","Lieu de naissance"],["nationality","Nationalité"],
    ["address","Adresse ou quartier"],["previous_school","Établissement précédent"]];
  async function save(e) {
    e.preventDefault();setSaving(true);setError("");setSuccess("");
    try {
      await api("parents/family-children/"+child.id,{
        ...form,revision:child.revision,
      },"PUT");
      await onUpdated();
      setSuccess("Profil enregistré. Les candidatures déjà déposées restent soumises à la vérification de l'école.");
      setOpen(false);
    } catch(ex) {setError(ex.message);}finally{setSaving(false);}
  }
  async function sendPhoto(e) {
    const file=e.target.files?.[0];e.target.value="";
    if(!file)return;
    setSaving(true);setError("");setSuccess("");
    try {
      const encoded=await compressPhoto(file);
      await api("parents/family-children/"+child.id+"/photo",{photo:encoded});
      await onUpdated();
      setSuccess("Photo privée enregistrée. L'école pourra la consulter dans votre candidature.");
    } catch(ex){setError(ex.message);}finally{setSaving(false);}
  }
  return <div className="yp-family-customizer">
    <div className="yp-family-portrait">
      {child.photo_url?<img src={child.photo_url+"?rev="+child.revision} alt={"Photo de "+child.first_name} loading="lazy"/>:
        <div className="yp-family-portrait-placeholder" aria-hidden="true">◉</div>}
      <div><strong>Photo de profil</strong><small>Visible uniquement par vous et par les établissements destinataires de votre dossier.</small>
        <label className="yp-upload-button">Choisir une photo
          <input type="file" accept="image/jpeg,image/png" disabled={saving} onChange={sendPhoto}/>
        </label></div>
    </div>
    <button type="button" className="yp-button" onClick={start}>{open?"Fermer":"Personnaliser le profil"}</button>
    {error&&<p role="alert" className="yp-error">{error}</p>}
    {success&&<p role="status" className="yp-success">{success}</p>}
    {open&&form&&<form onSubmit={save}>
      <h4>Informations personnelles de l'enfant</h4>
      <div className="yp-two">
        <label className="yp-field">Prénom<input required maxLength={120} value={form.first_name}
          onChange={e=>setForm(v=>({...v,first_name:e.target.value}))}/></label>
        <label className="yp-field">Nom<input required maxLength={120} value={form.last_name}
          onChange={e=>setForm(v=>({...v,last_name:e.target.value}))}/></label>
        <label className="yp-field">Naissance<input type="date" value={form.date_of_birth}
          onChange={e=>setForm(v=>({...v,date_of_birth:e.target.value}))}/></label>
        <label className="yp-field">Sexe<select value={form.profile.gender||""}
          onChange={e=>setForm(v=>({...v,profile:{...v.profile,gender:e.target.value}}))}>
          <option value="">Non renseigné</option><option value="F">Féminin</option><option value="M">Masculin</option>
        </select></label>
        {fields.map(([key,label])=><label key={key} className="yp-field">{label}<input
          maxLength={key==="address"?255:key==="previous_school"?180:key==="nationality"?80:120}
          value={form.profile[key]||""}
          onChange={e=>setForm(v=>({...v,profile:{...v.profile,[key]:e.target.value}}))}/></label>)}
      </div>
      <button className="yp-button yp-primary" disabled={saving}>{saving?"Enregistrement…":"Enregistrer les modifications"}</button>
      <p className="yp-muted">La fiche scolaire officielle n'est pas modifiée automatiquement : l'établissement doit valider les renseignements reçus.</p>
    </form>}
  </div>;
}

async function sendDocument(applicationId, code, file) {
  if (file.size>2_000_000) throw Error("Taille maximale : 2 Mo par document.");
  await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const form=new FormData();form.append("file",file);
  const response=await fetch("/api/v1/parents/applications/"+applicationId+"/documents/"+code,{
    method:"POST",credentials:"same-origin",headers:{"X-CSRFToken":csrf},body:form,
  });
  if (!response.ok) {
    const data=await response.json().catch(()=>({}));
    throw Error(data.error||"L'envoi du document a échoué.");
  }
}

const DOC_STATUS={
  missing:"À transmettre",pending:"En attente de vérification",verified:"Vérifié",rejected:"À remplacer",
};

export function ParentAdmissionDocuments({application,api}) {
  const [open,setOpen]=useState(false);
  const [documents,setDocuments]=useState([]);
  const [busy,setBusy]=useState("");
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const required=application.document_requirements||[];
  async function refresh(){const data=await api("parents/applications/"+application.id+"/documents");setDocuments(data.documents||[]);}
  useEffect(()=>{
    if(!open)return;
    let active=true;
    api("parents/applications/"+application.id+"/documents").then(data=>{if(active)setDocuments(data.documents||[])})
      .catch(e=>{if(active)setError(e.message)});
    return()=>{active=false;};
  },[application.id,open,api]);
  async function upload(event,code) {
    const file=event.target.files?.[0];event.target.value="";
    if(!file)return;
    setBusy(code);setError("");setMessage("");
    try {await sendDocument(application.id,code,file);await refresh();setMessage("Pièce enregistrée et transmise à l'établissement pour vérification.");}
    catch(e){setError(e.message);}finally{setBusy("");}
  }
  return <section className="yp-parent-docs">
    <button type="button" className="yp-button" onClick={()=>setOpen(v=>!v)}>
      {open?"Fermer les pièces justificatives":"Pièces justificatives et documents"}
      {required.length>0?" ("+required.length+")":""}
    </button>
    {open&&<>
      <p>Documents prévus par l'établissement lors du dépôt. Seul le secrétariat peut les vérifier.</p>
      {error&&<p role="alert" className="yp-error">{error}</p>}
      {message&&<p role="status" className="yp-success">{message}</p>}
      {documents.length===0&&<p className="yp-muted">Aucun justificatif demandé dans ce dossier.</p>}
      {documents.map(d=><div className="yp-doc-row" key={d.key}>
        <div><strong>{d.label}</strong><small>{d.required?"Obligatoire":"Facultatif"} · {DOC_STATUS[d.status]||d.status}</small>
          {d.review_reason&&<small>Motif de refus : {d.review_reason}</small>}
          {d.filename&&<small>{d.filename}</small>}</div>
        <div>{d.download_url&&<a className="yp-button" href={d.download_url}>Voir le fichier</a>}
          {["submitted","review"].includes(application.status)&&<label className="yp-upload-button">
            {busy===d.key?"Envoi…":d.uploaded?"Remplacer":"Transmettre"}
            <input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
              disabled={!!busy} onChange={e=>upload(e,d.key)}/>
          </label>}</div>
      </div>)}
    </>}
  </section>;
}
