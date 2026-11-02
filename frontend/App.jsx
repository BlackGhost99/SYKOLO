import React, { useState } from "react";
import YemDesktop from "./YemDesktop.jsx";
import AuthPanel from "./AuthPanel.jsx";

export default function App() {
  const [mode, setMode] = useState("workspace");
  return <div>
    <nav className="yem-mode-switch" aria-label="Mode d'application YEM">
      <strong>YEM</strong>
      <button type="button" aria-pressed={mode === "workspace"} onClick={() => setMode("workspace")}>Espace de gestion réel</button>
      <button type="button" aria-pressed={mode === "preview"} onClick={() => setMode("preview")}>Maquettes PC (démonstration)</button>
    </nav>
    {mode === "workspace" ?
      <div className="yem-live-workspace">
        <div role="status" className="yem-deploy-note">Espace de gestion connecté à l'API Django. Si les services ne sont pas disponibles, les données ne peuvent pas être enregistrées : YEM est actuellement hébergé en site statique sur Render.</div>
        <AuthPanel />
        <footer className="yem-company">YEM · Développé par BWETEK Informatyk</footer>
      </div> : <YemDesktop />}
  </div>;
}
