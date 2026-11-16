import React,{useEffect,useState} from "react";
import {Card} from "./yem-ui.jsx";
import {teacherRequest} from "./teacher-mobile-api.js";

function MarkForm({editable,criterion,mark,stages,statuses,save}){
  const guidance=mark?.snapshot?.remediation??criterion.remediation;
  return <form className="yf-form" onSubmit={event=>{
    event.preventDefault();
    save(criterion.id,mark?.revision||0,Object.fromEntries(new FormData(event.currentTarget)));
  }}>
    <h4>{mark?.snapshot?.label||criterion.label}</h4>
    {guidance&&<p>Piste proposée · {guidance}</p>}
    <fieldset className="yf-grid" disabled={!editable}>
      <label className="field">Maîtrise
        <select name="stage" defaultValue={mark?.stage||""} required>
          <option value="">Choisir un niveau</option>
          {Object.entries(stages).map(([key,label])=><option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <label className="field">Remédiation
        <select name="remediation_status" defaultValue={mark?.remediation_status||""}>
          <option value="">Aucune action renseignée</option>
          {Object.entries(statuses).map(([key,label])=><option key={key} value={key}>{label}</option>)}
        </select>
      </label>
      <label className="field">Suivi individuel
        <textarea name="follow_up" maxLength={500} rows={2} defaultValue={mark?.follow_up||""}/>
      </label>
    </fieldset>
    {editable&&<button type="submit">Enregistrer le suivi</button>}
  </form>;
}

function MasteryRoster({path,year,classroom,milestone}){
  const [data,setData]=useState(null);
  const [enrollment,setEnrollment]=useState("");
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [busy,setBusy]=useState(false);
  const [reload,setReload]=useState(0);
  useEffect(()=>{
    let alive=true;
    teacherRequest(path+"?"+new URLSearchParams({year,classroom,milestone}))
      .then(result=>{if(alive)setData(result);})
      .catch(failure=>{if(alive)setError(failure.message);});
    return()=>{alive=false;};
  },[path,year,classroom,milestone,reload]);

  async function save(criterion,revision,fields){
    setBusy(true);setError("");setNotice("");
    try {
      const mark=await teacherRequest(path,{year,classroom,milestone,enrollment,criterion,revision,...fields},"PATCH");
      setData(previous=>({...previous,students:previous.students.map(row=>row.enrollment===enrollment
        ? {...row,marks:[...row.marks.filter(item=>item.criterion!==criterion),mark]}:row)}));
      setNotice("Suivi enregistré.");
    }catch(failure){setError(failure.message);}
    finally{setBusy(false);}
  }

  const pupil=data?.students.find(row=>row.enrollment===enrollment);
  const criteria=new Map((data?.criteria||[]).map(item=>[item.id,item]));
  const records=pupil?.current&&data?.editable ? new Map(criteria) : new Map();
  for(const mark of pupil?.marks||[]){
    if(!records.has(mark.criterion))records.set(mark.criterion,mark.snapshot);
  }
  return <>
    {error&&<p role="alert">{error}</p>}
    {error&&<button type="button" onClick={()=>{setError("");setData(null);setReload(value=>value+1);}}>
      Recharger le suivi
    </button>}
    {notice&&<p role="status">{notice}</p>}
    {!data&&!error&&<p role="status">Chargement du suivi…</p>}
    {data?.students.length===0&&<p>Aucun élève disponible pour ce palier.</p>}
    {!!data?.students.length&&<label className="field">Élève
      <select value={enrollment} disabled={busy} onChange={event=>{setEnrollment(event.target.value);setNotice("");}}>
        <option value="">Choisir un élève</option>
        {data.students.map(row=><option key={row.enrollment} value={row.enrollment}>{row.name}</option>)}
      </select>
    </label>}
    {pupil&&records.size===0&&<p>Aucun suivi enregistré. Les critères se définissent dans le référentiel du niveau.</p>}
    {[...records].map(([id,criterion])=>{
      const mark=pupil.marks.find(record=>record.criterion===id);
      return <MarkForm key={enrollment+":"+id+":"+(mark?.revision||0)} criterion={criterion} mark={mark}
        stages={data.stages} statuses={data.remediation_statuses}
        editable={data.editable&&pupil.current&&criteria.has(id)&&!busy} save={save}/>;
    })}
  </>;
}

export default function PrimaryMastery({schoolId,yearId}){
  const path="schools/"+schoolId+"/academic/primary-mastery";
  const [catalog,setCatalog]=useState(null);
  const [classroom,setClassroom]=useState("");
  const [milestone,setMilestone]=useState("");
  const [error,setError]=useState("");
  useEffect(()=>{
    let alive=true;
    teacherRequest(path+"?"+new URLSearchParams({year:yearId}))
      .then(result=>{if(alive)setCatalog({classrooms:result.classrooms||[],milestones:result.milestones||[]});})
      .catch(failure=>{if(alive)setError(failure.message);});
    return()=>{alive=false;};
  },[path,yearId]);
  return <Card title="Suivi des acquis et des remédiations" icon="layers">
    {error&&<p role="alert">{error}</p>}
    {!catalog&&!error&&<p role="status">Chargement des classes et des paliers…</p>}
    {catalog&&!catalog.classrooms.length&&<p>Aucune classe primaire accessible.</p>}
    {catalog&&!!catalog.classrooms.length&&!catalog.milestones.length&&
      <p>Aucun palier primaire configuré pour cette année.</p>}
    {!!catalog?.classrooms.length&&!!catalog.milestones.length&&<div className="yf-grid">
      <label className="field">Classe primaire
        <select value={classroom} onChange={event=>setClassroom(event.target.value)}>
          <option value="">Choisir une classe</option>
          {catalog.classrooms.map(room=><option key={room.id} value={room.id}>{room.name}</option>)}
        </select>
      </label>
      <label className="field">Palier du suivi
        <select value={milestone} onChange={event=>setMilestone(event.target.value)}>
          <option value="">Choisir un palier</option>
          {catalog.milestones.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
    </div>}
    {classroom&&milestone&&<MasteryRoster key={classroom+":"+milestone} path={path} year={yearId}
      classroom={classroom} milestone={milestone}/>}
  </Card>;
}
