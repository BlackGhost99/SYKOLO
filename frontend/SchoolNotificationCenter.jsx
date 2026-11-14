import React, {useCallback, useEffect, useState} from "react";
import {PageHeader, Card, Button} from "./yem-ui.jsx";

async function inboxApi(path, body, method) {
  if (body !== undefined) await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const token=document.cookie.split("; ").find(item=>item.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path,{
    method: method||(body===undefined?"GET":"POST"),
    credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  if(!response.headers.get("content-type")?.includes("application/json"))throw Error("Service de notifications indisponible.");
  const result=await response.json();
  if(!response.ok)throw Error(result.error||"Action impossible.");
  return result;
}

/** A real school inbox: one click from the bell, no settings navigation required. */
export default function SchoolNotificationCenter({schoolId, onUnread}) {
  const base="schools/"+schoolId;
  const [data,setData]=useState({requests:[],messages:[],unread:0});
  const [selected,setSelected]=useState(null);
  const [candidates,setCandidates]=useState([]);
  const [guardian,setGuardian]=useState("");
  const [verified,setVerified]=useState(false);
  const [compose,setCompose]=useState(null);
  const [target,setTarget]=useState("");
  const [draft,setDraft]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [feedback,setFeedback]=useState("");
  const load=useCallback(async()=>{
    const response=await inboxApi(base+"/notification-inbox");
    setData(response);
    onUnread?.(response.unread||0);
    return response;
  },[base,onUnread]);

  useEffect(()=>{
    let active=true;
    inboxApi(base+"/notification-inbox").then(result=>{
      if(active){setData(result);onUnread?.(result.unread||0);}
    }).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;};
  },[base,onUnread]);

  async function run(action) {
    setBusy(true);setError("");setFeedback("");
    try{await action();await load();}
    catch(e){setError(e.message);}
    finally{setBusy(false);}
  }
  async function examine(item){
    setBusy(true);setError("");setFeedback("");setSelected(item);setCandidates([]);setGuardian("");setVerified(false);
    try{
      const result=await inboxApi(base+"/notification-inbox/requests/"+item.id+"/candidates");
      setCandidates(result.candidates||[]);
      if(!(result.candidates||[]).length)setError("Aucun dossier ne correspond : vérifiez le matricule dans les fiches élèves.");
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  function answer(item){
    setCompose({username:item.username||item.parent_username,request_id:item.id&&item.student_code!==undefined?item.id:item.request_id||null});
    setTarget(item.username||item.parent_username||"");
    setDraft("");
  }

  return <>
    <PageHeader title="Notifications" subtitle="Demandes à traiter, échanges avec les familles et messages du système YEM"/>
    <div className="yd-real-body">
      <Card title="Demandes de rattachement à vérifier" icon="bell">
        <p className="hint">Chaque demande est une notification du système à l’établissement. La confirmation d’identité reste obligatoire.</p>
        {!data.requests.length&&<p>Aucune demande en attente.</p>}
        {data.requests.map(item=><article className="yp-request" key={item.id}>
          <strong>{item.first_name} {item.last_name}</strong>
          <p>Matricule déclaré : <strong>{item.student_code||"non renseigné"}</strong> · Responsable : {item.account_name||item.guardian_name}</p>
          <p>Compte YEM Parents : {item.username} · Téléphone : {item.contact_phone||"non renseigné"}</p>
          <div className="actions">
            <Button disabled={busy} onClick={()=>examine(item)}>Examiner et accepter</Button>
            <Button disabled={busy} onClick={()=>answer(item)}>Écrire au parent</Button>
            <Button disabled={busy} onClick={()=>run(async()=>{
              if(!window.confirm("Refuser la demande après vérification ?"))return;
              await inboxApi(base+"/parent-existing-requests/"+item.id,{status:"rejected"},"PATCH");
              if(selected?.id===item.id)setSelected(null);
              setFeedback("La décision a été communiquée au parent.");
            })}>Refuser</Button>
          </div>
          {selected?.id===item.id&&<section className="yp-pane" aria-label="Vérifier la demande">
            <h3>Confirmer le responsable légal</h3>
            <p>Comparez l'identité du compte avec le dossier de l'élève et son justificatif.</p>
            <label className="field">Élève et responsable vérifié
              <select value={guardian} onChange={e=>{setGuardian(e.target.value);setVerified(false);}}>
                <option value="">Choisir le bon responsable légal…</option>
                {candidates.flatMap(s=>s.guardians.map(g=>
                  <option value={g.id} key={g.id}>{s.student_name} · {s.student_code} — {g.name} ({g.relationship||"Responsable"})</option>
                ))}
              </select>
            </label>
            <label className="field"><input type="checkbox" checked={verified}
              disabled={!guardian||busy} onChange={e=>setVerified(e.target.checked)}/>
              Je confirme avoir vérifié l'identité du parent et le bon matricule scolaire.
            </label>
            <div className="actions">
              <Button primary disabled={!guardian||!verified||busy} onClick={()=>run(async()=>{
                await inboxApi(base+"/parent-links",{
                  guardian,username:item.username,identity_verified:true,request_id:item.id,
                });
                setSelected(null);setCandidates([]);setGuardian("");setVerified(false);
                setFeedback("Demande acceptée : accès parent activé et notification envoyée.");
              })}>Accepter et activer l’accès</Button>
              <Button disabled={busy} onClick={()=>setSelected(null)}>Annuler</Button>
            </div>
          </section>}
        </article>)}
      </Card>
      <Card title="Messages des familles et du système" icon="bell">
        <Button disabled={busy} onClick={()=>run(async()=>{setFeedback("Notifications actualisées.");})}>Actualiser</Button>
        {!data.messages.length&&<p>Aucun message reçu.</p>}
        {data.messages.map(item=><article key={item.id} className="yp-request">
          <strong>{item.origin==="parent"?"Message d'un parent":"Notification YEM"}</strong>
          <p>{item.parent_username} · {item.message}</p>
          <small>{new Date(item.at).toLocaleString("fr-GA")}{item.read?" · Lu":" · Non lu"}</small>
          <div className="actions">
            {!item.read&&<Button disabled={busy} onClick={()=>run(async()=>{
              await inboxApi(base+"/notification-inbox/"+item.id,{read:true},"PATCH");
            })}>Marquer comme lu</Button>}
            <Button disabled={busy} onClick={()=>answer(item)}>Répondre</Button>
          </div>
        </article>)}
      </Card>
      <Card title="Contacter un parent" icon="users">
        <p className="hint">Vous pouvez écrire au titulaire d’une demande ou d’un dossier familial vérifié dans cet établissement.</p>
        <form onSubmit={e=>{e.preventDefault();run(async()=>{
          await inboxApi(base+"/notification-inbox",{
            username:target.trim(),message:draft.trim(),...(compose?.request_id?{request_id:compose.request_id}:{}),
          });
          setDraft("");setCompose(null);setFeedback("Message transmis au parent dans YEM Familles.");
        });}}>
          <label className="field">Identifiant du compte parent
            <input required maxLength={150} autoComplete="off" value={target}
              onChange={e=>{setTarget(e.target.value);setCompose(null);}}/>
          </label>
          <label className="field">Message
            <textarea required maxLength={700} rows={3} value={draft} onChange={e=>setDraft(e.target.value)}
              placeholder="Votre message à la famille…"/>
          </label>
          <Button type="submit" primary disabled={busy||!target.trim()||!draft.trim()}>Envoyer la notification</Button>
        </form>
      </Card>
      {error&&<p className="pc-alert" role="alert">{error}</p>}
      {feedback&&<p role="status">{feedback}</p>}
    </div>
  </>;
}
