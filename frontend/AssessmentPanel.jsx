import React, {useEffect,useState} from "react";

async function request(path,body,method){
  if(body!==undefined)await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{
    method:method||(body===undefined?"GET":"POST"),
    credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  if(!response.headers.get("content-type")?.includes("application/json"))throw Error("Serveur indisponible.");
  const data=await response.json();
  if(!response.ok)throw Error(data.error||"Accès refusé.");
  return data;
}

export default function AssessmentPanel({schoolId}){
  const base="schools/"+schoolId+"/";
  const [courses,setCourses]=useState([]);
  const [periods,setPeriods]=useState([]);
  const [subjects,setSubjects]=useState([]);
  const [classes,setClasses]=useState([]);
  const [course,setCourse]=useState("");
  const [assessment,setAssessment]=useState("");
  const [assessments,setAssessments]=useState([]);
  const [roster,setRoster]=useState([]);
  const [grades,setGrades]=useState([]);
  const [scoreDraft,setScoreDraft]=useState({});
  const [name,setName]=useState("");
  const [assessmentDate,setAssessmentDate]=useState("");
  const [kind,setKind]=useState("devoir");
  const [period,setPeriod]=useState("");
  const [weight,setWeight]=useState("1");
  const [message,setMessage]=useState("");
  const [visible,setVisible]=useState(true);
  const [busy,setBusy]=useState(false);
  const chosen=assessments.find(a=>a.id===assessment);
  const currentCourse=courses.find(c=>c.id===course);

  useEffect(()=>{
    let active=true;
    Promise.all([request(base+"courses"),request(base+"academic/periods"),
      request(base+"subjects"),request(base+"academic/classes")])
    .then(([a,b,c,d])=>{
      if(!active)return;
      setCourses(a.courses);setPeriods(b.periods);setSubjects(c.subjects);setClasses(d.classes);
    }).catch(()=>{if(active)setVisible(false);});
    return()=>{active=false;};
  },[schoolId]);

  useEffect(()=>{
    setAssessment("");setAssessments([]);setRoster([]);setGrades([]);
    if(!course)return;
    let active=true;
    request(base+"courses/"+course+"/assessments")
      .then(data=>{if(active)setAssessments(data.assessments);})
      .catch(err=>{if(active)setMessage(err.message);});
    return()=>{active=false;};
  },[course,schoolId]);

  useEffect(()=>{
    setRoster([]);setGrades([]);setScoreDraft({});
    if(!assessment)return;
    let active=true;
    Promise.all([
      request(base+"assessments/"+assessment+"/roster"),
      request(base+"assessments/"+assessment+"/grades"),
    ]).then(([r,g])=>{
      if(active){setRoster(r.students);setGrades(g.grades);}
    }).catch(err=>{if(active)setMessage(err.message);});
    return()=>{active=false;};
  },[assessment,schoolId]);

  async function run(fn){
    setMessage("");setBusy(true);
    try{await fn();}
    catch(e){setMessage(e.message);}
    finally{setBusy(false);}
  }

  function inputFor(student){
    const current=grades.find(g=>g.enrollment===student.enrollment_id);
    const value=Object.hasOwn(scoreDraft,student.enrollment_id)?scoreDraft[student.enrollment_id]:(current?.score??"");
    const scale=chosen?.policy?.scale||{};
    const numeric=["numeric","percentage"].includes(scale.kind);
    if(numeric)return <input type="number" step="any" min="0" max={scale.kind==="percentage"?100:scale.max}
      aria-label={"Note de "+student.last_name} value={value}
      onChange={e=>setScoreDraft(d=>({...d,[student.enrollment_id]:e.target.value}))}/>;
    return <select aria-label={"Résultat de "+student.last_name} value={value}
      onChange={e=>setScoreDraft(d=>({...d,[student.enrollment_id]:e.target.value}))}>
      <option value="">Absent / sans résultat</option>
      {(chosen?.policy?.bands||[]).map((b,i)=><option key={i} value={b.label}>{b.label}</option>)}
    </select>;
  }

  if(!visible)return null;
  return <section className="card" aria-label="Évaluations et notes" style={{marginTop:"1rem"}}>
    <h2>Évaluations et saisie des notes</h2>
    <p className="hint">Résultats non publiés. Les barèmes proviennent des paramètres pédagogiques de l’établissement et restent figés pour chaque évaluation.</p>
    <label className="field">Cours
      <select value={course} onChange={e=>{setCourse(e.target.value);setMessage("");}}>
        <option value="">Sélectionner un cours autorisé…</option>
        {courses.filter(c=>c.active).map(c=><option key={c.id} value={c.id}>{
          subjects.find(s=>s.id===c.subject)?.name||"Matière"
        } · {classes.find(cl=>cl.id===c.classroom)?.name||"Classe"}</option>)}
      </select>
    </label>
    {course&&<>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        const created=await request(base+"courses/"+course+"/assessments",{
          name,assessment_date:assessmentDate,kind,weight,period:period||null,
        });
        const result=await request(base+"courses/"+course+"/assessments");
        setAssessments(result.assessments);setAssessment(created.id);
        setName("");setMessage("Évaluation créée. Son barème a été fixé.");
      });}}>
        <h3>Nouvelle évaluation</h3>
        <div className="two">
          <label className="field">Nom
            <input required maxLength={180} value={name} onChange={e=>setName(e.target.value)}/>
          </label>
          <label className="field">Date
            <input required type="date" value={assessmentDate} onChange={e=>setAssessmentDate(e.target.value)}/>
          </label>
          <label className="field">Type (code personnalisable)
            <input required pattern="[a-z][a-z0-9_-]*" value={kind} maxLength={50} onChange={e=>setKind(e.target.value)}/>
          </label>
          <label className="field">Poids de l'évaluation
            <input required type="number" min="0.001" max="1000" step="0.001" value={weight} onChange={e=>setWeight(e.target.value)}/>
          </label>
          <label className="field">Période (facultative)
            <select value={period} onChange={e=>setPeriod(e.target.value)}>
              <option value="">Sans période particulière</option>
              {periods.filter(p=>p.active&&p.year===currentCourse?.year).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
        </div>
        <button disabled={busy} type="submit">Créer l'évaluation</button>
      </form>
      <label className="field">Évaluation existante
        <select value={assessment} onChange={e=>{setAssessment(e.target.value);setMessage("");}}>
          <option value="">Sélectionner…</option>
          {assessments.filter(a=>a.active).map(a=><option key={a.id} value={a.id}>{a.name} · {a.assessment_date}</option>)}
        </select>
      </label>
    </>}
    {chosen&&<>
      <h3>Notes de l'évaluation : {chosen.name}</h3>
      <p className="hint">Barème : {chosen.policy.scale.kind} · {chosen.policy.scale.max} · poids {chosen.weight}. Les absences suivent les paramètres du barème.</p>
      {roster.length===0?<p className="hint">Aucune inscription active dans cette classe.</p>:
        <div>
          {roster.map(s=>{
            const existing=grades.find(g=>g.enrollment===s.enrollment_id);
            return <form key={s.enrollment_id} onSubmit={e=>{e.preventDefault();run(async()=>{
              const raw=Object.hasOwn(scoreDraft,s.enrollment_id)?scoreDraft[s.enrollment_id]:(existing?.score??"");
              const numeric=["numeric","percentage"].includes(chosen.policy.scale.kind);
              const score=raw===""?null:numeric?Number(raw):raw;
              const prefix=base+"assessments/"+assessment+"/grades";
              if(existing){
                await request(prefix+"/"+existing.id,{revision:existing.revision,score},"PATCH");
              }else{
                await request(prefix,{enrollment:s.enrollment_id,score});
              }
              const fresh=await request(prefix);setGrades(fresh.grades);
              setScoreDraft(d=>{const x={...d};delete x[s.enrollment_id];return x;});
              setMessage("Note enregistrée.");
            });}}>
              <div className="two">
                <div><strong>{s.last_name} {s.first_name}</strong><p className="hint">{s.student_code}{existing?.label?" · "+existing.label:""}</p></div>
                <label className="field">Résultat {inputFor(s)}</label>
              </div>
              <button disabled={busy} type="submit">Enregistrer cette note</button>
            </form>;
          })}
        </div>}
    </>}
    {message&&<p role="status" aria-live="polite">{message}</p>}
  </section>;
}
