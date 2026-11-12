import React, { useEffect, useState } from "react";
import ParentDiscovery from "./ParentDiscovery.jsx";
import PWAInstall from "./PWAInstall.jsx";
import SingPayPayment from "./SingPayPayment.jsx";
import YemFamilles from "./YemFamilles.jsx";
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

export function FamilyWorkspace({accountView, onLogout, onSchoolWorkspace, user}) {
  return <div className="yd-parent-standalone yfm-standalone">
    <ParentPortal accountView={accountView} onLogout={onLogout}
      onSchoolWorkspace={onSchoolWorkspace} user={user}/>
    <footer className="yd-brand-footer"><span>YEM · Espace familles</span>
      <span>Développé par <strong>BWETEK Informatyk</strong></span></footer>
  </div>;
}

const CHILD_SECTIONS = [
  ["grades", "Notes"], ["reports", "Bulletins"], ["attendance", "Vie scolaire"],
  ["finance", "Frais"], ["timetable", "Emploi du temps"],
];

function gradeResult(grade) {
  if (grade.score == null) return "Non renseignée";
  const score = typeof grade.score === "number" ? String(grade.score).replace(".", ",") : String(grade.score);
  if (grade.scale_kind === "percentage") return score + " %";
  if (grade.scale_kind === "numeric" && grade.scale_max != null) return score + " / " + grade.scale_max;
  return score;
}

function AttendanceEntries({entries}) {
  return <ul>
    {entries.map(entry => <li key={entry.id}>
      {entry.date} · {entry.slot} · <strong>{entry.status}</strong>{entry.justified ? " (justifié)" : ""}
    </li>)}
  </ul>;
}

function ChildSchoolLife({detail}) {
  const attendance = detail.attendance || [];
  const incidents = attendance.filter(entry => entry.group !== "present");
  const presences = attendance.filter(entry => entry.group === "present");
  return <>
    <h4>Absences et retards</h4>
    <p>{detail.totals?.absent ?? 0} absence(s) · {detail.totals?.late ?? 0} retard(s)</p>
    {incidents.length > 0 ? <AttendanceEntries entries={incidents}/> :
      <p>{attendance.length ? "Aucune absence ni aucun retard enregistré." : "Aucun appel clôturé pour cette année."}</p>}
    {presences.length > 0 && <details>
      <summary>Présences enregistrées ({detail.totals?.present ?? presences.length})</summary>
      <AttendanceEntries entries={presences}/>
    </details>}
    <h4>Comportement et discipline</h4>
    {detail.conduct?.length ? <ul>
      {detail.conduct.map(notice => <li key={notice.id}>
        <strong>{notice.label}</strong> · {notice.date}<p>{notice.message}</p>
      </li>)}
    </ul> : <p>Aucune observation ni sanction communiquée par l’établissement.</p>}
  </>;
}

function ChildSchoolSection({base, tab, year}) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    portalApi(base + "/" + tab + "?year=" + encodeURIComponent(year))
      .then(result => { if (active) setDetail(result); })
      .catch(failure => { if (active) setError(failure.message); });
    return () => { active = false; };
  }, [base, tab, year]);

  if (error) return <p role="alert">{error}</p>;
  if (!detail) return <p role="status">Chargement des données scolaires…</p>;

  if (tab === "grades") return detail.grades?.length ? <Table className="yd-table"
    headers={["Matière", "Évaluation", "Date", "Note", "Coefficient"]}
    rows={detail.grades.map(grade => [
      grade.subject,
      grade.period ? grade.assessment + " · " + grade.period : grade.assessment,
      grade.date,
      <>{gradeResult(grade)}{grade.label && grade.label !== String(grade.score) ? " · " + grade.label : ""}</>,
      Number(grade.weight).toLocaleString("fr-FR"),
    ])}/> : <p>Aucune note publiée pour cette année.</p>;

  if (tab === "reports") return detail.reports?.length ? detail.reports.map(report =>
    <div key={report.id} style={{padding:"0.6rem 0",borderBottom:"1px solid #ddd"}}>
      <strong>{report.year} · {report.period}</strong>
      <span> · {report.score ?? report.label ?? "Résultat disponible"}
        {report.amendment_sequence ? " · Rectificatif n° " + report.amendment_sequence : ""}</span>
      <div><a href={"/api/v1/" + base + "/reports/" + report.id + "/pdf"}>Télécharger le bulletin PDF</a></div>
    </div>
  ) : <p>Aucun bulletin publié.</p>;

  if (tab === "attendance") return <ChildSchoolLife detail={detail}/>;

  if (tab === "finance") return <>
    {detail.scholarship && <p role="status"><strong>Boursier de l'État</strong> ·
      {detail.scholarship.coverage === "all"
        ? " Frais d'inscription et de scolarité intégralement pris en charge."
        : " Frais d'inscription pris en charge ; autres frais suivant le barème."}
      {" "}Décision n° {detail.scholarship.reference}. Aucun paiement du parent
      n'a été créé pour les frais couverts.</p>}
    <p>Relevé des encaissements de l'établissement. Les paiements SingPay nécessitent une confirmation serveur du prestataire.</p>
    {Object.entries(detail.totals || {}).map(([currency, value]) => <p key={currency}>
      {currency} · Facturé : <strong>{value.billed}</strong> · Payé : <strong>{value.paid}</strong>
      {" "}· Restant : <strong>{value.balance}</strong>
    </p>)}
    {(detail.charges || []).map(charge => <div key={charge.id}><p>{charge.label} · {charge.amount} {charge.currency}
      {" "}· Solde {charge.balance}{charge.due_date ? " · Échéance " + charge.due_date : ""}</p>
      {charge.currency === "XAF" && <SingPayPayment kind="charge" objectId={charge.id} api={portalApi} partial/>}
    </div>)}
    {!detail.charges?.length && <p>Aucun frais affecté.</p>}
  </>;

  return detail.entries?.length ? <Table className="yd-table"
    headers={["Jour", "Heure", "Cours", "Enseignant", "Salle"]}
    rows={detail.entries.map(entry => [
      DAYS[entry.weekday], entry.start + "–" + entry.end, entry.subject, entry.teacher, entry.room || "—",
    ])}/> : <p>Aucune séance programmée pour cette année.</p>;
}

function ChildSchoolRecord({child, relatedSchools, onSelectChild}) {
  const base = "parents/children/" + child.student;
  const [enrollments, setEnrollments] = useState(null);
  const [error, setError] = useState("");
  const [year, setYear] = useState("");
  const [tab, setTab] = useState("grades");

  useEffect(() => {
    let active = true;
    portalApi(base + "/enrollments").then(result => {
      if (!active) return;
      const rows = result.enrollments || [];
      setEnrollments(rows);
      const current = rows.find(row => row.year_status === "current")
        || rows.find(row => row.year_in_progress) || rows[0];
      setYear(current?.year_id || "");
    }).catch(failure => { if (active) setError(failure.message); });
    return () => { active = false; };
  }, [base]);

  const enrollment = enrollments?.find(row => row.year_id === year);
  return <Card title={child.last_name + " " + child.first_name}>
    <p>{child.school_name} · Matricule {child.student_code}</p>
    {child.matricule_yem && child.matricule_yem !== child.student_code &&
      <p>Identifiant permanent YEM · {child.matricule_yem}</p>}
    {relatedSchools.length > 1 && <label className="field">Établissement du parcours
      <select value={child.student} onChange={event => onSelectChild(event.target.value)}>
        {relatedSchools.map(school => <option key={school.student} value={school.student}>{school.school_name}</option>)}
      </select>
    </label>}
    {error ? <p role="alert">{error}</p> : !enrollments ? <p role="status">Chargement de la scolarité…</p> :
      !enrollment ? <p>La classe s’affichera dès que l’établissement aura enregistré l’inscription.</p> :
      <>
        <label className="field">Année scolaire
          <select value={year} onChange={event => setYear(event.target.value)}>
            {enrollments.map(row => <option key={row.id} value={row.year_id}>{row.year}</option>)}
          </select>
        </label>
        <p>Classe <strong>{enrollment.classroom}</strong> · <strong>{enrollment.class_size} {enrollment.class_size === 1 ? "élève inscrit" : "élèves inscrits"}</strong></p>
        {enrollment.enrolled_on && <p>Date d’inscription · {enrollment.enrolled_on}</p>}
        {(!enrollment.active || enrollment.status !== "inscrit") &&
          <p>{enrollment.active ? "Statut de l’inscription" : "Inscription inactive"} · {enrollment.status}</p>}
        <div className="actions" role="group" aria-label="Rubriques de la fiche scolaire">
          {CHILD_SECTIONS.map(([id, label]) => <button key={id} type="button" aria-pressed={tab === id}
            className={"yd-btn" + (tab === id ? " primary" : "")} onClick={() => setTab(id)}>{label}</button>)}
        </div>
        <ChildSchoolSection key={year + "/" + tab} base={base} tab={tab} year={year}/>
      </>}
  </Card>;
}

export default function ParentPortal({accountView, onLogout, onSchoolWorkspace, user}) {
  const [family, setFamily] = useState(null);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    portalApi("parents/children").then(result => {
      if (!active) return;
      const children = result.children || [];
      setFamily(result);
      setSelected(previous => children.some(child => child.student === previous)
        ? previous : children[0]?.student || "");
    }).catch(failure => { if (active) setError(failure.message); });
    return () => { active = false; };
  }, [refresh]);

  function refreshChildren() {
    setFamily(null);
    setError("");
    setRefresh(previous => previous + 1);
  }

  return <YemFamilles
    api={portalApi} accountView={accountView} onLogout={onLogout}
    onSchoolWorkspace={onSchoolWorkspace} user={user}
    family={family} children={family?.children || []} selected={selected}
    setSelected={setSelected} refreshChildren={refreshChildren}
    familyError={error} familyLoading={!family && !error}/>;
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
      <p className="hint">Demandez l’identifiant YEM Parents du responsable légal et vérifiez son identité avant d’activer l’accès à cet élève.</p>
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
