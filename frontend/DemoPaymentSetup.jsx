import React, {useEffect,useMemo,useState} from "react";

async function request(path, body) {
  if(body!==undefined)await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const token=document.cookie.split("; ").find(c=>c.startsWith("csrftoken="))?.split("=")[1]||"";
  const res=await fetch("/api/v1/"+path,{method:body===undefined?"GET":"POST",
    credentials:"same-origin",headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},
    body:body===undefined?undefined:JSON.stringify(body)});
  const data=await res.json();
  if(!res.ok)throw Error(data.error||"Configuration refusée.");
  return data;
}

export default function DemoPaymentSetup({schoolId,years=[],classes=[]}){
  const [policy,setPolicy]=useState(null);
  const [year,setYear]=useState("");
  const [level,setLevel]=useState("");
  const [amount,setAmount]=useState("2500");
  const [allowed,setAllowed]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const base="schools/"+schoolId+"/demo-admission-payments";
  useEffect(()=>{let live=true;request(base).then(x=>{
    if(live){setPolicy(x);setAllowed(x.allowed_usernames.join(", "));}
  }).catch(err=>{if(live)setMessage(err.message)});return()=>{live=false};},[base]);
  useEffect(()=>{if(!year&&years.length)setYear(String(years.find(y=>y.active)?.id||years[0]?.id||""));},[year,years]);
  const levels=useMemo(()=>{
    const found=new Set();
    return classes.filter(c=>c.year===year&&!found.has(c.level)&&found.add(c.level))
      .map(c=>({id:c.level,name:c.level_name||c.name}));
  },[classes,year]);
  useEffect(()=>{if(!levels.some(c=>c.id===level))setLevel(levels[0]?.id||"");},[level,levels]);
  const key=year&&level?year+":"+level:"";
  const stored=policy?.level_amounts_xaf?.[key];
  useEffect(()=>setAmount(String(stored??2500)),[key,stored]);
  if(!policy)return <p role="status">{message||"Chargement du mode simulation…"}</p>;
  async function save(e){
    e.preventDefault();setBusy(true);setMessage("");
    try {
      if(!year||!level)throw Error("Année et niveau obligatoires.");
      const amountNumber=Number(amount);
      if(!Number.isInteger(amountNumber)||amountNumber<100||amountNumber>10000000)throw Error("Montant fictif invalide.");
      const names=allowed.split(/[,;\n]/).map(v=>v.trim()).filter(Boolean);
      const result=await request(base,{
        revision:policy.revision,enabled:policy.enabled,
        level_amounts_xaf:{...policy.level_amounts_xaf,[key]:amountNumber},
        allowed_usernames:names,
      });
      setPolicy(result);setAllowed(result.allowed_usernames.join(", "));
      setMessage("Configuration de simulation enregistrée. Aucun argent ne sera encaissé.");
    }catch(err){setMessage(err.message)}finally{setBusy(false)}
  }
  return <section className="yp-settings" aria-label="Paiements de démonstration" style={{marginTop:24}}>
    <h3>Simulation interne YEM — sans argent</h3>
    <p>Pour les recettes uniquement. Configurez le montant fictif par année et niveau,
      puis indiquez les identifiants des parents fictifs autorisés. Les paiements simulés
      restent <strong>en dehors de la caisse et des reçus réels</strong>.</p>
    <form onSubmit={save}>
      <div className="yp-two">
        <label className="yp-field">Année scolaire
          <select value={year} onChange={e=>setYear(e.target.value)}>
            {years.filter(y=>y.active).map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
          </select>
        </label>
        <label className="yp-field">Niveau
          <select value={level} onChange={e=>setLevel(e.target.value)}>
            {levels.map(v=><option key={v.id} value={v.id}>{v.name}</option>)}
          </select>
        </label>
        <label className="yp-field">Montant fictif (FCFA)
          <input type="number" required min="100" max="10000000" value={amount}
            onChange={e=>setAmount(e.target.value)}/>
        </label>
      </div>
      <label className="yp-field">Identifiants de parents fictifs autorisés (séparés par des virgules)
        <textarea rows={2} value={allowed} onChange={e=>setAllowed(e.target.value)}
          placeholder="yemtest-parent-s, yemtest-parent-c"/>
      </label>
      <label className="yp-toggle"><input type="checkbox" checked={policy.enabled}
        onChange={e=>setPolicy(v=>({...v,enabled:e.target.checked}))}/>
        Autoriser les simulations pour ces seuls comptes</label>
      <button disabled={busy||!year||!level} className="yp-button yp-primary">Enregistrer la simulation</button>
      <p className="yp-muted">Un succès en simulation n'est jamais une preuve de paiement ni une admission.</p>
      {message&&<p role="status">{message}</p>}
    </form>
  </section>;
}
