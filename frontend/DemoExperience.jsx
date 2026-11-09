import React, {useState} from "react";
import {Shell,Icon,Card,Metric,PageHeader,Status,Button,YemLogo,NAV,LineChart,Donut,Table,InfoRow,SearchBox} from "./yem-ui.jsx";
import {SchoolSettings} from "./SchoolSettings.jsx";
import {createDemoState,ROUTE_LABELS,DEMO_YEARS,DEMO_CURRENT_YEAR,SCHOOL_ROLES,fcfa,remaining,schoolOf,availableRoutes,fakeId} from "./demo-data.js";
import "./yem-desktop.css";
import "./yem-demo.css";

// Identique au menu latéral du véritable SchoolDashboard (mêmes identifiants et libellés).
const SCHOOL_NAV = [...NAV.slice(0,2),["classes","layers","Classes"],...NAV.slice(2)]
  .map(([id,icon,label])=>[id,icon,id==="bulletins"?"Évaluations et notes":label]);
const DEMO_TABS={
  students:[["live","Liste des élèves"],["byclass","Inscriptions par classe"]],
  classes:[["live","Classes et effectifs"]],
  payments:[["finance","Frais et encaissements"],["live","Caisse du jour"],["tracking","Suivi des paiements"]],
  arrears:[["live","Impayés"]],
  bulletins:[["assessments","Évaluations et notes"],["reports","Bulletins"],["council","Conseils et décisions"]],
  absences:[["attendance","Appels et absences"]],
  parents:[["directory","Parents par classe"]],
  staff:[["directory","Équipe de l'établissement"],["onboarding","Ajouter un collaborateur"]],
};
const DEMO_SETTING_SECTIONS=[
  {id:"access",title:"Droits généraux",icon:"shield",items:[
    {id:"users",label:"Comptes et accès"},{id:"roles",label:"Rôles et droits d’accès"},
    {id:"cycle-access",label:"Accès par cycle"}]},
  {id:"school",title:"Classes de l’établissement",icon:"school",items:[
    {id:"classes",label:"Classes"},{id:"form",label:"Fiche d’inscription"},
    {id:"numbering",label:"Matricules"},{id:"curriculum",label:"Matières et programmes"},
    {id:"report-policy",label:"Barèmes et bulletins"},{id:"council-policy",label:"Décisions du conseil"},
    {id:"amendments",label:"Rectifier un bulletin"},{id:"timetable",label:"Emplois du temps"},
    {id:"academic",label:"Années et cycles"}]},
  {id:"admissions",title:"Admissions",icon:"adduser",items:[{id:"admission-policy",label:"Voies d’admission et fiche publique"}]},
  {id:"payments",title:"Paiements",icon:"card",items:[
    {id:"fees",label:"Tarifs et échéances"},{id:"gateway",label:"Paiement des dossiers et Mobile Money"}]},
  {id:"attendance",title:"Absences et retards",icon:"calendar",items:[{id:"attendance-policy",label:"Statuts de présence"}]},
  {id:"parents",title:"Parents",icon:"users",items:[{id:"parent-access",label:"Vérification et accès des responsables légaux"}]},
  {id:"staff",title:"Personnel",icon:"idcard",items:[
    {id:"organization",label:"Organigramme et fonctions"},
    {id:"staff-setup",label:"Comptes du personnel et affectations"}]},
];
const DEMO_ADVANCED={students:"form",classes:"classes",admissions:"admission-policy",
  payments:"fees",bulletins:"report-policy",absences:"attendance-policy",
  parents:"parent-access",staff:"staff-setup"};
const PARENT_NAV = [
  ["parent","home","Mes enfants"],["parent-payments","card","Frais & paiements"],
  ["parent-results","file","Notes & bulletins"],["parent-absences","calendar","Absences"],
  ["parent-admissions","adduser","Préinscriptions"],
];
const PLATFORM_NAV = [
  ["platform","home","Vue d'ensemble"],["schools","school","Établissements"],
  ["accounts","users","Utilisateurs & rôles"],
];
const defaultPage = {school:"dashboard",parent:"parent",platform:"platform"};
const channels = ["SingPay (simulation)","Espèces (simulation)","Virement (simulation)"];
function F({label,children}){return <label className="demo-field"><span>{label}</span>{children}</label>;}
function Empty({children}){return <p className="demo-empty">{children}</p>;}
function DemoButton({children,onClick,primary=false,icon="chevronright",disabled=false}){
  return <Button primary={primary} icon={icon} disabled={disabled} onClick={onClick}>{children}</Button>;
}
function PersonAvatar({name}){return <span className="demo-avatar" aria-hidden="true">{name.split(" ").slice(0,2).map(v=>v[0]).join("")}</span>;}
function moneyStatus(invoice){
  return remaining(invoice)===0?["green","Réglé"]:invoice.paid?["yellow","Partiel"]:["red","À payer"];
}
function DemoModal({mode,form,setForm,school,schools,student,invoice,onClose,onSubmit}){
  const change=(key,v)=>setForm(old=>({...old,[key]:v}));
  const titles={
    student:"Ajouter un élève — simulation",admission:"Nouvelle candidature — simulation",
    classroom:"Créer une classe — simulation",staff:"Ajouter un membre du personnel — simulation",
    school:"Créer un établissement — simulation",payment:"Simuler un règlement",
    receipt:"Reçu fictif de paiement",edit:"Modifier la fiche élève — simulation",
    export:"Aperçu d'export — démonstration",
    generation:"Générer des divisions — simulation",subject:"Ajouter une matière — simulation",
    timetable:"Planifier un cours — simulation",
  };
  const input=(key,label,placeholder="",type="text",required=true)=><F label={label}>
    <input type={type} required={required} placeholder={placeholder} value={form[key]||""}
      onChange={e=>change(key,e.target.value)}/></F>;
  const selectedSchool=schools.find(s=>s.id===(form.school||school?.id))||school||schools[0];
  const defaultStaffRole=school?.type==="Maternelle"?"Éducatrice / Maîtresse":
    school?.type==="Lycée technique"?"Enseignant technique":"Enseignant";
  const allowedRoles=SCHOOL_ROLES[school?.type]||SCHOOL_ROLES["Collège / Lycée"];
  const selects=(key,label,options)=><F label={label}><select value={form[key]||options[0]} onChange={e=>change(key,e.target.value)}>
    {options.map(o=><option key={o} value={o}>{o}</option>)}</select></F>;
  return <div className="demo-overlay" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}>
    <section className="demo-dialog" role="dialog" aria-modal="true" aria-label={titles[mode]||"Fenêtre de démonstration"}>
      <header className="demo-dialog-head"><div><small>YEM · DONNÉES FICTIVES</small><h2>{titles[mode]}</h2></div>
        <button type="button" onClick={onClose} aria-label="Fermer la fenêtre"><Icon name="close"/></button></header>
      {mode==="receipt"?<div className="demo-receipt">
        <YemLogo compact/><p><Status>Règlement simulé</Status></p>
        <dl><div><dt>Référence fictive</dt><dd>{form.reference}</dd></div>
          <div><dt>Élève</dt><dd>{form.student}</dd></div><div><dt>École</dt><dd>{form.schoolName}</dd></div>
          <div><dt>Montant</dt><dd>{fcfa(Number(form.amount))}</dd></div>
          <div><dt>Moyen</dt><dd>{form.method}</dd></div></dl>
        <p className="demo-emphasis">Aucun argent n'a été transféré. Ce document n'a aucune valeur comptable.</p>
        <div className="demo-actions"><DemoButton onClick={onClose} icon="check" primary>Fermer le reçu</DemoButton></div>
      </div>:mode==="export"?<div><p>Les exports réels existent dans YEM, mais cette présentation ne touche à aucun fichier d'élève réel.</p>
        <pre className="demo-export-preview">Élève;Classe;Établissement\nEssono Grâce;6e A;Lycée Démonstration\nMinko Alain;5e B;Lycée Démonstration</pre>
        <DemoButton onClick={onClose} primary>Fermer l'aperçu</DemoButton></div>:
      <form className="demo-dialog-form" onSubmit={e=>{e.preventDefault();onSubmit(mode,form);}}>
        {mode==="student"||mode==="edit"?<div className="demo-fields">
          {input("name","Nom et prénoms","Ex. Ndong Marc")}
          {selects("level","Classe / niveau",[
            ...new Set([
              ...form.state.classes.filter(c=>c.school===school.id).map(c=>c.name),
              ...school.levels.map(l=>l+" A"),
            ]),
          ])}
          {input("guardian","Responsable légal","Ex. Mme Ndong")}
          {input("phone","Téléphone du responsable","+241 ...","tel",false)}
        </div>:null}
        {mode==="admission"&&<div className="demo-fields">
          {input("name","Nom et prénoms du candidat","Ex. Nguema Léa")}
          <F label="Établissement"><select value={form.school||school?.id||schools[0].id}
            onChange={e=>setForm(old=>({...old,school:e.target.value,
              level:schools.find(s=>s.id===e.target.value)?.levels[0]||"",
              route:"direct"}))}>
            {schools.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></F>
          {selects("level","Niveau demandé",selectedSchool.levels)}
          <F label="Voie d'admission"><select value={form.route||"direct"} onChange={e=>change("route",e.target.value)}>
            {Object.entries(ROUTE_LABELS).filter(([k])=>availableRoutes(form.state,selectedSchool.id).includes(k))
              .map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></F>
          {form.route!=="direct"&&input("origin","Établissement d'origine","École précédente","text",false)}
        </div>}
        {mode==="classroom"&&<div className="demo-fields">{input("name","Nom de la classe","Ex. 6e C")}
          {input("capacity","Capacité maximale","35","number")}</div>}
        {mode==="staff"&&<div className="demo-fields">{input("name","Nom du personnel","Ex. Mme Mba")}
          {selects("role","Fonction principale",[defaultStaffRole,...allowedRoles.filter(r=>r!==defaultStaffRole)])}
          {selects("secondaryRole","Seconde fonction (facultative)",["Aucune",...(SCHOOL_ROLES[school?.type]||SCHOOL_ROLES["Collège / Lycée"])])}
          {selects("cycle","Affectation / cycle",["Tous les cycles",...school.levels])}
          <label className="demo-check"><input type="checkbox" checked={Boolean(form.hasAccount)}
            onChange={e=>change("hasAccount",e.target.checked)}/> Créer aussi un compte utilisateur (simulation)</label>
          <p className="demo-hint">Un personnel peut exercer plusieurs fonctions. Le compte de connexion reste facultatif.</p>
        </div>}
        {mode==="school"&&<div className="demo-fields">{input("name","Nom de l'établissement","Ex. Groupe scolaire Démonstration")}
          {selects("type","Type d'établissement",["Primaire","Maternelle","Collège / Lycée","Lycée technique"])}
          {input("city","Ville","Libreville")}{input("owner","Propriétaire / Fondateur (facultatif)","Ex. Mme Mba","text",false)}</div>}
        {mode==="generation"&&<div className="demo-fields">
          {selects("level","Niveau",school.levels)}
          <F label="Nombre de divisions"><input type="number" required min={1} max={13} value={form.count??2}
            onChange={e=>change("count",e.target.value)}/></F>
          <F label="Capacité par division"><input type="number" required min={1} max={200} value={form.capacity??35}
            onChange={e=>change("capacity",e.target.value)}/></F>
          <p className="demo-hint">Exemple : 6e A, 6e B, 6e C. Les doublons sont ignorés.</p>
        </div>}
        {mode==="subject"&&<div className="demo-fields">
          {input("name","Matière","Ex. Sciences physiques")}
          {selects("level","Niveau",school.levels)}
          {input("coefficient","Coefficient","2","number")}
        </div>}
        {mode==="timetable"&&<div className="demo-fields">
          {selects("className","Classe",form.state.classes.filter(x=>x.school===school.id&&x.year===form.year).map(x=>x.name))}
          {selects("day","Jour",["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi"])}
          {selects("slot","Créneau",["08:00–09:00","09:00–10:00","10:00–11:00","11:00–12:00","13:00–14:00","14:00–15:00"])}
          {input("subject","Matière","Ex. Mathématiques")}
          {input("teacher","Enseignant","Ex. Mme C. Mba")}
          {input("room","Salle","Ex. Salle 1")}
        </div>}
        {mode==="payment"&&<div className="demo-fields">
          <p>Élève : <b>{student?.name}</b><br/>Frais : <b>{invoice?.label}</b></p>
          <p>Solde à payer : <strong>{fcfa(invoice?remaining(invoice):0)}</strong></p>
          <F label="Montant à simuler (FCFA)"><input type="number" required min={1} max={remaining(invoice)}
            step={1} value={form.amount||""} onChange={e=>change("amount",e.target.value)}/></F>
          {selects("method","Mode simulé",channels)}
          <p className="demo-emphasis">Simulation uniquement. Aucun appel à SingPay, aucun débit ni reçu réel.</p>
        </div>}
        <div className="demo-dialog-footer"><button type="button" onClick={onClose}>Annuler</button>
          <button className="demo-main-btn" type="submit"><Icon name="check" size={19}/>
            {mode==="payment"?"Confirmer la simulation":"Enregistrer la simulation"}</button></div>
      </form>}
    </section>
  </div>;
}

export default function DemoExperience(){
  const [state,setState]=useState(createDemoState);
  const [year,setYear]=useState(DEMO_CURRENT_YEAR);
  const isClosed=year==="2025-2026";
  const [role,setRole]=useState("school");
  const [schoolId,setSchoolId]=useState("lycee");
  const [page,setPage]=useState("dashboard");
  const [sub,setSub]=useState("");
  const [settingsSelection,setSettingsSelection]=useState(null);
  const [settingsReturn,setSettingsReturn]=useState(null);
  const [selectedStudent,setSelectedStudent]=useState("s1");
  const [selectedAdmission,setSelectedAdmission]=useState("a1");
  const [selectedChild,setSelectedChild]=useState("s1");
  const [selectedInvoice,setSelectedInvoice]=useState("f1");
  const [statusFilter,setStatusFilter]=useState("all");
  const [search,setSearch]=useState("");
  const [modal,setModal]=useState(null);
  const [form,setForm]=useState({});
  const [notice,setNotice]=useState("");
  const [resultTab,setResultTab]=useState("notes");
  const school=schoolOf(state,schoolId)||state.schools[0];
  const currentStudents=state.students.filter(x=>x.school===school.id&&x.year===year);
  const currentApplications=state.applications.filter(x=>x.school===school.id&&x.year===year);
  const currentInvoices=state.invoices.filter(x=>x.school===school.id&&x.year===year);
  const currentClasses=state.classes.filter(x=>x.school===school.id&&x.year===year);
  const currentStaff=state.staff.filter(x=>x.school===school.id&&x.year===year);
  const chosen=currentStudents.find(x=>x.id===selectedStudent)||currentStudents[0];
  const application=currentApplications.find(x=>x.id===selectedAdmission)||currentApplications[0];
  const parentChildren=state.students.filter(x=>["s1","s4","s7"].includes(x.id)&&x.year===year);
  const child=parentChildren.find(x=>x.id===selectedChild)||parentChildren[0];
  const childSchool=schoolOf(state,child?.school);
  const activeInvoice=state.invoices.find(x=>x.id===selectedInvoice);
  const pendingTotal=currentInvoices.reduce((sum,f)=>sum+remaining(f),0);
  const parentsDue=state.invoices.filter(f=>f.student===child?.id&&f.year===year);
  const nav=role==="school"?SCHOOL_NAV:role==="parent"?PARENT_NAV:PLATFORM_NAV;
  const title=role==="school"?"Direction — "+school.name:role==="parent"?"Espace parent":"Console plateforme";
  const visibleStudents=currentStudents.filter(x=>(x.name+" "+x.level+" "+x.guardian).toLowerCase().includes(search.toLowerCase())&&(statusFilter==="all"||x.status===statusFilter));
  const visibleAdmissions=currentApplications.filter(x=>(x.name+" "+x.level+" "+ROUTE_LABELS[x.route]).toLowerCase().includes(search.toLowerCase()));

  function message(txt){setNotice(txt);}
  function open(kind,initial={}){
    if(isClosed&&kind!=="export"){message("Année clôturée : consultation seule. Sélectionnez une année ouverte pour modifier.");return;}
    setForm({state,year,...initial});setModal(kind);setNotice("");
  }
  function enter(nextRole){
    setRole(nextRole);setPage(defaultPage[nextRole]);setSub("");setSettingsSelection(null);setNotice("");setSearch("");
    setStatusFilter("all");setModal(null);
  }
  function pickSchool(id){
    setSchoolId(id);setPage("dashboard");setSub("");setSearch("");
    setSelectedStudent(state.students.find(s=>s.school===id)?.id||"");
    setSelectedAdmission(state.applications.find(a=>a.school===id)?.id||"");
  }
  function navigate(id,nextSub="",extra=null){
    setPage(id);setSub(nextSub);setSearch("");setNotice("");
    if(id==="settings"){
      const group=DEMO_SETTING_SECTIONS.find(section=>section.items.some(item=>item.id===nextSub));
      setSettingsSelection(group?{section:group.id,item:nextSub}:null);
    }else{
      setSettingsReturn(null);
    }
  }
  function goAdvanced(target){
    setSettingsReturn({page,sub});
    navigate("settings",target);
  }
  const demoTabs=(id)=>DEMO_TABS[id]?.length>1&&id!=="staff"?
    <div className="yd-real-tabs" role="tablist">{DEMO_TABS[id].map(([key,label])=>
      <button type="button" role="tab" aria-selected={(sub||DEMO_TABS[id][0][0])===key}
        className={(sub||DEMO_TABS[id][0][0])===key?"active":""} key={key}
        onClick={()=>setSub(key)}>{label}</button>)}</div>:null;
  const advanced=(id)=>DEMO_ADVANCED[id]?
    <Button icon="settings" className="small" onClick={()=>goAdvanced(DEMO_ADVANCED[id])}>Paramètres avancés</Button>:null;
  function updateStudent(id,fields){
    setState(old=>({...old,students:old.students.map(s=>s.id===id?{...s,...fields}:s)}));
  }
  function admissionAction(action){
    if(isClosed){message("Année clôturée : décision non modifiable.");return;}
    if(!application)return;
    if(action==="approve"&&(!application.eligible||!application.documents)){
      message("Vérifiez d'abord l'éligibilité et les pièces. Un concours réussi ne vaut pas inscription.");return;
    }
    if(action==="enroll"&&application.status!=="Accepté"){
      message("La direction doit accepter cette candidature avant son inscription.");return;
    }
    if(action==="enroll"){
      setState(old=>{
        const id=fakeId("s",old.students);
        const data={id,school:application.school,name:application.name,level:application.level+" A",
          guardian:"Responsable à compléter",phone:"",status:"Inscrit",average:null,absences:0,year};
        return {...old,students:[...old.students,data],
          applications:old.applications.map(a=>a.id===application.id?{...a,status:"Inscrit"}:a),
          events:[{kind:"Admission convertie",who:application.name},...old.events]};
      });
      message("Élève inscrit dans la démonstration, sans écriture en base.");return;
    }
    setState(old=>({...old,applications:old.applications.map(a=>a.id===application.id?{
      ...a,...(action==="verify"?{eligible:true,documents:true,status:"En étude"}:
        action==="approve"?{status:"Accepté"}:action==="wait"?{status:"Liste d'attente"}:{status:"Refusé"})
    }:a)}));
    message(action==="verify"?"Pièces et éligibilité marquées vérifiées (simulation).":
      action==="approve"?"Admission acceptée. L'inscription reste une étape séparée.":
        "Décision enregistrée uniquement dans la démonstration.");
  }
  function submit(kind,values){
    if(isClosed){message("Année clôturée : modification interdite.");setModal(null);return;}
    if(kind==="student"||kind==="edit"){
      const name=values.name?.trim(),guardian=values.guardian?.trim();
      if(!name||!guardian){message("Renseignez le nom et le responsable.");return;}
      if(kind==="student"){
        const record={id:fakeId("s",state.students),school:school.id,name,guardian,
          level:values.level||school.levels[0]+" A",phone:values.phone||"",status:"Inscrit",average:null,absences:0,year};
        setState(old=>({...old,students:[...old.students,record],events:[{kind:"Élève ajouté",who:name},...old.events]}));
        setSelectedStudent(record.id);
      }else{
        updateStudent(values.id,{name,guardian,phone:values.phone||"",level:values.level});
      }
      message("Fiche mise à jour dans les données fictives.");setModal(null);return;
    }
    if(kind==="admission"){
      const name=values.name?.trim();if(!name){message("Nom du candidat requis.");return;}
      const id=fakeId("a",state.applications);
      const chosenSchool=schoolOf(state,values.school||school.id)||school;
      const item={id,school:chosenSchool.id,name,level:values.level||chosenSchool.levels[0],
        route:values.route||"direct",status:"En attente",eligible:values.route==="direct",
        documents:values.route==="direct",origin:values.origin||"",parentDemo:Boolean(values.parentDemo),year};
      setState(old=>({...old,applications:[...old.applications,item],
        events:[{kind:"Candidature créée",who:name},...old.events]}));
      setSelectedAdmission(id);message("Candidature créée en mode démonstration.");setModal(null);return;
    }
    if(kind==="classroom"){
      const capacity=Number(values.capacity);
      if(!values.name?.trim()||!Number.isInteger(capacity)||capacity<1||capacity>200){
        message("Nom et capacité entre 1 et 200 requis.");return;
      }
      if(values.id){
        setState(old=>({...old,classes:old.classes.map(x=>x.id===values.id?{...x,name:values.name.trim(),capacity}:x)}));
      }else{
        if(currentClasses.some(x=>x.name.toLowerCase()===values.name.trim().toLowerCase())){
          message("Cette classe existe déjà pour l'année sélectionnée.");return;
        }
        setState(old=>({...old,classes:[...old.classes,{id:fakeId("c",old.classes),
          school:school.id,name:values.name.trim(),capacity,year}]}));
      }
      message("Classe créée dans la démonstration.");setModal(null);return;
    }
    if(kind==="generation"){
      const count=Number(values.count),capacity=Number(values.capacity),level=values.level||school.levels[0];
      if(!Number.isInteger(count)||count<1||count>13||!Number.isInteger(capacity)||capacity<1||capacity>200){
        message("Choisir 1 à 13 divisions et une capacité de 1 à 200.");return;
      }
      let added=0;
      setState(old=>{
        const classes=[...old.classes];
        for(let n=0;n<count;n++){
          const name=level+" "+String.fromCharCode(65+n);
          if(classes.some(x=>x.school===school.id&&x.year===year&&x.name===name))continue;
          classes.push({id:fakeId("c",classes),school:school.id,year,name,capacity});added++;
        }
        return {...old,classes};
      });
      message("Divisions générées dans la démonstration (les doublons sont ignorés).");
      setModal(null);return;
    }
    if(kind==="subject"){
      const coefficient=Number(values.coefficient);
      if(!values.name?.trim()||!Number.isFinite(coefficient)||coefficient<=0){
        message("Matière et coefficient positif requis.");return;
      }
      setState(old=>({...old,subjects:[...old.subjects,{
        id:fakeId("m",old.subjects),school:school.id,year,name:values.name.trim(),
        level:values.level||school.levels[0],coefficient
      }]}));
      message("Matière ajoutée aux données de présentation.");setModal(null);return;
    }
    if(kind==="timetable"){
      const {className,day,slot,subject,teacher,room}=values;
      if(!className||!day||!slot||!subject?.trim()||!teacher?.trim()||!room?.trim()){
        message("Renseignez la classe, le cours, l'enseignant, la salle et le créneau.");return;
      }
      const collision=state.timetable.find(t=>t.school===school.id&&t.year===year&&t.day===day&&t.slot===slot&&
        (t.className===className||t.teacher.toLowerCase()===teacher.trim().toLowerCase()||t.room.toLowerCase()===room.trim().toLowerCase()));
      if(collision){message("Conflit détecté : classe, enseignant ou salle déjà occupé sur ce créneau.");return;}
      setState(old=>({...old,timetable:[...old.timetable,{
        id:fakeId("t",old.timetable),school:school.id,year,className,day,slot,
        subject:subject.trim(),teacher:teacher.trim(),room:room.trim()
      }]}));
      message("Cours planifié dans la démonstration.");setModal(null);return;
    }
    if(kind==="staff"){
      if(!values.name?.trim()){message("Nom requis.");return;}
      const role=values.role||(school.type==="Maternelle"?"Éducatrice / Maîtresse":school.type==="Lycée technique"?"Enseignant technique":"Enseignant");
      const roles=[role,...(values.secondaryRole&&values.secondaryRole!=="Aucune"&&values.secondaryRole!==role?[values.secondaryRole]:[])];
      setState(old=>({...old,staff:[...old.staff,{id:fakeId("p",old.staff),school:school.id,year,
        name:values.name.trim(),role,roles,hasAccount:Boolean(values.hasAccount),
        cycles:[values.cycle||"Tous les cycles"]}]}));
      message(values.hasAccount?"Compte et fonctions fictifs créés. Aucun accès réel n'est ouvert.":
        "Personnel fictif créé sans compte de connexion.");setModal(null);return;
    }
    if(kind==="school"){
      if(!values.name?.trim()||!values.city?.trim()){message("Nom et ville requis.");return;}
      const id="demo-"+(state.schools.length+1);
      const levels=values.type==="Maternelle"?["Petite section","Moyenne section","Grande section"]:
        values.type==="Primaire"?["1ère année","2e année","3e année","4e année","5e année"]:
          ["6e","5e","4e","3e","2nde","1ère","Tle"];
      setState(old=>({...old,schools:[...old.schools,{id,name:values.name.trim(),
        type:values.type,city:values.city.trim(),levels,head:"À désigner",fee:45000,owner:values.owner||"À désigner"}]}));
      message("Établissement fictif créé.");setModal(null);return;
    }
    if(kind==="payment"){
      const amount=Number(values.amount),inv=state.invoices.find(x=>x.id===values.invoiceId);
      if(!inv||!Number.isInteger(amount)||amount<=0||amount>remaining(inv)){
        message("Le montant doit être positif et inférieur ou égal au solde.");return;
      }
      const ref="DEMO-"+String(state.events.length+1).padStart(5,"0");
      setState(old=>({...old,invoices:old.invoices.map(x=>x.id===inv.id?{
        ...x,paid:x.paid+amount}:x),events:[{kind:"Paiement simulé",who:ref},...old.events]}));
      const invStudent=state.students.find(s=>s.id===inv.student);
      const invSchool=schoolOf(state,inv.school);
      setForm({reference:ref,schoolName:invSchool?.name,student:invStudent?.name,
        amount,method:values.method||channels[0]});
      setModal("receipt");message("Simulation réussie : aucun mouvement d'argent.");return;
    }
  }
  function showPayment(inv){
    if(isClosed){message("Année clôturée : aucun encaissement possible.");return;}
    if(remaining(inv)<=0){message("Ce frais est déjà réglé dans la démonstration.");return;}
    setSelectedInvoice(inv.id);open("payment",{invoiceId:inv.id,
      amount:String(remaining(inv)),method:channels[0]});
  }
  function dashboard(){
    const totalPaid=currentInvoices.reduce((sum,f)=>sum+f.paid,0);
    const arrears=currentInvoices.filter(f=>remaining(f)>0);
    const lateFamilies=new Set(arrears.map(f=>f.student)).size;
    const months=["Juin","Juil.","Août","Sept.","Oct.","Nov."];
    const monthSeries=[.38,.53,.31,.7,.86,1].map(x=>Math.round(totalPaid*x));
    const max=Math.max(100000,Math.ceil(totalPaid/25000)*25000);
    const byMethod=[Math.floor(totalPaid*.45),Math.floor(totalPaid*.3),Math.floor(totalPaid*.2),
      Math.max(0,totalPaid-Math.floor(totalPaid*.45)-Math.floor(totalPaid*.3)-Math.floor(totalPaid*.2))];
    return <>
      <div className="yd-view-filters">
        <label>Année scolaire <select aria-label="Année de consultation" value={year}
          onChange={e=>setYear(e.target.value)}>{DEMO_YEARS.map(y=><option key={y}>{y}</option>)}</select></label>
        <label>Devise de consultation <select aria-label="Devise de consultation" defaultValue="XAF">
          <option value="XAF">XAF</option></select></label>
      </div>
      <PageHeader title="Tableau de bord" subtitle={`Vue de pilotage de ${school.name} — novembre 2026`}
        badge="Direction" badgeIcon="crown"/>
      <div className="yd-metrics five">
        <Metric icon="coins" label="Encaissé ce mois" value={fcfa(totalPaid)} trend="none" trendLabel="données de présentation"/>
        <Metric icon="file" label="Restant dû" value={fcfa(pendingTotal)} trend="none" trendLabel="toutes échéances"/>
        <Metric icon="users" label="Élèves actifs" value={String(currentStudents.length)} trend="none" trendLabel={year}/>
        <Metric icon="alert" label="Familles en retard" value={String(lateFamilies)} trend="none" trendLabel={fcfa(pendingTotal)+" échus"}/>
        <Metric icon="receipt" label="Paiements aujourd’hui" value={String(state.events.filter(x=>x.kind==="Paiement simulé").length)}
          trend="none" trendLabel="simulations uniquement"/>
      </div>
      <div className="yd-grid dash-main">
        <Card title="Évolution des encaissements" icon="barchart" subtitle="Montants encaissés (FCFA) sur les 6 derniers mois — exemple fictif">
          <LineChart points={monthSeries} labels={months} min={0} max={max} step={max/4}/>
        </Card>
        <Card title="Répartition des moyens de paiement" icon="wallet">
          <Donut size={160} values={byMethod} centerTop={totalPaid.toLocaleString("fr-FR")} centerBottom={"FCFA\nencaissés"}
            legend={["Airtel Money","Moov Money","Espèces","Virement"].map((label,i)=>
              [label+" : "+(totalPaid?Math.round(byMethod[i]/totalPaid*100):0)+" %","("+fcfa(byMethod[i])+")"])}/>
        </Card>
        <Card title="Actions rapides" icon="bolt" className="quick">
          <DemoButton icon="card" primary onClick={()=>navigate("payments","live")}>Nouvel encaissement</DemoButton>
          <DemoButton icon="mail" onClick={()=>navigate("arrears")}>Préparer les relances</DemoButton>
          <DemoButton icon="adduser" onClick={()=>{navigate("students","live");open("student",{level:school.levels[0]+" A"});}}>Inscrire un élève</DemoButton>
          <DemoButton icon="users" onClick={()=>navigate("students","byclass")}>Inscriptions par classe</DemoButton>
          <DemoButton icon="file" onClick={()=>navigate("bulletins")}>Générer les bulletins</DemoButton>
        </Card>
      </div>
      <div className="yd-grid dash-bottom">
        <Card title="Retardataires prioritaires" icon="users">
          <Table headers={["#","Élève","Classe","Montant dû","Statut"]}
            rows={arrears.slice(0,5).map((f,i)=>{
              const pupil=currentStudents.find(s=>s.id===f.student);
              return [i+1,pupil?.name||"—",pupil?.level||"—",fcfa(remaining(f)),<Status tone="red">En retard</Status>];
            })}/>
        </Card>
        <Card title="Derniers paiements du jour" icon="receipt">
          <Table headers={["Élève","Classe","Montant","Mode","Heure"]}
            rows={state.events.filter(x=>x.kind==="Paiement simulé").slice(0,5)
              .map((x)=>[x.who,"—","Simulé","Démo","—"])}/>
          {!state.events.some(x=>x.kind==="Paiement simulé")&&<Empty>Aucun paiement simulé aujourd’hui.</Empty>}
        </Card>
      </div>
      <div className="yd-real-body"><Card title="Modules de l'établissement" icon="school">
        <div className="pc-module-grid">{SCHOOL_NAV.filter(([id])=>id!=="dashboard").map(([id,icon,label])=>
          <button type="button" key={id} onClick={()=>navigate(id)}>
            <Icon name={icon} size={26}/><b>{label}</b><small>Consulter les données de démonstration</small>
          </button>)}</div>
      </Card></div>
    </>;
  }
  function students(advancedAction=null,tabs=null){
    return <><PageHeader title="Gestion des élèves" subtitle="Inscriptions, classes, responsables et suivi administratif" actions={advancedAction}/>{tabs}
      <div className="demo-toolbar"><input type="search" aria-label="Rechercher un élève" placeholder="Rechercher élève, classe ou responsable…"
        value={search} onChange={e=>setSearch(e.target.value)}/>
        <select aria-label="Filtrer par statut" value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}>
          <option value="all">Tous les statuts</option><option value="Inscrit">Inscrit</option>
        </select>
        <DemoButton primary icon="adduser" onClick={()=>open("student",{level:school.levels[0]+" A"})}>Nouvel élève</DemoButton>
        <DemoButton icon="excel" onClick={()=>open("export")}>Aperçu d'export</DemoButton></div>
      <div className="demo-grid-split">
        <Card title={"Élèves ("+visibleStudents.length+")"} icon="users">
          <div className="demo-table-wrap"><table><thead><tr><th>Élève</th><th>Classe</th><th>Statut</th></tr></thead>
            <tbody>{visibleStudents.map(s=><tr key={s.id} className={chosen?.id===s.id?"demo-selected":""}>
              <td><button type="button" className="demo-name" onClick={()=>setSelectedStudent(s.id)}>{s.name}</button></td>
              <td>{s.level}</td><td><Status>{s.status}</Status></td>
            </tr>)}</tbody></table>{!visibleStudents.length&&<Empty>Aucun élève ne correspond au filtre.</Empty>}</div>
        </Card><Card title="Fiche élève" icon="idcard">
          {chosen?<><div className="demo-profile"><PersonAvatar name={chosen.name}/>
            <div><h3>{chosen.name}</h3><span>{chosen.level} · {chosen.status}</span></div></div>
            <dl className="demo-dl"><div><dt>Responsable</dt><dd>{chosen.guardian}</dd></div>
              <div><dt>Contact</dt><dd>{chosen.phone||"À compléter"}</dd></div>
              <div><dt>Absences</dt><dd>{chosen.absences} jour(s)</dd></div>
              <div><dt>Évaluation</dt><dd>{chosen.average===null?"Compétences / non renseigné":chosen.average+"/20"}</dd></div></dl>
            <div className="demo-actions"><DemoButton primary icon="edit" onClick={()=>open("edit",chosen)}>Modifier la fiche</DemoButton>
              <DemoButton icon="coins" onClick={()=>{setSelectedInvoice(state.invoices.find(f=>f.student===chosen.id&&f.year===year)?.id||"");setPage("payments");}}>Frais de l'élève</DemoButton></div>
          </>:<Empty>Sélectionne un élève pour ouvrir sa fiche.</Empty>}
        </Card>
      </div></>;
  }
  function admissions(advancedAction=null){
    return <><PageHeader title="Admissions et préinscriptions" subtitle="Consultez les demandes et suivez leur inscription" actions={advancedAction}/>
      <div className="demo-toolbar"><input aria-label="Rechercher une candidature" placeholder="Rechercher candidature ou voie…" value={search}
        onChange={e=>setSearch(e.target.value)}/>
        <DemoButton icon="adduser" primary onClick={()=>open("admission",{school:school.id,route:"direct",level:school.levels[0]})}>Nouvelle candidature</DemoButton>
      </div><div className="demo-grid-split">
        <Card title="Demandes reçues" icon="users">
          {visibleAdmissions.map(a=><button className={"demo-line demo-line-button "+(application?.id===a.id?"demo-selected":"")}
            key={a.id} type="button" onClick={()=>setSelectedAdmission(a.id)}>
            <b>{a.name}</b><span>{a.level} · {ROUTE_LABELS[a.route]}</span><Status tone={a.status==="Refusé"?"red":"green"}>{a.status}</Status>
          </button>)}{!visibleAdmissions.length&&<Empty>Aucune candidature.</Empty>}
        </Card>
        <Card title="Dossier de candidature" icon="file">
          {application?<><div className="demo-profile"><PersonAvatar name={application.name}/><div><h3>{application.name}</h3>
            <span>{ROUTE_LABELS[application.route]} · {application.level}</span></div></div>
            <dl className="demo-dl"><div><dt>Établissement d'origine</dt><dd>{application.origin||"Non renseigné"}</dd></div>
              <div><dt>Éligibilité vérifiée</dt><dd>{application.eligible?"Oui":"Non"}</dd></div>
              <div><dt>Pièces contrôlées</dt><dd>{application.documents?"Oui":"Non"}</dd></div>
              <div><dt>Décision</dt><dd>{application.status}</dd></div></dl>
            <p className="demo-hint">Concours réussi ou orientation ne signifie pas inscription définitive. Les vérifications affichées ici sont fictives.</p>
            <div className="demo-actions">
              <DemoButton icon="checkcircle" onClick={()=>admissionAction("verify")} disabled={application.status==="Inscrit"}>Simuler la vérification</DemoButton>
              <DemoButton primary icon="check" onClick={()=>admissionAction("approve")} disabled={["Accepté","Inscrit","Refusé"].includes(application.status)}>Accepter</DemoButton>
              <DemoButton icon="users" onClick={()=>admissionAction("wait")}>Liste d'attente</DemoButton>
              <DemoButton icon="adduser" onClick={()=>admissionAction("enroll")} disabled={application.status==="Inscrit"}>Inscrire l'élève</DemoButton>
            </div>
          </>:<Empty>Choisir une candidature.</Empty>}
        </Card>
      </div></>;
  }
  function classes(advancedAction=null){
    return <><PageHeader title="Classes et effectifs" subtitle={school.type+" — "+year+" — divisions configurables"}
      actions={<div className="demo-actions">{advancedAction}
        <DemoButton icon="layers" primary onClick={()=>open("generation",{level:school.levels[0],count:2,capacity:35})}>Générer les classes</DemoButton>
        <DemoButton icon="plus" onClick={()=>open("classroom",{capacity:35})}>Créer une classe</DemoButton>
      </div>}/>
      <div className="demo-tiles">{currentClasses.map(cl=><div key={cl.id} className="demo-tile">
        <Icon name="layers" size={28}/><b>{cl.name}</b>
        <small>{currentStudents.filter(s=>s.level===cl.name).length} élève(s) / {cl.capacity} places</small>
        <div className="demo-actions">
          <button className="demo-table-action" type="button" onClick={()=>{setPage("students");setSearch(cl.name);}}>Voir élèves</button>
          <button className="demo-table-action" type="button" disabled={isClosed}
            onClick={()=>open("classroom",cl)}>Modifier</button>
          <button className="demo-table-action" type="button" disabled={isClosed}
            onClick={()=>{setState(old=>({...old,classes:old.classes.filter(x=>x.id!==cl.id)}));message("Classe retirée des données fictives.");}}>Supprimer</button>
        </div></div>)}{!currentClasses.length&&<Empty>Aucune classe pour {year}. Utilisez « Générer les classes ».</Empty>}</div>
    </>;
  }
  function arrears(advancedAction=null){
    const outstanding=currentInvoices.filter(f=>remaining(f)>0);
    const owed=outstanding.reduce((total,f)=>total+remaining(f),0);
    return <><PageHeader title="Impayés & relances" subtitle="Suivi des échéances, retards et soldes des familles" actions={advancedAction}/>
      <div className="demo-metrics"><Metric icon="users" label="Familles concernées" value={String(new Set(outstanding.map(f=>f.student)).size)}/>
        <Metric icon="coins" label="Total à recouvrer" value={fcfa(owed)}/></div>
      <Card title="Suivi des impayés" icon="alert"><div className="demo-table-wrap"><table>
        <thead><tr><th>Élève</th><th>Nature des frais</th><th>Solde</th><th>Action</th></tr></thead>
        <tbody>{outstanding.map(f=><tr key={f.id}>
          <td>{state.students.find(s=>s.id===f.student)?.name}</td><td>{f.label}</td><td>{fcfa(remaining(f))}</td>
          <td><button type="button" className="demo-table-action" onClick={()=>message("Relance préparée uniquement à l'écran : aucun WhatsApp, SMS ou e-mail envoyé.")}>
            Préparer une relance</button></td></tr>)}</tbody>
      </table>{!outstanding.length&&<Empty>Aucun impayé dans cette année scolaire.</Empty>}</div></Card>
      <p className="demo-hint">La démo illustre les relances. Aucune communication n'est envoyée à une famille.</p>
    </>;
  }
  function payments(onlyChild=false,advancedAction=null,tabs=null){
    const invoices=onlyChild?state.invoices.filter(f=>f.student===child?.id&&f.year===year):currentInvoices;
    return <><PageHeader title={onlyChild?"Frais & paiements":"Encaissements et caisse journalière"}
      subtitle={onlyChild?"Choisissez une facture pour simuler un règlement":"Suivi des paiements, reçus et méthodes d’encaissement"} actions={advancedAction}/>{tabs}
      <div className="demo-metrics"><Metric icon="file" label="Factures" value={String(invoices.length)}/>
        <Metric icon="coins" label="Restant dû" value={fcfa(invoices.reduce((s,f)=>s+remaining(f),0))}/>
        <Metric icon="checkcircle" label="Entièrement réglées" value={String(invoices.filter(f=>remaining(f)===0).length)}/></div>
      <Card title="Échéances et paiements" icon="card"><div className="demo-table-wrap"><table>
        <thead><tr><th>Élève</th><th>Frais</th><th>Montant</th><th>Restant</th><th>Statut</th><th>Action</th></tr></thead>
        <tbody>{invoices.map(inv=>{const stu=state.students.find(s=>s.id===inv.student),st=moneyStatus(inv);
          return <tr key={inv.id}><td>{stu?.name}</td><td>{inv.label}</td><td>{fcfa(inv.total)}</td>
            <td>{fcfa(remaining(inv))}</td><td><Status tone={st[0]}>{st[1]}</Status></td>
            <td><button type="button" className="demo-table-action" onClick={()=>showPayment(inv)}
              disabled={!remaining(inv)}> {remaining(inv)?"Simuler paiement":"Réglé"} </button></td></tr>;
        })}</tbody></table>{!invoices.length&&<Empty>Aucune facture disponible.</Empty>}</div></Card>
      <p className="demo-hint">L'intégration SingPay de l'application réelle n'est pas déclenchée. Tout paiement dans cette démonstration est une simulation locale.</p></>;
  }
  function reports(onlyChild=false,advancedAction=null,tabs=null,selectedTab=""){
    const students=onlyChild?(child?[child]:[]):currentStudents;
    const pupil=students.find(s=>s.id===selectedStudent)||students[0];
    const grade=state.grading[pupil?.school]||"20";
    const formattedAverage=()=>{
      if(!pupil||pupil.average===null)return "";
      if(grade==="letters")return pupil.average>=16?"A":pupil.average>=14?"B":pupil.average>=12?"C":"D";
      if(grade==="percent")return (pupil.average*5).toFixed(1)+" %";
      if(["10","15","100"].includes(grade))return (pupil.average*Number(grade)/20).toFixed(1)+" / "+grade;
      return pupil.average.toFixed(1)+" / 20";
    };
    const opts=students.filter(Boolean);
    return <><PageHeader title={onlyChild?"Notes et bulletins":"Évaluations et notes"}
      subtitle="Retrouvez les notes, bulletins et décisions à partir de la classe" actions={advancedAction}/>{tabs}
      <div className="demo-toolbar"><select aria-label="Élève pour les bulletins" value={pupil?.id||""}
        onChange={e=>setSelectedStudent(e.target.value)}>{opts.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <select aria-label="Période" value={resultTab} onChange={e=>setResultTab(e.target.value)}>
          <option value="notes">1er trimestre</option><option value="second">2e trimestre</option>
          <option value="third">3e trimestre</option></select></div>
      <Card title={"Aperçu de bulletin — "+(pupil?.name||"")} icon="file">
        {pupil?<><p><b>Classe :</b> {pupil.level} · <b>Établissement :</b> {schoolOf(state,pupil.school)?.name}</p>
          <div className="demo-report">
            {pupil.average===null||grade==="skills"?<><h3>Suivi par compétences</h3>
              <p>Communication : En cours d'acquisition</p><p>Motricité : Acquis</p>
              <p>Autonomie : En cours d'acquisition</p></>:
              <><h3>Résultat indicatif : {formattedAverage()}</h3>
                <div className="demo-line"><span>Français</span><b>15 / 20</b></div>
                <div className="demo-line"><span>Mathématiques</span><b>13 / 20</b></div>
                <div className="demo-line"><span>Histoire-Géographie</span><b>14 / 20</b></div></>}
          </div><div className="demo-actions"><DemoButton icon="printer" onClick={()=>{message("Aperçu de bulletin prêt à présenter, sans génération de document officiel.");}}>Prévisualiser le bulletin</DemoButton></div>
        </>:<Empty>Aucun élève dans cette sélection.</Empty>}
      </Card></>;
  }
  function absences(onlyChild=false,advancedAction=null){
    const pupils=onlyChild?[child]:currentStudents;
    return <><PageHeader title="Absences et retards" subtitle="Consultez les appels et les retards par classe" actions={advancedAction}/>
      <Card title="Présence par élève" icon="calendar">
        {pupils.filter(Boolean).map(s=>{const mark=state.marks[s.id]||"Présent";return <div key={s.id} className="demo-line demo-presence">
          <div><b>{s.name}</b><small>{s.level} · {s.absences} absence(s) enregistrée(s) dans le scénario</small></div>
          {onlyChild?<Status>{mark}</Status>:<div className="demo-segments">
            {["Présent","Absent","Retard"].map(v=><button key={v} type="button"
              aria-pressed={mark===v} className={mark===v?"active":""}
              disabled={isClosed} onClick={()=>setState(old=>({...old,marks:{...old.marks,[s.id]:v}}))}>{v}</button>)}
          </div>}</div>})}
        {!onlyChild&&<div className="demo-actions"><DemoButton primary icon="check" disabled={isClosed} onClick={()=>message("Appel enregistré dans la démonstration (aucune absence réelle créée).")}>Enregistrer l'appel</DemoButton></div>}
      </Card></>;
  }
  function staff(advancedAction=null){
    return <><PageHeader title="Personnel" subtitle="Retrouvez les collaborateurs et gérez leurs affectations"
      actions={<div className="demo-actions"><DemoButton primary icon="adduser" onClick={()=>open("staff")}>Ajouter un membre</DemoButton>{advancedAction}</div>}/>
      <Card title="Personnel de l'établissement" icon="users">{currentStaff.map(p=><div key={p.id} className="demo-line">
        <div className="demo-person-inline"><PersonAvatar name={p.name}/><div><b>{p.name}</b>
          <small>{(p.cycles||["Tous les cycles"]).join(", ")} · {p.hasAccount?"Compte simulé":"Sans compte"}</small>
        </div></div><Status>{(p.roles||[p.role]).join(" · ")}</Status></div>)}
        {!currentStaff.length&&<Empty>Aucun personnel fictif.</Empty>}
      </Card><p className="demo-hint">Dans YEM réel, les droits dépendent de l'établissement et des fonctions attribuées.</p></>;
  }
  function organization(){
    const roles=SCHOOL_ROLES[school.type]||SCHOOL_ROLES["Collège / Lycée"];
    return <><PageHeader title="Organigramme & rôles" subtitle="Fonctions adaptées au type d'établissement et permissions par cycle"/>
      <div className="demo-grid-two">
        <Card title="Fonctions disponibles" icon="users">
          {roles.map(name=><div key={name} className="demo-line"><b>{name}</b><small>{currentStaff.filter(p=>(p.roles||[p.role]).includes(name)).length} affectation(s)</small></div>)}
        </Card>
        <Card title="Affectations du personnel" icon="idcard">
          {currentStaff.map(p=><div className="demo-line" key={p.id}><b>{p.name}</b>
            <span>{(p.roles||[p.role]).join(" · ")}</span><small>{(p.cycles||["Tous les cycles"]).join(", ")}</small></div>)}
          <div className="demo-actions"><DemoButton icon="adduser" primary onClick={()=>{setPage("staff");open("staff");}}>Affecter un membre</DemoButton></div>
          <p className="demo-hint">Un compte est facultatif. Les fonctions et les droits sont distincts.</p>
        </Card>
      </div></>;
  }
  function generateSubjects(){
    if(isClosed){message("L'année clôturée ne peut pas être modifiée.");return;}
    const names=school.type==="Maternelle"?["Langage","Motricité","Éveil"]:
      school.type==="Primaire"?["Français","Mathématiques","Éveil","EPS"]:
      ["Français","Mathématiques","Anglais","Histoire-Géographie","SVT","Physique-Chimie"];
    setState(old=>{
      const subjects=[...old.subjects];
      for(const level of school.levels)for(const name of names){
        if(subjects.some(s=>s.school===school.id&&s.year===year&&s.level===level&&s.name===name))continue;
        subjects.push({id:fakeId("m",subjects),school:school.id,year,name,level,coefficient:1});
      }
      return {...old,subjects};
    });
    message("Matières générées pour les niveaux de "+school.name+" (sans doublons).");
  }
  function curriculum(){
    const items=state.subjects.filter(x=>x.school===school.id&&x.year===year);
    return <><PageHeader title="Matières et programmes" subtitle="Référentiel configurable par établissement, cycle et niveau"/>
      <div className="demo-actions"><DemoButton icon="layers" primary onClick={generateSubjects}>Générer les matières par niveau</DemoButton>
        <DemoButton icon="plus" onClick={()=>open("subject",{coefficient:"2"})}>Ajouter une matière</DemoButton></div>
      <Card title="Matières de l'année" icon="file"><div className="demo-table-wrap"><table>
        <thead><tr><th>Niveau</th><th>Matière</th><th>Coefficient</th><th>Action</th></tr></thead>
        <tbody>{items.map(item=><tr key={item.id}><td>{item.level}</td><td><b>{item.name}</b></td><td>{item.coefficient}</td>
          <td><button type="button" className="demo-table-action" disabled={isClosed}
            onClick={()=>setState(old=>({...old,subjects:old.subjects.filter(s=>s.id!==item.id)}))}>Retirer</button></td></tr>)}</tbody>
      </table>{!items.length&&<Empty>Aucune matière. Cliquez sur « Générer les matières par niveau ».</Empty>}</div></Card>
    </>;
  }
  function timetable(){
    const items=state.timetable.filter(t=>t.school===school.id&&t.year===year);
    return <><PageHeader title="Emplois du temps" subtitle="Planification des classes, enseignants et salles avec détection des conflits"/>
      <div className="demo-actions"><DemoButton icon="plus" primary onClick={()=>open("timetable")}>Planifier un cours</DemoButton></div>
      <Card title="Planning de la semaine" icon="calendar"><div className="demo-table-wrap"><table>
        <thead><tr><th>Jour</th><th>Horaire</th><th>Classe</th><th>Matière</th><th>Enseignant</th><th>Salle</th></tr></thead>
        <tbody>{items.map(t=><tr key={t.id}><td>{t.day}</td><td>{t.slot}</td><td>{t.className}</td>
          <td>{t.subject}</td><td>{t.teacher}</td><td>{t.room}</td></tr>)}</tbody>
      </table>{!items.length&&<Empty>Planning vide. Générer d'abord des classes, puis planifier un cours.</Empty>}</div></Card>
      <p className="demo-hint">Les conflits de classe, de salle et d'enseignant sur un même créneau sont bloqués dans cette simulation.</p>
    </>;
  }
  function years(){
    return <><PageHeader title="Années scolaires" subtitle="Consultation des bilans passés et préparation de la nouvelle rentrée"/>
      <div className="demo-tiles">{DEMO_YEARS.map(y=><button type="button" key={y}
        onClick={()=>{setYear(y);setSearch("");setNotice(y==="2025-2026"?"Année clôturée : lecture seule.":"Année "+y+" chargée en démonstration.");}}
        className={"demo-tile "+(y===year?"demo-tile-selected":"")}>
        <Icon name="calendar" size={28}/><b>{y}</b>
        <span>{y==="2025-2026"?"Clôturée — archive":y===DEMO_CURRENT_YEAR?"Année en cours":"Prochaine année — configurable"}</span>
        <small>{state.students.filter(s=>s.school===school.id&&s.year===y).length} élève(s) · {state.classes.filter(s=>s.school===school.id&&s.year===y).length} classe(s)</small>
        <span>Consulter l'année →</span></button>)}</div>
      <p className="demo-hint">Chaque année conserve des données distinctes. Dans la démonstration, les modifications restent uniquement en mémoire pendant la visite.</p>
    </>;
  }
  function settings(){
    const routes=availableRoutes(state,school.id);
    const grade=state.grading[school.id]||"20";
    const numbering=state.numbering[school.id]||{prefix:"YEM",padding:5,next:1};
    return <><PageHeader title="Paramètres de l'établissement" subtitle="Cycles, barèmes, matricules et admissions personnalisables"/>
      <div className="demo-grid-two"><Card title="Identité de l'établissement" icon="school"><dl className="demo-dl">
        <div><dt>Nom</dt><dd>{school.name}</dd></div><div><dt>Type</dt><dd>{school.type}</dd></div>
        <div><dt>Ville</dt><dd>{school.city}</dd></div><div><dt>Année scolaire</dt><dd>{year} (exemple)</dd></div></dl>
        <DemoButton icon="school" onClick={()=>enter("platform")}>Voir la console plateforme</DemoButton>
      </Card><Card title="Voies d'admission autorisées" icon="settings">
        {Object.entries(ROUTE_LABELS).map(([code,label])=><label key={code} className="demo-check">
          <input type="checkbox" disabled={isClosed} checked={routes.includes(code)} onChange={e=>{
            const value=e.target.checked;
            if(!value&&routes.length===1){message("Au moins une voie doit rester autorisée.");return;}
            setState(old=>({...old,routes:{...old.routes,
              [school.id]:value?[...routes,code]:routes.filter(x=>x!==code)}}));
          }}/> {label}</label>)}
        <div className="demo-actions"><DemoButton primary icon="check" onClick={()=>message("Paramètres enregistrés uniquement dans la démonstration.")}>Enregistrer la configuration</DemoButton></div>
      </Card></div>
      <div className="demo-grid-two">
        <Card title="Évaluations et bulletins" icon="file">
          <F label="Barème de référence"><select aria-label="Barème de notation" value={grade} disabled={isClosed}
            onChange={e=>setState(old=>({...old,grading:{...old.grading,[school.id]:e.target.value}}))}>
            {[["20","Notes sur 20"],["10","Notes sur 10"],["15","Notes sur 15"],["100","Notes sur 100"],
              ["percent","Pourcentage"],["letters","Lettres (A+ à E)"],["skills","Compétences"]].map(([v,l])=>
              <option key={v} value={v}>{l}</option>)}</select></F>
          <p className="demo-hint">Pondérations, moyennes et appréciations sont paramétrables dans YEM réel par établissement et par cycle.</p>
          <DemoButton icon="file" onClick={()=>setPage("bulletins")}>Consulter un bulletin</DemoButton>
        </Card>
        <Card title="Matricules des élèves" icon="idcard">
          <F label="Préfixe"><input aria-label="Préfixe du matricule" maxLength={12} disabled={isClosed}
            value={numbering.prefix} onChange={e=>setState(old=>({...old,numbering:{...old.numbering,
              [school.id]:{...numbering,prefix:e.target.value}}}))}/></F>
          <F label="Longueur du numéro"><input aria-label="Longueur du matricule" type="number" min={3} max={10} disabled={isClosed}
            value={numbering.padding} onChange={e=>setState(old=>({...old,numbering:{...old.numbering,
              [school.id]:{...numbering,padding:Number(e.target.value)}}}))}/></F>
          <p><b>Aperçu fictif :</b> {numbering.prefix}-{String(numbering.next).padStart(Math.min(10,Math.max(3,numbering.padding)), "0")}</p>
          <p className="demo-hint">Un matricule est attribué par le système, et non saisi librement.</p>
        </Card>
      </div></>;
  }
  function platform(){
    return <><PageHeader title="Console de la plateforme YEM" subtitle="Vue multi-établissements et administration — scénario fictif"/>
      <div className="demo-metrics"><Metric icon="school" label="Établissements" value={String(state.schools.length)}/>
        <Metric icon="users" label="Élèves" value={String(state.students.filter(x=>x.year===year).length)}/>
        <Metric icon="layers" label="Classes" value={String(state.classes.filter(x=>x.year===year).length)}/>
        <Metric icon="adduser" label="Demandes d'admission" value={String(state.applications.filter(x=>x.year===year).length)}/></div>
      <Card title="Répertoire des établissements" icon="school">
        {state.schools.map(s=><div key={s.id} className="demo-line"><div>
          <b>{s.name}</b><small>{s.city} · {s.type}</small></div>
          <DemoButton onClick={()=>{pickSchool(s.id);enter("school");}} icon="chevronright">Explorer l'établissement</DemoButton></div>)}
        <div className="demo-actions"><DemoButton primary icon="plus" onClick={()=>open("school",{type:"Primaire"})}>Ajouter un établissement fictif</DemoButton></div>
      </Card></>;
  }
  function schools(){
    return <><PageHeader title="Établissements" subtitle="Gestion multi-établissements — informations fictives"/>
      <div className="demo-actions"><DemoButton primary icon="plus" onClick={()=>open("school",{type:"Primaire"})}>Créer un établissement fictif</DemoButton></div>
      <Card title="Répertoire des écoles" icon="school">
        {state.schools.map(s=><div key={s.id} className="demo-line"><div><b>{s.name}</b>
          <small>{s.city} · {s.type} · Propriétaire : {s.owner||"À désigner"}</small></div>
          <DemoButton icon="chevronright" onClick={()=>{pickSchool(s.id);enter("school");}}>Ouvrir la démo direction</DemoButton>
        </div>)}</Card></>;
  }
  function accounts(){
    return <><PageHeader title="Utilisateurs & rôles" subtitle="Comptes et fonctions par établissement — illustration seulement"/>
      <div className="demo-toolbar"><select value={schoolId} aria-label="Choisir l'établissement pour les comptes" onChange={e=>pickSchool(e.target.value)}>
        {state.schools.map(s=><option value={s.id} key={s.id}>{s.name}</option>)}</select></div>
      <Card title="Rôles et utilisateurs fictifs" icon="shield">{currentStaff.map(p=><div className="demo-line" key={p.id}>
        <b>{p.name}</b><span>{p.role}</span><Status>Actif (démo)</Status></div>)}
        <div className="demo-actions"><DemoButton primary icon="adduser" onClick={()=>{enter("school");setPage("staff");open("staff");}}>Gérer le personnel de démonstration</DemoButton></div>
      </Card></>;
  }
  function parents(){
    return <><PageHeader title="Mes enfants" subtitle="Un seul espace parent pour plusieurs établissements — données fictives"/>
      {!parentChildren.length&&<p className="demo-hint">Aucun enfant rattaché à cet exemple pour l'année {year}.</p>}
      <div className="demo-tiles">{parentChildren.map(s=><button type="button" key={s.id} onClick={()=>setSelectedChild(s.id)}
        className={"demo-tile "+(s.id===child?.id?"demo-tile-selected":"")}>
        <PersonAvatar name={s.name}/><b>{s.name}</b><span>{schoolOf(state,s.school)?.name}</span><small>{s.level}</small></button>)}</div>
      <div className="demo-metrics">
        <Metric icon="file" label="Moyenne / Compétences" value={child?.average===null?"Compétences":(child?.average||0)+"/20"}/>
        <Metric icon="calendar" label="Absences" value={String(child?.absences||0)}/>
        <Metric icon="coins" label="À régler" value={fcfa(parentsDue.reduce((n,f)=>n+remaining(f),0))}/></div>
      <div className="demo-quick demo-parent-quick">
        <DemoButton icon="card" primary disabled={!child||isClosed} onClick={()=>setPage("parent-payments")}>Payer les frais (simulation)</DemoButton>
        <DemoButton icon="file" disabled={!child} onClick={()=>setPage("parent-results")}>Voir les bulletins</DemoButton>
        <DemoButton icon="calendar" disabled={!child} onClick={()=>setPage("parent-absences")}>Voir les absences</DemoButton>
        <DemoButton icon="school" onClick={()=>setPage("parent-admissions")}>Préinscrire un enfant</DemoButton>
      </div></>;
  }
  function parentAdmissions(){
    const mine=state.applications.filter(a=>a.parentDemo&&a.year===year);
    return <><PageHeader title="Préinscriptions" subtitle="Choisir une école, un niveau et une voie d'admission"/>
      <div className="demo-tiles">{state.schools.map(s=><button key={s.id} className="demo-tile" type="button"
        onClick={()=>open("admission",{school:s.id,route:"direct",level:s.levels[0],parentDemo:true})}>
        <Icon name="school" size={28}/><b>{s.name}</b><span>{s.city} · {s.type}</span><small>Demander une préinscription →</small>
      </button>)}</div>
      <Card title="Mes demandes fictives" icon="file">{mine.length?mine.map(a=><div className="demo-line" key={a.id}>
        <b>{a.name}</b><span>{schoolOf(state,a.school)?.name}</span><Status>{a.status}</Status></div>):
        <Empty>Aucune demande. Choisis une école pour simuler une préinscription.</Empty>}</Card></>;
  }
  function parentsDirectory(){
    const links=currentStudents.map(s=>({student:s,guardian:s.guardian})).filter(x=>x.guardian);
    return <><PageHeader title="Parents" subtitle="Les responsables légaux de chaque élève, par classe" actions={advanced("parents")}/>
      <div className="yd-real-body">
        <Card title="Parents par classe" icon="users"><div className="demo-table-wrap"><table className="clickable nowrap dense">
          <thead><tr><th>Responsable légal</th><th>Élève</th><th>Classe</th><th>Contact</th></tr></thead>
          <tbody>{links.map(({student:s,guardian})=><tr key={s.id}><td>{guardian}</td><td>{s.name}</td>
            <td>{s.level}</td><td>{s.phone||"À compléter"}</td></tr>)}</tbody>
        </table>{!links.length&&<Empty>Aucun responsable pour l'année sélectionnée.</Empty>}</div></Card>
      </div></>;
  }
  function settingPanel(id){
    const title=DEMO_SETTING_SECTIONS.flatMap(x=>x.items).find(x=>x.id===id)?.label||"Configuration";
    const screen={
      classes:classes,numbering:settings,curriculum:curriculum,"report-policy":settings,
      "council-policy":()=>reports(),"amendments":()=>reports(),
      timetable:timetable,academic:years,"admission-policy":settings,
      fees:settings,gateway:settings,"attendance-policy":()=>absences(),
      "parent-access":parentsDirectory,organization:organization,
      "staff-setup":staff,roles:organization,users:accounts,
      "cycle-access":organization,form:students,
    }[id];
    if(screen)return <div className="demo-settings-panel">{screen()}</div>;
    return <Card title={title} icon="settings"><p className="demo-hint">Aperçu de cette rubrique — données fictives.</p>
      <DemoButton onClick={()=>message("Aucune configuration réelle enregistrée.")} icon="check">Enregistrer la simulation</DemoButton>
    </Card>;
  }
  function schoolPageContent(){
    if(page==="settings")return <SchoolSettings sections={DEMO_SETTING_SECTIONS}
      selection={settingsSelection} onSelect={setSettingsSelection}
      render={settingPanel} isOwner={true}
      onReturn={settingsReturn?()=>{setPage(settingsReturn.page);setSub(settingsReturn.sub);setSettingsReturn(null);}:undefined}/>;
    if(page==="dashboard")return dashboard();
    const selectedTab=sub||DEMO_TABS[page]?.[0]?.[0]||"";
    const tabs=demoTabs(page);
    const advancedAction=advanced(page);
    if(page==="students")return <div className="demo-live-screen">
      <div className="yd-view-filters"><label>Année scolaire <select value={year} aria-label="Année de travail de l'établissement"
        onChange={e=>setYear(e.target.value)}>{DEMO_YEARS.map(y=><option key={y}>{y}</option>)}</select></label>
        <label>Devise de consultation <select aria-label="Devise de consultation" defaultValue="XAF"><option value="XAF">XAF</option></select></label></div>
      {selectedTab==="byclass"?<><PageHeader title="Inscriptions par classe" subtitle="Inscriptions, classes, responsables et suivi administratif" actions={advancedAction}/>{tabs}
        <div className="yd-real-body">{classes()}</div></>:
        <>{students(advancedAction,tabs)}</>}
    </div>;
    if(page==="classes")return <>{classes(advancedAction)}</>;
    if(page==="admissions")return <>{admissions(advancedAction)}</>;
    if(page==="payments")return <>{payments(false,advancedAction,tabs)}</>;
    if(page==="arrears")return <>{arrears(advancedAction)}</>;
    if(page==="bulletins")return <>{reports(false,advancedAction,tabs,selectedTab)}</>;
    if(page==="absences")return <>{absences(false,advancedAction)}</>;
    if(page==="parents")return parentsDirectory();
    if(page==="staff")return selectedTab==="onboarding"?
      <><PageHeader title="Personnel" subtitle="Retrouvez les collaborateurs et gérez leurs affectations" actions={advancedAction}/>
        <div className="yd-real-body"><Card title="Ajouter un collaborateur" icon="adduser"><div className="demo-actions">
          <DemoButton primary icon="adduser" onClick={()=>open("staff")}>Ajouter un membre du personnel</DemoButton>
          <DemoButton icon="users" onClick={()=>setSub("directory")}>Retour à l'équipe</DemoButton></div></Card></div></>:
      staff(advancedAction);
    return dashboard();
  }
  const pageContent=()=>{
    if(role==="platform")return page==="accounts"?accounts():page==="schools"?schools():platform();
    if(role==="parent")return page==="parent-payments"?payments(true):
      page==="parent-results"?reports(true):
      page==="parent-absences"?absences(true):
      page==="parent-admissions"?parentAdmissions():parents();
    return schoolPageContent();
  };
  return <div className="demo-app" data-demo="true">
    <div className="demo-ribbon" role="status">
      <strong><Icon name="shield" size={17}/> MODE DÉMONSTRATION</strong>
      <span>Tout est fictif. Aucune donnée réelle, aucun paiement, aucun e-mail.</span>
      <button type="button" onClick={()=>{setState(createDemoState());setNotice("Scénario réinitialisé.");setModal(null);
        setSchoolId("lycee");setSelectedStudent("s1");setSelectedAdmission("a1");
        setSelectedChild("s1");setSearch("");setSub("");setSettingsSelection(null);setYear(DEMO_CURRENT_YEAR);setPage(defaultPage[role]);}}>
        <Icon name="back" size={17}/> Réinitialiser
      </button>
      <a href="#/" aria-label="Revenir à l'application réelle">Retour à YEM réel <Icon name="chevronright" size={16}/></a>
    </div>

    <div className="demo-main">
      <Shell className="demo-shell" userName={title} nav={nav} active={page} onNavigate={p=>navigate(p)}
        schoolSelector={<div className="yd-school-select-wrap demo-real-selector">
          <label className="yd-school-select"><Icon name="school" size={24}/>
            {role==="school"?<select aria-label="Établissement de démonstration" value={schoolId}
              onChange={e=>pickSchool(e.target.value)}>
              {state.schools.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>:
              <b>{role==="platform"?"Console plateforme":"Espace parent"}</b>}
            <Icon name="chevron" size={18} className="chev"/>
          </label>
          <label className="yd-school-select" title="Année scolaire de consultation">
            <Icon name="calendar" size={18}/>
            <select aria-label="Année scolaire de démonstration" value={year}
              onChange={e=>{setYear(e.target.value);setSearch("");
                setNotice(e.target.value==="2025-2026"?"Année clôturée — lecture seule.":"Année "+e.target.value+" chargée.");}}>
              {DEMO_YEARS.map(y=><option key={y} value={y}>{y} · {y==="2025-2026"?"clôturée":y===DEMO_CURRENT_YEAR?"en cours":"en préparation"}</option>)}
            </select>
          </label>
        </div>}
        userMenu={<div className="demo-user-controls">
          <label className="demo-role-select"><span className="sr-only">Profil de démonstration</span>
            <select aria-label="Profil de démonstration" value={role} onChange={e=>enter(e.target.value)}>
              <option value="school">Direction / établissement</option>
              <option value="platform">Super-administrateur</option>
              <option value="parent">Parent d'élève</option>
            </select>
          </label>
          <div className="yd-user"><span className="yd-avatar"><Icon name="user" size={22}/></span>
            <span><b>{role==="school"?school.head:"Visiteur YEM"}</b>
              <small>{role==="school"?"Direction (simulation)":role==="platform"?"Administration plateforme":"Compte parent (simulation)"}</small>
            </span><Icon name="chevron" size={18}/></div>
        </div>}
        notifications={0}>
        {notice&&<div className="demo-notice" role="status"><Icon name="info" size={19}/>{notice}
          <button aria-label="Fermer le message" type="button" onClick={()=>setNotice("")}><Icon name="close" size={17}/></button></div>}
        {pageContent()}
        <footer className="yd-brand-footer"><span>YEM — Gestion scolaire &amp; universitaire · Données fictives</span><span>Développé par <strong>BWETEK Informatyk</strong></span></footer>
      </Shell>
    </div>
    {modal&&<DemoModal mode={modal} form={form} setForm={setForm} school={school}
      schools={state.schools} student={state.students.find(s=>s.id===activeInvoice?.student)}
      invoice={activeInvoice} onClose={()=>setModal(null)} onSubmit={submit}/>}
  </div>;
}
