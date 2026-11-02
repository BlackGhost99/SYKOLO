import React, {useEffect, useState} from "react";
import SchoolPanel from "./SchoolPanel.jsx";

export default function SchoolWorkspace() {
  const [authenticated,setAuthenticated] = useState(false);
  useEffect(() => {
    let active=true;
    async function reload() {
      try {
        const response=await fetch("/api/v1/auth/me", {credentials:"same-origin"});
        const data=await response.json();
        if (active) setAuthenticated(Boolean(response.ok && data.authenticated));
      } catch {if (active) setAuthenticated(false);}
    }
    reload();
    window.addEventListener("yem:auth-change",reload);
    return ()=>{active=false;window.removeEventListener("yem:auth-change",reload);};
  },[]);
  return authenticated ? <SchoolPanel/> : null;
}
