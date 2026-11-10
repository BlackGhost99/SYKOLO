import React, {useEffect, useState} from "react";

async function financeApi(path, data){
  if(data!==undefined){
    const csrf=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
    if(!csrf.ok)throw Error("Session expirée.");
  }
  const token=document.cookie.split("; ").find(c=>c.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{
    credentials:"same-origin",
    method:data===undefined?"GET":"POST",
    ...(data===undefined?{}:{headers:{"Content-Type":"application/json","X-CSRFToken":token},
      body:JSON.stringify(data)}),
  });
  const result=await response.json();
  if(!response.ok)throw Error(result.error||"Opération refusée.");
  return result;
}

export function FinancePolicyEditor({schoolId,year,level,canManage}){
  const [policy,setPolicy]=useState(null);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [required,setRequired]=useState(true);
  const [scholarships,setScholarships]=useState(true);
  useEffect(()=>{
    if(!year){setPolicy(null);return;}
    let active=true;
    setPolicy(null);setMessage("");
    const params=new URLSearchParams({year,...(level?{level}:{})});
    financeApi("schools/"+schoolId+"/admissions/finance-policy?"+params).then(data=>{
      if(!active)return;
      setPolicy(data);setRequired(data.effective.require_payment);
      setScholarships(data.effective.allow_government_scholarship);
    }).catch(e=>{if(active)setMessage(e.message)});
    return()=>{active=false;};
  },[schoolId,year,level]);
  if(!year)return null;
  return <section className="card" aria-label="Conditions financières d'inscription">
    <h3>Paiement obligatoire et bourses de l'État</h3>
    <p className="hint">Par défaut, une école privée n'inscrit définitivement un élève
      qu'après confirmation des frais d'inscription. Une bourse validée peut remplacer ce règlement.
      Un paiement fictif n'est jamais une recette réelle.</p>
    {!policy?<p role="status">{message||"Lecture des règles financières…"}</p>:<>
      <label className="field"><input type="checkbox" checked={required}
        disabled={!canManage||busy} onChange={e=>setRequired(e.target.checked)}/>
        Bloquer l'inscription officielle jusqu'au paiement des frais</label>
      <label className="field"><input type="checkbox" checked={scholarships}
        disabled={!canManage||busy} onChange={e=>setScholarships(e.target.checked)}/>
        Autoriser les bourses gouvernementales vérifiées</label>
      <p className="hint">{level?"Réglage pour le niveau choisi":"Réglage par défaut pour l'année scolaire"}.
        {policy.effective.configured?" Règle configurée.":" Valeurs par défaut."}</p>
      {canManage&&<button type="button" disabled={busy} onClick={async()=>{
        setBusy(true);setMessage("");
        try{
          const saved=await financeApi("schools/"+schoolId+"/admissions/finance-policy",{
            year,level:level||null,revision:policy.revision,
            require_payment:required,allow_government_scholarship:scholarships,
          });
          setPolicy({...policy,revision:saved.revision,effective:saved.effective});
          setMessage("Règle de paiement et d'exonération enregistrée.");
        }catch(e){setMessage(e.message)}finally{setBusy(false)}
      }}>Enregistrer ces règles</button>}
      {message&&<p role="status">{message}</p>}
    </>}
  </section>;
}

export function GovernmentScholarshipPanel({schoolId,application,canApprove,onUpdated}){
  const [coverage,setCoverage]=useState("all");
  const [reference,setReference]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const scholarship=application.finance?.scholarship;
  const policy=application.finance;
  useEffect(()=>{
    setCoverage(scholarship?.coverage||"all");
    setReference(scholarship?.reference||"");
    setMessage("");
  },[application.id,scholarship?.coverage,scholarship?.reference]);
  const canChange=canApprove&&["submitted","review","accepted"].includes(application.status);
  const blocked=policy?.blocker;
  return <section className="card" aria-label="Bourse gouvernementale">
    <h3>Frais d'inscription et bourse</h3>
    {scholarship?
      <p><strong>Boursier de l'État</strong> · {scholarship.coverage==="all"?
        "Prise en charge de tous les frais":"Frais d'inscription uniquement"}.
        Référence : {scholarship.reference}.</p>:
      <p>{policy?.require_payment?"Paiement obligatoire avant inscription.":"Paiement non bloquant selon les paramètres."}
        {blocked?" "+blocked:" Dossier prêt sur le plan financier."}</p>}
    {canChange && <>
      <label className="field">Prise en charge
        <select value={coverage} disabled={busy} onChange={e=>setCoverage(e.target.value)}>
          <option value="all">Tous les frais (inscription et scolarité)</option>
          <option value="admission">Frais d'inscription uniquement</option>
        </select>
      </label>
      <label className="field">Référence de la décision officielle
        <input value={reference} disabled={busy} maxLength={180}
          onChange={e=>setReference(e.target.value)}
          placeholder="N° de notification / attestation de bourse"/>
      </label>
      <div className="actions">
        <button type="button" disabled={busy||reference.trim().length<5}
          onClick={async()=>{
            setBusy(true);setMessage("");
            try{
              await financeApi("schools/"+schoolId+"/admissions/"+application.id+"/scholarship",{
                action:"approve",coverage,reference:reference.trim(),
                revision:scholarship?.revision||0,
              });
              setMessage("Bourse vérifiée et enregistrée. Aucun paiement fictif créé.");
              await onUpdated();
            }catch(e){setMessage(e.message)}finally{setBusy(false)}
          }}>Valider la bourse d'État</button>
        {scholarship&&<button type="button" disabled={busy||reference.trim().length<5}
          onClick={async()=>{
            setBusy(true);setMessage("");
            try{
              await financeApi("schools/"+schoolId+"/admissions/"+application.id+"/scholarship",{
                action:"revoke",coverage,reference:reference.trim(),revision:scholarship.revision,
              });
              setMessage("Bourse révoquée avant inscription.");
              await onUpdated();
            }catch(e){setMessage(e.message)}finally{setBusy(false)}
          }}>Annuler la décision de bourse</button>}
      </div>
    </>}
    {message&&<p role="status">{message}</p>}
  </section>;
}
