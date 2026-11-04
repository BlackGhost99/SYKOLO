import React,{useEffect,useState} from "react";

export default function PWAInstall() {
  const [deferred,setDeferred]=useState(null);
  const [installed,setInstalled]=useState(false);
  const [help,setHelp]=useState(false);
  useEffect(()=>{
    if(typeof window==="undefined")return;
    setInstalled(window.matchMedia?.("(display-mode: standalone)")?.matches||false);
    const before=e=>{e.preventDefault();setDeferred(e)};
    const done=()=>{setInstalled(true);setDeferred(null)};
    window.addEventListener("beforeinstallprompt",before);
    window.addEventListener("appinstalled",done);
    return()=>{window.removeEventListener("beforeinstallprompt",before);window.removeEventListener("appinstalled",done)};
  },[]);
  if(installed)return null;
  return <div style={{display:"inline-flex",gap:8,alignItems:"center",flexWrap:"wrap"}}>
    <button className="yp-button" type="button" onClick={async()=>{
      if(!deferred){setHelp(true);return;}
      await deferred.prompt();
      const choice=await deferred.userChoice;
      setDeferred(null);setHelp(choice?.outcome!=="accepted");
    }}>Installer YEM sur mon téléphone</button>
    {help&&<small role="status">Sur Android : ouvrir YEM dans Chrome, menu ⋮ puis « Installer l'application » ou « Ajouter à l'écran d'accueil ».</small>}
  </div>;
}
