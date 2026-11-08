import DelegationManager from "./DelegationManager.jsx";
import React, {useEffect,useState} from "react";
import AcademicPanel from "./AcademicPanel.jsx";
import StaffPanel from "./StaffPanel.jsx";
import StaffOnboarding from "./StaffOnboarding.jsx";
import CycleWorkspace from "./CycleWorkspace.jsx";
import OrganisationPanel, {MySchoolFunctions} from "./OrganisationPanel.jsx";
import RoleManager from "./RoleManager.jsx";
import CurriculumPanel from "./CurriculumPanel.jsx";
import AssessmentPanel from "./AssessmentPanel.jsx";
import ReportPanel from "./ReportPanel.jsx";
import CouncilPanel from "./CouncilPanel.jsx";
import FinancePanel from "./FinancePanel.jsx";
import AttendancePanel from "./AttendancePanel.jsx";
import TimetablePanel from "./TimetablePanel.jsx";
import AdmissionsPanel, {AdmissionSettings, AdmissionPaymentSettings} from "./AdmissionsPanel.jsx";
import {SchoolSettings, TeachingSettings} from "./SchoolSettings.jsx";
import {FamilyDirectory, StaffDirectory} from "./SchoolDirectories.jsx";
import StudentNumberingSettings from "./StudentNumberingSettings.jsx";
import {FamilyWorkspace, SchoolParentAccess} from "./ParentPortal.jsx";
import {LiveStudents,LivePayments,LiveArrears,LiveDashboard} from "./LiveScreens.jsx";
import ClassWorkspace from "./ClassWorkspace.jsx";
import {StudentForm,StudentFile,ClassEnrollments,ClassSetup,FormSettings,PaymentTracking,ImportStudents} from "./EnrollmentScreens.jsx";
import {Shell,NAV,PageHeader,Card,Icon,Button} from "./yem-ui.jsx";
import "./yem-desktop.css";

/* Espace réel connecté : mêmes cadre, menu et en-têtes que les maquettes (docs/maquettes),
   chaque entrée du menu ouvrant les modules existants autorisés pour le rôle du compte. */
const modules = {
  onboarding:{label:"Ajouter un collaborateur",read:"school.staff.manage",view:StaffOnboarding},
  academic:{label:"Années, cycles et classes",read:"school.academic.read",view:AcademicPanel},
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
  students:{title:"Gestion des élèves",subtitle:"Inscriptions, classes, responsables et suivi administratif",modules:[],lives:[
    {key:"live",label:"Liste des élèves",need:["school.students.read"]},
    {key:"byclass",label:"Inscriptions par classe",need:["school.students.read","school.academic.read"]}],
    hidden:{new:"school.students.manage",import:"school.students.manage",fiche:"school.students.read"}},
  classes:{modules:[],lives:[{key:"live",label:"Classes et effectifs",need:["school.academic.read"]}]},
  admissions:{title:"Admissions et préinscriptions",subtitle:"Consultez les demandes et suivez leur inscription",modules:["admissions"]},
  payments:{title:"Encaissements et caisse journalière",subtitle:"Suivi des paiements, reçus et méthodes d’encaissement",modules:["finance"],lives:[
    {key:"live",label:"Caisse du jour",need:["school.finance.read"]},
    {key:"tracking",label:"Suivi des paiements",need:["school.finance.read","school.students.read"]}]},
  arrears:{title:"Impayés & relances",subtitle:"Suivi des échéances, retards et soldes des familles",modules:[],lives:[{key:"live",label:"Impayés",need:["school.finance.read"]}]},
  bulletins:{title:"Évaluations et notes",subtitle:"Retrouvez les notes, bulletins et décisions à partir de la classe",modules:["assessments","reports","council"]},
  absences:{title:"Absences et retards",subtitle:"Consultez les appels et les retards par classe",modules:["attendance"]},
  parents:{title:"Parents",subtitle:"Les responsables légaux de chaque élève, par classe",modules:[],lives:[
    {key:"directory",label:"Parents par classe",need:["school.parents.manage","school.students.read","school.academic.read"]}]},
  staff:{title:"Personnel",subtitle:"Retrouvez les collaborateurs et gérez leurs affectations",modules:["onboarding"],lives:[
    {key:"directory",label:"Équipe de l’établissement",need:["school.staff.read"]}]},
};
const schoolNav = [...NAV.slice(0,2), ["classes","layers","Classes"], ...NAV.slice(2)].map(([id, icon, label]) => [id, icon, id === "bulletins" ? "Évaluations et notes" : label]);
const sectionIcon=Object.fromEntries(schoolNav.map(([id,icon])=>[id,icon]));

const settingsSections = [
  {id:"access", title:"Droits généraux", icon:"shield", items:[
    {id:"users", label:"Comptes et accès", need:["school.members.write"]},
    {id:"roles", label:"Rôles et droits d’accès", need:["school.roles.read"], owner:true},
    {id:"cycle-access", label:"Accès par cycle", ownerOnly:true},
  ]},
  {id:"school", title:"Classes de l’établissement", icon:"school", items:[
    {id:"classes", label:"Classes", need:["school.academic.read"]},
    {id:"form", label:"Fiche d’inscription", need:["school.students.read"]},
    {id:"numbering", label:"Matricules", need:["school.settings.write"]},
    {id:"curriculum", label:"Matières et programmes", need:["school.curriculum.read"]},
    {id:"report-policy", label:"Barèmes et bulletins", need:["school.settings.read"]},
    {id:"council-policy", label:"Décisions du conseil", need:["school.settings.read"]},
    {id:"amendments", label:"Rectifier un bulletin", need:["school.reports.amend","school.reports.read","school.students.read","school.academic.read"]},
    {id:"timetable", label:"Emplois du temps", need:["school.timetable.read"]},
    {id:"academic", label:"Années et cycles", need:["school.academic.read"]},
  ]},
  {id:"admissions", title:"Admissions", icon:"adduser", items:[
    {id:"admission-policy", label:"Voies d’admission et fiche publique", need:["school.admissions.read","school.academic.read"], any:["school.admissions.manage","school.admissions.decide"]},
  ]},
  {id:"payments", title:"Paiements", icon:"card", items:[
    {id:"fees", label:"Tarifs et échéances", need:["school.finance.manage","school.finance.read"]},
    {id:"gateway", label:"Paiement des dossiers et Mobile Money", need:["school.admissions.manage","school.finance.manage","school.academic.read"]},
  ]},
  {id:"attendance", title:"Absences et retards", icon:"calendar", items:[
    {id:"attendance-policy", label:"Statuts de présence", need:["school.settings.read"]},
  ]},
  {id:"parents", title:"Parents", icon:"users", items:[
    {id:"parent-access", label:"Vérification et accès des responsables légaux", need:["school.parents.manage"]},
  ]},
  {id:"staff", title:"Personnel", icon:"idcard", items:[
    {id:"organization", label:"Organigramme et fonctions", need:["school.organization.read"]},
    {id:"staff-setup", label:"Comptes du personnel et affectations", need:["school.staff.manage","school.staff.read","school.academic.read"]},
  ]},
];
const advancedSettingsTargets = {
  students:["form"], classes:["classes"], admissions:["admission-policy"], payments:["fees","gateway"],
  bulletins:["report-policy"], absences:["attendance-policy"], parents:["parent-access"],
  staff:["staff-setup","organization"],
};
const teachingKinds = {"report-policy":"bulletin","council-policy":"deliberation","attendance-policy":"attendance"};

async function get(path) {
  const r=await fetch("/api/v1/"+path,{credentials:"same-origin"});
  const data=await r.json();
  if (!r.ok) throw Error(data.error||"Accès refusé");
  return data;
}
const defaultPerson={username:"",email:"",first_name:"",last_name:"",password:"",role:"enseignant",function_codes:null};
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
  const [assignment,setAssignment]=useState({username:"",role:"enseignant",additional_roles:[],function_codes:[]});
  const [busy,setBusy]=useState(false);
  const [roleOptions,setRoleOptions]=useState([]);
  const [functions,setFunctions]=useState([]);
  const [members,setMembers]=useState([]);
  useEffect(()=>{
    let alive=true;
    get("schools/"+schoolId+"/members").then(result=>{if(alive)setMembers(result.members||[]);}).catch(err=>{if(alive)onMessage(err.message);});
    get("schools/"+schoolId+"/roles").then(result=>{
      if(!alive)return;
      setFunctions(result.functions||[]);
      const options=(result.roles||[]).filter(r=>r.available_for_accounts!==false).map(r=>[r.code,r.label,r.suggested_function]);
      if(options.length){
        setRoleOptions(options);
        setPerson(old=>options.some(([code])=>code===old.role)?old:{...old,role:options[0][0]});
      }
    }).catch(err=>{if(alive){setRoleOptions([]);onMessage(err.message);}});
    return()=>{alive=false;};
  },[schoolId]);
  const proposedFunction=roleOptions.find(([code])=>code===person.role)?.[2];
  const personFunctions=person.function_codes??(proposedFunction?[proposedFunction]:[]);
  const assignmentRoles=roleOptions.filter(([code])=>code!=="proprietaire");
  return <Card title="Créer un compte pour l'établissement" icon="adduser" subtitle="Le compte est rattaché uniquement à cette école. Les droits dépendent de son rôle.">
    <form onSubmit={async e=>{e.preventDefault();setBusy(true);onMessage("");try{const result=await addUser(schoolId,{...person,function_codes:personFunctions});setPerson(defaultPerson);setMembers((await get("schools/"+schoolId+"/members")).members||[]);onMessage("Compte créé : "+result.username);}catch(err){onMessage(err.message);}finally{setBusy(false);}}}><div className="pc-fields">
      {["first_name","last_name","username","email"].map(key=><label key={key}>{{first_name:"Prénom",last_name:"Nom",username:"Identifiant de connexion",email:"Email"}[key]}<input required value={person[key]} type={key==="email"?"email":"text"} onChange={e=>setPerson(x=>({...x,[key]:e.target.value}))}/></label>)}
      <label>Rôle<select value={person.role} onChange={e=>setPerson(x=>({...x,role:e.target.value,function_codes:null}))}>{roleOptions.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>Mot de passe initial<input required type="password" minLength={12} autoComplete="new-password" value={person.password} onChange={e=>setPerson(x=>({...x,password:e.target.value}))}/></label>
    </div><fieldset><legend>Fonctions exercées (facultatives, sans droits automatiques)</legend>{functions.map(f=><label key={f.code}><input type="checkbox" checked={personFunctions.includes(f.code)} onChange={e=>setPerson(old=>({...old,function_codes:e.target.checked?[...personFunctions,f.code]:personFunctions.filter(c=>c!==f.code)}))}/>{f.label}</label>)}</fieldset><button className="pc-primary" type="submit" disabled={busy||!roleOptions.length}>Créer le compte</button></form>
    <form aria-label="Fonctions d'un compte existant" onSubmit={async e=>{e.preventDefault();setBusy(true);try{await addUser(schoolId,assignment,"members");setMembers((await get("schools/"+schoolId+"/members")).members||[]);onMessage("Fonctions mises à jour.");}catch(err){onMessage(err.message);}finally{setBusy(false);}}}>
      <h3>Fonctions d'un compte existant</h3>
      <label>Compte existant<select required value={assignment.username} onChange={e=>{const m=members.find(x=>x.username===e.target.value);if(m)setAssignment({username:m.username,role:m.role,additional_roles:m.additional_roles||[],function_codes:m.function_codes||[]});}}><option value="">Choisir…</option>{members.filter(m=>!m.is_school_owner).map(m=><option key={m.user_id} value={m.username}>{m.username}</option>)}</select></label>
      <label>Rôle principal<select value={assignment.role} onChange={e=>setAssignment({...assignment,role:e.target.value})}>{assignmentRoles.map(([code,label])=><option key={code} value={code}>{label}</option>)}</select></label>
      <fieldset><legend>Fonctions supplémentaires (remplace la sélection précédente)</legend>{assignmentRoles.filter(([code])=>code!==assignment.role).map(([code,label])=><label key={code}><input type="checkbox" checked={assignment.additional_roles.includes(code)} onChange={e=>setAssignment(old=>({...old,additional_roles:e.target.checked?[...old.additional_roles,code]:old.additional_roles.filter(x=>x!==code)}))}/>{label}</label>)}</fieldset>
      <fieldset><legend>Fonctions exercées (remplace la sélection précédente)</legend>{functions.map(f=><label key={f.code}><input type="checkbox" checked={assignment.function_codes.includes(f.code)} onChange={e=>setAssignment(old=>({...old,function_codes:e.target.checked?[...old.function_codes,f.code]:old.function_codes.filter(c=>c!==f.code)}))}/>{f.label}</label>)}</fieldset>
      <button disabled={busy}>Enregistrer les fonctions</button>
    </form>
    <DelegationManager schoolId={schoolId} onFunctions={setFunctions}/>
  </Card>;
}

function ModuleGrid({visibleSections,navigate}) {
  const entries=Object.entries(visibleSections);
  return <div className="yd-real-body">{entries.length===0?<Card title="Aucun module attribué" icon="info"><p className="yd-card-sub">Aucun module n'est attribué à votre rôle dans cet établissement.</p></Card>:
    <div className="pc-module-grid">{entries.map(([id,s])=><button type="button" key={id} onClick={()=>navigate(id)}><Icon name={sectionIcon[id]} size={26}/><b>{schoolNav.find(n=>n[0]===id)?.[2]}</b><small>{[...s.lives.map(l=>l.label),...s.modules.map(k=>modules[k].label)].filter(Boolean).join(" · ") || s.subtitle}</small></button>)}</div>}</div>;
}

function UserMenu({user,roleLabel,onAccount,onFamilyWorkspace,onLogout}) {
  const [open,setOpen]=useState(false);
  const name=[user?.first_name,user?.last_name].filter(Boolean).join(" ")||user?.username||"Mon compte";
  return <div className="yd-user-wrap">
    <button type="button" className="yd-user-btn" aria-label={`Compte de ${name}`} aria-haspopup="menu" aria-expanded={open} onClick={()=>setOpen(o=>!o)}>
      <span className="yd-avatar"><Icon name="user" size={22} strokeWidth={0} className="filled"/></span>
      <span><b>{name}</b>{roleLabel&&<small>{roleLabel}</small>}</span><Icon name="chevron" size={18}/>
    </button>
    {open&&<div className="yd-menu right" role="menu">
      <button type="button" role="menuitem" onClick={()=>{setOpen(false);onAccount();}}><Icon name="shield" size={18}/>Sécurité du compte</button>
      {onFamilyWorkspace&&<button type="button" role="menuitem" onClick={onFamilyWorkspace}><Icon name="users" size={18}/>YEM Parents</button>}
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
  const [settingsSelection,setSettingsSelection]=useState(null);
  const [settingsReturn,setSettingsReturn]=useState(null);
  const [showWorkspace,setShowWorkspace]=useState(false);
  const [message,setMessage]=useState("");
  const [academicYears,setAcademicYears]=useState([]);
  const [workingYearId,setWorkingYearId]=useState("");
  useEffect(()=>{get("schools").then(d=>{setSchools(d.schools||[]);setChosen(old=>old||(d.schools||[]).find(s=>String(s.id)===String(initialSchoolId))?.id||(d.schools||[])[0]?.id||"");}).catch(e=>setMessage(e.message)).finally(()=>setLoaded(true));},[]);
  useEffect(()=>{
    if (!chosen) {setAccess(null);return;}
    let alive=true;setAccess(null);
    get("schools/"+chosen+"/my-access").then(x=>{if(alive)setAccess(x);}).catch(e=>{if(alive)setMessage(e.message);});
    setPage("dashboard");return ()=>{alive=false;};
  },[chosen]);
  useEffect(()=>{
    let live=true;
    setAcademicYears([]);setWorkingYearId("");
    if(chosen && access?.permissions?.includes("school.academic.read")){
      get("schools/"+chosen+"/academic/annual-snapshot").then(data=>{
        if(!live)return;
        setAcademicYears(data.years||[]);
        setWorkingYearId(data.year?.id||"");
      }).catch(()=>{if(live)setAcademicYears([])});
    }
    return ()=>{live=false};
  },[chosen,access]);
  useEffect(()=>{
    if(!chosen||!workingYearId||!access?.permissions?.includes("school.academic.read"))return;
    let live=true;
    get("schools/"+chosen+"/academic/annual-snapshot?year="+encodeURIComponent(workingYearId))
      .then(data=>{if(live)setAcademicYears(data.years||[])})
      .catch(()=>{});
    return()=>{live=false};
  },[chosen,workingYearId,access]);
  const perms=access?.permissions||[];
  const can = permission => perms.includes(permission);
  const isOwner = Boolean(access?.is_owner);
  const allowed = key => key === "onboarding"
    ? can("school.staff.manage") || isOwner
    : can(modules[key].read) || (key==="attendance" && can("school.attendance.assigned"));
  const canUsers = can("school.members.write");
  const restricted = Boolean(access?.cycle_scope_restricted);
  const availableSettings = restricted ? [] : settingsSections.map(section => ({
    ...section, items: section.items.filter(item =>
      item.ownerOnly ? isOwner :
        (item.owner && isOwner) || (item.need.every(can) && (!item.any || item.any.some(can)))),
  })).filter(section => section.items.length);
  const visibleSections = restricted
    ? Object.fromEntries([
        ...(can("school.students.read")?[["students",{...sections.students,modules:[],lives:[{key:"cycle-list",label:"Élèves autorisés",need:[]}]}]]:[]),
        ...(can("school.staff.manage")?[["staff",{...sections.staff,modules:["onboarding"],lives:[]}]]:[]),
      ])
    : Object.fromEntries(Object.entries(sections).map(([id,s])=>[id,{
        ...s,modules:s.modules.filter(allowed),lives:(s.lives||[]).filter(l=>l.need.every(can)),
      }]).filter(([,s])=>s.modules.length||s.lives.length));
  if (availableSettings.length) visibleSections.settings = {
    subtitle:"Réglages de l’établissement", modules:[], lives:[],
  };
  const nav=schoolNav.filter(([id])=>id==="dashboard"||visibleSections[id]);
  function navigate(id,subTab="",extra=null){
    setPage(id);setSub(subTab);setParams(extra);setMessage("");setSettingsReturn(null);
    if(id==="settings"){
      const group=availableSettings.find(group=>group.items.some(item=>item.id===subTab));
      setSettingsSelection(group ? {section:group.id,item:subTab} : null);
    }
    window.scrollTo?.(0,0);
  }
  const section=visibleSections[page];
  const tabs=section?[...section.lives.map(l=>[l.key,l.label]),...section.modules.map(k=>[k,modules[k].label])]:[];
  const hiddenTab=section?.hidden?.[sub]&&perms.includes(section.hidden[sub])?sub:null;
  const tab=hiddenTab||tabs.find(t=>t[0]===sub)?.[0]||tabs[0]?.[0];
  const View=tab&&modules[tab]?.view;
  const targets = page==="bulletins" && tab==="council"
    ? ["council-policy"] : advancedSettingsTargets[page] || [];
  const settingsTarget = section && !hiddenTab && targets.find(id =>
    availableSettings.some(group=>group.items.some(item=>item.id===id)));
  const advancedSettings = settingsTarget ? <Button icon="settings" className="small" onClick={()=>{
    navigate("settings",settingsTarget);
    setSettingsReturn({page,tab,params});
  }}>Paramètres avancés</Button> : null;
  const roleLabel=isOwner && access?.role!=="proprietaire"
    ? ["Propriétaire", access?.role_label].filter(Boolean).join(" · ")
    : access?.role_label;
  const panelProps={
    schoolId:chosen,canDecide:can("school.admissions.decide"),
    canCreate:can("school.admissions.manage"),canEnroll:can("school.admissions.enroll"),
    canManage:can("school.organization.manage"),canManageRoles:can("school.roles.manage"),
    canPublish:can("school.reports.publish"),onNavigate:navigate,
    workingYearId,onWorkingYearChange:setWorkingYearId,
  };
  function renderSetting(id){
    if(teachingKinds[id])return <TeachingSettings key={chosen+id} schoolId={chosen} kind={teachingKinds[id]}
      canEdit={can("school.settings.write")} canReadAcademic={can("school.academic.read")}/>;
    const common={schoolId:chosen,schoolName,onNavigate:navigate,workingYearId,onWorkingYearChange:setWorkingYearId};
    const SettingView=modules[id]?.view;
    return {
      users:<UsersForm key={chosen} schoolId={chosen} onMessage={setMessage}/>,
      "cycle-access":<StaffOnboarding key={chosen+"-cycle"} schoolId={chosen} mode="access"/>,
      classes:<ClassSetup key={chosen} {...common}/>,
      numbering:<StudentNumberingSettings key={chosen} {...common}/>,
      form:<FormSettings key={chosen} {...common} canEdit={can("school.students.manage")}/>,
      "admission-policy":<AdmissionSettings key={chosen} {...panelProps} canConfigureCatalog={can("school.admissions.manage")}/>,
      fees:<FinancePanel key={chosen} schoolId={chosen} mode="settings" workingYearId={workingYearId} onWorkingYearChange={setWorkingYearId}/>,
      gateway:<AdmissionPaymentSettings key={chosen} schoolId={chosen}/>,
      amendments:<CouncilPanel key={chosen} schoolId={chosen} mode="amendments"/>,
      "parent-access":<SchoolParentAccess key={chosen} schoolId={chosen} canAssignRole={canUsers} canReadStudents={can("school.students.read")}/>,
      "staff-setup":<StaffPanel key={chosen} schoolId={chosen} mode="settings" workingYearId={workingYearId} onWorkingYearChange={setWorkingYearId}/>,
    }[id] || (SettingView && <SettingView key={chosen+id} {...panelProps}/>);
  }
  const tabBar=tabs.length>1&&page!=="staff"?<div className="yd-real-tabs" role="tablist">{tabs.map(([k,l])=><button type="button" role="tab" aria-selected={tab===k} key={k} className={tab===k?"active":""} onClick={()=>setSub(k)}>{l}</button>)}</div>:null;
  const schoolName=access?.school?.name||schools.find(s=>s.id===chosen)?.name||"Mon établissement";
  const selector=<div className="yd-school-select-wrap"><label className="yd-school-select"><Icon name="school" size={24}/>
    {schools.length>1?<select aria-label="Établissement" value={chosen} onChange={e=>{
      setAccess(null);setShowWorkspace(false);setChosen(e.target.value);navigate("dashboard");
    }}>{schools.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>:<b>{schoolName}</b>}
    {schools.length>1&&<Icon name="chevron" size={18} className="chev"/>}</label>
    {academicYears.length>0&&<label className="yd-school-select" title="Année scolaire de consultation">
      <Icon name="calendar" size={18}/>
      <select aria-label="Année de travail de l'établissement" value={workingYearId}
        onChange={e=>setWorkingYearId(e.target.value)}>
        {academicYears.map(y=><option key={y.id} value={y.id}>{y.name}{y.active?"":" · archivée"}</option>)}
      </select>
    </label>}
  </div>;
  const isSchoolParent=access?.role==="parent"&&!user?.is_platform_admin;
  if (isSchoolParent&&!showWorkspace) {
    const canUseSchoolWorkspace=nav.length>1;
    return <FamilyWorkspace accountView={accountView} onLogout={onLogout}
      onSchoolWorkspace={canUseSchoolWorkspace?()=>setShowWorkspace(true):undefined}/>;
  }
  let content;
  if (page==="account") content=<><PageHeader title="Sécurité du compte" subtitle="Mot de passe, double authentification et déconnexion" banner={false}/><div className="yd-real-body">{accountView}</div></>;
  else if (loaded&&schools.length===0) content=<><PageHeader title="Tableau de bord" subtitle="Aucun établissement n'est encore rattaché à ce compte"/><Card title="Aucun établissement attribué" icon="school"><p className="yd-card-sub">Contactez l'administrateur de YEM pour recevoir un compte rattaché à votre établissement.</p></Card></>;
  else if (!access) content=<Card title="Chargement de vos droits…" icon="shield"/>;
  else if (page==="settings"&&availableSettings.length) content=<SchoolSettings sections={availableSettings}
    selection={settingsSelection} onSelect={setSettingsSelection} render={renderSetting} isOwner={isOwner}
    onReturn={settingsReturn ? ()=>navigate(settingsReturn.page,settingsReturn.tab,settingsReturn.params) : undefined}/>;
  else if (section&&(hiddenTab||section.lives.some(l=>l.key===tab))) {
    const props={schoolId:chosen,schoolName,tabs:tabBar,advancedSettings,onNavigate:navigate,params,workingYearId,onWorkingYearChange:setWorkingYearId,canManage:perms.includes("school.students.manage"),canIssueTransfer:perms.includes("school.students.manage")&&perms.includes("school.admissions.decide"),canReceive:perms.includes("school.finance.receive")};
    const k=chosen+JSON.stringify(params);
    content={
      "students:cycle-list":<CycleWorkspace key={chosen} schoolId={chosen} access={access}/>,
      "students:live":<LiveStudents key={chosen} {...props}/>,
      "students:byclass":<ClassEnrollments key={chosen} {...props}/>,
      "students:new":<StudentForm key={k} {...props}/>,
      "students:fiche":<StudentFile key={k} {...props}/>,
      "students:import":<ImportStudents key={chosen} {...props}/>,
      "classes:live":<ClassWorkspace key={chosen} schoolId={chosen} onNavigate={navigate} canReadStudents={can("school.students.read")} advancedSettings={advancedSettings} workingYearId={workingYearId} onWorkingYearChange={setWorkingYearId}/>,
      "payments:live":<LivePayments key={k} {...props}/>,
      "payments:tracking":<PaymentTracking key={chosen} {...props}/>,
      "arrears:live":<LiveArrears key={chosen} {...props}/>,
      "parents:directory":<><PageHeader title={section.title} subtitle={section.subtitle} actions={advancedSettings}/>
        <div className="yd-real-body"><FamilyDirectory key={chosen} schoolId={chosen} onNavigate={navigate} workingYearId={workingYearId}/></div></>,
      "staff:directory":<><PageHeader title={section.title} subtitle={section.subtitle} actions={advancedSettings}/>
        <div className="yd-real-body"><StaffDirectory key={chosen} schoolId={chosen}
          onAdd={allowed("onboarding")?()=>navigate("staff","onboarding"):undefined}
          onAssign={availableSettings.some(group=>group.items.some(item=>item.id==="staff-setup"))
            ?()=>navigate("settings","staff-setup"):undefined}/></div></>,
    }[page+":"+tab];
  }
  else if (section) content=<>
    <PageHeader title={section.title} subtitle={section.subtitle} actions={page==="staff"&&section.lives.length>0
      ? <><Button onClick={()=>navigate("staff")}>Retour à l’équipe</Button>{advancedSettings}</> : advancedSettings}/>
    {tabBar}
    <div className="yd-real-body">{View&&<View key={chosen+"-"+tab} {...panelProps}
      {...(["finance","onboarding"].includes(tab)?{mode:"daily"}:{})}
      {...(tab==="assessments"?{canEdit:can("school.assessments.manage")}:{})}
      {...(tab==="reports"?{canPrepare:can("school.reports.manage")}:{})}
      {...(tab==="council"?{canManage:can("school.deliberations.manage"),canFinalize:can("school.deliberations.finalize")}:{})}
      {...(tab==="attendance"?{
        attendanceAssignedOnly:!can("school.attendance.read")&&can("school.attendance.assigned"),
        attendanceCanWrite:can("school.attendance.write")||can("school.attendance.assigned"),
        attendanceCanFinalize:can("school.attendance.finalize"),
        onSettings:can("school.settings.write")&&can("school.settings.read")?()=>navigate("settings","attendance-policy"):undefined}:{})}/>}</div>
  </>;
  else if (perms.includes("school.finance.read")) content=<>
    <LiveDashboard key={chosen} schoolId={chosen} schoolName={schoolName} roleLabel={roleLabel} onNavigate={navigate} canReceive={perms.includes("school.finance.receive")} workingYearId={workingYearId} onWorkingYearChange={setWorkingYearId}/>
    <MySchoolFunctions schoolId={chosen}/>
    <ModuleGrid visibleSections={visibleSections} navigate={navigate}/>
  </>;
  else content=<>
    <PageHeader title="Tableau de bord" subtitle={`Vue de pilotage de ${schoolName}`} badge={roleLabel||"Membre"} badgeIcon="crown"/>
    <MySchoolFunctions schoolId={chosen}/>
    {restricted&&<div className="yd-real-body"><p className="hint">Ce compte est limité aux cycles autorisés. Les modules non encore sécurisés par cycle sont temporairement indisponibles.</p></div>}
    <ModuleGrid visibleSections={visibleSections} navigate={navigate}/>
  </>;
  const schoolCode = access?.school?.id === chosen && access.school.login_code;
  return <Shell nav={nav} active={page} onNavigate={navigate} notifications={0} schoolSelector={selector}
    userMenu={<UserMenu user={user} roleLabel={roleLabel} onAccount={()=>navigate("account")}
      onFamilyWorkspace={isSchoolParent?()=>setShowWorkspace(false):undefined} onLogout={onLogout}/>}>
    {message&&<p role="status" className="pc-alert">{message}</p>}
    {page==="dashboard"&&schoolCode&&canUsers&&<Card title="Code de connexion de l’établissement" icon="school">
      <label className="field">Code à communiquer au personnel
        <input readOnly value={schoolCode} onFocus={event=>event.target.select()} />
      </label>
      <Button type="button" onClick={async()=>{
        try {await navigator.clipboard.writeText(schoolCode);setMessage("Code établissement copié.");}
        catch {setMessage("Sélectionnez le code puis copiez-le.");}
      }}>Copier le code</Button>
    </Card>}
    {content}
    <footer className="yd-brand-footer"><span>YEM — Gestion scolaire &amp; universitaire</span><span>Développé par <strong>BWETEK Informatyk</strong></span></footer>
  </Shell>;
}
