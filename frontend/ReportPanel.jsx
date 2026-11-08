import React, {useEffect,useState} from "react";
import {TableScroll} from "./yem-ui.jsx";
import {ClassField} from "./SchoolSettings.jsx";

async function call(path,body){
  if(body!==undefined)await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const token=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{
    method:body===undefined?"GET":"POST",credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  if(!response.headers.get("content-type")?.includes("application/json"))throw Error("Service indisponible.");
  const data=await response.json();
  if(!response.ok)throw Error(data.error||"Accès refusé.");
  return data;
}

export default function ReportPanel({schoolId, canPrepare = true, canPublish = true}){
  const base="schools/"+schoolId+"/";
  const [pupils,setPupils]=useState([]);
  const [periods,setPeriods]=useState([]);
  const [reports,setReports]=useState([]);
  const [classes,setClasses]=useState([]);
  const [years,setYears]=useState([]);
  const [room,setRoom]=useState("");
  const [selectedEnrollment,setSelectedEnrollment]=useState("");
  const [selectedPeriod,setSelectedPeriod]=useState("");
  const [selectedReport,setSelectedReport]=useState("");
  const [preview,setPreview]=useState(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [loadError,setLoadError]=useState("");

  const classReports = base+"reports?classroom="+encodeURIComponent(room);
  const updateReports=async()=>{
    const result=await call(classReports);
    setReports(result.reports);setPupils(result.pupils);
  };
  useEffect(()=>{
    let active=true;
    Promise.all([
      call(base+"academic/periods"),call(base+"academic/classes"),call(base+"academic/years"),
    ]).then(([p,c,y])=>{
      if(!active)return;
      setPeriods(p.periods);setClasses(c.classes);setYears(y.years);
    }).catch(error=>{if(active)setLoadError(error.message);});
    return()=>{active=false;};
  },[schoolId]);
  useEffect(()=>{
    if(!room)return;
    let active=true;
    call(classReports).then(result=>{
      if(active){setReports(result.reports);setPupils(result.pupils);}
    }).catch(error=>{if(active)setMessage(error.message);});
    return()=>{active=false;};
  },[room,classReports]);
  useEffect(()=>{
    setPreview(null);
    if(!selectedReport)return;
    let active=true;
    call(base+"reports/"+selectedReport)
      .then(data=>{if(active)setPreview(data);})
      .catch(e=>{if(active)setMessage(e.message);});
    return()=>{active=false;};
  },[selectedReport,schoolId]);

  async function run(task) {
    setBusy(true);setMessage("");
    try{await task();}
    catch(e){setMessage(e.message);}
    finally{setBusy(false);}
  }

  if(loadError)return <p role="alert">{loadError}</p>;
  const activeEnrollment=pupils.find(e=>e.id===selectedEnrollment);
  const applicablePeriods=periods.filter(p=>p.year===activeEnrollment?.year);
  const current=reports.find(r=>r.enrollment===selectedEnrollment&&r.period===(selectedPeriod||null));
  const snapshot=preview?.snapshot;

  return <section className="card" aria-label="Bulletins et résultats" style={{marginTop:"1rem"}}>
    <h2>Bulletins et résultats</h2>
    <ClassField classes={classes} years={years} value={room} disabled={busy} onChange={value=>{
      setRoom(value);setPupils([]);setReports([]);setSelectedEnrollment("");setSelectedPeriod("");setSelectedReport("");setPreview(null);setMessage("");
    }}/>
    {room && <>
    {!pupils.length && <p>Aucun élève ou bulletin disponible pour cette classe.</p>}
    <form onSubmit={e=>{e.preventDefault();if(!canPrepare || !activeEnrollment?.can_prepare)return;run(async()=>{
      const result=await call(base+"reports",{
        enrollment:selectedEnrollment,period:selectedPeriod||null,revision:current?.revision||0,
      });
      await updateReports();setSelectedReport(result.id);setPreview(result);
      setMessage("Bulletin préparé. Vérifiez son contenu avant publication.");
    });}}>
      <div className="two">
        <label className="field">Élève inscrit
          <select required value={selectedEnrollment} onChange={e=>{setSelectedEnrollment(e.target.value);setSelectedPeriod("");setSelectedReport("");setPreview(null);}}>
            <option value="">Sélectionner…</option>
            {pupils.map(pupil=><option key={pupil.id} value={pupil.id}>{pupil.name}</option>)}
          </select>
        </label>
        <label className="field">Période à présenter
          <select value={selectedPeriod} onChange={e=>setSelectedPeriod(e.target.value)}>
            <option value="">Bilan de l'année complète</option>
            {applicablePeriods.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
      </div>
      {canPrepare && activeEnrollment?.can_prepare && <button type="submit" disabled={busy||!selectedEnrollment||current?.status==="published"}>Préparer le bulletin</button>}
      {current?.status==="published"&&<p className="hint">Ce bulletin est déjà publié et reste immuable.</p>}
    </form>
    <label className="field">Bulletins enregistrés
      <select value={selectedReport} onChange={e=>setSelectedReport(e.target.value)}>
        <option value="">Choisir…</option>
        {reports.filter(r=>selectedEnrollment && r.enrollment===selectedEnrollment).map(r=>
          <option key={r.id} value={r.id}>{periods.find(p=>p.id===r.period)?.name || "Année complète"} · {r.status==="published"?"Publié":"Brouillon"}</option>)}
      </select>
    </label>
    </>}
    {preview&&snapshot&&<>
      <h3>{snapshot.template.title} · {preview.status==="published"?"Publié":"Brouillon"}</h3>
      <p><strong>{snapshot.student.last_name} {snapshot.student.first_name}</strong> — {snapshot.student.code}</p>
      <p>{snapshot.class.name} · {snapshot.year.name} · {snapshot.period?.name||"Année complète"}</p>
      <TableScroll label="Notes du bulletin">
        <table style={{width:"100%"}}>
          <thead><tr><th>Matière</th><th>Coefficient</th><th>Résultat</th></tr></thead>
          <tbody>{snapshot.subjects.map(s=><tr key={s.course}>
            <td>{s.subject}</td><td>{s.coefficient}</td>
            <td>{snapshot.template.show_score && (s.result.score ?? "—")} {
              snapshot.template.show_label && (s.result.label || "")
            }</td>
          </tr>)}</tbody>
        </table></TableScroll>
      <p><strong>Résultat général :</strong> {snapshot.template.show_score && (snapshot.overall.score ?? "—")} {
        snapshot.template.show_label && (snapshot.overall.label ?? "Non calculé")
      }</p>
      <div className="actions">
        <a href={"/api/v1/"+base+"reports/"+preview.id+"/pdf"}>Exporter le bulletin PDF (A4)</a>
        {canPublish&&preview.status==="draft"&&<button type="button" disabled={busy} onClick={()=>run(async()=>{
          const issued=await call(base+"reports/"+preview.id+"/publish",{revision:preview.revision});
          await updateReports();setPreview(issued);setMessage("Bulletin publié et verrouillé.");
        })}>Publier le bulletin</button>}
      </div>
    </>}
    {message&&<p role="status" aria-live="polite">{message}</p>}
  </section>;
}
