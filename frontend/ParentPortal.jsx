import React, { useEffect, useState } from "react";
import ParentDiscovery from "./ParentDiscovery.jsx";
import PWAInstall from "./PWAInstall.jsx";
import SingPayPayment from "./SingPayPayment.jsx";

async function portalApi(path, body, method) {
  if (body !== undefined) await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
  const token = document.cookie.split("; ").find(x => x.startsWith("csrftoken="))?.split("=")[1] || "";
  const response = await fetch("/api/v1/" + path, {
    method: method || (body === undefined ? "GET" : "POST"),
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json", "X-CSRFToken": token },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw Error("Service non disponible. Vérifiez votre connexion.");
  }
  const result = await response.json();
  if (!response.ok) throw Error(result.error || "Accès refusé.");
  return result;
}

const DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
function Card({title, children}) {
  return <section className="yd-card" style={{padding:"1rem",marginBottom:"1rem"}}>
    <h3>{title}</h3>{children}
  </section>;
}
function Message({children}) {return children?<p role="status" aria-live="polite">{children}</p>:null;}

export default function ParentPortal() {
  const [children,setChildren] = useState([]);
  const [selected,setSelected] = useState("");
  const [tab,setTab] = useState("reports");
  const [detail,setDetail] = useState(null);
  const [schools,setSchools] = useState([]);
  const [school,setSchool] = useState("");
  const [links,setLinks] = useState([]);
  const [students,setStudents] = useState([]);
  const [guardians,setGuardians] = useState([]);
  const [chosenStudent,setChosenStudent] = useState("");
  const [guardian,setGuardian] = useState("");
  const [username,setUsername] = useState("");
  const [access,setAccess] = useState(false);
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState("");
  const [connected,setConnected] = useState(true);
  const [isParentAccount,setIsParentAccount] = useState(false);

  async function reloadChildren() {
    const result=await portalApi("parents/children");
    setChildren(result.children||[]);
  }
  async function reloadAdmin(id) {
    const [linkData,studentsData]=await Promise.all([
      portalApi("schools/"+id+"/parent-links"),
      portalApi("schools/"+id+"/students"),
    ]);
    setLinks(linkData.links||[]);
    setStudents(studentsData.students||[]);
    setAccess(true);
  }
  useEffect(()=>{
    let alive=true;
    Promise.all([
      portalApi("parents/children"),
      portalApi("schools").catch(()=>({schools:[]})),
    ]).then(([family,admin])=>{
      if (!alive)return;
      setChildren(family.children||[]);
      setIsParentAccount(!!family.parent_role);
      setSchools(admin.schools||[]);
    }).catch(error=>{if(alive){setConnected(false);setMessage(error.message);}});
    return()=>{alive=false};
  },[]);
  useEffect(()=>{
    let alive=true;
    setDetail(null);
    if(!selected)return()=>{alive=false};
    portalApi("parents/children/"+selected+"/"+tab)
      .then(result=>{if(alive)setDetail(result)})
      .catch(error=>{if(alive){setMessage(error.message);setDetail(null);}});
    return()=>{alive=false};
  },[selected,tab]);
  useEffect(()=>{
    let alive=true;
    setAccess(false);setLinks([]);setStudents([]);setChosenStudent("");setGuardian("");
    if(school)Promise.all([
      portalApi("schools/"+school+"/parent-links"),
      portalApi("schools/"+school+"/students"),
    ]).then(([links,students])=>{
      if(!alive)return;
      setLinks(links.links||[]);setStudents(students.students||[]);setAccess(true);
    }).catch(()=>{if(alive)setAccess(false)});
    return()=>{alive=false};
  },[school]);
  useEffect(()=>{
    let alive=true;setGuardians([]);setGuardian("");
    if(school&&chosenStudent&&access)
      portalApi("schools/"+school+"/students/"+chosenStudent+"/guardians")
        .then(data=>{if(alive)setGuardians(data.guardians||[])})
        .catch(()=>{if(alive)setGuardians([])});
    return()=>{alive=false};
  },[school,chosenStudent,access]);

  async function run(fn) {
    setBusy(true);setMessage("");
    try{await fn();}catch(error){setMessage(error.message);}finally{setBusy(false);}
  }
  const current=children.find(c=>c.student===selected);
  const relatedSchools=current?.matricule_yem
    ? children.filter(child=>child.matricule_yem===current.matricule_yem)
    : [];
  const base="parents/children/"+selected;
  return <div className="yd-parent-real">
    <div className="yd-hero">
      <div><h1>Espace parents</h1>
      <p>Consultation privée de vos enfants — informations réellement publiées par l'établissement.</p></div>
    </div>
    <PWAInstall />
    <ParentDiscovery />
    {!connected&&<Card title="Connexion requise">
      <p>Connectez-vous à un compte autorisé pour accéder à l'espace parents.</p><Message>{message}</Message>
    </Card>}
    {connected&&<>
      <Card title="Mes enfants">
        {children.length===0?
          <p>Aucun enfant n'est encore lié à ce compte. Contactez votre établissement pour faire vérifier votre qualité de responsable légal.</p>
          :<label className="field">Enfant
            <select value={selected} onChange={e=>{setSelected(e.target.value);setMessage("");}}>
              <option value="">Choisir un enfant…</option>
              {children.map(c=><option key={c.student} value={c.student}>{c.last_name} {c.first_name} · {c.school_name}</option>)}
            </select>
          </label>}
      </Card>
      {current&&<Card title={current.last_name+" "+current.first_name}>
        <p>{current.school_name} · matricule {current.student_code}</p>
        {current.matricule_yem&&current.matricule_yem!==current.student_code&&<p>Identifiant permanent YEM · {current.matricule_yem}</p>}
        {relatedSchools.length>1&&<label className="field">Établissements du parcours
          <select value={selected} onChange={e=>{setSelected(e.target.value);setMessage("");}}>
            {relatedSchools.map(child=><option key={child.student} value={child.student}>{child.school_name}</option>)}
          </select>
        </label>}
        <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:"1rem"}}>
          {[
            ["reports","Bulletins"],["enrollments","Scolarité"],["attendance","Présences"],
            ["finance","Frais"],["timetable","Emploi du temps"],
          ].map(([id,label])=><button key={id} type="button" className={"yd-btn"+(tab===id?" primary":"")}
            onClick={()=>{setTab(id);setMessage("");}}>{label}</button>)}
        </div>
        {!detail&&<p>Chargement des données autorisées…</p>}
        {tab==="enrollments"&&detail&&<>
          {(detail.enrollments||[]).length===0?<p>Aucune inscription disponible.</p>:
            (detail.enrollments||[]).map(e=><p key={e.id}><strong>{e.year}</strong> · {e.classroom} · {e.status}</p>)}
        </>}
        {tab==="reports"&&detail&&<>
          {(detail.reports||[]).length===0?<p>Aucun bulletin publié.</p>:
          (detail.reports||[]).map(r=><div key={r.id} style={{padding:"0.6rem 0",borderBottom:"1px solid #ddd"}}>
            <strong>{r.year} — {r.period}</strong>
            <span> · {r.score||r.label||"Résultat disponible"}
              {r.amendment_sequence?" · Rectificatif n° "+r.amendment_sequence:""}</span>
            <div><a href={"/api/v1/"+base+"/reports/"+r.id+"/pdf"}>Télécharger le bulletin PDF</a></div>
          </div>)}
        </>}
        {tab==="attendance"&&detail&&<>
          {(detail.attendance||[]).length===0?<p>Aucun appel clôturé pour cet enfant.</p>:
            (detail.attendance||[]).map((a,i)=><p key={i}>{a.date} · {a.slot} :
              <strong> {a.status}</strong>{a.justified?" (justifié)":""}</p>)}
        </>}
        {tab==="finance"&&detail&&<>
          <p>Relevé des encaissements de l'établissement. Les paiements SingPay nécessitent une confirmation serveur du prestataire.</p>
          {Object.entries(detail.totals||{}).map(([currency,value])=><p key={currency}>
            {currency} · Facturé : <strong>{value.billed}</strong> · Payé : <strong>{value.paid}</strong>
            {" "}· Restant : <strong>{value.balance}</strong>
          </p>)}
          {(detail.charges||[]).map(c=><div key={c.id}><p>{c.label} — {c.amount} {c.currency}
            {" "}· Solde {c.balance}{c.due_date?" · Échéance "+c.due_date:""}</p>
            {c.currency==="XAF"&&<SingPayPayment kind="charge" objectId={c.id} api={portalApi} partial/>}</div>)}
          {(detail.charges||[]).length===0&&<p>Aucun frais affecté.</p>}
        </>}
        {tab==="timetable"&&detail&&<>
          {(detail.entries||[]).length===0?<p>Aucune séance en vigueur n'a été programmée.</p>:
            <div style={{overflowX:"auto"}}><table style={{width:"100%"}}>
              <thead><tr><th>Jour</th><th>Heure</th><th>Cours</th><th>Enseignant</th><th>Salle</th></tr></thead>
              <tbody>{(detail.entries||[]).map(e=><tr key={e.id}>
                <td>{DAYS[e.weekday]}</td><td>{e.start}–{e.end}</td><td>{e.subject}</td>
                <td>{e.teacher}</td><td>{e.room||"—"}</td>
              </tr>)}</tbody>
            </table></div>}
        </>}
      </Card>}
      <Message>{message}</Message>
      {!isParentAccount&&schools.length>0&&<Card title="Administration — vérifier les accès familiaux">
        <p>Réservé à la direction autorisée. Contrôlez l'identité du responsable légal hors application
          avant d'accorder l'accès ; un téléphone ou un e-mail identique ne suffit pas.</p>
        <label className="field">Établissement
          <select value={school} onChange={e=>setSchool(e.target.value)}>
            <option value="">Choisir une école…</option>
            {schools.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        {school&&!access&&<p>Vous ne disposez pas des droits de vérification pour cet établissement.</p>}
        {access&&<>
          <label className="field">Élève
            <select value={chosenStudent} onChange={e=>setChosenStudent(e.target.value)}>
              <option value="">Choisir un élève…</option>
              {students.map(s=><option key={s.id} value={s.id}>{s.last_name} {s.first_name} · {s.student_code}</option>)}
            </select>
          </label>
          <label className="field">Responsable légal inscrit dans ce dossier
            <select value={guardian} onChange={e=>setGuardian(e.target.value)}>
              <option value="">Choisir le responsable…</option>
              {guardians.filter(g=>g.active).map(g=><option key={g.id} value={g.id}>{g.full_name} ({g.relationship||"Lien enregistré"})</option>)}
            </select>
          </label>
          <label className="field">Identifiant du compte utilisateur déjà créé
            <input value={username} onChange={e=>setUsername(e.target.value)} maxLength={150}
              autoComplete="off" placeholder="Compte parent existant"/>
          </label>
          <div style={{display:"flex",gap:8,flexWrap:"wrap",margin:"0.8rem 0"}}>
            <button className="yd-btn" type="button" disabled={busy||!username} onClick={()=>run(async()=>{
              await portalApi("schools/"+school+"/members",{username,role:"parent"});
              setMessage("Compte affecté au rôle parent ; vérifiez la personne avant d'activer le lien.");
            })}>1. Attribuer le rôle parent</button>
            <button className="yd-btn primary" type="button" disabled={busy||!guardian||!username} onClick={()=>run(async()=>{
              await portalApi("schools/"+school+"/parent-links",{guardian,username});
              await reloadAdmin(school);await reloadChildren();setMessage("Accès familial vérifié et activé.");
            })}>2. Vérifier et activer le lien</button>
          </div>
          <h4>Accès enregistrés</h4>
          {links.length===0?<p>Aucun lien vérifié.</p>:links.map(l=><p key={l.id} style={{padding:"0.5rem 0"}}>
            {l.student_name} · {l.guardian_name} → <strong>{l.username}</strong>
            {l.active?" · Actif":" · Révoqué"}
            {l.active&&<button className="yd-btn" type="button" disabled={busy}
              onClick={()=>run(async()=>{
                await portalApi("schools/"+school+"/parent-links/"+l.id,
                  {revision:l.revision,active:false},"PATCH");
                await reloadAdmin(school);await reloadChildren();
                setMessage("Accès révoqué immédiatement.");
              })}>Révoquer</button>}
          </p>)}
        </>}
      </Card>}
    </>}
  </div>;
}
