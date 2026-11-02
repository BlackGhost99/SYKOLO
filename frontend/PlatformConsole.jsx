import React, {useEffect, useState} from "react";
import SchoolPanel from "./SchoolPanel.jsx";
import "./platform-console.css";

const token = () => document.cookie.split("; ").find(x => x.startsWith("csrftoken="))?.split("=")[1] || "";
async function api(path, body) {
  if (body !== undefined) await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
  const response = await fetch("/api/v1/" + path, {
    credentials:"same-origin", method:body === undefined ? "GET" : "POST",
    headers:body === undefined ? {} : {"Content-Type":"application/json","X-CSRFToken":token()},
    body:body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw Error(data.error || "Action refusée.");
  return data;
}
const blank = {organization_name:"", school_name:"", username:"", email:"", first_name:"", last_name:"", password:"",role:"direction"};
const userBlank = {username:"", email:"", first_name:"", last_name:"", password:"", role:"enseignant"};

export default function PlatformConsole({user, mfaEnabled}) {
  const [page,setPage] = useState("overview");
  const [data,setData] = useState({schools:[],total:0,organizations:0,users:0});
  const [form,setForm] = useState(blank);
  const [person,setPerson] = useState(userBlank);
  const [school,setSchool] = useState("");
  const [message,setMessage] = useState("");
  const [loading,setLoading] = useState(false);
  async function refresh() {
    try { setData(await api("platform/schools")); }
    catch(e) { setMessage(e.message); }
  }
  useEffect(()=>{if (mfaEnabled) refresh();},[mfaEnabled]);
  const update = (setter,name,value) => setter(old=>({...old,[name]:value}));
  async function submit(action) {
    setLoading(true); setMessage("");
    try { await action(); await refresh(); } catch(e) { setMessage(e.message); } finally {setLoading(false);}
  }
  if (!mfaEnabled) return <section className="pc-mfa-warning">
    <h2>Finalisez la sécurité de votre console plateforme</h2>
    <p>Activez la double authentification dans la section Compte YEM ci-dessous, puis reconnectez-vous avec votre code pour accéder à la gestion des établissements.</p>
  </section>;

  return <div className="pc-shell">
    <aside className="pc-side">
      <div className="pc-identity"><span className="pc-symbol">Y</span><div><b>YEM</b><small>Console plateforme</small></div></div>
      {[
        ["overview","Vue d'ensemble"],["schools","Établissements"],["new","Créer un établissement"],
        ["users","Comptes et accès"],["manage","Gestion scolaire"]
      ].map(([key,label])=><button key={key} className={page===key?"active":""} onClick={()=>{setPage(key);setMessage("");}}>{label}</button>)}
      <div className="pc-sidefoot">Administration centrale<br/><small>Accès sécurisé · MFA</small></div>
    </aside>
    <main className="pc-content">
      <header className="pc-header"><div><small>PLATEFORME / {page.toUpperCase()}</small><h1>{{
        overview:"Tableau de bord",schools:"Établissements",new:"Nouvel établissement",users:"Gestion des utilisateurs",manage:"Administration pédagogique"
      }[page]}</h1></div><div className="pc-profile">{user.username}<span>Super-administrateur</span></div></header>
      {message && <p role="status" className="pc-alert">{message}</p>}
      {page==="overview" && <>
        <p className="pc-lead">Pilotez les établissements, leurs responsables et les accès depuis un espace distinct des écoles.</p>
        <div className="pc-stats"><article><small>Organisations</small><strong>{data.organizations}</strong></article><article><small>Établissements</small><strong>{data.total}</strong></article><article><small>Comptes utilisateurs</small><strong>{data.users}</strong></article></div>
        <section className="pc-panel"><h2>Actions prioritaires</h2><p>Commencez par créer un établissement et son responsable principal. Il pourra ensuite se connecter à son espace.</p><button className="pc-primary" onClick={()=>setPage("new")}>+ Créer un établissement</button></section>
      </>}
      {page==="schools" && <section className="pc-panel"><div className="pc-paneltop"><h2>Répertoire des établissements</h2><button className="pc-primary" onClick={()=>setPage("new")}>Nouvel établissement</button></div><div className="pc-table-wrap"><table className="pc-table"><thead><tr><th>Établissement</th><th>Organisation</th><th>Comptes affectés</th><th>Statut</th></tr></thead><tbody>{data.schools.map(s=><tr key={s.id}><td><b>{s.name}</b></td><td>{s.organization}</td><td>{s.members_count}</td><td>{s.active?"Actif":"Inactif"}</td></tr>)}</tbody></table>{data.schools.length===0 && <p>Aucun établissement créé pour le moment.</p>}</div></section>}
      {page==="new" && <section className="pc-panel pc-formpanel"><h2>Créer une organisation, une école et son compte principal</h2><p>Les trois éléments sont enregistrés ensemble. Si une opération échoue, rien n'est créé.</p>
        <form onSubmit={e=>{e.preventDefault();submit(async()=>{const result=await api("platform/schools",form);setForm(blank);setMessage("Établissement créé : "+result.name+" · compte "+result.username);setPage("schools");});}}>
          <div className="pc-fields">{[["organization_name","Organisation propriétaire"],["school_name","Nom de l'établissement"],["first_name","Prénom du responsable"],["last_name","Nom du responsable"],["username","Identifiant de connexion"],["email","Adresse email"]].map(([key,label])=><label key={key}>{label}<input required value={form[key]} type={key==="email"?"email":"text"} maxLength={key==="school_name"||key==="organization_name"?180:150} onChange={e=>update(setForm,key,e.target.value)}/></label>)}
            <label>Fonction principale<select value={form.role} onChange={e=>update(setForm,"role",e.target.value)}><option value="direction">Directeur / Directrice</option><option value="proprietaire">Propriétaire</option></select></label>
            <label>Mot de passe initial (12 caractères minimum)<input required type="password" minLength={12} autoComplete="new-password" value={form.password} onChange={e=>update(setForm,"password",e.target.value)}/></label>
          </div><button disabled={loading} className="pc-primary">Créer l'établissement et son responsable</button></form></section>}
      {page==="users" && <section className="pc-panel pc-formpanel"><h2>Créer un utilisateur scolaire</h2><p>Chaque compte est associé à un seul établissement dans cette opération. Les droits dépendent du rôle configuré par l'école.</p>
        <form onSubmit={e=>{e.preventDefault();submit(async()=>{const result=await api("platform/schools/"+school+"/users",person);setPerson(userBlank);setMessage("Compte créé : "+result.username);});}}>
          <div className="pc-fields"><label>Établissement<select required value={school} onChange={e=>setSchool(e.target.value)}><option value="">Sélectionner…</option>{data.schools.map(s=><option value={s.id} key={s.id}>{s.name}</option>)}</select></label>
          {["username","email","first_name","last_name"].map(key=><label key={key}>{{username:"Identifiant",email:"Email",first_name:"Prénom",last_name:"Nom"}[key]}<input required value={person[key]} type={key==="email"?"email":"text"} onChange={e=>update(setPerson,key,e.target.value)}/></label>)}
          <label>Rôle<select value={person.role} onChange={e=>update(setPerson,"role",e.target.value)}><option value="direction">Direction</option><option value="secretariat">Secrétariat</option><option value="enseignant">Enseignant</option><option value="comptabilite">Comptabilité</option><option value="parent">Parent</option><option value="eleve">Élève</option></select></label>
          <label>Mot de passe initial<input required type="password" minLength={12} autoComplete="new-password" value={person.password} onChange={e=>update(setPerson,"password",e.target.value)}/></label></div><button className="pc-primary" disabled={loading||!school}>Créer le compte</button></form></section>}
      {page==="manage" && <section className="pc-panel"><h2>Modules scolaires</h2><p>La gestion pédagogique avancée par le super-administrateur nécessite une attribution contrôlée des droits à chaque établissement. Les modules existants restent disponibles aux responsables scolaires dans leur espace.</p><SchoolPanel/></section>}
    </main>
  </div>;
}
