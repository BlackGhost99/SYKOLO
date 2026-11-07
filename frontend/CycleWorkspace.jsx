import React,{useEffect,useState} from "react";

async function read(schoolId,path){
  const r=await fetch("/api/v1/schools/"+schoolId+"/"+path,{credentials:"same-origin"});
  const d=await r.json();
  if(!r.ok)throw Error(d.error||"Accès indisponible.");
  return d;
}

/* Écran réservé aux comptes par cycle : n'interroge que les endpoints filtrés. */
export default function CycleWorkspace({schoolId,access}) {
  const [students,setStudents]=useState([]);
  const [classes,setClasses]=useState([]);
  const [enrollments,setEnrollments]=useState([]);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  const [search,setSearch]=useState("");
  useEffect(()=>{
    let alive=true;setLoading(true);setError("");
    Promise.all([
      read(schoolId,"students"),read(schoolId,"enrollments"),
      read(schoolId,"academic/classes")
    ]).then(([p,e,c])=>{
      if(!alive)return;
      setStudents(p.students||[]);setEnrollments(e.enrollments||[]);
      setClasses(c.classes||[]);
    }).catch(e=>{if(alive)setError(e.message)}).finally(()=>{if(alive)setLoading(false)});
    return()=>{alive=false};
  },[schoolId]);
  const view=students.filter(p=>(p.first_name+" "+p.last_name+" "+p.student_code)
      .toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <section className="yd-real-body" aria-label="Élèves des cycles autorisés">
    <div className="card">
      <h2>Élèves de mes cycles</h2>
      <p className="hint">Cycles autorisés : {(access?.access_cycles||[]).map(c=>c.name).join(" · ")||"Aucun cycle attribué"}. Les données des autres cycles ne sont pas transmises par le serveur.</p>
      <p className="hint">Consultation seulement pour l'instant. Les notes, bulletins, finances et modifications d'élèves seront disponibles après contrôle de leur périmètre côté serveur.</p>
      {loading?<p>Chargement…</p>:error?<p role="alert">{error}</p>:<>
        <p><strong>{view.length}</strong> élève(s) visible(s) · <strong>{classes.length}</strong> classe(s) · <strong>{enrollments.length}</strong> inscription(s) autorisée(s).</p>
        <label className="field">Rechercher un élève
          <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Nom, prénom ou matricule"/>
        </label>
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%"}}>
            <thead><tr><th>Élève</th><th>Matricule</th><th>Classes autorisées</th></tr></thead>
            <tbody>{view.map(p=><tr key={p.id}>
              <td>{p.first_name} {p.last_name}</td>
              <td>{p.student_code}</td>
              <td>{enrollments.filter(e=>e.student===p.id).map(e=>classes.find(c=>c.id===e.classroom)?.name||"—").join(", ")||"—"}</td>
            </tr>)}</tbody>
          </table>
        </div>
        {!view.length&&<p className="hint">Aucun élève correspondant dans les cycles autorisés.</p>}
      </>}
    </div>
  </section>;
}
