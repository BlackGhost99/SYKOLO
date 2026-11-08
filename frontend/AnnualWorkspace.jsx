import React, {useEffect, useState} from "react";
import {schoolRequest} from "./SchoolSettings.jsx";

const empty = {code:"",name:"",start_date:"",end_date:"",source_year:"",copy_classes:true};
const stateLabel = year => ({
  preparation:"En préparation",current:"En cours",closed:"Clôturée",
})[year?.status] || (year?.active ? "À vérifier" : "Archivée");
const yearlyStats = [
  ["classes","Classes"],["periods","Périodes"],["enrollments","Inscriptions"],
  ["staff_assignments","Affectations du personnel"],["assessments","Évaluations"],
  ["published_reports","Bulletins publiés"],
];

/** An annual workspace, not an independent application/database per year. */
export default function AnnualWorkspace({schoolId,yearId,onYearChange,onPrepared}) {
  const [data,setData] = useState(null);
  const [error,setError] = useState("");
  const [busy,setBusy] = useState(false);
  const [preparing,setPreparing] = useState(false);
  const [activating,setActivating] = useState(false);
  const [activationReason,setActivationReason] = useState("");
  const [draft,setDraft] = useState(empty);
  const [message,setMessage] = useState("");
  const prefix = "schools/"+schoolId+"/academic/";
  async function load(requested=yearId) {
    const snapshot=await schoolRequest(prefix+"annual-snapshot"+(requested?"?year="+encodeURIComponent(requested):""));
    setData(snapshot);
    if(snapshot.year?.id && snapshot.year.id!==requested) onYearChange(snapshot.year.id);
    return snapshot;
  }
  useEffect(()=>{
    let active=true;
    setData(null);setError("");
    schoolRequest(prefix+"annual-snapshot"+(yearId?"?year="+encodeURIComponent(yearId):""))
      .then(result=>{
        if(!active)return;
        setData(result);
        if(result.year?.id && !yearId)onYearChange(result.year.id);
      })
      .catch(e=>{if(active)setError(e.message)});
    return()=>{active=false};
  },[schoolId,yearId]);

  function startPreparation() {
    const year=data?.year;
    const match=/^(\d{4})-(\d{4})$/.exec(year?.code||"");
    const suggested=match?`${Number(match[1])+1}-${Number(match[2])+1}`:"";
    const shift=iso=>iso?iso.replace(/^\d{4}/,part=>String(Number(part)+1)):"";
    setDraft({
      code:suggested,name:suggested,
      start_date:shift(year?.start_date),end_date:shift(year?.end_date),
      source_year:year?.id||"",copy_classes:Boolean(year?.id),
    });
    setMessage("");setPreparing(true);
  }

  async function submit(event) {
    event.preventDefault();setBusy(true);setMessage("");setError("");
    try {
      const payload={...draft,source_year:draft.source_year||null};
      if(!payload.source_year)payload.copy_classes=false;
      const result=await schoolRequest(prefix+"prepare-year",payload);
      setPreparing(false);
      onYearChange(result.year.id);
      await onPrepared?.();
      await load(result.year.id);
      setMessage(`${result.year.name} prête : ${result.classes_copied} classe(s) reprises. Aucun élève, bulletin, paiement ou emploi du temps copié.`);
    }catch(e){setError(e.message)}
    finally{setBusy(false)}
  }

  async function activate(event) {
    event.preventDefault();
    if (!data?.year) return;
    setBusy(true);setError("");setMessage("");
    try {
      const result=await schoolRequest(prefix+"years/"+data.year.id+"/activate",{
        revision:data.year.revision,reason:activationReason.trim(),
      });
      setActivating(false);setActivationReason("");
      await onPrepared?.();
      await load(result.year.id);
      setMessage(result.message);
    }catch(e){setError(e.message)}
    finally{setBusy(false)}
  }

  return <div aria-label="Espace par année scolaire">
    <h3>Année scolaire de travail</h3>
    <p className="hint">Chaque année conserve ses classes, inscriptions, affectations, périodes, évaluations et bulletins. Les anciennes années restent consultables. Une seule année peut être déclarée « En cours » dans l'établissement.</p>
    {error&&<p role="alert">{error}</p>}
    {!data&&!error&&<p>Chargement du calendrier scolaire…</p>}
    {data&&<>
      {data.years.length>0?<label className="field">Consulter l'année
        <select aria-label="Année scolaire de travail" value={yearId||data.year?.id||""}
          onChange={e=>{onYearChange(e.target.value);setMessage("");setPreparing(false)}}>
          {data.years.map(y=><option value={y.id} key={y.id}>{y.name} · {stateLabel(y)}</option>)}
        </select>
      </label>:<p role="status">Aucune année scolaire enregistrée. Préparez la première année ci-dessous.</p>}
      {data.year&&<>
        <p><strong>{data.year.name}</strong> · du {data.year.start_date} au {data.year.end_date} · {stateLabel(data.year)}</p>
        <div className="two" aria-label="Bilan de l'année">{yearlyStats.map(([key,label])=>
          <div key={key} className="card" style={{padding:12,margin:0}}>
            <strong>{data.stats[key]===null?"—":data.stats[key]??0}</strong> · {label}
          </div>)}</div>
        <h4>Classes de {data.year.name}</h4>
        {data.classes.length?<div style={{overflowX:"auto"}}><table>
          <thead><tr><th>Classe</th><th>Niveau</th><th>Inscrits</th><th>Personnel</th><th>Bulletins</th></tr></thead>
          <tbody>{data.classes.map(c=><tr key={c.id}>
            <td>{c.name}{c.active?"":" (archivée)"}</td><td>{c.level} · {c.cycle}</td>
            <td>{c.enrolled??"—"}</td>
            <td>{Array.isArray(c.team)?(c.team.length?c.team.map((person,i)=>
              <div key={person.staff_id+":"+person.duty}>{person.name} · {person.duty}</div>):"Aucune affectation"):(c.staff_assignments??"—")}</td>
            <td>{c.published_reports??"—"}</td>
          </tr>)}</tbody>
        </table></div>:<p className="hint">Aucune classe pour cette année. Ajoutez-en une dans « Classes ».</p>}
        <h4>Calendrier des périodes</h4>
        {data.periods.length?<ul>{data.periods.map(p=><li key={p.id}>{p.name} · {p.start_date} → {p.end_date}{p.active?"":" (archivée)"}</li>)}</ul>
          :<p className="hint">Aucune période configurée. Utilisez « Périodes » pour ajouter trimestres, semestres ou autres divisions de cette année.</p>}
      </>}
      {data.can_activate_year&&!activating&&<button type="button" disabled={busy} onClick={()=>{setActivationReason("");setActivating(true);setError("");}}>
        Activer cette année scolaire
      </button>}
      {data.can_activate_year&&activating&&<form className="card" onSubmit={activate} style={{marginTop:12}}>
        <h4>Confirmation de l'activation</h4>
        <p className="hint">L'activation désigne cette année comme année de référence de l'établissement. Elle n'efface aucune donnée. Une seule année peut être en cours.</p>
        <label className="field">Motif de l'activation
          <textarea required minLength={8} maxLength={300} value={activationReason}
            onChange={e=>setActivationReason(e.target.value)}
            placeholder="Exemple : ouverture officielle de l'année 2026-2027"/>
        </label>
        <button type="submit" disabled={busy||activationReason.trim().length<8}>{busy?"Activation…":"Confirmer l'activation"}</button>
        <button type="button" disabled={busy} onClick={()=>setActivating(false)}>Annuler</button>
      </form>}
      {data.year?.status==="current"&&<p className="hint">La clôture n'est pas encore accessible : toutes les opérations de notes, paiements, absences et bulletins devront d'abord être verrouillées côté serveur.</p>}
      {data.year?.status==="closed"&&<p className="hint">Archive consultable. Les corrections officielles devront être historisées et autorisées.</p>}
      {data.can_prepare_year&&!preparing&&<button type="button" onClick={startPreparation}>Préparer une nouvelle année scolaire</button>}
      {data.can_prepare_year&&preparing&&<form onSubmit={submit} className="card" style={{marginTop:12}}>
        <h4>Préparer la nouvelle année</h4>
        <p className="hint">Les dates proposées sont indicatives : ajustez-les au calendrier réel de l'établissement. Seule la structure des classes peut être recopiée.</p>
        <div className="two">
          <label className="field">Code d'année
            <input required pattern="[a-z0-9][a-z0-9_-]*" maxLength={40} value={draft.code} placeholder="2027-2028" onChange={e=>setDraft(old=>({...old,code:e.target.value}))}/>
          </label>
          <label className="field">Nom d'année
            <input required maxLength={120} value={draft.name} onChange={e=>setDraft(old=>({...old,name:e.target.value}))}/>
          </label>
          <label className="field">Début de l'année
            <input type="date" required value={draft.start_date} onChange={e=>setDraft(old=>({...old,start_date:e.target.value}))}/>
          </label>
          <label className="field">Fin de l'année
            <input type="date" required min={draft.start_date||undefined} value={draft.end_date} onChange={e=>setDraft(old=>({...old,end_date:e.target.value}))}/>
          </label>
          {data.years.length>0&&<label className="field">Année de référence
            <select value={draft.source_year} onChange={e=>setDraft(old=>({...old,source_year:e.target.value,copy_classes:!!e.target.value}))}>
              <option value="">Aucune référence (année vierge)</option>
              {data.years.map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
            </select>
          </label>}
        </div>
        {draft.source_year&&<label style={{display:"flex",alignItems:"center",gap:8}}>
          <input type="checkbox" checked={draft.copy_classes} onChange={e=>setDraft(old=>({...old,copy_classes:e.target.checked}))}/>
          Reprendre les classes actives de l'année de référence (noms, niveaux et capacités)
        </label>}
        <p className="hint">Les élèves, enseignants affectés, notes, bulletins, frais, paiements et périodes ne seront jamais reproduits automatiquement.</p>
        <button type="submit" disabled={busy}>{busy?"Préparation…":"Créer l'année scolaire"}</button>
        <button type="button" disabled={busy} onClick={()=>setPreparing(false)}>Annuler</button>
      </form>}
      {message&&<p role="status">{message}</p>}
    </>}
  </div>;
}
