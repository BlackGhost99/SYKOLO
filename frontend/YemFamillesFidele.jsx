import React, {useEffect, useState} from "react";
import ParentDiscovery from "./ParentDiscovery.jsx";
import PWAInstall from "./PWAInstall.jsx";
import SingPayPayment from "./SingPayPayment.jsx";
import "./yem-familles-fidele.css";

// The approved four YEM Familles visuals are the source of truth for structure,
// card hierarchy and colors. Live school data replaces demonstration text only.
const lines = {
  cap:<><path d="m2 10 10-5 10 5-10 5-10-5Z"/><path d="M6 12.5V17c4 3 8 3 12 0v-4.5M22 10v7"/></>,
  bell:<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 9h18c0-1-3-2-3-9ZM10 21h4"/></>,
  help:<><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.7 2.7 0 1 1 4.5 2c-1.3.9-2 1.3-2 2.8M12 17.5h.01"/></>,
  users:<><path d="M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 20v-2a4 4 0 0 0-3-3.9M16 3.2a4 4 0 0 1 0 7.7"/></>,
  down:<path d="m6 9 6 6 6-6"/>,
  left:<path d="m15 18-6-6 6-6"/>,
  right:<path d="m9 18 6-6-6-6"/>,
  home:<><path d="m3 11 9-8 9 8M5 10v11h14V10M9 21v-7h6v7"/></>,
  user:<><circle cx="12" cy="7.5" r="4.5"/><path d="M3.5 21v-2.5a8.5 8.5 0 0 1 17 0V21"/></>,
  school:<><path d="M4 21V7l8-4 8 4v14M2 21h20M9 21v-7h6v7M8 9h1M15 9h1"/></>,
  calendar:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/></>,
  calendarCheck:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18m5 5 3 3 5-5"/></>,
  chart:<><rect x="3" y="13" width="4" height="8" rx="1"/><rect x="10" y="8" width="4" height="13" rx="1"/><rect x="17" y="3" width="4" height="18" rx="1"/></>,
  card:<><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h5"/></>,
  star:<path d="m12 2 3 6.2 6.8 1-4.9 4.8 1.2 6.8-6.1-3.2-6.1 3.2 1.2-6.8-4.9-4.8 6.8-1L12 2Z"/>,
  coins:<><ellipse cx="8" cy="6" rx="5" ry="2.5"/><path d="M3 6v9c0 3.4 10 3.4 10 0V6M3 10c0 3.3 10 3.3 10 0M3 14c0 3.3 10 3.3 10 0M14 9c3.6-2 8-.7 8 1.5V18c0 2.5-6 3.4-8 1"/></>,
  file:<><path d="M6 2h8l5 5v14H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z"/><path d="M14 2v6h5M8 13h7M8 17h7"/></>,
  notification:<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 8-3 9h18c0-1-3-2-3-9ZM10 21h4"/></>,
  book:<><path d="M12 6a9 9 0 0 0-9-2v15a9 9 0 0 1 9 2M12 6a9 9 0 0 1 9-2v15a9 9 0 0 0-9 2M12 6v15"/></>,
  clock:<><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></>,
  check:<><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></>,
  alert:<><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 17h.01"/></>,
  receipt:<><path d="M5 3h14v18l-3-2-4 2-4-2-3 2V3ZM8 8h8M8 12h8M8 16h5"/></>,
  download:<><path d="M12 3v13m-5-5 5 5 5-5M4 18v3h16v-3"/></>,
  document:<><path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2ZM14 2v6h6"/><path d="M8 15h8M8 19h6"/></>,
  clipboard:<><rect x="4" y="4" width="16" height="18" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="m8 14 3 3 5-6"/></>,
  medical:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M9 5V3h6v2m-3 5v6m-3-3h6"/></>,
  heart:<><path d="M20 5.8a5 5 0 0 0-7.2 0L12 7l-.8-1.2a5 5 0 0 0-7.2 7L12 21l8-8.2a5 5 0 0 0 0-7Z"/></>,
  phone:<path d="M5 2h5l2 5-3 2a15 15 0 0 0 6 6l2-3 5 2v5a3 3 0 0 1-3 3C9 22 2 15 2 5a3 3 0 0 1 3-3Z"/>,
  pin:<><path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></>,
  trophy:<><path d="M8 3h8v9a4 4 0 0 1-8 0V3ZM8 5H4v3a5 5 0 0 0 4 5M16 5h4v3a5 5 0 0 1-4 5M12 16v4m-5 1h10"/></>,
  message:<path d="M3 4h18v13H9l-6 4V4Zm4 5h10M7 13h7"/>,
  notebook:<><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 3v18M11 8h6M11 12h6M11 16h4"/></>,
  shield:<><path d="M12 2 21 6v6c0 5-4.5 8.5-9 10-4.5-1.5-9-5-9-10V6l9-4Z"/><path d="m8 12 3 3 5-5"/></>,
  calendarClock:<><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18m-8 3v3l2 1"/></>,
  wallet:<><path d="M3 8V6a3 3 0 0 1 3-3h13v4M3 8h17a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8ZM17 14h5"/></>,
};
function Icon({name, size=22, className=""}) {
  return <svg className={"yfx-icon "+className} width={size} height={size} viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
    strokeLinejoin="round" aria-hidden="true">{lines[name] || lines.file}</svg>;
}
const NAV = [["home","Accueil","home"],["children","Enfants","users"],["payments","Paiements","card"],["school","Scolarité","cap"],["profile","Profil","user"]];
const DAYS = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"];
const money = value => {
  if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value))) return "—";
  return Number(value).toLocaleString("fr-FR",{maximumFractionDigits:0})+" FCFA";
};
const fmt = value => {
  if (!value) return "Non renseignée";
  const date = new Date(String(value).includes("T") ? value : value+"T12:00:00");
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString("fr-GA",{day:"numeric",month:"short",year:"numeric"});
};
const score = g => {
  if (g.score === null || g.score === undefined) return g.label || "—";
  const value = String(g.score).replace(".",",");
  return g.scale_kind === "percentage" ? value+" %" :
    g.scale_kind === "numeric" && g.scale_max!=null ? value+" / "+g.scale_max : value;
};
const balance = c => Number(c?.balance || 0);
const status = c => {
  if (balance(c)<=0) return ["Payé","paid","check"];
  const now=new Date(),today=[now.getFullYear(),String(now.getMonth()+1).padStart(2,"0"),String(now.getDate()).padStart(2,"0")].join("-");
  return c.due_date && c.due_date<today ? ["En retard","late","alert"]:["À venir","due","clock"];
};
function Badge({children, tone="success", icon}) {
  return <span className={"yfx-badge yfx-badge-"+tone}>{icon&&<Icon name={icon} size={15}/>} {children}</span>;
}
function Section({title,icon,children,action,className=""}) {
  return <section className={"yfx-card "+className}>
    <header className="yfx-card-head">{icon&&<span className="yfx-icon-tile"><Icon name={icon} size={24}/></span>}
      <h3>{title}</h3>{action}</header>{children}
  </section>;
}
function Empty({children}) {return <p className="yfx-empty">{children}</p>;}
function photo(child) {
  const uri=child?.photo_url || child?.photo;
  return typeof uri==="string" && uri.startsWith("/") && !uri.startsWith("//") ? uri : null;
}
function Face({child}) {
  const src=photo(child);
  return <div className="yfx-face" aria-label="Photo de l'enfant">
    {src?<img src={src} alt="" loading="lazy"/>:<><Icon name="user" size={46}/><small>Photo non fournie</small></>}
  </div>;
}
function ChildCard({m, detailMode=false, showStats=false, gradeStats=false}) {
  const {child,children,selected,setSelected,enrollment,enrollments,year,setYear,attendancePercent,totalCalls,totals,reportMean,reportRows,observations}=m;
  if(!child) return null;
  const index=children.findIndex(c=>c.student===selected);
  const move=delta=>{if(children.length>1)setSelected(children[(index+delta+children.length)%children.length].student);};
  return <section className={"yfx-card yfx-child-card"+(showStats?" yfx-with-stats":"")+(gradeStats?" yfx-grade-card":"")}>
    <div className="yfx-child-main">
      <Face child={child}/>
      <div className="yfx-child-info"><h2>{child.first_name} {child.last_name}</h2>
        <p><Icon name="school" size={17}/><span>{child.school_name}</span></p>
        <p><Icon name="cap" size={18}/><span>{enrollment?.classroom||"Classe non renseignée"}</span>
          <span className="yfx-split"/> <Icon name="calendar" size={16}/>
          <span>{enrollment?.year ? "Année "+enrollment.year : "Année non renseignée"}</span></p>
        {detailMode&&<><p><Icon name="user" size={17}/><span>Profil scolaire vérifié</span>
          <span className="yfx-split"/><Icon name="file" size={16}/><span>Matricule : {child.matricule_yem||child.student_code||"—"}</span></p>
          <p><Icon name="users" size={17}/><span>Responsable légal : accès validé par l’établissement</span></p></>}
      </div>
      {children.length>1&&<div className="yfx-child-arrows">
        <button type="button" title="Enfant précédent" onClick={()=>move(-1)} aria-label="Enfant précédent"><Icon name="left"/></button>
        <button type="button" title="Enfant suivant" onClick={()=>move(1)} aria-label="Enfant suivant"><Icon name="right"/></button>
      </div>}
    </div>
    {enrollments?.length>1&&<label className="yfx-year-choice">Année scolaire
      <select value={year} onChange={e=>setYear(e.target.value)}>
        {enrollments.map(row=><option key={row.id} value={row.year_id}>{row.year}</option>)}
      </select></label>}
    {(showStats||gradeStats)&&<div className={"yfx-child-stats"+(gradeStats?" yfx-grade-stats":"")}>
      {gradeStats&&<div><Icon name="trophy" size={28}/><small>Moyenne actuelle</small><strong>{reportMean?reportMean:"—"}</strong><em>{reportMean?"Moyenne publiée":"Non publiée"}</em></div>}
      {gradeStats&&<div><Icon name="trophy" size={27}/><small>Rang</small><strong>—</strong><em>Non communiqué</em></div>}
      <div><Icon name="calendarCheck" size={27}/><small>Assiduité</small><strong>{attendancePercent}</strong>
        <em>{totalCalls?totalCalls+" appels clôturés":"Aucune donnée"}</em></div>
      {!gradeStats&&<div><Icon name="chart" size={28}/><small>Moyenne actuelle</small><strong>{reportMean||"—"}</strong><em>{reportMean?"Moyenne publiée":"Non publiée"}</em></div>}
      <div><Icon name="star" size={28}/><small>Comportement</small><strong className="yfx-behavior">{observations.length?observations.length+" avis":"—"}</strong><em>{observations.length?"Avis publiés":"Non communiqué"}</em></div>
    </div>}
  </section>;
}
function Head({m}) {
 const {screen,schoolTab,goSchool,navTo,goDiscovery,firstName,children,selected,setSelected,name,alerts}=m;
 const sub=screen==="payments" ? "Gérez les frais de scolarité, effectuez vos paiements en ligne et téléchargez vos reçus en toute sécurité." :
   "Suivez la scolarité de vos enfants et gérez vos démarches en toute simplicité.";
 return <header className="yfx-hero">
   <div className="yfx-shell">
    <nav className="yfx-topbar" aria-label="Navigation du compte parent">
      <div className="yfx-brand"><Icon name="cap" size={36}/><span><strong>YEM Familles</strong><small>Espace Parents</small></span></div>
      <div className="yfx-top-actions">
        <button type="button" aria-label="Voir les notifications" onClick={()=>goDiscovery("notifications")}>
          <Icon name="bell" size={25}/>{alerts.length>0&&<span className="yfx-red-dot"/>}</button>
        <button type="button" aria-label="Aide et compte" onClick={()=>navTo("profile")}><Icon name="help" size={25}/></button>
      </div>
    </nav>
    <div className="yfx-hero-body">
      {screen==="school" ? <div className="yfx-greeting">
        <button className="yfx-back" onClick={()=>navTo("home")} aria-label="Retour à l'accueil"><Icon name="left" size={26}/></button>
        <div>{schoolTab==="grades" ? <><span>Scolarité</span><h1>Notes et résultats</h1>
          <p>Suivez les résultats scolaires et les appréciations {name?"de "+name:"de votre enfant"}.</p></> :
          <><h1>Suivi scolaire{ name?" – "+name:""}</h1><p>Vie scolaire, emploi du temps et documents officiels.</p></>}</div></div> :
        <div className="yfx-greeting"><div><span>Bonjour,</span><h1>{firstName} <span className="yfx-wave" aria-hidden="true">👋</span></h1>
          <p>{sub}</p></div></div>}
      <label className="yfx-switcher"><Icon name="users" size={21}/><span>Mes enfants</span><Icon name="down" size={18}/>
        <select aria-label="Mes enfants" value={selected} onChange={e=>setSelected(e.target.value)} disabled={!children.length}>
          {!children.length&&<option value="">Aucun enfant rattaché</option>}
          {children.map(c=><option value={c.student} key={c.student}>{c.first_name} {c.last_name}</option>)}
        </select>
      </label>
    </div>
   </div>
 </header>;
}
function ActionTiles({goSchool,navTo}) {
  return <div className="yfx-action-grid">
    {[["Scolarité","cap",()=>goSchool("attendance")],["Paiements","card",()=>navTo("payments")],
      ["Notes","chart",()=>goSchool("grades")],["Emploi du temps","calendar",()=>goSchool("timetable")]].map(([label,ic,click])=>
      <button className="yfx-action" type="button" key={label} onClick={click}><Icon name={ic} size={32}/><strong>{label}</strong></button>)}
  </div>;
}
function Notifications({m}) {
 return <Section title="Notifications récentes" icon="bell" className="yfx-notifications"
   action={<button className="yfx-link" onClick={()=>m.goDiscovery("notifications")}>Tout voir</button>}>
  {m.alerts.length?m.alerts.slice(0,3).map(n=><div className="yfx-notification" key={n.kind+n.id}>
    <span className="yfx-row-icon"><Icon name="file" size={20}/></span>
    <div><strong>{n.message||"Information de l'établissement"}</strong><small>{n.school}</small></div>
    <small>{n.at?new Date(n.at).toLocaleDateString("fr-GA",{day:"numeric",month:"short"}):""}</small>
  </div>):<Empty>Aucune notification pour le moment.</Empty>}
 </Section>;
}
function RecentGrades({m}) {
 return <Section title="Dernières notes" icon="chart"
  action={<button className="yfx-link" onClick={()=>m.goSchool("grades")}>Tout voir</button>}>
   {m.gradeRows.length ? m.gradeRows.slice(0,4).map(g=><div className="yfx-last-grade" key={g.id}>
     <span>{g.subject}</span><Badge>{score(g)}</Badge></div>) :
     <Empty>{m.child ? "Aucune note publiée pour cette année.":"Les notes seront visibles après rattachement à l'établissement."}</Empty>}
 </Section>;
}
function SummaryFinance({m}) {
 const {financial,due,feesReady,currentYearLabel,navTo,data}=m;
 return <Section title="Situation financière" icon="coins" className="yfx-summary" action={data.finance?.scholarship?
   <Badge>Bourse de l'État</Badge>:<Badge icon="check">Dossier scolaire</Badge>}>
   <div className="yfx-finance-caption">{currentYearLabel}</div>
   <div className="yfx-figures">
    <div><small>Total payé</small><strong className="yfx-green">{feesReady&&financial?money(financial.paid):"—"}</strong></div>
    <div><small>Solde restant</small><strong>{feesReady&&financial?money(financial.balance):"—"}</strong></div>
    <div><small>Prochaine échéance</small><strong className="yfx-date">{due?<><Icon name="calendar" size={16}/>{fmt(due.due_date)}</>:"Non définie"}</strong></div>
   </div>
   <button type="button" className="yfx-primary" onClick={()=>navTo("payments")}><Icon name="card" size={21}/> Payer en ligne</button>
 </Section>;
}
function Home({m}) {
 return <><ActionTiles goSchool={m.goSchool} navTo={m.navTo}/>
  {m.child&&<SummaryFinance m={m}/>}
  <div className="yfx-grid-two"><Notifications m={m}/><RecentGrades m={m}/></div>
  <div className="yfx-bottom-links"><button onClick={()=>m.goDiscovery("schools")}>Découvrir les établissements</button>
    <button onClick={()=>m.goDiscovery("requests")}>Suivre mes demandes</button></div>
 </>;
}
function Payments({m}) {
 const {financial,charges,billed,paid,due,currentYearLabel,data,api,activeCharge,setActiveCharge,goDiscovery,child,enrollment}=m;
 const [method,setMethod]=useState("airtel");
 const pending=charges.filter(c=>balance(c)>0);
 function payNow(){if(!pending.length)return;setActiveCharge(prev=>prev||pending[0].id);
  document.getElementById("yfx-payment-form")?.scrollIntoView?.({behavior:"smooth",block:"start"});}
 const methods=[["airtel","Airtel Money"],["moov","Moov Money"],["singpay","SingPay"],["cash","Espèces au guichet"]];
 return <>{!child||!enrollment?<div className="yfx-card"><Empty>Les frais de scolarité officiels seront visibles après l'inscription et le rattachement de votre enfant par l'établissement.</Empty>
  <button className="yfx-outline" onClick={()=>goDiscovery("requests")}>Voir les demandes et frais d'admission</button></div>:<>
 <Section title="Frais de scolarité – Vue d’ensemble" icon="coins"
   action={data.finance?.scholarship?<Badge>Boursier</Badge>:<Badge>État des paiements</Badge>}>
   <p className="yfx-subtitle">{currentYearLabel}</p>
   {m.dataErrors.finance&&<p role="alert">{m.dataErrors.finance}</p>}
   <div className="yfx-figures yfx-four">
     <div><small>Total facturé</small><strong className="yfx-green">{financial?money(financial.billed):"—"}</strong></div>
     <div><small>Déjà payé</small><strong>{financial?money(financial.paid):"—"}</strong></div>
     <div><small>Solde restant</small><strong>{financial?money(financial.balance):"—"}</strong></div>
     <div><small>Prochaine échéance</small><strong className="yfx-date">{due?<><Icon name="calendar" size={16}/>{fmt(due.due_date)}</>:"—"}</strong></div>
   </div>
   {billed>0?<div className="yfx-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(Math.max(0,Math.min(100,100*paid/billed)))}><div style={{width:Math.max(0,Math.min(100,100*paid/billed))+"%"}}>{Math.round(100*paid/billed)} % payé</div></div>:null}
   {data.finance?.scholarship&&<p className="yfx-subtitle">Prise en charge : {data.finance.scholarship.coverage==="all"?"totale": "partielle ou selon décision de l'école"}.</p>}
 </Section>
 <Section title="Détail des frais" icon="calendar" className="yfx-fee-list">
   {charges.length?charges.map(c=>{const [label,tone,ic]=status(c);return <div className="yfx-fee" key={c.id}>
     <span className="yfx-row-icon"><Icon name="notebook" size={21}/></span>
     <div className="yfx-fee-name"><strong>{c.label}</strong><small>{c.due_date?"Échéance : "+fmt(c.due_date):"Aucune échéance"}</small></div>
     <strong className="yfx-fee-value">{money(c.amount)}</strong>
     <div className="yfx-fee-status"><Badge tone={tone} icon={ic}>{label}</Badge>
       {balance(c)>0&&<button type="button" className="yfx-link" onClick={()=>setActiveCharge(c.id)}>Payer</button>}</div>
   </div>;}):<Empty>{data.finance?"Aucun frais affecté pour cette année.":"Chargement des frais…"}</Empty>}
 </Section>
 <Section title="Payer en ligne" icon="card" className="yfx-pay-box">
   <p className="yfx-subtitle">Réglez les frais de scolarité en toute sécurité et en quelques clics.</p>
   <div className="yfx-methods" aria-label="Choix du moyen de paiement">
    {methods.map(([key,label])=><button key={key} type="button" className={method===key?"selected":""} aria-pressed={method===key} onClick={()=>setMethod(key)}>
     <span className={"yfx-method-mark yfx-"+key}>{key==="airtel"?"a":key==="moov"?"M":key==="singpay"?"S":<Icon name="wallet" size={30}/>}</span>
     <strong>{label}</strong></button>)}
   </div>
   {method==="cash"?<p className="yfx-cash-notice">Les espèces se règlent au guichet de l'établissement. Le paiement devient visible après validation par la caisse.</p>:
    <p className="yfx-cash-notice">Airtel Money et Moov Money passent par l'intégration SingPay de l'établissement, uniquement si son compte marchand est activé.</p>}
   {pending.length>0&&method!=="cash"&&<button className="yfx-primary" type="button" onClick={payNow}><Icon name="card" size={22}/> Payer maintenant</button>}
   {!pending.length&&<Empty>Aucun frais restant à régler.</Empty>}
   {pending.length>0&&method==="cash"&&<button className="yfx-outline" onClick={()=>goDiscovery("requests")}>Consulter les paiements au guichet</button>}
   {activeCharge&&method!=="cash"&&<div className="yfx-payment-form" id="yfx-payment-form">
     <label>Frais à payer <select aria-label="Frais à payer" value={activeCharge} onChange={e=>setActiveCharge(e.target.value)}>
      {pending.map(c=><option key={c.id} value={c.id}>{c.label} — {money(c.balance)}</option>)}</select></label>
     <SingPayPayment key={activeCharge} kind="charge" objectId={activeCharge} api={api} partial defaultChannel={method==="moov"?"moov":"airtel"}/>
   </div>}
 </Section>
 <Section title="Historique des paiements / Reçus" icon="receipt" action={<button className="yfx-link" onClick={()=>goDiscovery("requests")}><Icon name="download" size={16}/> Reçus d'admission</button>}>
  {charges.some(c=>Number(c.paid)>0)?charges.filter(c=>Number(c.paid)>0).map(c=><div className="yfx-payment-row" key={c.id}>
   <Icon name="check" size={21}/><div><strong>{c.label}</strong><small>Montant comptabilisé par l'établissement</small></div>
   <strong>{money(c.paid)}</strong></div>):
   <Empty>Aucun encaissement confirmé pour l’année sélectionnée.</Empty>}
   <p className="yfx-small-note">Les reçus et références certifiés sont disponibles pour les paiements confirmés par le prestataire ou dans les demandes d'admission.</p>
 </Section>
 </>}</>;
}
function SchoolResult({m}) {
 const {reportMean,gradeRows,reportRows,goSchool,childBase}=m;
 const [period,setPeriod]=useState("all");
 const periods=[...new Set([...gradeRows.map(x=>x.period),...reportRows.map(x=>x.period)].filter(Boolean))];
 useEffect(()=>setPeriod("all"),[m.selected,m.year]);
 const grades=period==="all"?gradeRows:gradeRows.filter(g=>g.period===period);
 const report=reportRows.find(r=>r.period===period) || reportRows[0];
 return <>
  <nav className="yfx-periods" aria-label="Période scolaire"><Icon name="book" size={23}/><strong>Période :</strong>
   {periods.length?periods.map(p=><button key={p} aria-pressed={period===p} onClick={()=>setPeriod(p)}>{p}</button>):
    <span>Aucune période publiée</span>}
   {periods.length>1&&<button aria-pressed={period==="all"} onClick={()=>setPeriod("all")}>Toutes</button>}
  </nav>
  <Section title="Notes par matière" className="yfx-grades-board">
   <div className="yfx-grade-table-head"><span>Matière</span><span>Note / barème</span><span>Évaluation et appréciation</span></div>
   {grades.length?grades.map(g=><div className="yfx-grade-row" key={g.id}>
     <div><span className="yfx-row-icon"><Icon name="book" size={21}/></span><strong>{g.subject}</strong></div>
     <Badge>{score(g)}</Badge><span className="yfx-grade-remark">{g.assessment}{g.label ? " · "+g.label :""}</span>
   </div>):<Empty>Aucune note publiée pour la période sélectionnée.</Empty>}
  </Section>
  <Section title="Appréciation générale" icon="message" className="yfx-appreciation">
   <p>{report?.label || "L’établissement n’a pas encore publié d’appréciation générale pour cette période."}</p>
  </Section>
  <div className="yfx-three-links">
    <button onClick={()=>goSchool("reports")}><Icon name="document" size={27}/><span><strong>Bulletin</strong><small>Voir / Télécharger</small></span><Icon name="right"/></button>
    <button onClick={()=>goSchool("timetable")}><Icon name="clipboard" size={27}/><span><strong>Emploi du temps</strong><small>Cours et horaires</small></span><Icon name="right"/></button>
    <button onClick={()=>goSchool("attendance")}><Icon name="calendar" size={27}/><span><strong>Absences</strong><small>Présences et retards</small></span><Icon name="right"/></button>
  </div>
 </>;
}
function SchoolLife({m}) {
 const {totals,attendancePercent,totalCalls,observations,data,goSchool,reportRows,childBase,future}=m;
 const events=m.alerts.filter(n=>n.school===m.child?.school_name).slice(0,3);
 return <>
  <div className="yfx-grid-two yfx-school-stats">
   <Section title="Assiduité" icon="calendarCheck">
    <p className="yfx-subtitle">Depuis le début de l'année sélectionnée</p>
    <p className="yfx-large-green">{attendancePercent} <small>{totalCalls? "("+totalCalls+" appels clôturés)" :""}</small></p>
    <div className="yfx-triplet">
     <div><small>Présences</small><strong>{totals?.present??"—"}</strong></div><div><small>Absences</small><strong>{totals?.absent??"—"}</strong></div>
     <div><small>Retards</small><strong>{totals?.late??"—"}</strong></div>
    </div>
   </Section>
   <Section title="Comportement / Discipline" icon="star">
    <p className="yfx-subtitle">Appréciations publiées par l'établissement</p>
    {observations.length?<div className="yfx-green-note">{observations[0].message}</div>:<Empty>Aucune observation ni sanction communiquée par l’établissement.</Empty>}
    <div className="yfx-triplet"><div><small>Observations</small><strong>{observations.length||0}</strong></div>
      <div><small>Comportement</small><strong>—</strong></div></div>
   </Section>
  </div>
  <div className="yfx-grid-two">
   <Section title="Emploi du temps – Aujourd'hui" icon="clock" action={<button className="yfx-link" onClick={()=>goSchool("timetable")}>Tout voir</button>}>
    {future.length?future.map(e=><div className="yfx-timetable-row" key={e.id}><span>{e.start} – {e.end}</span><strong>{e.subject}</strong><Icon name="check" size={18}/></div>):
     <Empty>Aucun cours communiqué pour aujourd'hui.</Empty>}
   </Section>
   <Section title="Événements à venir" icon="calendar" action={<button className="yfx-link" onClick={()=>m.goDiscovery("notifications")}>Tout voir</button>}>
    {events.length?events.map(e=><div className="yfx-event" key={e.kind+e.id}>
      <span className="yfx-event-date">{e.at?fmt(e.at).split(" ").slice(0,2).join(" "):"École"}</span>
      <div><strong>{e.message}</strong><small>{e.school}</small></div></div>):
     <Empty>Aucun événement scolaire publié.</Empty>}
   </Section>
  </div>
  <Section title="Derniers commentaires des enseignants" icon="message" className="yfx-appreciation">
   {observations.length?observations.slice(0,3).map(e=><p key={e.id}>« {e.message} »</p>):<Empty>Aucun commentaire d’enseignant publié.</Empty>}
  </Section>
  <div className="yfx-grid-two">
   <Section title="Documents officiels" icon="document">
    {reportRows.length?reportRows.slice(0,3).map(r=><div className="yfx-document-row" key={r.id}><Icon name="file" size={23}/>
      <div><strong>Bulletin de notes</strong><small>{r.period} · {r.year}</small></div>
      <a href={"/api/v1/"+childBase+"/reports/"+r.id+"/pdf"} className="yfx-pill-link">Consulter <Icon name="right" size={14}/></a></div>):
      <Empty>Aucun bulletin officiel publié.</Empty>}
   </Section>
   <Section title="Informations santé & urgence" icon="medical">
    <Empty>Les informations de santé et les contacts d'urgence ne sont pas communiqués dans l'espace parent pour le moment. Contactez l'établissement pour mettre à jour le dossier.</Empty>
   </Section>
  </div>
 </>;
}
function School({m}) {
 const tabs=[["grades","Notes"],["attendance","Vie scolaire"],["timetable","Emploi du temps"],["reports","Bulletins"]];
 return <>{!m.child?<section className="yfx-card"><Empty>Les informations scolaires seront disponibles après vérification du rattachement de votre enfant.</Empty></section>:<>
  <div className="yfx-school-tabs" aria-label="Rubriques de la fiche scolaire" role="navigation">
   {tabs.map(([key,label])=><button key={key} type="button" aria-pressed={m.schoolTab===key}
     onClick={()=>m.setSchoolTab(key)}>{label}</button>)}
  </div>
  {m.dataErrors[m.schoolTab]&&<p role="alert" className="yfx-alert">{m.dataErrors[m.schoolTab]}</p>}
  {m.schoolTab==="grades"?<SchoolResult m={m}/>:m.schoolTab==="attendance"?<SchoolLife m={m}/>:
   m.schoolTab==="timetable"?<Section title="Emploi du temps de la classe" icon="calendar">
    {m.data.timetable?.entries?.length?m.data.timetable.entries.map(e=><div className="yfx-timetable-row" key={e.id}>
      <span>{DAYS[e.weekday]||"Jour"} · {e.start} – {e.end}</span><strong>{e.subject}</strong><small>{e.teacher||"Enseignant non communiqué"}</small></div>):
      <Empty>Aucune séance publiée pour cette année.</Empty>}
    </Section>:<Section title="Bulletins officiels publiés" icon="document">
    {m.reportRows.length?m.reportRows.map(r=><div className="yfx-document-row" key={r.id}>
      <Icon name="document" size={24}/><div><strong>{r.period}</strong><small>{r.year}</small></div>
      <a className="yfx-pill-link" href={"/api/v1/"+m.childBase+"/reports/"+r.id+"/pdf"}>Télécharger le PDF <Icon name="download" size={16}/></a></div>):
      <Empty>Aucun bulletin publié pour cette année.</Empty>}
    </Section>}
 </>}</>;
}
function Children({m}) {
 return <>
 <Section title="Mes enfants" icon="users">
  {m.children.length?m.children.map(c=><button className="yfx-child-choice" type="button" key={c.student}
      onClick={()=>m.setSelected(c.student)} aria-pressed={c.student===m.selected}>
      <span className="yfx-small-face"><Icon name="user" size={22}/></span><span><strong>{c.first_name} {c.last_name}</strong>
      <small>{c.school_name}</small></span><span>{c.student===m.selected?"Sélectionné":"Afficher"}</span></button>):
      <Empty>Aucun dossier scolaire encore rattaché.</Empty>}
  <button className="yfx-outline" onClick={m.refreshChildren}>Actualiser mes enfants</button>
 </Section>
 <nav className="yfx-school-tabs" aria-label="Démarches des familles">
  {[["schools","Établissements"],["children","Profils enfants"],["requests","Mes demandes"],["notifications","Actualités"]].map(([key,label])=>
   <button key={key} aria-pressed={m.discoveryTab===key} onClick={()=>m.setDiscoveryTab(key)}>{label}</button>)}
 </nav>
 <ParentDiscovery embedded key={m.discoveryTab} activeSection={m.discoveryTab}/>
 </>;
}
export default function YemFamillesFidele({m}) {
 const {screen,child,navTo,goDiscovery,accountView,onSchoolWorkspace,onLogout,user,family,familyLoading,familyError,refreshChildren}=m;
 return <div className="yfx-app">
   <h2 className="yfx-sr-only">Espace parents</h2>
   <Head m={m}/>
   <main className="yfx-main">
    {familyError&&<p className="yfx-alert" role="alert">{familyError}<button onClick={refreshChildren}>Réessayer</button></p>}
    {familyLoading&&<p role="status" className="yfx-card">Chargement de la famille…</p>}
    {child&&<ChildCard m={m} detailMode={screen==="school"&&m.schoolTab!=="grades"}
      showStats={screen==="home"} gradeStats={screen==="school"&&m.schoolTab==="grades"}/>}
    {!child&&!familyLoading&&!familyError&&screen!=="profile"&&<Section title="Rattacher un enfant à mon compte" icon="users">
      <p>Pour suivre sa scolarité, l'établissement doit vérifier votre qualité de responsable légal et associer le dossier de l'enfant à votre compte.</p>
      <p>Identifiant à communiquer au secrétariat : <strong>{family?.parent_username||user?.username||"—"}</strong></p>
      <div className="yfx-bottom-links"><button onClick={refreshChildren}>Actualiser mes enfants</button>
        <button onClick={()=>goDiscovery("children")}>Ajouter un enfant</button></div>
     </Section>}
    {m.enrollmentError&&<p className="yfx-alert" role="alert">{m.enrollmentError}</p>}
    {screen==="home"&&<Home m={m}/>}
    {screen==="payments"&&<Payments m={m}/>}
    {screen==="school"&&<School m={m}/>}
    {screen==="children"&&<Children m={m}/>}
    {screen==="profile"&&<Section title="Mon profil et ma sécurité" icon="user">
      {accountView||<p>{user?.username||family?.parent_username||"Compte parent"}</p>}
      {onSchoolWorkspace&&<button className="yfx-outline" onClick={onSchoolWorkspace}>Espace établissement</button>}
      <button className="yfx-outline" onClick={onLogout}>Se déconnecter</button>
    </Section>}
    <div className="yfx-install"><PWAInstall/></div>
   </main>
   <nav className="yfx-bottom-nav" aria-label="Navigation YEM Familles">
     {NAV.map(([key,label,icon])=><button type="button" key={key} aria-current={screen===key?"page":undefined}
       onClick={()=>navTo(key)}><Icon name={icon} size={25}/><span>{label}</span></button>)}
   </nav>
 </div>;
}
