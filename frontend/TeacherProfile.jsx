import React, {useEffect,useState} from "react";
import {Button,Card,Icon} from "./yem-ui.jsx";
import "./teacher-profile.css";

const uri = schoolId => "/api/v1/schools/"+schoolId+"/staff/me/profile";
const photoUri = (schoolId,id) => "/api/v1/schools/"+schoolId+"/staff/"+id+"/photo";
async function request(url, method="GET", data) {
  if(method!=="GET") await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(c=>c.startsWith("csrftoken="))?.split("=")[1]||"";
  const headers=method==="GET"?{}:{"X-CSRFToken":csrf};
  if(method==="PATCH")headers["Content-Type"]="application/json";
  const response=await fetch(url,{method,credentials:"same-origin",headers,
    body:method==="PATCH"?JSON.stringify(data):method==="POST"?data:undefined});
  const json=await response.json();
  if(!response.ok)throw Error(json.error||"Opération refusée.");
  return json;
}
async function fitPhoto(file) {
  if (!file || !["image/jpeg","image/png"].includes(file.type) || file.size>8_000_000)
    throw Error("Choisissez une photo JPG ou PNG de 8 Mo maximum.");
  const bitmap=await new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onerror=()=>reject(Error("Lecture du fichier impossible."));
    reader.onload=()=>{
      const picture=new Image();
      picture.onload=()=>resolve(picture);
      picture.onerror=()=>reject(Error("Image illisible."));
      picture.src=reader.result;
    };
    reader.readAsDataURL(file);
  });
  const scale=Math.min(1,512/Math.max(bitmap.width,bitmap.height));
  const canvas=document.createElement("canvas");
  canvas.width=Math.max(1,Math.round(bitmap.width*scale));
  canvas.height=Math.max(1,Math.round(bitmap.height*scale));
  const context=canvas.getContext("2d");
  if(!context)throw Error("Impossible de préparer la photo.");
  context.fillStyle="#fff";
  context.fillRect(0,0,canvas.width,canvas.height);
  context.drawImage(bitmap,0,0,canvas.width,canvas.height);
  for(const q of [0.82,0.68,0.52]){
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/jpeg",q));
    if(blob && blob.size<=350_000)return blob;
  }
  throw Error("La photo reste trop volumineuse après réduction.");
}

export default function TeacherProfile({schoolId}) {
  const [profile,setProfile]=useState(null);
  const [presentation,setPresentation]=useState("");
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [saving,setSaving]=useState(false);
  const [photoRev,setPhotoRev]=useState(0);
  useEffect(()=>{
    let alive=true;
    setProfile(null);setError("");setMessage("");
    request(uri(schoolId)).then(data=>{if(alive){setProfile(data);setPresentation(data.presentation||"");}})
      .catch(e=>{if(alive)setError(e.message);});
    return()=>{alive=false;};
  },[schoolId]);
  const announce=data=>{setProfile(data);setPresentation(data.presentation||"");setPhotoRev(v=>v+1);
    window.dispatchEvent(new CustomEvent("yem:staff-photo-updated",{detail:{schoolId}}));};
  async function changePhoto(file) {
    if(!file)return;
    setSaving(true);setError("");setMessage("");
    try {
      const blob=await fitPhoto(file);
      const form=new FormData();
      form.append("photo",blob,"portrait.jpg");
      announce(await request(photoUri(schoolId,profile.staff_id),"POST",form));
      setMessage("Photo synchronisée avec la fiche du personnel.");
    } catch(e) {setError(e.message);} finally {setSaving(false);}
  }
  async function removePhoto() {
    setSaving(true);setError("");setMessage("");
    try{announce(await request(photoUri(schoolId,profile.staff_id),"DELETE"));
      setMessage("Photo retirée de la fiche du personnel.");}
    catch(e){setError(e.message);}finally{setSaving(false);}
  }
  async function save(event){
    event.preventDefault();setSaving(true);setError("");setMessage("");
    try{announce(await request(uri(schoolId),"PATCH",{revision:profile.revision,presentation}));
      setMessage("Présentation mise à jour.");}
    catch(e){setError(e.message);}finally{setSaving(false);}
  }
  return <div className="teacher-profile">
    <Card title="Mon profil professionnel" icon="idcard"
      subtitle="Votre photo et votre présentation sont visibles par l'administration autorisée de votre établissement.">
      {error&&<p role="alert">{error}</p>}
      {message&&<p role="status">{message}</p>}
      {!profile&&!error&&<p role="status">Chargement de votre fiche Personnel…</p>}
      {profile&&<>
        <div className="teacher-profile-identity">
          {profile.photo_url?<img className="teacher-profile-photo" src={profile.photo_url+"?rev="+photoRev} alt="Ma photo de profil"/>:
            <span className="teacher-profile-photo empty"><Icon name="user" size={40}/></span>}
          <div><h3>{profile.first_name} {profile.last_name}</h3><p>{profile.position}</p><small>Matricule : {profile.staff_code}</small></div>
        </div>
        <div className="actions">
          <label className="yd-btn teacher-photo-picker">Choisir ma photo
            <input aria-label="Choisir une photo de profil" type="file" accept="image/jpeg,image/png"
              disabled={saving} onChange={event=>{changePhoto(event.target.files?.[0]);event.target.value="";}}/>
          </label>
          {profile.photo_url&&<Button disabled={saving} onClick={removePhoto}>Supprimer la photo</Button>}
        </div>
        <form onSubmit={save}>
          <label className="field">Présentation professionnelle (facultative)
            <textarea maxLength={280} rows={3} value={presentation}
              onChange={event=>setPresentation(event.target.value)}
              placeholder="Ex. Enseignant de mathématiques, classes du collège…"/>
          </label>
          <p className="hint">{presentation.length}/280 caractères</p>
          <Button primary type="submit" disabled={saving||presentation===(profile.presentation||"")}>Enregistrer mon profil</Button>
        </form>
        <p className="hint">Le nom, le matricule, la fonction et les affectations sont gérés par l’établissement. Toute modification officielle doit passer par l’administration.</p>
      </>}
    </Card>
  </div>;
}
