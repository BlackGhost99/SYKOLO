import React,{useLayoutEffect,useMemo,useState} from "react";
import SchoolDashboard from "./SchoolDashboard.jsx";
import PlatformConsole from "./PlatformConsole.jsx";
import {FamilyWorkspace} from "./ParentPortal.jsx";
import {createOfflineDemoBackend} from "./demo-api-sandbox.js";
import "./yem-demo-real.css";

/* La présentation utilise exactement les composants de production :
 * menus, tableaux, boutons, barres de navigation, formulaires et styles.
 * Seule la couche API est remplacée par le bac à sable fictif en mémoire. */
const DEMO_USER={
  username:"visiteur.demo",first_name:"Visiteur",last_name:"YEM",
  is_platform_admin:true
};
const OPTIONS=[
  ["school","Direction / établissement"],
  ["platform","Super-administrateur"],
  ["parent","Parent d'élève"],
];
export default function RealDemoExperience(){
  const backend=useMemo(()=>createOfflineDemoBackend(),[]);
  const [ready,setReady]=useState(false);
  const [role,setRole]=useState("school");
  const [iteration,setIteration]=useState(0);
  const [showControls,setShowControls]=useState(true);
  const [notice,setNotice]=useState("");

  useLayoutEffect(()=>{
    const original=window.fetch;
    // Installé AVANT les useEffect des écrans réels. Aucune requête ne
    // sort du navigateur pour la démo, quelle que soit l'URL demandée.
    window.fetch=backend.fetch;
    setReady(true);
    return ()=>{window.fetch=original;};
  },[backend]);

  const reset=()=>{backend.reset();setIteration(i=>i+1);setNotice("Données de visite réinitialisées.");};
  const returnToReal=()=>{window.location.hash="#/";};
  const interceptLinks=event=>{
    const link=event.target.closest?.("a[href]");
    if(link && !link.getAttribute("href")?.startsWith("#/")){
      event.preventDefault();
      setNotice("Lien externe ou document réel désactivé dans la démonstration.");
    }
  };
  const account=<p>Profil de visite fictif : aucun mot de passe ou accès réel n'est utilisé.</p>;
  return <div className="yem-demo-real" data-demo="true" onClickCapture={interceptLinks}
    onSubmitCapture={event=>event.preventDefault()}>
    {ready&&<div className="yem-demo-real-app" key={role+"-"+iteration}>
      {role==="school"?<SchoolDashboard user={DEMO_USER} accountView={account} onLogout={returnToReal} initialSchoolId="lycee"/>:
       role==="platform"?<PlatformConsole user={DEMO_USER} mfaEnabled accountView={account} onLogout={returnToReal}/>:
       <FamilyWorkspace accountView={account} onLogout={returnToReal}/>}
    </div>}
    <aside className={"yem-demo-pilot"+(showControls?"":" collapsed")} aria-label="Pilotage de la démonstration">
      <button type="button" className="yem-demo-pilot-toggle"
        onClick={()=>setShowControls(o=>!o)}
        aria-expanded={showControls} aria-controls="yem-demo-pilot-body">
        <span className="yem-demo-pilot-dot"/> MODE DÉMONSTRATION
        <span aria-hidden="true">{showControls?"−":"+"}</span>
      </button>
      {showControls&&<div id="yem-demo-pilot-body" className="yem-demo-pilot-body">
        <p>Mêmes écrans que YEM réel · données fictives · aucun enregistrement serveur.</p>
        <div className="yem-demo-pilot-roles">
          {OPTIONS.map(([id,label])=><button type="button" key={id}
            className={role===id?"selected":""} aria-pressed={role===id}
            onClick={()=>{setRole(id);setNotice("");}}>{label}</button>)}
        </div>
        <div className="yem-demo-pilot-actions">
          <button type="button" onClick={reset}>Réinitialiser</button>
          <button type="button" onClick={returnToReal}>Espace de gestion réel</button>
        </div>
        {notice&&<p role="status" className="yem-demo-pilot-notice">{notice}</p>}
      </div>}
    </aside>
  </div>;
}
