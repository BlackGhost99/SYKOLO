import React,{useEffect,useState} from "react";
import {TableScroll} from "./yem-ui.jsx";
import DemoPaymentSetup from "./DemoPaymentSetup.jsx";

async function api(path,body) {
  if(body!==undefined)await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const r=await fetch("/api/v1/"+path,{
    method:body===undefined?"GET":"POST",credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  const json=await r.json();
  if(!r.ok)throw Error(json.error||"Opération refusée.");
  return json;
}

export function AdmissionTariffSettings({schoolId}) {
  const path="schools/"+schoolId+"/admission-fees";
  const [catalog,setCatalog]=useState(null);
  const [year,setYear]=useState("");
  const [level,setLevel]=useState("");
  const [amount,setAmount]=useState("");
  const [active,setActive]=useState(true);
  const [busy,setBusy]=useState(false);
  const [notice,setNotice]=useState("");
  const {fees=[],years=[],levels=[]}=catalog||{};
  const current=fees.find(f=>f.year===year&&f.level===level);
  useEffect(()=>{
    let live=true;
    api(path).then(data=>{if(live)setCatalog(data);})
      .catch(e=>{if(live)setNotice(e.message);});
    return()=>{live=false;};
  },[path]);
  useEffect(()=>{
    setAmount(String(current?.amount_xaf??""));
    setActive(current?.active??true);
  },[year,level,current]);
  async function run(fn){
    setBusy(true);setNotice("");
    try{await fn()}catch(e){setNotice(e.message)}finally{setBusy(false)}
  }
  if(!catalog)return <p role="status">{notice||"Chargement des tarifs d’inscription…"}</p>;
  return <section className="yp-settings" aria-label="Tarifs d’inscription">
    <h3>Tarifs d’inscription</h3>
    <p>Ce sont des <strong>frais de dossier d'admission</strong>, indépendants des frais de scolarité.
       Ils sont configurables par année et niveau : maternelle, primaire, collège, lycée ou groupe scolaire.</p>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      if(!year||!level)throw Error("Année et niveau obligatoires.");
      const item=await api(path,{
        year,level,revision:current?.revision??0,amount_xaf:Number(amount),active,
      });
      setCatalog(old=>({...old,fees:[...old.fees.filter(f=>f.id!==item.id),item]}));
      setNotice("Tarif d'admission enregistré. Les dossiers qui ont déjà un montant le conservent.");
    });}}>
      <div className="yp-two">
        <label className="yp-field">Année<select value={year} onChange={e=>setYear(e.target.value)}>
          <option value="">Choisir l’année</option>
          {years.map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
        </select></label>
        <label className="yp-field">Niveau<select value={level} onChange={e=>setLevel(e.target.value)}>
          <option value="">Choisir le niveau</option>
          {levels.map(l=><option key={l.id} value={l.id}>{l.name}</option>)}
        </select></label>
        <label className="yp-field">Montant d’inscription (FCFA/XAF)
          <input type="number" required min="100" max="10000000" step="1" value={amount} onChange={e=>setAmount(e.target.value)}/>
        </label>
      </div>
      <label className="yp-toggle"><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>
        Activer le tarif pour cette année et ce niveau</label>
      <button type="submit" className="yp-button yp-primary" disabled={busy||!year||!level}>Enregistrer le tarif</button>
    </form>
    {notice&&<p role="status">{notice}</p>}
  </section>;
}

export default function SchoolPaymentSetup({schoolId,years=[],classes=[]}) {
  const root="schools/"+schoolId+"/";
  const [gateway,setGateway]=useState(null);
  const [payments,setPayments]=useState([]);
  const [key,setKey]=useState("");
  const [secret,setSecret]=useState("");
  const [busy,setBusy]=useState(false);
  const [notice,setNotice]=useState("");
  useEffect(()=>{let live=true;
    Promise.all([api(root+"admission-gateway"),api(root+"admission-payments")])
      .then(([g,p])=>{if(live){setGateway(g);setPayments(p.payments||[]);}})
      .catch(e=>{if(live)setNotice(e.message);});
    return()=>{live=false;};
  },[root]);
  async function run(fn){
    setBusy(true);setNotice("");
    try{await fn()}catch(e){setNotice(e.message)}finally{setBusy(false)}
  }
  if(!gateway)return <p role="status">{notice||"Chargement du prestataire…"}</p>;
  return <section className="yp-settings" aria-label="Paiement en ligne des candidatures">
    <h3>Encaissement Mobile Money propre à votre école</h3>
    <p>Les paiements vont vers <strong>votre compte marchand PayCentral</strong>, pas celui d'une autre école.
       Ne communiquez jamais les clés API aux parents. <strong>La simulation ne collecte pas d'argent.</strong></p>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      const result=await api(root+"admission-gateway",{
        revision:gateway.revision,mode:gateway.mode,enabled:gateway.enabled,
        api_key:key,webhook_secret:secret,
      });
      setGateway(result);setKey("");setSecret("");
      setNotice("Passerelle enregistrée. Vérifiez le webhook avant toute ouverture réelle.");
    });}}>
      <label className="yp-field">Environnement
        <select value={gateway.mode} onChange={e=>setGateway(v=>({...v,mode:e.target.value,enabled:false}))}>
          <option value="sandbox">Simulation (aucun paiement réel)</option>
          <option value="live" disabled={!gateway.live_enabled_by_platform}>Production (contrat validé)</option>
        </select>
      </label>
      <label className="yp-field">Clé API marchande {gateway.has_keys?"(laisser vide pour conserver)":""}
        <input type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)}
          placeholder={gateway.mode==="sandbox"?"sk_sandbox_...":"sk_live_..."}/>
      </label>
      <label className="yp-field">Secret webhook signé {gateway.has_keys?"(laisser vide pour conserver)":""}
        <input type="password" autoComplete="off" value={secret} onChange={e=>setSecret(e.target.value)}
          placeholder="whsec_..."/>
      </label>
      <p>Webhook à déclarer dans PayCentral : <code>{gateway.webhook_url}</code></p>
      <label className="yp-toggle"><input type="checkbox" checked={gateway.enabled}
        onChange={e=>setGateway(v=>({...v,enabled:e.target.checked}))}/> Activer cette passerelle</label>
      {!gateway.encryption_ready&&<p className="yp-error">La clé de chiffrement serveur n'est pas encore configurée. Aucune clé marchande ne sera enregistrée.</p>}
      {gateway.mode==="live"&&!gateway.live_enabled_by_platform&&<p className="yp-error">Paiement réel désactivé par sécurité au niveau plateforme.</p>}
      <button className="yp-button yp-primary" type="submit" disabled={busy}>Enregistrer la passerelle</button>
    </form>
    <DemoPaymentSetup schoolId={schoolId} years={years} classes={classes}/>
    <h3 style={{marginTop:22}}>Transactions de candidature</h3>
    <p>Vérifiez toujours le statut de paiement auprès du prestataire. Les transactions en simulation ne représentent pas des encaissements réels.</p>
    <button type="button" className="yp-button" disabled={busy} onClick={()=>run(async()=>{
      const response=await api(root+"admission-payments");
      setPayments(response.payments||[]);setNotice("Liste actualisée.");
    })}>Actualiser les transactions</button>
    {payments.length===0?<p>Aucune tentative de paiement en ligne.</p>:
      <TableScroll label="Configuration des paiements"><table style={{width:"100%",marginTop:12}}>
        <thead><tr><th>Référence</th><th>Montant</th><th>Canal</th><th>État</th><th>Mode</th></tr></thead>
        <tbody>{payments.map(p=><tr key={p.id}>
          <td><code>{p.merchant_reference}</code></td>
          <td>{Number(p.amount_xaf).toLocaleString("fr-FR")} FCFA</td>
          <td>{p.channel}</td><td>{p.state}</td><td>{p.provider_mode==="sandbox"?"SIMULATION":"Réel"}</td>
        </tr>)}</tbody>
      </table></TableScroll>}
    {notice&&<p role="status">{notice}</p>}
  </section>;
}
