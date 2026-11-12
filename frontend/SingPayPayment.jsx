import React, {useEffect, useRef, useState} from "react";

export default function SingPayPayment({kind, objectId, api, partial=false, defaultChannel="airtel"}) {
  const [quote,setQuote]=useState(null), [amount,setAmount]=useState("");
  const [channel,setChannel]=useState(defaultChannel), [phone,setPhone]=useState("");
  useEffect(()=>setChannel(defaultChannel),[defaultChannel]);
  const [busy,setBusy]=useState(false), [message,setMessage]=useState("");
  const operation=useRef(null);
  const base="parents/singpay/"+kind+"/"+objectId;
  useEffect(()=>{
    let alive=true; setQuote(null); operation.current=null;
    api(base+"/quote").then(data=>{if(alive){setQuote(data);setAmount(data.balance_xaf)}})
      .catch(error=>{if(alive)setMessage(error.message)});
    return()=>{alive=false};
  },[base,api]);
  async function run(action) {
    setBusy(true);setMessage("");
    try {await action();const latest=await api(base+"/quote");setQuote(latest);if(!operation.current)setAmount(latest.balance_xaf)}
    catch(error){setMessage(error.message)}finally{setBusy(false)}
  }
  if(!quote)return message?<p role="status">{message}</p>:null;
  const merchant=quote.merchant, value=Number(amount);
  const fee=Math.ceil(value*merchant.fee_basis_points/10000)+merchant.fee_fixed_xaf;
  const open=quote.payments.some(p=>["initiating","pending","unknown","review","refund_review"].includes(p.state));
  return <section aria-label="Paiement SingPay">
    {!merchant.active?<p>SingPay sera proposé après validation du compte marchand de cet établissement.</p>:<>
      <p>Bénéficiaire : <strong>{merchant.beneficiary}</strong> · {merchant.mode==="test"?"Test prestataire, sans crédit de scolarité":"Compte marchand de l'établissement"}</p>
      <form onSubmit={event=>{event.preventDefault();run(async()=>{
        // A connection error retains the exact request and its idempotency key.
        if(!operation.current)operation.current={amount_xaf:value,channel,phone,
          merchant_revision:merchant.revision,idempotency_key:crypto.randomUUID()};
        const payment=await api(base+"/pay",operation.current);
        setMessage(payment.notice+" Validez uniquement sur votre téléphone Mobile Money.");
      })}}>
        <label>Montant XAF <input type="number" min="100" max={quote.balance_xaf} step="1" required
          value={amount} disabled={!partial||busy||!!operation.current} onChange={e=>setAmount(e.target.value)}/></label>
        <label>Opérateur <select value={channel} disabled={busy||!!operation.current} onChange={e=>setChannel(e.target.value)}>
          <option value="airtel">Airtel Money</option><option value="moov">Moov Money</option>
        </select></label>
        <label>Téléphone Mobile Money <input type="tel" required placeholder="074000000"
          value={phone} disabled={busy||!!operation.current} onChange={e=>setPhone(e.target.value)}/></label>
        <p>Total débité : <strong>{Number.isFinite(value)?value:0} XAF</strong>. Frais contractuels estimés : {Number.isFinite(fee)?fee:0} XAF,
          pris en charge par l'école. Net estimé pour l'école : {Number.isFinite(value-fee)?value-fee:0} XAF.</p>
        <button type="submit" disabled={busy||open||!Number.isInteger(value)||value<100||fee>value||value>Number(quote.balance_xaf)}>Payer à l'établissement</button>
      </form>
    </>}
    {quote.payments.map(payment=><div key={payment.id}>
      <p>{payment.reference} · {payment.amount_xaf} XAF · {payment.state} · {payment.notice}</p>
      <button type="button" disabled={busy} onClick={()=>run(async()=>{
        const checked=await api("parents/singpay/payments/"+payment.id+"/refresh",{});
        setMessage(checked.notice);
        if(["failed","success","test_success"].includes(checked.state))operation.current=null;
      })}>Vérifier auprès du prestataire</button>
      {payment.paid_confirmed&&<a href={"/api/v1/parents/singpay/payments/"+payment.id+"/receipt"}>Reçu vérifié</a>}
    </div>)}
    {message&&<p role="status">{message}</p>}
  </section>;
}
