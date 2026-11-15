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

  async function save(event,row){
    event.preventDefault();
    setBusy(row.enrollment);setError("");setNotice("");
    try{
      const body={classroom,day,enrollment:row.enrollment,revision:row.revision,
        observation:new FormData(event.currentTarget).get("observation")};
      const saved=await teacherRequest(path,body);
      setData(previous=>({...previous,students:previous.students.map(student=>
        student.enrollment===row.enrollment?{...student,...saved}:student)}));
      setNotice("Observation enregistrée.");
    }catch(e){setError(e.message);}
    finally{setBusy("");}
  }

  return <>
    {error&&<p role="alert">{error}</p>}
    {notice&&<p role="status">{notice}</p>}
    {!data&&!error&&<p role="status">Chargement du groupe…</p>}
    {data?.students.length===0&&<p>Aucun enfant inscrit à cette date.</p>}
    {data?.students.map(row=><form className="yf-form" key={row.enrollment+":"+row.revision}
      onSubmit={e=>save(e,row)}>
      <label className="field">Observation de {row.name}
        <textarea name="observation" defaultValue={row.observation} rows={2} maxLength={600}
          required readOnly={!data.editable||!row.current} disabled={Boolean(busy)}/>
      </label>
      {data.editable&&row.current&&<button type="submit" disabled={Boolean(busy)}>Enregistrer</button>}
    </form>)}
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
