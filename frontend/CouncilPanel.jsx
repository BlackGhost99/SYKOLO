import React, {useEffect, useState} from "react";

async function api(path, data) {
  if (data !== undefined) await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
  const token = document.cookie.split("; ").find(c => c.startsWith("csrftoken="))?.split("=")[1] || "";
  const response = await fetch("/api/v1/" + path, {
    method: data === undefined ? "GET" : "POST", credentials:"same-origin",
    headers: data === undefined ? {} : {"Content-Type":"application/json","X-CSRFToken":token},
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw Error("Service indisponible.");
  const result = await response.json();
  if (!response.ok) throw Error(result.error || "Action refusée.");
  return result;
}

export default function CouncilPanel({schoolId}) {
  const base = "schools/" + schoolId + "/";
  const [classes, setClasses] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [enrollments, setEnrollments] = useState([]);
  const [students, setStudents] = useState([]);
  const [reports, setReports] = useState([]);
  const [councils, setCouncils] = useState([]);
  const [selectedClass, setSelectedClass] = useState("");
  const [selectedPeriod, setSelectedPeriod] = useState("");
  const [selectedCouncil, setSelectedCouncil] = useState("");
  const [title, setTitle] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [choices, setChoices] = useState([]);
  const [selectedEnrollment, setSelectedEnrollment] = useState("");
  const [selectedReport, setSelectedReport] = useState("");
  const [decisionCode, setDecisionCode] = useState("");
  const [rationale, setRationale] = useState("");
  const [councilData, setCouncilData] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [amendments, setAmendments] = useState([]);
  const [amendCourse, setAmendCourse] = useState("");
  const [amendPercent, setAmendPercent] = useState("");
  const [amendReason, setAmendReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [allowed, setAllowed] = useState(true);

  async function load() {
    const [c,p,e,s,r,session] = await Promise.all([
      api(base+"academic/classes"), api(base+"academic/periods"), api(base+"enrollments"),
      api(base+"students"), api(base+"reports"), api(base+"councils"),
    ]);
    setClasses(c.classes || []);setPeriods(p.periods || []);
    setEnrollments(e.enrollments || []);setStudents(s.students || []);
    setReports(r.reports || []);setCouncils(session.councils || []);
  }
  useEffect(() => {
    let alive=true;
    Promise.all([
      api(base+"academic/classes"),api(base+"academic/periods"),api(base+"enrollments"),
      api(base+"students"),api(base+"reports"),api(base+"councils"),
    ]).then(([c,p,e,s,r,session]) => {
      if(!alive)return;
      setClasses(c.classes||[]);setPeriods(p.periods||[]);
      setEnrollments(e.enrollments||[]);setStudents(s.students||[]);
      setReports(r.reports||[]);setCouncils(session.councils||[]);
    }).catch(() => {if(alive)setAllowed(false);});
    return () => {alive=false;};
  },[schoolId]);
  useEffect(() => {
    if (!selectedClass) {setChoices([]);return;}
    let alive=true;
    api(base+"council-choices?classroom="+encodeURIComponent(selectedClass))
      .then(v => {if(alive)setChoices(v.decisions||[]);})
      .catch(() => {if(alive)setChoices([]);});
    return () => {alive=false;};
  },[schoolId,selectedClass]);
  useEffect(() => {
    if(!selectedCouncil){setCouncilData(null);return;}
    let alive=true;
    api(base+"councils/"+selectedCouncil).then(v=>{if(alive)setCouncilData(v);})
      .catch(e=>{if(alive)setMessage(e.message);});
    return()=>{alive=false;};
  },[schoolId,selectedCouncil]);
  useEffect(() => {
    if(!selectedReport){setReportData(null);setAmendments([]);return;}
    let alive=true;
    Promise.all([api(base+"reports/"+selectedReport),api(base+"reports/"+selectedReport+"/amendments")])
      .then(([r,a])=>{if(alive){setReportData(r);setAmendments(a.amendments||[]);}})
      .catch(e=>{if(alive)setMessage(e.message);});
    return()=>{alive=false;};
  },[schoolId,selectedReport]);

  async function run(task) {
    setBusy(true);setMessage("");
    try {await task();}
    catch(e) {setMessage(e.message);}
    finally {setBusy(false);}
  }
  if(!allowed)return null;
  const classroom=classes.find(c=>c.id===selectedClass);
  const council=councilData;
  const pupilList=enrollments.filter(e=>e.classroom===council?.classroom);
  const reportsForPupil=reports.filter(r=>r.enrollment===selectedEnrollment && r.period===council?.period && r.status==="published");
  const reportSubjects=reportData?.snapshot?.subjects || [];
  const chosenCourse=reportSubjects.find(s=>s.course===amendCourse);

  return <section className="card" aria-label="Conseils et délibérations" style={{marginTop:"1rem"}}>
    <h2>Conseils de classe et décisions</h2>
    <p className="hint">Les décisions possibles sont configurées par l'établissement dans les paramètres « deliberation.decisions ». Aucune décision de passage n'est automatique.</p>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      const created=await api(base+"councils",{
        classroom:selectedClass,period:selectedPeriod||null,title,meeting_date:meetingDate,
      });
      await load();setSelectedCouncil(created.id);setTitle("");
      setMessage("Conseil créé : préparez les décisions avant clôture.");
    });}}>
      <div className="two">
        <label className="field">Classe
          <select required value={selectedClass} onChange={e=>{setSelectedClass(e.target.value);setSelectedPeriod("");}}>
            <option value="">Choisir...</option>
            {classes.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="field">Période
          <select value={selectedPeriod} onChange={e=>setSelectedPeriod(e.target.value)}>
            <option value="">Année entière</option>
            {periods.filter(p=>p.year===classroom?.year).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label className="field">Intitulé du conseil
          <input required maxLength={140} value={title} onChange={e=>setTitle(e.target.value)} />
        </label>
        <label className="field">Date de réunion
          <input required type="date" value={meetingDate} onChange={e=>setMeetingDate(e.target.value)} />
        </label>
      </div>
      <button type="submit" disabled={busy || !selectedClass}>Créer le conseil</button>
    </form>
    <label className="field">Conseils enregistrés
      <select value={selectedCouncil} onChange={e=>{setSelectedCouncil(e.target.value);setSelectedEnrollment("");}}>
        <option value="">Choisir...</option>
        {councils.map(c=><option key={c.id} value={c.id}>{c.title} · {c.status==="closed"?"Clôturé":"Brouillon"}</option>)}
      </select>
    </label>
    {council&&<>
      <p><strong>{council.title}</strong> · {council.status==="closed"?"Clôturé":"En préparation"} · {council.decisions?.length||0} décision(s)</p>
      {council.decisions?.map(d=><p key={d.id}>{students.find(s=>s.id===enrollments.find(e=>e.id===d.enrollment)?.student)?.last_name||"Élève"} : {d.label}</p>)}
      {council.status==="draft"&&<form onSubmit={e=>{e.preventDefault();run(async()=>{
        const current=council.decisions?.find(d=>d.enrollment===selectedEnrollment);
        await api(base+"councils/"+council.id+"/decisions",{
          enrollment:selectedEnrollment,report:selectedReport,code:decisionCode,rationale,
          revision:current?.revision||0,
        });
        setCouncilData(await api(base+"councils/"+council.id));
        setMessage("Décision enregistrée.");
      });}}>
        <h3>Délibérer pour un élève</h3>
        <label className="field">Élève de la classe
          <select required value={selectedEnrollment} onChange={e=>{setSelectedEnrollment(e.target.value);setSelectedReport("");}}>
            <option value="">Choisir...</option>
            {pupilList.map(e=><option key={e.id} value={e.id}>{students.find(s=>s.id===e.student)?.last_name||e.id.slice(0,8)}</option>)}
          </select>
        </label>
        <label className="field">Bulletin publié de la période
          <select required value={selectedReport} onChange={e=>setSelectedReport(e.target.value)}>
            <option value="">Choisir...</option>
            {reportsForPupil.map(r=><option key={r.id} value={r.id}>{r.id.slice(0,8)} · Publié</option>)}
          </select>
        </label>
        <label className="field">Décision
          <select required value={decisionCode} onChange={e=>setDecisionCode(e.target.value)}>
            <option value="">Choisir...</option>
            {choices.map(c=><option key={c.code} value={c.code}>{c.label}</option>)}
          </select>
        </label>
        <label className="field">Motif de décision
          <textarea required maxLength={1000} value={rationale} onChange={e=>setRationale(e.target.value)} />
        </label>
        <button type="submit" disabled={busy||!selectedReport||!decisionCode}>Enregistrer la décision</button>
      </form>}
      {council.status==="draft"&&<button type="button" disabled={busy||!council.decisions?.length} onClick={()=>run(async()=>{
        const result=await api(base+"councils/"+council.id+"/close",{revision:council.revision});
        setCouncilData({...council,...result});
        await load();setMessage("Conseil clôturé et décisions verrouillées.");
      })}>Clôturer le conseil</button>}
    </>}
    <h3>Rectifications des bulletins publiés</h3>
    <p className="hint">Chaque rectification est un document supplémentaire : le bulletin original reste inchangé.</p>
    <label className="field">Bulletin à rectifier
      <select value={selectedReport} onChange={e=>{setSelectedReport(e.target.value);setAmendCourse("");}}>
        <option value="">Choisir...</option>
        {reports.filter(r=>r.status==="published").map(r=><option key={r.id} value={r.id}>{r.id.slice(0,8)} · Élève {r.enrollment.slice(0,8)}</option>)}
      </select>
    </label>
    {selectedReport && reportData?.status==="published"&&<>
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        const result=await api(base+"reports/"+selectedReport+"/amendments",{
          course:amendCourse,percent:amendPercent,reason:amendReason,
          revision:amendments.length?amendments[amendments.length-1].sequence:0,
        });
        const data=await api(base+"reports/"+selectedReport+"/amendments");
        setAmendments(data.amendments);setAmendPercent("");setAmendReason("");
        setMessage("Rectificatif n° "+result.sequence+" créé. L'original est conservé.");
      });}}>
        <div className="two">
          <label className="field">Matière à rectifier
            <select required value={amendCourse} onChange={e=>setAmendCourse(e.target.value)}>
              <option value="">Choisir...</option>
              {reportSubjects.map(s=><option key={s.course} value={s.course}>{s.subject}</option>)}
            </select>
          </label>
          <label className="field">Nouveau résultat en %
            <input type="number" step="any" min="0" max="100" required value={amendPercent} onChange={e=>setAmendPercent(e.target.value)} />
          </label>
        </div>
        {chosenCourse && <p className="hint">Résultat initial : {chosenCourse.result.percent??"Non évalué"} %.</p>}
        <label className="field">Justification obligatoire
          <textarea required minLength={10} maxLength={1000} value={amendReason} onChange={e=>setAmendReason(e.target.value)} />
        </label>
        <button disabled={busy||!amendCourse} type="submit">Créer un rectificatif</button>
      </form>
      {amendments.map(a=><p key={a.id}>Rectificatif n° {a.sequence} · {a.before_percent??"—"} % → {a.after_percent} % · <a href={"/api/v1/"+base+"reports/"+selectedReport+"/amendments/"+a.id+"/pdf"}>PDF A4</a></p>)}
    </>}
    {message&&<p role="status" aria-live="polite">{message}</p>}
  </section>;
}
