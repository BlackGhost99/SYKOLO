import React,{useLayoutEffect,useMemo,useState} from "react";
import SchoolDashboard from "./SchoolDashboard.jsx";
import PlatformConsole from "./PlatformConsole.jsx";
import {FamilyWorkspace} from "./ParentPortal.jsx";
import {createOfflineDemoBackend} from "./demo-api-sandbox.js";
import {downloadDemoPdf} from "./demo-pdf.js";
import {DEMO_ROLES} from "./demo-roles.js";
import "./yem-demo-real.css";

/* La présentation utilise exactement les composants de production :
 * menus, tableaux, boutons, barres de navigation, formulaires et styles.
 * Seule la couche API est remplacée par le bac à sable fictif en mémoire. */
// Empêche qu'une erreur d'une rubrique simulée efface toute la page.
class DemoRuntimeBoundary extends React.Component {
  constructor(props){super(props);this.state={failed:false};}
  static getDerivedStateFromError(){return {failed:true};}
  render(){
    if(this.state.failed)return <main className="yem-demo-error" role="alert">
      <h1>Cette rubrique de démonstration ne peut pas s'afficher.</h1>
      <p>Les données fictives de cette rubrique sont incomplètes. Aucun compte, paiement ni dossier réel n'a été modifié.</p>
      <button type="button" onClick={()=>{this.setState({failed:false});this.props.onReset();}}>
        Réinitialiser la démonstration
      </button>
    </main>;
    return this.props.children;
  }
}
export default function RealDemoExperience(){
  const backend=useMemo(()=>createOfflineDemoBackend(),[]);
  const [ready,setReady]=useState(false);
  const [role,setRole]=useState("direction");
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

  const chooseRole=event=>{
    const next=event.target.value;
    backend.setRole(next);
    setRole(next);
    setNotice("");
  };
  const user={username:"demo."+role,first_name:"Visiteur",last_name:"YEM",is_platform_admin:role==="platform"};
  const reset=()=>{backend.reset();setIteration(i=>i+1);setNotice("Données de visite réinitialisées.");};
  const returnToReal=()=>{window.location.hash="#/";};
  const interceptLinks=async event=>{
    const href=event.target.closest?.("a[href]")?.getAttribute("href");
    if(!href||href.startsWith("#/"))return;
    event.preventDefault();
    if(event.type!=="click")return;
    if(href.startsWith("/api/v1/")&&/\/(pdf|receipt)$/.test(href)){
      const result=await backend.fetch(href);
      const document=await result.json();
      if(result.ok&&document.lines){
        downloadDemoPdf(document);
        setNotice("Document fictif téléchargé.");
        return;
      }
    }
    setNotice("Ce lien est indisponible dans la démonstration.");
  };
  const account=<p>Profil de visite fictif : aucun mot de passe ou accès réel n'est utilisé.</p>;
  return <div className="yem-demo-real" data-demo="true" onClickCapture={interceptLinks} onAuxClickCapture={interceptLinks}
    onContextMenuCapture={interceptLinks} onDragStartCapture={interceptLinks}
    onSubmitCapture={event=>event.preventDefault()}>
    {ready&&<DemoRuntimeBoundary key={role+"-"+iteration} onReset={reset}>
      <div className="yem-demo-real-app">
        {role==="platform"?<PlatformConsole user={user} mfaEnabled accountView={account} onLogout={returnToReal}/>:
         role==="parent"?<FamilyWorkspace accountView={account} onLogout={returnToReal}/>:
         <SchoolDashboard user={user} accountView={account} onLogout={returnToReal} initialSchoolId="lycee"/>}
      </div>
    </DemoRuntimeBoundary>}
    <aside className={"yem-demo-pilot"+(showControls?"":" collapsed")} aria-label="Pilotage de la démonstration">
      <button type="button" className="yem-demo-pilot-toggle"
        onClick={()=>setShowControls(o=>!o)}
        aria-expanded={showControls} aria-controls="yem-demo-pilot-body">
        <span className="yem-demo-pilot-dot"/> MODE DÉMONSTRATION
        <span aria-hidden="true">{showControls?"−":"+"}</span>
      </button>
      {showControls&&<div id="yem-demo-pilot-body" className="yem-demo-pilot-body">
        <p>Mêmes écrans que YEM réel · données fictives · aucun enregistrement serveur.</p>
        <label className="yem-demo-pilot-roles">Profil de démonstration
          <select value={role} onChange={chooseRole}>
            {Object.entries(DEMO_ROLES).map(([id,{label}])=><option key={id} value={id}>{label}</option>)}
          </select>
        </label>
        <div className="yem-demo-pilot-actions">
          <button type="button" onClick={reset}>Réinitialiser</button>
          <button type="button" onClick={returnToReal}>Espace de gestion réel</button>
        </div>
        {notice&&<p role="status" className="yem-demo-pilot-notice">{notice}</p>}
      </div>}
    </aside>
  </div>;
}
