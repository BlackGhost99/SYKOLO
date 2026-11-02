import React, {useEffect,useState} from "react";

async function call(path,body){
  if(body!==undefined)await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const token=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{
    method:body===undefined?"GET":"POST",credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  if(!response.headers.get("content-type")?.includes("application/json"))throw Error("Service indisponible.");
  const data=await response.json();
  if(!response.ok)throw Error(data.error||"Accès refusé.");
  return data;
}

export default function ReportPanel({schoolId}){
  const base="schools/"+schoolId+"/";
  const [enrollments,setEnrollments]=useState([]);
  const [students,setStudents]=useState([]);
  const [periods,setPeriods]=useState([]);
  const [reports,setReports]=useState([]);
  const [courses,setCourses]=useState([]);
  const [selectedEnrollment,setSelectedEnrollment]=useState("");
  const [selectedPeriod,setSelectedPeriod]=useState("");
  const [selectedReport,setSelectedReport]=useState("");
  const [preview,setPreview]=useState(null);
  const [selectedCourse,setSelectedCourse]=useState("");
  const [assessments,setAssessments]=useState([]);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [visible,setVisible]=useState(true);

  const updateReports=async()=>{
    const result=await call(base+"reports");setReports(result.reports);
  };
  useEffect(()=>{
    let active=true;
    Promise.all([
      call(base+"reports"),call(base+"enrollments"),call(base+"students"),
      call(base+"academic/periods"),call(base+"courses"),
    ]).then(([r,e,s,p,c])=>{
      if(!active)return;
      setReports(r.reports);setEnrollments(e.enrollments);setStudents(s.students);
      setPeriods(p.periods);setCourses(c.courses);
    }).catch(()=>{if(active)setVisible(false);});
    return()=>{active=false;};
  },[schoolId]);
  useEffect(()=>{
    setAssessments([]);
    if(!selectedCourse)return;
    let active=true;
    call(base+"courses/"+selectedCourse+"/assessments")
      .then(data=>{if(active)setAssessments(data.assessments);})
      .catch(e=>{if(active)setMessage(e.message);});
    return()=>{active=false;};
  },[selectedCourse,schoolId]);
  useEffect(()=>{
    if(!selectedReport){setPreview(null);return;}
    let active=true;
    call(base+"reports/"+selectedReport)
      .then(data=>{if(active)setPreview(data);})
      .catch(e=>{if(active)setMessage(e.message);});
    return()=>{active=false;};
  },[selectedReport,schoolId]);

  async function run(task) {
    setBusy(true);setMessage("");
    try{await task();}
    catch(e){setMessage(e.message);}
    finally{setBusy(false);}
  }

  if(!visible)return null;
  const activeEnrollment=enrollments.find(e=>e.id===selectedEnrollment);
  const applicablePeriods=periods.filter(p=>p.year===activeEnrollment?.year);
  const current=reports.find(r=>r.enrollment===selectedEnrollment&&r.period===(selectedPeriod||null));
  const snapshot=preview?.snapshot;

  return <section className="card" aria-label="Bulletins et résultats" style={{marginTop:"1rem"}}>
    <h2>Bulletins et résultats</h2>
    <p className="hint">Seules les évaluations validées par la direction alimentent les bulletins. La publication fige une copie contrôlée ; les brouillons PDF sont marqués non officiels.</p>
    <div className="two">
      <label className="field">Cours à valider
        <select value={selectedCourse} onChange={e=>setSelectedCourse(e.target.value)}>
          <option value="">Choisir un cours…</option>
          {courses.map(c=><option key={c.id} value={c.id}>{c.subject.slice(0,8)} · {c.classroom.slice(0,8)}</option>)}
        </select>
      </label>
      {selectedCourse&&<label className="field">Évaluations de ce cours
        <div>
          {assessments.map(a=><div key={a.id} style={{padding:"0.25rem 0"}}>
            <span>{a.name} · {a.published?"Publiée":"Brouillon"}</span>
            {!a.published&&<button type="button" disabled={busy} style={{marginLeft:"0.5rem"}} onClick={()=>run(async()=>{
              await call(base+"assessments/"+a.id+"/publish",{revision:a.revision});
              const result=await call(base+"courses/"+selectedCourse+"/assessments");
              setAssessments(result.assessments);setMessage("Évaluation publiée et verrouillée.");
            })}>Publier</button>}
          </div>)}
        </div>
      </label>}
    </div>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      const result=await call(base+"reports",{
        enrollment:selectedEnrollment,period:selectedPeriod||null,revision:current?.revision||0,
      });
      await updateReports();setSelectedReport(result.id);setPreview(result);
      setMessage("Bulletin préparé. Vérifiez son contenu avant publication.");
    });}}>
      <h3>Générer ou actualiser un brouillon</h3>
      <div className="two">
        <label className="field">Élève inscrit
          <select required value={selectedEnrollment} onChange={e=>{setSelectedEnrollment(e.target.value);setSelectedPeriod("");}}>
            <option value="">Sélectionner…</option>
            {enrollments.map(e=>{
              const s=students.find(st=>st.id===e.student);
              return <option key={e.id} value={e.id}>{s?s.last_name+" "+s.first_name+" · "+s.student_code:e.id.slice(0,8)}</option>;
            })}
          </select>
        </label>
        <label className="field">Période à présenter
          <select value={selectedPeriod} onChange={e=>setSelectedPeriod(e.target.value)}>
            <option value="">Bilan de l'année complète</option>
            {applicablePeriods.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
      </div>
      <button type="submit" disabled={busy||!selectedEnrollment||current?.status==="published"}>Préparer le bulletin</button>
      {current?.status==="published"&&<p className="hint">Ce bulletin est déjà publié et reste immuable.</p>}
    </form>
    <label className="field">Bulletins enregistrés
      <select value={selectedReport} onChange={e=>setSelectedReport(e.target.value)}>
        <option value="">Choisir…</option>
        {reports.map(r=><option key={r.id} value={r.id}>{r.year.slice(0,8)} · {r.enrollment.slice(0,8)} · {r.status}</option>)}
      </select>
    </label>
    {preview&&snapshot&&<>
      <h3>{snapshot.template.title} · {preview.status==="published"?"Publié":"Brouillon"}</h3>
      <p><strong>{snapshot.student.last_name} {snapshot.student.first_name}</strong> — {snapshot.student.code}</p>
      <p>{snapshot.class.name} · {snapshot.year.name} · {snapshot.period?.name||"Année complète"}</p>
      <div style={{overflowX:"auto"}}>
        <table style={{width:"100%"}}>
          <thead><tr><th>Matière</th><th>Coefficient</th><th>Résultat</th></tr></thead>
          <tbody>{snapshot.subjects.map(s=><tr key={s.course}>
            <td>{s.subject}</td><td>{s.coefficient}</td>
            <td>{s.result.score||"—"} {s.result.label||""}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <p><strong>Résultat général :</strong> {snapshot.overall.score??"—"} · {snapshot.overall.label??"Non calculé"}</p>
      <div className="actions">
        <a href={"/api/v1/"+base+"reports/"+preview.id+"/pdf"}>Exporter le bulletin PDF (A4)</a>
        {preview.status==="draft"&&<button type="button" disabled={busy} onClick={()=>run(async()=>{
          const issued=await call(base+"reports/"+preview.id+"/publish",{revision:preview.revision});
          await updateReports();setPreview(issued);setMessage("Bulletin publié et verrouillé.");
        })}>Publier le bulletin</button>}
      </div>
    </>}
    {message&&<p role="status" aria-live="polite">{message}</p>}
  </section>;
}
