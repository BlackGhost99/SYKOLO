import React, {useCallback, useEffect, useMemo, useRef, useState} from "react";
import SchoolDashboard from "./SchoolDashboard.jsx";
import AdminPasswordReset from "./AdminPasswordReset.jsx";
import brand from "./assets/yem-brand.webp";
import "./superadmin.css";

/* Tableau de bord réel : aucun chiffre, utilisateur ni établissement fictif. */
const csrf = () => document.cookie.split("; ").find(c => c.startsWith("csrftoken="))?.split("=")[1] || "";
async function api(path, body) {
  if (body !== undefined) {
    const csrfResponse = await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
    if (!csrfResponse.ok) throw Error("Impossible de sécuriser cette opération.");
  }
  const response = await fetch("/api/v1/" + path, {
    credentials:"same-origin",
    method:body === undefined ? "GET" : "POST",
    headers:body === undefined ? {} : {"Content-Type":"application/json", "X-CSRFToken":csrf()},
    body:body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) throw Error("Réponse inattendue du serveur YEM.");
  const data = await response.json();
  if (!response.ok) throw Error(data.error || "Opération refusée.");
  return data;
}
const menu = [
  ["overview", "Vue d'ensemble", "home"],
  ["organizations", "Organisations", "layers"],
  ["schools", "Établissements", "school"],
  ["users", "Utilisateurs & rôles", "users"],
  ["audit", "Sécurité & audit", "shield"],
  ["plans", "Abonnements", "card"],
  ["settings", "Paramètres plateforme", "settings"],
];
const eventLabels = {
  organization_created:"a créé une organisation",
  school_provisioned:"a créé un établissement",
  school_profile_updated:"a modifié la classification d’un établissement",
  member_account_created:"a créé un compte scolaire",
  platform_admin_school_access:"a ouvert un accès d'administration",
  member_role_changed:"a modifié un rôle",
  member_reactivated:"a réactivé un accès",
  member_suspended:"a suspendu un accès",
  school_reactivated:"a réactivé un établissement",
  school_suspended:"a suspendu un établissement",
  school_renamed:"a renommé un établissement",
  limits_updated:"a modifié les limites de l'établissement",
  role_created:"a créé un rôle",
  role_updated:"a mis à jour un rôle",
  settings_updated:"a mis à jour les paramètres",
  student_created:"a créé une fiche élève",
};
function dateText(value) {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : new Intl.DateTimeFormat("fr-GA",{day:"2-digit",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"}).format(d);
}
const fmt = n => (typeof n === "number" ? new Intl.NumberFormat("fr-GA").format(n) : "—");
const orgBlank = {name:""};
const schoolBlank = {organization_name:"",organization_id:"",school_name:"",school_type:"",education_cycles:[],username:"",email:"",first_name:"",last_name:"",password:"",role:"direction"};
const userBlank = {username:"",email:"",first_name:"",last_name:"",password:"",role:"",function_codes:null};
const icons = {
  home:<><path d="m3 10 9-7 9 7v10H3z"/><path d="M9 20v-6h6v6"/></>,
  layers:<><path d="m12 2 9 5-9 5-9-5zM3 12l9 5 9-5M3 17l9 5 9-5"/></>,
  school:<><path d="M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6M9 11h.01M15 11h.01"/></>,
  users:<><circle cx="9" cy="8" r="3"/><path d="M2 20c0-4 3-7 7-7s7 3 7 7M17 5a3 3 0 0 1 0 6M19 14c2 1 3 3 3 6"/></>,
  shield:<><path d="m12 2 9 4v6c0 5-3.5 8-9 10-5.5-2-9-5-9-10V6z"/><path d="m8 12 3 3 5-6"/></>,
  card:<><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h4"/></>,
  settings:<><path d="M10 2h4l1 3 3 1 3-1 2 4-2 2v3l2 2-2 4-3-1-3 1-1 3h-4l-1-3-3-1-3 1-2-4 2-2v-3L1 9l2-4 3 1 3-1z"/><circle cx="12" cy="12" r="3"/></>,
  search:<><circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/></>,
  bell:<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 9h18c0-1-3-2-3-9M10 21h4"/></>,
  chevron:<path d="m6 9 6 6 6-6"/>,
  right:<path d="m9 5 7 7-7 7"/>,
  left:<path d="m15 5-7 7 7 7"/>,
  plus:<path d="M12 5v14M5 12h14"/>,
  userplus:<><circle cx="9" cy="8" r="4"/><path d="M2 21v-2c0-4 3-6 7-6s7 2 7 6v2M19 8v8M15 12h8"/></>,
  clock:<><circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/></>,
  activity:<><path d="M2 12h5l3-7 4 14 3-7h5"/></>,
  pause:<><rect x="4" y="4" width="16" height="16" rx="8"/><path d="M10 9v6m4-6v6"/></>,
  check:<path d="m5 12 4 4L19 6"/>,
  logout:<><path d="M10 3H4v18h6M14 7l5 5-5 5M8 12h11"/></>,
  dots:<><circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/></>,
  mail:<><rect x="2" y="5" width="20" height="14" rx="2"/><path d="m3 7 9 7 9-7"/></>,
  edit:<><path d="m3 17 14-14 4 4-14 14H3z"/></>,
  lock:<><rect x="4" y="11" width="16" height="11" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></>,
  book:<><path d="M12 6C8 3 4 3 2 4v15c4-2 7-1 10 1 3-2 6-3 10-1V4c-2-1-6-1-10 2zM12 6v14"/></>,
  refresh:<><path d="M20 10a8 8 0 1 0-2 7M20 4v6h-6"/></>,
  menu:<path d="M3 6h18M3 12h18M3 18h18"/>,
  external:<><path d="M13 4h7v7M20 4l-9 9"/><path d="M20 14v6H4V4h6"/></>,
  info:<><circle cx="12" cy="12" r="10"/><path d="M12 11v6M12 7h.01"/></>,
};
function Icon({name,size=21}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icons[name] || icons.info}</svg>;
}
function Status({active}) {
  return <span className={"ya-status "+(active?"ya-status-active":"ya-status-paused")}><span/> {active?"Actif":"Suspendu"}</span>;
}
function Field({label,children}) {return <label className="ya-field"><span>{label}</span>{children}</label>;}
function Metric({icon,label,value,foot,onClick,warning=false}) {
  return <button type="button" className={"ya-metric"+(warning?" ya-metric-alert":"")} onClick={onClick}>
    <span className="ya-metric-symbol"><Icon name={icon} size={29}/></span>
    <span><small>{label}</small><strong>{fmt(value)}</strong><em>{foot}</em></span>
    <span className="ya-metric-go"><Icon name="right" size={17}/></span>
  </button>;
}
function Progress({value,max,label}) {
  const percent=max ? Math.min(100,Math.round(value/max*100)) : null;
  return <div className="ya-progress-row">
    <div className="ya-progress-top"><span>{label} : {fmt(value)} / {max===null?"Sans limite":fmt(max)}</span><b>{percent===null?"—":percent+" %"}</b></div>
    <div className={"ya-progress"+(max===null?" ya-unlimited":"")}><span style={{width:(percent??0)+"%"}}/></div>
  </div>;
}
function AuditFeed({events=[],onAll}) {
  return <section className="ya-box ya-audit-card">
    <div className="ya-box-head"><div className="ya-heading-icon"><Icon name="clock" size={23}/></div><div><h2>Activité récente (audit)</h2><p>Opérations réelles enregistrées par la plateforme.</p></div>
      {onAll&&<button className="ya-btn ya-btn-outline ya-view-all" onClick={onAll}>Voir tout l'audit <Icon name="right" size={15}/></button>}
    </div>
    {events.length ? <div className="ya-event-list">{events.map(e=><div className="ya-event" key={e.source+"-"+e.id}>
      <span className="ya-event-icon"><Icon name={e.event?.includes("suspend")?"pause":e.event?.includes("role")?"shield":"userplus"} size={17}/></span>
      <div><strong>{e.actor}</strong> {eventLabels[e.event] || e.event} {e.school&&<span>— {e.school}</span>}{e.reason&&<small>Motif : {e.reason}</small>}</div><time>{dateText(e.at)}</time>
    </div>)}</div>:<div className="ya-empty">Aucune opération enregistrée pour le moment.</div>}
  </section>;
}
function Directory({dashboard,filters,setFilters,onSchool,selected,onNew,compact=false}) {
  const rows=dashboard.schools || [];
  const change=(k,v)=>setFilters(old=>({...old,[k]:v,page:k==="page"?v:1}));
  return <section className="ya-box ya-directory">
    <div className="ya-box-head">
      <div className="ya-heading-icon"><Icon name="school" size={24}/></div><div><h2>Répertoire des établissements</h2><p>Liste réelle des établissements de la plateforme.</p></div>
      <button className="ya-btn ya-btn-primary ya-new-school" onClick={onNew}><Icon name="plus" size={17}/> Nouvel établissement</button>
    </div>
    <div className="ya-directory-filters">
      <label className="ya-directory-search"><Icon name="search" size={18}/><input aria-label="Rechercher un établissement" type="search" placeholder="Rechercher un établissement…" value={filters.q} onChange={e=>change("q",e.target.value)}/></label>
      <select aria-label="Filtrer par organisation" value={filters.organization} onChange={e=>change("organization",e.target.value)}>
        <option value="">Toutes les organisations</option>{(dashboard.organization_options||[]).map(o=><option key={o.id} value={o.id}>{o.name}</option>)}
      </select>
      <select aria-label="Filtrer par statut" value={filters.status} onChange={e=>change("status",e.target.value)}>
        <option value="all">Tous les statuts</option><option value="active">Actifs</option><option value="inactive">Suspendus</option>
      </select>
    </div>
    <div className="ya-table-overflow" role="region" aria-label="Annuaire des établissements" tabIndex={0}><table className="ya-table"><thead><tr>
      <th><button onClick={()=>change("sort",filters.sort==="name"?"-name":"name")}>Établissement ↕</button></th>
      <th>Organisation</th><th>Utilisateurs</th><th>Statut</th><th>Actions</th>
    </tr></thead><tbody>{rows.map(s=><tr key={s.id} className={s.id===selected?"ya-selected":""}>
      <td><div className="ya-school-name"><span className="ya-school-icon"><Icon name="school" size={21}/></span><span><strong>{s.name}</strong><small>{s.students_count} élève(s)</small></span></div></td>
      <td>{s.organization}</td><td><span className="ya-cell-count"><Icon name="users" size={17}/>{fmt(s.members_count)}</span></td>
      <td><Status active={s.active}/></td>
      <td><button className="ya-btn ya-btn-table" onClick={()=>onSchool(s.id)}>Gérer <Icon name="right" size={15}/></button></td>
    </tr>)}</tbody></table></div>
    {!rows.length&&<div className="ya-empty">Aucun établissement ne correspond aux filtres.</div>}
    <div className="ya-pagination">
      <span>{dashboard.filtered_total?((dashboard.page-1)*dashboard.per_page+1):0}–{Math.min(dashboard.filtered_total||0, (dashboard.page||1)*(dashboard.per_page||5))} sur {fmt(dashboard.filtered_total||0)} établissements</span>
      <div className="ya-pager">
        <button aria-label="Page précédente" disabled={(dashboard.page||1)<=1} onClick={()=>change("page",Math.max(1,(dashboard.page||1)-1))}><Icon name="left" size={17}/></button>
        <span>Page {dashboard.page||1} / {dashboard.pages||1}</span>
        <button aria-label="Page suivante" disabled={(dashboard.page||1)>=(dashboard.pages||1)} onClick={()=>setFilters(o=>({...o,page:(dashboard.page||1)+1}))}><Icon name="right" size={17}/></button>
      </div>
      <label className="ya-page-size">Par page <select value={filters.per_page} onChange={e=>change("per_page",Number(e.target.value))}><option value={5}>5</option><option value={10}>10</option><option value={20}>20</option></select></label>
    </div>
  </section>;
}
function Detail({detail,loading,tab,setTab,onCreate,onRole,onStatus,onAccess,onPlan,onRename,onProfile,cycleLabels}) {
  if (loading && !detail) return <section className="ya-box ya-detail"><div className="ya-empty">Chargement de la fiche…</div></section>;
  if (!detail) return <section className="ya-box ya-detail"><div className="ya-empty">Sélectionnez un établissement dans le répertoire pour consulter sa fiche et ses accès.</div></section>;
  const s=detail.school,people=detail.members||[];
  const director=people.find(m=>m.active&&!m.is_platform_admin&&["direction","proprietaire"].includes(m.role_code));
  return <section className="ya-box ya-detail">
    <div className="ya-detail-top"><span className="ya-detail-building"><Icon name="school" size={34}/></span><div className="ya-detail-title"><h2>{s.name}</h2><p>{s.organization}</p><small>ID : {s.id.slice(0,8).toUpperCase()}</small></div><Status active={s.active}/></div>
    {detail.login_code&&<Field label="Code de connexion de l’établissement">
      <input readOnly value={detail.login_code} onFocus={event=>event.target.select()}/>
    </Field>}
    <div className="ya-detail-tabs" role="tablist" aria-label="Détails de l'établissement">
      {[["info","Informations"],["roles","Accès & rôles"],["limits","Limites & abonnement"],["history","Historique"]].map(([key,label])=><button key={key} role="tab" aria-selected={tab===key} className={tab===key?"active":""} onClick={()=>setTab(key)}>{label}</button>)}
    </div>
    {tab==="info"&&<div className="ya-detail-content">
      <div className="ya-info-row"><Icon name="users" size={20}/><span>Direction principale</span><strong>{director?director.name:"Non désignée"}</strong></div>
      <div className="ya-info-row"><Icon name="mail" size={20}/><span>Contact</span><strong>{director?.email || "Non renseigné"}</strong></div>
      <div className="ya-info-row"><Icon name="shield" size={20}/><span>Rôle principal</span><strong>{director?.role || "À attribuer"}</strong></div>
      <div className="ya-info-row"><Icon name="school" size={20}/><span>Type d’établissement</span><strong>{s.school_type_label||"À classifier"}</strong></div>
      <div className="ya-info-row"><Icon name="book" size={20}/><span>Cycles enseignés</span><strong>{(s.education_cycles||[]).map(c=>cycleLabels?.[c]||c).join(" · ")||"Non renseignés"}</strong></div>
      <div className="ya-info-row"><Icon name="users" size={20}/><span>Comptes actifs</span><strong>{fmt(detail.members_count)}</strong></div>
      <div className="ya-info-row"><Icon name="book" size={20}/><span>Élèves actifs</span><strong>{fmt(detail.students_count)}</strong></div>
      <div className="ya-detail-progress"><Progress value={detail.members_count} max={detail.policy.max_users} label="Utilisateurs"/><Progress value={detail.students_count} max={detail.policy.max_students} label="Élèves"/></div>
    </div>}
    {tab==="roles"&&<div className="ya-detail-content">
      <p className="ya-small-copy">Comptes et rôles propres à cet établissement. Les changements demandent un motif et sont audités.</p>
      <div className="ya-mini-people">{people.slice(0,8).map(m=><div className="ya-mini-person" key={m.id}><div><b>{m.name}</b><small>{m.role} · {m.active?"Actif":"Accès suspendu"}</small></div>{!m.is_platform_admin&&<button className="ya-link" onClick={()=>onRole(m)}>Modifier</button>}</div>)}</div>
      {detail.members_truncated&&<p className="ya-note">La fiche affiche les 250 premiers comptes. Ouvrez la gestion des utilisateurs pour la recherche.</p>}
    </div>}
    {tab==="limits"&&<div className="ya-detail-content"><p className="ya-small-copy">Formule administrative : <strong>{detail.policy.plan_name}</strong></p>
      <Progress value={detail.members_count} max={detail.policy.max_users} label="Utilisateurs"/><Progress value={detail.students_count} max={detail.policy.max_students} label="Élèves"/>
      <p className="ya-note">Le suivi des formules n'implique pas de facturation automatique.</p>
      <button className="ya-btn ya-btn-outline" onClick={onPlan}>Modifier les plafonds</button>
    </div>}
    {tab==="history"&&<div className="ya-detail-content ya-history">{(detail.events||[]).length?detail.events.slice(0,7).map(e=><div key={e.source+"-"+e.id}><strong>{e.actor}</strong><span>{eventLabels[e.event]||e.event}</span><time>{dateText(e.at)}</time></div>):<p className="ya-small-copy">Aucun événement enregistré.</p>}</div>}
    <div className="ya-detail-buttons">
      <button className="ya-btn ya-btn-primary" onClick={onCreate} disabled={!s.active}><Icon name="userplus" size={17}/> Créer un compte</button>
      <button className="ya-btn ya-btn-outline" onClick={()=>onRole(null)}><Icon name="shield" size={17}/> Attribuer un rôle</button>
      <button className={"ya-btn "+(s.active?"ya-btn-danger":"ya-btn-outline")} onClick={onStatus}><Icon name={s.active?"pause":"check"} size={17}/>{s.active?"Suspendre":"Réactiver"}</button>
      <button className="ya-btn ya-btn-outline" onClick={onAccess} disabled={!s.active}><Icon name="external" size={16}/> Ouvrir l'école</button>
    </div>
    <button className="ya-link ya-rename" onClick={onProfile}><Icon name="settings" size={14}/> Configurer le type et les cycles</button>
    <button className="ya-link ya-rename" onClick={onRename}><Icon name="edit" size={14}/> Renommer l'établissement</button>
  </section>;
}
function Modal({modal,detail,reason,setReason,roleId,setRoleId,onCancel,onConfirm,busy}) {
  if (!modal) return null;
  const title={role:"Attribuer un rôle",memberStatus:"Modifier l'accès du compte",schoolStatus:"Modifier le statut de l'établissement",rename:"Renommer l'établissement"}[modal.type];
  return <div className="ya-modal-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onCancel();}}>
    <div className="ya-modal" role="dialog" aria-modal="true" aria-label={title}>
      <div className="ya-modal-heading"><h2>{title}</h2><button aria-label="Fermer" onClick={onCancel}>×</button></div>
      <p>{modal.member?.name || detail?.school?.name}. Toute modification est enregistrée dans le journal d'audit.</p>
      {modal.type==="role"&&<Field label="Rôle attribué"><select value={roleId} onChange={e=>setRoleId(e.target.value)}>{(detail?.roles||[]).map(r=><option key={r.id} value={r.id}>{r.label}</option>)}</select></Field>}
      {modal.type==="rename"&&<Field label="Nouveau nom"><input value={modal.name||""} onChange={e=>modal.setName(e.target.value)} maxLength={180} required/></Field>}
      <Field label="Motif obligatoire"><textarea value={reason} onChange={e=>setReason(e.target.value)} maxLength={240} rows={3} placeholder="Expliquez pourquoi vous effectuez cette modification…"/></Field>
      <div className="ya-modal-footer"><button className="ya-btn ya-btn-outline" onClick={onCancel}>Annuler</button><button className="ya-btn ya-btn-primary" disabled={busy||!reason.trim()||(modal.type==="role"&&!roleId)||(modal.type==="rename"&&!modal.name?.trim())} onClick={onConfirm}>{busy?"Enregistrement…":"Confirmer"}</button></div>
    </div>
  </div>;
}
export default function PlatformConsole({user,mfaEnabled,accountView,onLogout}) {
  const [view,setView]=useState("overview");
  const [filters,setFilters]=useState({q:"",organization:"",status:"all",sort:"name",page:1,per_page:5});
  const [dashboard,setDashboard]=useState({schools:[],organization_options:[],recent_events:[],organizations:0,schools_total:0,users_active:0,schools_inactive:0});
  const [schoolId,setSchoolId]=useState("");
  const [detail,setDetail]=useState(null);
  const [detailLoading,setDetailLoading]=useState(false);
  const [detailTab,setDetailTab]=useState("info");
  const [busy,setBusy]=useState(false);
  const [notice,setNotice]=useState(null);
  const [refreshKey,setRefreshKey]=useState(0);
  const [detailKey,setDetailKey]=useState(0);
  const [organizations,setOrganizations]=useState([]);
  const [allSchools,setAllSchools]=useState([]);
  const [schoolProfiles,setSchoolProfiles]=useState([]);
  const [cycleLabels,setCycleLabels]=useState({});
  const [profileForm,setProfileForm]=useState({school_type:"",education_cycles:[]});
  const [events,setEvents]=useState([]);
  const [organizationForm,setOrganizationForm]=useState(orgBlank);
  const [schoolForm,setSchoolForm]=useState(schoolBlank);
  const [person,setPerson]=useState(userBlank);
  const [policyForm,setPolicyForm]=useState({plan_name:"Sans formule",max_users:"",max_students:"",revision:0});
  const [memberSearch,setMemberSearch]=useState("");
  const [memberPage,setMemberPage]=useState(1);
  const [memberResults,setMemberResults]=useState({members:[],total:0,page:1,pages:1,per_page:20});
  const [memberLoading,setMemberLoading]=useState(false);
  const [resetMember,setResetMember]=useState(null);
  const [modal,setModal]=useState(null);
  const [reason,setReason]=useState("");
  const [roleId,setRoleId]=useState("");
  const [menuOpen,setMenuOpen]=useState(false);
  const [profileOpen,setProfileOpen]=useState(false);
  const searchRef=useRef(null);
  const selectedDetail=detail?.school?.id===schoolId?detail:null;
  const selectedName=selectedDetail?.school?.name||dashboard.schools.find(s=>s.id===schoolId)?.name||"établissement";
  const goto=useCallback(page=>{setView(page);setMenuOpen(false);setProfileOpen(false);setNotice(null);window.scrollTo?.(0,0);},[]);
  const update=(setter,name,val)=>setter(old=>({...old,[name]:val}));
  const reload=()=>{setRefreshKey(k=>k+1);setDetailKey(k=>k+1);};
  useEffect(()=>{
    function shortcut(e) {
      if ((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k") {e.preventDefault();searchRef.current?.focus();}
    }
    window.addEventListener("keydown",shortcut);
    return ()=>window.removeEventListener("keydown",shortcut);
  },[]);
  useEffect(()=>{
    if (!mfaEnabled) return;
    let live=true;
    const params=new URLSearchParams(Object.entries(filters).map(([k,v])=>[k,String(v)]));
    api("platform/dashboard?"+params.toString()).then(result=>{
      if(!live)return;
      setDashboard(result);
      if(!schoolId&&result.schools?.length) setSchoolId(result.schools[0].id);
    }).catch(e=>{if(live)setNotice({type:"error",message:e.message});});
    return()=>{live=false;};
  },[mfaEnabled,filters,refreshKey]);
  useEffect(()=>{
    if(!mfaEnabled)return;
    let live=true;
    api("platform/schools").then(result=>{if(live){setAllSchools(result.schools||[]);setSchoolProfiles(result.school_profiles||[]);setCycleLabels(result.cycle_labels||{});}})
      .catch(e=>{if(live)setNotice({type:"error",message:e.message});});
    return()=>{live=false;};
  },[mfaEnabled,refreshKey]);
  useEffect(()=>{
    if(!mfaEnabled||!schoolId){setDetail(null);return;}
    let live=true;setDetailLoading(true);
    api("platform/schools/"+schoolId+"/detail").then(result=>{if(live)setDetail(result);})
      .catch(e=>{if(live){setDetail(null);setNotice({type:"error",message:e.message});}})
      .finally(()=>{if(live)setDetailLoading(false);});
    return()=>{live=false;};
  },[mfaEnabled,schoolId,detailKey]);
  useEffect(()=>{
    if (view==="organizations") {
      let live=true;api("platform/organizations").then(x=>{if(live)setOrganizations(x.organizations||[]);}).catch(e=>{if(live)setNotice({type:"error",message:e.message});});
      return ()=>{live=false;};
    }
    if (view==="audit") {
      let live=true;api("platform/audit?limit=100").then(x=>{if(live)setEvents(x.events||[]);}).catch(e=>{if(live)setNotice({type:"error",message:e.message});});
      return ()=>{live=false;};
    }
  },[view,refreshKey]);
  useEffect(()=>{
    if(view!=="users" || !mfaEnabled || !schoolId){
      setMemberResults({members:[],total:0,page:1,pages:1,per_page:20});
      return;
    }
    let live=true;
    setMemberLoading(true);
    const params=new URLSearchParams({q:memberSearch,page:String(memberPage),per_page:"20"});
    api("platform/schools/"+schoolId+"/members?"+params.toString()).then(result=>{
      if(live)setMemberResults(result);
    }).catch(error=>{if(live)setNotice({type:"error",message:error.message});})
      .finally(()=>{if(live)setMemberLoading(false);});
    return()=>{live=false;};
  },[view,schoolId,memberPage,memberSearch,refreshKey,mfaEnabled]);
  useEffect(()=>{
    if(selectedDetail?.policy) setPolicyForm({
      plan_name:selectedDetail.policy.plan_name,
      max_users:selectedDetail.policy.max_users==null?"":String(selectedDetail.policy.max_users),
      max_students:selectedDetail.policy.max_students==null?"":String(selectedDetail.policy.max_students),
      revision:selectedDetail.policy.revision,
    });
  },[selectedDetail?.school?.id,selectedDetail?.policy?.revision]);
  async function execute(task,success,after) {
    setBusy(true);setNotice(null);
    try {
      const result=await task();
      setNotice({type:"success",message:success});
      if (after) after(result);
      reload();
      return result;
    } catch(e) {setNotice({type:"error",message:e.message});return null;}
    finally {setBusy(false);}
  }
  function chooseSchool(id) {setSchoolId(String(id));setDetailTab("info");setMemberPage(1);}
  function openModal(type, member=null) {
    if(type==="role"&&!member) member=(selectedDetail?.members||[]).find(x=>!x.is_platform_admin)||null;
    setRoleId(member?.role_id||selectedDetail?.roles?.[0]?.id||"");
    setReason("");
    setModal({type,member,name:selectedDetail?.school?.name||"",setName:name=>setModal(o=>({...o,name}))});
  }
  async function confirmModal() {
    if(!modal||!selectedDetail)return;
    const base="platform/schools/"+schoolId;
    let url=base+"/action",body={reason:reason.trim()};
    if (modal.type==="schoolStatus") body={...body,action:"status",active:!selectedDetail.school.active};
    else if (modal.type==="rename") body={...body,action:"rename",name:modal.name.trim()};
    else {
      if(!modal.member)return;
      url=base+"/members/"+modal.member.id+"/action";
      body=modal.type==="role"?{...body,action:"role",role_id:roleId}:{...body,action:"status",active:!modal.member.membership_active};
    }
    const result=await execute(()=>api(url,body),"Modification enregistrée et auditée.");
    if(result){setDetail(result);setModal(null);}
  }
  async function enterSchool() {
    if(!selectedDetail || !window.confirm("Ouvrir un accès de direction à cet établissement ? L'opération sera journalisée."))return;
    const r=await execute(()=>api("platform/schools/"+schoolId+"/admin-access",{}),"Accès à l'espace scolaire ouvert.");
    if(r)setView("school-workspace");
  }
  async function newOrganization(e) {
    e.preventDefault();
    const result=await execute(()=>api("platform/organizations",{name:organizationForm.name}),"Organisation créée.");
    if(result){setOrganizationForm(orgBlank);setOrganizations(old=>[...old,{...result,schools_count:0}]);}
  }
  useEffect(()=>{
    if(selectedDetail?.school){setProfileForm({school_type:selectedDetail.school.school_type||"",education_cycles:[...(selectedDetail.school.education_cycles||[])]});}
  },[selectedDetail?.school?.id,selectedDetail?.school?.school_type,selectedDetail?.school?.education_cycles?.join(",")]);
  function chooseProfile(code,setter){
    const p=schoolProfiles.find(x=>x.code===code);
    setter(old=>({...old,school_type:code,education_cycles:[...(p?.default_cycles||[])]}));
  }
  function toggleCycle(code,setter){
    setter(old=>({...old,education_cycles:old.education_cycles.includes(code)?old.education_cycles.filter(x=>x!==code):[...old.education_cycles,code]}));
  }
  async function saveSchoolProfile(e){
    e.preventDefault();if(!schoolId)return;
    const payload={action:"profile",school_type:profileForm.school_type,education_cycles:profileForm.education_cycles,reason:reason.trim()};
    const result=await execute(()=>api("platform/schools/"+schoolId+"/action",payload),"Classification enregistrée et auditée.");
    if(result){setDetail(result);setReason("");goto("schools");setNotice({type:"success",message:"Type et cycles mis à jour sans modifier les classes ni les élèves."});}
  }
  async function newSchool(e) {
    e.preventDefault();
    const result=await execute(()=>api("platform/schools",schoolForm),"Établissement et responsable créés.");
    if(result){setSchoolId(result.id);setSchoolForm(schoolBlank);goto("schools");setNotice({type:"success",message:"Établissement "+result.name+" créé, compte "+result.username+" opérationnel."});}
  }
  const selectedRole = selectedDetail?.roles?.find(role => role.code === person.role) || selectedDetail?.roles?.[0];
  const proposedFunction = selectedRole?.suggested_function;
  const personFunctions = person.function_codes ?? (proposedFunction ? [proposedFunction] : []);
  async function newUser(e) {
    e.preventDefault();
    if(!schoolId)return;
    const role=selectedRole?.code;
    if(!role){setNotice({type:"error",message:"Aucun rôle disponible pour cette école."});return;}
    const result=await execute(()=>api("platform/schools/"+schoolId+"/users",{...person,role,function_codes:personFunctions}),"Compte scolaire créé.");
    if(result)setPerson(userBlank);
  }
  async function savePlan(e) {
    e.preventDefault();
    if(!schoolId)return;
    const numeric=value=>value===""?null:Number(value);
    const payload={action:"plan",plan_name:policyForm.plan_name,
      max_users:numeric(policyForm.max_users),max_students:numeric(policyForm.max_students),
      revision:policyForm.revision,reason:reason.trim()};
    const result=await execute(()=>api("platform/schools/"+schoolId+"/action",payload),"Formule et limites enregistrées.");
    if(result){setDetail(result);setReason("");}
  }
  function filteredAudit(events) {
    return events.filter(e=>!memberSearch||[e.actor,e.event,e.school,e.subject,e.reason].join(" ").toLowerCase().includes(memberSearch.toLowerCase()));
  }
  const visibleMembers=memberResults.members||[];
  const openForAccount=()=>{goto("users");};
  const detailActions={
    onCreate:openForAccount,
    onRole:m=>{if(!selectedDetail?.members?.length)return goto("users");openModal("role",m);},
    onStatus:()=>openModal("schoolStatus"),
    onAccess:enterSchool,
    onPlan:()=>goto("plans"),
    onRename:()=>openModal("rename"),
    onProfile:()=>{setReason("");goto("profile");},
    cycleLabels,
  };

  if (!mfaEnabled) return <div className="ya-mfa"><div className="ya-warning"><Icon name="lock"/><div><h2>Sécurisez votre espace de super-administration</h2><p>Activez la double authentification pour accéder aux établissements, aux rôles et aux données de plateforme.</p></div></div>{accountView}</div>;
  if(view==="school-workspace")return <div className="ya-workspace">
    <div className="ya-return"><img src={brand} alt="Logo YEM"/><div><b>Espace scolaire — intervention auditée</b><small>{selectedName}</small></div><button onClick={()=>goto("schools")}>← Retour à la console super-admin</button></div>
    <SchoolDashboard user={user} initialSchoolId={schoolId} accountView={accountView} onLogout={onLogout}/>
  </div>;
  return <div className="ya-root">
    <aside className={"ya-sidebar"+(menuOpen?" ya-expanded":"")} aria-label="Navigation de super-administration">
      <div className="ya-brand"><img src={brand} alt="Logo officiel YEM"/><div><b>YEM</b><span>Console de super-administration<br/>de la plateforme</span></div></div>
      <button type="button" className="ya-mobile-toggle" aria-label="Menu de super-administration"
        aria-controls="ya-platform-navigation" aria-expanded={menuOpen} onClick={()=>setMenuOpen(open=>!open)}>
        <Icon name="menu" size={23}/>
      </button>
      <div className="ya-sidebar-rule"/>
      <nav id="ya-platform-navigation" className="ya-nav" aria-label="Administration YEM">{menu.map(([key,label,icon])=><button type="button" key={key} className={view===key?"active":""} aria-current={view===key?"page":undefined} onClick={()=>goto(key)}><Icon name={icon} size={23}/><span>{label}</span></button>)}</nav>
      <div className="ya-sidebar-bottom"><span className="ya-online"/> Session protégée par MFA <button onClick={onLogout}><Icon name="logout" size={17}/> Déconnexion</button></div>
    </aside>
    <main className="ya-main">
      <header className="ya-top">
        <div className="ya-top-title"><p>PLATEFORME / SUPER-ADMIN</p><h1>{view==="overview"?"Console d'administration YEM":({
          organizations:"Organisations",schools:"Établissements",users:"Utilisateurs & rôles",
          audit:"Sécurité & audit",plans:"Abonnements et limites",settings:"Paramètres de la plateforme",newSchool:"Nouvel établissement",profile:"Type et cycles de l’établissement",
        }[view]||"Console d'administration YEM")}</h1><span>Administration globale de YEM — organisations, établissements, utilisateurs et droits.</span></div>
        <div className="ya-top-actions"><div className="ya-global-search"><Icon name="search" size={20}/><input ref={searchRef} type="search" aria-label="Recherche globale" placeholder="Rechercher un établissement…" value={filters.q} onChange={e=>setFilters(o=>({...o,q:e.target.value,page:1}))}/><kbd>Ctrl + K</kbd></div>
          <button className="ya-icon-button" title="Historique des opérations" aria-label="Historique des opérations" onClick={()=>goto("audit")}><Icon name="bell" size={23}/></button>
          <div className="ya-profile-wrap"><button type="button" className="ya-profile" aria-label="Compte super-admin" onClick={()=>setProfileOpen(o=>!o)} aria-expanded={profileOpen}><span className="ya-avatar"><Icon name="users" size={21}/></span><span><b>{user?.username||"Super-admin"}</b><small>Super-administrateur</small></span><Icon name="chevron" size={17}/></button>
          {profileOpen&&<div className="ya-profile-menu"><button onClick={()=>goto("settings")}>Sécurité de mon compte</button><button onClick={onLogout}>Se déconnecter</button></div>}</div>
        </div>
      </header>
      {notice&&<div role="status" className={"ya-notice ya-"+notice.type}><Icon name={notice.type==="success"?"check":"info"} size={18}/>{notice.message}<button onClick={()=>setNotice(null)} aria-label="Fermer le message">×</button></div>}
      {view==="overview"&&<>
        <div className="ya-stats">
          <Metric icon="layers" label="Organisations" value={dashboard.organizations} foot="Structures propriétaires" onClick={()=>goto("organizations")}/>
          <Metric icon="school" label="Établissements" value={dashboard.schools_total} foot={fmt(dashboard.schools_active)+" en activité"} onClick={()=>goto("schools")}/>
          <Metric icon="users" label="Utilisateurs actifs" value={dashboard.users_active} foot="Comptes des écoles actives" onClick={()=>goto("users")}/>
          <Metric icon="pause" label="Établissements suspendus" value={dashboard.schools_inactive} foot="À examiner" warning onClick={()=>{setFilters(o=>({...o,status:"inactive",page:1}));goto("schools");}}/>
        </div>
        <div className="ya-work-grid">
          <Directory dashboard={dashboard} filters={filters} setFilters={setFilters} onSchool={chooseSchool} selected={schoolId} onNew={()=>goto("newSchool")} compact/>
          <Detail detail={selectedDetail} loading={detailLoading} tab={detailTab} setTab={setDetailTab} {...detailActions}/>
        </div>
        <div className="ya-bottom-grid">
          <section className="ya-box ya-quick"><div className="ya-box-head"><div className="ya-heading-icon"><Icon name="activity" size={23}/></div><div><h2>Création rapide</h2><p>Actions courantes de super-administration.</p></div></div>
            <div className="ya-quick-grid">{[["school","Nouvel établissement","newSchool"],["layers","Nouvelle organisation","organizations"],["mail","Créer un directeur","users"],["userplus","Créer un compte","users"]].map(([icon,label,key])=><button type="button" key={label} onClick={()=>{if(label==="Créer un directeur")setPerson(old=>({...old,role:"direction",function_codes:null}));goto(key);}}><Icon name={icon} size={29}/><strong>{label}</strong><Icon name="right" size={19}/></button>)}</div>
          </section>
          <AuditFeed events={dashboard.recent_events||[]} onAll={()=>goto("audit")}/>
        </div>
      </>}
      {view==="schools"&&<div className="ya-work-grid ya-directory-view"><Directory dashboard={dashboard} filters={filters} setFilters={setFilters} onSchool={chooseSchool} selected={schoolId} onNew={()=>goto("newSchool")}/><Detail detail={selectedDetail} loading={detailLoading} tab={detailTab} setTab={setDetailTab} {...detailActions}/></div>}
      {view==="organizations"&&<div className="ya-two-panels">
        <section className="ya-box"><div className="ya-box-head"><div className="ya-heading-icon"><Icon name="layers"/></div><div><h2>Organisations enregistrées</h2><p>Structures propriétaires et nombre d'établissements.</p></div></div>
          <div className="ya-org-list">{organizations.map(o=><button key={o.id} onClick={()=>{setFilters(x=>({...x,organization:o.id,page:1}));goto("schools");}}><span><Icon name="layers"/></span><b>{o.name}</b><small>{fmt(o.schools_count)} établissement(s)</small><Icon name="right" size={17}/></button>)}</div>
          {!organizations.length&&<div className="ya-empty">Aucune organisation créée.</div>}</section>
        <section className="ya-box ya-form-box"><h2>Nouvelle organisation</h2><p>Créer une structure propriétaire sans compte ou école fictive.</p><form onSubmit={newOrganization}>
          <Field label="Nom de l'organisation"><input required maxLength={180} value={organizationForm.name} onChange={e=>update(setOrganizationForm,"name",e.target.value)} placeholder="Ex. Groupe scolaire…"/></Field>
          <button className="ya-btn ya-btn-primary" disabled={busy} type="submit"><Icon name="plus" size={18}/> Créer l'organisation</button>
        </form></section>
      </div>}
      {view==="newSchool"&&<div className="ya-box ya-form-page"><div className="ya-box-head"><div className="ya-heading-icon"><Icon name="school"/></div><div><h2>Créer une école et son responsable</h2><p>L'organisation, l'établissement et le compte sont créés de façon atomique.</p></div></div>
        <form onSubmit={newSchool}><h3>01 — Établissement</h3><div className="ya-form-grid">
          <Field label="Organisation propriétaire"><select value={schoolForm.organization_id?"existing":"new"} onChange={e=>setSchoolForm(old=>({...old,organization_id:e.target.value==="new"?"":dashboard.organization_options?.[0]?.id||""}))}><option value="new">Nouvelle organisation</option>{dashboard.organization_options?.length>0&&<option value="existing">Organisation existante</option>}</select></Field>
          {schoolForm.organization_id?<Field label="Sélectionner l'organisation"><select value={schoolForm.organization_id} required onChange={e=>update(setSchoolForm,"organization_id",e.target.value)}>{(dashboard.organization_options||[]).map(o=><option key={o.id} value={o.id}>{o.name}</option>)}</select></Field>
          :<Field label="Nom de la nouvelle organisation"><input required maxLength={180} value={schoolForm.organization_name} onChange={e=>update(setSchoolForm,"organization_name",e.target.value)}/></Field>}
          <Field label="Nom de l'établissement"><input required maxLength={180} value={schoolForm.school_name} onChange={e=>update(setSchoolForm,"school_name",e.target.value)}/></Field>
          <Field label="Type d’établissement"><select required value={schoolForm.school_type} onChange={e=>chooseProfile(e.target.value,setSchoolForm)}><option value="">Choisir la catégorie…</option>{schoolProfiles.map(p=><option value={p.code} key={p.code}>{p.label}</option>)}</select></Field>
          {schoolForm.school_type&&<div className="ya-field"><span>Cycles réellement enseignés</span><div role="group" aria-label="Cycles enseignés" style={{display:"grid",gap:8}}>{(schoolProfiles.find(p=>p.code===schoolForm.school_type)?.allowed_cycles||[]).map(c=><label key={c}><input type="checkbox" checked={schoolForm.education_cycles.includes(c)} onChange={()=>toggleCycle(c,setSchoolForm)}/> {cycleLabels[c]||c}</label>)}</div><small>Les classes ne sont pas créées automatiquement.</small></div>}
        </div><h3>02 — Compte du responsable</h3><div className="ya-form-grid">
          {[["first_name","Prénom"],["last_name","Nom"],["username","Identifiant"],["email","Adresse e-mail"]].map(([k,l])=><Field key={k} label={l}><input type={k==="email"?"email":"text"} required maxLength={k==="email"?254:150} value={schoolForm[k]} onChange={e=>update(setSchoolForm,k,e.target.value)}/></Field>)}
          <Field label="Fonction du responsable"><select value={schoolForm.role} onChange={e=>update(setSchoolForm,"role",e.target.value)}><option value="direction">{schoolForm.school_type==="primaire"?"Direction du primaire":schoolForm.school_type==="maternelle"?"Direction de la maternelle":"Direction"}</option><option value="proprietaire">Propriétaire de l'école</option></select></Field>
          <Field label="Mot de passe initial (12 caractères minimum)"><input type="password" required minLength={12} autoComplete="new-password" value={schoolForm.password} onChange={e=>update(setSchoolForm,"password",e.target.value)}/></Field>
        </div><div className="ya-form-footer"><button className="ya-btn ya-btn-primary" type="submit" disabled={busy||!schoolForm.school_type||!schoolForm.education_cycles.length}>{busy?"Création…":"Créer l’établissement et son responsable"}</button><button className="ya-btn ya-btn-outline" type="button" onClick={()=>goto("schools")}>Annuler</button></div>
        </form>
      </div>}
      {view==="profile"&&<div className="ya-box ya-form-page"><div className="ya-box-head"><div className="ya-heading-icon"><Icon name="school"/></div><div><h2>Type et cycles enseignés</h2><p>Classification de l’établissement ; aucune classe ou inscription ne sera modifiée.</p></div></div>
        {selectedDetail?<form onSubmit={saveSchoolProfile}>
          <p className="ya-selected-school">Établissement : <b>{selectedDetail.school.name}</b></p>
          <div className="ya-form-grid">
            <Field label="Catégorie administrative"><select required value={profileForm.school_type} onChange={e=>chooseProfile(e.target.value,setProfileForm)}><option value="">À classifier…</option>{schoolProfiles.map(p=><option key={p.code} value={p.code}>{p.label}</option>)}</select></Field>
            {profileForm.school_type!=="non_classe"&&<div className="ya-field"><span>Cycles réellement enseignés</span><div role="group" aria-label="Cycles enseignés" style={{display:"grid",gap:8}}>{(schoolProfiles.find(p=>p.code===profileForm.school_type)?.allowed_cycles||[]).map(c=><label key={c}><input type="checkbox" checked={profileForm.education_cycles.includes(c)} onChange={()=>toggleCycle(c,setProfileForm)}/> {cycleLabels[c]||c}</label>)}</div></div>}
          </div>
          <Field label="Motif obligatoire"><textarea required maxLength={240} rows={3} value={reason} onChange={e=>setReason(e.target.value)}/></Field>
          <div className="ya-form-footer"><button className="ya-btn ya-btn-primary" disabled={busy||!profileForm.education_cycles.length||profileForm.school_type==="non_classe"} type="submit">Enregistrer la classification</button><button type="button" className="ya-btn ya-btn-outline" onClick={()=>goto("schools")}>Retour aux établissements</button></div>
        </form>:<p className="ya-empty">Sélectionnez d’abord un établissement dans le répertoire.</p>}
      </div>}
      {view==="users"&&<div className="ya-two-panels ya-users-layout">
        <section className="ya-box"><h2>Utilisateurs et droits d'accès</h2><p>Les permissions sont propres à l'établissement choisi.</p>
          <button className="ya-btn ya-btn-outline" type="button" onClick={()=>setResetMember({mode:"parent"})}>
            Récupération d'un compte parent
          </button>
          <Field label="Établissement"><select value={schoolId} onChange={e=>chooseSchool(e.target.value)}><option value="">Choisir…</option>{allSchools.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}{selectedDetail&&!allSchools.some(s=>s.id===schoolId)&&<option value={schoolId}>{selectedDetail.school.name}</option>}</select></Field>
          <Field label="Rechercher un compte"><input type="search" value={memberSearch} onChange={e=>{setMemberSearch(e.target.value);setMemberPage(1);}} placeholder="Nom, identifiant, e-mail, rôle…"/></Field>
          <div className="ya-member-list">{memberLoading?<p className="ya-empty">Chargement des comptes…</p>:visibleMembers.length?visibleMembers.map(m=><div key={m.id} className="ya-member"><span className="ya-member-avatar"><Icon name="users"/></span><div><b>{m.name}</b><small>{m.username} · {m.is_platform_admin?"Plateforme (intervention)":m.role} · {m.active?"Actif":"Suspendu"}</small><small>{m.email}</small></div>
            {!m.is_platform_admin&&<div className="ya-member-actions"><button onClick={()=>openModal("role",m)}>Changer le rôle</button><button onClick={()=>openModal("memberStatus",m)}>{m.membership_active?"Suspendre":"Réactiver"}</button><button className="ya-reset-account" type="button" onClick={()=>setResetMember(m)}>Mot de passe oublié</button></div>}</div>):<p className="ya-empty">Aucun compte à afficher pour cette sélection.</p>}</div>
          <div className="ya-pagination ya-members-pagination">
            <span>{fmt(memberResults.total||0)} compte(s)</span>
            <div className="ya-pager">
              <button aria-label="Page précédente des comptes" disabled={memberLoading||memberPage<=1} onClick={()=>setMemberPage(p=>Math.max(1,p-1))}><Icon name="left" size={17}/></button>
              <span>Page {memberResults.page||1} / {memberResults.pages||1}</span>
              <button aria-label="Page suivante des comptes" disabled={memberLoading||memberPage>=(memberResults.pages||1)} onClick={()=>setMemberPage(p=>p+1)}><Icon name="right" size={17}/></button>
            </div>
          </div>
        </section>
        <section className="ya-box ya-form-box"><h2>Créer un compte</h2><p>Identifiants et permissions isolés par établissement.</p><form onSubmit={newUser}>
          <p className="ya-selected-school">Établissement : <b>{selectedName}</b></p>
          <div className="ya-form-grid">
            {[["first_name","Prénom"],["last_name","Nom"],["username","Identifiant de connexion"],["email","E-mail"]].map(([k,l])=><Field key={k} label={l}><input required type={k==="email"?"email":"text"} value={person[k]} onChange={e=>update(setPerson,k,e.target.value)}/></Field>)}
            <Field label="Rôle dans l'établissement"><select required value={selectedRole?.code||""} onChange={e=>setPerson(old=>({...old,role:e.target.value,function_codes:null}))}>{(selectedDetail?.roles||[]).map(r=><option key={r.id} value={r.code}>{r.label}</option>)}</select></Field>
            <p>Code de connexion : <strong>{selectedDetail?.login_code||""}</strong></p>
            <fieldset><legend>Fonctions facultatives (sans droits automatiques)</legend>{(selectedDetail?.functions||[]).map(f=><label key={f.code}><input type="checkbox" checked={personFunctions.includes(f.code)} onChange={e=>setPerson(old=>({...old,function_codes:e.target.checked?[...personFunctions,f.code]:personFunctions.filter(c=>c!==f.code)}))}/>{f.label}</label>)}</fieldset>
            <Field label="Mot de passe initial"><input required type="password" minLength={12} autoComplete="new-password" value={person.password} onChange={e=>update(setPerson,"password",e.target.value)}/></Field>
          </div><button type="submit" disabled={busy||!schoolId||!selectedDetail?.school?.active} className="ya-btn ya-btn-primary"><Icon name="userplus" size={18}/> Créer le compte</button>
        </form></section>
      </div>}
      {view==="audit"&&<div className="ya-box ya-audit-page"><div className="ya-box-head"><div className="ya-heading-icon"><Icon name="shield"/></div><div><h2>Journal d'audit de la plateforme</h2><p>Dernières opérations enregistrées, avec utilisateur et horodatage.</p></div><button className="ya-btn ya-btn-outline" onClick={reload}><Icon name="refresh" size={17}/> Actualiser</button></div>
        <Field label="Rechercher dans l'historique"><input type="search" value={memberSearch} onChange={e=>setMemberSearch(e.target.value)} placeholder="Événement, acteur, école ou motif…"/></Field>
        <AuditFeed events={filteredAudit(events)}/>
      </div>}
      {view==="plans"&&<div className="ya-two-panels">
        <section className="ya-box"><h2>Limites de l'établissement</h2><p>Les plafonds fixés ici sont appliqués à la création de comptes et d'élèves.</p>
          <Field label="Établissement"><select value={schoolId} onChange={e=>chooseSchool(e.target.value)}><option value="">Choisir…</option>{allSchools.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}{selectedDetail&&!allSchools.some(s=>s.id===schoolId)&&<option value={schoolId}>{selectedDetail.school.name}</option>}</select></Field>
          {selectedDetail&&<div className="ya-plan-info"><h3>{selectedDetail.school.name}</h3><Progress label="Utilisateurs" value={selectedDetail.members_count} max={selectedDetail.policy.max_users}/><Progress label="Élèves" value={selectedDetail.students_count} max={selectedDetail.policy.max_students}/></div>}
        </section>
        <section className="ya-box ya-form-box"><h2>Paramétrer une formule</h2><p>Gestion administrative uniquement : aucun prélèvement ou paiement automatique n'est effectué.</p>
          <form onSubmit={savePlan}>
            <Field label="Nom de la formule"><input required maxLength={80} value={policyForm.plan_name} onChange={e=>update(setPolicyForm,"plan_name",e.target.value)}/></Field>
            <div className="ya-form-grid"><Field label="Maximum de comptes (vide = illimité)"><input type="number" min="1" max="1000000" value={policyForm.max_users} onChange={e=>update(setPolicyForm,"max_users",e.target.value)}/></Field>
            <Field label="Maximum d'élèves (vide = illimité)"><input type="number" min="1" max="1000000" value={policyForm.max_students} onChange={e=>update(setPolicyForm,"max_students",e.target.value)}/></Field></div>
            <Field label="Motif de modification"><textarea required maxLength={240} rows={3} value={reason} onChange={e=>setReason(e.target.value)}/></Field>
            <button className="ya-btn ya-btn-primary" type="submit" disabled={busy||!selectedDetail}>Enregistrer les limites</button>
          </form>
        </section>
      </div>}
      {view==="settings"&&<section className="ya-settings-wrap"><div className="ya-box ya-settings-note"><h2>Paramètres et sécurité de la plateforme</h2><p>Les paramètres pédagogiques appartiennent aux établissements. Les paramètres de sécurité ci-dessous concernent uniquement votre compte de super-administration.</p></div>{accountView}</section>}
      <footer className="ya-footer"><span><strong>YEM</strong> — Gestion scolaire &amp; universitaire</span><span>Développé par <b>BWETEK Informatyk</b></span></footer>
    </main>
    <Modal modal={modal} detail={selectedDetail} reason={reason} setReason={setReason} roleId={roleId} setRoleId={setRoleId} onCancel={()=>setModal(null)} onConfirm={confirmModal} busy={busy}/>
    {resetMember&&(schoolId||resetMember.mode==="parent")&&
      <AdminPasswordReset schoolId={schoolId} member={resetMember}
        parent={resetMember.mode==="parent"} onClose={()=>setResetMember(null)}/>} 
  </div>;
}
