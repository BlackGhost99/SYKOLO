import React, {useEffect,useState} from "react";
import RealDemoExperience from "./RealDemoExperience.jsx";
import AuthPanel from "./AuthPanel.jsx";
import "./platform-console.css";

function RealApp() {
  const [authenticated,setAuthenticated]=useState(false);
  const [apiAvailable,setApiAvailable]=useState(null);
  const [platformAdmin,setPlatformAdmin]=useState(false);
  useEffect(()=>{
    let active=true;
    async function refresh() {
      try {
        const response=await fetch("/api/v1/auth/me",{credentials:"same-origin"});
        if (!response.ok||!response.headers.get("content-type")?.includes("application/json")) throw Error("API indisponible");
        const data=await response.json();
        if (active) {setApiAvailable(true);setAuthenticated(Boolean(data.authenticated));setPlatformAdmin(Boolean(data.user?.is_platform_admin));}
      } catch {
        if(active) {setApiAvailable(false);setAuthenticated(false);}
      }
    }
    refresh();
    window.addEventListener("yem:auth-change",refresh);
    return ()=>{active=false;window.removeEventListener("yem:auth-change",refresh);};
  },[]);
  if (authenticated && !platformAdmin) return <AuthPanel />;
  return <div>
    {!authenticated && <nav className="yem-mode-switch yem-mode-switch-login" aria-label="Mode d'application YEM">
      <strong>YEM</strong>
      <button type="button" aria-pressed="true" onClick={()=>{window.location.hash="#/";}}>Espace de gestion réel</button>
      <button type="button" onClick={()=>{window.location.hash="#/demo";}}>Démonstration interactive · Présentation</button>
    </nav>}
    <div className={authenticated?"yem-live-workspace yem-auth-app":"yem-live-workspace yem-entry-workspace"}>
      {apiAvailable===false && <div role="status" className="yem-deploy-note">L'API YEM est indisponible. Vérifiez le service Django pour enregistrer des données.</div>}
      <AuthPanel />
      <footer className="yem-company">YEM · Développé par BWETEK Informatyk</footer>
    </div>
  </div>;
}

/* Entrée indépendante : ne monte jamais AuthPanel ni les requêtes réelles YEM
   lorsque la démo est active, y compris si le visiteur possède une session. */
export default function App(){
  const parentApp = window.location.pathname === "/parents-app/" || new URLSearchParams(window.location.search).get("app") === "parents";
  const [demo,setDemo]=useState(()=>!parentApp && window.location.hash.startsWith("#/demo"));
  useEffect(()=>{
    const onHashChange=()=>{
      const next=!parentApp && window.location.hash.startsWith("#/demo");
      // Détruit le document et ses opérations en cours avant de retrouver l’API réelle.
      if(demo&&!next)window.location.reload();
      else setDemo(next);
    };
    window.addEventListener("hashchange",onHashChange);
    return()=>window.removeEventListener("hashchange",onHashChange);
  },[demo,parentApp]);
  // Dedicated family entry, independent of the demonstration and staff UI.
  if(parentApp) return <div className="yem-live-workspace yem-auth-app"><AuthPanel parentOnly/><footer className="yem-company">YEM · Développé par BWETEK Informatyk</footer></div>;
  return demo?<RealDemoExperience/>:<RealApp/>;
}
