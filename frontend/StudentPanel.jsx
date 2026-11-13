import React, { useEffect, useState } from "react";

async function call(path, body) {
  if (body !== undefined) await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{
    method:body===undefined?"GET":"POST",
    credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) throw Error("Serveur indisponible.");
  const result=await response.json();
  if(!response.ok) throw Error(result.error||"Requête refusée.");
  return result;
}

export default function StudentPanel({schoolId}) {
  const base="schools/"+schoolId+"/";
  const [students,setStudents]=useState([]);
  const [years,setYears]=useState([]);
  const [classes,setClasses]=useState([]);
  const [chosen,setChosen]=useState("");
  const [first,setFirst]=useState("");
  const [last,setLast]=useState("");
  const [birth,setBirth]=useState("");
  const [parentName,setParentName]=useState("");
  const [parentRelation,setParentRelation]=useState("");
  const [parentPhone,setParentPhone]=useState("");
  const [parentEmail,setParentEmail]=useState("");
  const [year,setYear]=useState("");
  const [classroom,setClassroom]=useState("");
  const [enrolledOn,setEnrolledOn]=useState("");
  const [enrollments,setEnrollments]=useState([]);
  const [message,setMessage]=useState("");
  const [allowed,setAllowed]=useState(true);
  const [busy,setBusy]=useState(false);
  async function refresh(){
    const [a,b,c,d]=await Promise.all([
      call(base+"students"),call(base+"academic/years"),call(base+"academic/classes"),call(base+"enrollments"),
    ]);
    setStudents(a.students);setYears(b.years);setClasses(c.classes);setEnrollments(d.enrollments);
  }
  useEffect(()=>{
    let mounted=true;
    Promise.all([
      call(base+"students"),call(base+"academic/years"),call(base+"academic/classes"),call(base+"enrollments"),
    ]).then(([a,b,c,d])=>{
      if(!mounted)return;
      setStudents(a.students);setYears(b.years);setClasses(c.classes);setEnrollments(d.enrollments);
    }).catch(e=>{if(mounted){setAllowed(false);setMessage("Gestion des élèves réservée au personnel autorisé.");}});
    return()=>{mounted=false;};
  },[schoolId]);
  async function run(fn){
    setBusy(true);setMessage("");
    try {await fn();await refresh();}
    catch(e){setMessage(e.message);}
    finally{setBusy(false);}
  }
  if(!allowed)return null;
  const activeClasses=classes.filter(c=>c.active && c.year===year);
  const displayed=students.find(s=>s.id===chosen);
  return (
    <section className="card" aria-label="Élèves et inscriptions" style={{marginTop:"1rem"}}>
      <h2>Élèves et inscriptions</h2>
      <p className="hint">Données privées de cet établissement. Les dossiers sont archivés, jamais supprimés physiquement.</p>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        await call(base+"students",{
          first_name:first,last_name:last,date_of_birth:birth||null,
        });
        setFirst("");setLast("");setBirth("");
        setMessage("Élève enregistré.");
      });}}>
        <h3>Nouvelle fiche élève</h3>
        <div className="two">
          <label className="field">Prénom(s)
            <input value={first} onChange={e=>setFirst(e.target.value)} maxLength={120} required />
          </label>
          <label className="field">Nom
            <input value={last} onChange={e=>setLast(e.target.value)} maxLength={120} required />
          </label>
          <label className="field">Naissance (facultatif)
            <input type="date" value={birth} onChange={e=>setBirth(e.target.value)} />
          </label>
        </div>
        <button type="submit" disabled={busy}>Créer le dossier</button>
      </form>
      <label className="field">Élève sélectionné
        <select value={chosen} onChange={e=>setChosen(e.target.value)}>
          <option value="">Choisir…</option>
          {students.map(s=><option key={s.id} value={s.id}>{s.last_name} {s.first_name} · {s.student_code}</option>)}
        </select>
      </label>
      {displayed && <>
        <p><strong>{displayed.last_name} {displayed.first_name}</strong></p>
        <section aria-label="Matricules de l'élève" className="yp-settings">
          <p>Matricule YEM : <strong>{displayed.matricule_yem}</strong></p>
          <p>Matricule établissement : <strong>{displayed.student_code}</strong></p>
          <p className="hint">Ces références identifient le dossier. Seule une inscription officielle valide la scolarité pour une année donnée.</p>
        </section>
        <form onSubmit={e=>{e.preventDefault();run(async()=>{
          await call(base+"students/"+chosen+"/guardians",{
            full_name:parentName,relationship:parentRelation,phone:parentPhone,email:parentEmail,
          });
          setParentName("");setParentRelation("");setParentPhone("");setParentEmail("");
          setMessage("Responsable enregistré.");
        });}}>
          <h3>Ajouter un responsable légal</h3>
          <div className="two">
            <label className="field">Nom complet
              <input value={parentName} onChange={e=>setParentName(e.target.value)} required maxLength={180} />
            </label>
            <label className="field">Relation avec l’élève
              <input value={parentRelation} onChange={e=>setParentRelation(e.target.value)} maxLength={80} />
            </label>
            <label className="field">Téléphone
              <input type="tel" value={parentPhone} onChange={e=>setParentPhone(e.target.value)} maxLength={45} />
            </label>
            <label className="field">Email
              <input type="email" value={parentEmail} onChange={e=>setParentEmail(e.target.value)} maxLength={254} />
            </label>
          </div>
          <button type="submit" disabled={busy}>Ajouter le responsable</button>
        </form>
        <form onSubmit={e=>{e.preventDefault();run(async()=>{
          await call(base+"enrollments",{
            student:chosen,year,classroom,enrolled_on:enrolledOn,status:"inscrit",
          });
          setMessage("Inscription scolaire enregistrée.");
        });}}>
          <h3>Inscription ou réinscription</h3>
          <div className="two">
            <label className="field">Année scolaire
              <select value={year} required onChange={e=>{setYear(e.target.value);setClassroom("");}}>
                <option value="">Sélectionner…</option>
                {years.filter(y=>y.active).map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
              </select>
            </label>
            <label className="field">Classe
              <select value={classroom} required onChange={e=>setClassroom(e.target.value)}>
                <option value="">Sélectionner…</option>
                {activeClasses.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="field">Date de l’inscription
              <input type="date" required value={enrolledOn} onChange={e=>setEnrolledOn(e.target.value)} />
            </label>
          </div>
          <button type="submit" disabled={busy}>Inscrire l’élève</button>
        </form>
        <p className="hint">
          {enrollments.filter(e=>e.student===chosen).length} inscription(s) enregistrée(s) pour cet élève. Les transferts de classe sont historisés.
        </p>
      </>}
      {message && <p role="status" aria-live="polite">{message}</p>}
    </section>
  );
}
