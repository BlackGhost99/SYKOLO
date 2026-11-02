import React, {useEffect, useState} from "react";

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

export default function AttendancePanel({schoolId}) {
  const root = "schools/" + schoolId + "/";
  const base = root + "attendance/";
  const [classes,setClasses]=useState([]);
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
    request(root+"academic/classes").then(v=>{if(active)setClasses(v.classes||[])})
      .catch(()=>{if(active)setClasses([])});
    return()=>{active=false;};
  },[schoolId]);

  useEffect(()=>{
    let active=true;
    setSessions([]);setSelectedSession("");setStatuses([]);setDrafts({});setPolicyMessage("");setSummary(null);setHistory(null);
    if (!selectedClass) return()=>{active=false};
    Promise.all([
      request(base+"options?classroom="+encodeURIComponent(selectedClass)),
      request(base+"sessions?classroom="+encodeURIComponent(selectedClass)),
    ]).then(([opts,s])=>{
      if (!active)return;
      setStatuses(opts.statuses||[]);setSessions(s.sessions||[]);
    }).catch(e=>{if(active)setPolicyMessage(e.message)});
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
  const chosenClass=classes.find(x=>x.id===selectedClass);
  const roster=sessionData?.roster||[];
  const recorded=roster.filter(x=>x.mark).length;
  const prepared=roster.filter(x=>{
    const d=drafts[x.enrollment];
    if(!d?.status)return false;
    const m=x.mark;
    return !m || d.status!==m.status || d.note!==m.note || d.justification!==m.justification || d.justified!==m.justified;
  });
  return <section className="card" style={{marginTop:"1rem"}} aria-label="Appels et assiduité">
    <h2>Appels et assiduité</h2>
    <p className="hint">Une séance par classe, date et créneau. Aucune présence présumée : les élèves non renseignés restent sans statut.</p>
    <label className="field">Classe
      <select value={selectedClass} onChange={e=>setSelectedClass(e.target.value)}>
        <option value="">Choisir une classe...</option>
        {classes.filter(x=>x.active).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
    </label>
    {policyMessage&&<p role="status">{policyMessage} Ajoutez par exemple dans les paramètres de l'école :
      <code>{'{"attendance":{"statuses":[{"code":"p","label":"Présent","group":"present"},{"code":"a","label":"Absent","group":"absent"},{"code":"r","label":"Retard","group":"late"}]}}'}</code>
    </p>}
    {selectedClass&&statuses.length>0&&<>
      <h3>Créer une séance</h3>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        const result=await request(base+"sessions",{
          classroom:selectedClass,date,slot,label,
        });
        await reloadSessions();setSelectedSession(result.id);setMessage("Nouvel appel créé.");
      })}}>
        <div className="two">
          <label className="field">Date
            <input type="date" min={chosenClass?undefined:undefined} required value={date} onChange={e=>setDate(e.target.value)} />
          </label>
          <label className="field">Code du créneau
            <input required maxLength={48} pattern="[a-z0-9][a-z0-9_-]*" value={slot} onChange={e=>setSlot(e.target.value)} placeholder="matin, cours1..." />
          </label>
          <label className="field">Intitulé
            <input required maxLength={120} value={label} onChange={e=>setLabel(e.target.value)} placeholder="Appel du matin" />
          </label>
        </div>
        <button disabled={busy} type="submit">Créer la séance</button>
      </form>
      <label className="field">Séances enregistrées
        <select value={selectedSession} onChange={e=>setSelectedSession(e.target.value)}>
          <option value="">Choisir une séance...</option>
          {sessions.map(s=><option key={s.id} value={s.id}>{s.date} · {s.label} {s.closed_at?"· Clôturée":""}</option>)}
        </select>
      </label>
    </>}
    {sessionData&&<>
      <h3>Feuille d'appel du {sessionData.date} — {sessionData.label}</h3>
      <p>{recorded}/{roster.length} élèves renseignés. {sessionData.closed_at?"Séance clôturée.":"Modifications encore possibles."}</p>
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
        {roster.map(e=>{
          const d=drafts[e.enrollment]||{};
          return <div key={e.enrollment} style={{padding:"0.6rem 0",borderBottom:"1px solid var(--border,#ddd)"}}>
            <strong>{e.last_name} {e.first_name}</strong> <small>({e.student_code})</small>
            <div className="two">
              <label className="field">Statut
                <select disabled={!!sessionData.closed_at} value={d.status||""} onChange={ev=>edit(e.enrollment,"status",ev.target.value)}>
                  <option value="">Non renseigné</option>
                  {statuses.map(s=><option key={s.code} value={s.code}>{s.label}</option>)}
                </select>
              </label>
              <label className="field">Observation
                <input disabled={!!sessionData.closed_at} maxLength={500} value={d.note||""} onChange={ev=>edit(e.enrollment,"note",ev.target.value)} />
              </label>
              <label className="field">Justification déposée (texte administratif)
                <input disabled={!!sessionData.closed_at} maxLength={500} value={d.justification||""} onChange={ev=>edit(e.enrollment,"justification",ev.target.value)} />
              </label>
              <label className="field">Justification vérifiée
                <input type="checkbox" disabled={!!sessionData.closed_at} checked={!!d.justified}
                  onChange={ev=>edit(e.enrollment,"justified",ev.target.checked)} />
              </label>
            </div>
            {e.mark&&<button type="button" disabled={busy} onClick={()=>run(async()=>{
              const h=await request(base+"sessions/"+selectedSession+"/marks/"+e.enrollment+"/history");
              setHistory({name:e.first_name+" "+e.last_name,items:h.history||[]});
            })}>Voir l'historique</button>}
          </div>;
        })}
        {!sessionData.closed_at&&<>
          <label className="field">Motif obligatoire des corrections (si statut déjà enregistré)
            <textarea maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Pourquoi cette correction ?" />
          </label>
          <button disabled={busy||prepared.length===0||prepared.length>100} type="submit">Enregistrer {prepared.length} modification(s)</button>
        </>}
      </form>
      {!sessionData.closed_at&&<button type="button" disabled={busy||roster.length===0||recorded!==roster.length} onClick={()=>run(async()=>{
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
    {selectedClass&&statuses.length>0&&<>
      <h3>Statistiques d'assiduité</h3>
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
        Séances : {summary.sessions} · Marques renseignées : {summary.recorded} ·
        Présences : {summary.groups.present} · Absences : {summary.groups.absent} ·
        Retards : {summary.groups.late} · Autres : {summary.groups.other}
      </p>}
    </>}
    {message&&<p role="status" aria-live="polite">{message}</p>}
  </section>;
}
