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

/** Readiness is informative: the server independently validates every decision. */
export function AdmissionDecisionReadiness({application}){
  if(!["submitted","review"].includes(application.status))return null;
  if(application.acceptance_blocker)return <p role="status" className="ar-missing">
    Admission non prête : {Object.entries(DOCUMENTS).reduce((label,[key,name])=>label.replaceAll(key,name),application.acceptance_blocker)}
  </p>;
  return <p role="status" className="ar-message">
    Pièces et critères d’admission vérifiés. La direction peut statuer ; les frais ou la bourse restent distincts de cette décision.
  </p>;
}

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
      <h4>Pièces obligatoires selon la voie</h4>
      <p className="hint">Cochez uniquement les pièces que l'établissement exige réellement (par exemple acte de naissance ou derniers bulletins). Les autres pièces restent facultatives. La preuve d'un concours ou d'une affectation reste obligatoire, même si elle n'est pas cochée ci-dessous.</p>
      {canDecide&&<button type="button" className="ar-secondary" onClick={()=>setPolicy(old=>({...old,required_documents:{...old.required_documents,...Object.fromEntries(old.enabled_routes.map(route=>[route,[...new Set([...(old.required_documents[route]||[]),"birth_certificate",...(route==="direct"?[]:["previous_reports"])])]]))}}))}>Préremplir les pièces habituelles (modifiable avant enregistrement)</button>}
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


function DocumentReferenceForm({codes,allowCustom=false,application,perform,path,api,busy}){
  const [code,setCode]=useState(codes[0]||"");
  const [customCode,setCustomCode]=useState("");
  const [reference,setReference]=useState("");
  const choicesKey=codes.join("|");
  useEffect(()=>{setCode(current=>codes.includes(current)?current:(codes[0]||""));},[choicesKey]);
  const validCode=code==="_other"?/^[a-z][a-z0-9_-]{0,47}$/.test(customCode):codes.includes(code);
  return <div className="ar-attach">
    <div className="two">
      <label className="field">Type de justificatif
        <select value={code} onChange={e=>setCode(e.target.value)}>
          {codes.length===0&&<option value="">Aucune pièce supplémentaire disponible</option>}
          {codes.map(k=><option key={k} value={k}>{DOCUMENTS[k]||k}</option>)}
          {allowCustom&&<option value="_other">Autre pièce</option>}
        </select>
      </label>
      {code==="_other"&&<label className="field">Code personnalisé
        <input maxLength={48} pattern="[a-z][a-z0-9_-]*" value={customCode} onChange={e=>setCustomCode(e.target.value)}/>
      </label>}
      <label className="field">Référence du justificatif
        <input maxLength={180} value={reference} onChange={e=>setReference(e.target.value)}
          placeholder="N° ou référence du document consulté"/>
      </label>
    </div>
    <button type="button" disabled={busy||!reference.trim()||!validCode} onClick={async()=>{
      const response=await perform(()=>api(path+"/documents",{
        revision:application.revision,code:code==="_other"?customCode:code,reference:reference.trim()
      }));
      if(response){setReference("");setCustomCode("");}
    }}>Ajouter cette référence</button>
    <p className="hint">Il s'agit d'une référence de document présenté à l'établissement, pas d'un téléversement de pièce sensible.</p>
  </div>;
}

export function AdmissionProofPanel({api,base,application,canDecide=false,canPrepare=false,onUpdated}){
  const [record,setRecord]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
  const [result,setResult]=useState("pending"),[resultRef,setResultRef]=useState(""),[authority,setAuthority]=useState("");
  const [resultReason,setResultReason]=useState(""),[reviewReason,setReviewReason]=useState("");
  const path=base+"/"+application.id;
  useEffect(()=>{
    setResult(application.external_result||"pending");
    setResultRef(application.route_reference||"");
    setAuthority(application.orientation_authority||"");
    setResultReason("");setMessage("");
  },[application.id,application.external_result,application.route_reference,application.orientation_authority]);
  useEffect(()=>{
    let active=true;
    api(path+"/documents").then(x=>{if(active)setRecord(x)})
      .catch(e=>{if(active)setMessage(e.message)});
    return()=>{active=false};
  },[api,path,application.revision]);
  const active=application.status==="submitted"||application.status==="review";
  const canRecord=canDecide||canPrepare;
  const editable=active&&canRecord;
  const docs=record?.documents||[];
  const required=application.required_documents||[];
  const missing=required.filter(k=>!docs.some(d=>d.code===k&&d.status==="verified"));
  const toAdd=required.filter(k=>!docs.some(d=>d.code===k));
  const optionalCodes=Object.keys(DOCUMENTS).filter(k=>!required.includes(k)&&!docs.some(d=>d.code===k));
  const optionalRegistered=docs.some(d=>!required.includes(d.code));
  const canSaveResult=Boolean(resultReason.trim())&&(result!=="eligible"||Boolean(resultRef.trim()))&&
    (application.route!=="orientation"||result!=="eligible"||Boolean(authority.trim()));
  async function perform(fn){
    setBusy(true);setMessage("");
    try{const response=await fn();await onUpdated();return response;}
    catch(e){setMessage(e.message);return null;}
    finally{setBusy(false);}
  }
  return <div className="ar-proof">
    <h4>1. Vérifier la voie d'admission</h4>
    <p className="hint">Parcours : <strong>{ROUTES[application.route]||application.route}</strong>
      {application.origin_school?" · Établissement d'origine : "+application.origin_school:""}</p>
    {application.route!=="direct"?<div className="ar-outcome">
      <p className="hint">Renseignez le résultat vérifié, sa référence et le motif du contrôle. Cela ne constitue pas encore une admission.</p>
      <div className="two">
        <label className="field">Éligibilité déclarée
          <select disabled={!editable||busy} value={result} onChange={e=>setResult(e.target.value)}>
            <option value="pending">En attente de vérification</option>
            <option value="eligible">Éligible / admis à l'examen</option>
            <option value="ineligible">Non éligible / non admis</option>
          </select>
        </label>
        <label className="field">Référence du concours / décision {result==="eligible"?"(obligatoire)":""}
          <input disabled={!editable||busy} maxLength={140} value={resultRef} onChange={e=>setResultRef(e.target.value)}
            placeholder="Référence vérifiable du résultat ou de la décision"/>
        </label>
        {application.route==="orientation"&&<label className="field">Autorité d'orientation
          <input disabled={!editable||busy} maxLength={120} value={authority} onChange={e=>setAuthority(e.target.value)}
            placeholder="Ex. Commission d'orientation"/>
        </label>}
      </div>
      {editable&&<>
        <label className="field">Motif de validation du résultat (obligatoire)
          <textarea maxLength={280} rows={2} value={resultReason} onChange={e=>setResultReason(e.target.value)}
            placeholder="Ex. Résultat vérifié sur le procès-verbal du concours"/>
        </label>
        <button disabled={busy||!canSaveResult} type="button" onClick={()=>perform(()=>
          api(path+"/eligibility",{revision:application.revision,result,route_reference:resultRef,
            orientation_authority:application.route==="orientation"?authority:"",reason:resultReason.trim()}))}>
          Enregistrer l'éligibilité
        </button>
        {!canSaveResult&&<p className="ar-help">Pour activer : renseignez le motif du contrôle
          {result==="eligible"?" et la référence du résultat":""}
          {application.route==="orientation"&&result==="eligible"?" ainsi que l'autorité d'orientation":""}.</p>}
      </>}
    </div>:<p className="ar-message">Inscription directe : aucun résultat de concours à enregistrer.</p>}

    <h4>2. Vérifier les pièces réellement obligatoires</h4>
    {required.length===0?<p className="ar-message">Aucun justificatif supplémentaire exigé pour ce parcours. Les autres pièces sont facultatives.</p>:<>
      <p className="ar-required">Pièces exigées : {required.map(k=>DOCUMENTS[k]||k).join(" · ")}</p>
      {!!missing.length&&<p className="ar-missing">Justificatifs non vérifiés : {missing.map(k=>DOCUMENTS[k]||k).join(" · ")}</p>}
      {!missing.length&&<p className="ar-message">Toutes les pièces obligatoires sont vérifiées.</p>}
    </>}
    {editable&&toAdd.length>0&&<>
      <p className="hint">Ajoutez d'abord la référence des pièces exigées ci-dessus.</p>
      <DocumentReferenceForm codes={toAdd} application={application} perform={perform} path={path} api={api} busy={busy}/>
    </>}
    {docs.length>0&&<>
      <h4>Documents enregistrés et contrôle</h4>
      {active&&canDecide&&<label className="field">Motif de vérification documentaire (obligatoire pour vérifier ou refuser)
        <textarea maxLength={280} rows={2} value={reviewReason} onChange={e=>setReviewReason(e.target.value)}
          placeholder="Ex. Original du document examiné par la direction"/>
      </label>}
      {active&&canPrepare&&!canDecide&&<p className="hint">Le secrétariat prépare les justificatifs ; la direction en confirme la validité.</p>}
      <div className="ar-document-list">{docs.map(d=><div key={d.id} className="ar-document">
        <div><strong>{DOCUMENTS[d.code]||d.code}{required.includes(d.code)?" · Obligatoire":" · Facultatif"}</strong>
          <small>Référence : {d.reference}</small>
          <small>Contrôle : {d.status==="verified"?"Vérifié":d.status==="rejected"?"Non conforme":"En attente"}
            {d.review_reason?" — "+d.review_reason:""}</small>
        </div>
        {active&&canDecide&&<div className="ar-review-actions">
          <button disabled={busy||!reviewReason.trim()} type="button" onClick={()=>perform(()=>
            api(path+"/documents/"+d.id+"/review",{revision:application.revision,status:"verified",reason:reviewReason.trim()}))}>
            Vérifier
          </button>
          <button disabled={busy||!reviewReason.trim()} type="button" onClick={()=>perform(()=>
            api(path+"/documents/"+d.id+"/review",{revision:application.revision,status:"rejected",reason:reviewReason.trim()}))}>
            Non conforme
          </button>
        </div>}
      </div>)}</div>
    </>}
    {editable&&<details className="ar-options">
      <summary>Options avancées — ajouter une pièce complémentaire (facultatif)</summary>
      <p className="hint">Ces documents ne bloquent pas l'admission, sauf si l'établissement les a configurés comme obligatoires.</p>
      <DocumentReferenceForm codes={optionalCodes} allowCustom application={application}
        perform={perform} path={path} api={api} busy={busy}/>
    </details>}
    {!editable&&optionalRegistered&&<p className="hint">Les pièces complémentaires restent consultables dans l'historique du dossier.</p>}
    {message&&<p role="status" className="ar-message">{message}</p>}
  </div>;
}
