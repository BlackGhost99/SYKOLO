import React,{useEffect,useState} from "react";

/** Read-only receipt-level drilldown for ONE school/year/category/currency/code. */
export default function IncomeTransactionExplorer({schoolId,yearId,category,currency,feeCode}){
  const [opened,setOpened]=useState(false);
  const [page,setPage]=useState(1);
  const [revision,setRevision]=useState(0);
  const [view,setView]=useState(null);
  const [error,setError]=useState("");
  useEffect(()=>{setOpened(false);setPage(1);setView(null);setError("");},
    [schoolId,yearId,category,currency,feeCode]);
  useEffect(()=>{
    if(!opened||!yearId)return;
    let alive=true;
    setView(null);setError("");
    const p=new URLSearchParams({year:yearId,category,currency,fee_code:feeCode,page:String(page)});
    fetch(`/api/v1/schools/${schoolId}/finance/entry-transactions?${p}`,{
      credentials:"same-origin",cache:"no-store",
    }).then(async response=>{
      if(!response.ok){
        const json=await response.json().catch(()=>({}));
        throw Error(json.error||"Le registre est indisponible.");
      }
      return response.json();
    }).then(data=>{if(alive)setView(data);}).catch(e=>{if(alive)setError(e.message);});
    return()=>{alive=false;};
  },[schoolId,yearId,category,currency,feeCode,page,opened,revision]);
  return <div className="yd-card-sub" style={{marginBlock:8}}>
    <button type="button" disabled={!yearId} aria-expanded={opened}
      onClick={()=>setOpened(v=>!v)}>
      {opened?"Fermer les transactions":"Voir les transactions de "+feeCode}
    </button>
    {opened&&<div style={{marginTop:10}}>
      {error&&<p role="alert">{error}</p>}
      {!error&&!view&&<p role="status">Chargement des transactions…</p>}
      {view&&<>
        <p>{view.total} règlement(s) enregistré(s) · {feeCode} · {currency}.
          Ces montants sont déclarés, non certifiés par une banque.</p>
        {!view.rows?.length?<p>Aucune opération pour cette page.</p>:
          <div style={{overflowX:"auto"}}><table className="dense">
            <thead><tr><th>Date</th><th>Montant</th><th>Mode déclaré</th><th>Justificatif</th></tr></thead>
            <tbody>{view.rows.map(item=><tr key={item.id}>
              <td>{item.date}{item.future_dated?" (date future)":""}</td>
              <td>{new Intl.NumberFormat("fr-FR",{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(item.amount))} {item.currency}</td>
              <td>{item.evidence==="simulation"?"Simulation":item.evidence==="legacy_unverified"?"Ancien cash non vérifié":item.method}</td>
              <td><a href={item.receipt_url} target="_blank" rel="noopener noreferrer">
                Voir le reçu PDF</a></td>
            </tr>)}</tbody>
          </table></div>}
        <div className="actions">
          <button type="button" disabled={page<=1} onClick={()=>setPage(p=>p-1)}>Précédent</button>
          <span>Page {page} / {Math.max(view.pages||1,1)}</span>
          <button type="button" disabled={page>=view.pages} onClick={()=>setPage(p=>p+1)}>Suivant</button>
          <button type="button" onClick={()=>setRevision(v=>v+1)}>Actualiser</button>
        </div>
      </>}
    </div>}
  </div>;
}
