import React, {useEffect,useState} from "react";

async function call(path,body){
  if(body!==undefined)await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const token=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{method:body===undefined?"GET":"POST",credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},
    body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.headers.get("content-type")?.includes("application/json"))throw Error("Service pédagogique indisponible.");
  const data=await response.json();
  if(!response.ok)throw Error(data.error||"Accès refusé.");
  return data;
}

export default function CurriculumPanel({schoolId}){
  const base="schools/"+schoolId+"/";
  const [subjects,setSubjects]=useState([]);
  const [courses,setCourses]=useState([]);
  const [years,setYears]=useState([]);
  const [classes,setClasses]=useState([]);
  const [assignments,setAssignments]=useState([]);
  const [subjectCode,setSubjectCode]=useState("");
  const [subjectName,setSubjectName]=useState("");
  const [selectedSubject,setSelectedSubject]=useState("");
  const [selectedYear,setSelectedYear]=useState("");
  const [classroom,setClassroom]=useState("");
  const [coefficient,setCoefficient]=useState("1");
  const [course,setCourse]=useState("");
  const [unitCode,setUnitCode]=useState("");
  const [unitTitle,setUnitTitle]=useState("");
  const [unitObjectives,setUnitObjectives]=useState("");
  const [instructor,setInstructor]=useState("");
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [visible,setVisible]=useState(true);
  async function reload(){
    const [a,b,c,d]=await Promise.all([
      call(base+"subjects"),call(base+"courses"),call(base+"academic/years"),call(base+"academic/classes"),
    ]);
    setSubjects(a.subjects);setCourses(b.courses);setYears(c.years);setClasses(d.classes);
    const res=await call(base+"staff-assignments").catch(()=>({assignments:[]}));
    setAssignments(res.assignments);
  }
  useEffect(()=>{
    let active=true;
    Promise.all([
      call(base+"subjects"),call(base+"courses"),call(base+"academic/years"),call(base+"academic/classes"),
    ]).then(async ([a,b,c,d])=>{
      if(!active)return;
      setSubjects(a.subjects);setCourses(b.courses);setYears(c.years);setClasses(d.classes);
      const res=await call(base+"staff-assignments").catch(()=>({assignments:[]}));
      if(active)setAssignments(res.assignments);
    }).catch(()=>{if(active)setVisible(false);});
    return()=>{active=false;};
  },[schoolId]);
  async function run(fn){
    setMessage("");setBusy(true);
    try {await fn();await reload();}
    catch(e){setMessage(e.message);}
    finally{setBusy(false);}
  }
  if(!visible)return null;
  return <section className="card" aria-label="Matières et programmes" style={{marginTop:"1rem"}}>
    <h2>Matières et programmes</h2>
    <p className="hint">Chaque classe peut avoir ses propres matières et coefficients. Les enseignants affectés pourront éditer les unités de leurs cours.</p>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      await call(base+"subjects",{code:subjectCode,name:subjectName});
      setSubjectCode("");setSubjectName("");setMessage("Matière créée.");
    });}}>
      <h3>Nouvelle matière</h3>
      <div className="two">
        <label className="field">Code
          <input required pattern="[a-z0-9][a-z0-9_-]*" value={subjectCode} maxLength={50} onChange={e=>setSubjectCode(e.target.value)} placeholder="maths"/>
        </label>
        <label className="field">Nom
          <input required value={subjectName} maxLength={120} onChange={e=>setSubjectName(e.target.value)}/>
        </label>
      </div>
      <button type="submit" disabled={busy}>Créer la matière</button>
    </form>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      await call(base+"courses",{subject:selectedSubject,year:selectedYear,classroom,coefficient});
      setMessage("Matière ajoutée à la classe.");
    });}}>
      <h3>Programme d'une classe</h3>
      <div className="two">
        <label className="field">Matière
          <select required value={selectedSubject} onChange={e=>setSelectedSubject(e.target.value)}>
            <option value="">Choisir…</option>
            {subjects.filter(s=>s.active).map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <label className="field">Année
          <select required value={selectedYear} onChange={e=>{setSelectedYear(e.target.value);setClassroom("");}}>
            <option value="">Choisir…</option>
            {years.filter(y=>y.active).map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
          </select>
        </label>
        <label className="field">Classe
          <select required value={classroom} onChange={e=>setClassroom(e.target.value)}>
            <option value="">Choisir…</option>
            {classes.filter(c=>c.active&&c.year===selectedYear).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="field">Coefficient
          <input required type="number" min="0.001" max="1000" step="0.001" value={coefficient} onChange={e=>setCoefficient(e.target.value)}/>
        </label>
      </div>
      <button type="submit" disabled={busy}>Associer matière et classe</button>
    </form>
    <label className="field">Cours enregistré
      <select value={course} onChange={e=>setCourse(e.target.value)}>
        <option value="">Choisir…</option>
        {courses.filter(c=>c.active).map(c=><option key={c.id} value={c.id}>{
          subjects.find(s=>s.id===c.subject)?.name||"Matière"
        } · {classes.find(cl=>cl.id===c.classroom)?.name||"Classe"} (coef. {c.coefficient})</option>)}
      </select>
    </label>
    {course&&<>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        await call(base+"courses/"+course+"/units",{code:unitCode,title:unitTitle,objectives:unitObjectives});
        setUnitCode("");setUnitTitle("");setUnitObjectives("");setMessage("Unité de programme créée.");
      });}}>
        <h3>Unité du programme</h3>
        <div className="two">
          <label className="field">Code
            <input required pattern="[a-z0-9][a-z0-9_-]*" maxLength={50} value={unitCode} onChange={e=>setUnitCode(e.target.value)}/>
          </label>
          <label className="field">Titre
            <input required maxLength={180} value={unitTitle} onChange={e=>setUnitTitle(e.target.value)}/>
          </label>
        </div>
        <label className="field">Objectifs pédagogiques
          <textarea rows={3} maxLength={2000} value={unitObjectives} onChange={e=>setUnitObjectives(e.target.value)}/>
        </label>
        <button type="submit" disabled={busy}>Ajouter l'unité</button>
      </form>
      {assignments.length>0&&<form onSubmit={e=>{e.preventDefault();run(async()=>{
        await call(base+"courses/"+course+"/instructors",{staff_assignment:instructor});
        setInstructor("");setMessage("Enseignant associé.");
      });}}>
        <h3>Associer un enseignant affecté à cette classe</h3>
        <label className="field">Affectation du personnel
          <select required value={instructor} onChange={e=>setInstructor(e.target.value)}>
            <option value="">Sélectionner…</option>
            {assignments.filter(a=>a.active&&a.classroom===courses.find(c=>c.id===course)?.classroom).map(a=><option key={a.id} value={a.id}>{a.duty} · {a.staff.slice(0,8)}</option>)}
          </select>
        </label>
        <button type="submit" disabled={busy}>Associer au cours</button>
      </form>}
    </>}
    <p className="hint">{subjects.length} matière(s), {courses.length} cours enregistré(s).</p>
    {message&&<p role="status">{message}</p>}
  </section>;
}
