import React,{useEffect,useState} from "react";
import {YemLogo,Icon,Button,Card} from "./yem-ui.jsx";
import TeacherMobileGrades from "./TeacherMobileGrades.jsx";
import TeacherMobileAttendance from "./TeacherMobileAttendance.jsx";
import TeacherProfile from "./TeacherProfile.jsx";
import PWAInstall from "./PWAInstall.jsx";
import {teacherRequest} from "./teacher-mobile-api.js";
import "./teacher-mobile.css";

const tabs=[
  {id:"accueil",label:"Accueil",icon:"home"},
  {id:"notes",label:"Notes",icon:"file"},
  {id:"moyennes",label:"Moyennes",icon:"barchart"},
  {id:"appel",label:"Appel",icon:"users"},
  {id:"profil",label:"Profil",icon:"user"},
];

export default function TeacherMobileWorkspace({
  schoolId,schoolName,user,permissions=[],workingYearId="",years=[],
  schools=[],onSchoolChange,onYearChange,onLogout,onExit,accountView,
}){
  const [tab,setTab]=useState("accueil");
  const [data,setData]=useState({courses:[],classes:[],subjects:[],periods:[],assignments:[]});
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [portrait,setPortrait]=useState(null);
  const [photoRev,setPhotoRev]=useState(0);
  const hasCurriculum=permissions.includes("school.curriculum.read")&&permissions.includes("school.academic.read");
  const hasAcademic=permissions.includes("school.academic.read");
  useEffect(()=>{setTab("accueil");},[schoolId]);
  useEffect(()=>{
    let active=true;setLoading(true);setError("");
    const root="schools/"+schoolId+"/";
    const jobs={
      courses:hasCurriculum?teacherRequest(root+"curriculum/my-courses"):Promise.resolve({courses:[]}),
      classes:hasAcademic?teacherRequest(root+"academic/classes"):Promise.resolve({classes:[]}),
      subjects:hasCurriculum?teacherRequest(root+"subjects"):Promise.resolve({subjects:[]}),
      periods:hasCurriculum?teacherRequest(root+"academic/periods"):Promise.resolve({periods:[]}),
      assignments:teacherRequest(root+"staff/me/assignments"),
    };
    Promise.all(Object.entries(jobs).map(async ([key,job])=>{
      try{return [key,await job,null];}catch(err){return [key,{},err.message];}
    })).then(results=>{
      if(!active)return;
      const fresh={courses:[],classes:[],subjects:[],periods:[],assignments:[]};
      const errors=[];
      results.forEach(([key,result,problem])=>{
        fresh[key]=result[key]||[];
        if(problem)errors.push(problem);
      });
      setData(fresh);setLoading(false);setError([...new Set(errors)].join(" · "));
    });
    return()=>{active=false};
  },[schoolId,hasCurriculum,hasAcademic]);
  useEffect(()=>{
    let active=true;
    const root="schools/"+schoolId+"/staff/me/profile";
    const load=()=>teacherRequest(root).then(v=>{
      if(active)setPortrait(v.photo_url);
    }).catch(()=>{if(active)setPortrait(null);});
    load();
    const refresh=event=>{
      if(event.detail?.schoolId===schoolId){setPhotoRev(n=>n+1);load();}
    };
    window.addEventListener("yem:staff-photo-updated",refresh);
    return()=>{active=false;window.removeEventListener("yem:staff-photo-updated",refresh);};
  },[schoolId]);
  const activeCourses=data.courses.filter(c=>c.active&&(!workingYearId||c.year===workingYearId));
  const activeAssignments=data.assignments.filter(a=>a.active&&(!workingYearId||a.year===workingYearId));
  const myClasses=new Set([...activeCourses.map(c=>c.classroom),...activeAssignments.map(a=>a.classroom)]);
  const givenName=user?.first_name||user?.username||"Professeur";
  const open=id=>{setTab(id);window.scrollTo?.(0,0);};
  return <div className="ym-prof-app">
    <header className="ym-prof-header">
      <div className="ym-prof-header-top">
        <YemLogo compact/>
        <button className="ym-prof-portrait" type="button" aria-label="Modifier mon profil" onClick={()=>open("profil")}>
          {portrait?<img src={portrait+"?v="+photoRev} alt="Ma photo"/>:<Icon name="user" size={24}/>}
        </button>
      </div>
      <div className="ym-prof-school">
        <span>ESPACE PROFESSEUR</span>
        {schools.length>1?<select aria-label="Établissement" value={schoolId} onChange={e=>onSchoolChange?.(e.target.value)}>
          {schools.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
        </select>:<strong>{schoolName}</strong>}
      </div>
      {years.length>0&&<label className="ym-prof-year">
        Année scolaire
        <select aria-label="Année scolaire" value={workingYearId}
          onChange={e=>onYearChange?.(e.target.value)}>
          <option value="">Toutes les années</option>
          {years.map(y=><option value={y.id} key={y.id}>{y.name} {y.status==="closed"?"(archivée)":""}</option>)}
        </select>
      </label>}
    </header>
    <main className="ym-prof-body" id="ym-prof-main">
      {tab==="accueil"&&<div className="ym-page">
        <h1>Tableau de bord</h1>
        <p className="ym-prof-greeting">Bonjour, {givenName}.</p>
        <Card title="YEM sur votre téléphone" icon="mobile"
          subtitle="Installez votre espace professeur comme une application, avec les mêmes données que le site de l'établissement.">
          <PWAInstall buttonClassName="yd-btn primary" label="Ajouter YEM à mon téléphone"/>
          <p className="ym-hint">Une connexion est requise pour consulter ou enregistrer les notes et les présences.</p>
        </Card>
        <div className="ym-overview">
          <div><Icon name="cap"/><strong>{activeCourses.length}</strong><span>Matières attribuées</span></div>
          <div><Icon name="users"/><strong>{myClasses.size}</strong><span>Classes affectées</span></div>
        </div>
        <Card title="Mes actions" icon="list">
          <div className="ym-shortcuts">
            <Button icon="file" onClick={()=>open("notes")}>Saisir les notes</Button>
            <Button icon="barchart" onClick={()=>open("moyennes")}>Consulter les moyennes</Button>
            <Button icon="users" onClick={()=>open("appel")}>Faire l'appel</Button>
            <Button icon="user" onClick={()=>open("profil")}>Mon profil</Button>
          </div>
        </Card>
      </div>}
      {loading&&tab!=="profil"&&<p role="status" className="ym-hint">Chargement de vos affectations…</p>}
      {error&&tab!=="profil"&&<p role="alert" className="ym-alert">Certaines données sont indisponibles : {error}</p>}
      {!loading&&(tab==="notes"||tab==="moyennes")&&<TeacherMobileGrades
        key={schoolId+":"+workingYearId+":"+tab} schoolId={schoolId}
        courses={data.courses} classes={data.classes} subjects={data.subjects}
        periods={data.periods} yearId={workingYearId} mode={tab}/>}
      {!loading&&tab==="appel"&&<TeacherMobileAttendance
        key={schoolId+":"+workingYearId} schoolId={schoolId} classes={data.classes}
        assignments={data.assignments} workingYearId={workingYearId}/>}
      {tab==="profil"&&<div className="ym-page">
        <h1>Mon profil</h1>
        <TeacherProfile schoolId={schoolId}/>
        {accountView&&<Card title="Sécurité du compte" icon="shield"
          subtitle="Mot de passe, authentification et sécurité de votre accès YEM.">
          <details className="ym-details"><summary>Ouvrir les paramètres de sécurité</summary>
            <div className="ym-account-security">{accountView}</div>
          </details>
        </Card>}
        {onExit&&<Button icon="layers" onClick={onExit}>Retour à l'espace établissement</Button>}
        {onLogout&&<Button icon="logout" onClick={onLogout}>Se déconnecter</Button>}
      </div>}
      <footer className="ym-prof-footer">YEM · Développé par BWETEK Informatyk</footer>
    </main>
    <nav className="ym-prof-nav" aria-label="Navigation de l'espace professeur">
      {tabs.map(item=><button type="button" key={item.id} aria-current={tab===item.id?"page":undefined}
        className={tab===item.id?"active":""} onClick={()=>open(item.id)}>
        <Icon name={item.icon} size={21}/><span>{item.label}</span>
      </button>)}
    </nav>
  </div>;
}
