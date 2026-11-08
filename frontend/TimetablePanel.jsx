import React,{useEffect,useState} from "react";
import {TableScroll} from "./yem-ui.jsx";
async function api(path,body,method){
  if(body!==undefined)await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const r=await fetch("/api/v1/"+path,{
    method:method||(body===undefined?"GET":"POST"),credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  if(!r.headers.get("content-type")?.includes("application/json"))throw Error("Serveur indisponible.");
  const result=await r.json();
  if(!r.ok)throw Error((result.error||"Accès refusé.")+(result.conflicts?" : "+result.conflicts.map(c=>c.resources.join(", ")+" ("+c.start+"–"+c.end+")").join("; "):""));
  return result;
}
const DAYS=["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"];
export default function TimetablePanel({schoolId,workingYearId="",onWorkingYearChange}){
  const root="schools/"+schoolId+"/",base=root+"timetable/";
  const [years,setYears]=useState([]),[classes,setClasses]=useState([]),
    [courses,setCourses]=useState([]),[subjects,setSubjects]=useState([]),
    [rooms,setRooms]=useState([]),[slots,setSlots]=useState([]),
    [entries,setEntries]=useState([]),[instructors,setInstructors]=useState([]),
    [staff,setStaff]=useState([]),[assignments,setAssignments]=useState([]);
  const [year,setYear]=useState(workingYearId),[classroom,setClassroom]=useState(""),
    [course,setCourse]=useState(""),[instructor,setInstructor]=useState(""),
    [slot,setSlot]=useState(""),[room,setRoom]=useState(""),
    [weekday,setWeekday]=useState("0"),[from,setFrom]=useState(""),[to,setTo]=useState(""),
    [editing,setEditing]=useState(""),[busy,setBusy]=useState(false),
    [error,setError]=useState(""),[visible,setVisible]=useState(true);
  const [roomCode,setRoomCode]=useState(""),[roomName,setRoomName]=useState(""),[roomCapacity,setRoomCapacity]=useState("");
  const [slotCode,setSlotCode]=useState(""),[slotLabel,setSlotLabel]=useState(""),[slotStart,setSlotStart]=useState(""),[slotEnd,setSlotEnd]=useState("");
  useEffect(()=>{setYear(workingYearId);setClassroom("");setEditing("");setCourse("");setSlot("");setInstructor("");},[workingYearId,schoolId]);
  async function refresh(){
    const [r,s,e]=await Promise.all([api(base+"rooms"),api(base+"slots"),api(base+"entries")]);
    setRooms(r.rooms||[]);setSlots(s.slots||[]);setEntries(e.entries||[]);
  }
  useEffect(()=>{
    let active=true;
    Promise.all([api(root+"academic/years"),api(root+"academic/classes"),api(root+"courses"),
      api(root+"subjects"),api(base+"rooms"),api(base+"slots"),api(base+"entries"),
      api(root+"staff").catch(()=>({staff:[]})),
      api(root+"staff-assignments").catch(()=>({assignments:[]}))])
      .then(([y,c,co,s,r,t,e,st,a])=>{
        if(!active)return;
        setYears(y.years||[]);setClasses(c.classes||[]);setCourses(co.courses||[]);
        setSubjects(s.subjects||[]);setRooms(r.rooms||[]);setSlots(t.slots||[]);
        setEntries(e.entries||[]);setStaff(st.staff||[]);setAssignments(a.assignments||[]);
      }).catch(()=>{if(active)setVisible(false)});
    return()=>{active=false};
  },[schoolId]);
  useEffect(()=>{
    let active=true;
    setInstructors([]);
    if(course)api(root+"courses/"+course+"/instructors").then(v=>{if(active)setInstructors(v.instructors||[])})
      .catch(()=>{if(active)setInstructors([])});
    return()=>{active=false};
  },[schoolId,course]);
  async function run(fn){
    setBusy(true);setError("");
    try{await fn();await refresh()}catch(e){setError(e.message)}finally{setBusy(false)}
  }
  function reset(){setEditing("");setCourse("");setInstructor("");setSlot("");setRoom("")}
  function subject(id){return subjects.find(s=>s.id===courses.find(c=>c.id===id)?.subject)?.name||"Matière"}
  function teacherName(i){
    const a=assignments.find(x=>x.id===i.staff_assignment);
    const p=staff.find(x=>x.id===a?.staff);
    return p?p.last_name+" "+p.first_name:"Intervenant affecté";
  }
  function edit(e){
    setYear(e.year);setClassroom(e.classroom);setCourse(e.course);setEditing(e.id);
    setSlot(e.slot);setRoom(e.room||"");setWeekday(String(e.weekday));
    setFrom(e.effective_from);setTo(e.effective_to);
  }
  if(!visible)return null;
  const selected=entries.filter(e=>e.active&&(!year||e.year===year)&&(!classroom||e.classroom===classroom));
  const selectedCourses=courses.filter(c=>c.active&&c.year===year&&c.classroom===classroom);
  return <section className="card" aria-label="Emplois du temps" style={{marginTop:"1rem"}}>
    <h2>Emplois du temps et planification</h2>
    <p className="hint">Le serveur empêche les doubles réservations de salle, de classe et d'enseignant.</p>
    <div className="two">
      <label className="field">Année scolaire<select value={year} onChange={e=>{setYear(e.target.value);onWorkingYearChange?.(e.target.value);setClassroom("");reset()}}>
        <option value="">Toutes les années</option>
        {years.map(y=><option key={y.id} value={y.id}>{y.name}{y.active?"":" (archivée)"}</option>)}
      </select></label>
      <label className="field">Classe<select value={classroom} onChange={e=>{setClassroom(e.target.value);reset()}}>
        <option value="">Toutes les classes</option>
        {classes.filter(c=>c.active&&(!year||c.year===year)).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
      </select></label>
    </div>
    <TableScroll label="Créneaux de l’emploi du temps">
      <table style={{width:"100%",borderCollapse:"collapse"}}>
        <thead><tr>{DAYS.map(d=><th key={d} style={{padding:8,textAlign:"left"}}>{d}</th>)}</tr></thead>
        <tbody><tr>{DAYS.map((_,i)=><td key={i} style={{verticalAlign:"top",padding:6,minWidth:145}}>
          {selected.filter(x=>x.weekday===i).sort((a,b)=>a.start_time.localeCompare(b.start_time)).map(x=>
            <div key={x.id} style={{border:"1px solid #bbb",borderRadius:7,padding:7,marginBottom:6}}>
              <strong>{x.start_time}–{x.end_time}</strong>
              <div>{subject(x.course)}</div>
              <small>{classes.find(c=>c.id===x.classroom)?.name||"Classe"} · {x.teacher}</small>
              <div><small>{rooms.find(r=>r.id===x.room)?.name||"Salle non attribuée"}</small></div>
              <button type="button" disabled={busy} onClick={()=>edit(x)}>Modifier</button>
            </div>)}
        </td>)}</tr></tbody>
      </table></TableScroll>
    <h3>{editing?"Déplacer une séance":"Programmer une séance"}</h3>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      if(editing){
        const current=entries.find(x=>x.id===editing);
        await api(base+"entries/"+editing,{revision:current.revision,instructor,slot,room:room||null,
          weekday:Number(weekday),effective_from:from,effective_to:to},"PATCH");
      }else{
        await api(base+"entries",{course,instructor,slot,room:room||null,
          weekday:Number(weekday),effective_from:from,effective_to:to});
      }
      reset();
    })}}>
      <div className="two">
        <label className="field">Cours<select value={course} required disabled={!!editing} onChange={e=>{setCourse(e.target.value);setInstructor("");}}>
          <option value="">Choisir…</option>
          {selectedCourses.map(c=><option key={c.id} value={c.id}>{subject(c.id)}</option>)}
        </select></label>
        <label className="field">Enseignant<select value={instructor} required onChange={e=>setInstructor(e.target.value)}>
          <option value="">Choisir…</option>
          {instructors.filter(i=>i.active).map(i=><option key={i.id} value={i.id}>{teacherName(i)}</option>)}
        </select></label>
        <label className="field">Jour<select value={weekday} onChange={e=>setWeekday(e.target.value)}>
          {DAYS.map((d,i)=><option key={d} value={i}>{d}</option>)}
        </select></label>
        <label className="field">Créneau<select value={slot} required onChange={e=>setSlot(e.target.value)}>
          <option value="">Choisir…</option>
          {slots.filter(s=>s.active&&s.year===year).map(s=><option key={s.id} value={s.id}>{s.label} {s.start_time}–{s.end_time}</option>)}
        </select></label>
        <label className="field">Salle<select value={room} onChange={e=>setRoom(e.target.value)}>
          <option value="">Sans salle</option>
          {rooms.filter(r=>r.active).map(r=><option key={r.id} value={r.id}>{r.name}</option>)}
        </select></label>
        <label className="field">Du<input required type="date" value={from} onChange={e=>setFrom(e.target.value)}/></label>
        <label className="field">Au<input required type="date" min={from||undefined} value={to} onChange={e=>setTo(e.target.value)}/></label>
      </div>
      <button disabled={busy||!course||!instructor||!slot||!from||!to} type="submit">{editing?"Enregistrer le déplacement":"Programmer"}</button>
      {editing&&<button type="button" disabled={busy} onClick={()=>run(async()=>{
        const x=entries.find(e=>e.id===editing);
        await api(base+"entries/"+editing,{revision:x.revision,active:false},"PATCH");
        reset();
      })}>Archiver la séance</button>}
      {editing&&<button type="button" onClick={reset}>Annuler</button>}
    </form>
    <h3>Salles</h3>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      await api(base+"rooms",{code:roomCode,name:roomName,capacity:roomCapacity?Number(roomCapacity):null});
      setRoomCode("");setRoomName("");setRoomCapacity("");
    })}}>
      <div className="two">
        <label className="field">Code<input required maxLength={48} pattern="[a-z0-9][a-z0-9_-]*" value={roomCode} onChange={e=>setRoomCode(e.target.value)}/></label>
        <label className="field">Nom<input required maxLength={120} value={roomName} onChange={e=>setRoomName(e.target.value)}/></label>
        <label className="field">Capacité<input type="number" min="1" max="100000" value={roomCapacity} onChange={e=>setRoomCapacity(e.target.value)}/></label>
      </div>
      <button disabled={busy} type="submit">Ajouter une salle</button>
    </form>
    <h3>Créneaux horaires</h3>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      await api(base+"slots",{year,code:slotCode,label:slotLabel,start_time:slotStart,end_time:slotEnd});
      setSlotCode("");setSlotLabel("");setSlotStart("");setSlotEnd("");
    })}}>
      <div className="two">
        <label className="field">Code<input required maxLength={48} pattern="[a-z0-9][a-z0-9_-]*" value={slotCode} onChange={e=>setSlotCode(e.target.value)}/></label>
        <label className="field">Nom<input required maxLength={120} value={slotLabel} onChange={e=>setSlotLabel(e.target.value)}/></label>
        <label className="field">Début<input required type="time" value={slotStart} onChange={e=>setSlotStart(e.target.value)}/></label>
        <label className="field">Fin<input required type="time" value={slotEnd} onChange={e=>setSlotEnd(e.target.value)}/></label>
      </div>
      <button disabled={busy||!year} type="submit">Ajouter un créneau</button>
    </form>
    {error&&<p role="status" aria-live="polite">{error}</p>}
  </section>;
}
