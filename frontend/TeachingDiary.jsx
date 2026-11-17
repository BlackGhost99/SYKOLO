import React, {useEffect, useRef, useState} from "react";
import {teacherRequest} from "./teacher-mobile-api.js";
import "./teaching-diary.css";

const today = () => {
  const d = new Date();
  return [d.getFullYear(), String(d.getMonth()+1).padStart(2,"0"), String(d.getDate()).padStart(2,"0")].join("-");
};
const blank = () => ({id:"", day:today(), title:"", lesson:"", homework:"", due_on:"", published:false});

export function ResourceLinks({resources=[],href}) {
  if(!resources.length)return null;
  return <div><strong>Documents pédagogiques</strong><ul>{resources.map(r=><li key={r.id}><a href={href(r)}>{r.filename}</a> · {Math.ceil(r.size/1024)} Ko</li>)}</ul></div>;
}
function ResourceUpload({entry,schoolId,onRefresh,api}) {
  const [file,setFile]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
  const input=useRef(null),key=useRef(null),running=useRef(false);
  const root="schools/"+schoolId+"/diary/entries/"+entry.id+"/resources";
  async function upload(e) {
    e.preventDefault();
    if(running.current||!file)return;
    running.current=true;setBusy(true);setMessage("");
    try {
      const csrfResponse=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
      if(!csrfResponse.ok)throw Error("Votre session a expiré.");
      const csrf=document.cookie.split("; ").find(v=>v.startsWith("csrftoken="))?.split("=")[1]||"";
      const form=new FormData();
      key.current ||= crypto.randomUUID();
      form.append("id",key.current);form.append("file",file);
      const r=await fetch("/api/v1/"+root,{method:"POST",credentials:"same-origin",headers:{"X-CSRFToken":csrf},body:form});
      const result=await r.json();
      if(!r.ok)throw Error(result.error||"Document refusé.");
      setFile(null);key.current=null;if(input.current)input.current.value="";
      onRefresh();
    }catch(e){setMessage(e.message);}
    finally{running.current=false;setBusy(false);}
  }
  async function revoke(r) {
    if(running.current)return;
    running.current=true;setBusy(true);setMessage("");
    try{await api(root+"/"+r.id,{},"PATCH");onRefresh();}
    catch(e){setMessage(e.message);}finally{running.current=false;setBusy(false);}
  }
  return <div className="yem-diary-resources">
    {(entry.resources||[]).map(r=><div key={r.id}><button type="button" className="yd-btn" disabled={busy} onClick={()=>revoke(r)}>Retirer {r.filename}</button></div>)}
    <form onSubmit={upload}><label className="field">Joindre un document texte UTF-8 (.txt, 1 Mio maximum)
      <input ref={input} type="file" accept=".txt,text/plain" disabled={busy} onChange={e=>{setFile(e.target.files?.[0]||null);key.current=null;setMessage("");}}/></label>
      <button type="submit" className="yd-btn" disabled={busy||!file||file.size>1048576}>Joindre le document</button>
    </form>{message&&<p role="alert">{message}</p>}
  </div>;
}

function Entries({entries, onEdit, resourceHref, schoolId, onRefresh, api}) {
  if (!entries.length) return <p>Aucune séance enregistrée.</p>;
  return <div className="yem-diary-list">{entries.map(e=><article key={e.id}>
    <div className="yem-diary-entry-head"><div><small>{e.day} · {e.classroom} · {e.subject}</small>
      <h3>{e.title}</h3></div>{onEdit&&<span>{e.published?"Publié":"Brouillon"}</span>}</div>
    <p className="yem-diary-text">{e.lesson}</p>
    {e.homework&&<div className="yem-diary-homework"><strong>Travail à faire{e.due_on?" pour le "+e.due_on:""}</strong><p className="yem-diary-text">{e.homework}</p></div>}
    {resourceHref&&<ResourceLinks resources={e.resources} href={r=>resourceHref(e,r)}/>}
    {onEdit&&<button className="yd-btn" type="button" onClick={()=>onEdit(e)}>Modifier la séance</button>}
    {onEdit&&schoolId&&<ResourceUpload entry={e} schoolId={schoolId} onRefresh={onRefresh} api={api}/>}
  </article>)}
  {entries.length>=200&&<p>Les 200 dernières séances sont affichées.</p>}</div>;
}

export default function TeachingDiary({schoolId, yearId="", api=teacherRequest}) {
  const root="schools/"+schoolId+"/diary/courses";
  const [courses,setCourses]=useState([]);
  const [course,setCourse]=useState("");
  const [entries,setEntries]=useState([]);
  const [writable,setWritable]=useState(false);
  const [form,setForm]=useState(blank);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [refresh,setRefresh]=useState(0);
  const running=useRef(false);
  const currentCourse=useRef(course);
  currentCourse.current=course;
  useEffect(()=>{
    let alive=true;
    setLoading(true);setError("");
    api(root+(yearId?"?year="+encodeURIComponent(yearId):"")).then(r=>{
      if(!alive)return;
      setCourses(r.courses||[]);setCourse((r.courses||[])[0]?.id||"");
      if(!r.courses?.length)setLoading(false);
    }).catch(e=>{if(alive){setError(e.message);setLoading(false);}});
    return()=>{alive=false;};
  },[root,yearId,api]);
  useEffect(()=>{
    let alive=true;
    setLoading(!!course);setEntries([]);setWritable(false);
    if(!course)return;
    api(root+"/"+course).then(r=>{if(alive){setEntries(r.entries||[]);setWritable(!!r.writable);}})
      .catch(e=>{if(alive)setError(e.message);}).finally(()=>{if(alive)setLoading(false);});
    return()=>{alive=false;};
  },[root,course,refresh,api]);
  function choose(id){setError("");setMessage("");setForm(blank());setCourse(id);}
  function change(key,value){setForm(old=>({...old,[key]:value}));}
  async function save(event,published){
    event.preventDefault();
    if(running.current||!course||!writable)return;
    const old=form, selected=course;
    const id=old.id||crypto.randomUUID();
    const payload={id,day:old.day,title:old.title,lesson:old.lesson,homework:old.homework,
      due_on:old.due_on||null,published};
    if(old.revision)payload.revision=old.revision;
    // Keep the same create-operation identifier after any ambiguous network failure.
    if(!old.id)setForm(f=>({...f,id}));
    running.current=true;setBusy(true);setError("");setMessage("");
    try {
      await api(root+"/"+selected,payload,old.revision?"PATCH":"POST");
      if(currentCourse.current===selected){setForm(blank());setMessage(published?"Séance publiée aux familles.":"Brouillon enregistré.");setRefresh(n=>n+1);}
    }catch(error){if(currentCourse.current===selected)setError(error.message);}
    finally{running.current=false;setBusy(false);}
  }
  const setEntry=e=>{setMessage("");setError("");setForm({...e,due_on:e.due_on||""});};
  return <section className="yem-diary" aria-label="Cahier de textes">
    <label className="field">Classe et matière<select value={course} disabled={busy||!courses.length}
      onChange={e=>choose(e.target.value)}><option value="">Choisir un cours</option>
      {courses.map(c=><option key={c.id} value={c.id}>{c.classroom} · {c.subject} · {c.year_name}</option>)}</select></label>
    {loading&&<p role="status">Chargement du cahier de textes…</p>}
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
    {!loading&&!courses.length&&<p>Aucun cours autorisé pour cette année.</p>}
    {!loading&&course&&!writable&&<p>Consultation seule : cours ou année non modifiable.</p>}
    {!loading&&writable&&<form className="yem-diary-form" onSubmit={e=>save(e,form.published)}>
      <h3>{form.revision?"Modifier la séance":"Nouvelle séance"}</h3>
      <label className="field">Date du cours<input required type="date" value={form.day} disabled={busy} onChange={e=>change("day",e.target.value)}/></label>
      <label className="field">Titre du cours<input required maxLength={180} value={form.title} disabled={busy} onChange={e=>change("title",e.target.value)}/></label>
      <label className="field">Contenu de la séance<textarea required rows={4} maxLength={4000} value={form.lesson} disabled={busy} onChange={e=>change("lesson",e.target.value)}/></label>
      <label className="field">Travail à faire (facultatif)<textarea rows={3} maxLength={4000} value={form.homework} disabled={busy} onChange={e=>{change("homework",e.target.value);if(!e.target.value.trim())change("due_on","");}}/></label>
      <label className="field">Échéance du devoir<input type="date" min={form.day} disabled={busy||!form.homework.trim()} value={form.due_on} onChange={e=>change("due_on",e.target.value)}/></label>
      <label><input type="checkbox" checked={form.published} disabled={busy} onChange={e=>change("published",e.target.checked)}/> Publier pour les familles de cette classe</label>
      <p>Ne saisissez aucune information personnelle sur un élève. Les brouillons ne sont jamais visibles par les familles.</p>
      <div className="actions"><button className="yd-btn primary" type="submit" disabled={busy}>{form.published?"Enregistrer et publier":"Enregistrer le brouillon"}</button>
      <button className="yd-btn" type="button" disabled={busy} onClick={()=>{setForm(blank());setError("");}}>Nouvelle saisie</button></div>
    </form>}
    {!loading&&course&&<Entries entries={entries} onEdit={writable&&!busy?setEntry:null} schoolId={schoolId} api={api} onRefresh={()=>setRefresh(n=>n+1)} resourceHref={(e,r)=>"/api/v1/schools/"+schoolId+"/diary/entries/"+e.id+"/resources/"+r.id}/>}
  </section>;
}

export function FamilyTeachingDiary({api=teacherRequest,childBase,year}) {
  const [entries,setEntries]=useState(null);
  const [error,setError]=useState("");
  useEffect(()=>{
    let alive=true;setEntries(null);setError("");
    if(!childBase||!year){setEntries([]);return;}
    api(childBase+"/diary?year="+encodeURIComponent(year)).then(r=>{if(alive)setEntries(r.entries||[]);})
      .catch(e=>{if(alive)setError(e.message);});
    return()=>{alive=false;};
  },[api,childBase,year]);
  if(error)return <p role="alert">{error}</p>;
  if(!entries)return <p role="status">Chargement des séances publiées…</p>;
  return <Entries entries={entries} resourceHref={(_e,r)=>"/api/v1/"+childBase+"/diary/resources/"+r.id+"?year="+encodeURIComponent(year)}/>;
}
