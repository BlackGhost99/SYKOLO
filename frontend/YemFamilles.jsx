import React, {useEffect, useMemo, useState} from "react";
import ParentDiscovery from "./ParentDiscovery.jsx";
import PWAInstall from "./PWAInstall.jsx";
import SingPayPayment from "./SingPayPayment.jsx";
import YemFamillesFidele from "./YemFamillesFidele.jsx";

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
  const now = new Date();
  const today = [now.getFullYear(),String(now.getMonth()+1).padStart(2,"0"),String(now.getDate()).padStart(2,"0")].join("-");
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
  const [discoveryTab, setDiscoveryTab] = useState("children");
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
  return <YemFamillesFidele m={{
    api, accountView, onLogout, onSchoolWorkspace, user, family, children,
    selected, setSelected, refreshChildren, familyError, familyLoading,
    screen, navTo, goSchool, goDiscovery,
    schoolTab, setSchoolTab, discoveryTab, setDiscoveryTab,
    enrollments, enrollment, enrollmentError, year, setYear,
    data, dataErrors, gradeRows, reportRows, totals, totalCalls,
    attendancePercent, financial, charges, paid, billed, due,
    reportMean, publishedReport, observations, future, name, child, childBase,
    currentYearLabel, alerts, firstName, feesReady, paymentsAvailable,
    activeCharge, setActiveCharge, gradeEmpty
  }}/>;
}
