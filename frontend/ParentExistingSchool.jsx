import React, {useEffect, useState} from "react";

const STATUS = {
  pending: "En cours de vérification",
  approved: "Rattachement vérifié",
  rejected: "Demande non validée — contactez l'établissement",
  cancelled: "Demande annulée",
};

/**
 * Parents deja scolarises : le formulaire ne cree ni nouvelle candidature
 * ni eleve scolaire. L'ecole verifie le responsable legal dans son dossier.
 */
export default function ParentExistingSchool({api}) {
  const [search,setSearch]=useState("");
  const [schools,setSchools]=useState([]);
  const [requests,setRequests]=useState([]);
  const [school,setSchool]=useState("");
  const [fields,setFields]=useState({
    first_name:"",last_name:"",student_code:"",guardian_name:"",contact_phone:"",
  });
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");

  const reload=async()=>{
    const result=await api("parents/existing-requests");
    setRequests(result.requests||[]);
  };
  useEffect(()=>{
    let active=true;
    Promise.all([api("parents/existing-schools"),api("parents/existing-requests")])
      .then(([list,items])=>{if(active){setSchools(list.schools||[]);setRequests(items.requests||[]);}})
      .catch(err=>{if(active)setError(err.message);})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[api]);
  useEffect(()=>{
    let active=true;
    const id=setTimeout(()=>{
      api("parents/existing-schools?q="+encodeURIComponent(search.trim()))
        .then(result=>{if(active)setSchools(result.schools||[]);})
        .catch(err=>{if(active)setError(err.message);});
    },250);
    return()=>{active=false;clearTimeout(id);};
  },[search,api]);

  async function run(action) {
    setBusy(true);setError("");setMessage("");
    try{await action();await reload();}
    catch(e){setError(e.message);}
    finally{setBusy(false);}
  }
  const set=(key,value)=>setFields(old=>({...old,[key]:value}));

  return <section className="yp-pane" aria-label="Enfant déjà inscrit dans un établissement">
    <h3>Mon enfant est déjà inscrit</h3>
    <p>Votre enfant fréquente déjà une école ? Vous n'avez pas besoin de l'inscrire une deuxième fois.
      Retrouvez son établissement et demandez à être relié à son dossier scolaire officiel.</p>
    {error&&<p className="yp-error" role="alert">{error}</p>}
    {message&&<p className="yp-success" role="status">{message}</p>}
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      const result=await api("parents/existing-requests",{school,...fields});
      setMessage(result.status==="pending"
        ?"Demande enregistrée. L'établissement vérifiera votre identité et votre lien avec l'enfant."
        :"Demande reçue.");
      setFields({first_name:"",last_name:"",student_code:"",guardian_name:"",contact_phone:""});
    });}}>
      <label className="yp-field">Rechercher l'établissement
        <input type="search" value={search} maxLength={80} placeholder="Nom de l'école ou du lycée"
          onChange={e=>{setSearch(e.target.value);setSchool("");}}/>
      </label>
      <label className="yp-field">Établissement de l'enfant
        <select required value={school} disabled={busy||loading} onChange={e=>setSchool(e.target.value)}>
          <option value="">Sélectionner un établissement</option>
          {schools.map(row=><option value={row.id} key={row.id}>{row.name}</option>)}
        </select>
      </label>
      {!loading&&schools.length===0&&<p role="status">Aucun établissement trouvé. Vérifiez son nom ou contactez son secrétariat.</p>}
      <div className="yp-two">
        <label className="yp-field">Prénom de l'enfant
          <input required maxLength={120} autoComplete="off" value={fields.first_name}
            onChange={e=>set("first_name",e.target.value)}/>
        </label>
        <label className="yp-field">Nom de l'enfant
          <input required maxLength={120} autoComplete="off" value={fields.last_name}
            onChange={e=>set("last_name",e.target.value)}/>
        </label>
      </div>
      <label className="yp-field">Matricule scolaire, si connu (facultatif)
        <input maxLength={50} value={fields.student_code} onChange={e=>set("student_code",e.target.value)}
          placeholder="Matricule inscrit sur les documents scolaires"/>
      </label>
      <label className="yp-field">Votre nom tel qu'enregistré comme responsable légal
        <input required maxLength={180} value={fields.guardian_name}
          onChange={e=>set("guardian_name",e.target.value)}/>
      </label>
      <label className="yp-field">Téléphone de contact (facultatif)
        <input type="tel" maxLength={45} autoComplete="tel" value={fields.contact_phone}
          onChange={e=>set("contact_phone",e.target.value)}/>
      </label>
      <p className="yp-muted">Votre demande ne prouve pas l'identité de l'enfant et ne donne aucun accès immédiat.
        L'établissement contrôlera le dossier et pourra demander un justificatif.</p>
      <button className="yp-button yp-primary" type="submit" disabled={busy||!school}>
        {busy?"Enregistrement...":"Demander le rattachement"}
      </button>
    </form>
    <h3>Suivi de mes demandes</h3>
    <button type="button" className="yp-button" disabled={busy} onClick={()=>run(async()=>{
      setMessage("Suivi actualisé.");
    })}>Actualiser les demandes</button>
    {loading&&<p role="status">Chargement des demandes…</p>}
    {!loading&&requests.length===0&&<p>Aucune demande de rattachement enregistrée.</p>}
    {requests.map(item=><article className="yp-request" key={item.id}>
      <b>{item.first_name} {item.last_name} · {item.school_name}</b>
      <p role="status">{STATUS[item.status]||"Vérification à confirmer"}</p>
      {item.status==="approved"&&item.access_active&&<p>Accès activé. Revenez à l'accueil et utilisez « Actualiser mes enfants » pour consulter son dossier.</p>}
      {item.status==="approved"&&!item.access_active&&<p role="alert">L'accès familial n'est plus actif. Contactez l'établissement pour vérifier les autorisations.</p>}
      {item.status==="pending"&&<button type="button" className="yp-button" disabled={busy}
        onClick={()=>run(async()=>{
          await api("parents/existing-requests/"+item.id,{status:"cancelled"},"PATCH");
          setMessage("Demande annulée.");
        })}>Annuler cette demande</button>}
    </article>)}
  </section>;
}

export function SchoolExistingRequests({api,base,reloadKey,onSelect}) {
  const [rows,setRows]=useState([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  async function load(){
    const result=await api(base+"/parent-existing-requests");
    setRows(result.requests||[]);
  }
  useEffect(()=>{
    let live=true;
    api(base+"/parent-existing-requests").then(result=>{if(live)setRows(result.requests||[]);})
      .catch(err=>{if(live)setError(err.message);});
    return()=>{live=false;};
  },[api,base,reloadKey]);
  return <section aria-label="Demandes de rattachement des familles">
    <h3>Demandes reçues d'enfants déjà scolarisés</h3>
    <p className="hint">Contrôlez le dossier élève et le responsable légal avant de lier son compte.
      Ne créez ni nouvel élève ni inscription.</p>
    {error&&<p role="alert">{error}</p>}
    {message&&<p role="status">{message}</p>}
    {rows.length===0?<p>Aucune demande en attente.</p>:rows.map(item=><div key={item.id} className="yp-request">
      <strong>{item.first_name} {item.last_name}</strong>
      <p>{item.school_name} · Matricule déclaré : {item.student_code||"non communiqué"}</p>
      <p>Compte parent : <strong>{item.username}</strong></p>
      <p>Responsable déclaré : {item.guardian_name}{item.contact_phone?" · "+item.contact_phone:""}</p>
      <div className="actions">
        <button type="button" className="yp-button" disabled={busy}
          onClick={()=>{onSelect(item);setMessage("Sélectionnez le dossier et le responsable réel puis confirmez la vérification.");}}>
          Examiner et rattacher
        </button>
        <button type="button" className="yp-button" disabled={busy} onClick={async()=>{
          if(typeof window!=="undefined"&&!window.confirm("Refuser cette demande après vérification ?"))return;
          setBusy(true);setError("");setMessage("");
          try {
            await api(base+"/parent-existing-requests/"+item.id,{status:"rejected"},"PATCH");
            await load();setMessage("Demande refusée et conservée dans l'historique.");
          } catch(e){setError(e.message);}finally{setBusy(false);}
        }}>Refuser</button>
      </div>
    </div>)}
  </section>;
}
