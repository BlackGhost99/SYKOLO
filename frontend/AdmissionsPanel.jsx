import React, {useEffect, useState} from "react";
import {AdmissionPolicyEditor,AdmissionProofPanel,AdmissionDecisionReadiness,ROUTES} from "./AdmissionRoutesPanel.jsx";
import {SchoolCatalogSettings} from "./ParentDiscovery.jsx";
import SchoolPaymentSetup from "./SchoolPaymentSetup.jsx";
import AdmissionCashDesk, {librevilleToday} from "./AdmissionCashDesk.jsx";
import {FinancePolicyEditor,GovernmentScholarshipPanel} from "./AdmissionFinance.jsx";
import {useSchoolData} from "./SchoolSettings.jsx";

async function admissionApi(path, body){
  if(body!==undefined) await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{
    method:body===undefined?"GET":"POST", credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:body===undefined?undefined:JSON.stringify(body)
  });
  if(!response.headers.get("content-type")?.includes("application/json"))throw Error("Service indisponible.");
  const json=await response.json();
  if(!response.ok)throw Error(json.error||"Opération refusée.");
  return json;
}

const STATES={submitted:"Déposée",review:"En étude",accepted:"Admise",rejected:"Refusée",enrolled:"Inscrite"};
export function AdmissionSettings({schoolId, canDecide, canConfigureCatalog, canConfigureFinance=false}) {
  const root = "schools/" + schoolId + "/";
  const {data, error} = useSchoolData(root, "academic/years academic/levels");
  const [year, setYear] = useState("");
  const [level, setLevel] = useState("");
  return <section className="card">
    <h3>Voies d’admission et pièces à fournir</h3>
    {error && <p role="alert">{error}</p>}
    {data && <div className="two">
      <label className="field">Année scolaire
        <select value={year} onChange={event => setYear(event.target.value)}>
          <option value="">Choisir l’année…</option>
          {data.years.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <label className="field">Niveau
        <select value={level} onChange={event => setLevel(event.target.value)}>
          <option value="">Tous les niveaux</option>
          {data.levels.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
    </div>}
    {year && <AdmissionPolicyEditor api={admissionApi} base={root + "admissions"} year={year} level={level || null} canDecide={canDecide}/>}
    {year && <FinancePolicyEditor schoolId={schoolId} year={year} level={level||null} canManage={canConfigureFinance}/>} 
    {canConfigureCatalog && <SchoolCatalogSettings schoolId={schoolId}/>}
  </section>;
}

export function AdmissionPaymentSettings({schoolId}) {
  const {data, error} = useSchoolData("schools/" + schoolId + "/", "academic/years academic/classes academic/levels");
  if (!data) return <p role="status">{error || "Chargement des années et des niveaux…"}</p>;
  const classes = data.classes.filter(item => item.active).map(item => ({
    ...item, level_name: data.levels.find(level => level.id === item.level)?.name,
  }));
  return <SchoolPaymentSetup schoolId={schoolId} years={data.years} classes={classes}/>;
}

export default function AdmissionsPanel({schoolId,canDecide=false,canCreate=true,canEnroll=true,canReceive=false,canApproveScholarship=false}){
  const root="schools/"+schoolId+"/";
  const base=root+"admissions";
  const [formError,setFormError]=useState("");
  const [years,setYears]=useState([]),[classes,setClasses]=useState([]),
    [students,setStudents]=useState([]),[applications,setApplications]=useState([]);
  const [year,setYear]=useState(""),[classroom,setClassroom]=useState(""),
    [first,setFirst]=useState(""),[last,setLast]=useState(""),[birth,setBirth]=useState(""),
    [guardian,setGuardian]=useState(""),[relation,setRelation]=useState(""),
    [phone,setPhone]=useState(""),[email,setEmail]=useState(""),
    [route,setRoute]=useState("direct"),[origin,setOrigin]=useState(""),
    [routeReference,setRouteReference]=useState(""),[orientationAuthority,setOrientationAuthority]=useState(""),
    [routePolicy,setRoutePolicy]=useState(null),
    [existing,setExisting]=useState(""),[chosen,setChosen]=useState(""),
    [reason,setReason]=useState(""),
    [enrollDate,setEnrollDate]=useState(""),[capacity,setCapacity]=useState(null),
    [history,setHistory]=useState(null),[busy,setBusy]=useState(false),
    [message,setMessage]=useState(""),[loadError,setLoadError]=useState("");
  async function refresh(){
    const result=await admissionApi(base);
    setApplications(result.applications||[]);
  }
  useEffect(()=>{
    let active=true;
    admissionApi(base).then(result=>{
      if(active)setApplications(result.applications||[]);
    }).catch(error=>{if(active)setLoadError(error.message);});
    Promise.all([
      admissionApi(root+"academic/years"),admissionApi(root+"academic/classes"),
    ]).then(([ys,cs])=>{
      if(!active)return;
      setYears(ys.years||[]);setClasses(cs.classes||[]);
    }).catch(error=>{if(active && canCreate)setFormError(error.message);});
    if(canCreate) admissionApi(root+"students").then(result=>{
      if(active)setStudents(result.students||[]);
    }).catch(()=>{if(active)setStudents([]);});
    return()=>{active=false};
  },[schoolId,canCreate]);
  useEffect(()=>{
    let active=true;setCapacity(null);
    if(classroom)admissionApi(base+"/capacity/"+classroom).then(x=>{if(active)setCapacity(x)})
      .catch(()=>{if(active)setCapacity(null)});
    return()=>{active=false};
  },[schoolId,classroom,applications]);
  const selectedLevel=classes.find(c=>c.id===classroom)?.level||null;
  useEffect(()=>{
    let live=true;setRoutePolicy(null);
    if(!year)return;
    const params=new URLSearchParams({year,...(selectedLevel?{level:selectedLevel}:{})});
    admissionApi(base+"/policy?"+params.toString())
      .then(result=>{if(live){setRoutePolicy(result);
        setRoute(current=>result.enabled_routes.includes(current)?current:result.enabled_routes[0]);}})
      .catch(err=>{if(live)setMessage(err.message)});
    return()=>{live=false;};
  },[base,year,selectedLevel]);
  async function run(fn){
    setBusy(true);setMessage("");
    try{await fn();await refresh()}catch(error){setMessage(error.message)}
    finally{setBusy(false)}
  }
  if(loadError)return <p role="alert">{loadError}</p>;
  const current=applications.find(x=>x.id===chosen);
  const availableClasses=classes.filter(x=>x.active&&x.year===year);
  return <section className="card" style={{marginTop:"1rem"}} aria-label="Admissions et préinscriptions">
    <h2>Admissions et préinscriptions</h2>
    <p className="hint">La direction statue sur la candidature. La caisse confirme les espèces reçues. Le secrétariat ou la direction finalise ensuite l’inscription si le dossier est admis et que les frais obligatoires sont réglés ou couverts.</p>
    {canCreate && <details>
    <summary>Nouvelle candidature</summary>
    {formError && <p role="alert">{formError}</p>}
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      const application=await admissionApi(base,{
        year,classroom,first_name:first,last_name:last,
        date_of_birth:birth||null,guardian_name:guardian,
        guardian_relationship:relation,guardian_phone:phone,
        guardian_email:email,source:"guichet",existing_student:existing||null,
        route,origin_school:origin,route_reference:route==="direct"?"":routeReference,
        orientation_authority:route==="orientation"?orientationAuthority:""
      });
      setChosen(application.id);setEnrollDate(librevilleToday());setFirst("");setLast("");setBirth("");setGuardian("");
      setPhone("");setEmail("");setRelation("");setExisting("");
      setRouteReference("");setOrientationAuthority("");setOrigin("");
      setMessage("Candidature enregistrée. Aucun dossier élève officiel n'a encore été créé.");
    })}}>
      <div className="two">
        <label className="field">Année scolaire
          <select required value={year} onChange={e=>{setYear(e.target.value);setClassroom("");setRoute("direct");}}>
            <option value="">Choisir une année</option>
            {years.filter(x=>x.active).map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label className="field">Classe demandée
          <select required value={classroom} onChange={e=>setClassroom(e.target.value)}>
            <option value="">Choisir une classe</option>
            {availableClasses.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        </label>
        <label className="field">Voie d'admission
          <select value={route} onChange={e=>setRoute(e.target.value)}>
            {Object.entries(ROUTES).filter(([key])=>(routePolicy?.enabled_routes||Object.keys(ROUTES)).includes(key))
              .map(([key,label])=><option key={key} value={key}>{label}</option>)}
          </select>
        </label>
        <label className="field">Établissement d'origine
          <input maxLength={180} value={origin} onChange={e=>setOrigin(e.target.value)}
            placeholder="École précédente (si applicable)"/>
        </label>
        {route!=="direct"&&<label className="field">Référence du concours / de l'affectation (si connue)
          <input maxLength={140} value={routeReference} onChange={e=>setRouteReference(e.target.value)}/>
        </label>}
        {route==="orientation"&&<label className="field">Autorité d'orientation (si connue)
          <input maxLength={120} value={orientationAuthority} onChange={e=>setOrientationAuthority(e.target.value)}/>
        </label>}
        <label className="field">Prénom(s) de l'élève
          <input required maxLength={120} value={first} onChange={e=>setFirst(e.target.value)}/>
        </label>
        <label className="field">Nom de l'élève
          <input required maxLength={120} value={last} onChange={e=>setLast(e.target.value)}/>
        </label>
        <label className="field">Naissance (facultatif)
          <input type="date" value={birth} onChange={e=>setBirth(e.target.value)}/>
        </label>
        <label className="field">Responsable légal
          <input required maxLength={180} value={guardian} onChange={e=>setGuardian(e.target.value)}/>
        </label>
        <label className="field">Lien de parenté
          <input maxLength={80} value={relation} onChange={e=>setRelation(e.target.value)}/>
        </label>
        <label className="field">Téléphone
          <input type="tel" maxLength={45} value={phone} onChange={e=>setPhone(e.target.value)}/>
        </label>
        <label className="field">Email
          <input type="email" maxLength={254} value={email} onChange={e=>setEmail(e.target.value)}/>
        </label>
        <label className="field">Dossier élève existant (facultatif)
          <select value={existing} onChange={e=>setExisting(e.target.value)}>
            <option value="">Nouvel élève</option>
            {students.filter(x=>x.active).map(x=><option key={x.id} value={x.id}>{x.last_name} {x.first_name} · {x.student_code}</option>)}
          </select>
        </label>
      </div>
      {capacity&&<p className="hint">Classe : {capacity.occupied} inscrit(s), {capacity.accepted_pending} admis en attente.
        {capacity.remaining===null?" Capacité non plafonnée.":" Places restantes à l'inscription : "+capacity.remaining+"."}
      </p>}
      <button disabled={busy||!year||!classroom} type="submit">Déposer la candidature</button>
    </form></details>}
    <h3>Traitement des candidatures</h3>
    <button type="button" disabled={busy} onClick={()=>run(()=>{
      setMessage("Candidatures actualisées.");
    })}>Actualiser les candidatures</button>
    <label className="field">Candidature
      <select value={chosen} onChange={e=>{setChosen(e.target.value);setReason("");setHistory(null);setEnrollDate(librevilleToday());}}>
        <option value="">Choisir un dossier…</option>
        {applications.map(x=><option key={x.id} value={x.id}>{x.last_name} {x.first_name} · {STATES[x.status]||x.status}</option>)}
      </select>
    </label>
    {current&&<div>
      <p><strong>{current.last_name} {current.first_name}</strong> · {STATES[current.status]} ·
        {ROUTES[current.route]||"Inscription directe"} ·
        {classes.find(c=>c.id===current.classroom)?.name||"Classe"}
      </p>
      <p className="hint">Responsable : {current.guardian_name} · Dépôt : {new Date(current.submitted_at).toLocaleDateString("fr-FR")}.
        {current.decision_reason?" Décision : "+current.decision_reason:""}
      </p>
      {current.source==="parent_mobile" && <AdmissionCashDesk key={current.id} schoolId={schoolId}
        applicationId={current.id} canReceive={canReceive} onUpdated={refresh}/>}
      {current.status!=="enrolled"&&current.status!=="rejected"&&current.finance?.blocker&&
        <p role="status">Avant l’inscription définitive. {current.finance.blocker}</p>}
      {(current.status==="submitted"||current.status==="review")&&!canDecide&&
        <p>Décision d’admission attendue de la direction.</p>}
      <AdmissionProofPanel key={current.id} api={admissionApi} base={base}
        application={current} canDecide={canDecide} onUpdated={refresh}/>
      <AdmissionDecisionReadiness application={current}/>
      <GovernmentScholarshipPanel schoolId={schoolId} application={current}
        canApprove={canApproveScholarship} onUpdated={refresh}/>
      {(current.status==="submitted"||current.status==="review")&&canDecide&&<form onSubmit={e=>e.preventDefault()}>
        <label className="field">Motif de la décision (requis pour accepter ou refuser)
          <textarea placeholder="Ex. dossier complet et place disponible" maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/>
        </label>
        {current.status==="submitted"&&<button disabled={busy} type="button" onClick={()=>run(async()=>{
          await admissionApi(base+"/"+current.id+"/decide",{revision:current.revision,status:"review",reason});
          setReason("");
        })}>Passer en étude</button>}
        <button disabled={busy||reason.trim().length===0||Boolean(current.acceptance_blocker)} type="button" onClick={()=>run(async()=>{
          await admissionApi(base+"/"+current.id+"/decide",{revision:current.revision,status:"accepted",reason});
          setReason("");
        })}>Accepter la candidature (direction)</button>
        <button disabled={busy||reason.trim().length===0} type="button" onClick={()=>run(async()=>{
          await admissionApi(base+"/"+current.id+"/decide",{revision:current.revision,status:"rejected",reason});
          setReason("");
        })}>Refuser la candidature (direction)</button>
      </form>}
      {current.status==="accepted"&&!canEnroll&&<p>Le secrétariat ou la direction peut finaliser l’inscription.</p>}
      {current.status==="accepted"&&canEnroll&&<form onSubmit={e=>{e.preventDefault();run(async()=>{
        await admissionApi(base+"/"+current.id+"/convert",{
          revision:current.revision,enrolled_on:enrollDate
        });
        setMessage("Inscription officielle créée ; vous pouvez gérer les frais dans la caisse scolaire.");
      })}}>
        <p className="hint">L'établissement vérifie à nouveau la capacité lors de l'inscription officielle.</p>
        <div className="two">
          <label className="field">Date de l'inscription
            <input type="date" required value={enrollDate} onChange={e=>setEnrollDate(e.target.value)}/>
          </label>
        </div>
        <button disabled={busy||!enrollDate||Boolean(current.finance?.blocker)} type="submit">Confirmer l’inscription définitive</button>
      </form>}
      {current.status==="enrolled"&&<p>Inscription confirmée</p>}
      <button type="button" disabled={busy} onClick={()=>run(async()=>{
        const result=await admissionApi(base+"/"+current.id+"/history");
        setHistory(result.history||[]);
      })}>Voir l'historique des décisions</button>
      {history&&<div>
        {history.map((h,i)=><p key={i}><strong>{STATES[h.status]||h.status}</strong> · {new Date(h.at).toLocaleString("fr-FR")}
          {h.reason?" — "+h.reason:""}</p>)}
      </div>}
    </div>}
    {message&&<p role="status" aria-live="polite">{message}</p>}
  </section>;
}
