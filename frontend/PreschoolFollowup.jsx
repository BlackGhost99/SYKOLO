import React,{useEffect,useState} from "react";
import {Card} from "./yem-ui.jsx";
import {teacherRequest} from "./teacher-mobile-api.js";

function DailyRoster({path,classroom,day}){
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [busy,setBusy]=useState("");
  useEffect(()=>{
    let alive=true;
    teacherRequest(path+"?"+new URLSearchParams({classroom,day}))
      .then(result=>{if(alive)setData(result);})
      .catch(e=>{if(alive)setError(e.message);});
    return()=>{alive=false;};
  },[path,classroom,day]);

  async function save(event,row,action="observation"){
    event.preventDefault();
    setBusy(row?.enrollment||"reference");setError("");setNotice("");
    const form=event.currentTarget;
    try{
      const fields=Object.fromEntries(new FormData(form));
      const body={classroom,day,action,...fields};
      if(row)body.enrollment=row.enrollment;
      if(action==="observation")body.revision=row.revision;
      if(action==="mark"){
        body.revision=row.marks.find(mark=>mark.competency===fields.competency)?.revision||0;
      }
      const saved=await teacherRequest(path,body);
      if(action==="reference"){
        setData(previous=>({...previous,competencies:[
          ...previous.competencies.filter(item=>item.id!==saved.id),saved,
        ].sort((a,b)=>a.label.localeCompare(b.label))}));
      }else{
        setData(previous=>({...previous,students:previous.students.map(student=>{
          if(student.enrollment!==row.enrollment)return student;
          if(action==="mark")return {...student,marks:[...student.marks.filter(
            mark=>mark.competency!==saved.competency),saved]};
          if(action==="liaison")return {...student,liaison:[...student.liaison.filter(item=>item.id!==saved.id),saved]};
          return {...student,...saved};
        })}));
      }
      if(action==="liaison"||action==="reference")form.reset();
      setNotice({observation:"Observation enregistrée.",reference:"Compétence ajoutée.",
        mark:"Compétence évaluée.",liaison:"Message publié dans le carnet de liaison."}[action]);
    }catch(e){setError(e.message);}
    finally{setBusy("");}
  }

  return <>
    {error&&<p role="alert">{error}</p>}
    {notice&&<p role="status">{notice}</p>}
    {!data&&!error&&<p role="status">Chargement du groupe…</p>}
    {data?.can_manage_reference&&<form className="yf-form" onSubmit={e=>save(e,null,"reference")}>
      <label className="field">Nouvelle compétence pour ce niveau
        <input name="label" maxLength={120} required/>
      </label>
      <button type="submit" disabled={Boolean(busy)}>Ajouter au référentiel</button>
    </form>}
    {data?.students.length===0&&<p>Aucun enfant inscrit à cette date.</p>}
    {data?.students.map(row=><section key={row.enrollment}>
    <form className="yf-form" key={row.revision} onSubmit={e=>save(e,row)}>
      <label className="field">Observation de {row.name}
        <textarea name="observation" defaultValue={row.observation} rows={2} maxLength={600}
          required readOnly={!data.editable||!row.current} disabled={Boolean(busy)}/>
      </label>
      {data.editable&&row.current&&<button type="submit" disabled={Boolean(busy)}>Enregistrer</button>}
    </form>
    <details>
      <summary>Compétences · {row.name}</summary>
      {!!row.marks?.length&&<ul>{row.marks.map(mark=><li key={mark.competency}>
        {data.competencies.find(item=>item.id===mark.competency)?.label} · {data.stages[mark.stage]}
      </li>)}</ul>}
      {data.editable&&row.current&&!!data.competencies?.length&&
        <form className="yf-form" onSubmit={e=>save(e,row,"mark")}>
          <div className="yf-grid">
            <label className="field">Compétence de {row.name}
              <select name="competency" required defaultValue="">
                <option value="">Choisir une compétence</option>
                {data.competencies.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label className="field">Niveau observé pour {row.name}
              <select name="stage" required defaultValue="">
                <option value="">Choisir un niveau</option>
                {Object.entries(data.stages).map(([id,label])=><option key={id} value={id}>{label}</option>)}
              </select>
            </label>
          </div>
          <button type="submit" disabled={Boolean(busy)}>Enregistrer la compétence</button>
        </form>}
    </details>
    <details>
      <summary>Carnet de liaison · {row.name}</summary>
      {!!row.liaison?.length&&<ul>{row.liaison.map(item=><li key={item.id}>{item.message}</li>)}</ul>}
      {data.editable&&row.current&&<form className="yf-form" onSubmit={e=>save(e,row,"liaison")}>
        <label className="field">Message à la famille de {row.name}
          <textarea name="message" required maxLength={600} rows={2}/>
        </label>
        <button type="submit" disabled={Boolean(busy)}>Publier dans le carnet de liaison</button>
      </form>}
    </details>
    </section>)}
  </>;
}

export default function PreschoolFollowup({schoolId,yearId}){
  const path="schools/"+schoolId+"/academic/preschool-followup";
  const [rooms,setRooms]=useState(null);
  const [classroom,setClassroom]=useState("");
  const [day,setDay]=useState("");
  const [error,setError]=useState("");
  useEffect(()=>{
    let alive=true;
    setRooms(null);setClassroom("");setError("");
    if(yearId)teacherRequest(path+"?"+new URLSearchParams({year:yearId}))
      .then(result=>{if(alive)setRooms(result.classrooms||[]);})
      .catch(e=>{if(alive)setError(e.message);});
    return()=>{alive=false;};
  },[path,yearId]);

  return <Card title="Suivi quotidien" icon="calendar">
    {!yearId&&<p>Sélectionnez une année scolaire.</p>}
    {error&&<p role="alert">{error}</p>}
    {yearId&&!rooms&&!error&&<p role="status">Chargement des groupes…</p>}
    {rooms?.length===0&&<p>Aucun groupe de crèche ou de préscolaire accessible pour cette année.</p>}
    {!!rooms?.length&&<>
      <p>Réservé à l’équipe pédagogique. Notez les activités, la participation et les observations utiles à l’accompagnement de l’enfant.</p>
      <div className="yf-grid">
        <label className="field">Groupe
          <select value={classroom} onChange={e=>setClassroom(e.target.value)}>
            <option value="">Choisir un groupe</option>
            {rooms.map(room=><option key={room.id} value={room.id}>{room.name}</option>)}
          </select>
        </label>
        <label className="field">Date du suivi
          <input type="date" value={day} onChange={e=>setDay(e.target.value)}/>
        </label>
      </div>
      {classroom&&day&&<DailyRoster key={classroom+":"+day} path={path} classroom={classroom} day={day}/>}
    </>}
  </Card>;
}
