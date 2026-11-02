import React, { useEffect, useState } from "react";
import YemDesktop from "./YemDesktop.jsx";
import AuthPanel from "./AuthPanel.jsx";

export default function App() {
  const [mode, setMode] = useState("workspace");
  const [apiAvailable, setApiAvailable] = useState(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/auth/me", { credentials: "same-origin", signal: controller.signal })
      .then(async response => {
        if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) throw Error("API hors ligne");
        const data = await response.json();
        if (typeof data.authenticated !== "boolean") throw Error("API invalide");
        setApiAvailable(true);
      })
      .catch(error => { if (error.name !== "AbortError") setApiAvailable(false); });
    return () => controller.abort();
  }, [retry]);
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
