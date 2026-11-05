import React, {useEffect,useState} from "react";

async function api(path,body,method) {
  if (body!==undefined) await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{method:method||(body===undefined?"GET":"POST"),credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.headers.get("content-type")?.includes("application/json"))throw Error("Serveur indisponible.");
  const data=await response.json();
  if(!response.ok)throw Error(data.error||"Accès refusé.");
  return data;
}

export default function StaffPanel({schoolId}){
  const base="schools/"+schoolId+"/";
  const [staff,setStaff]=useState([]);
  const [years,setYears]=useState([]);
  const [classes,setClasses]=useState([]);
  const [assignments,setAssignments]=useState([]);
  const [staffCode,setStaffCode]=useState("");
  const [first,setFirst]=useState("");
  const [last,setLast]=useState("");
  const [position,setPosition]=useState("");
  const [username,setUsername]=useState("");
  const [linkStaff,setLinkStaff]=useState("");
  const [linkUsername,setLinkUsername]=useState("");
  const [selectedStaff,setSelectedStaff]=useState("");
  const [selectedYear,setSelectedYear]=useState("");
  const [selectedClass,setSelectedClass]=useState("");
  const [duty,setDuty]=useState("enseignant");
  const [error,setError]=useState("");
  const [visible,setVisible]=useState(true);
  const [busy,setBusy]=useState(false);
  const refresh=async()=>{
    const [a,b,c,d]=await Promise.all([
      api(base+"staff"),api(base+"academic/years"),api(base+"academic/classes"),api(base+"staff-assignments")
    ]);
    setStaff(a.staff);setYears(b.years);setClasses(c.classes);setAssignments(d.assignments);
  };
  useEffect(()=>{
    let active=true;
    Promise.all([api(base+"staff"),api(base+"academic/years"),api(base+"academic/classes"),api(base+"staff-assignments")])
    .then(([a,b,c,d])=>{
      if(!active)return;
      setStaff(a.staff);setYears(b.years);setClasses(c.classes);setAssignments(d.assignments);
    }).catch(()=>{if(active)setVisible(false);});
    return()=>{active=false;};
  },[schoolId]);
  async function run(fn){
    setBusy(true);setError("");
    try{await fn();await refresh();}
    catch(e){setError(e.message);}
    finally{setBusy(false);}
  }
  if(!visible)return null;
  return (
    <section className="card" aria-label="Personnel et affectations" style={{marginTop:"1rem"}}>
      <h2>Personnel et affectations</h2>
      <p className="hint">Une fiche du personnel peut être créée avant son compte YEM. L'affectation relie le personnel à une classe et une année.</p>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        await api(base+"staff",{staff_code:staffCode,first_name:first,last_name:last,position,username:username||null});
        setStaffCode("");setFirst("");setLast("");setPosition("");setUsername("");setError("Personnel enregistré.");
      });}}>
        <h3>Créer une fiche du personnel</h3>
        <div className="two">
          <label className="field">Matricule
            <input required value={staffCode} maxLength={50} onChange={e=>setStaffCode(e.target.value)}/>
          </label>
          <label className="field">Prénom(s)
            <input required value={first} maxLength={120} onChange={e=>setFirst(e.target.value)}/>
          </label>
          <label className="field">Nom
            <input required value={last} maxLength={120} onChange={e=>setLast(e.target.value)}/>
          </label>
          <label className="field">Fonction
            <input required value={position} maxLength={100} onChange={e=>setPosition(e.target.value)} placeholder="Ex. Enseignant, CPE, surveillant"/>
          </label>
          <label className="field">Compte YEM existant (facultatif)
            <input value={username} maxLength={150} onChange={e=>setUsername(e.target.value)} placeholder="Identifiant d'un membre de l'école"/>
          </label>
        </div>
        <button disabled={busy} type="submit">Enregistrer le personnel</button>
      </form>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        const record=staff.find(p=>p.id===linkStaff);
        if(!record)throw Error("Sélectionnez une fiche du personnel.");
        await api(base+"staff/"+linkStaff,{revision:record.revision,username:linkUsername.trim()},"PATCH");
        setLinkUsername("");
        setError("Compte lié à la fiche du personnel.");
      });}}>
        <h3>Rattacher un compte YEM à un personnel existant</h3>
        <p className="hint">Créez d'abord le compte dans « Comptes et accès ». Cette liaison est utile pour les nominations et pour afficher les fonctions après connexion.</p>
        <div className="two">
          <label className="field">Personnel
            <select required value={linkStaff} onChange={e=>setLinkStaff(e.target.value)}>
              <option value="">Choisir une fiche…</option>
              {staff.filter(p=>p.active).map(p=><option key={p.id} value={p.id}>{p.last_name} {p.first_name} · {p.account_id?"Compte lié":"Sans compte"}</option>)}
            </select>
          </label>
          <label className="field">Identifiant d'un compte actif de cette école
            <input required maxLength={150} value={linkUsername} onChange={e=>setLinkUsername(e.target.value)} placeholder="Identifiant de connexion"/>
          </label>
        </div>
        <button disabled={busy||!linkStaff||!linkUsername.trim()} type="submit">Associer le compte à cette fiche</button>
      </form>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        await api(base+"staff-assignments",{staff:selectedStaff,year:selectedYear,classroom:selectedClass,duty});
        setError("Affectation enregistrée.");
      });}}>
        <h3>Affecter à une classe</h3>
        <div className="two">
          <label className="field">Personnel
            <select value={selectedStaff} onChange={e=>setSelectedStaff(e.target.value)} required>
              <option value="">Sélectionner…</option>
              {staff.filter(s=>s.active).map(s=><option key={s.id} value={s.id}>{s.last_name} {s.first_name} ({s.staff_code})</option>)}
            </select>
          </label>
          <label className="field">Année scolaire
            <select value={selectedYear} required onChange={e=>{setSelectedYear(e.target.value);setSelectedClass("");}}>
              <option value="">Sélectionner…</option>
              {years.filter(y=>y.active).map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
            </select>
          </label>
          <label className="field">Classe
            <select value={selectedClass} required onChange={e=>setSelectedClass(e.target.value)}>
              <option value="">Sélectionner…</option>
              {classes.filter(c=>c.active&&c.year===selectedYear).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label className="field">Responsabilité (code libre)
            <input pattern="[a-z][a-z0-9_-]*" value={duty} maxLength={50} required onChange={e=>setDuty(e.target.value)} />
          </label>
        </div>
        <button disabled={busy} type="submit">Enregistrer l'affectation</button>
      </form>
      <p className="hint">{staff.length} fiche(s) de personnel · {assignments.filter(a=>a.active).length} affectation(s) active(s). Les droits sont contrôlés par établissement.</p>
      {error&&<p role="status" aria-live="polite">{error}</p>}
    </section>
  );
}
