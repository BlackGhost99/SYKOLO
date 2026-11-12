import React,{useEffect,useState} from "react";

async function cashApi(path,body){
  if(body!==undefined)await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const token=document.cookie.split("; ").find(v=>v.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{
    method:body===undefined?"GET":"POST",credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  const json=await response.json();
  if(!response.ok)throw Error(json.error||"Opération caisse refusée.");
  return json;
}

export function librevilleToday(){
  return new Intl.DateTimeFormat("sv-SE",{
    timeZone:"Africa/Libreville",year:"numeric",month:"2-digit",day:"2-digit",
  }).format(new Date());
}

export default function AdmissionCashDesk({schoolId,canReceive=false,applicationId,onUpdated}){
  const base="schools/"+schoolId+"/admission-cash";
  const queue=applicationId ? base+"?application="+encodeURIComponent(applicationId) : base;
  const [items,setItems]=useState(null);
  const [reference,setReference]=useState({});
  const [acknowledged,setAcknowledged]=useState({});
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  useEffect(()=>{
    let live=true;
    cashApi(queue).then(data=>{if(live)setItems(data.payments||[]);})
      .catch(e=>{if(live)setMessage(e.message);});
    return()=>{live=false;};
  },[queue]);
  async function refresh(){
    const data=await cashApi(queue);
    setItems(data.payments||[]);
  }
  async function confirm(row){
    setBusy(true);setMessage("");
    try{
      if(!acknowledged[row.request])throw Error(
        row.is_demo?"Confirmez que personne ne remet d'argent pour ce test.":"Cochez la confirmation de remise physique des espèces."
      );
      const ref=(reference[row.request]||"").trim();
      if(ref.length<3)throw Error("Indiquez une référence de caisse (au moins 3 caractères).");
      const receipt=await cashApi(base+"/"+row.request+"/confirm",{
        reference:ref,
        received_on:librevilleToday(),
        received_cash:!row.is_demo,
        acknowledge_demo:row.is_demo,
      });
      setAcknowledged(v=>({...v,[row.request]:false}));
      setItems(current=>current.map(item=>item.request===row.request ? {
        ...item,payment_status:receipt.status,
        receipt_url:"/api/v1/"+base+"/"+row.request+"/receipt",
      } : item));
      setMessage(row.is_demo?
        "Simulation validée par le caissier : aucun argent encaissé. Notification et document accessibles au parent.":
        "Espèces reçues et enregistrées. Notification et reçu PDF accessibles au parent.");
      try { await onUpdated?.(); }
      catch(e) { setMessage("Paiement enregistré. Actualisez la candidature pour mettre à jour son état. "+e.message); }
    }catch(e){setMessage(e.message)}finally{setBusy(false)}
  }
  return <section className="yp-settings" aria-label="Caisse des candidatures en espèces" style={{marginTop:22}}>
    <h3>Frais de dossier — Paiements en espèces au guichet</h3>
    <p>Les parents choisissent « Espèces à l'école ». Seul l'économe/caissier habilité
      peut confirmer la remise d'argent. La direction et le secrétariat peuvent suivre
      les dossiers sans encaisser à la place du caissier.</p>
    <button className="yp-button" type="button" disabled={busy}
      onClick={()=>{setBusy(true);refresh().then(()=>setMessage("Caisse actualisée."))
        .catch(e=>setMessage(e.message)).finally(()=>setBusy(false));}}>
      Actualiser la caisse des admissions
    </button>
    {!items&&!message&&<p role="status">Chargement des paiements en espèces…</p>}
    {items?.length===0&&<p>{applicationId ? "Cette candidature ne prévoit pas de règlement en espèces." : "Aucune candidature avec règlement en espèces."}</p>}
    {items?.map(row=><article key={row.request} style={{borderTop:"1px solid #ddd",padding:"12px 0"}}>
      <strong>{row.child}</strong> · {row.classroom} · {row.year}
      <p>Parent : {row.parent} · Dossier : {row.admission_status}</p>
      <p>Montant : {row.amount_xaf?Number(row.amount_xaf).toLocaleString("fr-FR")+" FCFA":"Tarif non configuré"}
        {row.is_demo&&" · SIMULATION — 0 FCFA reçu"}</p>
      {row.scholarship_active&&<p role="status">Bourse gouvernementale validée : aucun nouvel encaissement de frais de dossier autorisé.</p>}
      <p>État caisse : <strong>{({
        a_regler_sur_place:"En attente de réception",
        recu:"Espèces reçues",
        simule:"Simulation confirmée",
        annule:"Reçu annulé",
        dispense_bourse:"Frais pris en charge par bourse",
        inscription_deja_finalisee:"Inscription déjà définitive — pas de nouveau règlement",
      })[row.payment_status]||row.payment_status}</strong></p>
      {row.receipt_url&&<a href={row.receipt_url} target="_blank" rel="noreferrer">
        {row.is_demo?"Document de simulation PDF":"Reçu de caisse PDF"}
      </a>}
      {canReceive&&row.can_pay!==false&&row.admission_status!=="rejected"&&row.admission_status!=="enrolled"&&row.payment_status==="a_regler_sur_place"&&Boolean(row.amount_xaf)&&<>
        <label className="yp-field">Référence de caisse
          <input maxLength={100} value={reference[row.request]||""}
            onChange={e=>setReference(v=>({...v,[row.request]:e.target.value}))}
            placeholder={row.is_demo?"TEST-CAISSE-SECONDE":"Référence du guichet"}/>
        </label>
        <label style={{display:"block",margin:"8px 0"}}>
          <input type="checkbox" checked={!!acknowledged[row.request]}
            onChange={e=>setAcknowledged(v=>({...v,[row.request]:e.target.checked}))}/>
          {row.is_demo?
            " Je confirme que cette opération est un TEST : aucun argent reçu.":
            " Je confirme avoir physiquement reçu les espèces indiquées."}
        </label>
        <button className="yp-button yp-primary" type="button" disabled={busy||!acknowledged[row.request]||(reference[row.request]||"").trim().length<3}
          onClick={()=>confirm(row)}>
          {row.is_demo?"Valider la simulation sans encaissement":"Confirmer les espèces reçues"}
        </button>
      </>}
    </article>)}
    {message&&<p role="status">{message}</p>}
  </section>;
}
