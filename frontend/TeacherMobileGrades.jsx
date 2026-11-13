import React,{useEffect,useMemo,useState} from "react";
import {Button,Card,Icon} from "./yem-ui.jsx";
import {teacherRequest,displayNumber} from "./teacher-mobile-api.js";

export function CoursePicker({courses,classes,subjects,courseId,onChange}){
  const [classId,setClassId]=useState("");
  const valid=courses.some(c=>c.id===courseId);
  const selected=valid?courseId:"";
  useEffect(()=>{
    const current=courses.find(c=>c.id===courseId);
    if(current)setClassId(current.classroom);
    else if(!courses.some(c=>c.classroom===classId))setClassId(courses[0]?.classroom||"");
  },[courses,courseId,classId]);
  const options=courses.filter(c=>c.classroom===classId);
  useEffect(()=>{
    if(selected && !options.some(c=>c.id===selected))onChange("");
  },[classId,selected]);
  return <div className="ym-select-row">
    <label>Classe
      <select aria-label="Classe enseignée" value={classId} onChange={e=>{setClassId(e.target.value);onChange("");}}>
        <option value="">Choisir une classe</option>
        {[...new Set(courses.map(c=>c.classroom))].map(id=><option key={id} value={id}>
          {classes.find(c=>c.id===id)?.name||"Classe"}
        </option>)}
      </select>
    </label>
    <label>Matière
      <select aria-label="Matière enseignée" value={selected} onChange={e=>onChange(e.target.value)}>
        <option value="">Choisir une matière</option>
        {options.map(c=><option key={c.id} value={c.id}>
          {subjects.find(s=>s.id===c.subject)?.name||"Matière"}
        </option>)}
      </select>
    </label>
  </div>;
}

export default function TeacherMobileGrades({schoolId,courses,classes,subjects,periods,yearId,mode="notes"}){
  const root="schools/"+schoolId+"/";
  const [course,setCourse]=useState("");
  const [assessment,setAssessment]=useState("");
  const [assessments,setAssessments]=useState([]);
  const [roster,setRoster]=useState([]);
  const [grades,setGrades]=useState([]);
  const [drafts,setDrafts]=useState({});
  const [meanPeriod,setMeanPeriod]=useState("");
  const [means,setMeans]=useState(null);
  const [newName,setNewName]=useState("");
  const [newDate,setNewDate]=useState("");
  const [newKind,setNewKind]=useState("devoir");
  const [newWeight,setNewWeight]=useState("1");
  const [newPeriod,setNewPeriod]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const yearCourses=useMemo(()=>courses.filter(c=>c.active&&(!yearId||c.year===yearId)),[courses,yearId]);
  const chosen=assessments.find(a=>a.id===assessment);
  useEffect(()=>{setCourse("");},[schoolId,yearId]);
  useEffect(()=>{
    setAssessments([]);setAssessment("");setGrades([]);setRoster([]);setDrafts({});
    setMeans(null);setMeanPeriod("");setMessage("");setError("");
    if(!course)return;
    let active=true;
    teacherRequest(root+"courses/"+course+"/assessments")
      .then(v=>{if(active)setAssessments(v.assessments||[]);})
      .catch(e=>{if(active)setError(e.message);});
    return()=>{active=false};
  },[schoolId,course]);
  useEffect(()=>{
    setRoster([]);setGrades([]);setDrafts([]);
    if(!assessment||mode!=="notes")return;
    let active=true;
    Promise.all([teacherRequest(root+"assessments/"+assessment+"/roster"),
      teacherRequest(root+"assessments/"+assessment+"/grades")])
      .then(([a,b])=>{if(active){setRoster(a.students||[]);setGrades(b.grades||[]);setDrafts({});}})
      .catch(e=>{if(active)setError(e.message);});
    return()=>{active=false};
  },[schoolId,assessment,mode]);
  useEffect(()=>{
    setMeans(null);
    if(!course||mode!=="moyennes")return;
    let active=true;
    const endpoint=root+"courses/"+course+"/averages"+(meanPeriod?"?period="+encodeURIComponent(meanPeriod):"");
    teacherRequest(endpoint).then(data=>{if(active)setMeans(data);})
      .catch(e=>{if(active)setError(e.message)});
    return()=>{active=false};
  },[schoolId,course,meanPeriod,mode]);
  const activeAssessments=assessments.filter(a=>a.active);
  const policy=chosen?.policy?.scale||{};
  const numeric=["numeric","percentage"].includes(policy.kind);
  const editable=!!chosen&&!chosen.published&&chosen.active;
  const entries=roster.map(s=>{
    const grade=grades.find(g=>g.enrollment===s.enrollment_id);
    const draft=Object.prototype.hasOwnProperty.call(drafts,s.enrollment_id)?drafts[s.enrollment_id]:undefined;
    return {student:s,grade,raw:draft!==undefined?draft:(grade?.score??"")};
  });
  async function saveGrades(){
    const dirty=entries.filter(e=>Object.prototype.hasOwnProperty.call(drafts,e.student.enrollment_id));
    if(!dirty.length)return;
    setBusy(true);setError("");setMessage("");
    try{
      const batch=dirty.map(({student,grade,raw})=>({
        enrollment:student.enrollment_id,revision:grade?.revision||0,
        score:raw===""?null:numeric?Number(raw):raw,
      }));
      await teacherRequest(root+"assessments/"+assessment+"/grades/batch",{grades:batch});
      const latest=await teacherRequest(root+"assessments/"+assessment+"/grades");
      setGrades(latest.grades||[]);setDrafts({});
      setMessage(batch.length+" note(s) enregistrée(s) ensemble.");
    }catch(e){setError(e.message+" Aucune modification du lot n'a été acceptée en cas d'erreur de validation.");}
    finally{setBusy(false);}
  }
  async function createAssessment(e){
    e.preventDefault();setBusy(true);setError("");setMessage("");
    try{
      const created=await teacherRequest(root+"courses/"+course+"/assessments",{
        name:newName.trim(),assessment_date:newDate,kind:newKind.trim(),weight:newWeight,
        period:newPeriod||null,
      });
      const fresh=await teacherRequest(root+"courses/"+course+"/assessments");
      setAssessments(fresh.assessments||[]);setAssessment(created.id);setNewName("");setNewDate("");
      setMessage("Évaluation créée avec le barème configuré par l'établissement.");
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <div className="ym-page">
    <Card title={mode==="notes"?"Saisie des notes":"Moyennes par matière"} icon="file"
      subtitle="Les matières et classes sont limitées à vos affectations.">
      <CoursePicker courses={yearCourses} classes={classes} subjects={subjects}
        courseId={course} onChange={setCourse}/>
      {!yearCourses.length&&<p className="hint">Aucune matière n'est encore affectée à votre compte pour cette année.</p>}
      {course&&mode==="notes"&&<>
        <label className="ym-label">Évaluation
          <select aria-label="Évaluation" value={assessment} onChange={e=>{setAssessment(e.target.value);setError("");}}>
            <option value="">Choisir une évaluation</option>
            {activeAssessments.map(a=><option value={a.id} key={a.id}>{a.name} · {a.assessment_date}</option>)}
          </select>
        </label>
        <details className="ym-details"><summary>Créer une évaluation</summary>
          <form onSubmit={createAssessment} className="ym-stack">
            <label>Nom<input required maxLength={180} value={newName} onChange={e=>setNewName(e.target.value)}/></label>
            <label>Date<input required type="date" value={newDate} onChange={e=>setNewDate(e.target.value)}/></label>
            <label>Type<input required pattern="[a-z][a-z0-9_-]*" value={newKind} onChange={e=>setNewKind(e.target.value)}/></label>
            <label>Coefficient<input type="number" required min="0.01" max="1000" step="0.001" value={newWeight} onChange={e=>setNewWeight(e.target.value)}/></label>
            <label>Période (facultative)<select value={newPeriod} onChange={e=>setNewPeriod(e.target.value)}>
              <option value="">Sans période</option>
              {periods.filter(p=>p.year===yearCourses.find(c=>c.id===course)?.year&&p.active).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
            </select></label>
            <Button primary type="submit" disabled={busy}>Créer l'évaluation</Button>
          </form>
        </details>
      </>}
      {course&&mode==="moyennes"&&<label className="ym-label">Période
        <select aria-label="Période des moyennes" value={meanPeriod} onChange={e=>{setMeanPeriod(e.target.value);setError("");}}>
          <option value="">Toutes les périodes</option>
          {periods.filter(p=>p.year===yearCourses.find(c=>c.id===course)?.year).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </label>}
    </Card>
    {error&&<p role="alert" className="ym-alert">{error}</p>}
    {message&&<p role="status" className="ym-notice">{message}</p>}
    {mode==="notes"&&chosen&&<Card title={chosen.name} icon="file"
      subtitle={"Barème : "+(chosen.policy?.name||"configuré")+
        " · Coefficient "+chosen.weight+(chosen.published?" · Publiée":" · Brouillon")}>
      <p className="ym-hint">Un champ vide représente une note non renseignée, pas une note zéro.</p>
      <div className="ym-progress">{grades.filter(g=>g.status==="calculated").length} note(s) calculée(s) sur {roster.length} élèves</div>
      {entries.length===0&&<p className="hint">Aucun élève inscrit dans cette classe.</p>}
      <div className="ym-student-list">{entries.map(({student,grade,raw},i)=><div className="ym-student" key={student.enrollment_id}>
        <div className="ym-student-name"><span className="ym-num">{i+1}</span>
          <span><strong>{student.last_name} {student.first_name}</strong><small>{student.student_code}</small></span></div>
        <label>Note {numeric?(policy.kind==="percentage"?"sur 100":"sur "+policy.max):""}
          {numeric?<input aria-label={"Note de "+student.last_name} type="number" min="0"
            max={policy.kind==="percentage"?100:policy.max} step="any"
            disabled={!editable||busy} value={raw} onChange={e=>setDrafts(v=>({...v,[student.enrollment_id]:e.target.value}))}/>:
          <select aria-label={"Résultat de "+student.last_name} disabled={!editable||busy}
            value={raw} onChange={e=>setDrafts(v=>({...v,[student.enrollment_id]:e.target.value}))}>
            <option value="">Non renseigné</option>
            {(chosen.policy?.bands||[]).map((b,j)=><option value={b.label} key={j}>{b.label}</option>)}
          </select>}
        </label>
      </div>)}</div>
      {editable&&<Button primary disabled={busy||!Object.keys(drafts).length||Object.keys(drafts).length>100}
        onClick={saveGrades} icon="check">Enregistrer {Object.keys(drafts).length} modification(s)</Button>}
      {chosen.published&&<p className="ym-notice">Évaluation publiée : notes en lecture seule.</p>}
      {Object.keys(drafts).length>100&&<p className="ym-alert">Enregistrez au maximum 100 notes à la fois.</p>}
    </Card>}
    {mode==="moyennes"&&course&&<Card title="Moyennes indicatives" icon="barchart"
      subtitle="Résultats provisoires calculés avec les coefficients et barèmes des évaluations.">
      {!means?<p role="status">Calcul des moyennes…</p>:<>
        <div className="ym-summary-grid">
          <div><strong>{displayNumber(means.class_average_on_20)} / 20</strong><small>Moyenne des élèves évalués</small></div>
          <div><strong>{means.calculated_count} / {means.student_count}</strong><small>Élèves évalués</small></div>
        </div>
        <p className="ym-hint">{means.assessment_count} évaluation(s) · Les notes absentes ne comptent pas comme zéro. Les notes sur 10, 15, 100, en lettres ou compétences sont normalisées pour ce suivi, sans remplacer les bulletins officiels.</p>
        <div className="ym-student-list">{[...means.students].sort((a,b)=>
          (b.average_on_20===null?-1:a.average_on_20===null?1:Number(b.average_on_20)-Number(a.average_on_20))
        ).map(s=><div className="ym-average-row" key={s.enrollment}>
          <span><strong>{s.last_name} {s.first_name}</strong><small>{s.evaluated}/{s.expected} évaluation(s) {s.complete?"· complet":"· incomplet"}</small></span>
          <strong className="ym-score">{displayNumber(s.average_on_20)} /20</strong>
        </div>)}</div>
      </>}
    </Card>}
  </div>;
}
