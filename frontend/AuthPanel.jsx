import React, { useEffect, useState } from "react";
import PlatformConsole from "./PlatformConsole.jsx";
import SchoolDashboard from "./SchoolDashboard.jsx";

const csrfToken = () =>
  document.cookie.split("; ").find((item) => item.startsWith("csrftoken="))?.split("=")[1] || "";

async function authApi(path, body) {
  if (body !== undefined) await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
  const response = await fetch("/api/v1/auth/" + path, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw Error("Service temporairement indisponible.");
  const data = await response.json();
  if (!response.ok) {
    const error = Error(data.error || "Requête refusée.");
    error.mfaRequired = data.mfa_required;
    throw error;
  }
  return data;
}

export default function AuthPanel() {
  const [account, setAccount] = useState(null);
  const [tab, setTab] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(null);
  const [recovery, setRecovery] = useState([]);
  const [busy, setBusy] = useState(false);
  const link = new URLSearchParams(window.location.hash.split("?")[1] || "");
  const isResetLink = window.location.hash.startsWith("#/reset?");

  useEffect(() => {
    let mounted = true;
    authApi("me").then((data) => {
      if (mounted) setAccount(data);
    }).catch(() => { if (mounted) setAccount({ authenticated: false }); window.dispatchEvent(new Event("yem:auth-change")); });
    return () => { mounted = false; };
  }, []);

  async function run(task) {
    setBusy(true);
    setMessage("");
    try { await task(); }
    catch (e) {
      if (e.mfaRequired) setMessage("Ajoutez votre code d’authentification pour vous connecter.");
      else setMessage(e.message);
    } finally { setBusy(false); }
  }

  return (
    <div className={account?.authenticated ? "yem-logged-in" : ""}>
      {account?.authenticated && (account.user?.is_platform_admin ? <PlatformConsole user={account.user} mfaEnabled={account.mfa_enabled} /> : <SchoolDashboard />)}
    <section className="card" id="compte" aria-label="Sécurité du compte" style={{ marginBottom: "1rem" }}>
      <h2>Compte YEM · Accès sécurisé</h2>
      <p className="hint">Les comptes sont créés par un administrateur. Le laboratoire ci-dessous reste une démonstration publique avec données fictives.</p>
      {account?.authenticated ? (
        <>
          <p>Connecté : <strong>{account.user.username}</strong> · MFA : {account.mfa_enabled ? "activé" : "désactivé"}</p>
          <div className="actions">
            <button disabled={busy} onClick={() => run(async () => {
              await authApi("logout", {});
              setAccount({ authenticated: false });
              setPending(null); setRecovery([]); setPassword(""); setCode(""); window.dispatchEvent(new Event("yem:auth-change"));
            })}>Se déconnecter</button>
            {!account.mfa_enabled && <button disabled={busy} onClick={() => setTab("mfa")}>Activer la double authentification</button>}
            {account.mfa_enabled && <button disabled={busy} onClick={() => setTab("disable")}>Désactiver le MFA</button>}
            <button disabled={busy} onClick={() => setTab("change")}>Changer le mot de passe</button>
          </div>

          {tab === "mfa" && !account.mfa_enabled && (
            <form onSubmit={(e) => { e.preventDefault(); run(async () => {
              if (!pending) {
                setPending(await authApi("mfa/begin", { password }));
                setPassword("");
                setMessage("Ajoutez la clé dans votre application TOTP puis confirmez.");
              } else {
                const result = await authApi("mfa/confirm", { code });
                setRecovery(result.recovery_codes);
                setAccount({ ...account, mfa_enabled: true });
                setPending(null); setCode("");
                setMessage("MFA activé. Conservez les codes de secours dans un lieu sûr.");
              }
            }); }}>
              {!pending ? <label className="field">Mot de passe actuel
                <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
              </label> : <>
                <p>Clé TOTP (à saisir dans votre application) : <code>{pending.manual_secret}</code></p>
                <p className="hint">Ne partagez pas cette clé. Un QR code pourra être ajouté ultérieurement.</p>
                <label className="field">Code à six chiffres
                  <input inputMode="numeric" autoComplete="one-time-code" required value={code} onChange={(e) => setCode(e.target.value)} />
                </label>
              </>}
              <button disabled={busy} type="submit">{pending ? "Confirmer le MFA" : "Commencer l’activation MFA"}</button>
            </form>
          )}
          {recovery.length > 0 && <div role="status"><p><strong>Codes de secours, affichés une seule fois :</strong></p><pre style={{ overflowX: "auto" }}>{recovery.join("\n")}</pre><button onClick={() => setRecovery([])}>J’ai enregistré ces codes</button></div>}
          {tab === "disable" && account.mfa_enabled && (
            <form onSubmit={(e) => { e.preventDefault(); run(async () => {
              await authApi("mfa/disable", { password, code });
              setAccount({ ...account, mfa_enabled: false }); setPassword(""); setCode("");
              setMessage("MFA désactivé.");
            }); }}>
              <label className="field">Mot de passe
                <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
              </label>
              <label className="field">TOTP ou code de secours
                <input required value={code} onChange={(e) => setCode(e.target.value)} />
              </label>
              <button type="submit" disabled={busy}>Confirmer la désactivation</button>
            </form>
          )}
          {tab === "change" && (
            <form onSubmit={(e) => { e.preventDefault(); run(async () => {
              await authApi("password/change", { current_password: password, new_password: newPassword });
              setPassword(""); setNewPassword(""); setMessage("Mot de passe changé.");
            }); }}>
              <label className="field">Ancien mot de passe
                <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
              </label>
              <label className="field">Nouveau mot de passe
                <input type="password" autoComplete="new-password" required minLength={12} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
              </label>
              <button disabled={busy} type="submit">Enregistrer le nouveau mot de passe</button>
            </form>
          )}
        </>
      ) : (
        <>
          <div className="actions">
            <button type="button" onClick={() => { setTab("login"); setMessage(""); }}>Connexion</button>
            <button type="button" onClick={() => { setTab("reset"); setMessage(""); }}>Mot de passe oublié</button>
          </div>
          {isResetLink ? (
            <form onSubmit={(e) => { e.preventDefault(); run(async () => {
              await authApi("password/reset/confirm", {
                uid: link.get("uid"), token: link.get("token"), password: newPassword,
              });
              setMessage("Mot de passe modifié. Vous pouvez vous connecter.");
              setTab("login"); setNewPassword("");
              window.history.replaceState(null, "", window.location.pathname);
            }); }}>
              <label className="field">Nouveau mot de passe
                <input type="password" autoComplete="new-password" minLength={12} required value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
              </label>
              <button disabled={busy}>Réinitialiser le mot de passe</button>
            </form>
          ) : tab === "reset" ? (
            <form onSubmit={(e) => { e.preventDefault(); run(async () => {
              const result = await authApi("password/reset/request", { email });
              setMessage(result.message);
            }); }}>
              <label className="field">Adresse email du compte
                <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
              </label>
              <button disabled={busy} type="submit">Envoyer un lien</button>
            </form>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); run(async () => {
              const result = await authApi("login", { username, password, code });
              setAccount(result); window.dispatchEvent(new Event("yem:auth-change")); setPassword(""); setCode(""); setMessage("Connexion réussie.");
            }); }}>
              <label className="field">Identifiant
                <input autoComplete="username" required value={username} onChange={(e) => setUsername(e.target.value)} />
              </label>
              <label className="field">Mot de passe
                <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
              </label>
              <label className="field">Code TOTP ou secours (si MFA activé)
                <input value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" />
              </label>
              <button disabled={busy} type="submit">Se connecter</button>
            </form>
          )}
        </>
      )}
      {message && <p role="status" aria-live="polite">{message}</p>}
    </section>
    </div>
  );
}
