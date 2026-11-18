import {ContextTarget, ContextReadOnly} from "./ContextMenu.jsx";
import React, {useEffect, useRef, useState} from "react";
import {teacherRequest} from "./teacher-mobile-api.js";
import "./teaching-diary.css";
import CourseProgress from "./CourseProgress.jsx";
import SecondaryMastery from "./SecondaryMastery.jsx";

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

const formatDay=value=>value ? value.split("-").reverse().join("/") : "—";
const classKey=c=>JSON.stringify([c.year||c.year_name||"",c.classroom_id||c.classroom]);
const normalized=value=>String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("fr");
function Entries({entries, onEdit, onDuplicate, resourceHref, schoolId, onRefresh, api}) {
  if (!entries.length) return <p>Aucune séance enregistrée.</p>;
  return <div className="yem-diary-list">{entries.map(e=><ContextTarget as="article" key={e.id} showTrigger actions={onEdit?[{id:"edit",label:"Modifier la séance",write:true,run:()=>onEdit(e)},
      ...(onDuplicate?[{id:"copy",label:"Dupliquer en nouveau brouillon",write:true,run:()=>onDuplicate(e)}]:[])]:[]}>
    <div className="yem-diary-entry-head"><div><small>{formatDay(e.day)} · {e.classroom} · {e.subject}</small>
      <h3>{e.title}</h3></div>{typeof e.published==="boolean"&&<span className={"diary-status "+(e.published?"is-published":"is-draft")}>{e.published?"Publié":"Brouillon"}</span>}</div>
    <p className="yem-diary-text">{e.lesson}</p>
    {e.homework&&<div className="yem-diary-homework"><strong>Travail à faire{e.due_on?" pour le "+formatDay(e.due_on):""}</strong><p className="yem-diary-text">{e.homework}</p></div>}
    {resourceHref&&<ResourceLinks resources={e.resources} href={r=>resourceHref(e,r)}/>}
    {onEdit&&<button className="yd-btn" type="button" onClick={()=>onEdit(e)}>Modifier la séance</button>}
    {onEdit&&schoolId&&<ResourceUpload entry={e} schoolId={schoolId} onRefresh={onRefresh} api={api}/>}
  </ContextTarget>)}
  {entries.length>=200&&<p>Les 200 dernières séances sont affichées.</p>}</div>;
}

export default function TeachingDiary({schoolId, yearId="", api=teacherRequest, audience="school"}) {
  const root="schools/"+schoolId+"/diary/courses";
  const [courses,setCourses]=useState([]);
  const [course,setCourse]=useState("");
  const [showProgress,setShowProgress]=useState(false);
  const [showMastery,setShowMastery]=useState(false);
  const [entries,setEntries]=useState([]);
  const [query,setQuery]=useState("");
  const [status,setStatus]=useState("all");
  const [historyDay,setHistoryDay]=useState("");
  const formRef=useRef(null);
  const [courseWritable,setWritable]=useState(false);
  const readOnly=React.useContext(ContextReadOnly);
  const writable=courseWritable&&!readOnly;
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
  function choose(id){if(id===course)return;setQuery("");setStatus("all");setHistoryDay("");setShowMastery(false);setShowProgress(false);setError("");setMessage("");setForm(blank());setCourse(id);}
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
  const setEntry=e=>{setMessage("");setError("");setForm({...e,due_on:e.due_on||""});formRef.current?.scrollIntoView?.({block:"start",behavior:"smooth"});};
  const duplicateEntry=e=>{
    if((form.id||form.title||form.lesson||form.homework)&&!window.confirm("Remplacer la saisie en cours par une nouvelle copie non publiée ?"))return;
    setError("");setMessage("Nouvelle copie préparée. Vérifiez la date et les devoirs avant l’enregistrement. Les pièces jointes ne sont pas recopiées.");
    setForm({...blank(),title:e.title,lesson:e.lesson,homework:e.homework||""});
    formRef.current?.scrollIntoView?.({block:"start",behavior:"smooth"});
  };
  const selected=courses.find(c=>c.id===course);
  const classes=[...new Map(courses.map(c=>[classKey(c),c])).values()];
  const classCourses=selected?courses.filter(c=>classKey(c)===classKey(selected)):[];
  const shown=entries.filter(e=>(status==="all"||(status==="published"?e.published:!e.published))&&(!historyDay||e.day===historyDay)&&(!query.trim()||normalized([e.title,e.lesson,e.homework].join(" ")).includes(normalized(query.trim()))));
  const teacher=audience==="teacher";
  const diaryVisible=!showMastery&&!showProgress;
  return <section className={"yem-diary"+(teacher?" diary-teacher":"")} aria-label="Cahier de textes">
    <div className="diary-overview">
      <div className="diary-context-head"><div><span className="diary-eyebrow">{teacher?"MES COURS":"ESPACE PÉDAGOGIQUE"}</span><h2>{selected?selected.classroom+" · "+selected.subject:"Sélectionner un cours"}</h2><p>{selected?.year_name||"Année scolaire"}{teacher?" · Votre cahier de textes":""}</p></div><div className="diary-summary"><strong>{entries.length}</strong><span>Séances</span><strong>{entries.filter(e=>e.published).length}</strong><span>Publiées</span></div></div>
      <div className="diary-context-grid">
        {diaryVisible&&<label className="field">Date du cours<input form="yem-active-diary-form" required={writable} type="date" value={form.day} disabled={busy||!writable||loading} onChange={e=>change("day",e.target.value)}/></label>}
        <label className="field">Classe<select value={selected?classKey(selected):""} disabled={busy||!courses.length} onChange={e=>choose(courses.find(c=>classKey(c)===e.target.value)?.id||"")}><option value="" disabled>Choisir une classe</option>{classes.map(c=><option key={classKey(c)} value={classKey(c)}>{c.classroom}{!yearId&&c.year_name?" · "+c.year_name:""}</option>)}</select></label>
        <label className="field">Matière<select value={course} disabled={busy||!classCourses.length} onChange={e=>choose(e.target.value)}><option value="" disabled>Choisir une matière</option>{classCourses.map(c=><option key={c.id} value={c.id}>{c.subject}</option>)}</select></label>
      </div>
    </div>
    {loading&&<p role="status">Chargement du cahier de textes…</p>}
    {error&&<p role="alert" className="diary-feedback diary-error">{error}</p>}{message&&<p role="status" className="diary-feedback">{message}</p>}
    {!loading&&!courses.length&&<p>Aucun cours autorisé pour cette année.</p>}
    {!loading&&course&&<nav className="diary-tabs" aria-label="Outils pédagogiques"><button className="yd-btn" type="button" aria-pressed={diaryVisible} onClick={()=>{setShowProgress(false);setShowMastery(false);}}>Séances et devoirs</button><button className="yd-btn" type="button" aria-pressed={showProgress} onClick={()=>{setShowMastery(false);setShowProgress(v=>!v);}}>Suivre la progression du programme</button>{selected?.secondary&&<button className="yd-btn" type="button" aria-pressed={showMastery} onClick={()=>{setShowProgress(false);setShowMastery(v=>!v);}}>Compétences et remédiation</button>}</nav>}
    {!loading&&course&&showMastery&&<SecondaryMastery key={course} schoolId={schoolId} course={course} api={api}/>}
    {!loading&&course&&showProgress&&<CourseProgress key={course} schoolId={schoolId} course={course} entries={entries} api={api}/>}
    {diaryVisible&&!loading&&course&&!writable&&<p>Consultation seule : cours ou année non modifiable.</p>}
    {diaryVisible&&!loading&&course&&<div className="diary-workspace">
    {writable&&<form ref={formRef} id="yem-active-diary-form" className="yem-diary-form" onSubmit={e=>save(e,form.published)}>
      <div className="diary-section-heading"><span className="diary-eyebrow">01 · SÉANCE</span><h3>{form.revision?"Modifier la séance":"Nouvelle séance"}</h3><p>{formatDay(form.day)} · {selected?.classroom} · {selected?.subject}</p></div>
      <label className="field">Titre du cours<input required maxLength={180} placeholder="Ex. Introduction aux fractions" value={form.title} disabled={busy} onChange={e=>change("title",e.target.value)}/></label>
      <label className="field">Contenu de la séance<textarea required rows={5} maxLength={4000} placeholder="Notions abordées, activités, exercices réalisés…" value={form.lesson} disabled={busy} onChange={e=>change("lesson",e.target.value)}/></label>
      <div className="diary-homework-form"><div className="diary-section-heading"><span className="diary-eyebrow">02 · DEVOIRS</span><h3>Travail à faire</h3></div>
      <label className="field">Travail à faire (facultatif)<textarea rows={3} maxLength={4000} placeholder="Exercices, leçon à réviser…" value={form.homework} disabled={busy} onChange={e=>{change("homework",e.target.value);if(!e.target.value.trim())change("due_on","");}}/></label>
      <label className="field">Échéance du devoir<input type="date" min={form.day} disabled={busy||!form.homework.trim()} value={form.due_on} onChange={e=>change("due_on",e.target.value)}/></label></div>
      <div className="diary-publication"><span className="diary-eyebrow">03 · PUBLICATION</span><label><input type="checkbox" checked={form.published} disabled={busy} onChange={e=>change("published",e.target.checked)}/> Publier pour les familles de cette classe</label>
      <p>Les brouillons restent privés. N’indiquez aucune information personnelle sur un élève.</p></div>
      <div className="actions diary-actions"><button className="yd-btn" type="button" disabled={busy} onClick={()=>{setForm(blank());setError("");}}>Nouvelle saisie</button><button className="yd-btn primary" type="submit" disabled={busy}>{busy?"Enregistrement…":form.published?"Enregistrer et publier":"Enregistrer le brouillon"}</button></div>
    </form>}
    <section className="diary-history" aria-label="Historique des séances">
      <div className="diary-section-heading"><span className="diary-eyebrow">JOURNAL DE CLASSE</span><h3>{teacher?"Mes séances":"Historique des séances"}</h3><p>{entries.length} séance{entries.length!==1?"s":""} pour ce cours{entries.length>=200?" (200 dernières)":" "}</p></div>
      <div className="diary-history-filters">
        <label className="field">Rechercher une séance<input type="search" placeholder="Titre, contenu, devoir…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
        <label className="field">Statut<select value={status} onChange={e=>setStatus(e.target.value)}><option value="all">Tous les statuts</option><option value="published">Publié</option><option value="draft">Brouillon</option></select></label>
        <label className="field">Date de séance<input type="date" value={historyDay} onChange={e=>setHistoryDay(e.target.value)}/></label>
      </div>
      {shown.length!==entries.length&&<p role="status">{shown.length} résultat{shown.length!==1?"s":""}</p>}
      {entries.length>0&&!shown.length?<p className="diary-empty">Aucune séance ne correspond aux filtres. <button type="button" className="yd-btn" onClick={()=>{setQuery("");setStatus("all");setHistoryDay("");}}>Réinitialiser</button></p>:<Entries entries={shown} onEdit={writable&&!busy?setEntry:null} onDuplicate={writable&&!busy?duplicateEntry:null} schoolId={schoolId} api={api} onRefresh={()=>setRefresh(n=>n+1)} resourceHref={(e,r)=>"/api/v1/schools/"+schoolId+"/diary/entries/"+e.id+"/resources/"+r.id}/>}
    </section></div>}
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
