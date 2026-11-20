import React, {useEffect, useState} from "react";
import {TableScroll} from "./yem-ui.jsx";

// The established YEM theme is inherited from the dashboard; no mock balances.
const todayLocal = () => {
  const date = new Date();
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
};
const csrf = () => document.cookie.split("; ").find(x => x.startsWith("csrftoken="))?.split("=")[1] || "";

async function financeRequest(path, data) {
  if (data !== undefined) {
    const token = await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
    if (!token.ok) throw Error("Impossible de vérifier la sécurité du compte.");
  }
  const response = await fetch("/api/v1/" + path, {
    credentials:"same-origin",
    cache:"no-store",
    method:data === undefined ? "GET" : "POST",
    headers:data === undefined ? {} : {"Content-Type":"application/json","X-CSRFToken":csrf()},
    body:data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) throw Error("Serveur YEM indisponible.");
  const result = await response.json();
  if (!response.ok) throw Error(result.error || "Opération financière refusée.");
  return result;
}

const formatMoney = (amount, currency) =>
  new Intl.NumberFormat("fr-GA", {minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(amount)) + " " + (currency === "XAF" ? "FCFA" : currency);

export default function CashClosingPanel({schoolId, defaultDay}) {
  const [permissions,setPermissions]=useState([]);
  const [rows,setRows]=useState([]);
  const [summary,setSummary]=useState(null);
  const [unclosed,setUnclosed]=useState(null);
  const [historyDay,setHistoryDay]=useState("");
  const [refreshError,setRefreshError]=useState("");
  const [updated,setUpdated]=useState("");
  const [day,setDay]=useState(defaultDay || todayLocal());
  const [currency,setCurrency]=useState("XAF");
  const [counted,setCounted]=useState("");
  const [note,setNote]=useState("");
  const [approvalNotes,setApprovalNotes]=useState({});
  const [transfer,setTransfer]=useState({closing:"",kind:"handover",amount:"",reference:"",destination:"",day:todayLocal()});
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");

  const canRead=permissions.includes("school.finance.read");
  const canReceive=permissions.includes("school.finance.receive");
  const canApprove=permissions.includes("school.finance.approve");

  useEffect(()=>{
    setPermissions([]);setRows([]);setSummary(null);setUnclosed(null);setUpdated("");
    setHistoryDay("");setRefreshError("");setApprovalNotes({});
    setTransfer({closing:"",kind:"handover",amount:"",reference:"",destination:"",day:todayLocal()});
  },[schoolId]);
  useEffect(()=>{
    if(busy)return;
    let alive=true,running=false;
    async function refresh(){
      if(running||document.hidden)return;
      running=true;
      try{
        const [access,result,report]=await Promise.all([
          financeRequest(`schools/${schoolId}/my-access`),
          financeRequest(`schools/${schoolId}/finance/cash/closings`),
          financeRequest(`schools/${schoolId}/finance/summary`),
        ]);
        if(!alive)return;
        setPermissions(access.permissions||[]);
        setRows(result.closings||[]);
        setSummary(report);
        setUnclosed(Array.isArray(result.unclosed_days)?{rows:result.unclosed_days,start:result.unclosed_start,end:result.unclosed_end}:null);
        setUpdated(new Date().toLocaleString("fr-GA"));
        setRefreshError("");
      }catch(e){
        if(alive){setPermissions([]);setRows([]);setSummary(null);setUnclosed(null);setUpdated("");setRefreshError(e.message);}
      }finally{running=false;}
    }
    refresh();
    const timer=window.setInterval(refresh,30000);
    window.addEventListener("focus",refresh);
    document.addEventListener("visibilitychange",refresh);
    return ()=>{alive=false;window.clearInterval(timer);window.removeEventListener("focus",refresh);document.removeEventListener("visibilitychange",refresh);};
  },[schoolId,busy]);

  async function act(task,success) {
    setBusy(true);setError("");setMessage("");
    try {
      await task();
      setMessage(success);
    } catch(e) {setError(e.message);}
    finally {setBusy(false);}
  }

  if(!canRead && !error && !refreshError)return null;
  return <section className="yd-cash-closing" aria-label="Clôture de caisse">
    <h3>Contrôle quotidien des recettes en espèces</h3>
    {refreshError&&<p role="alert" className="pc-alert">Actualisation impossible : {refreshError}</p>}
    {updated&&<p className="yd-card-sub">Dernière actualisation : {updated} · actualisation automatique toutes les 30 secondes.</p>}
    {canRead&&unclosed&&<div style={{marginBottom:16}}>
      <h4>Recettes sans déclaration de caisse</h4>
      <p className="yd-card-sub">Période : {unclosed.start} au {unclosed.end}. Espèces déclarées uniquement, par agent et devise.</p>
      {unclosed.rows.length===0?<p>Aucune recette sans déclaration sur cette période.</p>:<TableScroll label="Recettes sans clôture"><table className="dense"><thead><tr><th>Jour</th><th>Agent</th><th>Recettes attendues</th></tr></thead><tbody>{unclosed.rows.map(r=><tr key={JSON.stringify([r.day,r.agent,r.currency])}><td>{r.day}</td><td>{r.agent}</td><td>{formatMoney(r.expected,r.currency)}</td></tr>)}</tbody></table></TableScroll>}
    </div>}
    {canRead&&summary&&<details style={{marginBottom:16}}>
      <summary>Situation financière par devise · tous exercices (historique)</summary>
      <p className="yd-card-sub">Montants déclarés manuellement par l'établissement, hors confirmations automatiques des banques et opérateurs mobiles.</p>
      {Object.keys(summary.currencies).length===0
        ?<p className="yd-card-sub">Aucun frais encore facturé.</p>
        :<TableScroll label="Totaux par devise"><table className="dense">
          <thead><tr><th>Devise</th><th>Facturé</th><th>Encaissé</th><th>Restant dû</th><th>Échu et impayé</th></tr></thead>
          <tbody>{Object.entries(summary.currencies).map(([devise,row])=><tr key={devise}>
            <td>{devise}</td>
            <td>{formatMoney(row.billed,devise)}</td>
            <td>{formatMoney(row.paid,devise)}</td>
            <td>{formatMoney(row.balance,devise)}</td>
            <td>{formatMoney(row.overdue,devise)}</td>
          </tr>)}</tbody>
        </table></TableScroll>}
    </details>}
    <p className="yd-card-sub">Seuls les encaissements en espèces effectivement enregistrés sont comptés. Les paiements Mobile Money et virements ne sont pas de l'argent en caisse. Ce contrôle porte sur les recettes journalières, pas sur un solde de trésorerie incluant fonds de caisse et dépenses.</p>
    {canReceive&&<form onSubmit={e=>{e.preventDefault();act(async()=>{
      await financeRequest(`schools/${schoolId}/finance/cash/closings`,{
        day,currency,counted:counted.replace(",", "."),note,
      });
      setCounted("");setNote("");
    },"Déclaration de caisse enregistrée. En attente d'un contrôle indépendant.");}} style={{display:"grid",gap:12}}>
      <div className="yd-cash-fields" style={{display:"grid",gridTemplateColumns:"repeat(auto-fit, minmax(150px, 1fr))",gap:12}}>
        <label>Date<input type="date" required max={todayLocal()} value={day} onChange={e=>setDay(e.target.value)}/></label>
        <label>Devise<input required maxLength={3} minLength={3} pattern="[A-Z]{3}" value={currency} onChange={e=>setCurrency(e.target.value.toUpperCase())}/></label>
        <label>Espèces physiquement comptées<input required inputMode="decimal" placeholder="Ex. 450000" value={counted} pattern="[0-9]+([.,][0-9]{1,2})?" onChange={e=>setCounted(e.target.value)}/></label>
      </div>
      <label>Justification (obligatoire en cas d'écart)<textarea rows={2} value={note} maxLength={500} onChange={e=>setNote(e.target.value)} placeholder="Comptage, éventuels écarts et pièces justificatives…"/></label>
      <button type="submit" className="yd-btn" disabled={busy||!counted||!day}>Soumettre le contrôle de caisse</button>
    </form>}
    {permissions.includes("school.finance.deposit")&&<form aria-label="Remise ou dépôt" onSubmit={e=>{e.preventDefault(); const {closing,...data}=transfer; act(()=>financeRequest(`schools/${schoolId}/finance/cash/closings/${closing}/transfers`,data),"Mouvement enregistré, justificatif à contrôler.");}}>
      <h4>Remise des fonds / dépôt bancaire</h4>
      <label>Clôture validée<select required value={transfer.closing} onChange={e=>setTransfer({...transfer,closing:e.target.value})}><option value="">Choisir</option>{rows.filter(r=>r.status==="approved").map(r=><option key={r.id} value={r.id}>{r.day} · {r.submitted_by} · {r.currency}</option>)}</select></label>
      <label>Opération<select value={transfer.kind} onChange={e=>setTransfer({...transfer,kind:e.target.value})}><option value="handover">Remise physique</option><option value="deposit">Dépôt bancaire</option></select></label>
      {[['amount','Montant'],['reference','Référence du justificatif'],['destination','Destinataire / banque'],['day','Date']].map(([key,label])=><label key={key}>{label}<input required type={key==='day'?'date':'text'} value={transfer[key]} onChange={e=>setTransfer({...transfer,[key]:e.target.value})}/></label>)}
      <button disabled={busy} className="yd-btn">Enregistrer le mouvement</button>
    </form>}
    {rows.flatMap(r=>(r.transfers||[]).map(t=><p key={t.id}>{t.kind==='handover'?'Remise':'Dépôt'} · {formatMoney(t.amount,r.currency)} · {t.destination} · {t.reference} · {t.approved_by?`Contrôlé par ${t.approved_by}`:canApprove?<button disabled={busy} onClick={()=>act(()=>financeRequest(`schools/${schoolId}/finance/cash/closings/${r.id}/transfers/${t.id}/approve`,{}),"Justificatif contrôlé.")}>Contrôler le justificatif</button>:"À contrôler"}</p>))}
    {error&&<p role="alert" className="pc-alert">{error}</p>}
    {message&&<p role="status" className="yd-form-msg">{message}</p>}
    {canRead&&<div style={{marginTop:14}}>
      <h4>Déclarations récentes</h4>
      <label>Filtrer les 100 dernières déclarations par date<input type="date" value={historyDay} onChange={e=>setHistoryDay(e.target.value)}/></label>
      {rows.filter(r=>!historyDay||r.day===historyDay).length===0?<p className="yd-card-sub">Aucune déclaration dans les résultats affichés. L’économe soumet le comptage avant contrôle du comptable.</p>:
       <TableScroll label="Historique des clôtures"><table className="dense">
         <thead><tr><th>Jour</th><th>Agent</th><th>Attendu</th><th>Compté</th><th>Écart</th><th>Contrôle</th></tr></thead>
         <tbody>{rows.filter(r=>!historyDay||r.day===historyDay).map(row=><tr key={row.id}>
           <td>{row.day}</td><td>{row.submitted_by}</td>
           <td>{formatMoney(row.expected,row.currency)}</td>
           <td>{formatMoney(row.counted,row.currency)}</td>
           <td>{formatMoney(row.difference,row.currency)}
             {row.adjustment_since_submission!=="0.00"&&<small> Ajustement postérieur : {formatMoney(row.adjustment_since_submission,row.currency)}</small>}</td>
           <td>{row.status==="approved"?"Validé par "+row.approved_by:
             canApprove?<div style={{display:"grid",gap:6}}>
               <input aria-label={"Motif de validation "+row.day} placeholder="Motif (en cas d'écart)" maxLength={500} value={approvalNotes[row.id]||""}
                 onChange={e=>setApprovalNotes(old=>({...old,[row.id]:e.target.value}))}/>
               <button type="button" className="yd-btn" disabled={busy} onClick={()=>act(()=>
                 financeRequest(`schools/${schoolId}/finance/cash/closings/${row.id}/approve`,{note:approvalNotes[row.id]||""}),
               "Clôture vérifiée et validée.")}>Valider</button>
             </div>:"En attente"}</td>
         </tr>)}</tbody>
       </table></TableScroll>}
    </div>}
  </section>;
}
