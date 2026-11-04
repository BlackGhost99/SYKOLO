import React, {useEffect, useState} from "react";

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
  const [day,setDay]=useState(defaultDay || todayLocal());
  const [currency,setCurrency]=useState("XAF");
  const [counted,setCounted]=useState("");
  const [note,setNote]=useState("");
  const [approvalNotes,setApprovalNotes]=useState({});
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");

  const canRead=permissions.includes("school.finance.read");
  const canReceive=permissions.includes("school.finance.receive");
  const canApprove=permissions.includes("school.finance.reverse");

  async function reload() {
    const result=await financeRequest(`schools/${schoolId}/finance/cash/closings`);
    setRows(result.closings || []);
  }
  useEffect(()=>{
    let alive=true;
    Promise.all([
      financeRequest(`schools/${schoolId}/my-access`),
      financeRequest(`schools/${schoolId}/finance/cash/closings`),
    ]).then(([access,result])=>{
      if (!alive) return;
      setPermissions(access.permissions||[]);
      setRows(result.closings||[]);
    }).catch(e=>{if(alive)setError(e.message);});
    return ()=>{alive=false;};
  },[schoolId]);

  async function act(task,success) {
    setBusy(true);setError("");setMessage("");
    try {
      await task();
      await reload();
      setMessage(success);
    } catch(e) {setError(e.message);}
    finally {setBusy(false);}
  }

  if(!canRead && !error)return null;
  return <section className="yd-cash-closing" aria-label="Clôture de caisse">
    <h3>Contrôle quotidien des espèces</h3>
    <p className="yd-card-sub">Seuls les encaissements en espèces effectivement enregistrés sont comptés. Les paiements Mobile Money et virements ne sont pas de l'argent en caisse.</p>
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
    {error&&<p role="alert" className="pc-alert">{error}</p>}
    {message&&<p role="status" className="yd-form-msg">{message}</p>}
    {canRead&&<div style={{marginTop:14}}>
      <h4>Déclarations récentes</h4>
      {rows.length===0?<p className="yd-card-sub">Aucune clôture de caisse enregistrée.</p>:
       <div className="yd-table-wrap"><table className="dense">
         <thead><tr><th>Jour</th><th>Agent</th><th>Attendu</th><th>Compté</th><th>Écart</th><th>Contrôle</th></tr></thead>
         <tbody>{rows.slice(0,12).map(row=><tr key={row.id}>
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
       </table></div>}
    </div>}
  </section>;
}
