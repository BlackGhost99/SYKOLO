import React, {useEffect, useMemo, useState} from "react";

/** Fee taxonomy editor, restricted by the parent to school.finance.manage.
 *  Category rules are NOT monetary movements, and do not edit any payment.
 */
const pathFor = schoolId => "/api/v1/schools/" + schoolId + "/finance/entry-categories";
const FALLBACK = "Non classé explicitement";

async function readCategories(schoolId) {
  const response = await fetch(pathFor(schoolId), {credentials:"same-origin",cache:"no-store"});
  if(!response.ok) throw Error("Classement des frais indisponible.");
  return response.json();
}
async function classify(schoolId, data) {
  const csrfResponse=await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  if(!csrfResponse.ok) throw Error("Session de sécurité indisponible.");
  const token=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch(pathFor(schoolId),{
    method:"PATCH",credentials:"same-origin",cache:"no-store",
    headers:{"Content-Type":"application/json","X-CSRFToken":token},
    body:JSON.stringify(data),
  });
  const result=await response.json();
  if(!response.ok)throw Error(result.error||"Classement refusé.");
  return result;
}

export default function IncomeFeeCategoryPanel({schoolId,schedules=[],yearId=""}){
  const [catalog,setCatalog]=useState(null);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [selected,setSelected]=useState("");
  const [category,setCategory]=useState("scolarite");
  const [reason,setReason]=useState("");
  const [historicalAck,setHistoricalAck]=useState(false);
  const available=useMemo(()=>schedules.filter(row=>!yearId||row.year===yearId),[schedules,yearId]);

  useEffect(()=>{
    let alive=true;
    setCatalog(null);setSelected("");setError("");setMessage("");
    readCategories(schoolId).then(result=>{if(alive)setCatalog(result);})
      .catch(e=>{if(alive)setError(e.message);});
    return()=>{alive=false;};
  },[schoolId]);
  useEffect(()=>{setSelected("");setHistoricalAck(false);},[yearId]);

  async function submit(event){
    event.preventDefault();
    if(!selected||!catalog||reason.trim().length<10||busy)return;
    setBusy(true);setError("");setMessage("");
    try{
      const result=await classify(schoolId,{
        schedule:selected,category,reason:reason.trim(),revision:catalog.revision,
        acknowledge_history:historicalAck,
      });
      setCatalog(await readCategories(schoolId));
      setMessage(result.unchanged ? "Ce tarif est déjà classé ainsi." :
        "Classement enregistré et journalisé. Aucun paiement n'a été modifié.");
      setReason("");setHistoricalAck(false);
    }catch(e){setError(e.message);}
    finally{setBusy(false);}
  }
  return <section className="card" aria-label="Classification des frais de recettes" style={{marginBlock:16}}>
    <h3>Nature financière des frais</h3>
    <p className="hint">Attribuez une catégorie à chaque tarif. La scolarité reste prioritaire et l'extrascolaire séparée.
      Les écritures de démonstration sont toujours exclues des recettes vérifiées.</p>
    {error&&<p role="alert">{error}</p>}
    {message&&<p role="status">{message}</p>}
    {!catalog?<p>Chargement du classement…</p>:<>
      <form onSubmit={submit} style={{display:"grid",gap:12}}>
        <label className="field">Tarif à classer
          <select value={selected} onChange={e=>{setSelected(e.target.value);setHistoricalAck(false);}} required>
            <option value="">Sélectionner un tarif</option>
            {available.map(item=><option key={item.id} value={item.id}>
              {item.code} — {item.label} ({item.currency})
            </option>)}
          </select>
        </label>
        <label className="field">Catégorie
          <select value={category} onChange={e=>setCategory(e.target.value)}>
            {(catalog.categories||[]).map(item=><option key={item.code} value={item.code}>{item.label}</option>)}
          </select>
        </label>
        <label className="field">Justification de la classification
          <input minLength={10} maxLength={240} required value={reason}
            onChange={e=>setReason(e.target.value)}
            placeholder="Ex. Prestation facultative autorisée par l'école"/>
        </label>
        <label className="field">
          <input type="checkbox" checked={historicalAck}
            onChange={e=>setHistoricalAck(e.target.checked)}/>
          Je confirme avoir vérifié les anciennes créances de ce tarif s'il en existe.
        </label>
        <button type="submit" disabled={busy||!selected||reason.trim().length<10}>
          {busy?"Enregistrement…":"Enregistrer et historiser"}
        </button>
      </form>
      <details style={{marginTop:12}}>
        <summary>Consulter les classements ({available.length} tarifs)</summary>
        <div style={{overflowX:"auto"}}>
          <table className="dense"><thead><tr><th>Code tarif</th><th>Catégorie explicite</th></tr></thead>
            <tbody>{available.map(item=><tr key={item.id}>
              <td>{item.code}</td>
              <td>{(catalog.categories||[]).find(c=>c.code===catalog.assignments?.[item.id])?.label||FALLBACK}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </details>
      <p className="hint">Le premier classement d'un tarif historique exige une confirmation. Une fois des créances existantes classées, la catégorie est figée. Les mutations ultérieures doivent passer par une procédure comptable contrôlée.</p>
    </>}
  </section>;
}
