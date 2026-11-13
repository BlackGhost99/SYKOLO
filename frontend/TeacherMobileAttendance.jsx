import React,{useEffect,useMemo,useState} from "react";
import {Button,Card} from "./yem-ui.jsx";
import {teacherRequest} from "./teacher-mobile-api.js";

const readState=item=>({
  status:item.mark?.status||"",note:item.mark?.note||"",
  justification:item.mark?.justification||"",
  justified:item.mark?.justified||false,
  revision:item.mark?.revision||0,
});
function nowLocal(){
  const t=new Date();
  const date=[t.getFullYear(),String(t.getMonth()+1).padStart(2,"0"),String(t.getDate()).padStart(2,"0")].join("-");
  const hour=[String(t.getHours()).padStart(2,"0"),String(t.getMinutes()).padStart(2,"0")].join(":");
  return {date,hour};
}
export default function TeacherMobileAttendance({schoolId,classes,assignments,workingYearId}){
  const root="schools/"+schoolId+"/attendance/";
  const allowed=new Set(assignments.filter(a=>a.active&&(!workingYearId||a.year===workingYearId)).map(a=>a.classroom));
  const available=classes.filter(c=>c.active&&allowed.has(c.id)&&(!workingYearId||c.year===workingYearId));
  const [classId,setClassId]=useState("");
  const [sessionId,setSessionId]=useState("");
  const [sessions,setSessions]=useState([]);
  const [statuses,setStatuses]=useState([]);
  const [session,setSession]=useState(null);
  const [drafts,setDrafts]=useState({});
  const [date,setDate]=useState(()=>nowLocal().date);
  const [hour,setHour]=useState(()=>nowLocal().hour);
  const [label,setLabel]=useState("");
  const [reason,setReason]=useState("");
  const [filter,setFilter]=useState("all");
  const [search,setSearch]=useState("");
  const [remarks,setRemarks]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  useEffect(()=>{
    setClassId("");setSessionId("");setSessions([]);setStatuses([]);setSession(null);
  },[schoolId,workingYearId]);
  useEffect(()=>{
    setSessions([]);setStatuses([]);setSession(null);setSessionId("");setError("");setMessage("");
    if(!classId)return;
    let active=true;
    Promise.all([
      teacherRequest(root+"options?classroom="+encodeURIComponent(classId)),
      teacherRequest(root+"sessions?classroom="+encodeURIComponent(classId)),
    ]).then(([a,b])=>{if(active){setStatuses(a.statuses||[]);setSessions(b.sessions||[]);}})
      .catch(e=>{if(active)setError(e.message)});
    return()=>{active=false;};
  },[schoolId,classId]);
  useEffect(()=>{
    setSession(null);setDrafts({});setFilter("all");
    if(!sessionId)return;
    let active=true;
    teacherRequest(root+"sessions/"+sessionId)
      .then(v=>{if(active){setSession(v);setDrafts(Object.fromEntries(v.roster.map(item=>[item.enrollment,readState(item)])));}})
      .catch(e=>{if(active)setError(e.message)});
    return()=>{active=false;};
  },[schoolId,sessionId]);
  const roster=session?.roster||[];
  const changed=useMemo(()=>roster.filter(item=>{
    const draft=drafts[item.enrollment];
    if(!draft?.status||item.mark?.justified)return false;
    const mark=item.mark;
    return !mark||mark.status!==draft.status||mark.note!==draft.note||
      mark.justification!==draft.justification||mark.justified!==draft.justified;
  }),[roster,drafts]);
  const correcting=changed.some(item=>!!item.mark);
  const counts=Object.fromEntries(["present","absent","late","other"].map(g=>[g,0]));
  for(const item of roster){
    const status=drafts[item.enrollment]?.status||item.mark?.status;
    const group=statuses.find(s=>s.code===status)?.group||item.mark?.group;
    if(group&&group in counts)counts[group]++;
  }
  async function reloadSession(){
    const latest=await teacherRequest(root+"sessions/"+sessionId);
    setSession(latest);
    setDrafts(Object.fromEntries(latest.roster.map(item=>[item.enrollment,readState(item)])));
  }
  async function create(e){
    e.preventDefault();setBusy(true);setError("");setMessage("");
    try{
      const created=await teacherRequest(root+"sessions",{
        classroom:classId,date,slot:hour.replace(":","-"),label:label.trim()||"Appel de "+hour,
      });
      const list=await teacherRequest(root+"sessions?classroom="+encodeURIComponent(classId));
      setSessions(list.sessions||[]);setSessionId(created.id);
      setMessage("Nouvel appel prêt. Sélectionnez les présences puis enregistrez.");
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function save(){
    if(!changed.length)return;
    setBusy(true);setError("");setMessage("");
    try{
      const marks=changed.map(row=>({
        enrollment:row.enrollment,...drafts[row.enrollment],
        note:remarks.trim()||drafts[row.enrollment].note||"",
        reason:row.mark?reason.trim():"",
      }));
      await teacherRequest(root+"sessions/"+sessionId+"/marks",{marks});
      await reloadSession();
      const list=await teacherRequest(root+"sessions?classroom="+encodeURIComponent(classId));
      setSessions(list.sessions||[]);setReason("");setRemarks("");
      setMessage(marks.length+" présence(s) enregistrée(s).");
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  const choose=(enrollment,status)=>setDrafts(v=>({...v,[enrollment]:{...v[enrollment],status}}));
  const markUnmarkedPresent=()=>{
    const present=statuses.find(s=>s.group==="present");
    if(!present)return;
    setDrafts(v=>Object.fromEntries(roster.map(item=>[
      item.enrollment,item.mark?{...v[item.enrollment]}:
        {...v[item.enrollment],status:present.code},
    ])));
  };
  const displayRoster=roster.filter(item=>{
    const current=drafts[item.enrollment]?.status||item.mark?.status;
    const group=statuses.find(s=>s.code===current)?.group||item.mark?.group;
    if(filter!=="all"&&group!==filter)return false;
    return (item.last_name+" "+item.first_name+" "+item.student_code).toLocaleLowerCase("fr")
      .includes(search.trim().toLocaleLowerCase("fr"));
  });
  return <div className="ym-page ym-call-screen">
    <section className="ym-course-filters">
      <h1>Appel des élèves</h1>
      <label className="ym-label">Classe
        <select aria-label="Classe pour l'appel" value={classId} onChange={e=>setClassId(e.target.value)}>
          <option value="">Choisir une classe</option>
          {available.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      {!available.length&&<p className="ym-empty">Aucune classe affectée pour cette année.</p>}
      {!!classId&&<>
        <label className="ym-label">Séance
          <select aria-label="Séance d'appel" value={sessionId} onChange={e=>{setSessionId(e.target.value);setError("");}}>
            <option value="">Choisir une séance</option>
            {sessions.map(s=><option key={s.id} value={s.id}>{s.date} · {s.label}{s.closed_at?" (clôturée)":""}</option>)}
          </select>
        </label>
        <details className="ym-details"><summary>Créer une nouvelle séance</summary>
          <form className="ym-stack" onSubmit={create}>
            <label>Date<input aria-label="Date de l'appel" type="date" value={date} required onChange={e=>setDate(e.target.value)}/></label>
            <label>Heure<input aria-label="Heure de l'appel" type="time" value={hour} required onChange={e=>setHour(e.target.value)}/></label>
            <label>Intitulé<input aria-label="Intitulé de l'appel" maxLength={120}
              placeholder="Ex. Mathématiques" value={label} onChange={e=>setLabel(e.target.value)}/></label>
            <Button primary type="submit" disabled={busy||!statuses.length}>Créer la séance</Button>
          </form>
        </details>
      </>}
    </section>
    {error&&<p className="ym-alert" role="alert">{error}</p>}
    {message&&<p className="ym-notice" role="status">{message}</p>}
    {session&&<section className="ym-call-card" aria-label="Feuille d'appel">
      <div className="ym-call-heading">
        <span className="ym-call-icon"><Icon name="users" size={30}/></span>
        <div><h2>Appel – {available.find(c=>c.id===classId)?.name||"Classe"}</h2>
          <p>{session.label} · {session.date}{session.slot?" · "+session.slot.replace("-","h"):""}</p>
        </div>
      </div>
      <div className="ym-attendance-stats">
        <div><Icon name="users" size={20}/><strong>{counts.present}</strong><span>Présents</span></div>
        <div><Icon name="user" size={20}/><strong>{counts.absent}</strong><span>Absents</span></div>
        <div><Icon name="calendar" size={20}/><strong>{counts.late}</strong><span>Retards</span></div>
      </div>
      <div className="ym-search-row">
        <label className="ym-search-box"><Icon name="search" size={18}/>
          <input type="search" aria-label="Rechercher un élève" value={search}
            placeholder="Rechercher un élève…" onChange={e=>setSearch(e.target.value)}/>
        </label>
        <label className="ym-search-filter">
          <select aria-label="Filtrer les présences" value={filter} onChange={e=>setFilter(e.target.value)}>
            <option value="all">Tous</option>
            <option value="present">Présents</option>
            <option value="absent">Absents</option><option value="late">Retards</option>
          </select>
        </label>
      </div>
      <div className="ym-section-heading">
        <h2>Liste des élèves ({roster.length})</h2>
        {!session.closed_at&&<button type="button" className="ym-text-action" onClick={markUnmarkedPresent}
          disabled={busy||!statuses.some(s=>s.group==="present")}>
          Tout cocher « Présent »</button>}
      </div>
      <div className="ym-call-roster">{displayRoster.length===0&&<p className="ym-empty">Aucun élève pour ce filtre.</p>}
        {displayRoster.map((item)=>{
          const state=drafts[item.enrollment]||readState(item);
          const locked=Boolean(session.closed_at||item.mark?.justified);
          const initials=(item.first_name?.[0]||"")+(item.last_name?.[0]||"");
          return <div className="ym-call-row" key={item.enrollment}>
            <span className="ym-pupil-avatar" aria-hidden="true">{initials.toUpperCase()}</span>
            <div className="ym-call-pupil"><strong>{item.last_name} {item.first_name}</strong>
              {item.mark?.justified&&<small>Justificatif validé</small>}</div>
            <div className="ym-status-buttons" role="group" aria-label={"Présence de "+item.last_name}>
              {statuses.filter(s=>["present","absent","late"].includes(s.group)).map(s=>
                <button key={s.code} type="button" disabled={busy||locked}
                  aria-pressed={state.status===s.code}
                  className={"ym-status "+s.group+(state.status===s.code?" selected":"")}
                  onClick={()=>choose(item.enrollment,s.code)}>{s.label}</button>)}
            </div>
            {statuses.some(s=>s.group==="other")&&<label className="ym-inline-label">Autre statut
              <select disabled={busy||locked} aria-label={"Autre statut de "+item.last_name}
                value={statuses.some(s=>s.group==="other"&&s.code===state.status)?state.status:""}
                onChange={e=>choose(item.enrollment,e.target.value)}>
                <option value="">Choisir</option>{statuses.filter(s=>s.group==="other").map(s=>
                  <option key={s.code} value={s.code}>{s.label}</option>)}
              </select>
            </label>}
          </div>;
        })}
      </div>
      {!session.closed_at&&<>
        <label className="ym-call-remark">Remarque (facultative, appliquée aux présences modifiées)
          <textarea aria-label="Remarque sur les présences modifiées" maxLength={500}
            value={remarks} onChange={e=>setRemarks(e.target.value)}
            placeholder="Observation concernant les élèves mis à jour…"/>
        </label>
        {correcting&&<label className="ym-label">Motif obligatoire de correction
          <textarea aria-label="Motif des corrections" value={reason}
            required maxLength={500} onChange={e=>setReason(e.target.value)}
            placeholder="Motif de la modification des présences déjà enregistrées"/>
        </label>}
        <Button primary className="ym-full-btn" icon="check"
          disabled={busy||!changed.length||(correcting&&!reason.trim())||changed.length>100}
          onClick={save}>Enregistrer {changed.length} présence(s)</Button>
        <p className="ym-hint">L'enregistrement ne clôture pas l'appel. La clôture est réservée à l'administration.</p>
        {changed.length>100&&<p className="ym-alert">Maximum 100 présences par enregistrement.</p>}
      </>}
      {session.closed_at&&<p className="ym-notice">Appel clôturé : correction réservée à la procédure administrative.</p>}
    </section>}
  </div>;
}
