import React, {useEffect,useState} from "react";
import AcademicPanel from "./AcademicPanel.jsx";
import StudentPanel from "./StudentPanel.jsx";
import StaffPanel from "./StaffPanel.jsx";
import CurriculumPanel from "./CurriculumPanel.jsx";
import AssessmentPanel from "./AssessmentPanel.jsx";
import ReportPanel from "./ReportPanel.jsx";
import CouncilPanel from "./CouncilPanel.jsx";
import FinancePanel from "./FinancePanel.jsx";
import AttendancePanel from "./AttendancePanel.jsx";
import TimetablePanel from "./TimetablePanel.jsx";
import AdmissionsPanel from "./AdmissionsPanel.jsx";
import "./platform-console.css";

const modules = [
  {key:"academic",label:"Années, cycles et classes",read:"school.academic.read",view:AcademicPanel},
  {key:"students",label:"Élèves et inscriptions",read:"school.students.read",view:StudentPanel},
  {key:"staff",label:"Personnel et enseignants",read:"school.staff.read",view:StaffPanel},
  {key:"curriculum",label:"Matières et programmes",read:"school.curriculum.read",view:CurriculumPanel},
  {key:"timetable",label:"Emplois du temps",read:"school.timetable.read",view:TimetablePanel},
  {key:"assessments",label:"Évaluations",read:"school.assessments.read",view:AssessmentPanel},
  {key:"reports",label:"Bulletins",read:"school.reports.read",view:ReportPanel},
  {key:"council",label:"Délibérations",read:"school.deliberations.read",view:CouncilPanel},
  {key:"attendance",label:"Présences",read:"school.attendance.read",view:AttendancePanel},
  {key:"finance",label:"Finances",read:"school.finance.read",view:FinancePanel},
  {key:"admissions",label:"Admissions",read:"school.admissions.read",view:AdmissionsPanel},
];
async function get(path) {
  const r=await fetch("/api/v1/"+path,{credentials:"same-origin"});
  const data=await r.json();
  if (!r.ok) throw Error(data.error||"Accès refusé");
  return data;
}
export default function SchoolDashboard() {
  const [schools,setSchools]=useState([]);
  const [chosen,setChosen]=useState("");
  const [access,setAccess]=useState(null);
  const [page,setPage]=useState("home");
  const [message,setMessage]=useState("");
  useEffect(()=>{get("schools").then(d=>{setSchools(d.schools||[]);setChosen(old=>old||(d.schools||[])[0]?.id||"");}).catch(e=>setMessage(e.message));},[]);
  useEffect(()=>{
    if (!chosen) {setAccess(null);return;}
    let alive=true;setAccess(null);
    get("schools/"+chosen+"/my-access").then(x=>{if(alive)setAccess(x);}).catch(e=>{if(alive)setMessage(e.message);});
    setPage("home");return ()=>{alive=false;};
  },[chosen]);
  const available=modules.filter(m=>access?.permissions?.includes(m.read));
  const selectedModule=available.find(m=>m.key===page);
  const View=selectedModule?.view;
  return <div className="pc-school-shell">
    <div className="pc-school-top"><div><small>YEM / ESPACE ÉTABLISSEMENT</small><h2>{access?.school?.name||"Mon établissement"}</h2><p>Tableau de bord adapté aux droits de votre compte scolaire.</p></div>
      <label>Établissement<select value={chosen} onChange={e=>setChosen(e.target.value)}>{schools.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
    </div>
    {message&&<p role="status" className="pc-alert">{message}</p>}
    {schools.length===0?<div className="pc-panel"><h3>Aucun établissement attribué</h3><p>Contactez l'administrateur de YEM pour recevoir un compte rattaché à votre établissement.</p></div>:
      !access?<div className="pc-panel">Chargement de vos droits…</div>:<>
      <div className="pc-role">Compte : <strong>{access.role_label||"Membre"}</strong> · {available.length} module(s) accessibles</div>
      <div className="pc-school-nav"><button className={page==="home"?"active":""} onClick={()=>setPage("home")}>Accueil</button>{available.map(m=><button key={m.key} className={page===m.key?"active":""} onClick={()=>setPage(m.key)}>{m.label}</button>)}</div>
      {page==="home"&&<div className="pc-panel"><h3>Bienvenue dans votre établissement</h3><p>Accédez aux modules autorisés pour votre rôle. Les années, classes, barèmes, bulletins et emplois du temps sont gérés par établissement.</p><div className="pc-module-grid">{available.map(m=><button key={m.key} onClick={()=>setPage(m.key)}><b>{m.label}</b><small>Ouvrir le module</small></button>)}</div>{available.length===0&&<p>Aucun module supplémentaire n'est attribué à votre rôle.</p>}</div>}
      {View&&<View key={chosen+"-"+page} schoolId={chosen}/>}
    </>}
  </div>;
}
