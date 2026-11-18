import CommercialSimulator from "./CommercialSimulator.jsx";
import React, {useEffect, useRef, useState} from "react";
import SubscriptionDocuments from "./SubscriptionDocuments.jsx";
import CommercialAdjustments from "./CommercialAdjustments.jsx";
import CommercialAccess from "./CommercialAccess.jsx";
import "./commercial-estimate.css";

const money = value => new Intl.NumberFormat("fr-GA").format(value) + " FCFA";
const methods = [["especes","Espèces"],["mobile_money","Mobile Money"],["virement","Virement déclaré"],["autre","Autre"]];
export default function PlatformSubscriptions({schoolId, api, tariffRevision=0}) {
  const [years,setYears]=useState([]);
  const [year,setYear]=useState("");
  const [data,setData]=useState(null);
  const [period,setPeriod]=useState("annuel");
  const [activate,setActivate]=useState(false);
  const [discount,setDiscount]=useState("0");
  const [includeSetup,setIncludeSetup]=useState(false);
  const [reload,setReload]=useState(0);
  const [reason,setReason]=useState("");
  const [reference,setReference]=useState("");
  const [amount,setAmount]=useState("");
  const [method,setMethod]=useState("especes");
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const pending=useRef(false);
  const quoteGeneration=useRef(0);
  const path="platform/schools/"+schoolId+"/subscriptions";
  function assign(value) {
    setData(value);
    if(value.counts){setPeriod("annuel");setDiscount("0");setIncludeSetup(false);}
  }
  useEffect(()=>{
    let alive=true;
    api(path).then(value=>{
      if(!alive)return;
      setYears(value.years);
      setYear(value.suggested_year||value.years[0]?.id||"");
      if(!value.years.length)setLoading(false);
    }).catch(err=>{if(alive){setMessage(err.message);setLoading(false);}});
    return()=>{alive=false;};
  },[path,api]);
  useEffect(()=>{
    let alive=true,reading=false;
    setData(null);setReason("");setReference("");setAmount("");setMessage("");setActivate(false);
    setPeriod("annuel");setDiscount("0");setIncludeSetup(false);
    if(!year)return;
    setLoading(true);
    async function refresh(force=false){
      if(!alive||reading||pending.current||(!force&&document.hidden))return;
      reading=true;const version=quoteGeneration.current;
      try{
        const value=await api(path,{action:"quote",year_id:year});
        if(alive&&version===quoteGeneration.current)setData(value);
      }catch(err){if(alive&&version===quoteGeneration.current){setData(null);setMessage(err.message);}}
      finally{reading=false;if(alive)setLoading(false);}
    }
    const poll=()=>refresh();
    refresh(true);
    const timer=window.setInterval(poll,30000);
    window.addEventListener("focus",poll);document.addEventListener("visibilitychange",poll);
    return()=>{alive=false;window.clearInterval(timer);window.removeEventListener("focus",poll);document.removeEventListener("visibilitychange",poll);};
  },[path,year,api,reload,tariffRevision]);
  async function submit(action,values) {
    if(pending.current||(action==="issue"&&activationBlocker))return;
    pending.current=true;quoteGeneration.current++;setBusy(true);setMessage("");
    try {
      const operationReason=action==="issue"&&!reason.trim()&&Number(discount)===0?"Activation du service payant sans remise exceptionnelle":reason.trim();
      assign(await api(path,{action,year_id:year,reason:operationReason,...values}));
      setActivate(false);setReason("");setReference("");setAmount("");setMessage("Opération commerciale enregistrée.");
    } catch(err){setMessage(err.message);}
    finally{pending.current=false;setBusy(false);}
  }
  const sub=data?.subscription;
  const gross=data?.terms?.gross_xaf ?? 0;
  const minimum=data?.terms?.minimum_xaf ?? 0;
  const annualBeforeDiscount=Math.max(gross,minimum);
  const discountOK=discount!==""&&Number.isSafeInteger(Number(discount))&&Number(discount)>=0&&Number(discount)<=annualBeforeDiscount;
  const annual=annualBeforeDiscount-(discountOK?Number(discount):0);
  const setup=includeSetup?(data?.setup_suggested_xaf||0):0;
  const total=annual+setup;
  const installments={annuel:1,semestriel:2,trimestriel:4,mensuel:12}[period];
  const validReason=reason.trim().length>0&&reason.trim().length<=240;
  const activationBlocker=busy?"Activation en cours…":!data?.can_issue?(data?.issue_blocker||"Cette année scolaire ou cet établissement ne permet pas une activation."):!Object.keys(data?.counts||{}).length?"Aucun cycle configuré.":!discountOK?"Renseignez une remise valide (0 si aucune).":Number(discount)>0&&!validReason?"Justifiez la remise exceptionnelle.":!activate?"Cochez l’autorisation de passage au service payant.":"";
  return <section className="ya-box ya-form-box yem-commercial-panel" aria-label="Abonnement commercial YEM">
    <h2>Abonnement annuel YEM</h2>
    {year&&<CommercialSimulator platform schoolId={schoolId} yearId={year} api={api} tariffRevision={tariffRevision} refreshKey={sub?.id||0}/> }
    <CommercialAccess key={schoolId+":"+reload+":"+(sub?.id||0)} schoolId={schoolId} api={api}/>
    <p>Facturation de la plateforme, distincte des frais de scolarité. Un seul contrat par établissement et année, ventilé par cycle. Aucun prélèvement ni suspension automatique. Les tarifs sont définis dans la grille centrale.</p>
    <label className="ya-field"><span>Année scolaire</span><select value={year} disabled={busy} onChange={e=>setYear(e.target.value)}>
      <option value="">Choisir une année…</option>{years.map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
    </select></label>
    {loading&&<p role="status">Chargement des effectifs…</p>}
    {!loading&&!years.length&&<p>Créez une année scolaire pour préparer un abonnement.</p>}
    {data?.counts&&<form onSubmit={e=>{e.preventDefault();submit("issue",{expected_counts:data.counts,policy_revision:data.policy_revision,period,discount_xaf:Number(discount),include_setup:includeSetup,expected_total_xaf:total});}}>
      <h3>Activer le service payant</h3>
      <p className="hint">Service gratuit tant que l’abonnement n’est pas activé. Effectif réel : <strong>{data.terms.student_count}</strong> · Grille n°{data.policy_revision}. Les effectifs sont automatiquement actualisés.</p>
      <p>Minimum annuel unique : {money(minimum)} · Complément minimum : {money(Math.max(0,minimum-gross))}</p>
      <label className="ya-field"><span>Remise exceptionnelle (FCFA) · 0 si aucune</span><input type="number" min="0" max={annualBeforeDiscount} step="1" value={discount} disabled={busy} onChange={e=>setDiscount(e.target.value)}/></label>
      <label className="ya-field"><span>Modalité de règlement</span><select value={period} onChange={e=>setPeriod(e.target.value)} disabled={busy}>
        <option value="annuel">Annuel · 1 versement</option><option value="semestriel">Semestriel · 2 versements</option><option value="trimestriel">Trimestriel · 4 versements</option><option value="mensuel">Mensuel · 12 versements</option></select></label>
      <p>Abonnement annuel net : <b>{money(annual)}</b> · {installments} versement(s) de {money(Math.floor(annual/installments))}{annual%installments!==0?" (écart d’arrondi sur les premières échéances)":""}.</p>
      <p>Première échéance si activation maintenant : <strong>{data.first_due}</strong>. Aucune date effective avant validation.</p>
      {!!data.setup_suggested_xaf&&<label><input type="checkbox" checked={includeSetup} disabled={busy} onChange={e=>setIncludeSetup(e.target.checked)}/> Ajouter la mise en service unique : {money(data.setup_suggested_xaf)}</label>}
      <p>Échéancier calculé sur douze mois à partir de la première échéance, indépendamment des vacances scolaires.</p>
      <p><strong>Total à contractualiser : {money(total)}</strong></p>
      <label className="ya-field"><span>Motif / référence du contrat {Number(discount)>0?"(obligatoire pour la remise)":"(facultatif)"}</span><textarea value={reason} required={Number(discount)>0} rows={2} maxLength={240} onChange={e=>setReason(e.target.value)}/></label>
      <p>Les effectifs, tarifs, minimums, échéances et remises sont figés à la création. Vérifiez le devis avant enregistrement.</p>
      {data.trial&&data.trial.status!=="converted"&&<p role="note">L’émission de ce contrat met fin à l’essai gratuit et crée les échéances contractuelles.</p>}
      <button type="button" className="ya-btn ya-btn-outline" disabled={busy} onClick={()=>setReload(n=>n+1)}>Recalculer les effectifs</button>
      <label className="yem-billing-toggle"><input type="checkbox" role="switch" checked={activate} disabled={busy||!data.can_issue} onChange={e=>setActivate(e.target.checked)}/><span><strong>Autoriser le passage au service payant</strong><small>Je confirme le démarrage des obligations contractuelles. Le service reste gratuit tant que je n’ai pas validé.</small></span></label>
      <p id="yem-activation-status" role="status" className="yem-activation-status">{activationBlocker||"Prêt à activer la facturation : vérifiez le montant et la première échéance."}</p>
      <button type="submit" className="ya-btn ya-btn-primary" aria-describedby="yem-activation-status" disabled={Boolean(activationBlocker)}>Activer la facturation</button>
    </form>}
    {!loading&&data&&year&&<CommercialAdjustments key={year+":"+(sub?.amendments?.length||0)+":"+(data.trial?.status||"")} api={api} path={path} year={year} sub={sub} trial={data.trial} canTrial={data.can_trial&&data.can_issue} disabled={busy} onSaved={()=>setReload(n=>n+1)}/>}
    {sub&&<div>
      <h3>Contrat annuel enregistré</h3>
      <p className="yem-estimate-state"><strong>Service payant activé</strong><small>Activation enregistrée. Les échéances et paiements existants ne sont pas annulables par un interrupteur.</small></p>
      <SubscriptionDocuments documents={sub.documents}/>
      {sub.lines.map(line=><p key={line.cycle}>{line.label} : {line.students} × {money(line.rate_xaf)} = <strong>{money(line.amount_xaf)}</strong></p>)}
      {sub.terms?.period&&<><p>Abonnement annuel : {money(sub.terms.annual_xaf)} · Minimum : {money(sub.terms.minimum_xaf)} · Remise : {money(sub.terms.discount_xaf)} · Mise en service : {money(sub.terms.setup_xaf)}</p>
        <h4>Échéancier contractuel — {({annuel:"annuel",semestriel:"semestriel",trimestriel:"trimestriel",mensuel:"mensuel"})[sub.terms.period]}</h4>{sub.schedule.map(item=><p key={item.kind+item.number}>{item.kind==="mise_en_service"?"Mise en service":item.kind==="avenant"?"Avenant "+item.number:"Versement "+item.number} — {item.due_date} — {money(item.amount_xaf)} · reste : {money(item.balance_xaf)} {item.days_overdue>0?" · "+item.days_overdue+" j de retard":""}</p>)}</>}
      <p>Total : <b>{money(sub.total_xaf)}</b> · Réglé : <b>{money(sub.paid_xaf)}</b> · Solde : <b>{money(sub.balance_xaf)}</b></p>
      <label className="ya-field"><span>Motif / justificatif de l’opération</span><textarea value={reason} rows={2} maxLength={240} onChange={e=>setReason(e.target.value)}/></label>
      {sub.balance_xaf>0&&<form onSubmit={e=>{e.preventDefault();submit("payment",{reference,amount_xaf:Number(amount),method});}}>
        <div className="ya-form-grid">
          <label className="ya-field"><span>Référence de règlement</span><input required maxLength={100} value={reference} onChange={e=>setReference(e.target.value)}/></label>
          <label className="ya-field"><span>Montant reçu (FCFA)</span><input required type="number" min="1" max={sub.balance_xaf} step="1" value={amount} onChange={e=>setAmount(e.target.value)}/></label>
          <label className="ya-field"><span>Moyen de règlement déclaré</span><select value={method} onChange={e=>setMethod(e.target.value)}>{methods.map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
        </div>
        <button className="ya-btn ya-btn-primary" disabled={busy||!validReason||!reference.trim()||!Number.isSafeInteger(Number(amount))||Number(amount)<=0||Number(amount)>sub.balance_xaf}>Enregistrer un règlement déjà reçu</button>
      </form>}
      <h3>Historique des règlements</h3>
      {!sub.payments.length&&<p>Aucun règlement déclaré.</p>}
      {sub.payments.map(p=><div key={p.id} className="ya-info-row yem-commercial-row"><span>{p.reference} · {money(p.amount_xaf)} · {methods.find(m=>m[0]===p.method)?.[1]||p.method}</span>
        {p.voided?<small>Annulé : {p.void_reason}</small>:<button type="button" className="ya-btn ya-btn-outline" disabled={busy||!validReason} onClick={()=>submit("void",{payment_id:p.id})}>Annuler l’écriture</button>}
      </div>)}
    </div>}
    {message&&<p role="status">{message}</p>}
  </section>;
}
