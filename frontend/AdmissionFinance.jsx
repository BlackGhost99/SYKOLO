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
  const grant=application.finance?.scholarship;
  const amounts=application.finance?.amounts||{};
  const [enabled,setEnabled]=useState(Boolean(grant));
  const [coverage,setCoverage]=useState(grant?.coverage||"all");
  const [type,setType]=useState("total");
  const [calculation,setCalculation]=useState("percent");
  const [percent,setPercent]=useState(50);
  const [fixed,setFixed]=useState("");
  const [reference,setReference]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  useEffect(()=>{
    setEnabled(Boolean(grant));
    setCoverage(grant?.coverage||"all");
    setType(grant?.calculation==="fixed"||((grant?.percentage||100)<100)?"partial":"total");
    setCalculation(grant?.calculation||"percent");
    setPercent(grant?.percentage<100?grant.percentage:50);
    setFixed(grant?.fixed_amount_xaf||"");
    setReference(grant?.reference||"");
    setMessage("");
  },[application.id,grant?.revision,grant?.reference]);
  const editable=canApprove&&["submitted","review","accepted"].includes(application.status);
  const grossAdmission=Number(amounts.admission_gross_xaf||0);
  const grossTuition=Number(amounts.tuition_gross_xaf||0);
  const eligible=(coverage!=="tuition"?grossAdmission:0)+(coverage!=="admission"?grossTuition:0);
  const desired=type==="total"?eligible:calculation==="fixed"
    ?Math.min(eligible,Math.max(0,Number(fixed)||0))
    :Math.round(eligible*Math.min(100,Math.max(0,Number(percent)||0))/100);
  const predictedAdmission=coverage==="tuition"?0:type==="total"?grossAdmission:
    calculation==="fixed"?Math.min(grossAdmission,desired):Math.round(grossAdmission*Number(percent||0)/100);
  const predictedTuition=coverage==="admission"?0:type==="total"?grossTuition:
    calculation==="fixed"?Math.min(grossTuition,Math.max(0,desired-predictedAdmission)):
      Math.round(grossTuition*Number(percent||0)/100);
  const active=Boolean(grant);
  const coveredAdmission=active?Number(amounts.admission_scholarship_xaf||0):
    enabled?predictedAdmission:0;
  const coveredTuition=active?Number(amounts.tuition_scholarship_xaf||0):
    enabled?predictedTuition:0;
  const format=n=>new Intl.NumberFormat("fr-FR").format(n)+" FCFA";
  return <section className="card" aria-label="Bourse gouvernementale">
    <h3>Bourse et reste à payer</h3>
    <p className="hint">La direction vérifie la décision de bourse. Le caissier ne crée aucun faux reçu pour la part prise en charge.</p>
    {editable&&<label className="field"><input type="checkbox" checked={enabled} disabled={busy||active}
        onChange={e=>setEnabled(e.target.checked)}/> Élève boursier</label>}
    {active&&<p role="status"><strong>Bourse vérifiée</strong> · référence {grant.reference}. Pour la retirer, utilisez l'annulation documentée ci-dessous.</p>}
    {enabled&&editable&&!active&&<>
      <label className="field">Type de bourse
        <select value={type} disabled={busy} onChange={e=>setType(e.target.value)}>
          <option value="total">Totale — 100 % des frais concernés</option>
          <option value="partial">Partielle — prise en charge limitée</option>
        </select>
      </label>
      <label className="field">Prise en charge
        <select value={coverage} disabled={busy} onChange={e=>setCoverage(e.target.value)}>
          <option value="all">Tous les frais scolaires</option>
          <option value="admission">Frais d'inscription uniquement</option>
          <option value="tuition">Frais de scolarité uniquement</option>
        </select>
      </label>
      {type==="partial"&&<>
        <label className="field">Mode de calcul
          <select value={calculation} disabled={busy} onChange={e=>setCalculation(e.target.value)}>
            <option value="percent">Pourcentage</option>
            <option value="fixed">Montant fixe en FCFA</option>
          </select>
        </label>
        {calculation==="percent"?
          <label className="field">Pourcentage couvert
            <input type="number" min="1" max="99" required disabled={busy} value={percent}
              onChange={e=>setPercent(e.target.value)}/>
          </label>:
          <label className="field">Montant couvert (FCFA)
            <input type="number" min="1" max="100000000" required disabled={busy} value={fixed}
              onChange={e=>setFixed(e.target.value)}/>
          </label>}
      </>}
    </>}
    <div aria-label="Calcul de la bourse" className="yp-settings">
      <p>Frais d'inscription : <strong>{format(grossAdmission)}</strong> · Bourse : <strong>{format(coveredAdmission)}</strong></p>
      <p>Scolarité prévisionnelle : <strong>{format(grossTuition)}</strong> · Bourse : <strong>{format(coveredTuition)}</strong></p>
      <p><strong>Reste à payer à l'inscription : {format(Math.max(0,grossAdmission-coveredAdmission))}</strong></p>
      <p><strong>Reste annuel prévisionnel : {format(Math.max(0,grossAdmission+grossTuition-coveredAdmission-coveredTuition))}</strong></p>
      <p className="hint">La scolarité suit ses échéances après l'inscription ; il n'est pas nécessaire de payer toute l'année à l'avance.</p>
    </div>
    {editable&&(enabled||active)&&<>
      <label className="field">Référence de la décision officielle
        <input value={reference} disabled={busy} maxLength={180}
          onChange={e=>setReference(e.target.value)}
          placeholder="N° de notification / attestation de bourse"/>
      </label>
      <div className="actions">
        {enabled&&!active&&<button type="button" disabled={busy||reference.trim().length<5||
          (type==="partial"&&(calculation==="percent"?!(Number(percent)>0&&Number(percent)<100):
            !(Number(fixed)>0&&Number(fixed)<=eligible)))}
          onClick={async()=>{
            setBusy(true);setMessage("");
            try{
              await financeApi("schools/"+schoolId+"/admissions/"+application.id+"/scholarship",{
                action:"approve",coverage,reference:reference.trim(),revision:grant?.revision||0,
                calculation:type==="total"?"percent":calculation,
                percentage:type==="total"?100:calculation==="percent"?Number(percent):100,
                fixed_amount_xaf:type==="partial"&&calculation==="fixed"?Number(fixed):null,
              });
              setMessage("Bourse vérifiée. Le dossier financier affiche le solde réellement exigible.");
              await onUpdated();
            }catch(e){setMessage(e.message)}finally{setBusy(false)}
          }}>Valider la bourse d'État</button>}
        {active&&<button type="button" disabled={busy||reference.trim().length<5}
          onClick={async()=>{
            setBusy(true);setMessage("");
            try{
              await financeApi("schools/"+schoolId+"/admissions/"+application.id+"/scholarship",{
                action:"revoke",coverage:grant.coverage,reference:reference.trim(),
                revision:grant.revision,
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
