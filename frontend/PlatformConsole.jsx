import React, {useEffect, useMemo, useState} from "react";
import SchoolDashboard from "./SchoolDashboard.jsx";
import brand from "./assets/yem-brand.webp";
import "./platform-console.css";

const token = () => document.cookie.split("; ").find(x => x.startsWith("csrftoken="))?.split("=")[1] || "";
async function api(path, body) {
  if (body !== undefined) await fetch("/api/v1/auth/csrf", {credentials: "same-origin"});
  const response = await fetch("/api/v1/" + path, {
    credentials: "same-origin",
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : {"Content-Type": "application/json", "X-CSRFToken": token()},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) throw Error("Le serveur YEM ne répond pas correctement.");
  const data = await response.json();
  if (!response.ok) throw Error(data.error || "Opération refusée.");
  return data;
}

const blank = {organization_name: "", organization_id: "", school_name: "", username: "", email: "", first_name: "", last_name: "", password: "", role: "direction"};
const userBlank = {username: "", email: "", first_name: "", last_name: "", password: "", role: "enseignant"};
const menus = [
  ["overview", "Vue d'ensemble", "◫"],
  ["schools", "Établissements", "▤"],
  ["new", "Nouvel établissement", "+"],
  ["users", "Comptes et accès", "♙"],
  ["school", "Interventions", "↗"],
  ["account", "Sécurité du compte", "◇"],
];
const titles = {
  overview: "Vue d'ensemble",
  schools: "Répertoire des établissements",
  new: "Créer un établissement",
  users: "Comptes et accès",
  school: "Fiche établissement",
  account: "Sécurité du compte",
};
const roleOptions = [
  ["direction", "Direction"], ["secretariat", "Secrétariat"],
  ["enseignant", "Enseignant"], ["comptabilite", "Comptabilité"],
  ["parent", "Parent"], ["eleve", "Élève"],
];

export default function PlatformConsole({user, mfaEnabled, accountView, onLogout}) {
  const [page, setPage] = useState("overview");
  const [data, setData] = useState({schools: [], total: 0, organizations: 0, users: 0, organization_options: []});
  const [form, setForm] = useState(blank);
  const [person, setPerson] = useState(userBlank);
  const [school, setSchool] = useState("");
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  async function refresh() {
    const result = await api("platform/schools");
    setData(result);
    return result;
  }
  useEffect(() => {
    if (!mfaEnabled) return;
    let live = true;
    api("platform/schools").then(result => {if (live) setData(result);})
      .catch(error => {if (live) {setMessage(error.message); setSuccess(false);}});
    return () => {live = false;};
  }, [mfaEnabled]);
  const chosen = data.schools.find(item => String(item.id) === String(school));
  const filtered = useMemo(() => data.schools.filter(item =>
    (item.name + " " + item.organization).toLocaleLowerCase("fr").includes(search.toLocaleLowerCase("fr").trim())
  ), [data.schools, search]);
  const update = (setter, name, value) => setter(old => ({...old, [name]: value}));
  function navigate(key) {setPage(key); setMessage(""); setMenuOpen(false);}
  function openSchool(id) {setSchool(String(id)); navigate("school");}
  async function submit(action) {
    setLoading(true); setMessage(""); setSuccess(false);
    try {
      const result = await action();
      await refresh();
      return result;
    } catch (error) {
      setMessage(error.message);
      return null;
    } finally {setLoading(false);}
  }
  async function enterSchool() {
    if (!chosen || !window.confirm("Ouvrir un accès de direction à cet établissement ? Cette intervention sera enregistrée dans son journal.")) return;
    const result = await submit(() => api("platform/schools/" + chosen.id + "/admin-access", {}));
    if (result) setPage("school-workspace");
  }

  if (!mfaEnabled) return <div className="pc-mfa-container">
    <div className="pc-mfa-warning"><h2>Activation MFA obligatoire</h2>
      <p>Pour administrer les établissements, activez d'abord la double authentification de votre compte. La console reste protégée tant que cette étape n'est pas terminée.</p>
    </div>
    {accountView}
  </div>;

  if (page === "school-workspace") return <div className="pc-standalone-school">
    <div className="pc-school-return"><img src={brand} alt="Logo YEM"/><div><strong>Intervention dans un établissement</strong><span>{chosen?.name || "Établissement"}</span></div>
      <button type="button" onClick={() => navigate("school")}>← Retour à la console plateforme</button>
    </div>
    <SchoolDashboard user={user} initialSchoolId={school} accountView={accountView} onLogout={onLogout}/>
  </div>;

  return <div className="pc-shell">
    <aside className={"pc-side" + (menuOpen ? " expanded" : "")} aria-label="Administration de la plateforme">
      <div className="pc-identity"><img className="pc-brand" src={brand} alt="Logo officiel YEM"/><div><b>YEM</b><small>Console plateforme</small></div></div>
      <div className="pc-menu-caption">ADMINISTRATION GÉNÉRALE</div>
      <nav className="pc-nav" aria-label="Navigation de la console">
        {menus.map(([key, label, symbol]) => <button type="button" key={key} className={page === key ? "active" : ""} aria-current={page === key ? "page" : undefined} onClick={() => navigate(key)}><span className="pc-menu-icon" aria-hidden="true">{symbol}</span>{label}</button>)}
      </nav>
      <div className="pc-sidefoot"><span className="pc-online"></span> Console sécurisée<br/><small>YEM · Administration centrale</small><button type="button" className="pc-logout" onClick={onLogout}>Se déconnecter</button></div>
    </aside>
    <main className="pc-content">
      <header className="pc-header">
        <div><div className="pc-eyebrow">PLATEFORME YEM / {titles[page]}</div><h1>{titles[page]}</h1><p>Gérez le réseau scolaire sans mélanger les données des établissements.</p></div>
        <div className="pc-profile"><span className="pc-avatar">●</span><div><strong>{user?.username || "Administrateur"}</strong><small>Super-administrateur</small></div></div>
        <button type="button" className="pc-mobile-menu" aria-expanded={menuOpen} onClick={() => setMenuOpen(v => !v)}>☰ Menu</button>
      </header>
      {message && <div role="status" className={"pc-alert" + (success ? " pc-success" : "")}>{message}</div>}
      {page === "overview" && <>
        <section className="pc-welcome"><div><span className="pc-welcome-tag">VUE PLATEFORME</span><h2>Bienvenue dans votre espace de pilotage</h2><p>Un point d'entrée unique pour vos organisations, établissements et responsables. Les espaces pédagogiques restent indépendants.</p><button className="pc-primary" onClick={() => navigate("new")}>+ Nouvel établissement</button></div><img src={brand} alt="" aria-hidden="true"/></section>
        <div className="pc-stats">
          <article><small>Organisations</small><strong>{data.organizations}</strong><span>Structures propriétaires</span></article>
          <article><small>Établissements</small><strong>{data.total}</strong><span>Dans le réseau YEM</span></article>
          <article><small>Comptes utilisateurs</small><strong>{data.users}</strong><span>Sur la plateforme</span></article>
        </div>
        <section className="pc-panel"><div className="pc-paneltop"><div><h2>Établissements récents</h2><p>Accès rapide aux fiches d'administration.</p></div><button className="pc-outline" onClick={() => navigate("schools")}>Voir le répertoire</button></div>
          {data.schools.length ? <div className="pc-school-cards">{data.schools.slice(0, 6).map(s => <button key={s.id} className="pc-school-card" onClick={() => openSchool(s.id)}><span className="pc-school-initial">{s.name.slice(0, 1).toUpperCase()}</span><span><b>{s.name}</b><small>{s.organization} · {s.members_count} compte(s)</small></span><span className="pc-card-arrow">↗</span></button>)}</div> : <div className="pc-empty"><strong>Aucun établissement pour le moment</strong><p>Commencez par créer une organisation, son premier établissement et son responsable.</p></div>}
        </section>
      </>}
      {page === "schools" && <section className="pc-panel">
        <div className="pc-paneltop"><div><h2>Tous les établissements</h2><p>Sélectionnez une école pour accéder à sa fiche. Aucun accès pédagogique n'est ouvert automatiquement.</p></div><button className="pc-primary" onClick={() => navigate("new")}>+ Créer</button></div>
        <div className="pc-toolbar"><label className="pc-search">Rechercher un établissement ou une organisation<input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Nom de l'établissement, organisation…" /></label><span>{filtered.length} résultat(s)</span></div>
        <div className="pc-table-wrap"><table className="pc-table"><thead><tr><th>Établissement</th><th>Organisation</th><th>Comptes</th><th>État</th><th>Action</th></tr></thead><tbody>
          {filtered.map(s => <tr key={s.id}><td><b>{s.name}</b></td><td>{s.organization}</td><td>{s.members_count}</td><td><span className={"pc-status" + (s.active ? "" : " inactive")}>{s.active ? "Actif" : "Inactif"}</span></td><td><button className="pc-text-btn" onClick={() => openSchool(s.id)}>Voir la fiche ↗</button></td></tr>)}
        </tbody></table>{!filtered.length && <p className="pc-empty">Aucun établissement ne correspond à votre recherche.</p>}</div>
      </section>}
      {page === "school" && <section className="pc-panel">
        <div className="pc-paneltop"><div><h2>Administration par établissement</h2><p>Choisissez une école avant toute intervention. Les opérations sont journalisées côté serveur.</p></div><button className="pc-outline" onClick={() => navigate("schools")}>Répertoire</button></div>
        <label className="pc-select-school">Établissement concerné<select value={school} onChange={e => setSchool(e.target.value)}><option value="">Sélectionner un établissement…</option>{data.schools.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        {chosen ? <div className="pc-detail">
          <div className="pc-detail-main"><div className="pc-detail-icon">{chosen.name.slice(0, 1)}</div><div><h3>{chosen.name}</h3><p>{chosen.organization}</p><span className={"pc-status" + (chosen.active ? "" : " inactive")}>{chosen.active ? "Établissement actif" : "Établissement inactif"}</span></div></div>
          <div className="pc-detail-stats"><div><strong>{chosen.members_count}</strong><span>comptes actifs</span></div><div><strong>Direction</strong><span>accès après validation</span></div></div>
          <div className="pc-detail-actions"><button className="pc-primary" disabled={loading || !chosen.active} onClick={enterSchool}>Ouvrir l'espace scolaire ↗</button><button className="pc-outline" onClick={() => navigate("users")}>+ Créer un compte pour cette école</button></div>
          <p className="pc-hint">L'accès de direction n'est accordé qu'après confirmation et inscription de l'intervention dans le journal. L'espace scolaire s'ouvre sur une page entière.</p>
        </div> : <div className="pc-empty">Sélectionnez un établissement pour consulter ses informations et ses actions.</div>}
      </section>}
      {page === "new" && <section className="pc-panel pc-formpanel"><h2>Nouvel établissement et responsable principal</h2><p>Créez un établissement rattaché à une organisation nouvelle ou existante. Le responsable reçoit un compte personnel et les droits correspondant à son rôle.</p>
        <form onSubmit={async e => {e.preventDefault();const result = await submit(() => api("platform/schools", form));if (result) {setForm(blank);setSchool(String(result.id));navigate("school");setMessage("Établissement créé : " + result.name + " · responsable : " + result.username);setSuccess(true);}}}>
          <div className="pc-form-section"><h3>1. Structure propriétaire</h3><div className="pc-fields">
            <label>Mode de rattachement<select value={form.organization_id ? "existing" : "new"} onChange={e => setForm(o => ({...o, organization_id: e.target.value === "new" ? "" : (data.organization_options?.[0]?.id || "")}))}><option value="new">Créer une organisation</option>{data.organization_options?.length > 0 && <option value="existing">Utiliser une organisation existante</option>}</select></label>
            {form.organization_id ? <label>Organisation existante<select required value={form.organization_id} onChange={e => update(setForm, "organization_id", e.target.value)}>{data.organization_options?.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
            : <label>Nom de l'organisation<input required maxLength={180} value={form.organization_name} onChange={e => update(setForm, "organization_name", e.target.value)}/></label>}
            <label>Nom de l'établissement<input required maxLength={180} value={form.school_name} onChange={e => update(setForm, "school_name", e.target.value)}/></label>
          </div></div>
          <div className="pc-form-section"><h3>2. Identité du responsable</h3><div className="pc-fields">
            {[["first_name", "Prénom"], ["last_name", "Nom"], ["username", "Identifiant de connexion"], ["email", "Adresse email"]].map(([key, label]) => <label key={key}>{label}<input required type={key === "email" ? "email" : "text"} maxLength={key === "email" ? 254 : 150} value={form[key]} onChange={e => update(setForm, key, e.target.value)}/></label>)}
            <label>Fonction du responsable<select value={form.role} onChange={e => update(setForm, "role", e.target.value)}><option value="direction">Directeur / Directrice</option><option value="proprietaire">Propriétaire</option></select></label>
            <label>Mot de passe initial (12 caractères minimum)<input required minLength={12} type="password" autoComplete="new-password" value={form.password} onChange={e => update(setForm, "password", e.target.value)}/></label>
          </div></div>
          <div className="pc-form-actions"><button className="pc-primary" type="submit" disabled={loading}>{loading ? "Enregistrement…" : "Créer l'établissement et son responsable"}</button><button className="pc-outline" type="button" onClick={() => navigate("schools")}>Annuler</button></div>
        </form>
      </section>}
      {page === "users" && <section className="pc-panel pc-formpanel"><h2>Créer un compte d'établissement</h2><p>Chaque utilisateur reçoit un identifiant propre. Les droits restent limités aux permissions du rôle défini dans l'établissement.</p>
        <form onSubmit={async e => {e.preventDefault();const result = await submit(() => api("platform/schools/" + school + "/users", person));if (result) {setPerson(userBlank);setMessage("Compte créé : " + result.username);setSuccess(true);}}}>
          <div className="pc-form-section"><h3>1. Affectation</h3><div className="pc-fields">
            <label>Établissement<select required value={school} onChange={e => setSchool(e.target.value)}><option value="">Sélectionner…</option>{data.schools.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
            <label>Rôle<select value={person.role} onChange={e => update(setPerson, "role", e.target.value)}>{roleOptions.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          </div></div>
          <div className="pc-form-section"><h3>2. Informations du compte</h3><div className="pc-fields">
            {[["first_name", "Prénom"], ["last_name", "Nom"], ["username", "Identifiant"], ["email", "Email"]].map(([key, label]) => <label key={key}>{label}<input required type={key === "email" ? "email" : "text"} value={person[key]} onChange={e => update(setPerson, key, e.target.value)}/></label>)}
            <label>Mot de passe initial<input type="password" required minLength={12} autoComplete="new-password" value={person.password} onChange={e => update(setPerson, "password", e.target.value)}/></label>
          </div></div>
          <button className="pc-primary" type="submit" disabled={loading || !school}>{loading ? "Enregistrement…" : "Créer le compte"}</button>
        </form>
      </section>}
      {page === "account" && <div className="pc-account-area">{accountView}</div>}
      <footer className="pc-footer">YEM — Gestion scolaire et universitaire <span>Développé par <strong>BWETEK Informatyk</strong></span></footer>
    </main>
  </div>;
}
