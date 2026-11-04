import React, {useEffect,useState} from "react";
import AcademicPanel from "./AcademicPanel.jsx";
import StudentPanel from "./StudentPanel.jsx";
import StaffPanel from "./StaffPanel.jsx";
import OrganisationPanel, {MySchoolFunctions} from "./OrganisationPanel.jsx";
import RoleManager from "./RoleManager.jsx";
import CurriculumPanel from "./CurriculumPanel.jsx";
import AssessmentPanel from "./AssessmentPanel.jsx";
import ReportPanel from "./ReportPanel.jsx";
import CouncilPanel from "./CouncilPanel.jsx";
import FinancePanel from "./FinancePanel.jsx";
import AttendancePanel from "./AttendancePanel.jsx";
import TimetablePanel from "./TimetablePanel.jsx";
import AdmissionsPanel from "./AdmissionsPanel.jsx";
import ParentPortal from "./ParentPortal.jsx";
import {LiveStudents,LivePayments,LiveArrears,LiveDashboard} from "./LiveScreens.jsx";
import {Shell,NAV,PageHeader,Card,Icon,Button} from "./yem-ui.jsx";
import "./yem-desktop.css";

/* Espace réel connecté : mêmes cadre, menu et en-têtes que les maquettes (docs/maquettes),
   chaque entrée du menu ouvrant les modules existants autorisés pour le rôle du compte. */
const modules = {
  academic:{label:"Années, cycles et classes",read:"school.academic.read",view:AcademicPanel},
  students:{label:"Élèves et inscriptions",read:"school.students.read",view:StudentPanel},
  staff:{label:"Personnel et enseignants",read:"school.staff.read",view:StaffPanel},
  organization:{label:"Organigramme et fonctions",read:"school.organization.read",view:OrganisationPanel},
  roles:{label:"Rôles et permissions",read:"school.roles.read",view:RoleManager},
  curriculum:{label:"Matières et programmes",read:"school.curriculum.read",view:CurriculumPanel},
  timetable:{label:"Emplois du temps",read:"school.timetable.read",view:TimetablePanel},
  assessments:{label:"Évaluations et notes",read:"school.assessments.read",view:AssessmentPanel},
  reports:{label:"Bulletins",read:"school.reports.read",view:ReportPanel},
  council:{label:"Conseils et décisions",read:"school.deliberations.read",view:CouncilPanel},
  attendance:{label:"Appels et absences",read:"school.attendance.read",view:AttendancePanel},
  finance:{label:"Frais et encaissements",read:"school.finance.read",view:FinancePanel},
  admissions:{label:"Admissions",read:"school.admissions.read",view:AdmissionsPanel},
};
/* Chaque entrée du menu des maquettes regroupe un ou plusieurs modules réels. */
const sections = {
  students:{title:"Gestion des élèves",subtitle:"Inscriptions, classes, responsables et suivi administratif",modules:["students"],live:{label:"Liste des élèves",need:"school.students.read",manage:"Fiches et inscriptions"}},
  admissions:{title:"Admissions & préinscriptions",subtitle:"Demandes, inscriptions au secrétariat, capacité d’accueil et paiement",modules:["admissions"]},
  payments:{title:"Encaissements et caisse journalière",subtitle:"Suivi des paiements, reçus et méthodes d’encaissement",modules:["finance"],live:{label:"Caisse du jour",need:"school.finance.read",manage:"Tarifs, frais et relevés"}},
  arrears:{title:"Impayés & relances",subtitle:"Suivi des échéances, retards et soldes des familles",modules:[],live:{label:"Impayés",need:"school.finance.read"}},
  bulletins:{title:"Bulletins et résultats scolaires",subtitle:"Évaluations, préparation, contrôle et publication des bulletins",modules:["assessments","reports","council"]},
  absences:{title:"Absences et retards",subtitle:"Appels, absences, retards et justificatifs",modules:["attendance","timetable"]},
  staff:{title:"Personnel",subtitle:"Équipe pédagogique et administrative, affectations et comptes",modules:["staff","organization","roles"],extra:"users"},
  settings:{title:"Paramétrage de l’établissement",subtitle:"Années, classes, matières, barèmes et emplois du temps",modules:["academic","curriculum","timetable"]},
};
const sectionIcon=Object.fromEntries(NAV.map(([id,icon])=>[id,icon]));

async function get(path) {
  const r=await fetch("/api/v1/"+path,{credentials:"same-origin"});
  const data=await r.json();
  if (!r.ok) throw Error(data.error||"Accès refusé");
  return data;
}
const defaultPerson={username:"",email:"",first_name:"",last_name:"",password:"",role:"enseignant"};
const DEFAULT_ROLE_OPTIONS=[["direction","Direction"],["secretariat","Secrétariat"],["enseignant","Enseignant"],["comptabilite","Comptabilité"],["parent","Parent"],["eleve","Élève"]];
async function addUser(schoolId, body, endpoint="users") {
  await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
  const token=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const r=await fetch("/api/v1/schools/"+schoolId+"/"+endpoint,{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","X-CSRFToken":token},body:JSON.stringify(body)});
  const data=await r.json();
  if(!r.ok)throw Error(data.error||"Création refusée");
  return data;
}

function UsersForm({schoolId,onMessage}) {
  const [person,setPerson]=useState(defaultPerson);
  const [assignment,setAssignment]=useState({username:"",role:"enseignant",additional_roles:[]});
  const [busy,setBusy]=useState(false);
  const [roleOptions,setRoleOptions]=useState(DEFAULT_ROLE_OPTIONS);
  useEffect(()=>{
    let alive=true;
    get("schools/"+schoolId+"/roles").then(result=>{
      if(!alive)return;
      const options=(result.roles||[]).map(r=>[r.code,r.label]);
      if(options.length){
        setRoleOptions(options);
        setPerson(old=>options.some(([code])=>code===old.role)?old:{...old,role:options[0][0]});
      }
    }).catch(()=>{if(alive)setRoleOptions(DEFAULT_ROLE_OPTIONS);});
    return()=>{alive=false;};
  },[schoolId]);
  return <Card title="Créer un compte pour l'établissement" icon="adduser" subtitle="Le compte est rattaché uniquement à cette école. Les droits dépendent de son rôle.">
    <form onSubmit={async e=>{e.preventDefault();setBusy(true);onMessage("");try{const result=await addUser(schoolId,person);setPerson(defaultPerson);onMessage("Compte créé : "+result.username);}catch(err){onMessage(err.message);}finally{setBusy(false);}}}><div className="pc-fields">
      {["first_name","last_name","username","email"].map(key=><label key={key}>{{first_name:"Prénom",last_name:"Nom",username:"Identifiant de connexion",email:"Email"}[key]}<input required value={person[key]} type={key==="email"?"email":"text"} onChange={e=>setPerson(x=>({...x,[key]:e.target.value}))}/></label>)}
      <label>Rôle<select value={person.role} onChange={e=>setPerson(x=>({...x,role:e.target.value}))}>{roleOptions.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>Mot de passe initial<input required type="password" minLength={12} autoComplete="new-password" value={person.password} onChange={e=>setPerson(x=>({...x,password:e.target.value}))}/></label>
    </div><button className="pc-primary" type="submit" disabled={busy}>Créer le compte</button></form>
    <form aria-label="Fonctions d'un compte existant" onSubmit={async e=>{e.preventDefault();setBusy(true);try{await addUser(schoolId,assignment,"members");onMessage("Fonctions mises à jour.");}catch(err){onMessage(err.message);}finally{setBusy(false);}}}>
      <h3>Fonctions d'un compte existant</h3>
      <label>Identifiant<input required value={assignment.username} onChange={e=>setAssignment({...assignment,username:e.target.value})}/></label>
      <label>Rôle principal<select value={assignment.role} onChange={e=>setAssignment({...assignment,role:e.target.value})}>{roleOptions.map(([code,label])=><option key={code} value={code}>{label}</option>)}</select></label>
      <fieldset><legend>Fonctions supplémentaires (remplace la sélection précédente)</legend>{roleOptions.filter(([code])=>code!==assignment.role).map(([code,label])=><label key={code}><input type="checkbox" checked={assignment.additional_roles.includes(code)} onChange={e=>setAssignment(old=>({...old,additional_roles:e.target.checked?[...old.additional_roles,code]:old.additional_roles.filter(x=>x!==code)}))}/>{label}</label>)}</fieldset>
      <button disabled={busy}>Enregistrer les fonctions</button>
    </form>
  </Card>;
}

function ModuleGrid({visibleSections,navigate}) {
  const entries=Object.entries(visibleSections);
  return <div className="yd-real-body">{entries.length===0?<Card title="Aucun module attribué" icon="info"><p className="yd-card-sub">Aucun module n'est attribué à votre rôle dans cet établissement.</p></Card>:
    <div className="pc-module-grid">{entries.map(([id,s])=><button type="button" key={id} onClick={()=>navigate(id)}><Icon name={sectionIcon[id]} size={26}/><b>{NAV.find(n=>n[0]===id)?.[2]}</b><small>{[s.live?.label,...s.modules.map(k=>modules[k].label)].filter(Boolean).concat(s.users?["Comptes et accès"]:[]).join(" · ")}</small></button>)}</div>}</div>;
}

function UserMenu({user,roleLabel,onAccount,onLogout}) {
  const [open,setOpen]=useState(false);
  const name=[user?.first_name,user?.last_name].filter(Boolean).join(" ")||user?.username||"Mon compte";
  return <div className="yd-user-wrap">
    <button type="button" className="yd-user-btn" aria-haspopup="menu" aria-expanded={open} onClick={()=>setOpen(o=>!o)}>
      <span className="yd-avatar"><Icon name="user" size={22} strokeWidth={0} className="filled"/></span>
      <span><b>{name}</b>{roleLabel&&<small>{roleLabel}</small>}</span><Icon name="chevron" size={18}/>
    </button>
    {open&&<div className="yd-menu right" role="menu">
      <button type="button" role="menuitem" onClick={()=>{setOpen(false);onAccount();}}><Icon name="shield" size={18}/>Sécurité du compte</button>
      {onLogout&&<button type="button" role="menuitem" onClick={()=>{setOpen(false);onLogout();}}><Icon name="logout" size={18}/>Se déconnecter</button>}
    </div>}
  </div>;
}

export default function SchoolDashboard({user,accountView,onLogout,initialSchoolId=""}) {
  const [schools,setSchools]=useState([]);
  const [loaded,setLoaded]=useState(false);
  const [chosen,setChosen]=useState("");
  const [access,setAccess]=useState(null);
  const [page,setPage]=useState("dashboard");
  const [sub,setSub]=useState("");
  const [params,setParams]=useState(null);
  const [isParent,setIsParent]=useState(true);
  const [showWorkspace,setShowWorkspace]=useState(false);
  const [message,setMessage]=useState("");
  useEffect(()=>{get("schools").then(d=>{setSchools(d.schools||[]);setChosen(old=>old||(d.schools||[]).find(s=>String(s.id)===String(initialSchoolId))?.id||(d.schools||[])[0]?.id||"");}).catch(e=>setMessage(e.message)).finally(()=>setLoaded(true));},[]);
  useEffect(()=>{let live=true;fetch("/api/v1/parents/children",{credentials:"same-origin"}).then(r=>r.ok?r.json():null).then(d=>{if(live&&d?.parent_role)setIsParent(true);}).catch(()=>{});return()=>{live=false;};},[]);
  useEffect(()=>{
    if (!chosen) {setAccess(null);return;}
    let alive=true;setAccess(null);
    get("schools/"+chosen+"/my-access").then(x=>{if(alive)setAccess(x);}).catch(e=>{if(alive)setMessage(e.message);});
    setPage("dashboard");return ()=>{alive=false;};
  },[chosen]);
  const perms=access?.permissions||[];
  const allowed=key=>perms.includes(modules[key].read);
  const canUsers=perms.includes("school.members.write");
  const visibleSections=Object.fromEntries(Object.entries(sections).map(([id,s])=>[id,{...s,modules:s.modules.filter(allowed),users:s.extra==="users"&&canUsers,live:s.live&&perms.includes(s.live.need)?s.live:null}]).filter(([,s])=>s.modules.length||s.users||s.live));
  const nav=NAV.filter(([id])=>id==="dashboard"||visibleSections[id]||(id==="parents"&&isParent));
  function navigate(id,subTab="",extra=null){setPage(id);setSub(subTab);setParams(extra);setMessage("");window.scrollTo?.(0,0);}
  const section=visibleSections[page];
  const tabs=section?[...(section.live?[["live",section.live.label]]:[]),...section.modules.map(k=>[k,section.live?.manage||modules[k].label]),...(section.users?[["users","Comptes et accès"]]:[])]:[];
  const tab=tabs.find(t=>t[0]===sub)?.[0]||tabs[0]?.[0];
  const View=tab&&modules[tab]?.view;
  const tabBar=tabs.length>1?<div className="yd-real-tabs" role="tablist">{tabs.map(([k,l])=><button type="button" role="tab" aria-selected={tab===k} key={k} className={tab===k?"active":""} onClick={()=>setSub(k)}>{l}</button>)}</div>:null;
  const schoolName=access?.school?.name||schools.find(s=>s.id===chosen)?.name||"Mon établissement";
  const selector=<div className="yd-school-select-wrap"><label className="yd-school-select"><Icon name="school" size={24}/>
    {schools.length>1?<select aria-label="Établissement" value={chosen} onChange={e=>setChosen(e.target.value)}>{schools.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>:<b>{schoolName}</b>}
    {schools.length>1&&<Icon name="chevron" size={18} className="chev"/>}</label></div>;
  // Une famille connectée arrive directement dans YEM Parents, sans tableau de bord scolaire.
  // Un même compte peut aussi travailler dans un établissement : la bascule reste accessible.
  const parentLanding = loaded && (schools.length === 0 || (access?.role === "parent" && !showWorkspace));
  if (parentLanding) return <div className="yd-parent-standalone" style={{maxWidth:1040,margin:"0 auto",padding:"1rem"}}>
    <nav aria-label="Navigation du compte parent" style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:12,flexWrap:"wrap",marginBottom:14}}>
      <strong style={{fontSize:21,color:"#175c46"}}>YEM Parents</strong>
      <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
        {schools.length>0&&<button type="button" className="yd-btn" onClick={()=>setShowWorkspace(true)}>Espace établissement</button>}
        <button type="button" className="yd-btn" onClick={()=>setPage(page==="account"?"parents":"account")}>{page==="account"?"Mes enfants":"Mon compte"}</button>
        <button type="button" className="yd-btn" onClick={onLogout}>Se déconnecter</button>
      </div>
    </nav>
    {page==="account"?accountView:<ParentPortal/>}
    <footer className="yd-brand-footer"><span>YEM · Espace familles</span><span>Développé par <strong>BWETEK Informatyk</strong></span></footer>
  </div>;
  let content;
  if (page==="account") content=<><PageHeader title="Sécurité du compte" subtitle="Mot de passe, double authentification et déconnexion" banner={false}/><div className="yd-real-body">{accountView}</div></>;
  else if (page==="parents") content=<div className="yd-real-body"><ParentPortal/></div>;
  else if (loaded&&schools.length===0) content=<><PageHeader title="Tableau de bord" subtitle="Aucun établissement n'est encore rattaché à ce compte"/><Card title="Aucun établissement attribué" icon="school"><p className="yd-card-sub">Contactez l'administrateur de YEM pour recevoir un compte rattaché à votre établissement.</p>{isParent&&<Button primary icon="users" onClick={()=>navigate("parents")}>Ouvrir l'espace parents</Button>}</Card></>;
  else if (!access) content=<Card title="Chargement de vos droits…" icon="shield"/>;
  else if (section&&tab==="live") {
    const props={schoolId:chosen,schoolName,tabs:tabBar,onNavigate:navigate,params,canManage:perms.includes("school.students.manage"),canReceive:perms.includes("school.finance.receive")};
    content={students:<LiveStudents key={chosen} {...props}/>,payments:<LivePayments key={chosen+JSON.stringify(params)} {...props}/>,arrears:<LiveArrears key={chosen} {...props}/>}[page];
  }
  else if (section) content=<>
    <PageHeader title={section.title} subtitle={section.subtitle}/>
    {tabBar}
    <div className="yd-real-body">{tab==="users"?<UsersForm schoolId={chosen} onMessage={setMessage}/>:View&&<View key={chosen+"-"+tab} schoolId={chosen} canDecide={perms.includes("school.admissions.decide")} canConfigurePayment={perms.includes("school.admissions.manage")&&perms.includes("school.finance.manage")} canManage={perms.includes("school.organization.manage")} canManageRoles={perms.includes("school.roles.manage")}/>}</div>
  </>;
  else if (perms.includes("school.finance.read")) content=<>
    <LiveDashboard key={chosen} schoolId={chosen} schoolName={schoolName} roleLabel={access.role_label} onNavigate={navigate} canReceive={perms.includes("school.finance.receive")}/>
    <MySchoolFunctions schoolId={chosen}/>
    <ModuleGrid visibleSections={visibleSections} navigate={navigate}/>
  </>;
  else content=<>
    <PageHeader title="Tableau de bord" subtitle={`Vue de pilotage de ${schoolName}`} badge={access.role_label||"Membre"} badgeIcon="crown"/>
    <MySchoolFunctions schoolId={chosen}/>
    <ModuleGrid visibleSections={visibleSections} navigate={navigate}/>
  </>;
  return <Shell nav={nav} active={page} onNavigate={navigate} notifications={0} schoolSelector={selector}
    userMenu={<UserMenu user={user} roleLabel={access?.role_label} onAccount={()=>navigate("account")} onLogout={onLogout}/>}>
    {message&&<p role="status" className="pc-alert">{message}</p>}
    {content}
    <footer className="yd-brand-footer"><span>YEM — Gestion scolaire &amp; universitaire</span><span>Développé par <strong>BWETEK Informatyk</strong></span></footer>
  </Shell>;
}
