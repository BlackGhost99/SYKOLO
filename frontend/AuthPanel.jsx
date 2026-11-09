import React, { useEffect, useState } from "react";
import brand from "./assets/yem-brand.webp";
import "./yem-login-original.css";
import PlatformConsole from "./PlatformConsole.jsx";
import SchoolDashboard from "./SchoolDashboard.jsx";
import {FamilyWorkspace} from "./ParentPortal.jsx";

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
    error.status = response.status;
    error.mfaRequired = data.mfa_required;
    throw error;
  }
  return data;
}

export default function AuthPanel() {
  const [account, setAccount] = useState(null);
  const [tab, setTab] = useState("login");
  const [loginScope, setLoginScope] = useState(() => (
    {"#/admin":"platform", "#/parents":"parent"}[window.location.hash] || "school"
  ));
  const [schoolCode, setSchoolCode] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [registerFirst, setRegisterFirst] = useState("");
  const [registerLast, setRegisterLast] = useState("");
  const [registrationStatus, setRegistrationStatus] = useState(null);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(null);
  const [recovery, setRecovery] = useState([]);
  const [busy, setBusy] = useState(false);
  const link = new URLSearchParams(window.location.hash.split("?")[1] || "");
  const isResetLink = window.location.hash.startsWith("#/reset?");
  const isVerifyLink = window.location.hash.startsWith("#/verify?");
  const registrationReady = registrationStatus?.email_registration_available;
  const emailVerificationRequired = registrationStatus?.email_verification_required !== false;
  const registrationNotice = registrationReady === false
    ? "L’inscription parent est temporairement indisponible."
    : !emailVerificationRequired
      ? "Mode test : aucun e-mail d’activation n’est envoyé. Le compte est utilisable immédiatement. L’accès aux dossiers des élèves reste soumis à la vérification de l’établissement."
      : registrationStatus?.email_test_mode
        ? "Mode test Resend : seuls les destinataires autorisés peuvent recevoir un lien. Un domaine d’envoi vérifié est nécessaire pour ouvrir les inscriptions à tous les parents."
        : "";

  useEffect(() => {
    let live = true;
    authApi("parents/registration-status").then(data=>{
      if(live)setRegistrationStatus(data);
    }).catch(()=>{if(live)setRegistrationStatus({email_registration_available:false});});
    return()=>{live=false};
  },[]);
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

  async function signIn(credentials) {
    await authApi("login", credentials);
    const session = await authApi("me");
    if (!session.authenticated || session.login_scope !== credentials.scope) {
      throw Error("La session n’a pas pu s’ouvrir. Réessayez de vous connecter.");
    }
    setAccount(session);
    setPassword("");
    setCode("");
    window.dispatchEvent(new Event("yem:auth-change"));
  }

  async function registerParent() {
    const result = await authApi("parents/register", {
      username, first_name: registerFirst, last_name: registerLast,
      email, password: newPassword,
    });
    setLoginScope("parent");
    window.history.replaceState(null, "", "#/parents");

    if (result.email_verification_required === false) {
      try {
        await signIn({ username, password: newPassword, scope: "parent" });
      } catch (error) {
        if (error.status === 401 && !error.mfaRequired) {
          setMessage("Impossible d’ouvrir l’espace Parents avec ces informations. Si vous avez déjà un compte, utilisez son identifiant dans Connexion. Pour une nouvelle inscription, essayez un autre identifiant et une autre adresse e-mail.");
          return;
        }
        setTab("login");
        setNewPassword("");
        throw error;
      }
      setMessage("Vous êtes connecté à YEM Parents.");
    } else {
      setMessage(result.message);
    }
    setTab("login");
    setNewPassword("");
  }

  async function logout() {
    await authApi("logout", {});
    setAccount({ authenticated: false });
    setPending(null); setRecovery([]); setPassword(""); setCode(""); window.dispatchEvent(new Event("yem:auth-change"));
  }

  const accountCard = (
    <section className="card pc-account-card" id="compte" aria-label="Sécurité du compte" style={{ marginBottom: "1rem" }}>
      <h2>{account?.authenticated ? "Compte YEM · Accès sécurisé" : "Accès sécurisé à YEM"}</h2>
      <p className="hint">{account?.authenticated
        ? "Gérez votre mot de passe, votre double authentification et vos codes de récupération. Les informations affichées ici concernent votre compte réel."
        : "Choisissez votre espace et connectez-vous avec les identifiants associés à votre compte."}</p>
      {account?.authenticated ? (
        <>
          <p>Connecté : <strong>{account.user.username}</strong> · MFA : {account.mfa_enabled ? "activé" : "désactivé"}</p>
          <div className="actions">
            <button disabled={busy} onClick={() => run(logout)}>Se déconnecter</button>
            {!account.mfa_enabled && <button disabled={busy} onClick={() => setTab("mfa")}>Activer la double authentification</button>}
            {account.mfa_enabled && <button disabled={busy} onClick={() => setTab("disable")}>Désactiver le MFA</button>}
            <button disabled={busy} onClick={() => setTab("change")}>Changer le mot de passe</button>
          </div>

          {tab === "mfa" && !account.mfa_enabled && (
            <form onSubmit={(e) => { e.preventDefault(); run(async () => {
              if (!pending) {
                setPending(await authApi("mfa/begin", { password }));
                setPassword("");
                setCode("");
                setMessage("Scannez le nouveau QR code avec votre application d’authentification. Saisissez ensuite le code à six chiffres.");
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
                <h3>Scannez ce QR code avec votre téléphone</h3>
                <p className="hint">Ouvrez Google Authenticator, Microsoft Authenticator ou Authy, puis choisissez « Ajouter un compte » → « Scanner un QR code ».</p>
                <div style={{display:"inline-block",background:"#fff",border:"1px solid #dbe4dd",borderRadius:12,padding:18,margin:"8px 0 16px"}}>
                  <img src={pending.qr_image} width="235" height="235" alt="QR code privé pour activer la double authentification YEM" style={{display:"block",maxWidth:"100%",height:"auto"}} />
                </div>
                <details><summary>Je ne peux pas scanner : afficher la clé de secours</summary><p><code>{pending.manual_secret}</code></p></details>
                <p className="hint">Ce QR code contient une clé secrète : ne le partagez pas et ne faites pas de capture d’écran.</p>
                <label className="field">Code à six chiffres
                  <input inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" placeholder="Ex. : 123456" required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g,""))} />
                </label>
              </>}
              <button disabled={busy} type="submit">{pending ? "Confirmer le code à six chiffres" : "Générer un nouveau QR code"}</button>
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
          <div className="actions yem-login-actions">
            <button type="button" onClick={() => { setTab("login"); setMessage(""); }}>Connexion</button>
            <button type="button" onClick={() => { setTab("reset"); setMessage(""); }}>Mot de passe oublié</button>
            <button type="button" onClick={() => { setTab("register"); setMessage(""); }}>Créer un compte parent</button>
            {emailVerificationRequired && <button type="button" onClick={() => { setTab("resend"); setMessage(""); }}>Renvoyer mon lien d'activation</button>}
          </div>
          {isVerifyLink ? (
            <form onSubmit={(e) => { e.preventDefault(); run(async () => {
              await authApi("parents/verify", { uid: link.get("uid"), token: link.get("token") });
              setTab("login"); setMessage("Compte parent activé. Connectez-vous avec votre identifiant.");
              window.history.replaceState(null, "", window.location.pathname);
            }); }}>
              <p>Confirmez votre adresse e-mail afin d’activer votre compte YEM Parents.</p>
              <button disabled={busy} type="submit">Activer mon compte</button>
            </form>
          ) : isResetLink ? (
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
          ) : tab === "resend" ? (
            <form onSubmit={e=>{e.preventDefault();run(async()=>{
              const response=await authApi("parents/resend-verification",{email});
              setMessage(response.message);
              setTab("login");
            });}}>
              <p>Si votre compte parent a été créé et n'est pas encore activé, un nouveau lien de confirmation vous sera envoyé.</p>
              {registrationNotice && <p role="status">{registrationNotice}</p>}
              <label className="field">Adresse e-mail
                <input type="email" required value={email} onChange={e=>setEmail(e.target.value)}/>
              </label>
              <button disabled={busy||registrationReady===false} type="submit">Renvoyer le lien</button>
            </form>
          ) : tab === "register" ? (
            <form onSubmit={(e) => { e.preventDefault(); run(registerParent); }}>
              <p>Un seul compte parent pour plusieurs enfants et plusieurs écoles. {emailVerificationRequired ? "Vous devrez confirmer votre adresse e-mail avant la première connexion." : "Après la création, vous pourrez vous connecter immédiatement."}</p>
              {registrationNotice && <p role="status">{registrationNotice}</p>}
              <label className="field">Prénom<input required maxLength={120} autoComplete="given-name" value={registerFirst} onChange={e=>setRegisterFirst(e.target.value)}/></label>
              <label className="field">Nom<input required maxLength={120} autoComplete="family-name" value={registerLast} onChange={e=>setRegisterLast(e.target.value)}/></label>
              <label className="field">Identifiant<input required minLength={3} maxLength={50} autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)}/></label>
              <label className="field">Adresse e-mail<input required type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)}/></label>
              <label className="field">Mot de passe (au moins 12 caractères)<input required type="password" minLength={12} autoComplete="new-password" value={newPassword} onChange={e=>setNewPassword(e.target.value)}/></label>
              <button disabled={busy||registrationReady===false} type="submit">Créer mon compte parent</button>
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
              await signIn({ username, password, code, scope: loginScope, school_code: schoolCode.trim() });
              setMessage("Connexion réussie.");
            }); }}>
              <h3>{loginScope === "platform" ? "Administration YEM" : loginScope === "parent" ? "Espace parents" : "Connexion établissement"}</h3>
              <div className="actions yem-login-scopes" role="group" aria-label="Choisir votre espace de connexion">
                <button type="button" aria-pressed={loginScope === "school"} onClick={()=>{setLoginScope("school");setPassword("");setCode("");window.history.replaceState(null,"","#/ecole");}}>Établissement</button>
                <button type="button" aria-pressed={loginScope === "parent"} onClick={()=>{setLoginScope("parent");setPassword("");setCode("");window.history.replaceState(null,"","#/parents");}}>Parents</button>
                <button type="button" aria-pressed={loginScope === "platform"} onClick={()=>{setLoginScope("platform");setPassword("");setCode("");window.history.replaceState(null,"","#/admin");}}>Administration plateforme</button>
              </div>
              {loginScope === "school" && <label className="field">Code de l'établissement
                <input required value={schoolCode} onChange={e=>setSchoolCode(e.target.value)} placeholder="Code fourni par votre établissement" autoComplete="organization"/>
              </label>}
              <label className="field">Identifiant
                <input disabled={loginScope === "school" && !schoolCode.trim()} autoComplete="username" required value={username} onChange={(e) => setUsername(e.target.value)} />
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
      {message && <p role="status" aria-live="polite" className="yem-auth-message">{message}</p>}
    </section>
  );

  if (account?.authenticated && account.user?.is_platform_admin) {
    return <PlatformConsole user={account.user} mfaEnabled={account.mfa_enabled} accountView={accountCard} onLogout={() => run(logout)}/>;
  }
  if (account?.authenticated && account.login_scope === "parent") {
    return <FamilyWorkspace accountView={accountCard} onLogout={() => run(logout)} />;
  }
  if (account?.authenticated) {
    return <SchoolDashboard user={account.user} initialSchoolId={account.school_id} accountView={accountCard} onLogout={() => run(logout)} />;
  }
  // L'illustration approuvée est affichée comme un seul fichier, sans recréation
  // des logos, motifs ou zones graphiques. Seuls les champs HTML restent actifs.
  const originalSchoolView = loginScope === "school" && tab === "login" && !isResetLink && !isVerifyLink;
  return (
    <div className={originalSchoolView ? "yem-original-login yem-original-login--exact" : "yem-original-login"}>
      <div className="yem-original-login__frame">
        <img
          className="yem-original-login__image"
          src="/yem-login-original.jpg"
          alt=""
          draggable="false"
        />
        <div className="yem-original-login__form">
          {accountCard}
        </div>
      </div>
    </div>
  );
}
