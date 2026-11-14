import React, {useEffect,useState} from "react";
import {Button,Card,Icon} from "./yem-ui.jsx";
import "./school-branding.css";

const route = schoolId => "/api/v1/schools/"+schoolId+"/branding";

async function identityRequest(url, method="GET", payload){
  if(method!=="GET"){
    const csrfResponse=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
    if(!csrfResponse.ok)throw Error("Session expirée. Reconnectez-vous.");
  }
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const headers=method==="GET"?{}:{"X-CSRFToken":csrf};
  if(method==="POST" && !(payload instanceof FormData))headers["Content-Type"]="application/json";
  if(method==="DELETE")headers["Content-Type"]="application/json";
  const response=await fetch(url,{
    credentials:"same-origin",method,headers,
    body:payload instanceof FormData?payload:
      payload===undefined?undefined:JSON.stringify(payload),
  });
  const data=await response.json();
  if(!response.ok)throw Error(data.error||"Échec de mise à jour de l'identité.");
  return data;
}

/* Préparer de vraies images légères : aucune donnée en base64 dans les paramètres. */
async function fitSchoolImage(file,kind){
  if(!file || !["image/jpeg","image/png"].includes(file.type) || file.size>8_000_000)
    throw Error("Choisissez une image JPG ou PNG de 8 Mo maximum.");
  const picture=await new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onerror=()=>reject(Error("Impossible de lire l'image."));
    reader.onload=()=>{
      const img=new Image();
      img.onload=()=>resolve(img);
      img.onerror=()=>reject(Error("Image illisible."));
      img.src=reader.result;
    };
    reader.readAsDataURL(file);
  });
  const [width,height,limit]=kind==="logo"?[480,480,350_000]:[1800,540,900_000];
  const scale=Math.min(1,width/picture.width,height/picture.height);
  const canvas=document.createElement("canvas");
  canvas.width=Math.max(1,Math.round(picture.width*scale));
  canvas.height=Math.max(1,Math.round(picture.height*scale));
  const context=canvas.getContext("2d");
  if(!context)throw Error("Traitement de l'image indisponible.");
  if(kind==="banner"){context.fillStyle="#ffffff";context.fillRect(0,0,canvas.width,canvas.height);}
  context.drawImage(picture,0,0,canvas.width,canvas.height);
  if(file.type==="image/png"&&kind==="logo"){
    const png=await new Promise(resolve=>canvas.toBlob(resolve,"image/png"));
    if(png&&png.size<=limit)return {blob:png,name:"logo.png"};
  }
  for(const quality of [0.88,0.76,0.64,0.50]){
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/jpeg",quality));
    if(blob&&blob.size<=limit)return {blob,name:kind+".jpg"};
  }
  throw Error("L'image reste trop lourde : choisissez une photo plus simple.");
}

export default function SchoolBrandingSettings({schoolId,canEdit=false,onUpdated}){
  const [branding,setBranding]=useState(null);
  const [city,setCity]=useState("");
  const [tagline,setTagline]=useState("");
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  useEffect(()=>{
    let active=true;
    setLoading(true);setBranding(null);setError("");setMessage("");
    identityRequest(route(schoolId)).then(data=>{
      if(active){setBranding(data);setCity(data.city||"");setTagline(data.tagline||"");}
    }).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setLoading(false)});
    return()=>{active=false};
  },[schoolId]);
  function publish(updated){
    setBranding(updated);setCity(updated.city||"");setTagline(updated.tagline||"");
    onUpdated?.(updated);
    window.dispatchEvent(new CustomEvent("yem:school-branding-updated",{detail:{schoolId}}));
  }
  async function save(event){
    event.preventDefault();setBusy(true);setError("");setMessage("");
    try{
      const updated=await identityRequest(route(schoolId),"POST",{
        revision:branding.revision,city:city.trim(),tagline:tagline.trim(),
      });
      publish(updated);setMessage("Informations de l'établissement synchronisées.");
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function changeImage(kind,file){
    if(!file)return;
    setBusy(true);setError("");setMessage("");
    try{
      const resized=await fitSchoolImage(file,kind);
      const form=new FormData();
      form.append("revision",String(branding.revision));
      form.append("image",resized.blob,resized.name);
      const updated=await identityRequest(route(schoolId)+"/"+kind,"POST",form);
      publish(updated);setMessage((kind==="logo"?"Logo":"Bannière")+" de l'établissement synchronisé(e).");
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function deleteImage(kind){
    setBusy(true);setError("");setMessage("");
    try{
      const updated=await identityRequest(route(schoolId)+"/"+kind,"DELETE",{revision:branding.revision});
      publish(updated);setMessage("Image de l'établissement retirée.");
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <div className="school-identity-settings">
    <Card title="Identité de l'établissement" icon="school" subtitle="Les mêmes éléments seront visibles dans les interfaces PC de tous les rôles de cette école. Le logo et les couleurs de YEM restent inchangés.">
      {error&&<p role="alert" className="pc-alert">{error}</p>}
      {message&&<p role="status">{message}</p>}
      {loading&&<p role="status">Chargement de l'identité de l'établissement…</p>}
      {branding&&<>
        <div className="school-identity-preview" aria-label="Prévisualisation de la bannière de l'établissement">
          {branding.banner_url&&<img className="school-identity-preview-banner" src={branding.banner_url} alt="Bannière de l'établissement"/>}
          <div className="school-identity-preview-overlap">
            {branding.logo_url?<img className="school-identity-preview-logo" src={branding.logo_url} alt="Logo de l'établissement"/>:
              <span className="school-identity-preview-fallback"><Icon name="school" size={28}/></span>}
            <div><strong>{branding.name}</strong><span>{branding.city||"Ville non renseignée"}</span>
              {branding.tagline&&<small>{branding.tagline}</small>}</div>
          </div>
        </div>
        <form onSubmit={save}>
          <div className="two">
            <label className="field">Nom de l'établissement
              <input readOnly value={branding.name} title="Nom enregistré dans la fiche de l'établissement"/>
            </label>
            <label className="field">Ville (facultatif)
              <input maxLength={120} value={city} disabled={!canEdit||busy}
                placeholder="Ex. Libreville" onChange={e=>setCity(e.target.value)}/>
            </label>
          </div>
          <label className="field">Devise / slogan (facultatif)
            <input maxLength={160} value={tagline} disabled={!canEdit||busy}
              placeholder="Ex. Savoir, respect et réussite" onChange={e=>setTagline(e.target.value)}/>
          </label>
          {canEdit&&<Button primary type="submit" disabled={busy||
            (city.trim()===(branding.city||"")&&tagline.trim()===(branding.tagline||""))}>Enregistrer les informations</Button>}
        </form>
        <div className="school-identity-images">
          <section>
            <h3>Logo de l'établissement</h3>
            <p className="hint">À droite des pages et à côté du nom de l'école. Le logo YEM en haut à gauche ne change pas.</p>
            {canEdit&&<label className="yd-btn school-identity-picker">Choisir un logo
              <input aria-label="Choisir le logo de l'établissement" type="file" accept="image/jpeg,image/png"
                disabled={busy} onChange={e=>{changeImage("logo",e.target.files?.[0]);e.target.value="";}}/>
            </label>}
            {canEdit&&branding.logo_url&&<Button onClick={()=>deleteImage("logo")} disabled={busy}>Retirer le logo de l'école</Button>}
          </section>
          <section>
            <h3>Bannière de l'établissement</h3>
            <p className="hint">Une photo horizontale de l'école, idéalement au format panoramique.</p>
            {canEdit&&<label className="yd-btn school-identity-picker">Choisir une bannière
              <input aria-label="Choisir la bannière de l'établissement" type="file" accept="image/jpeg,image/png"
                disabled={busy} onChange={e=>{changeImage("banner",e.target.files?.[0]);e.target.value="";}}/>
            </label>}
            {canEdit&&branding.banner_url&&<Button onClick={()=>deleteImage("banner")} disabled={busy}>Retirer la bannière</Button>}
          </section>
        </div>
        {!canEdit&&<p className="hint">Seule une personne habilitée à gérer les paramètres de l'établissement peut modifier ces informations.</p>}
      </>}
    </Card>
  </div>;
}
