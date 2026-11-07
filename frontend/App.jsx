import React, {useEffect,useState} from "react";
import YemDesktop from "./YemDesktop.jsx";
import DemoExperience from "./DemoExperience.jsx";
import AuthPanel from "./AuthPanel.jsx";
import "./platform-console.css";

function RealApp() {
  const [mode,setMode]=useState("workspace");
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
        if (active) {setApiAvailable(true);setAuthenticated(Boolean(data.authenticated));setPlatformAdmin(Boolean(data.user?.is_platform_admin));if(data.authenticated)setMode("workspace");}
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
    {!authenticated && <nav className="yem-mode-switch" aria-label="Mode d'application YEM">
      <strong>YEM</strong>
      <button type="button" aria-pressed={mode==="workspace"} onClick={()=>setMode("workspace")}>Espace de gestion réel</button>
      <button type="button" aria-pressed={mode==="preview"} onClick={()=>setMode("preview")}>Maquettes PC (référence statique)</button>
      <button type="button" onClick={()=>{window.location.hash="#/demo";}}>Démonstration interactive · Présentation</button>
    </nav>}
    {mode==="workspace"||authenticated ?
      <div className={authenticated?"yem-live-workspace yem-auth-app":"yem-live-workspace"}>
        {apiAvailable===false && <div role="status" className="yem-deploy-note">L'API YEM est indisponible. Vérifiez le service Django pour enregistrer des données.</div>}
        <AuthPanel />
        <footer className="yem-company">YEM · Développé par BWETEK Informatyk</footer>
      </div> : <YemDesktop />}
  </div>;
}

/* Entrée indépendante : ne monte jamais AuthPanel ni les requêtes réelles YEM
   lorsque la démo est active, y compris si le visiteur possède une session. */
export default function App(){
  const [demo,setDemo]=useState(()=>window.location.hash.startsWith("#/demo"));
  useEffect(()=>{
    const onHashChange=()=>setDemo(window.location.hash.startsWith("#/demo"));
    window.addEventListener("hashchange",onHashChange);
    return()=>window.removeEventListener("hashchange",onHashChange);
  },[]);
  return demo?<DemoExperience/>:<RealApp/>;
}
