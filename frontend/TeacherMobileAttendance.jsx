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
        enrollment:row.enrollment,...drafts[row.enrollment],reason:row.mark?reason.trim():"",
      }));
      await teacherRequest(root+"sessions/"+sessionId+"/marks",{marks});
      await reloadSession();
      const list=await teacherRequest(root+"sessions?classroom="+encodeURIComponent(classId));
      setSessions(list.sessions||[]);setReason("");
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
  return <div className="ym-page">
    <Card title="Appel des élèves" icon="users" subtitle="Uniquement vos classes affectées ; les corrections sont historisées.">
      <label className="ym-label">Classe
        <select aria-label="Classe pour l'appel" value={classId} onChange={e=>setClassId(e.target.value)}>
          <option value="">Choisir une classe</option>
          {available.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      {!available.length&&<p className="hint">Aucune classe affectée au compte pour l'année scolaire sélectionnée.</p>}
      {!!classId&&<>
        <label className="ym-label">Séance
          <select aria-label="Séance d'appel" value={sessionId} onChange={e=>{setSessionId(e.target.value);setError("");}}>
            <option value="">Choisir une séance</option>
            {sessions.map(s=><option key={s.id} value={s.id}>{s.date} · {s.label}{s.closed_at?" (clôturée)":""}</option>)}
          </select>
        </label>
        <details className="ym-details"><summary>Créer un nouvel appel</summary>
          <form className="ym-stack" onSubmit={create}>
            <label>Date<input aria-label="Date de l'appel" type="date" value={date} required onChange={e=>setDate(e.target.value)}/></label>
            <label>Heure<input aria-label="Heure de l'appel" type="time" value={hour} required onChange={e=>setHour(e.target.value)}/></label>
            <label>Intitulé (facultatif)<input aria-label="Intitulé de l'appel" maxLength={120}
              placeholder="Ex. Mathématiques" value={label} onChange={e=>setLabel(e.target.value)}/></label>
            <Button primary type="submit" disabled={busy||!statuses.length}>Créer la séance</Button>
          </form>
        </details>
      </>}
    </Card>
    {error&&<p className="ym-alert" role="alert">{error}</p>}
    {message&&<p className="ym-notice" role="status">{message}</p>}
    {session&&<Card title={session.label} icon="calendar" subtitle={session.date+(session.closed_at?" · Appel clôturé":" · Appel ouvert")}>
      <div className="ym-attendance-stats">
        <div><strong>{counts.present}</strong><span>Présents</span></div>
        <div><strong>{counts.absent}</strong><span>Absents</span></div>
        <div><strong>{counts.late}</strong><span>Retards</span></div>
      </div>
      <div className="ym-attendance-actions">
        <label>Afficher<select aria-label="Filtrer les présences" value={filter} onChange={e=>setFilter(e.target.value)}>
          <option value="all">Tous</option>
          <option value="absent">Absents</option><option value="late">Retards</option>
        </select></label>
        {!session.closed_at&&<Button onClick={markUnmarkedPresent}
          disabled={busy||!statuses.some(s=>s.group==="present")}>
          Tout marquer présent (non renseignés)</Button>}
      </div>
      <div className="ym-student-list">{roster.filter(item=>{
        if(filter==="all")return true;
        const active=drafts[item.enrollment]?.status||item.mark?.status;
        return (statuses.find(s=>s.code===active)?.group||item.mark?.group)===filter;
      }).map((item,i)=>{
        const data=drafts[item.enrollment]||readState(item);
        const readOnly=Boolean(session.closed_at||item.mark?.justified);
        return <div className="ym-attendance-student" key={item.enrollment}>
          <div className="ym-student-name">
            <span className="ym-num">{i+1}</span>
            <span><strong>{item.last_name} {item.first_name}</strong><small>{item.student_code}</small></span>
          </div>
          <div className="ym-status-buttons" role="group" aria-label={"Présence de "+item.last_name}>
            {statuses.filter(s=>["present","absent","late"].includes(s.group)).map(status=>
              <button key={status.code} type="button" disabled={busy||readOnly}
                aria-pressed={data.status===status.code}
                className={"ym-status "+status.group+(data.status===status.code?" selected":"")}
                onClick={()=>choose(item.enrollment,status.code)}>{status.label}</button>)}
          </div>
          {statuses.some(s=>s.group==="other")&&<label className="ym-inline-label">Autre statut
            <select disabled={busy||readOnly} aria-label={"Autre statut de "+item.last_name}
              value={statuses.some(s=>s.group==="other"&&s.code===data.status)?data.status:""}
              onChange={e=>choose(item.enrollment,e.target.value)}>
              <option value="">Choisir</option>
              {statuses.filter(s=>s.group==="other").map(s=><option key={s.code} value={s.code}>{s.label}</option>)}
            </select>
          </label>}
          {item.mark?.justified&&<small>Justificatif validé par l'administration : présence verrouillée.</small>}
        </div>;
      })}</div>
      {!session.closed_at&&changed.length>0&&<>
        {correcting&&<label className="ym-label">Motif des corrections
          <textarea aria-label="Motif des corrections" value={reason}
            required maxLength={500} onChange={e=>setReason(e.target.value)}
            placeholder="Pourquoi corriger les présences déjà enregistrées ?"/>
        </label>}
        <Button primary icon="check" disabled={busy||(correcting&&!reason.trim())||changed.length>100}
          onClick={save}>Enregistrer {changed.length} présence(s)</Button>
        {changed.length>100&&<p className="ym-alert">Maximum 100 présences par enregistrement.</p>}
      </>}
      {session.closed_at&&<p className="ym-notice">Cet appel est clôturé. Toute correction relève de la procédure administrative.</p>}
    </Card>}
  </div>;
}
