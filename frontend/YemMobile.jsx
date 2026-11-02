import React, { useEffect, useState } from "react";
import { Icon, BookMark, YemLogo, QrCode, Button } from "./yem-ui.jsx";
import banner from "./assets/yem-school-banner.jpg";

/* Expérience mobile de référence : docs/maquettes/08-mobile-parent-appel-recu.jpg. Données fictives. */

export function useIsMobile(breakpoint = 760) {
  const query = `(max-width: ${breakpoint}px)`;
  const get = () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(query).matches;
  const [mobile, setMobile] = useState(get);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return undefined;
    const mq = window.matchMedia(query);
    const on = () => setMobile(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, [query]);
  return mobile;
}

function MobileHeader({ onMenu }) {
  return <header className="ym-header">
    <div className="ym-logo"><BookMark size={42}/><div><b>YEM</b><span>Gestion scolaire &amp; universitaire</span></div></div>
    <span className="ym-bell" aria-label="3 notifications"><Icon name="bell" size={26} strokeWidth={1.6}/><i>3</i></span>
    <button type="button" className="ym-burger" aria-label="Menu" onClick={onMenu}><Icon name="menu" size={28} strokeWidth={1.8}/></button>
  </header>;
}
function Tabs({ tabs, value, onChange }) {
  return <nav className="ym-tabs" aria-label="Sections">{tabs.map(([key, icon, label]) => <button type="button" key={key} className={value === key ? "active" : ""} aria-current={value === key ? "page" : undefined} onClick={() => onChange(key)}><Icon name={icon} size={20}/>{label}</button>)}</nav>;
}

function ParentHome({ go }) {
  return <>
    <div className="ym-title"><h1>Espace parent</h1><p>Suivi de la scolarité de votre enfant</p></div>
    <button type="button" className="ym-child"><span className="ym-av"><Icon name="user" size={26} strokeWidth={0} className="filled"/></span><b>MINTSA Grâce — 6<sup>e</sup> B</b><Icon name="chevron" size={20}/></button>
    <div className="ym-tile pay"><Icon name="coins" size={30} strokeWidth={1.5}/><div><span>Prochain paiement</span><strong>75 000 FCFA</strong></div><div className="right"><em>Échéance</em><small>12 janv. 2027</small></div></div>
    <button type="button" className="ym-tile" onClick={() => go("bulletins")}><Icon name="file" size={28} strokeWidth={1.5}/><div><span>Dernier bulletin</span><strong>Disponible</strong></div><Icon name="chevronright" size={22}/></button>
    <button type="button" className="ym-tile"><Icon name="alert" size={28} strokeWidth={1.5}/><div><span>Absences</span><strong>2 <small>(ce mois-ci)</small></strong></div><Icon name="chevronright" size={22}/></button>
    <div className="ym-actions"><Button primary icon="card">Payer</Button><Button icon="download" onClick={() => go("receipt")}>Télécharger le reçu</Button><Button icon="file" onClick={() => go("bulletins")}>Voir le bulletin</Button></div>
  </>;
}

const CALL = [["ABOGA Samuel", 0], ["BIKOE Emma", 0], ["NDONG Kevin", 1], ["OBAME Lucie", 0], ["MINKO David", 2], ["NZE Carla", 0]];
function TeacherCall() {
  const [marks, setMarks] = useState(CALL.map(c => c[1]));
  const [done, setDone] = useState(false);
  return <>
    <div className="ym-title"><h1>Appel enseignant</h1><p>Enregistrer la présence des élèves</p></div>
    <div className="ym-filters"><div className="ym-select"><Icon name="users" size={20}/><b>CM1 A</b><Icon name="chevron" size={18}/></div><div className="ym-select"><Icon name="calendar" size={20}/><span>12 janv. 2027</span></div></div>
    <table className="ym-call"><thead><tr><th>#</th><th>Élève</th><th>Présent</th><th>Absent</th><th>Retard</th></tr></thead>
      <tbody>{CALL.map(([name], i) => <tr key={name}><td>{i + 1}</td><td>{name}</td>{[0, 1, 2].map(k => <td key={k}><button type="button" className={`ym-radio ${marks[i] === k ? "on" : ""}`} aria-label={`${name} : ${["présent", "absent", "retard"][k]}`} aria-pressed={marks[i] === k} onClick={() => { setDone(false); setMarks(m => m.map((v, j) => j === i ? k : v)); }}/></td>)}</tr>)}</tbody></table>
    <div className="ym-spacer"/>
    {done && <p className="ym-ok" role="status">Appel enregistré pour la démonstration.</p>}
    <Button primary icon="check" className="ym-wide" onClick={() => setDone(true)}>Valider l’appel</Button>
  </>;
}

function Receipt({ back }) {
  return <>
    <div className="ym-title row"><button type="button" className="ym-back" aria-label="Retour" onClick={back}><Icon name="back" size={24}/></button><h1>Reçu de paiement</h1></div>
    <article className="ym-receipt">
      <img src={banner} alt="École Privée Les Amandiers" className="ym-banner"/>
      <h2>Reçu de paiement</h2><p className="ym-num">N° REÇU : YEM-2027-000458</p>
      <dl>{[["Élève", "MINTSA Grâce"], ["Classe", <>6<sup>e</sup> B</>], ["Montant payé", <span className="ym-paid">75 000 FCFA</span>], ["Mode de paiement", "Airtel Money"], ["Date de paiement", "12 janv. 2027"], ["Solde restant", "50 000 FCFA"]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      <div className="ym-qr"><QrCode size={104} seed={11}/></div>
    </article>
  </>;
}
function Bulletins() {
  return <><div className="ym-title"><h1>Bulletins</h1><p>Résultats publiés par l’établissement</p></div>
    {[["1er trimestre 2026 – 2027", "13,84 / 20 · Rang 5e / 35"], ["3e trimestre 2025 – 2026", "13,10 / 20 · Rang 7e / 34"]].map(([t, s]) => <button type="button" key={t} className="ym-tile"><Icon name="file" size={28} strokeWidth={1.5}/><div><span>{t}</span><strong>{s}</strong></div><Icon name="download" size={22}/></button>)}</>;
}
function Simple({ title, sub }) { return <div className="ym-title"><h1>{title}</h1><p>{sub}</p></div>; }

const SPACES = {
  parent: { label: "Espace parent", tabs: [["home", "home", "Accueil"], ["payments", "card", "Paiements"], ["bulletins", "file", "Bulletins"]] },
  teacher: { label: "Appel enseignant", tabs: [["call", "users", "Appel"], ["notes", "barchart", "Notes"], ["bulletins", "file", "Bulletins"]] },
  cashier: { label: "Reçu de paiement", tabs: [["payments", "card", "Paiements"], ["receipts", "file", "Reçus"], ["history", "clock", "Historique"]] },
};

export function MobileScreen({ space: initialSpace = "parent", allowSwitch = true }) {
  const [space, setSpace] = useState(initialSpace);
  const [tab, setTab] = useState(SPACES[initialSpace].tabs[0][0]);
  const [view, setView] = useState(initialSpace === "cashier" ? "receipt" : null);
  const [menu, setMenu] = useState(false);
  const def = SPACES[space];
  function choose(s) { setSpace(s); setTab(SPACES[s].tabs[0][0]); setView(s === "cashier" ? "receipt" : null); setMenu(false); }
  function go(target) { if (target === "receipt") { setSpace("cashier"); setTab("payments"); setView("receipt"); } else { setTab(target); setView(null); } }
  let body;
  if (view === "receipt") body = <Receipt back={() => choose("parent")}/>;
  else if (space === "parent") body = tab === "home" ? <ParentHome go={go}/> : tab === "bulletins" ? <Bulletins/> : <Simple title="Paiements" sub="Échéances et paiements de votre enfant"/>;
  else if (space === "teacher") body = tab === "call" ? <TeacherCall/> : tab === "bulletins" ? <Bulletins/> : <Simple title="Notes" sub="Saisie des notes de vos classes"/>;
  else body = tab === "receipts" ? <Simple title="Reçus" sub="Reçus émis aujourd’hui"/> : tab === "history" ? <Simple title="Historique" sub="Paiements des 30 derniers jours"/> : <Receipt back={() => choose("parent")}/>;
  return <div className="ym-screen">
    <MobileHeader onMenu={() => allowSwitch && setMenu(m => !m)}/>
    {menu && <div className="ym-menu" role="menu">{Object.entries(SPACES).map(([k, v]) => <button type="button" role="menuitem" key={k} className={space === k ? "active" : ""} onClick={() => choose(k)}>{v.label}</button>)}</div>}
    <Tabs tabs={def.tabs} value={tab} onChange={t => { setTab(t); setView(space === "cashier" && t === "payments" ? "receipt" : null); }}/>
    <main className="ym-body">{body}</main>
  </div>;
}

export function MobileApp() { return <div className="ym-app"><MobileScreen/></div>; }

function Phone({ children }) {
  return <div className="ym-phone"><div className="ym-status"><b>09:41</b><span className="ym-notch"/><span className="ym-icons"><i/><i/><i/><i/><em/></span></div>{children}</div>;
}
export function MobileShowcase() {
  return <section className="ym-showcase" aria-label="Expérience mobile">
    <div className="ym-show-head"><YemLogo/><div className="ym-show-sep"/><div><h1>YEM — Expérience mobile</h1><p>Parents, enseignants et opérations rapides</p></div></div>
    <div className="ym-phones">
      {[["parent", "users", "Espace parent"], ["teacher", "cap", "Appel enseignant"], ["cashier", "receipt", "Reçu de paiement"]].map(([s, ic, l]) => <figure key={s}><Phone><MobileScreen space={s} allowSwitch={false}/></Phone><figcaption><Icon name={ic} size={30}/>{l}</figcaption></figure>)}
    </div>
  </section>;
}
