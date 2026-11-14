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
  const [notesPeriod,setNotesPeriod]=useState("");
  const [notesKind,setNotesKind]=useState("");
  const [peerGrades,setPeerGrades]=useState({});
  const availablePeriods=periods.filter(p=>p.year===yearCourses.find(c=>c.id===course)?.year);
  const filteredAssessments=activeAssessments.filter(a=>
    (!notesPeriod||a.period===notesPeriod)&&(!notesKind||a.kind===notesKind));
  // One assessment is edited at a time. Other columns are read-only until selected.
  // Each column's save is an independent atomic server-side transaction.
  const columns=chosen?[
    chosen,...filteredAssessments.filter(a=>a.id!==chosen.id).slice(0,3),
  ]:[];
  useEffect(()=>{
    let alive=true;setPeerGrades({});
    if(!chosen||mode!=="notes")return;
    Promise.all(columns.filter(a=>a.id!==chosen.id).map(async a=>{
      try{const result=await teacherRequest(root+"assessments/"+a.id+"/grades");
        return [a.id,result.grades||[]];}
      catch{return [a.id,[]];}
    })).then(rows=>{if(alive)setPeerGrades(Object.fromEntries(rows));});
    return()=>{alive=false};
  },[schoolId,course,assessment,notesPeriod,notesKind,mode,assessments]);
  const valuesByAssessment=Object.fromEntries(columns.map(a=>[
    a.id,a.id===assessment?grades:(peerGrades[a.id]||[]),
  ]));
  const progressSaved=columns.reduce((n,a)=>n+
    (valuesByAssessment[a.id]||[]).filter(g=>g.status==="calculated").length,0);
  const progressTotal=roster.length*columns.length;
  const percent=progressTotal?Math.round(100*progressSaved/progressTotal):0;
  const meanValues=(means?.students||[]).filter(s=>s.average_on_20!==null).map(s=>Number(s.average_on_20));
  const lowest=meanValues.length?Math.min(...meanValues):null;
  const highest=meanValues.length?Math.max(...meanValues):null;
  const coverage=means?.student_count?Math.round(100*(means.calculated_count||0)/means.student_count):0;
  const buckets=[
    {label:"< 10",min:0,max:10},{label:"10 – 12",min:10,max:12},{label:"12 – 14",min:12,max:14},
    {label:"14 – 16",min:14,max:16},{label:"≥ 16",min:16,max:Infinity},
  ];
  const ranked=[...(means?.students||[])].sort((a,b)=>
    (b.average_on_20===null?-1:a.average_on_20===null?1:Number(b.average_on_20)-Number(a.average_on_20)));
  function exportAverages(){
    if(!means)return;
    const escape=value=>'"'+String(value??"").replaceAll('"','""')+'"';
    const rows=[["Élève","Matricule","Moyenne indicative sur 20","Évaluations saisies","Évaluations prévues"],
      ...ranked.map(s=>[s.last_name+" "+s.first_name,s.student_code||"",s.average_on_20??"",
        s.evaluated,s.expected])];
    const text="\uFEFF"+rows.map(r=>r.map(escape).join(";")).join("\r\n");
    const url=URL.createObjectURL(new Blob([text],{type:"text/csv;charset=utf-8"}));
    const link=document.createElement("a");link.href=url;link.download="yem-moyennes-provisoires.csv";
    document.body.append(link);link.click();link.remove();URL.revokeObjectURL(url);
  }
  return <div className="ym-page ym-prof-course-screen">
    <section className="ym-course-filters">
      <h1>{mode==="notes"?"Saisie des notes":"Moyennes par matière"}</h1>
      <CoursePicker courses={yearCourses} classes={classes} subjects={subjects}
        courseId={course} onChange={setCourse}/>
      {!yearCourses.length&&<p className="ym-empty">Aucune matière affectée pour cette année scolaire.</p>}
      {course&&mode==="notes"&&<>
        <div className="ym-filter-pills" role="group" aria-label="Filtres des notes">
          <span>Période</span><span>Évaluations</span><span>Barème YEM</span>
        </div>
        <div className="ym-filter-row">
          <label>Période
            <select aria-label="Période des notes" value={notesPeriod}
              onChange={e=>{setNotesPeriod(e.target.value);setAssessment("");}}>
              <option value="">Toutes les périodes</option>
              {availablePeriods.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label>Type d'évaluation
            <select aria-label="Type d'évaluation" value={notesKind}
              onChange={e=>{setNotesKind(e.target.value);setAssessment("");}}>
              <option value="">Tous les types</option>
              {[...new Set(activeAssessments.map(a=>a.kind))].map(kind=><option key={kind} value={kind}>{kind}</option>)}
            </select>
          </label>
        </div>
        <label className="ym-label">Évaluation à modifier
          <select aria-label="Évaluation" value={assessment} onChange={e=>{setAssessment(e.target.value);setError("");}}>
            <option value="">Choisir une évaluation</option>
            {filteredAssessments.map(a=><option key={a.id} value={a.id}>
              {a.name} · {a.assessment_date}{a.published?" · publiée":""}
            </option>)}
          </select>
        </label>
        <details className="ym-details"><summary>Créer une évaluation</summary>
          <form onSubmit={createAssessment} className="ym-stack">
            <label>Nom<input required maxLength={180} value={newName} onChange={e=>setNewName(e.target.value)}/></label>
            <label>Date<input required type="date" value={newDate} onChange={e=>setNewDate(e.target.value)}/></label>
            <label>Type<input required pattern="[a-z][a-z0-9_-]*" value={newKind} onChange={e=>setNewKind(e.target.value)}/></label>
            <label>Coefficient<input type="number" required min="0.01" max="1000" step="0.001"
              value={newWeight} onChange={e=>setNewWeight(e.target.value)}/></label>
            <label>Période (facultative)<select value={newPeriod} onChange={e=>setNewPeriod(e.target.value)}>
              <option value="">Sans période</option>{availablePeriods.filter(p=>p.active).map(p=>
                <option key={p.id} value={p.id}>{p.name}</option>)}
            </select></label>
            <Button primary type="submit" disabled={busy}>Créer l'évaluation</Button>
          </form>
        </details>
      </>}
      {course&&mode==="moyennes"&&<label className="ym-label">Période
        <select aria-label="Période des moyennes" value={meanPeriod} onChange={e=>{setMeanPeriod(e.target.value);setError("");}}>
          <option value="">Toutes les périodes</option>
          {availablePeriods.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </label>}
    </section>
    {error&&<p role="alert" className="ym-alert">{error}</p>}
    {message&&<p role="status" className="ym-notice">{message}</p>}
    {mode==="notes"&&chosen&&<section className="ym-note-sheet" aria-label="Cahier de notes">
      <div className="ym-section-heading"><h2>Progression de la saisie</h2><strong>{percent} %</strong></div>
      <p className="ym-hint">{progressSaved} notes calculées sur {progressTotal} cellules affichées.
        Sélectionnez une évaluation pour modifier sa colonne.</p>
      <progress className="ym-progress-track" value={progressSaved} max={progressTotal||1}
        aria-label="Progression de la saisie"/>
      <div className="ym-section-heading">
        <h2>Liste des élèves ({roster.length})</h2><span>{columns.length} évaluation(s)</span>
      </div>
      {!roster.length&&<p className="ym-empty">Aucun élève inscrit dans cette classe.</p>}
      <div className="ym-grade-table-wrap" role="region" aria-label="Tableau des notes par évaluation" tabIndex={0}>
        <table className="ym-grade-table"><thead><tr>
          <th scope="col">N°</th><th scope="col" className="ym-grade-student">Nom et prénom</th>
          {columns.map(a=><th scope="col" key={a.id} className={a.id===chosen.id?"ym-current-assessment":""}>
            <button type="button" onClick={()=>{setAssessment(a.id);setError("");}} aria-label={"Modifier "+a.name}>
              {a.name}<small>{a.policy?.scale?.kind==="numeric"?"/ "+a.policy.scale.max:
                a.policy?.scale?.kind==="percentage"?"%":"Barème configuré"}</small>
            </button></th>)}
        </tr></thead><tbody>{entries.map(({student,grade,raw},index)=><tr key={student.enrollment_id}>
          <td>{index+1}</td>
          <th scope="row" className="ym-grade-student">{student.last_name} {student.first_name}</th>
          {columns.map(a=>{
            const g=a.id===chosen.id?grade:(valuesByAssessment[a.id]||[]).find(item=>item.enrollment===student.enrollment_id);
            const editableCell=a.id===chosen.id&&editable;
            const scale=a.policy?.scale||{};
            const number=["numeric","percentage"].includes(scale.kind);
            return <td key={a.id} className={editableCell?"ym-grade-active-cell":""}>
              {a.id===chosen.id?(number?
                <input aria-label={"Note de "+student.last_name} type="number" inputMode="decimal"
                  min={0} max={scale.kind==="percentage"?100:scale.max} step="any"
                  disabled={!editableCell||busy} value={raw} placeholder="—"
                  onChange={e=>setDrafts(v=>({...v,[student.enrollment_id]:e.target.value}))}/>:
                <select aria-label={"Résultat de "+student.last_name} disabled={!editableCell||busy}
                  value={raw} onChange={e=>setDrafts(v=>({...v,[student.enrollment_id]:e.target.value}))}>
                  <option value="">—</option>
                  {(a.policy?.bands||[]).map((b,j)=><option value={b.label} key={j}>{b.label}</option>)}
                </select>):<span className="ym-grade-readonly">{g?.score===null||g?.score===undefined?"—":
                  typeof g.score==="object"?(g.label||"Renseigné"):String(g.score)}</span>}
            </td>;
          })}
        </tr>)}</tbody></table>
      </div>
      <p className="ym-grade-mobile-hint">Sur téléphone, choisissez l’évaluation à modifier dans le filtre ci-dessus.</p>
      <p className="ym-hint">Un champ vide signifie « non renseigné », jamais zéro. Sur écran large, touchez l’en-tête d’une autre colonne pour la modifier.</p>
      {editable&&<Button primary className="ym-full-btn"
        disabled={busy||!Object.keys(drafts).length||Object.keys(drafts).length>100}
        onClick={saveGrades} icon="check">Enregistrer {Object.keys(drafts).length} modification(s)</Button>}
      {chosen.published&&<p className="ym-notice">Évaluation publiée : notes en lecture seule.</p>}
      {Object.keys(drafts).length>100&&<p className="ym-alert">Enregistrez au maximum 100 notes à la fois.</p>}
    </section>}
    {mode==="moyennes"&&course&&<section className="ym-averages-view">
      {!means?<p role="status" className="ym-hint">Calcul des moyennes…</p>:<>
        <p className="ym-hint">Résultats provisoires calculés pour cette matière · {means.assessment_count} évaluation(s).
          Pondérations et barèmes issus de YEM.</p>
        <div className="ym-stats-four">
          <div><span>Moyenne de la classe</span><strong>{displayNumber(means.class_average_on_20)+" / 20"}</strong></div>
          <div><span>Meilleure moyenne</span><strong>{displayNumber(highest)} <small>/ 20</small></strong></div>
          <div><span>Plus faible moyenne</span><strong>{displayNumber(lowest)} <small>/ 20</small></strong></div>
          <div><span>Moyennes calculées</span><strong>{coverage} %</strong><small>({means.calculated_count} sur {means.student_count})</small></div>
        </div>
        <section className="ym-chart-card" aria-label="Répartition des moyennes">
          <h2>Répartition des moyennes</h2>
          {meanValues.length===0?<p className="ym-empty">Aucune moyenne à représenter.</p>:
          <div className="ym-chart-bars">{buckets.map(b=>{
            const count=meanValues.filter(x=>x>=b.min&&x<b.max).length;
            const percentage=Math.round(100*count/meanValues.length);
            return <div className="ym-chart-bin" key={b.label}>
              <strong>{percentage} %</strong><div className="ym-chart-bar-shell">
                <div style={{height:percentage+"%"}} className="ym-chart-bar"/></div>
              <span>{b.label}</span>
            </div>;
          })}</div>}
        </section>
        <section className="ym-ranking" aria-label="Classement des élèves">
          <h2>Classement des élèves</h2>
          {!ranked.length&&<p className="ym-empty">Aucun élève dans cette classe.</p>}
          {ranked.map((s,index)=><div className="ym-ranking-row" key={s.enrollment}>
            <span className="ym-rank">{s.average_on_20===null?"—":index+1}</span>
            <span className="ym-ranking-name"><strong>{s.last_name} {s.first_name}</strong>
              <small>{s.evaluated}/{s.expected} évaluation(s) {s.complete?"· complet":"· incomplet"}</small></span>
            <strong className="ym-ranking-mark">{displayNumber(s.average_on_20)} <small>/20</small></strong>
          </div>)}
        </section>
        <Button icon="file" className="ym-full-btn" onClick={exportAverages}>Exporter les moyennes</Button>
        <p className="ym-hint">Les notes manquantes ne sont pas transformées en zéros.
          Cet affichage sur 20 est indicatif : la validation officielle des bulletins reste réservée aux responsables habilités.</p>
      </>}
    </section>}
  </div>;
}
