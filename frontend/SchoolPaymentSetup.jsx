import React,{useEffect,useMemo,useState} from "react";

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

export default function SchoolPaymentSetup({schoolId,years=[],classes=[]}) {
  const root="schools/"+schoolId+"/";
  const [gateway,setGateway]=useState(null);
  const [fees,setFees]=useState([]);
  const [payments,setPayments]=useState([]);
  const [key,setKey]=useState("");
  const [secret,setSecret]=useState("");
  const [year,setYear]=useState("");
  const [level,setLevel]=useState("");
  const [amount,setAmount]=useState("1000");
  const [active,setActive]=useState(true);
  const [busy,setBusy]=useState(false);
  const [notice,setNotice]=useState("");
  const levels=useMemo(()=>{
    const seen=new Set();
    return classes.filter(c=>{
      if(c.year!==year||seen.has(c.level))return false;
      seen.add(c.level);return true;
    }).map(c=>({id:c.level,label:c.level_name||c.name}));
  },[classes,year]);
  const current=fees.find(f=>f.year===year&&f.level===level);
  useEffect(()=>{if(!year&&years.length)setYear(String(years.find(y=>y.active)?.id||years[0].id));},[years,year]);
  useEffect(()=>{if(!level||!levels.some(l=>l.id===level))setLevel(levels[0]?.id||"");},[levels,level]);
  useEffect(()=>{setAmount(String(current?.amount_xaf??1000));setActive(current?.active??true);},[current?.id,current?.revision,year,level]);
  useEffect(()=>{let live=true;
    Promise.all([api(root+"admission-gateway"),api(root+"admission-fees"),api(root+"admission-payments")])
    .then(([g,f,p])=>{if(live){setGateway(g);setFees(f.fees||[]);setPayments(p.payments||[]);}})
    .catch(e=>{if(live)setNotice(e.message)});
    return()=>{live=false};
  },[schoolId]);
  async function run(fn){
    setBusy(true);setNotice("");
    try{await fn()}catch(e){setNotice(e.message)}finally{setBusy(false)}
  }
  if(!gateway)return <p role="status">{notice||"Chargement des frais et du prestataire…"}</p>;
  return <section className="yp-settings" aria-label="Tarifs et paiement des candidatures">
    <h3>Frais d'admission · Libreville / Gabon</h3>
    <p>Ce sont des <strong>frais de dossier d'admission</strong>, indépendants des frais de scolarité.
       Ils sont configurables par année et niveau : maternelle, primaire, collège, lycée ou groupe scolaire.</p>
    <form onSubmit={e=>{e.preventDefault();run(async()=>{
      if(!year||!level)throw Error("Année et niveau obligatoires.");
      const item=await api(root+"admission-fees",{
        year,level,revision:current?.revision??0,amount_xaf:Number(amount),active,
      });
      setFees(old=>[...old.filter(f=>f.id!==item.id),item]);
      setNotice("Tarif d'admission enregistré. Les demandes antérieures conservent leur montant.");
    });}}>
      <div className="yp-two">
        <label className="yp-field">Année<select value={year} onChange={e=>setYear(e.target.value)}>
          {years.filter(y=>y.active).map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
        </select></label>
        <label className="yp-field">Niveau<select value={level} onChange={e=>setLevel(e.target.value)}>
          {levels.map(l=><option key={l.id} value={l.id}>{l.label}</option>)}
        </select></label>
        <label className="yp-field">Montant du dossier (FCFA/XAF)
          <input type="number" required min="100" max="10000000" step="1" value={amount} onChange={e=>setAmount(e.target.value)}/>
        </label>
      </div>
      <label className="yp-toggle"><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>
        Activer le tarif pour cette année et ce niveau</label>
      <button type="submit" className="yp-button yp-primary" disabled={busy||!year||!level}>Enregistrer les frais d'admission</button>
    </form>
    <h3 style={{marginTop:22}}>Encaissement Mobile Money propre à votre école</h3>
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
      <p>Webhook à déclarer dans PayCentral : <code>{typeof window==="undefined"?"":window.location.origin+"/api/v1/parents/paycentral/webhook"}</code></p>
      <label className="yp-toggle"><input type="checkbox" checked={gateway.enabled}
        onChange={e=>setGateway(v=>({...v,enabled:e.target.checked}))}/> Activer cette passerelle</label>
      {!gateway.encryption_ready&&<p className="yp-error">La clé de chiffrement serveur n'est pas encore configurée. Aucune clé marchande ne sera enregistrée.</p>}
      {gateway.mode==="live"&&!gateway.live_enabled_by_platform&&<p className="yp-error">Paiement réel désactivé par sécurité au niveau plateforme.</p>}
      <button className="yp-button yp-primary" type="submit" disabled={busy}>Enregistrer la passerelle</button>
    </form>
    <h3 style={{marginTop:22}}>Transactions de candidature</h3>
    <p>Vérifiez toujours le statut de paiement auprès du prestataire. Les transactions en simulation ne représentent pas des encaissements réels.</p>
    <button type="button" className="yp-button" disabled={busy} onClick={()=>run(async()=>{
      const response=await api(root+"admission-payments");
      setPayments(response.payments||[]);setNotice("Liste actualisée.");
    })}>Actualiser les transactions</button>
    {payments.length===0?<p>Aucune tentative de paiement en ligne.</p>:
      <div style={{overflowX:"auto"}}><table style={{width:"100%",marginTop:12}}>
        <thead><tr><th>Référence</th><th>Montant</th><th>Canal</th><th>État</th><th>Mode</th></tr></thead>
        <tbody>{payments.map(p=><tr key={p.id}>
          <td><code>{p.merchant_reference}</code></td>
          <td>{Number(p.amount_xaf).toLocaleString("fr-FR")} FCFA</td>
          <td>{p.channel}</td><td>{p.state}</td><td>{p.provider_mode==="sandbox"?"SIMULATION":"Réel"}</td>
        </tr>)}</tbody>
      </table></div>}
    {notice&&<p role="status">{notice}</p>}
  </section>;
}
