import React, { useEffect, useState } from "react";
import ParentDiscovery from "./ParentDiscovery.jsx";
import PWAInstall from "./PWAInstall.jsx";
import SingPayPayment from "./SingPayPayment.jsx";
import {Button, Card as SchoolCard, Status, Table} from "./yem-ui.jsx";

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

export function FamilyWorkspace({accountView, onLogout, onSchoolWorkspace}) {
  const [showAccount, setShowAccount] = useState(false);
  return <div className="yd-parent-standalone">
    <nav aria-label="Navigation du compte parent">
      <strong>YEM Parents</strong>
      <div>
        {onSchoolWorkspace&&<Button onClick={onSchoolWorkspace}>Espace établissement</Button>}
        <Button onClick={()=>setShowAccount(open=>!open)}>{showAccount?"Retour à l’espace parents":"Mon compte"}</Button>
        <Button onClick={onLogout}>Se déconnecter</Button>
      </div>
    </nav>
    {showAccount?accountView:<ParentPortal/>}
    <footer className="yd-brand-footer"><span>YEM · Espace familles</span><span>Développé par <strong>BWETEK Informatyk</strong></span></footer>
  </div>;
}

export default function ParentPortal() {
  const [children,setChildren] = useState(null);
  const [selected,setSelected] = useState("");
  const [tab,setTab] = useState("reports");
  const [detail,setDetail] = useState(null);
  const [message,setMessage] = useState("");
  const [connected,setConnected] = useState(true);

  useEffect(()=>{
    let alive=true;
    portalApi("parents/children").then(family=>{
      if(alive)setChildren(family.children||[]);
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
  const current=children?.find(c=>c.student===selected);
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
      <Card title="Suivi scolaire de mes enfants">
        {!children?<p role="status">Chargement des dossiers scolaires liés…</p>:children.length===0?
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
          {detail.scholarship&&<p role="status"><strong>Boursier de l'État</strong> ·
            {detail.scholarship.coverage==="all"
              ?" Frais d'inscription et de scolarité intégralement pris en charge."
              :" Frais d'inscription pris en charge ; autres frais suivant le barème."}
            {" "}Décision n° {detail.scholarship.reference}. Aucun paiement du parent
            n'a été créé pour les frais couverts.</p>}
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
    </>}
  </div>;
}

export function SchoolParentAccess({schoolId, canAssignRole, canReadStudents}) {
  const base = "schools/"+schoolId;
  const [links, setLinks] = useState(null);
  const [students, setStudents] = useState(null);
  const [student, setStudent] = useState("");
  const [guardians, setGuardians] = useState(null);
  const [guardian, setGuardian] = useState("");
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [loadError, setLoadError] = useState("");
  const [guardiansError, setGuardiansError] = useState("");

  useEffect(()=>{
    let alive=true;
    portalApi(base+"/parent-links").then(result=>{
      if(alive)setLinks(result.links);
    }).catch(error=>{if(alive)setLoadError(error.message);});
    if(canReadStudents)portalApi(base+"/students").then(result=>{
      if(alive)setStudents(result.students.filter(row=>row.active));
    }).catch(error=>{if(alive)setLoadError(error.message);});
    return()=>{alive=false;};
  },[base,canReadStudents]);

  useEffect(()=>{
    if(!student||!canReadStudents)return;
    let alive=true;
    portalApi(base+"/students/"+student+"/guardians").then(result=>{
      if(alive)setGuardians(result.guardians.filter(row=>row.active));
    }).catch(error=>{if(alive)setGuardiansError(error.message);});
    return()=>{alive=false;};
  },[base,student,canReadStudents]);

  async function run(action) {
    setBusy(true);
    setMessage("");
    try{await action();}catch(error){setMessage(error.message);}finally{setBusy(false);}
  }

  return <SchoolCard title="Responsables légaux et comptes parents" icon="users">
    {loadError&&<p role="alert">{loadError}</p>}
    <Message>{message}</Message>
    {canReadStudents&&links&&students&&<>
      <p className="hint">Vérifiez l’identité du responsable légal hors de YEM avant d’activer l’accès à cet élève.</p>
      <label className="field">Élève
        <select value={student} disabled={busy} onChange={e=>{
          setStudent(e.target.value);setGuardian("");setGuardians(null);setGuardiansError("");setMessage("");
        }}>
          <option value="">Choisir un élève…</option>
          {students.map(s=><option key={s.id} value={s.id}>{s.last_name} {s.first_name} · {s.student_code}</option>)}
        </select>
      </label>
      <label className="field">Responsable légal
        <select value={guardian} disabled={busy||!guardians?.length} onChange={e=>setGuardian(e.target.value)}>
          <option value="">Choisir le responsable…</option>
          {guardians?.map(g=><option key={g.id} value={g.id}>{g.full_name} ({g.relationship||"Lien enregistré"})</option>)}
        </select>
      </label>
      {student&&guardiansError&&<p role="alert">{guardiansError}</p>}
      {student&&!guardiansError&&!guardians&&<p role="status">Chargement des responsables légaux…</p>}
      {student&&guardians?.length===0&&<p className="hint">Ajoutez d’abord le responsable légal dans la fiche de l’élève.</p>}
      <label className="field">Identifiant du compte parent existant
        <input value={username} onChange={e=>setUsername(e.target.value)} disabled={busy} maxLength={150} autoComplete="off"/>
      </label>
      <div className="actions">
        {canAssignRole&&<Button disabled={busy||!guardian||!username.trim()} onClick={()=>run(async()=>{
          await portalApi(base+"/members",{username:username.trim(),role:"parent",create_only:true});
          setMessage("Compte rattaché au rôle parent dans cet établissement.");
        })}>Rattacher le compte parent</Button>}
        <Button primary disabled={busy||!guardian||!username.trim()} onClick={()=>run(async()=>{
          const verified=await portalApi(base+"/parent-links",{guardian,username:username.trim()});
          setLinks(previous=>[verified,...previous.filter(link=>link.id!==verified.id)]);
          setMessage("Accès familial vérifié et activé.");
        })}>Vérifier et activer l’accès</Button>
      </div>
    </>}
    <h3>Accès enregistrés</h3>
    {!links&&!loadError&&<p role="status">Chargement des accès familiaux…</p>}
    {links?.length===0&&<p>Aucun accès familial enregistré.</p>}
    {links?.length>0&&<Table className="yd-table" headers={["Élève","Responsable légal","Compte parent","Statut","Action"]}
      rows={links.map(link=>[
        link.student_name,
        link.guardian_name,
        link.username,
        <Status tone={link.active?"green":"gray"}>{link.active?"Actif":"Révoqué"}</Status>,
        link.active?<Button className="small" disabled={busy}
          ariaLabel={"Révoquer l’accès de "+link.guardian_name+" pour "+link.student_name}
          onClick={()=>run(async()=>{
            const revoked=await portalApi(base+"/parent-links/"+link.id,{revision:link.revision,active:false},"PATCH");
            setLinks(previous=>previous.map(row=>row.id===revoked.id?revoked:row));
            setMessage("Accès familial révoqué.");
          })}>Révoquer</Button>:"—",
      ])}/>}
  </SchoolCard>;
}
