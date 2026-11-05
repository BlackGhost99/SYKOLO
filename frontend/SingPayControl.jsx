import React, {useEffect,useState} from "react";

async function api(path,body) {
  if(body!==undefined)await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(v=>v.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{method:body===undefined?"GET":"POST",credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.ok)throw Error(response.status===403?"Accès réservé.":(await response.json()).error||"Service indisponible.");
  return response.json();
}

export default function SingPayControl({schoolId}) {
  const [merchant,setMerchant]=useState(null),[payments,setPayments]=useState(null);
  const [message,setMessage]=useState(""),[busy,setBusy]=useState(false);
  const base="schools/"+schoolId+"/singpay";
  useEffect(()=>{
    let alive=true;setMerchant(null);setPayments(null);setMessage("");
    api(base+"/merchant").then(v=>{if(alive&&Number.isInteger(v.revision))setMerchant(v)}).catch(()=>{});
    api(base+"/reconciliation").then(v=>{if(alive&&Array.isArray(v.payments))setPayments(v.payments)}).catch(()=>{});
    return()=>{alive=false};
  },[base]);
  async function run(action) {
    setBusy(true);setMessage("");
    try{await action();setMessage("Contrôle enregistré.");if(payments!==null)setPayments((await api(base+"/reconciliation")).payments)}
    catch(error){setMessage(error.message)}finally{setBusy(false)}
  }
  if(!merchant&&payments===null)return null;
  return <section className="yd-card" style={{padding:"1rem",marginTop:"1rem"}}>
    <h3>SingPay — compte école et rapprochement</h3>
    <p>L'activation des paiements reste suspendue à la validation du prestataire. Aucun transfert n'est déclenché ici.</p>
    {merchant&&<details><summary>Préparer le compte marchand de l'établissement</summary>
      <p>Bénéficiaire enregistré : {merchant.beneficiary||"À renseigner"}. Fournissez uniquement les identifiants du compte de cette école et sa distribution autorisée.</p>
      <form aria-label="Compte marchand école" onSubmit={event=>{
        event.preventDefault();const form=event.currentTarget, data=new FormData(form);
        const body=Object.fromEntries(data);
        body.revision=merchant.revision;body.enabled=false;
        body.fee_basis_points=Number(body.fee_basis_points);body.fee_fixed_xaf=Number(body.fee_fixed_xaf);
        run(async()=>{setMerchant(await api(base+"/merchant",body));form.reset()});
      }}>
        {[["beneficiary_name","Bénéficiaire légal",180],["contract_reference","Référence du contrat école / SingPay",180],
          ["wallet_id","Identifiant du portefeuille école",120],["disbursement_id","Distribution destinataire école",120],
          ["client_id","Identifiant client SingPay",120],["client_secret","Secret client SingPay",500]].map(([name,label,max])=>
            <label key={name} className="field">{label}<input name={name} required maxLength={max}
              type={name==="client_secret"?"password":"text"} autoComplete="off" disabled={busy}/></label>)}
        <label className="field">Environnement<select name="mode" defaultValue="test" disabled={busy}>
          <option value="test">Test prestataire</option><option value="live">Production — préparation uniquement</option>
        </select></label>
        <label className="field">Frais contractuels en points de base (100 = 1 %)<input name="fee_basis_points" type="number" min="0" max="10000" step="1" defaultValue={merchant.fee_basis_points} required disabled={busy}/></label>
        <label className="field">Frais fixes contractuels XAF<input name="fee_fixed_xaf" type="number" min="0" max="100000" step="1" defaultValue={merchant.fee_fixed_xaf} required disabled={busy}/></label>
        <button type="submit" disabled={busy}>Enregistrer sans activer les paiements</button>
      </form>
    </details>}
    {payments!==null&&<>
      <h4>Contrôle des paiements et du règlement marchand</h4>
      {!payments.length&&<p>Aucun paiement SingPay enregistré.</p>}
      {payments.map(payment=><article key={payment.id}>
        <p><strong>{payment.reference}</strong> · {payment.beneficiary} · {payment.amount_xaf} XAF · {payment.state}</p>
        <button type="button" disabled={busy} onClick={()=>run(()=>api(base+"/reconciliation",{intent:payment.id}))}>Rapprocher auprès de SingPay</button>
        {payment.settlement?<>
          <p>Relevé {payment.settlement.statement_reference} · Net reçu {payment.settlement.received_net_xaf} XAF · Frais constatés {payment.settlement.observed_fee_xaf} XAF · {payment.settlement.approved?"Contrôlé par un second agent":"Second contrôle requis"}</p>
          {!payment.settlement.approved&&<button type="button" disabled={busy} onClick={()=>run(()=>api(base+"/payments/"+payment.id+"/settlement",{approve:true}))}>Approuver le rapprochement d'un autre agent</button>}
        </>:payment.paid_confirmed&&<form aria-label={"Règlement "+payment.reference} onSubmit={event=>{
          event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget));
          data.received_net_xaf=Number(data.received_net_xaf);data.observed_fee_xaf=Number(data.observed_fee_xaf);
          run(()=>api(base+"/payments/"+payment.id+"/settlement",data));
        }}>
          <label>Référence du relevé de règlement<input name="statement_reference" minLength="5" maxLength="180" required disabled={busy}/></label>
          <label>Net réellement reçu XAF<input name="received_net_xaf" type="number" min="0" step="1" required disabled={busy}/></label>
          <label>Frais réellement constatés XAF<input name="observed_fee_xaf" type="number" min="0" step="1" required disabled={busy}/></label>
          <button type="submit" disabled={busy}>Soumettre le rapprochement documentaire</button>
        </form>}
      </article>)}
    </>}
    {message&&<p role="status">{message}</p>}
  </section>;
}
