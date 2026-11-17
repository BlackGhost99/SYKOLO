import React,{useEffect,useRef,useState} from "react";
import {teacherRequest} from "./teacher-mobile-api.js";

function Unit({unit,editable,busy,start,end,save}) {
 const mark=unit.mark;
 const [form,setForm]=useState({stage:mark?.stage||"",action:mark?.action||"",action_status:mark?.action_status||"",due_on:mark?.due_on||""});
 const field=(k,v)=>setForm(old=>({...old,[k]:v}));
 const disabled=!editable||busy||!unit.active;
 return <form className="yem-diary-form" onSubmit={e=>{e.preventDefault();save({unit:unit.id,revision:mark?.revision||0,...form,due_on:form.due_on||null});}}>
  <h3>{mark?.unit_title||unit.title}{!unit.active?" · Archivé":""}</h3><p>{mark?.objectives_snapshot||unit.objectives}</p>
  {!mark&&<p>Non évalué</p>}{mark?.overdue&&<p>Action de remédiation en retard.</p>}
  <label className="field">Maîtrise<select required value={form.stage} disabled={disabled} onChange={e=>field("stage",e.target.value)}>
    <option value="">Non évalué</option><option value="not_yet">À travailler</option><option value="developing">En cours</option><option value="achieved">Acquis</option></select></label>
  <label className="field">Action de remédiation<textarea maxLength={500} disabled={disabled} value={form.action} onChange={e=>field("action",e.target.value)}/></label>
  <label className="field">État de la remédiation<select disabled={disabled} value={form.action_status} onChange={e=>{const status=e.target.value;setForm(old=>({...old,action_status:status,...(!status?{action:"",due_on:""}:{})}));}}>
    <option value="">Aucune action</option><option value="planned">À engager</option><option value="ongoing">En cours</option><option value="completed">Réalisée</option></select></label>
  <label className="field">Échéance<input type="date" min={start} max={end} disabled={disabled||!form.action_status} value={form.due_on} onChange={e=>field("due_on",e.target.value)}/></label>
  {!disabled&&<button type="submit" className="yd-btn" disabled={!form.stage||Boolean(form.action.trim())!==Boolean(form.action_status)}>Enregistrer le suivi</button>}
 </form>;
}

export default function SecondaryMastery({schoolId,course,api=teacherRequest}) {
 const path="schools/"+schoolId+"/diary/courses/"+course+"/remediation";
 const [roster,setRoster]=useState(null),[student,setStudent]=useState(""),[data,setData]=useState(null),[error,setError]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false),[reload,setReload]=useState(0);
 const running=useRef(false);
 useEffect(()=>{let alive=true;setRoster(null);setStudent("");setData(null);setError("");api(path).then(r=>{if(alive)setRoster(r);}).catch(e=>{if(alive)setError(e.message);});return()=>{alive=false;};},[path,api]);
 useEffect(()=>{let alive=true;setData(null);if(student)api(path+"?enrollment="+encodeURIComponent(student)).then(r=>{if(alive)setData(r);}).catch(e=>{if(alive)setError(e.message);});return()=>{alive=false;};},[path,student,api,reload]);
 async function save(fields){
  if(running.current)return;
  running.current=true;setBusy(true);setError("");setMessage("");
  try{const mark=await api(path,{...fields,enrollment:student},"PATCH");setData(old=>old?{...old,units:old.units.map(u=>u.id===fields.unit?{...u,mark}:u)}:old);setMessage("Suivi enregistré.");}
  catch(e){setError(e.message);}finally{running.current=false;setBusy(false);}
 }
 return <section className="yem-diary" aria-label="Compétences et remédiation">
  <h3>Compétences et remédiation</h3>
  <p>Suivi individuel interne. L'absence d'évaluation ne signifie pas un échec. Ne renseignez aucune donnée médicale ou familiale.</p>
  {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  {error&&student&&<button type="button" onClick={()=>{setError("");setReload(n=>n+1);}}>Actualiser le suivi</button>}
  {!roster&&!error&&<p role="status">Chargement des élèves…</p>}
  {roster&&<label className="field">Élève<select value={student} disabled={busy} onChange={e=>{setStudent(e.target.value);setMessage("");setError("");}}>
   <option value="">Choisir un élève</option>{roster.students.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>}
  {roster?.truncated&&<p>Les 500 premiers élèves sont affichés.</p>}
  {student&&!data&&!error&&<p role="status">Chargement du suivi…</p>}
  {data&&!data.writable&&<p>Consultation seule.</p>}
  {data?.truncated&&<p>Les 500 premiers chapitres sont affichés.</p>}
  {data?.units.length===0&&<p>Aucun chapitre configuré pour ce cours.</p>}
  {data?.units.map(u=><Unit key={student+":"+u.id+":"+(u.mark?.revision||0)} unit={u} editable={data.writable} busy={busy} start={data.year_start} end={data.year_end} save={save}/>)}
 </section>;
}
