import React,{useEffect,useMemo,useState} from "react";
import {YemLogo,Icon,Button,Card} from "./yem-ui.jsx";
import TeacherMobileGrades from "./TeacherMobileGrades.jsx";
import TeacherMobileAttendance from "./TeacherMobileAttendance.jsx";
import TeacherProfile from "./TeacherProfile.jsx";
import PWAInstall from "./PWAInstall.jsx";
import {teacherRequest} from "./teacher-mobile-api.js";
import "./teacher-mobile.css";

const tabs=[
  {id:"accueil",label:"Accueil",icon:"home"},
  {id:"classes",label:"Classes",icon:"users"},
  {id:"notes",label:"Notes",icon:"file"},
  {id:"moyennes",label:"Moyennes",icon:"barchart"},
  {id:"appel",label:"Appel",icon:"check"},
  {id:"profil",label:"Profil",icon:"user"},
];
const week=["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"];
const localDate=()=>{const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-")};
const weekDay=()=>((new Date().getDay()+6)%7);
const displayClass=(classes,id)=>classes.find(c=>c.id===id)?.name||"Classe";

export default function TeacherMobileWorkspace({
  schoolId,schoolName,user,permissions=[],workingYearId="",years=[],
  schools=[],onSchoolChange,onYearChange,onLogout,onExit,accountView,
}){
  const [tab,setTab]=useState("accueil");
  const [data,setData]=useState({courses:[],classes:[],subjects:[],periods:[],assignments:[],entries:[]});
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [portrait,setPortrait]=useState(null);
  const [photoRev,setPhotoRev]=useState(0);
  const [todayCalls,setTodayCalls]=useState(null);
  const hasCurriculum=permissions.includes("school.curriculum.read")&&permissions.includes("school.academic.read");
  const hasAcademic=permissions.includes("school.academic.read");
  const hasTimetable=permissions.includes("school.timetable.read");
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
      entries:hasTimetable?teacherRequest(root+"timetable/entries"):Promise.resolve({entries:[]}),
    };
    Promise.all(Object.entries(jobs).map(async ([key,promise])=>{
      try{return [key,await promise,null];}catch(e){return [key,{},e.message];}
    })).then(results=>{
      if(!active)return;
      const next={courses:[],classes:[],subjects:[],periods:[],assignments:[],entries:[]};
      const issues=[];
      for(const [key,result,err] of results){next[key]=result[key]||[];if(err)issues.push(err);}
      setData(next);setLoading(false);setError([...new Set(issues)].join(" · "));
    });
    return()=>{active=false};
  },[schoolId,hasCurriculum,hasAcademic,hasTimetable]);
  useEffect(()=>{
    let active=true;
    const load=()=>teacherRequest("schools/"+schoolId+"/staff/me/profile")
      .then(v=>{if(active)setPortrait(v.photo_url);})
      .catch(()=>{if(active)setPortrait(null);});
    load();
    const update=e=>{if(e.detail?.schoolId===schoolId){setPhotoRev(n=>n+1);load();}};
    window.addEventListener("yem:staff-photo-updated",update);
    return()=>{active=false;window.removeEventListener("yem:staff-photo-updated",update);};
  },[schoolId]);
  const activeCourses=useMemo(()=>data.courses.filter(c=>c.active&&(!workingYearId||c.year===workingYearId)),[data.courses,workingYearId]);
  const activeAssignments=useMemo(()=>data.assignments.filter(a=>a.active&&(!workingYearId||a.year===workingYearId)),[data.assignments,workingYearId]);
  const classIds=[...new Set([...activeCourses.map(c=>c.classroom),...activeAssignments.map(a=>a.classroom)])];
  const activeEntries=data.entries.filter(e=>e.active&&(!workingYearId||e.year===workingYearId));
  const today=localDate();
  const todayEntries=activeEntries.filter(e=>e.weekday===weekDay()&&e.effective_from<=today&&e.effective_to>=today)
    .sort((a,b)=>a.start_time.localeCompare(b.start_time));
  useEffect(()=>{
    let active=true;setTodayCalls(null);
    if(!classIds.length||loading)return;
    Promise.all(classIds.map(id=>teacherRequest("schools/"+schoolId+"/attendance/sessions?classroom="+encodeURIComponent(id))
      .then(v=>(v.sessions||[]).filter(s=>s.date===localDate()).length).catch(()=>null))).then(counts=>{
      if(active)setTodayCalls(counts.some(x=>x===null)?null:counts.reduce((a,b)=>a+b,0));
    });
    return()=>{active=false};
  },[schoolId,workingYearId,loading,activeCourses,activeAssignments]);
  const givenName=user?.first_name||user?.username||"Professeur";
  const open=id=>{setTab(id);window.scrollTo?.(0,0);};
  const title={accueil:"Bonjour, "+givenName,classes:"Mes classes",notes:"Notes",moyennes:"Moyennes",
    appel:"Appel des élèves",profil:"Mon profil",emploi:"Mon emploi du temps"}[tab];
  const subjectName=course=>data.subjects.find(s=>s.id===course.subject)?.name||"Matière";
  return <div className="ym-prof-app">
    <header className="ym-prof-header">
      <div className="ym-prof-header-top">
        <YemLogo compact/>
        <span className="ym-prof-header-role">Espace professeur</span>
        <button className="ym-prof-portrait" type="button" aria-label="Modifier mon profil" onClick={()=>open("profil")}>
          {portrait?<img src={portrait+"?v="+photoRev} alt="Ma photo"/>:<Icon name="user" size={24}/>}
        </button>
      </div>
      <h2 className="ym-prof-hero-title">{title}</h2>
      <div className="ym-prof-school">
        <span><Icon name="school" size={15}/> </span>
        {schools.length>1?<select aria-label="Établissement" value={schoolId} onChange={e=>onSchoolChange?.(e.target.value)}>
          {schools.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
        </select>:<strong>{schoolName}</strong>}
      </div>
      {years.length>0&&<label className="ym-prof-year">
        Année scolaire
        <select aria-label="Année scolaire" value={workingYearId} onChange={e=>onYearChange?.(e.target.value)}>
          <option value="">Toutes les années</option>
          {years.map(y=><option value={y.id} key={y.id}>{y.name} {y.status==="closed"?"(archivée)":""}</option>)}
        </select>
      </label>}
    </header>
    <main className="ym-prof-body" id="ym-prof-main">
      {loading&&tab!=="profil"&&<p role="status" className="ym-hint">Chargement de vos cours et de vos affectations…</p>}
      {error&&tab!=="profil"&&<p role="alert" className="ym-alert">Certaines données sont indisponibles : {error}</p>}
      {tab==="accueil"&&<div className="ym-page">
        <h1>Tableau de bord</h1>
        <Card className="ym-install-card" title="Installer l'application" icon="mobile">
          <p className="ym-hint">Accédez rapidement à YEM depuis votre écran d'accueil. Une connexion reste nécessaire pour consulter les données scolaires.</p>
          <PWAInstall buttonClassName="yd-btn primary" label="Ajouter YEM à mon téléphone"/>
        </Card>
        <div className="ym-overview" aria-label="Indicateurs du professeur">
          <div><Icon name="calendar" size={22}/><strong>{hasTimetable?todayEntries.length:"—"}</strong><span>Cours aujourd'hui</span></div>
          <div><Icon name="file" size={22}/><strong>{activeCourses.length}</strong><span>Matières et classes enseignées</span></div>
          <div><Icon name="users" size={22}/><strong>{classIds.length}</strong><span>Classes affectées</span></div>
          <div><Icon name="check" size={22}/><strong>{todayCalls===null?"—":todayCalls}</strong><span>Appels enregistrés aujourd'hui</span></div>
        </div>
        <section className="ym-shortcuts-section" aria-label="Accès rapides">
          <h2>Accès rapides</h2>
          <div className="ym-shortcuts">
            {[
              ["classes","users","Mes classes"],["notes","file","Notes"],["moyennes","barchart","Moyennes"],
              ["appel","check","Appel"],["emploi","calendar","Emploi du temps"],
            ].map(([id,icon,label])=><button type="button" className="ym-shortcut" onClick={()=>open(id)} key={id}>
              <span><Icon name={icon} size={26}/></span><strong>{label}</strong>
            </button>)}
          </div>
        </section>
        <section className="ym-sessions" aria-label="Séances d'aujourd'hui">
          <div className="ym-section-heading"><h2>Séances d'aujourd'hui</h2>
            <button type="button" onClick={()=>open("emploi")}>Voir l'emploi du temps <Icon name="chevron" size={15}/></button>
          </div>
          {!hasTimetable?<p className="ym-hint">L'emploi du temps n'est pas accessible à ce compte.</p>:
          !todayEntries.length?<p className="ym-empty">Aucune séance planifiée aujourd'hui.</p>:
          todayEntries.map(e=><button type="button" className="ym-session-row" onClick={()=>open("emploi")} key={e.id}>
            <span className="ym-session-icon"><Icon name="file" size={22}/></span>
            <span className="ym-session-time"><strong>{e.start_time} – {e.end_time}</strong></span>
            <span className="ym-session-subject"><strong>{e.subject}</strong><small>{displayClass(data.classes,e.classroom)}</small></span>
            <Icon name="chevron" size={17}/>
          </button>)}
        </section>
      </div>}
      {!loading&&tab==="classes"&&<div className="ym-page">
        <section className="ym-section-heading"><h1>Mes classes</h1><span>{classIds.length} classe(s)</span></section>
        {!classIds.length&&<p className="ym-empty">Aucune classe ne vous a encore été affectée.</p>}
        {classIds.map(id=><Card key={id} className="ym-class-card" title={displayClass(data.classes,id)} icon="users">
          <p className="ym-hint">Matières attribuées</p>
          <div className="ym-tag-list">{activeCourses.filter(c=>c.classroom===id).map(c=>
            <span className="ym-tag" key={c.id}>{subjectName(c)}</span>)}</div>
          <div className="ym-inline-actions"><Button icon="file" onClick={()=>open("notes")}>Notes</Button>
            <Button icon="check" onClick={()=>open("appel")}>Faire l'appel</Button></div>
        </Card>)}
      </div>}
      {!loading&&tab==="emploi"&&<div className="ym-page">
        <div className="ym-section-heading"><h1>Emploi du temps</h1><Button onClick={()=>open("accueil")}>Accueil</Button></div>
        {!activeEntries.length?<p className="ym-empty">Aucun cours planifié pour l'année sélectionnée.</p>:
          week.map((day,index)=>{
            const slots=activeEntries.filter(e=>e.weekday===index).sort((a,b)=>a.start_time.localeCompare(b.start_time));
            return slots.length?<Card key={day} title={day} icon="calendar">
              {slots.map(s=><div className="ym-schedule-item" key={s.id}>
                <strong>{s.start_time} – {s.end_time}</strong>
                <span>{s.subject} · {displayClass(data.classes,s.classroom)}</span>
              </div>)}
            </Card>:null;
          })}
      </div>}
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
      {tabs.map(item=><button type="button" key={item.id}
        aria-current={tab===item.id?"page":undefined}
        className={tab===item.id?"active":""} onClick={()=>open(item.id)}>
        <Icon name={item.icon} size={21}/><span>{item.label}</span>
      </button>)}
    </nav>
  </div>;
}
