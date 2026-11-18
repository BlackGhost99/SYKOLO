import React,{useEffect,useState,useRef} from "react";
import {teacherRequest} from "./teacher-mobile-api.js";

const labels={not_started:"Non commencé",in_progress:"En cours",completed:"Dispensé"};
function ProgressUnit({unit, writable, entries, start, end, save, busy}) {
  const [form,setForm]=useState(unit);
  useEffect(()=>setForm(unit),[unit]);
  const change=(key,value)=>setForm(old=>({...old,[key]:value}));
  const edit=writable&&unit.active;
  const disabled=!edit||busy;
  return <article className="yem-diary-form">
    <div className="yem-diary-entry-head"><h3>{unit.title}</h3><span>{!unit.active?"Archivé":labels[unit.status]}{unit.overdue?" · En retard":""}{unit.completed_late?" · Dispensé en retard":""}</span></div>
    {unit.objectives&&<p className="yem-diary-text">{unit.objectives}</p>}
    <label className="field">Début prévu<input type="date" min={start} max={end} disabled={disabled} value={form.planned_start||""} onChange={e=>change("planned_start",e.target.value||null)}/></label>
    <label className="field">Fin prévue<input type="date" min={form.planned_start||start} max={end} disabled={disabled} value={form.planned_end||""} onChange={e=>change("planned_end",e.target.value||null)}/></label>
    <label className="field">Avancement<select disabled={disabled} value={form.status} onChange={e=>{const status=e.target.value;setForm(old=>({...old,status,completed_on:status==="completed"?old.completed_on:null,evidence:status==="not_started"?null:old.evidence}));}}>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
    {form.status==="completed"&&<label className="field">Date effective<input type="date" min={start} max={end} disabled={disabled} value={form.completed_on||""} onChange={e=>change("completed_on",e.target.value||null)}/></label>}
    {form.status!=="not_started"&&<label className="field">Séance justificative (facultatif)<select disabled={disabled} value={form.evidence||""} onChange={e=>change("evidence",e.target.value||null)}>
      <option value="">Aucune séance associée</option>{form.evidence&&!entries.some(e=>e.id===form.evidence)&&<option value={form.evidence}>Séance déjà associée</option>}
      {entries.map(e=><option key={e.id} value={e.id}>{e.day} · {e.title}</option>)}
    </select></label>}
    {edit&&<button type="button" className="yd-btn" disabled={busy||(form.status==="completed"&&!form.completed_on)} onClick={()=>save({unit:unit.id,revision:unit.revision,planned_start:form.planned_start||null,planned_end:form.planned_end||null,status:form.status,completed_on:form.completed_on||null,evidence:form.evidence||null})}>Enregistrer la progression</button>}
  </article>;
}
export default function CourseProgress({schoolId,course,entries=[],api=teacherRequest}) {
  const path="schools/"+schoolId+"/diary/courses/"+course+"/progress";
  const [data,setData]=useState(null),[error,setError]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
  const running=useRef(false);
  const [refresh,setRefresh]=useState(0);
  useEffect(()=>{
    let active=true;setData(null);setError("");
    api(path).then(r=>{if(active)setData(r);}).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;};
  },[path,api,refresh]);
  async function save(payload){
    if(running.current)return;
    running.current=true;setBusy(true);setError("");setMessage("");
    try{await api(path,payload,"PATCH");setMessage("Progression enregistrée.");setRefresh(n=>n+1);}
    catch(e){setError(e.message);}
    finally{running.current=false;setBusy(false);}
  }
  const s=data?.summary;
  return <section className="yem-diary" aria-label="Progression du programme">
    <h3>Progression du programme</h3>
    <p>Chapitres dispensés selon les déclarations pédagogiques, sans calcul de maîtrise des élèves.</p>
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    {!data&&!error&&<p role="status">Chargement de la progression…</p>}
    {data&&<>
      <div className="yem-diary-form">
        <strong>{s.completed} / {s.total} chapitres dispensés{s.percent===null?"":" · "+s.percent+" %"}</strong>
        {s.total>0&&<progress aria-label="Chapitres dispensés" value={s.completed} max={s.total}/>}
        <p>{s.in_progress} en cours · {s.overdue} échéance(s) dépassée(s) · {s.unplanned} sans échéance · {s.completed_late} dispensé(s) en retard</p>
      </div>
      {!data.writable&&<p>Consultation seule.</p>}
      {!data.units.length&&<p>Aucun chapitre configuré. Créez les unités dans Matières et programmes.</p>}
      {data.truncated&&<p>Les 500 premiers chapitres sont affichés. La synthèse porte sur tous les chapitres actifs.</p>}
      {data.units.map(unit=><ProgressUnit key={unit.id} unit={unit} writable={data.writable} entries={entries} start={data.year_start} end={data.year_end} save={save} busy={busy}/>)}
    </>}
  </section>;
}
