import React, {useEffect,useState} from "react";
import "./admission-routes.css";

export const ROUTES = {
  direct:"Inscription directe",
  concours:"Concours ou test d'admission",
  orientation:"Affectation / orientation",
};
export const DOCUMENTS = {
  birth_certificate:"Acte de naissance",
  previous_reports:"Bulletins précédents",
  school_certificate:"Attestation de scolarité",
  guardian_id:"Pièce du représentant légal",
  health_record:"Carnet de santé (si exigé)",
  concours_result:"Justificatif du résultat au concours",
  orientation_decision:"Attestation ou décision d'affectation",
};
const basicDocs = Object.keys(DOCUMENTS);
const emptyDocs = ()=>({direct:[],concours:[],orientation:[]});

export function AdmissionPolicyEditor({api,base,year,level,canDecide,onSaved}){
  const [policy,setPolicy]=useState(null);
  const [busy,setBusy]=useState(false),[message,setMessage]=useState("");
  const [newCode,setNewCode]=useState("");
  const [newCodeRoute,setNewCodeRoute]=useState("direct");
  useEffect(()=>{
    let live=true;setPolicy(null);setMessage("");
    if(!year)return;
    const params=new URLSearchParams({year,...(level?{level}:{})});
    api(base+"/policy?"+params.toString()).then(data=>{
      if(live)setPolicy({...data,required_documents:{...emptyDocs(),...data.required_documents}});
    }).catch(e=>{if(live)setMessage(e.message)});
    return()=>{live=false;};
  },[api,base,year,level]);
  if(!year)return <p className="hint">Sélectionnez une année scolaire pour les paramètres d'admission.</p>;
  if(!policy)return <p className="hint">{message||"Chargement des règles d'admission…"}</p>;
  const update=(part,value)=>setPolicy(old=>({...old,[part]:value}));
  function toggleRoute(route){
    update("enabled_routes",policy.enabled_routes.includes(route)?
      policy.enabled_routes.filter(x=>x!==route):[...policy.enabled_routes,route]);
  }
  function toggleDoc(route,code){
    const docs=policy.required_documents[route]||[];
    update("required_documents",{...policy.required_documents,
      [route]:docs.includes(code)?docs.filter(x=>x!==code):[...docs,code]});
  }
  async function save(e){
    e.preventDefault();setBusy(true);setMessage("");
    try{
      const response=await api(base+"/policy",{
        year,level:level||null,revision:policy.scope_revision,
        enabled_routes:policy.enabled_routes,
        required_documents:policy.required_documents
      });
      setPolicy({...response,required_documents:{...emptyDocs(),...response.required_documents}});
      onSaved?.(response);
      setMessage("Règles enregistrées pour ce niveau et cette année scolaire.");
    }catch(e){setMessage(e.message)}finally{setBusy(false)}
  }
  return <div className="ar-policy">
    <p className="hint">Portée : {level?"niveau scolaire sélectionné":"tous les niveaux de l'année"}.
      Les changements concernent les futures candidatures ; les pièces déjà exigées restent attachées aux dossiers existants.</p>
    <form onSubmit={save}>
      <div className="ar-route-options">{Object.entries(ROUTES).map(([code,label])=>
        <label key={code} className="ar-route-option">
          <input type="checkbox" disabled={!canDecide} checked={policy.enabled_routes.includes(code)}
            onChange={()=>toggleRoute(code)}/> <b>{label}</b>
        </label>
      )}</div>
      <h4>Pièces supplémentaires obligatoires selon la voie</h4>
      <p className="hint">La preuve d'un concours ou d'une affectation reste obligatoire, même si elle n'est pas cochée ci-dessous.</p>
      <div className="ar-policy-grids">{Object.keys(ROUTES).filter(k=>policy.enabled_routes.includes(k)).map(route=>
        <fieldset key={route}><legend>{ROUTES[route]}</legend>
          {[...new Set([...basicDocs,...(policy.required_documents[route]||[])])].map(code=>
            <label key={code} className="ar-doc-check">
              <input type="checkbox" disabled={!canDecide}
                checked={(policy.required_documents[route]||[]).includes(code)}
                onChange={()=>toggleDoc(route,code)}/>
              <span>{DOCUMENTS[code]||code}</span>
            </label>)}
        </fieldset>)}</div>
      {canDecide&&<div className="ar-custom">
        <label className="field">Voie concernée par cette pièce
          <select value={policy.enabled_routes.includes(newCodeRoute)?newCodeRoute:policy.enabled_routes[0]}
            onChange={e=>setNewCodeRoute(e.target.value)}>
            {policy.enabled_routes.map(r=><option key={r} value={r}>{ROUTES[r]}</option>)}
          </select>
        </label>
        <label className="field">Nouveau code de pièce personnalisée (minuscules, chiffres et tirets)
          <input pattern="[a-z][a-z0-9_-]*" maxLength={48} value={newCode} onChange={e=>setNewCode(e.target.value)}
            placeholder="ex. autorisation_parentale"/>
        </label>
        <button type="button" disabled={!/^[a-z][a-z0-9_-]{0,47}$/.test(newCode)} onClick={()=>{
          const route=policy.enabled_routes.includes(newCodeRoute)?newCodeRoute:policy.enabled_routes[0];if(!route)return;
          setPolicy(old=>({...old,required_documents:{...old.required_documents,
            [route]:[...new Set([...(old.required_documents[route]||[]),newCode])]}}));
          setNewCode("");
        }}>Ajouter à la voie choisie</button>
      </div>}
      {canDecide&&<button type="submit" disabled={busy||!policy.enabled_routes.length}>
        {busy?"Enregistrement…":"Enregistrer les règles d'admission"}
      </button>}
    </form>
    {message&&<p role="status" className="ar-message">{message}</p>}
  </div>;
}

export function AdmissionProofPanel({api,base,application,canDecide,onUpdated}){
  const [record,setRecord]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
  const [code,setCode]=useState(""),[customCode,setCustomCode]=useState(""),[reference,setReference]=useState("");
  const [result,setResult]=useState("pending"),[resultRef,setResultRef]=useState(""),[authority,setAuthority]=useState("");
  const [reason,setReason]=useState("");
  const path=base+"/"+application.id;
  useEffect(()=>{
    let active=true;
    setResult(application.external_result||"pending");
    setResultRef(application.route_reference||"");
    setAuthority(application.orientation_authority||"");
    setReason("");setMessage("");
    return()=>{active=false};
  },[application.id,application.external_result,application.route_reference,application.orientation_authority]);
  useEffect(()=>{
    let active=true;
    api(path+"/documents").then(x=>{if(active)setRecord(x)}).catch(e=>{if(active)setMessage(e.message)});
    return()=>{active=false};
  },[api,path,application.revision]);
  const active=application.status==="submitted"||application.status==="review";
  const docs=record?.documents||[];
  const missing=(application.required_documents||[]).filter(k=>!docs.some(d=>d.code===k&&d.status==="verified"));
  async function perform(fn){
    setBusy(true);setMessage("");
    try{const x=await fn();await onUpdated();return x;}
    catch(e){setMessage(e.message);return null;}
    finally{setBusy(false);}
  }
  return <div className="ar-proof">
    <h4>Parcours : {ROUTES[application.route]||application.route}</h4>
    {application.origin_school&&<p className="hint">Établissement d'origine : {application.origin_school}</p>}
    {application.route!=="direct"&&<div className="ar-outcome">
      <h4>{application.route==="concours"?"Résultat du concours / test":"Décision d'affectation / orientation"}</h4>
      <p className="hint">Une déclaration d'éligibilité ne vaut pas admission : la direction doit vérifier la preuve puis accepter le dossier.</p>
      <div className="two">
        <label className="field">Éligibilité déclarée
          <select disabled={!active||busy} value={result} onChange={e=>setResult(e.target.value)}>
            <option value="pending">En attente de vérification</option><option value="eligible">Éligible / admis à l'examen</option>
            <option value="ineligible">Non éligible / non admis</option>
          </select>
        </label>
        <label className="field">Référence du concours / décision
          <input disabled={!active||busy} maxLength={140} value={resultRef} onChange={e=>setResultRef(e.target.value)}
            placeholder="Référence officielle ou interne vérifiable"/>
        </label>
        {application.route==="orientation"&&<label className="field">Autorité qui a affecté l'élève
          <input disabled={!active||busy} maxLength={120} value={authority} onChange={e=>setAuthority(e.target.value)}
            placeholder="Ex. Commission d'orientation"/>
        </label>}
      </div>
      {active&&<button disabled={busy||!reason.trim()} type="button" onClick={()=>perform(()=>
        api(path+"/eligibility",{revision:application.revision,result,route_reference:resultRef,
          orientation_authority:application.route==="orientation"?authority:"",reason:reason.trim()}))}>
        Enregistrer l'éligibilité
      </button>}
    </div>}
    <h4>Pièces justificatives et vérification humaine</h4>
    <p className="hint">Phase initiale : enregistrement des références et des vérifications. Aucun fichier sensible d'enfant n'est téléchargé ici.</p>
    {application.required_documents?.length>0&&<p className="ar-required">
      À valider : {application.required_documents.map(k=>DOCUMENTS[k]||k).join(" · ")}
    </p>}
    {!!missing.length&&<p className="ar-missing">Justificatifs non vérifiés : {missing.map(k=>DOCUMENTS[k]||k).join(" · ")}</p>}
    {docs.length>0&&<div className="ar-document-list">{docs.map(d=><div key={d.id} className="ar-document">
      <div><strong>{DOCUMENTS[d.code]||d.code}</strong><small>Référence : {d.reference}</small>
        <small>Contrôle : {d.status==="verified"?"Vérifié":d.status==="rejected"?"Refusé":"À contrôler"}
          {d.review_reason?" — "+d.review_reason:""}</small></div>
      {active&&canDecide&&<div className="ar-review-actions">
        <button disabled={busy||!reason.trim()} type="button" onClick={()=>perform(()=>
          api(path+"/documents/"+d.id+"/review",{revision:application.revision,status:"verified",reason:reason.trim()}))}>
          Vérifier
        </button>
        <button disabled={busy||!reason.trim()} type="button" onClick={()=>perform(()=>
          api(path+"/documents/"+d.id+"/review",{revision:application.revision,status:"rejected",reason:reason.trim()}))}>
          Non conforme
        </button>
      </div>}
    </div>)}</div>}
    {active&&<div className="ar-attach">
      <h4>Enregistrer une référence de justificatif</h4>
      <div className="two">
        <label className="field">Type de justificatif
          <select value={code} onChange={e=>setCode(e.target.value)}><option value="">Choisir une pièce</option>
            {[...new Set([...Object.keys(DOCUMENTS),...(application.required_documents||[])])]
              .filter(k=>!docs.some(d=>d.code===k)).map(k=><option key={k} value={k}>{DOCUMENTS[k]||k}</option>)}
            <option value="_other">Autre pièce</option>
          </select>
        </label>
        {code==="_other"&&<label className="field">Code personnalisé
          <input maxLength={48} pattern="[a-z][a-z0-9_-]*" value={customCode} onChange={e=>setCustomCode(e.target.value)}/>
        </label>}
        <label className="field">Référence du justificatif
          <input maxLength={180} value={reference} onChange={e=>setReference(e.target.value)}
            placeholder="Ex. Copie du document consultée au secrétariat"/>
        </label>
      </div>
      <button type="button" disabled={busy||!reference.trim()||!(code==="_other"?/^[a-z][a-z0-9_-]{0,47}$/.test(customCode):code)}
        onClick={async()=>{const res=await perform(()=>api(path+"/documents",{
          revision:application.revision,code:code==="_other"?customCode:code,reference:reference.trim()
        }));if(res){setReference("");setCode("");setCustomCode("");}}}>
        Ajouter cette référence
      </button>
    </div>}
    {active&&<label className="field">Motif de contrôle / mise à jour du dossier (obligatoire)
      <textarea maxLength={280} value={reason} onChange={e=>setReason(e.target.value)}
        placeholder="Ex. Attestation contrôlée auprès de la direction"/>
    </label>}
    {message&&<p role="status" className="ar-message">{message}</p>}
  </div>;
}
