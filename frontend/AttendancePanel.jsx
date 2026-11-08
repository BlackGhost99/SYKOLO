import React, {useEffect, useState} from "react";
import {ClassField} from "./SchoolSettings.jsx";

async function request(path, data) {
  if (data !== undefined) await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
  const csrf = document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1] || "";
  const r = await fetch("/api/v1/" + path, {
    method: data === undefined ? "GET" : "POST",
    credentials:"same-origin",
    headers:data === undefined ? {} : {"Content-Type":"application/json","X-CSRFToken":csrf},
    body:data === undefined ? undefined : JSON.stringify(data),
  });
  if (!r.headers.get("content-type")?.includes("application/json")) throw Error("Service indisponible.");
  const v = await r.json();
  if (!r.ok) throw Error(v.error || "Opération refusée.");
  return v;
}

export default function AttendancePanel({schoolId, onSettings, attendanceAssignedOnly = false,
  attendanceCanWrite = true, attendanceCanFinalize = true}) {
  const root = "schools/" + schoolId + "/";
  const base = root + "attendance/";
  const [classes,setClasses]=useState([]);
  const [years,setYears]=useState([]);
  const [markFilter,setMarkFilter]=useState("all");
  const [selectedClass,setSelectedClass]=useState("");
  const [sessions,setSessions]=useState([]);
  const [selectedSession,setSelectedSession]=useState("");
  const [sessionData,setSessionData]=useState(null);
  const [statuses,setStatuses]=useState([]);
  const [date,setDate]=useState("");
  const [slot,setSlot]=useState("");
  const [label,setLabel]=useState("");
  const [drafts,setDrafts]=useState({});
  const [reason,setReason]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [policyMessage,setPolicyMessage]=useState("");
  const [summary,setSummary]=useState(null);
  const [history,setHistory]=useState(null);
  const [dateFrom,setDateFrom]=useState("");
  const [dateTo,setDateTo]=useState("");

  useEffect(()=>{
    let active=true;
    Promise.all([
      request(root+"academic/classes"),
      request(root+"academic/years"),
      attendanceAssignedOnly ? request(root+"staff/me/assignments") : null,
    ]).then(([c,y,assigned])=>{
      if(!active)return;
      const ids=new Set(assigned?.assignments.map(item=>item.classroom));
      setClasses((c.classes||[]).filter(room=>!attendanceAssignedOnly||ids.has(room.id)));
      setYears(y.years||[]);
    }).catch(error=>{if(active)setMessage(error.message);});
    return()=>{active=false;};
  },[schoolId,attendanceAssignedOnly]);

  useEffect(()=>{
    let active=true;
    setSessions([]);setSelectedSession("");setStatuses([]);setDrafts({});setPolicyMessage("");setSummary(null);setHistory(null);
    if (!selectedClass) return()=>{active=false};
    request(base+"options?classroom="+encodeURIComponent(selectedClass))
      .then(opts=>{if(active)setStatuses(opts.statuses||[]);})
      .catch(()=>{if(active)setPolicyMessage("Les statuts de présence sont indisponibles pour cette classe.");});
    request(base+"sessions?classroom="+encodeURIComponent(selectedClass))
      .then(result=>{if(active)setSessions(result.sessions||[]);})
      .catch(error=>{if(active)setMessage(error.message);});
    return()=>{active=false};
  },[schoolId,selectedClass]);

  useEffect(()=>{
    let active=true;
    setSessionData(null);setDrafts({});setHistory(null);
    if(!selectedSession)return()=>{active=false};
    request(base+"sessions/"+selectedSession).then(v=>{
      if(!active)return;
      setSessionData(v);
      setDrafts(Object.fromEntries(v.roster.map(e=>[e.enrollment, {
        status:e.mark?.status||"", note:e.mark?.note||"",
        justification:e.mark?.justification||"", justified:e.mark?.justified||false,
        revision:e.mark?.revision||0,
      }])));
    }).catch(e=>{if(active)setMessage(e.message)});
    return()=>{active=false};
  },[schoolId,selectedSession]);

  async function run(fn) {
    setBusy(true);setMessage("");
    try {await fn();}
    catch(e){setMessage(e.message)}
    finally {setBusy(false)}
  }
  async function reloadSessions() {
    const result=await request(base+"sessions?classroom="+encodeURIComponent(selectedClass));
    setSessions(result.sessions||[]);
  }
  async function reloadSession() {
    const result=await request(base+"sessions/"+selectedSession);
    setSessionData(result);
    setDrafts(Object.fromEntries(result.roster.map(e=>[e.enrollment, {
      status:e.mark?.status||"", note:e.mark?.note||"",
      justification:e.mark?.justification||"", justified:e.mark?.justified||false,
      revision:e.mark?.revision||0,
    }])));
  }
  function edit(enrollment,key,value) {
    setDrafts(prev=>({...prev,[enrollment]:{...prev[enrollment],[key]:value}}));
  }

  const roster=sessionData?.roster||[];
  const recorded=roster.filter(x=>x.mark).length;
  const prepared=roster.filter(x=>{
    const d=drafts[x.enrollment];
    if(!d?.status || (attendanceAssignedOnly && x.mark?.justified))return false;
    const m=x.mark;
    return !m || d.status!==m.status || d.note!==m.note || d.justification!==m.justification || d.justified!==m.justified;
  });
  return <section className="card" style={{marginTop:"1rem"}} aria-label="Appels et assiduité">
    <h2>Absences, retards et appels</h2>
    <ClassField classes={classes} years={years} value={selectedClass} disabled={busy} onChange={value=>{
      setSelectedClass(value);setMessage("");setMarkFilter("all");setDate("");setDateFrom("");setDateTo("");
    }}/>
    {policyMessage&&<p role="status">{policyMessage} {onSettings&&<button type="button" onClick={onSettings}>Configurer les statuts</button>}</p>}
    {selectedClass&&<>
      <label className="field">Appels enregistrés
        <select value={selectedSession} disabled={busy} onChange={e=>{setSelectedSession(e.target.value);setMarkFilter("all");}}>
          <option value="">Choisir un appel…</option>
          {sessions.map(s=><option key={s.id} value={s.id}>{s.date} · {s.label} {s.closed_at?"· Clôturé":""}</option>)}
        </select>
      </label>
      {!sessions.length && <p>Aucun appel enregistré pour cette classe.</p>}
      {attendanceCanWrite && statuses.length>0 && <details><summary>Faire un nouvel appel</summary>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        const result=await request(base+"sessions",{
          classroom:selectedClass,date,slot:slot.replace(":", "-"),label:label.trim() ? slot+" · "+label.trim() : slot,
        });
        await reloadSessions();setSelectedSession(result.id);setMessage("Nouvel appel créé.");
      })}}>
        <div className="two">
          <label className="field">Date
            <input type="date" required value={date} onChange={e=>setDate(e.target.value)} />
          </label>
          <label className="field">Heure de l’appel
            <input required type="time" value={slot} onChange={e=>setSlot(e.target.value)} />
          </label>
          <label className="field">Intitulé (facultatif)
            <input maxLength={110} value={label} onChange={e=>setLabel(e.target.value)} placeholder="Appel du matin" />
          </label>
        </div>
        <button disabled={busy} type="submit">Créer la séance</button>
      </form></details>}
    </>}
    {sessionData&&<>
      <h3>Feuille d'appel du {sessionData.date} — {sessionData.label}</h3>
      <p>{recorded}/{roster.length} élèves renseignés. {sessionData.closed_at?"Séance clôturée.":"Modifications encore possibles."}</p>
      <label className="field">Afficher
        <select value={markFilter} onChange={e=>setMarkFilter(e.target.value)}>
          <option value="all">Tous les élèves</option><option value="absent">Absents</option><option value="late">En retard</option>
        </select>
      </label>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        const marks=prepared.map(e=>({
          enrollment:e.enrollment,...drafts[e.enrollment],
          reason:e.mark?reason:"",
        }));
        if(!marks.length)throw Error("Aucune modification à enregistrer.");
        const result=await request(base+"sessions/"+selectedSession+"/marks",{marks});
        await reloadSession();await reloadSessions();setReason("");
        setMessage(result.marks.length+" saisie(s) enregistrée(s).");
      })}}>
        {roster.filter(e=>markFilter==="all" || e.mark?.group===markFilter).map(e=>{
          const d=drafts[e.enrollment]||{};
          const readOnly=!attendanceCanWrite||sessionData.closed_at||(attendanceAssignedOnly&&e.mark?.justified);
          return <div key={e.enrollment} style={{padding:"0.6rem 0",borderBottom:"1px solid var(--border,#ddd)"}}>
            <strong>{e.last_name} {e.first_name}</strong> <small>({e.student_code})</small>
            {e.mark && <p>{e.mark.label}{e.mark.justified?" · Justifié":""}</p>}
            {!readOnly&&statuses.length>0&&<div className="two">
              <label className="field">Présence
                <select value={d.status||""} onChange={ev=>edit(e.enrollment,"status",ev.target.value)}>
                  <option value="">Non renseigné</option>
                  {statuses.map(s=><option key={s.code} value={s.code}>{s.label}</option>)}
                </select>
              </label>
              <details><summary>Ajouter une observation ou un justificatif</summary>
              <label className="field">Observation
                <input maxLength={500} value={d.note||""} onChange={ev=>edit(e.enrollment,"note",ev.target.value)} />
              </label>
              <label className="field">Justificatif
                <input maxLength={500} value={d.justification||""} onChange={ev=>edit(e.enrollment,"justification",ev.target.value)} />
              </label>
              {!attendanceAssignedOnly && <label className="field">Justification vérifiée
                <input type="checkbox" checked={!!d.justified}
                  onChange={ev=>edit(e.enrollment,"justified",ev.target.checked)} />
              </label>}
              </details>
            </div>}
            {e.mark&&<button type="button" disabled={busy} onClick={()=>run(async()=>{
              const h=await request(base+"sessions/"+selectedSession+"/marks/"+e.enrollment+"/history");
              setHistory({name:e.first_name+" "+e.last_name,items:h.history||[]});
            })}>Voir l'historique</button>}
          </div>;
        })}
        {attendanceCanWrite&&!sessionData.closed_at&&statuses.length>0&&<>
          {prepared.some(row=>row.mark) && <label className="field">Motif de la correction
            <textarea maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Pourquoi cette correction ?" required />
          </label>}
          <button disabled={busy||prepared.length===0||prepared.length>100} type="submit">Enregistrer {prepared.length} modification(s)</button>
        </>}
      </form>
      {attendanceCanFinalize&&!sessionData.closed_at&&<button type="button" disabled={busy||roster.length===0||recorded!==roster.length} onClick={()=>run(async()=>{
        await request(base+"sessions/"+selectedSession+"/close",{revision:sessionData.revision});
        await reloadSession();await reloadSessions();setMessage("Appel clôturé.");
      })}>Clôturer l'appel (direction)</button>}
    </>}
    {history&&<div>
      <h3>Historique : {history.name}</h3>
      {history.items.map(h=><p key={h.revision}>
        Révision {h.revision} · {h.after.label} {h.after.justified?"· Justifié":""} · {h.reason||"Première saisie"} · {new Date(h.created_at).toLocaleString("fr-FR")}
      </p>)}
    </div>}
    {selectedClass&&<details>
      <summary>Bilan des absences et retards sur une période</summary>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        setSummary(await request(base+"summary?classroom="+selectedClass+"&from="+dateFrom+"&to="+dateTo));
      })}}>
        <div className="two">
          <label className="field">Du
            <input required type="date" value={dateFrom} onChange={e=>setDateFrom(e.target.value)} />
          </label>
          <label className="field">Au
            <input required type="date" value={dateTo} onChange={e=>setDateTo(e.target.value)} />
          </label>
        </div>
        <button type="submit" disabled={busy}>Calculer la synthèse</button>
      </form>
      {summary&&<p>
        Appels : {summary.sessions} ·
        Présences : {summary.groups.present} · Absences : {summary.groups.absent} ·
        Retards : {summary.groups.late} · Autres : {summary.groups.other}
      </p>}
    </details>}
    {message&&<p role="status" aria-live="polite">{message}</p>}
  </section>;
}
