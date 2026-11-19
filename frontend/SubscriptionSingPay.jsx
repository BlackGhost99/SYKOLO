import React,{useEffect,useRef,useState} from "react";
async function api(path,body){
  if(body!==undefined)await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(v=>v.startsWith("csrftoken="))?.split("=")[1]||"";
  const r=await fetch("/api/v1/"+path,{method:body===undefined?"GET":"POST",credentials:"same-origin",headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},body:body===undefined?undefined:JSON.stringify(body)});
  const v=await r.json();if(!r.ok)throw Error(v.error||"Service indisponible.");return v;
}
export default function SubscriptionSingPay({schoolId,subscriptionId}){
  const path=`schools/${schoolId}/owner/subscriptions/${subscriptionId}/singpay`;
  const [data,setData]=useState(null),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
  const pending=useRef(null),lock=useRef(false);
  useEffect(()=>{let alive=true;setData(null);pending.current=null;api(path).then(v=>{if(alive&&v.merchant&&Array.isArray(v.payments))setData(v)}).catch(e=>{if(alive)setMessage(e.message)});return()=>{alive=false}},[path]);
  async function run(action){if(lock.current)return;lock.current=true;setBusy(true);setMessage("");try{await action();setData(await api(path))}catch(e){setMessage(e.message)}finally{lock.current=false;setBusy(false)}}
  return <section aria-label="Paiement SingPay de l’abonnement"><h3>Régler l’abonnement par Mobile Money</h3>
    {message&&<p role="alert">{message}</p>}
    {data&&<><p>Bénéficiaire : {data.merchant.beneficiary||"Compte BWETEK à configurer"}. Solde : {data.balance_xaf} FCFA.</p>
      {data.merchant.active&&data.balance_xaf>=100?<form onSubmit={event=>{event.preventDefault();const form=new FormData(event.currentTarget);if(!pending.current)pending.current={amount_xaf:Number(form.get("amount")),phone:form.get("phone"),channel:form.get("channel"),idempotency_key:crypto.randomUUID(),merchant_revision:data.merchant.revision};run(async()=>{await api(path,pending.current);pending.current=null})}}>
        <p>{data.merchant.mode==="test"?"Mode test : aucun règlement de contrat réel.":"Validez la demande sur votre téléphone. Les frais contractuels sont à la charge de BWETEK."}</p>
        <label>Montant FCFA<input name="amount" type="number" min="100" max={Math.min(10000000,data.balance_xaf)} step="1" defaultValue={data.balance_xaf} required disabled={busy||!!pending.current}/></label>
        <label>Opérateur<select name="channel" disabled={busy||!!pending.current}><option value="airtel">Airtel Money</option><option value="moov">Moov Money</option></select></label>
        <label>Téléphone Mobile Money<input name="phone" type="tel" required disabled={busy||!!pending.current}/></label>
        <button disabled={busy}>Payer BWETEK Informatyk</button>
      </form>:<p>{data.balance_xaf<100?"Aucun montant payable en ligne.":"Le compte marchand BWETEK doit être validé et activé."}</p>}
      {data.payments.map(row=><div key={row.id}><p>{row.reference} — {row.amount_xaf} FCFA — {row.state}</p>
        <button disabled={busy} onClick={()=>run(()=>api(`${path}/${row.id}/refresh`,{}))}>Vérifier le paiement</button>
        {row.receipt&&<a href={row.receipt} target="_blank" rel="noreferrer">Reçu d’abonnement</a>}
      </div>)}
    </>}
  </section>
}
