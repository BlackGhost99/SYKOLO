import React, {useEffect, useState} from "react";
import AnnualWorkspace from "./AnnualWorkspace.jsx";
import {PageHeader, Card} from "./yem-ui.jsx";

const yearState = {preparation:"En préparation",current:"En cours",closed:"Clôturée"};
const blankEvent = {title:"",kind:"autre",scope:"all",start_date:"",end_date:"",
  description:"",source:"school",source_url:""};
const blankPeriod = {code:"",name:"",start_date:"",end_date:""};
const officialSource = "https://www.gabonreview.com/gabon-la-rentree-des-classes-fixee-au-7-septembre-2026/";
const ga2026Periods = [
  {code:"t1",name:"1er trimestre",start_date:"2026-09-07",end_date:"2026-11-28"},
  {code:"t2",name:"2e trimestre",start_date:"2026-12-07",end_date:"2027-03-06"},
  {code:"t3",name:"3e trimestre",start_date:"2027-03-15",end_date:"2027-07-10"},
];
const ga2026Events = [
  {title:"Rentrée administrative",kind:"rentree",start_date:"2026-08-31",end_date:"2026-08-31"},
  {title:"Rentrée des classes",kind:"rentree",start_date:"2026-09-07",end_date:"2026-09-07"},
  {title:"Vacances de fin du 1er trimestre",kind:"vacances",start_date:"2026-11-28",end_date:"2026-12-06"},
  {title:"Vacances de fin du 2e trimestre",kind:"vacances",start_date:"2027-03-06",end_date:"2027-03-14"},
  {title:"Fin des cours (classes sans examen)",kind:"cours",start_date:"2027-06-05",end_date:"2027-06-05"},
  {title:"Période des examens nationaux",kind:"examen",start_date:"2027-05-24",end_date:"2027-07-10"},
];

async function calendarRequest(path, body, method="POST") {
  if (body !== undefined) {
    const csrf=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
    if (!csrf.ok) throw Error("Session indisponible, reconnectez-vous.");
  }
  const token=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.slice(10)||"";
  const response=await fetch("/api/v1/"+path,{
    credentials:"same-origin",
    ...(body===undefined?{}:{
      method,headers:{"Content-Type":"application/json","X-CSRFToken":token},
      body:JSON.stringify(body),
    }),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw Error("Service du calendrier indisponible.");
  }
  const result=await response.json();
  if (!response.ok) throw Error(result.error||"Opération refusée.");
  return result;
}

const dateLabel=value=>value?new Date(value+"T12:00:00").toLocaleDateString("fr-FR",
  {day:"2-digit",month:"short",year:"numeric"}):"—";
const kindLabel=(list,code)=>list?.find(x=>x.code===code)?.label||code;

export default function PedagogicalCalendar({
  schoolId,workingYearId="",onWorkingYearChange,onYearsUpdated,
}) {
  const prefix="schools/"+schoolId+"/academic/";
  const [snapshot,setSnapshot]=useState(null);
  const [catalog,setCatalog]=useState(null);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [yearDraft,setYearDraft]=useState(null);
  const [periodDraft,setPeriodDraft]=useState(null);
  const [eventDraft,setEventDraft]=useState(null);
  const [version,setVersion]=useState(0);
  const selectedYear=snapshot?.year;
  const canEdit=Boolean(snapshot?.can_edit_year);
  const canManage=Boolean(catalog?.can_manage);
  const reference2026=selectedYear && selectedYear.start_date.startsWith("2026-")
    && selectedYear.end_date.startsWith("2027-");

  useEffect(()=>{
    let alive=true;
    setLoading(true);setError("");setPeriodDraft(null);setEventDraft(null);setYearDraft(null);
    (async()=>{
      const annual=await calendarRequest(prefix+"annual-snapshot"+
        (workingYearId?"?year="+encodeURIComponent(workingYearId):""));
      const events=annual.year
        ? await calendarRequest(prefix+"pedagogical-calendar?year="+encodeURIComponent(annual.year.id))
        : null;
      if (!alive) return;
      setSnapshot(annual);setCatalog(events);
      if (annual.year && !workingYearId) onWorkingYearChange?.(annual.year.id);
    })().catch(e=>{if(alive)setError(e.message)}).finally(()=>{if(alive)setLoading(false)});
    return()=>{alive=false};
  },[schoolId,workingYearId,version]);

  async function run(task,{refreshYears=false}={}) {
    setBusy(true);setError("");setMessage("");
    try {
      const response=await task();
      if (refreshYears) onYearsUpdated?.();
      setVersion(v=>v+1);
      return response;
    } catch(e) {
      setError(e.message);
      return null;
    } finally {setBusy(false)}
  }

  function editingYear() {
    setYearDraft({name:selectedYear.name,
      start_date:selectedYear.start_date,end_date:selectedYear.end_date});
    setPeriodDraft(null);setEventDraft(null);
  }

  async function saveYear(e) {
    e.preventDefault();
    const changes={revision:selectedYear.revision};
    for (const field of ["name","start_date","end_date"]) {
      if (yearDraft[field]!==selectedYear[field]) changes[field]=yearDraft[field];
    }
    if (Object.keys(changes).length===1) {setYearDraft(null);return;}
    const updated=await run(()=>calendarRequest(prefix+"years/"+selectedYear.id,changes,"PATCH"),
      {refreshYears:true});
    if (updated) {setYearDraft(null);setMessage("Année renommée / dates mises à jour partout dans YEM, sans changer ses dossiers.")}
  }

  async function savePeriod(e) {
    e.preventDefault();
    const existing=periodDraft.id;
    const body=existing
      ? {revision:periodDraft.revision,name:periodDraft.name,
         start_date:periodDraft.start_date,end_date:periodDraft.end_date}
      : {code:periodDraft.code,name:periodDraft.name,year:selectedYear.id,
         start_date:periodDraft.start_date,end_date:periodDraft.end_date};
    const result=await run(()=>calendarRequest(prefix+"periods"+
      (existing?"/"+existing:""),body,existing?"PATCH":"POST"));
    if(result){setPeriodDraft(null);setMessage(existing?"Période mise à jour.":"Période ajoutée.")}
  }

  async function togglePeriod(item) {
    const result=await run(()=>calendarRequest(prefix+"periods/"+item.id,{
      revision:item.revision,active:!item.active,
    },"PATCH"));
    if(result)setMessage(result.active?"Période réactivée.":"Période archivée.");
  }

  async function saveEvent(e) {
    e.preventDefault();
    const existing=eventDraft.id;
    const {id,revision,year,...fields}=eventDraft;
    const body=existing?{revision,...fields}:{year:selectedYear.id,...fields};
    const result=await run(()=>calendarRequest(prefix+"pedagogical-calendar"+
      (existing?"/"+existing:""),body,existing?"PATCH":"POST"));
    if(result){setEventDraft(null);setMessage(existing?"Événement modifié.":"Événement ajouté au calendrier.")}
  }

  async function toggleEvent(item) {
    const result=await run(()=>calendarRequest(prefix+"pedagogical-calendar/"+item.id,
      {revision:item.revision,active:!item.active},"PATCH"));
    if(result)setMessage(result.active?"Événement réactivé.":"Événement archivé.");
  }

  const events=catalog?.events||[];
  const periods=snapshot?.periods||[];
  return <>
    <PageHeader title="Calendrier pédagogique"
      subtitle="Année en cours, périodes, vacances, évaluations et échéances de l’établissement" banner={false}/>
    <div className="yd-real-body">
      {error&&<p role="alert" className="pc-alert">{error}</p>}
      {message&&<p role="status" className="pc-alert">{message}</p>}
      {loading&&<p role="status">Chargement du calendrier pédagogique…</p>}
      {!loading&&!selectedYear&&<Card title="Créer votre première année scolaire" icon="calendar">
        <p>Chaque classe, inscription et bilan appartient à une année. Commencez par une année avec ses dates réelles.</p>
        <AnnualWorkspace schoolId={schoolId} yearId="" onYearChange={onWorkingYearChange}
          onPrepared={()=>{onYearsUpdated?.();setVersion(v=>v+1);}}/>
      </Card>}
      {!loading&&selectedYear&&<>
        <Card title="Année scolaire et statut" icon="calendar">
          <div className="yf-inline-form wrap">
            <label className="field">Année à consulter
              <select aria-label="Année du calendrier" value={selectedYear.id}
                onChange={e=>onWorkingYearChange?.(e.target.value)}>
                {snapshot.years.map(year=><option key={year.id} value={year.id}>
                  {year.name} · {yearState[year.status]||"Archivée"}
                </option>)}
              </select>
            </label>
            <p><strong>{yearState[selectedYear.status]||"Archivée"}</strong>
              {" · "}{dateLabel(selectedYear.start_date)} — {dateLabel(selectedYear.end_date)}</p>
          </div>
          <p>Code interne stable : <code>{selectedYear.code}</code>. Le nom affiché peut être corrigé sans changer les dossiers ni les références de l'année.</p>
          {canEdit&&!yearDraft&&<button type="button" disabled={busy}
            onClick={editingYear}>Corriger le nom ou les dates de cette année</button>}
          {yearDraft&&<form className="yf-form" onSubmit={saveYear}>
            <div className="yf-grid">
              <label className="field">Nom de l'année scolaire
                <input required maxLength={120} value={yearDraft.name}
                  onChange={e=>setYearDraft(d=>({...d,name:e.target.value}))}/>
              </label>
              <label className="field">Début de l'année
                <input type="date" required value={yearDraft.start_date}
                  onChange={e=>setYearDraft(d=>({...d,start_date:e.target.value}))}/>
              </label>
              <label className="field">Fin de l'année
                <input type="date" required value={yearDraft.end_date}
                  onChange={e=>setYearDraft(d=>({...d,end_date:e.target.value}))}/>
              </label>
            </div>
            <p className="hint">Les dates d'une année contenant des inscriptions ou des périodes peuvent être verrouillées pour protéger l'historique. Le nom reste modifiable tant que l'année n'est pas clôturée.</p>
            <div className="yf-inline-form">
              <button type="submit" disabled={busy}>Enregistrer cette année</button>
              <button type="button" disabled={busy} onClick={()=>setYearDraft(null)}>Annuler</button>
            </div>
          </form>}
          {!canEdit&&<p className="hint">Année clôturée ou droits insuffisants : consultation uniquement. Les archives ne sont jamais modifiées rétroactivement.</p>}
        </Card>

        <Card title="Périodes pédagogiques" icon="calendar">
          <p>Trimestres, semestres ou périodes personnalisées. Une année peut avoir son propre découpage ; les périodes actives ne doivent pas se chevaucher.</p>
          {periods.length? <div style={{overflowX:"auto"}}><table className="xs">
            <thead><tr><th>Période</th><th>Dates</th><th>Statut</th><th>Actions</th></tr></thead>
            <tbody>{periods.map(item=><tr key={item.id}>
              <td><strong>{item.name}</strong></td>
              <td>{dateLabel(item.start_date)} — {dateLabel(item.end_date)}</td>
              <td>{item.active?"Active":"Archivée"}</td>
              <td>{canEdit&&<>
                <button type="button" className="yf-link" disabled={busy} onClick={()=>{setPeriodDraft({...item});setEventDraft(null);}}>Modifier</button>{" "}
                <button type="button" className="yf-link" disabled={busy} onClick={()=>togglePeriod(item)}>
                  {item.active?"Archiver":"Réactiver"}
                </button>
              </>}</td>
            </tr>)}</tbody>
          </table></div>:<p className="hint">Aucune période créée. Vous pouvez commencer par le premier trimestre.</p>}
          {canEdit&&<div className="yf-inline-form wrap">
            <button type="button" disabled={busy} onClick={()=>{setPeriodDraft({...blankPeriod,
              start_date:selectedYear.start_date,end_date:selectedYear.end_date});setEventDraft(null);}}>
              Ajouter une période
            </button>
          </div>}
          {canEdit&&reference2026&&<details className="yf-details">
            <summary>Référence du Gabon 2026–2027 : proposer un trimestre</summary>
            <p>Dates indicatives issues du calendrier national. Vérifiez les éventuelles décisions de réaménagement et adaptez-les avant enregistrement.</p>
            <div className="yf-inline-form wrap">{ga2026Periods.map(item=><button type="button" key={item.code}
              disabled={busy} onClick={()=>{setPeriodDraft({...item});setEventDraft(null);}}>
              {item.name} : {dateLabel(item.start_date)} — {dateLabel(item.end_date)}
            </button>)}</div>
            <a href={officialSource} target="_blank" rel="noreferrer">Consulter la source du calendrier gabonais</a>
          </details>}
          {canEdit&&periodDraft&&<form className="yf-form" onSubmit={savePeriod}>
            <h4>{periodDraft.id?"Modifier cette période":"Nouvelle période"}</h4>
            <div className="yf-grid">
              <label className="field">Nom de la période
                <input required maxLength={120} value={periodDraft.name}
                  onChange={e=>setPeriodDraft(d=>({...d,name:e.target.value}))}/>
              </label>
              {!periodDraft.id&&<label className="field">Code de la période
                <input required maxLength={40} pattern="[a-z0-9][a-z0-9_-]*" value={periodDraft.code}
                  placeholder="t1" onChange={e=>setPeriodDraft(d=>({...d,code:e.target.value}))}/>
              </label>}
              <label className="field">Début
                <input type="date" required value={periodDraft.start_date}
                  onChange={e=>setPeriodDraft(d=>({...d,start_date:e.target.value}))}/>
              </label>
              <label className="field">Fin
                <input type="date" required value={periodDraft.end_date}
                  onChange={e=>setPeriodDraft(d=>({...d,end_date:e.target.value}))}/>
              </label>
            </div>
            <div className="yf-inline-form">
              <button type="submit" disabled={busy}>Enregistrer la période</button>
              <button type="button" disabled={busy} onClick={()=>setPeriodDraft(null)}>Annuler</button>
            </div>
          </form>}
        </Card>

        <Card title="Échéances, congés et examens" icon="calendar">
          <p>Ajoutez les rentrées, vacances, arrêts des notes, remises de bulletins, réunions et examens. Ces repères n'activent pas automatiquement une évaluation ou une clôture comptable.</p>
          {events.length?<div style={{overflowX:"auto"}}><table className="xs">
            <thead><tr><th>Date</th><th>Événement</th><th>Cycle</th><th>Statut</th><th>Actions</th></tr></thead>
            <tbody>{events.map(item=><tr key={item.id}>
              <td>{dateLabel(item.start_date)}{item.end_date!==item.start_date?
                " — "+dateLabel(item.end_date):""}</td>
              <td><strong>{item.title}</strong><br/><small>{kindLabel(catalog.kinds,item.kind)}
                {" · "}{item.source==="official"?"Référence nationale":"Établissement"}</small>
                {item.description&&<p>{item.description}</p>}</td>
              <td>{kindLabel(catalog.scopes,item.scope)}</td>
              <td>{item.active?"Actif":"Archivé"}</td>
              <td>{canManage&&<>
                <button type="button" className="yf-link" disabled={busy}
                  onClick={()=>{setEventDraft({...item});setPeriodDraft(null);}}>Modifier</button>{" "}
                <button type="button" className="yf-link" disabled={busy} onClick={()=>toggleEvent(item)}>
                  {item.active?"Archiver":"Réactiver"}</button>
              </>}</td>
            </tr>)}</tbody>
          </table></div>:<p className="hint">Aucun événement ajouté pour cette année.</p>}
          {canManage&&<button type="button" disabled={busy}
            onClick={()=>{setEventDraft({...blankEvent,start_date:selectedYear.start_date,
              end_date:selectedYear.start_date});setPeriodDraft(null);}}>Ajouter un événement</button>}
          {canManage&&reference2026&&<details className="yf-details">
            <summary>Référence nationale 2026–2027 : pré-remplir un repère</summary>
            <p>Ces propositions ne sont pas enregistrées tant que vous ne les confirmez pas.</p>
            <div className="yf-inline-form wrap">{ga2026Events.map(item=><button type="button"
              key={item.title} disabled={busy} onClick={()=>{setEventDraft({
                ...blankEvent,...item,source:"official",source_url:officialSource,
              });setPeriodDraft(null);}}>
              {item.title} · {dateLabel(item.start_date)}
            </button>)}</div>
          </details>}
          {canManage&&eventDraft&&<form className="yf-form" onSubmit={saveEvent}>
            <h4>{eventDraft.id?"Modifier cet événement":"Nouvel événement pédagogique"}</h4>
            <div className="yf-grid">
              <label className="field">Intitulé
                <input required maxLength={160} value={eventDraft.title}
                  onChange={e=>setEventDraft(d=>({...d,title:e.target.value}))}/>
              </label>
              <label className="field">Catégorie
                <select value={eventDraft.kind} onChange={e=>setEventDraft(d=>({...d,kind:e.target.value}))}>
                  {catalog.kinds.map(kind=><option key={kind.code} value={kind.code}>{kind.label}</option>)}
                </select>
              </label>
              <label className="field">Cycles concernés
                <select value={eventDraft.scope} onChange={e=>setEventDraft(d=>({...d,scope:e.target.value}))}>
                  {catalog.scopes.map(scope=><option key={scope.code} value={scope.code}>{scope.label}</option>)}
                </select>
              </label>
              <label className="field">Début
                <input required type="date" value={eventDraft.start_date}
                  onChange={e=>setEventDraft(d=>({...d,start_date:e.target.value}))}/>
              </label>
              <label className="field">Fin
                <input required type="date" value={eventDraft.end_date}
                  onChange={e=>setEventDraft(d=>({...d,end_date:e.target.value}))}/>
              </label>
              <label className="field">Origine du repère
                <select value={eventDraft.source} onChange={e=>setEventDraft(d=>({...d,source:e.target.value}))}>
                  <option value="school">Établissement</option>
                  <option value="official">Référence nationale (à vérifier)</option>
                </select>
              </label>
              <label className="field">Lien vers la source, facultatif
                <input type="url" maxLength={500} value={eventDraft.source_url}
                  onChange={e=>setEventDraft(d=>({...d,source_url:e.target.value}))}/>
              </label>
            </div>
            <label className="field">Précisions pédagogiques
              <textarea maxLength={500} value={eventDraft.description}
                onChange={e=>setEventDraft(d=>({...d,description:e.target.value}))}/>
            </label>
            <div className="yf-inline-form">
              <button type="submit" disabled={busy}>Enregistrer l'événement</button>
              <button type="button" disabled={busy} onClick={()=>setEventDraft(null)}>Annuler</button>
            </div>
          </form>}
        </Card>

        <details className="yf-details">
          <summary>Préparation de l'année suivante, activation et bilan des années précédentes</summary>
          <AnnualWorkspace schoolId={schoolId} yearId={selectedYear.id}
            onYearChange={onWorkingYearChange}
            onPrepared={()=>{onYearsUpdated?.();setVersion(v=>v+1);}}/>
        </details>
      </>}
    </div>
  </>;
}
