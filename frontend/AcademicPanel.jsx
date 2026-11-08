import React, { useEffect, useState } from "react";
import AnnualWorkspace from "./AnnualWorkspace.jsx";

const TYPES = [
  {key:"years",label:"Années scolaires",fields:["start_date","end_date"]},
  {key:"cycles",label:"Cycles",fields:["order"]},
  {key:"levels",label:"Niveaux",fields:["cycle","order"]},
  {key:"tracks",label:"Filières",fields:["level","order"]},
  {key:"classes",label:"Classes",fields:["year","level","track","capacity"]},
  {key:"periods",label:"Périodes",fields:["year","start_date","end_date","order"]},
];
const LABELS = {year:"Année",cycle:"Cycle",level:"Niveau",track:"Filière facultative",capacity:"Capacité facultative",start_date:"Début",end_date:"Fin",order:"Ordre"};
const PARENT = {year:"years",cycle:"cycles",level:"levels",track:"tracks"};
const init = () => ({code:"",name:"",year:"",cycle:"",level:"",track:"",order:0,capacity:"",start_date:"",end_date:""});

async function request(path, body, method) {
  if (body !== undefined) await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
  const csrf = document.cookie.split("; ").find(x => x.startsWith("csrftoken="))?.split("=")[1] || "";
  const response = await fetch("/api/v1/" + path, {
    method: method || (body === undefined ? "GET" : "POST"),
    credentials:"same-origin",
    headers:body === undefined ? {} : {"Content-Type":"application/json","X-CSRFToken":csrf},
    body:body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) throw Error("Service académique indisponible.");
  const value = await response.json();
  if (!response.ok) throw Error(value.error || "Permission insuffisante.");
  return value;
}

export default function AcademicPanel({schoolId}) {
  const [resource,setResource] = useState("years");
  const [yearId,setYearId] = useState("");
  const [all,setAll] = useState({});
  const [form,setForm] = useState(init);
  const [busy,setBusy] = useState(false);
  const [allowed,setAllowed] = useState(true);
  const [message,setMessage] = useState("");
  const prefix = "schools/" + schoolId + "/academic/";

  async function refresh() {
    const results = await Promise.all(TYPES.map(async item => {
      try {return [item.key, (await request(prefix + item.key))[item.key] || []];}
      catch (e) {if (e.message === "Permission insuffisante.") throw e; return [item.key, []];}
    }));
    setAll(Object.fromEntries(results));
    setAllowed(true);
  }
  useEffect(() => {
    let active = true;
    setAll({}); setYearId(""); setForm(init()); setAllowed(true); setMessage("");
    Promise.all(TYPES.map(async item => {
      const result = await request("schools/" + schoolId + "/academic/" + item.key);
      return [item.key, result[item.key] || []];
    })).then(results => {if (active) setAll(Object.fromEntries(results));}).catch(err => {
      if (active) {setAllowed(false); setMessage("Gestion académique non accessible : " + err.message);}
    });
    return () => {active = false;};
  }, [schoolId]);

  const type = TYPES.find(t => t.key === resource);
  useEffect(()=>{
    if(resource==="classes"||resource==="periods")setForm(old=>({...old,year:yearId}));
  },[resource,yearId]);
  const visibleRows=(all[resource]||[]).filter(row=>(
    (resource==="classes"||resource==="periods")&&yearId?row.year===yearId:true
  ));
  function update(name,value) {setForm(previous => ({...previous,[name]:value}));}
  async function submit(event) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const data = {code:form.code.trim(),name:form.name.trim()};
      for (const field of type.fields) {
        if (field === "order") data.order = Number(form.order);
        else if (field === "capacity") data.capacity = form.capacity === "" ? null : Number(form.capacity);
        else if (field === "track") data.track = form.track || null;
        else data[field] = form[field];
      }
      await request(prefix + resource, data);
      setForm({...init(),year:yearId}); await refresh();
      setMessage("Enregistrement réussi.");
    } catch (e) {setMessage(e.message);} finally {setBusy(false);}
  }
  async function setActive(item) {
    setBusy(true); setMessage("");
    try {
      await request(prefix + resource + "/" + item.id, {revision:item.revision,active:!item.active},"PATCH");
      await refresh(); setMessage(item.active ? "Élément archivé." : "Élément réactivé.");
    } catch (e) {setMessage(e.message);} finally {setBusy(false);}
  }
  function fieldControl(field) {
    if (PARENT[field]) {
      const options = all[PARENT[field]] || [];
      return <select value={form[field]} required={field !== "track"} onChange={e => update(field,e.target.value)}>
        <option value="">Sélectionner…</option>
        {options.filter(p => p.active).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>;
    }
    if (field === "start_date" || field === "end_date")
      return <input type="date" required value={form[field]} onChange={e=>update(field,e.target.value)} />;
    return <input type="number" min={field==="capacity"?1:0} max={field==="capacity"?5000:1000}
      value={form[field]} onChange={e=>update(field,e.target.value)} placeholder={field==="capacity"?"Sans limite définie":""} />;
  }
  return (
    <section className="card" aria-label="Structure académique" style={{marginTop:"1rem"}}>
      <h2>Structure académique</h2>
      <p className="hint">Années, cycles, niveaux, filières, classes et périodes. Aucun calendrier scolaire n’est imposé.</p>
      {!allowed ? <p role="status">{message}</p> : <>
        <label className="field">Élément à gérer
          <select value={resource} onChange={e=>{setResource(e.target.value);setForm({...init(),year:yearId});setMessage("");}}>
            {TYPES.map(t=><option key={t.key} value={t.key}>{t.label}</option>)}
          </select>
        </label>
        {resource==="years"
          ? <AnnualWorkspace schoolId={schoolId} yearId={yearId} onYearChange={setYearId} onPrepared={refresh}/>
          : <>
            {(resource==="classes"||resource==="periods")&&yearId&&<p className="hint">Année scolaire sélectionnée : {(all.years||[]).find(y=>y.id===yearId)?.name}. Les opérations ci-dessous concernent uniquement cette année.</p>}
            <form onSubmit={submit}>
          <div className="two">
            <label className="field">Code
              <input required maxLength={40} pattern="[a-z0-9][a-z0-9_-]*" value={form.code} onChange={e=>update("code",e.target.value)} placeholder="ex : 2026-2027" />
            </label>
            <label className="field">Intitulé
              <input required maxLength={120} value={form.name} onChange={e=>update("name",e.target.value)} placeholder="Nom libre" />
            </label>
            {type.fields.map(field=><label className="field" key={field}>{LABELS[field]}{fieldControl(field)}</label>)}
          </div>
          <button type="submit" disabled={busy}>Ajouter : {type.label.toLowerCase()}</button>
            </form>
          </>}
        <h3>{type.label} déjà créés ({visibleRows.length})</h3>
        {visibleRows.length===0 ? <p className="hint">Aucun élément enregistré pour cette sélection.</p>
          : <ul>{visibleRows.map(row=><li key={row.id} style={{marginBottom:"0.8rem"}}>
            <strong>{row.name}</strong> <small>({row.code}) {row.active ? "" : "· Archivé"}</small>
            <button type="button" style={{marginLeft:"0.8rem"}} disabled={busy}
              onClick={()=>setActive(row)}>{row.active?"Archiver":"Réactiver"}</button>
          </li>)}</ul>}
        <p className="hint">L’archivage conserve l’historique. Les corrections détaillées peuvent être effectuées via l’API sécurisée et les révisions.</p>
        {message && <p role="status" aria-live="polite">{message}</p>}
      </>}
    </section>
  );
}
