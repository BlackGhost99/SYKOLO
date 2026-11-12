import React, {useEffect, useMemo, useState} from "react";
import ParentDiscovery from "./ParentDiscovery.jsx";
import PWAInstall from "./PWAInstall.jsx";
import SingPayPayment from "./SingPayPayment.jsx";
import "./yem-familles.css";

const NAV = [
  ["home", "Accueil", "⌂"],
  ["children", "Enfants", "♧"],
  ["payments", "Paiements", "▣"],
  ["school", "Scolarité", "▤"],
  ["profile", "Profil", "◯"],
];
const WEEKDAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
const EMPTY = {grades:null, attendance:null, finance:null, reports:null, timetable:null};

function money(value) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("fr-FR", {maximumFractionDigits:0}) + " FCFA" : "—";
}
function dateLabel(value) {
  if (!value) return "Non définie";
  const date = new Date(value + (String(value).includes("T") ? "" : "T12:00:00"));
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("fr-GA", {day:"numeric", month:"short", year:"numeric"});
}
function scoreLabel(grade) {
  if (!grade || grade.score == null) return "Non renseignée";
  if (grade.scale_kind === "percentage") return String(grade.score).replace(".", ",") + " %";
  if (grade.scale_kind === "numeric" && grade.scale_max != null)
    return String(grade.score).replace(".", ",") + " / " + grade.scale_max;
  return String(grade.score).replace(".", ",") + (grade.label ? " · " + grade.label : "");
}
function unpaidCharge(charge) {
  return Number(charge?.balance || 0) > 0;
}
function dueStatus(charge) {
  if (!unpaidCharge(charge)) return ["Payé", "paid"];
  if (!charge.due_date) return ["À régler", "due"];
  const today = new Date().toLocaleDateString("en-CA");
  return charge.due_date < today ? ["En retard", "late"] : ["À venir", "due"];
}
function initials(child) {
  return ((child?.first_name?.[0] || "") + (child?.last_name?.[0] || "")).toUpperCase() || "YE";
}
function Tile({children, action, icon}) {
  return <button className="yfm-tile" type="button" onClick={action}>
    <span className="yfm-tile-icon" aria-hidden="true">{icon}</span><strong>{children}</strong>
  </button>;
}
function Panel({title, icon, more, children, className=""}) {
  return <section className={"yfm-panel " + className}>
    <div className="yfm-panel-title"><span className="yfm-panel-icon" aria-hidden="true">{icon}</span>
      <h3>{title}</h3>{more}</div>{children}
  </section>;
}
function ParentHelp({username, refreshChildren}) {
  return <section className="yfm-panel yfm-help">
    <h3>Rattacher un enfant à mon compte</h3>
    <p>Pour consulter ses notes, ses bulletins et ses paiements, l'établissement doit vérifier votre qualité de responsable légal et associer sa fiche à votre compte.</p>
    <p>Communiquez votre identifiant YEM Parents et le nom de l’enfant au secrétariat.</p>
    {username && <p className="yfm-code">Identifiant à communiquer <strong>{username}</strong></p>}
    <button type="button" className="yfm-outline" onClick={refreshChildren}>Actualiser mes enfants</button>
  </section>;
}

export default function YemFamilles({api, accountView, onLogout, onSchoolWorkspace, user, family, children, selected, setSelected, refreshChildren, familyError, familyLoading}) {
  const [screen, setScreen] = useState("home");
  const [schoolTab, setSchoolTab] = useState("grades");
  const [discoveryTab, setDiscoveryTab] = useState("schools");
  const [enrollments, setEnrollments] = useState(null);
  const [enrollmentError, setEnrollmentError] = useState("");
  const [year, setYear] = useState("");
  const [data, setData] = useState(EMPTY);
  const [dataErrors, setDataErrors] = useState({});
  const [notifications, setNotifications] = useState(null);
  const [activeCharge, setActiveCharge] = useState("");
  const child = children.find(c => c.student === selected);
  const childId = child?.student;
  const childBase = childId ? "parents/children/" + childId : "";

  useEffect(() => {
    let alive = true;
    api("parents/notifications").then(result => {if(alive) setNotifications(result.notifications || []);})
      .catch(() => {if(alive) setNotifications([]);});
    return () => {alive = false;};
  }, [api]);

  useEffect(() => {
    let alive = true;
    setEnrollments(null);setEnrollmentError("");setYear("");setData(EMPTY);
    if (!childBase) return () => {alive = false;};
    api(childBase + "/enrollments").then(result => {
      if (!alive) return;
      const rows = result.enrollments || [];
      setEnrollments(rows);
      const row = rows.find(r => r.year_status === "current")
        || rows.find(r => r.year_in_progress) || rows[0];
      setYear(row?.year_id || "");
    }).catch(error => {if(alive) setEnrollmentError(error.message);});
    return () => {alive = false;};
  }, [api, childBase]);

  useEffect(() => {
    let alive = true;
    setData(EMPTY);setDataErrors({});setActiveCharge("");
    if (!childBase || !year) return () => {alive = false;};
    const names = ["grades", "attendance", "finance", "reports", "timetable"];
    Promise.allSettled(names.map(name => api(childBase + "/" + name + "?year=" + encodeURIComponent(year))))
      .then(results => {
        if (!alive) return;
        const next = {}, errors = {};
        results.forEach((result, index) => {
          if (result.status === "fulfilled") next[names[index]] = result.value;
          else errors[names[index]] = result.reason?.message || "Données indisponibles.";
        });
        setData({...EMPTY, ...next});setDataErrors(errors);
      });
    return () => {alive = false;};
  }, [api, childBase, year]);

  const enrollment = enrollments?.find(row => row.year_id === year);
  const gradeRows = data.grades?.grades || [];
  const reportRows = data.reports?.reports || [];
  const totals = data.attendance?.totals;
  const totalCalls = totals ? Number(totals.present || 0) + Number(totals.absent || 0) + Number(totals.late || 0) : 0;
  const attendancePercent = totalCalls ? Math.round((Number(totals.present || 0) / totalCalls) * 100) + " %" : "—";
  const financial = data.finance?.totals?.XAF || null;
  const charges = (data.finance?.charges || []).filter(c => c.currency === "XAF");
  const paid = Number(financial?.paid || 0);
  const billed = Number(financial?.billed || 0);
  const due = charges.filter(unpaidCharge).filter(c=>c.due_date).sort((a,b)=>a.due_date.localeCompare(b.due_date))[0];
  const publishedReport = reportRows.find(r=>r.score != null);
  const reportMean = publishedReport ? String(publishedReport.score).replace(".", ",") : null;
  const observations = data.attendance?.conduct || [];
  const future = useMemo(() => {
    const today = new Date().getDay();
    const weekday = today === 0 ? 6 : today - 1;
    return (data.timetable?.entries || []).filter(row=>Number(row.weekday)===weekday);
  }, [data.timetable]);
  const name = child ? child.first_name + " " + child.last_name : "";
  const currentYearLabel = enrollment?.year || "Année non renseignée";
  const alerts = notifications || [];
  const firstName = user?.first_name || user?.username || family?.parent_username || "Parent";

  function navTo(next) {setScreen(next);setActiveCharge("");}
  function goSchool(tab) {setSchoolTab(tab);navTo("school");}
  function goDiscovery(tab) {setDiscoveryTab(tab);navTo("children");}
  const feesReady = data.finance !== null && !dataErrors.finance;
  const paymentsAvailable = !!(child && enrollment);
  const help = <ParentHelp username={family?.parent_username || user?.username} refreshChildren={refreshChildren}/>;
  const gradeEmpty = data.grades === null ? "Chargement des notes publiées…" : "Aucune note publiée pour cette année.";
  const currentDetails = child && <section className="yfm-child-card">
    <div className="yfm-child-line"><div className="yfm-avatar" aria-hidden="true">{initials(child)}</div>
      <div className="yfm-child-name"><h2>{name}</h2><p>{child.school_name}</p>
        <p>{enrollment ? enrollment.classroom + " · " + currentYearLabel : enrollmentError || "Classe non encore enregistrée"}</p>
        <p className="yfm-matricule">Matricule : {child.matricule_yem || child.student_code || "Non renseigné"}</p>
      </div></div>
    {enrollments?.length > 0 && <label className="yfm-year">Année scolaire
      <select value={year} onChange={e=>setYear(e.target.value)}>
        {enrollments.map(row=><option key={row.id} value={row.year_id}>{row.year}</option>)}
      </select>
    </label>}
    {enrollment && <p className="yfm-class-size">Classe : <strong>{enrollment.classroom}</strong> · <strong>{enrollment.class_size} élèves inscrits</strong></p>}
    <div className="yfm-stats">
      <div><small>Assiduité</small><strong>{attendancePercent}</strong><span>{totalCalls ? totalCalls+" appels clôturés" : "Sans données"}</span></div>
      <div><small>Moyenne publiée</small><strong>{reportMean || "—"}</strong><span>{publishedReport ? publishedReport.period || "Bulletin disponible" : "Non publiée"}</span></div>
      <div><small>Vie scolaire</small><strong>{observations.length ? observations.length+" avis" : "—"}</strong><span>{observations.length ? "Observations publiées" : "Aucun avis publié"}</span></div>
    </div>
  </section>;

  return <div className="yfm-app">
    <div className="yfm-hero">
      <nav className="yfm-topbar" aria-label="Navigation du compte parent">
        <div className="yfm-brand"><span className="yfm-brand-logo" aria-hidden="true">✦</span>
          <div><strong>YEM Familles</strong><small>Espace Parents</small></div>
        </div>
        <div className="yfm-top-actions">
          <button type="button" onClick={()=>goDiscovery("notifications")} aria-label="Voir les notifications">♧{alerts.length ? <span className="yfm-dot"/> : null}</button>
          <button type="button" onClick={()=>navTo("profile")}>Mon compte</button>
          <button type="button" onClick={onLogout}>Se déconnecter</button>
        </div>
      </nav>
      <div className="yfm-greeting"><div><small>Bonjour,</small><h1>{firstName}</h1>
        <p>Suivez la scolarité de vos enfants et gérez vos démarches en toute simplicité.</p></div>
        {children.length > 1 && <label className="yfm-hero-select">Mes enfants
          <select value={selected} onChange={e=>setSelected(e.target.value)}>
            {children.map(c=><option key={c.student} value={c.student}>{c.first_name} {c.last_name}</option>)}
          </select>
        </label>}
      </div>
    </div>
    <div className="yfm-content">
      {familyError && <p role="alert" className="yfm-alert">{familyError} <button onClick={refreshChildren}>Réessayer</button></p>}
      {familyLoading && <p role="status">Chargement des informations de votre famille…</p>}
      {currentDetails}
      {!child && !familyLoading && !familyError && screen!=="profile" && help}
      {child && enrollmentError && <p role="alert" className="yfm-alert">{enrollmentError}</p>}
      {child && !enrollments && !enrollmentError && <p role="status">Chargement de la scolarité…</p>}

      {screen === "home" && <>
        <div className="yfm-shortcuts">
          <Tile icon="▤" action={()=>goSchool("attendance")}>Scolarité</Tile>
          <Tile icon="▣" action={()=>navTo("payments")}>Paiements</Tile>
          <Tile icon="▥" action={()=>goSchool("grades")}>Notes</Tile>
          <Tile icon="▦" action={()=>goSchool("timetable")}>Emploi du temps</Tile>
        </div>
        {child && <Panel title="Situation financière" icon="▣" className="yfm-finance-panel">
          <p className="yfm-muted">{currentYearLabel}{data.finance?.scholarship ? " · Bourse de l'État" : ""}</p>
          {dataErrors.finance && <p role="alert">{dataErrors.finance}</p>}
          <div className="yfm-money-grid">
            <div><small>Total payé</small><strong>{feesReady && financial ? money(financial.paid) : "—"}</strong></div>
            <div><small>Solde restant</small><strong>{feesReady && financial ? money(financial.balance) : "—"}</strong></div>
            <div><small>Prochaine échéance</small><strong>{due ? dateLabel(due.due_date) : "Non définie"}</strong></div>
          </div>
          <button type="button" className="yfm-primary" onClick={()=>navTo("payments")}>Consulter et payer les frais</button>
        </Panel>}
        <div className="yfm-two-panels">
          <Panel title="Notifications récentes" icon="♧" more={<button className="yfm-textlink" onClick={()=>goDiscovery("notifications")}>Tout voir</button>}>
            {alerts.length ? alerts.slice(0,3).map(n=><div key={n.kind+n.id} className="yfm-feed"><strong>{n.school}</strong>
              <p>{n.message}</p><small>{n.at ? new Date(n.at).toLocaleString("fr-GA") : ""}</small></div>)
              : <p className="yfm-muted">Aucune notification pour le moment.</p>}
          </Panel>
          <Panel title="Dernières notes" icon="▥" more={<button className="yfm-textlink" onClick={()=>goSchool("grades")}>Tout voir</button>}>
            {gradeRows.length ? gradeRows.slice(0,4).map(g=><div className="yfm-note-row" key={g.id}><span>{g.subject}</span><strong>{scoreLabel(g)}</strong></div>)
              : <p className="yfm-muted">{child ? gradeEmpty : "Les notes apparaîtront après le rattachement à un dossier scolaire."}</p>}
          </Panel>
        </div>
        <div className="yfm-cta-row">
          <button className="yfm-outline" onClick={()=>goDiscovery("schools")}>Découvrir les établissements</button>
          <button className="yfm-outline" onClick={()=>goDiscovery("requests")}>Suivre mes demandes</button>
        </div>
      </>}

      {screen === "payments" && <>
        <h2 className="yfm-section-heading">Paiements et frais de scolarité</h2>
        {!paymentsAvailable ? <p className="yfm-muted">Les frais officiels apparaîtront une fois l'enfant inscrit et rattaché par l’établissement.</p> : <>
          <Panel title="Frais de scolarité — Vue d’ensemble" icon="▣">
            <p className="yfm-muted">{currentYearLabel}</p>
            {dataErrors.finance && <p role="alert">{dataErrors.finance}</p>}
            {data.finance?.scholarship && <p role="status">Boursier de l'État · {data.finance.scholarship.coverage==="all" ? "Frais de scolarité et d'inscription pris en charge" : "Prise en charge selon décision"}.</p>}
            <div className="yfm-money-grid yfm-money-grid-wide">
              <div><small>Total facturé</small><strong>{financial ? money(financial.billed) : "—"}</strong></div>
              <div><small>Déjà payé</small><strong>{financial ? money(financial.paid) : "—"}</strong></div>
              <div><small>Solde restant</small><strong>{financial ? money(financial.balance) : "—"}</strong></div>
              <div><small>Échéance suivante</small><strong>{due ? dateLabel(due.due_date) : "Non définie"}</strong></div>
            </div>
            {billed>0 && <div className="yfm-progress" aria-label={Math.round(100*paid/billed)+" % des frais payés"}><div style={{width:Math.min(100,100*paid/billed)+"%"}}/></div>}
          </Panel>
          <Panel title="Détail des frais" icon="▦">
            {charges.length ? charges.map(c=>{
              const [status,tone]=dueStatus(c);
              return <div className="yfm-charge" key={c.id}>
                <div><strong>{c.label}</strong><small>{c.due_date ? "Échéance : "+dateLabel(c.due_date) : "Échéance non définie"}</small></div>
                <div><b>{money(c.amount)}</b><span className={"yfm-status "+tone}>{status}</span>
                  {unpaidCharge(c) && <button className="yfm-textlink" onClick={()=>setActiveCharge(activeCharge===c.id?"":c.id)}>{activeCharge===c.id?"Fermer":"Payer en ligne"}</button>}</div>
                {activeCharge===c.id && <div className="yfm-charge-pay"><p>Choisissez Airtel Money ou Moov Money dans le formulaire sécurisé SingPay, si l'établissement a activé son compte marchand.</p>
                  <SingPayPayment kind="charge" objectId={c.id} api={api} partial/></div>}
              </div>;
            }) : <p className="yfm-muted">{data.finance ? "Aucun frais affecté à cette année." : "Chargement du relevé de l’établissement…"}</p>}
            <p className="yfm-muted">Les espèces sont encaissées au guichet de l'école. Les montants versés ne sont confirmés qu'après enregistrement par l'établissement.</p>
          </Panel>
          <Panel title="Paiements et reçus" icon="▧">
            <p className="yfm-muted">Les montants payés ci-dessus proviennent du journal de caisse de l'établissement. Les reçus SingPay confirmés se consultent depuis le paiement correspondant.</p>
            <div className="yfm-cta-row"><button className="yfm-outline" onClick={()=>goDiscovery("requests")}>Voir mes paiements de candidature</button></div>
          </Panel>
        </>}
        {!child && <button className="yfm-outline" onClick={()=>goDiscovery("requests")}>Mes demandes et paiements de dossier</button>}
      </>}

      {screen === "school" && <>
        <h2 className="yfm-section-heading">Suivi scolaire {child ? "— "+name : ""}</h2>
        {!child ? <p>Les notes, les présences et les bulletins seront accessibles après validation du rattachement par l’établissement.</p> : <>
          <nav className="yfm-subtabs" aria-label="Rubriques de la fiche scolaire">
            {[["grades","Notes"],["attendance","Vie scolaire"],["timetable","Emploi du temps"],["reports","Bulletins"]].map(([key,label])=>
              <button key={key} type="button" aria-pressed={schoolTab===key} onClick={()=>setSchoolTab(key)}>{label}</button>)}
          </nav>
          {dataErrors[schoolTab] && <p role="alert" className="yfm-alert">{dataErrors[schoolTab]}</p>}
          {schoolTab==="grades" && <Panel title="Notes et résultats" icon="▥">
            {publishedReport && <p className="yfm-emphasis">Moyenne publiée : <strong>{reportMean}</strong> · {publishedReport.period || "Bulletin"}</p>}
            {gradeRows.length ? gradeRows.map(g=><div className="yfm-grade" key={g.id}>
              <div><strong>{g.subject}</strong><small>{g.assessment}{g.period ? " · "+g.period : ""}{g.date ? " · "+dateLabel(g.date) : ""}</small></div>
              <strong>{scoreLabel(g)}</strong></div>) : <p className="yfm-muted">{gradeEmpty}</p>}
            <button className="yfm-outline" onClick={()=>setSchoolTab("reports")}>Consulter les bulletins</button>
          </Panel>}
          {schoolTab==="attendance" && <div className="yfm-two-panels">
            <Panel title="Assiduité" icon="▦">
              <p className="yfm-big-stat">{attendancePercent}</p>
              <div className="yfm-money-grid"><div><small>Présences</small><strong>{totals?.present ?? "—"}</strong></div>
                <div><small>Absences</small><strong>{totals?.absent ?? "—"}</strong></div><div><small>Retards</small><strong>{totals?.late ?? "—"}</strong></div></div>
              {(data.attendance?.attendance || []).filter(a=>a.group!=="present").map(a=><p key={a.id} className="yfm-feed">{a.date} · {a.slot} · {a.status}{a.justified ? " (justifié)" : ""}</p>)}
            </Panel>
            <Panel title="Comportement et discipline" icon="☆">
              {observations.length ? observations.map(o=><div key={o.id} className="yfm-feed"><strong>{o.label}</strong>
                <p>{o.message}</p><small>{dateLabel(o.date)}</small></div>) : <p className="yfm-muted">Aucune observation ni sanction communiquée par l’établissement.</p>}
            </Panel>
          </div>}
          {schoolTab==="timetable" && <Panel title="Emploi du temps" icon="▦">
            {data.timetable?.entries?.length ? data.timetable.entries.map(e=><div key={e.id} className="yfm-grade">
              <div><strong>{WEEKDAYS[e.weekday] || "Jour non défini"} · {e.subject}</strong><small>{e.teacher || "Enseignant non indiqué"} · {e.room || "Salle non indiquée"}</small></div>
              <b>{e.start}–{e.end}</b></div>) : <p className="yfm-muted">Aucune séance programmée pour cette année.</p>}
          </Panel>}
          {schoolTab==="reports" && <Panel title="Bulletins publiés" icon="▤">
            {reportRows.length ? reportRows.map(r=><div className="yfm-grade" key={r.id}><div><strong>{r.period || "Année entière"}</strong>
              <small>{r.year}{r.amendment_sequence ? " · Rectificatif n° "+r.amendment_sequence : ""}</small></div>
              <a className="yfm-outline" href={"/api/v1/"+childBase+"/reports/"+r.id+"/pdf"}>Télécharger le PDF</a></div>) :
              <p className="yfm-muted">Aucun bulletin publié pour cette année.</p>}
          </Panel>}
        </>}
      </>}

      {screen === "children" && <>
        <h2 className="yfm-section-heading">Mes enfants et mes démarches</h2>
        {children.length>0 && <Panel title="Dossiers scolaires rattachés" icon="♧">
          {children.map(c=><button key={c.student} className={"yfm-child-picker"+(selected===c.student?" active":"")} onClick={()=>setSelected(c.student)}>
            <span className="yfm-mini-avatar">{initials(c)}</span><span>{c.first_name} {c.last_name}<small>{c.school_name}</small></span>
            <span>{selected===c.student?"Sélectionné":"Voir le dossier"}</span>
          </button>)}
          <button className="yfm-outline" onClick={refreshChildren}>Actualiser mes enfants</button>
        </Panel>}
        <nav className="yfm-subtabs" aria-label="Démarches des familles">
          {[["schools","Établissements"],["children","Profils enfants"],["requests","Mes demandes"],["notifications","Actualités"]].map(([key,label])=>
            <button key={key} type="button" aria-pressed={discoveryTab===key} onClick={()=>setDiscoveryTab(key)}>{label}</button>)}
        </nav>
        <ParentDiscovery key={discoveryTab} embedded activeSection={discoveryTab}/>
      </>}

      {screen === "profile" && <>
        <h2 className="yfm-section-heading">Mon profil et la sécurité</h2>
        <p className="yfm-muted">Gérez votre mot de passe et les options de sécurité de votre compte YEM Parents.</p>
        {accountView || <Panel title="Mon compte" icon="◯"><p>{user?.username || "Compte parent"}</p></Panel>}
        {onSchoolWorkspace && <button className="yfm-outline" onClick={onSchoolWorkspace}>Espace établissement</button>}
      </>}
      <div className="yfm-install"><PWAInstall/></div>
    </div>
    <nav className="yfm-bottom" aria-label="Navigation YEM Familles">
      {NAV.map(([id,label,icon])=><button key={id} type="button" aria-current={screen===id?"page":undefined} onClick={()=>navTo(id)}>
        <span aria-hidden="true">{icon}</span><small>{label}</small></button>)}
    </nav>
  </div>;
}
