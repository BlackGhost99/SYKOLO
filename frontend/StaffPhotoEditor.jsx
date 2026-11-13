import React,{useState} from "react";

/* L'image reste dans la base sécurisée de l'établissement, jamais dans le cache PWA. */
async function prepareImage(file) {
  if (!["image/jpeg","image/png"].includes(file.type)) throw Error("Choisissez une photo JPG ou PNG.");
  if (file.size > 12_000_000) throw Error("Image trop volumineuse (12 Mo maximum avant compression).");
  const objectURL=URL.createObjectURL(file);
  let image;
  try {
    image=await new Promise((resolve,reject)=>{
      const img=new Image();
      img.onload=()=>resolve(img);
      img.onerror=()=>reject(Error("La photo choisie est illisible."));
      img.src=objectURL;
    });
  } finally {
    URL.revokeObjectURL(objectURL);
  }
  let width=image.naturalWidth,height=image.naturalHeight;
  if (!width||!height) throw Error("Image illisible.");
  const max=480;
  const factor=Math.min(1,max/Math.max(width,height));
  width=Math.max(1,Math.round(width*factor));
  height=Math.max(1,Math.round(height*factor));
  let result=null;
  for(const quality of [0.83,0.65,0.48]) {
    const canvas=document.createElement("canvas");
    canvas.width=width;canvas.height=height;
    const ctx=canvas.getContext("2d");
    if(!ctx)throw Error("La compression de photos n'est pas disponible.");
    ctx.fillStyle="#ffffff";ctx.fillRect(0,0,width,height);
    ctx.drawImage(image,0,0,width,height);
    result=await new Promise(resolve=>canvas.toBlob(resolve,"image/jpeg",quality));
    if(result && result.size<=350_000) break;
    width=Math.max(1,Math.round(width*0.7));
    height=Math.max(1,Math.round(height*0.7));
  }
  if(!result||result.size>350_000)throw Error("Impossible de réduire cette photo à 350 Ko.");
  return new File([result],"profil.jpg",{type:"image/jpeg"});
}

export default function StaffPhotoEditor({schoolId,staffId="",own=false,photoUrl=null,canEdit=false,onChange}) {
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const base=`/api/v1/schools/${schoolId}/staff/${own?"me":staffId}/photo`;
  async function send(method,file) {
    setBusy(true);setError("");setNotice("");
    try{
      const csrf=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
      if(!csrf.ok)throw Error("Session expirée, reconnectez-vous.");
      const token=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
      const body=file?new FormData():undefined;
      if(body)body.append("photo",await prepareImage(file));
      const response=await fetch(base,{
        method,credentials:"same-origin",
        headers:{"X-CSRFToken":token},body,
      });
      const data=await response.json();
      if(!response.ok)throw Error(data.error||"Impossible de modifier la photo.");
      onChange?.(data.photo_url||null);
      window.dispatchEvent(new CustomEvent("yem:staff-photo-updated",{detail:{schoolId,staffId}}));
      setNotice(method==="DELETE"?"Photo supprimée.":"Photo enregistrée dans la fiche du personnel.");
    }catch(e){setError(e.message||"Erreur lors de l'enregistrement.");}
    finally{setBusy(false);}
  }
  return <div className="yp-staff-photo-editor">
    <div className="yp-staff-photo-avatar" aria-label={photoUrl?"Photo du personnel":"Aucune photo de profil"}>
      {photoUrl?<img src={photoUrl} alt="Photo de profil du personnel"/>:<span aria-hidden="true">👤</span>}
    </div>
    <div>
      <strong>Photo de profil</strong>
      <p className="hint">Une seule photo pour l'espace professeur, la liste du personnel et la fiche professionnelle.</p>
      {canEdit&&<div className="actions">
        <label className="yd-btn yp-upload-label">{busy?"Enregistrement…":"Choisir une photo"}
          <input type="file" accept="image/jpeg,image/png" disabled={busy}
            onChange={event=>{const file=event.target.files?.[0];event.target.value="";if(file)send("POST",file);}}/>
        </label>
        {photoUrl&&<button type="button" className="yd-btn" disabled={busy} onClick={()=>send("DELETE")}>Supprimer</button>}
      </div>}
      {error&&<p role="alert">{error}</p>}
      {notice&&<p role="status">{notice}</p>}
    </div>
  </div>;
}
