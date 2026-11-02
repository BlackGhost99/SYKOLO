import React, { useMemo, useState } from "react";
import "./yem-desktop.css";

const GREEN = "#1f6b2f";

function Icon({ name, size = 20 }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };
  const paths = {
    home: <><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9 21v-7h6v7"/></>,
    users: <><circle cx="9" cy="8" r="3"/><path d="M3.5 20v-2.2c0-3 2.5-5.3 5.5-5.3s5.5 2.3 5.5 5.3V20"/><circle cx="17.3" cy="9" r="2.2"/><path d="M15.5 14c2.8-.5 5 1.4 5 4v2"/></>,
    adduser: <><circle cx="9" cy="8" r="3"/><path d="M3.5 20v-2.2c0-3 2.5-5.3 5.5-5.3s5.5 2.3 5.5 5.3V20"/><path d="M18 5v6M15 8h6"/></>,
    card: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18M7 14h4"/></>,
    alert: <><path d="M10.3 3.4 2.6 17a2 2 0 0 0 1.8 3h15.2a2 2 0 0 0 1.8-3L13.7 3.4a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></>,
    file: <><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5M9 12h6M9 16h6"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21h-4v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H3v-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6V3h4v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.1v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    school: <><path d="m3 10 9-5 9 5-9 5-9-5Z"/><path d="M6 12.5V18h12v-5.5M9 18v-4h6v4M3 21h18"/></>,
    search: <><circle cx="11" cy="11" r="6"/><path d="m16 16 5 5"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
    coins: <><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v4c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 10v4c0 1.7 3.1 3 7 3s7-1.3 7-3v-4M5 14v4c0 1.7 3.1 3 7 3s7-1.3 7-3v-4"/></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
    trend: <><path d="m3 17 5-5 4 4 8-9"/><path d="M15 7h5v5"/></>,
    plane: <><path d="m22 2-7 20-4-9-9-4 20-7Z"/><path d="M11 13 22 2"/></>,
    whatsapp: <><path d="M20 11.5a8 8 0 0 1-11.8 7l-4.2 1 1.1-4A8 8 0 1 1 20 11.5Z"/><path d="M8.5 8.5c.7 3 2 4.3 5 5"/></>,
    message: <><path d="M4 5h16v11H8l-4 3V5Z"/><path d="M8 9h.01M12 9h.01M16 9h.01"/></>,
    download: <><path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 21h16"/></>,
    printer: <><path d="M6 9V3h12v6"/><rect x="5" y="14" width="14" height="7"/><rect x="3" y="9" width="18" height="8" rx="2"/></>,
    sliders: <><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="10" cy="18" r="2"/></>,
    cap: <><path d="m2 10 10-5 10 5-10 5-10-5Z"/><path d="M6 12v5c3 2 9 2 12 0v-5"/></>,
    scale: <><path d="M12 3v18M6 6h12M5 6 2 12h6L5 6ZM19 6l-3 6h6l-3-6Z"/><path d="M8 21h8"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    dots: <><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none"/></>,
  };
  return <svg {...common}>{paths[name] || paths.file}</svg>;
}

const nav = [
  ["dashboard", "home", "Tableau de bord"],
  ["students", "users", "Élèves"],
  ["admissions", "adduser", "Admissions"],
  ["payments", "card", "Paiements"],
  ["arrears", "alert", "Impayés & relances"],
  ["bulletins", "file", "Bulletins"],
  ["absences", "calendar", "Absences"],
  ["parents", "users", "Parents"],
  ["staff", "users", "Personnel"],
  ["settings", "settings", "Paramètres"],
  ["branding", "school", "Identité visuelle"],
];

function Button({ children, primary = false, icon, className = "" }) {
  return <button type="button" className={`yd-btn ${primary ? "primary" : ""} ${className}`}>{icon && <Icon name={icon} size={18}/>}<span>{children}</span></button>;
}
function Status({ children, tone = "green" }) { return <span className={`yd-status ${tone}`}>{children}</span>; }
function Metric({ icon, label, value, footer, trend = "up" }) {
  return <div className="yd-metric"><Icon name={icon} size={28}/><div><div className="yd-metric-label">{label}</div><strong>{value}</strong><small className={trend === "up" ? "good" : trend === "down" ? "good" : "muted"}>{trend === "up" ? "↗" : trend === "down" ? "↘" : "="} &nbsp;{footer}</small></div></div>;
}
function Card({ title, icon, children, className = "", right }) {
  return <section className={`yd-card ${className}`}><div className="yd-card-title"><span>{icon && <Icon name={icon} size={22}/>}<b>{title}</b></span>{right}</div>{children}</section>;
}
function Donut({ centerTop, centerBottom, legend }) {
  return <div className="yd-donut-wrap"><div className="yd-donut"><div><strong>{centerTop}</strong><span>{centerBottom}</span></div></div><div className="yd-legend">{legend.map((x,i)=><div key={i}><i style={{opacity:1-i*.18}}/><span>{x}</span></div>)}</div></div>;
}
function PageHeader({ title, subtitle, badge, actions }) {
  return <><div className="yd-hero"><div><h1>{title}</h1><p>{subtitle}</p></div>{badge && <span className="yd-page-badge">{badge}</span>}<div className="yd-school-banner"/></div>{actions && <div className="yd-page-actions">{actions}</div>}</>;
}

function Dashboard() {
  return <>
    <PageHeader title="Tableau de bord fondateur" subtitle="Vue de pilotage de l’établissement — janvier 2027" badge="♛  Vue Fondateur" />
    <div className="yd-metrics five">
      <Metric icon="coins" label="Encaissé ce mois" value="8 950 000 FCFA" footer="+12,6 %   vs. déc. 2026"/>
      <Metric icon="file" label="Restant dû" value="3 240 000 FCFA" footer="−18,4 %   vs. déc. 2026" trend="down"/>
      <Metric icon="users" label="Élèves actifs" value="352" footer="+2,0 %   vs. déc. 2026"/>
      <Metric icon="alert" label="Familles en retard" value="41" footer="−6 familles   vs. déc. 2026" trend="down"/>
      <Metric icon="layers" label="Dépenses à approuver" value="3" footer="stable   vs. déc. 2026" trend="flat"/>
    </div>
    <div className="yd-grid dashboard-main">
      <Card title="Évolution des encaissements" icon="trend" className="chart-card"><p className="yd-muted">Montants encaissés (FCFA) sur les 6 derniers mois</p><svg className="yd-linechart" viewBox="0 0 600 190" preserveAspectRatio="none"><g className="grid"><line x1="45" y1="20" x2="45" y2="165"/><line x1="45" y1="165" x2="580" y2="165"/><line x1="45" y1="125" x2="580" y2="125"/><line x1="45" y1="85" x2="580" y2="85"/><line x1="45" y1="45" x2="580" y2="45"/></g><polyline points="70,140 155,120 240,90 330,78 430,68 555,36"/><g className="dots"><circle cx="70" cy="140" r="4"/><circle cx="155" cy="120" r="4"/><circle cx="240" cy="90" r="4"/><circle cx="330" cy="78" r="4"/><circle cx="430" cy="68" r="4"/><circle cx="555" cy="36" r="4"/></g><g className="labels"><text x="55" y="182">août 2026</text><text x="140" y="182">sept.</text><text x="225" y="182">oct.</text><text x="315" y="182">nov.</text><text x="420" y="182">déc.</text><text x="535" y="182">janv.</text></g></svg></Card>
      <Card title="Répartition des moyens de paiement" icon="card"><Donut centerTop="8 950 000" centerBottom="FCFA encaissés" legend={["Airtel Money : 42 %","Moov Money : 28 %","Espèces : 18 %","Virement : 12 %"]}/></Card>
      <Card title="Actions rapides" icon="trend" className="quick"><Button primary>Nouvel encaissement</Button><Button>Envoyer les relances</Button><Button>Valider les dépenses</Button><Button>Générer les bulletins</Button></Card>
    </div>
    <div className="yd-grid dashboard-bottom">
      <Card title="Retardataires prioritaires" icon="users"><SimpleTable headers={["#","Élève","Classe","Montant dû","Statut"]} rows={[["1","MOUKAGNI Loïc","3ᵉ A","125 000 FCFA",<Status>En retard</Status>],["2","NDONG Alida","4ᵉ B","95 000 FCFA",<Status>À relancer</Status>],["3","BITEGHE Mathis","5ᵉ A","80 000 FCFA",<Status>En retard</Status>],["4","OBAME Chloé","6ᵉ B","60 000 FCFA",<Status>À relancer</Status>],["5","MINKO Steeve","2nde A","45 000 FCFA",<Status>En retard</Status>]]}/></Card>
      <Card title="Dépenses en attente d’approbation" icon="layers"><SimpleTable headers={["#","Libellé","Montant","Date","Demandée par"]} rows={[["1","Achat de manuels scolaires (2ᵉ trimestre)","1 250 000 FCFA","12 janv. 2027","Responsable pédagogique"],["2","Entretien et maintenance des climatisations","480 000 FCFA","13 janv. 2027","Responsable logistique"],["3","Fournitures de bureau (secrétariat)","175 000 FCFA","14 janv. 2027","Secrétaire administrative"]]}/></Card>
    </div>
  </>;
}

function SimpleTable({ headers, rows, compact=false }) {
  return <div className="yd-table-wrap"><table className={compact ? "compact" : ""}><thead><tr>{headers.map((h,i)=><th key={i}>{h}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{r.map((c,j)=><td key={j}>{c}</td>)}</tr>)}</tbody></table></div>;
}

const studentRows = [
  ["1","NZE Aaron","6ᵉ B","NZE Sylvie","+241 77 43 21 08","Partiel",<Status tone="yellow">Partiel</Status>,"•••"],
  ["2","MBOUMBA Alicia","CE2 A","MBOUMBA Rodrigue","+241 66 28 54 17","À jour",<Status>À jour</Status>,"•••"],
  ["3","OBIANG Thiery","CM1","OBIANG Clarisse","+241 74 19 03 21","Impayé",<Status tone="red">Impayé</Status>,"•••"],
  ["4","MINKO Grace","3ᵉ A","MINKO Patrick","+241 77 91 44 06","Partiel",<Status tone="yellow">Partiel</Status>,"•••"],
  ["5","BIBANG Yann","CE2 A","BIBANG Estelle","+241 62 85 76 33","À jour",<Status>À jour</Status>,"•••"],
  ["6","NGUEMA Élodie","CM1","NGUEMA Joseph","+241 74 37 60 90","À jour",<Status>À jour</Status>,"•••"],
  ["7","EKOMIE David","6ᵉ B","EKOMIE Mireille","+241 66 14 88 27","Pré-inscrit",<Status tone="gray">Pré-inscrit</Status>,"•••"],
  ["8","ISSANI Maëlle","3ᵉ A","ISSANI Arnaud","+241 77 05 29 16","Impayé",<Status tone="red">Impayé</Status>,"•••"],
];
function Students() {
  return <><PageHeader title="Gestion des élèves" subtitle="Inscriptions, classes, responsables et suivi administratif"/>
    <div className="yd-toolbar"><div className="yd-search"><Icon name="search" size={18}/><input placeholder="Rechercher un élève (nom, prénom, matricule...)"/></div><select><option>Toutes les classes</option></select><select><option>Tous les statuts</option></select><Button primary icon="adduser">Nouvel élève</Button><Button icon="file">Importer Excel</Button></div>
    <div className="yd-metrics four"><Metric icon="users" label="Élèves actifs" value="352" footer="+2,0 %   vs. déc. 2026"/><Metric icon="cap" label="Nouveaux inscrits" value="24" footer="+9,1 %   vs. déc. 2026"/><Metric icon="alert" label="Dossiers incomplets" value="13" footer="−18,8 %   vs. déc. 2026" trend="down"/><Metric icon="whatsapp" label="Parents sans numéro WhatsApp" value="9" footer="−10,0 %   vs. déc. 2026" trend="down"/></div>
    <div className="yd-grid students-grid"><Card title="Liste des élèves (352)" icon="users"><SimpleTable compact headers={["#","Élève","Classe","Parent / Tuteur","Téléphone","Situation financière","Statut","Actions"]} rows={studentRows}/></Card><StudentPreview/></div>
  </>;
}
function StudentPreview(){return <Card title="Aperçu de l’élève" icon="users" className="student-preview"><div className="yd-person"><div className="yd-avatar">●</div><div><h3>NZE Aaron</h3><b>Classe : 6ᵉ B</b><span>Matricule : ELA000458</span></div></div><InfoRow k="Parent / Tuteur" v="NZE Sylvie"/><InfoRow k="Téléphone" v="+241 77 43 21 08" icon="whatsapp"/><InfoRow k="Total annuel" v="425 000 FCFA"/><InfoRow k="Montant payé" v="300 000 FCFA"/><InfoRow k="Reste à payer" v="125 000 FCFA" highlight/><Button primary>Voir la fiche</Button><Button>Encaisser</Button><Button icon="whatsapp">Contacter le parent</Button></Card>}
function InfoRow({k,v,highlight,icon}){return <div className={`yd-info-row ${highlight?"highlight":""}`}><span>{icon&&<Icon name={icon} size={16}/>} {k}</span><b>{v}</b></div>}

function Admissions(){
 const rows=[["1","MOUKAGNI Loïc","3ᵉ","M. Moukagni Eric","✓ Complet","✓ Confirmé",<Status>Paiement confirmé</Status>,"—","•••"],["2","NDONG Aïda","4ᵉ","Mme Ndong Clarisse","✓ Complet","✕ Non payé",<Status tone="yellow">En étude</Status>,"—","•••"],["3","BITEGHE Mathis","5ᵉ","M. Biteghe Patrick","✓ Complet","✕ Non payé",<Status>Admis sous réserve</Status>,"—","•••"],["4","OBAME Chloé","6ᵉ","Mme Obame Sandrine","✓ Complet","✓ Confirmé",<Status>Paiement confirmé</Status>,"Réservation expire le 17 janv. 2027","•••"],["5","MINKO Steeve","2nde","M. Minko Jean","⚠ Incomplet","✕ Non payé",<Status tone="yellow">En attente</Status>,"—","•••"],["6","BOVOUNGOU Eva","CP1","Mme Bovoungou Marie","✓ Complet","Exonération validée",<Status>Paiement confirmé</Status>,"—","•••"],["7","NZE Paul","CE2","M. Nze Armand","✓ Complet","✕ Non payé",<Status tone="red">Liste d’attente</Status>,"—","•••"],["8","MEBIYO Sara","6ᵉ","Mme Mebiyo Élise","✓ Complet","✓ Confirmé",<Status>Admis sous réserve</Status>,"—","•••"]];
 return <><PageHeader title="Admissions & préinscriptions" subtitle="Demandes en ligne, inscriptions au secrétariat, capacité d’accueil et paiement"/>
  <div className="yd-grid admissions-grid"><div><Card title="Capacité d’accueil" icon="layers" right={<span className="yd-link">Voir toutes les classes  ›</span>}><div className="capacity-row">{[["CP1 A","35 / 40","5 places restantes",87],["CE2 A","33 / 35","2 places restantes",94],["6ᵉ B","42 / 45","3 places restantes",93],["2nde A","38 / 40","2 places restantes",95]].map((x,i)=><div className="capacity" key={i}><span><Icon name="users" size={22}/><b>{x[0]}</b></span><strong>{x[1]}</strong><em>{x[2]}</em><div><i style={{width:x[3]+"%"}}/></div></div>)}</div></Card>
  <div className="yd-metrics four mini"><Metric icon="file" label="Demandes reçues" value="86" footer="+12,4 %   vs. déc. 2026"/><Metric icon="file" label="Dossiers complets" value="54" footer="+17,4 %   vs. déc. 2026"/><Metric icon="users" label="Places réservées" value="18" footer="+20,0 %   vs. déc. 2026"/><Metric icon="alert" label="Liste d’attente" value="7" footer="+0   vs. déc. 2026" trend="flat"/></div>
  <div className="yd-filter-row"><select><option>Année scolaire 2026 – 2027</option></select><select><option>Tous les niveaux</option></select><select><option>Toutes les classes</option></select><select><option>Tous les statuts</option></select></div>
  <Card title="Demandes d’admission" icon="users" right={<span className="yd-muted">86 demandes &nbsp; <Button>Exporter</Button></span>}><SimpleTable compact headers={["#","Candidat","Niveau demandé","Responsable","Dossier","Paiement","Statut","Réservation","Actions"]} rows={rows}/><div className="yd-note">ⓘ &nbsp; Une demande n’est confirmée qu’après validation administrative et paiement confirmé.</div></Card></div><AdmissionPreview/></div>
 </>;
}
function AdmissionPreview(){return <Card title="Aperçu du dossier" icon="file" className="admission-preview"><div className="yd-person photo"><div className="yd-child">👧🏾</div><div><h3>OBAME Chloé</h3><span>N° de demande : ADM-2027-0042</span><Status>Admis sous réserve</Status></div></div><InfoRow k="Classe demandée" v="6ᵉ"/><InfoRow k="Responsable" v="Mme Obame Sandrine"/><div className="yd-docs"><b>Pièces fournies (4/4)</b><span>☑ Acte de naissance</span><span>☑ 2 photos d’identité</span><span>☑ Dernier bulletin</span><span>☑ Pièce d’identité du responsable</span></div><InfoRow k="Montant inscription" v="50 000 FCFA"/><InfoRow k="Paiement" v="Non confirmé"/><Button primary>Valider le dossier</Button><Button>Envoyer le lien de paiement</Button><Button>Placer en liste d’attente</Button></Card>}

function Payments(){
 const rows=[["R-2027-001284","MOUKAGNI Loïc","3ᵉ A","125 000 FCFA","Airtel Money","10:24"],["R-2027-001285","NDONG Aïda","4ᵉ B","75 000 FCFA","Espèces","10:47"],["R-2027-001286","BITEGHE Mathis","5ᵉ A","150 000 FCFA","Moov Money","11:06"],["R-2027-001287","OBAME Chloé","6ᵉ B","100 000 FCFA","Virement","11:32"],["R-2027-001288","MINKO Steeve","2nde A","50 000 FCFA","Airtel Money","12:05"],["R-2027-001289","BEKA Élise","1ère C","75 000 FCFA","Espèces","12:28"]];
 return <><PageHeader title="Encaissements et caisse journalière" subtitle="Suivi des paiements, reçus et méthodes d’encaissement" badge="◉  Économe"/>
 <div className="yd-metrics four"><Metric icon="coins" label="Encaissé aujourd’hui" value="1 275 000 FCFA" footer="+8,6 %   vs. hier (1 174 000 FCFA)"/><Metric icon="file" label="Nombre de paiements" value="18" footer="+20,0 %   vs. hier (15)"/><Metric icon="coins" label="Espèces" value="390 000 FCFA" footer="30,6 %   du total" trend="flat"/><Metric icon="card" label="Mobile money" value="885 000 FCFA" footer="69,4 %   du total" trend="flat"/></div>
 <div className="yd-grid payments-grid"><PaymentForm/><div className="yd-stack"><Card title="Derniers paiements du jour" icon="file"><SimpleTable headers={["# Reçu","Élève","Classe","Montant","Mode","Heure"]} rows={rows}/></Card><Card title="Caisse du jour" icon="layers"><div className="cash-row"><Donut centerTop="1 275 000" centerBottom="FCFA encaissés" legend={["Airtel Money : 630 000 FCFA (49,4 %)","Moov Money : 255 000 FCFA (20,0 %)","Espèces : 390 000 FCFA (30,6 %)","Virement : 0 FCFA (0,0 %)"]}/><div className="cash-total"><span>Total encaissé</span><strong>1 275 000 FCFA</strong><Button primary>Clôturer la caisse</Button></div></div></Card></div></div>
 </>;
}
function PaymentForm(){return <Card title="Nouvel encaissement" icon="card" className="payment-form"><label>Élève *</label><select><option>NGOMA Junior — 5ᵉ A</option></select><label>Parent *</label><div className="yd-input-like">NGOMA Paul (Père)<span>☎ +241 77 23 45 67</span></div><label>Impayés sélectionnés *</label><div className="yd-debts"><span className="active">☑ Scolarité – 2ᵉ trimestre <b>75 000 FCFA</b></span><span>☐ Cantine – Janvier <b>20 000 FCFA</b></span><span>☐ Activités pédagogiques – 2ᵉ trimestre <b>15 000 FCFA</b></span></div><label>Mode de paiement *</label><div className="yd-paymodes"><Button primary>Airtel Money</Button><Button>Moov Money</Button><Button>Espèces</Button><Button>Virement</Button></div><label>Montant saisi *</label><div className="yd-amount"><div>75 000 <span>FCFA</span></div><span className="yd-toggle on"/> Paiement partiel</div><div className="yd-balance"><span>Solde après paiement</span><strong>50 000 FCFA</strong></div><Button primary className="wide">✓ &nbsp; Valider le paiement</Button></Card>}

function Arrears(){
 const rows=[["1","NZE Kévin","4ᵉ B","M. NZE Martin","12 janv. 2027","75 000 FCFA","11 janv. 2027","◉",<Status tone="red">En retard</Status>,"•••"],["2","MBOUI Emma","3ᵉ A","Mme MBOUI Clarisse","10 janv. 2027","125 000 FCFA","10 janv. 2027","▣",<Status tone="yellow">À relancer</Status>,"•••"],["3","ONDO Thierry","6ᵉ B","M. ONDO Jacques","14 janv. 2027","60 000 FCFA","09 janv. 2027","◉",<Status>Promesse de paiement</Status>,"•••"],["4","AYANG Lucie","5ᵉ A","Mme AYANG Patricia","13 janv. 2027","45 000 FCFA","—","—",<Status tone="gray">Sans réponse</Status>,"•••"],["5","MINKO Steve","2nde A","M. MINKO Daniel","12 janv. 2027","95 000 FCFA","11 janv. 2027","▣",<Status tone="red">En retard</Status>,"•••"],["6","NGOULOU Sara","3ᵉ B","Mme NGOULOU Émilie","15 janv. 2027","80 000 FCFA","13 janv. 2027","◉",<Status tone="yellow">À relancer</Status>,"•••"],["7","BITEGHE Liam","6ᵉ A","M. BITEGHE Alain","12 janv. 2027","50 000 FCFA","10 janv. 2027","▣",<Status tone="gray">Sans réponse</Status>,"•••"],["8","OBAME Chloé","5ᵉ B","Mme OBAME Sandra","14 janv. 2027","110 000 FCFA","12 janv. 2027","◉",<Status>Promesse de paiement</Status>,"•••"]];
 return <><PageHeader title="Impayés & relances" subtitle="Suivi des échéances, retards et messages aux familles" actions={<><Button primary icon="plane">Envoyer les relances</Button><Button icon="whatsapp">WhatsApp</Button><Button icon="message">SMS</Button><Button icon="download">Exporter</Button></>}/>
 <div className="yd-grid arrears-layout"><div><div className="yd-metrics four"><Metric icon="coins" label="Total restant dû" value="3 240 000 FCFA" footer="−18,4 %   vs. déc. 2026" trend="down"/><Metric icon="alert" label="Familles en retard" value="41" footer="−6 familles   vs. déc. 2026" trend="down"/><Metric icon="plane" label="Relances envoyées aujourd’hui" value="12" footer="+20,0 %   vs. hier"/><Metric icon="users" label="Promesses de paiement" value="7" footer="+2   vs. déc. 2026"/></div><Card title="Liste des familles en impayé (41)" icon="users"><SimpleTable compact headers={["","Élève","Classe","Responsable","Échéance","Montant dû","Dernière relance","Canal","Statut","Actions"]} rows={rows}/></Card></div><div className="yd-stack"><Card title="Aperçu du message" icon="message"><div className="yd-channel-tabs"><span>◉ WhatsApp</span><span>▣ SMS</span><span>✉ Email</span></div><div className="yd-message-preview">Bonjour M. NZE Martin,<br/><br/>Nous vous rappelons que les frais de scolarité de votre enfant <b>NZE Kévin (4ᵉ B)</b> s’élèvent à <b>75 000 FCFA</b>, échus le <b>12 janv. 2027</b>.<br/><br/>Nous vous invitons à régulariser cette situation dans les meilleurs délais.<br/><br/>L’École Privée Les Amandiers vous remercie pour votre diligence.<small>10:24 ✓✓</small></div></Card><Card title="Répartition des impayés par classe" icon="trend"><div className="bar-list">{[["3ᵉ A",8],["4ᵉ B",7],["5ᵉ A",6],["6ᵉ B",5],["3ᵉ B",4],["2nde A",4],["6ᵉ A",3],["5ᵉ B",3]].map((x,i)=><div key={i}><span>{x[0]}</span><i style={{width:(x[1]*11)+"%"}}/><b>{x[1]} familles</b></div>)}</div></Card></div></div>
 </>;
}

function BulletinConfig(){
 return <><PageHeader title="Paramétrage pédagogique et bulletins" subtitle="Barèmes, types d’évaluations, modèles de bulletins et règles de publication"/>
 <div className="yd-filter-row wide"><select><option>Année scolaire : 2026 – 2027</option></select><select><option>Cycle : Collège</option></select><select><option>Niveau : 5ᵉ</option></select><select><option>Classe : 5ᵉ A</option></select></div>
 <div className="yd-metrics three"><Metric icon="sliders" label="Systèmes de notation actifs" value="4" footer="" trend="flat"/><Metric icon="file" label="Modèles de bulletins" value="3" footer="" trend="flat"/><Metric icon="layers" label="Configurations publiées" value="12" footer="" trend="flat"/></div>
 <div className="yd-grid config-grid"><Card title="Systèmes de notation" icon="scale"><p className="yd-muted">Choisissez et paramétrez les systèmes de notation disponibles pour ce cycle / niveau.</p><div className="notation-list">{[["Sur 20","Barème : 0 à 20 · Pas : 0,25",true],["Sur 10","Barème : 0 à 10 · Pas : 0,5",true],["Sur 100","Barème : 0 à 100 · Pas : 1",true],["Pourcentage","Barème : 0 % à 100 % · Pas : 1 %",true],["Lettres (A+, A, B, C)","Échelle : A+, A, B, C, D, E",true],["Mentions (Excellent, Très bien, Bien)","Échelle : Excellent, Très bien, Bien, Assez bien, Passable, Insuffisant",true],["Compétences","Niveaux : Maîtrisée, En cours, Non maîtrisée",false]].map((x,i)=><div key={i}><span>{x[2]?"☑":"☐"}</span><div><b>{x[0]}</b><small>{x[1]}</small></div><Button>⚙ Configurer</Button></div>)}</div><div className="yd-note">ⓘ &nbsp; <b>Paramétrable et flexible :</b> activez les systèmes utiles, modifiez les barèmes, les pas, les échelles et les mentions selon vos besoins.</div></Card>
 <div className="yd-stack"><Card title="Types d’évaluations et pondérations" icon="layers"><p className="yd-muted">Définissez les types d’évaluations et leurs pondérations dans la moyenne.</p><SimpleTable headers={["","Type d’évaluation","Pondération","",""]} rows={[["⋮⋮","Devoir de classe","30 %","✎","⌫"],["⋮⋮","Interrogation","20 %","✎","⌫"],["⋮⋮","Composition","50 %","✎","⌫"]]}/><Button className="center">＋ Ajouter un type</Button></Card><Card title="Règles de calcul" icon="card"><div className="rule-list"><InfoRow k="Arrondi des moyennes" v="À 2 décimales"/><InfoRow k="Classement des élèves" v="🟢 Activé"/><InfoRow k="Calcul par coefficient" v="🟢 Activé"/><InfoRow k="Notes absentes" v="Non comptées"/></div></Card></div>
 <Card title="Modèle de bulletin" icon="file" className="bulletin-model"><p className="yd-muted">Configurez le modèle de bulletin et les sections à inclure.</p><div className="model-grid"><div className="section-checks"><b>Sections à inclure</b>{["Photo de l’élève","Rang","Conduite","Absences","Signatures","QR code","Appréciation générale"].map(x=><span key={x}>☑ {x}</span>)}</div><MiniBulletin/></div><div className="yd-note">ⓘ &nbsp; <b>Modèles personnalisables :</b> choisissez les informations, leur ordre et la présentation.</div></Card></div>
 <div className="yd-footer-actions"><Button>▦ &nbsp; Tester le calcul</Button><Button>▤ &nbsp; Enregistrer en brouillon</Button><Button primary icon="plane">Publier la configuration</Button></div>
 </>;
}
function MiniBulletin(){return <div className="mini-bulletin"><div className="mini-head"><span>▰ École Privée<br/>Les Amandiers</span><b>Bulletin de notes</b></div><div className="mini-person">● <span>Nom : ______<br/>Classe : 5ᵉ A<br/>Rang : 3ᵉ / 28</span></div><div className="mini-table"><b>Matière</b><b>Moy.</b><b>Appréciation</b>{Array.from({length:6}).map((_,i)=><React.Fragment key={i}><i/><i/><i/></React.Fragment>)}</div><div className="mini-lines">Appréciation générale<br/>──────────<br/>──────────────</div><div className="mini-foot">▦ &nbsp;&nbsp;&nbsp; Signatures</div></div>}

function Bulletins(){
 const rows=[["1","MOUKAGNI Loïc","15,62 / 20","1er","Très bien","0 jour",<Status>À jour</Status>],["2","BITEGHE Mathis","14,90 / 20","2e","Très bien","1 jour",<Status>À jour</Status>],["3","OBAME Chloé","14,86 / 20","3e","Bien","0 jour",<Status>À jour</Status>],["4","MINKO Steeve","14,20 / 20","4e","Bien","2 jours",<Status>À jour</Status>],["5","NDONG Eléonore","13,84 / 20","5e","Très bien","2 jours",<Status>À jour</Status>],["6","OKOUMBA Daniel","13,56 / 20","6e","Bien","1 jour",<Status>À jour</Status>],["7","ESSONO Aïcha","13,20 / 20","7e","Bien","3 jours",<Status tone="yellow">En attente</Status>],["8","NGUEMA Paul","12,96 / 20","8e","Assez bien","2 jours",<Status>À jour</Status>]];
 return <><PageHeader title="Bulletins et résultats scolaires" subtitle="Préparation, contrôle et génération des bulletins du trimestre"/>
 <div className="yd-toolbar bullet"><select><option>Classe : 6ᵉ B</option></select><select><option>Période : 1er trimestre</option></select><span/><Button primary icon="printer">Générer les bulletins</Button><Button icon="download">Exporter PDF</Button></div>
 <div className="yd-metrics four"><Metric icon="users" label="Élèves évalués" value="35" footer="+0   vs. période précédente"/><Metric icon="file" label="Bulletins générés" value="32" footer="+6   vs. période précédente"/><Metric icon="alert" label="Bulletins en attente" value="3" footer="−6   vs. période précédente" trend="down"/><Metric icon="coins" label="Paiements à jour" value="29" footer="+4   vs. période précédente"/></div>
 <div className="yd-grid bulletins-grid"><Card title="Élèves de la classe 6ᵉ B (35)" icon="users"><div className="yd-search full"><Icon name="search" size={18}/><input placeholder="Rechercher un élève..."/></div><SimpleTable compact headers={["#","Élève","Moyenne générale","Rang","Conduite","Absences","Paiement"]} rows={rows}/></Card><ReportCard/></div>
 </>;
}
function ReportCard(){return <div className="report-sheet"><div className="report-brand"><div><span className="report-book">▰</span><b>École Privée<br/>Les Amandiers</b><small>Libreville – Gabon</small></div><div><h2>BULLETIN DE NOTES</h2><span>1er trimestre – Année scolaire 2026 – 2027</span></div></div><div className="report-person"><div>●</div><b>Élève : NDONG Eléonore<br/>Classe : 6ᵉ B<br/>Matricule : 6B-023</b><span>Effectif de la classe : 35<br/>Période : 1er trimestre<br/>Date d’édition : 12 janv. 2027</span></div><SimpleTable headers={["Matière","Note / 20","Moy. de classe / 20","Appréciation"]} rows={[["Français","14,00","12,36","Bien"],["Mathématiques","13,50","11,72","Bien"],["Anglais","15,00","13,08","Très bien"],["Histoire–Géographie","12,50","11,64","Assez bien"],["SVT","14,00","12,90","Bien"],["Physique–Chimie","13,00","12,15","Bien"],["ECM","16,00","14,02","Très bien"],["Éducation Artistique","15,50","14,33","Très bien"],["EPS","17,00","15,24","Très bien"]]}/><div className="report-summary"><div><span>Moyenne générale</span><strong>13,84 / 20</strong></div><div><span>Rang</span><strong>5ᵉ / 35</strong></div><div><span>Conduite</span><Status>Très bien</Status></div><div><span>Absences</span><strong>2 jours</strong></div></div><div className="report-foot"><div className="qr">▦▦<br/>▦▦</div><div><b>Authenticité du bulletin</b><span>Scannez ce QR code pour vérifier<br/>la conformité du document.</span></div><div><b>Le Professeur principal</b><em>Jungo</em></div><div><b>La Directrice</b><em>Jrnn</em></div></div></div>}

function Placeholder({title}){return <><PageHeader title={title} subtitle="Module conservé dans la navigation PC"/><Card title={title} icon="file"><p className="yd-muted">Cet écran n’était pas inclus dans les maquettes PC de référence fournies. Il reste volontairement neutre pour ne rien réinventer.</p></Card></>}

const BRAND_KEY = "yem.preview.branding.v1";
const defaultBrand = {name:"École Privée Les Amandiers",color:"#1f6b2f",logo:"",banner:""};
function getBrand(){
  try {
    const saved = JSON.parse(window.localStorage.getItem(BRAND_KEY) || "null");
    if (!saved || typeof saved !== "object") return defaultBrand;
    const color = /^#[0-9a-fA-F]{6}$/.test(saved.color || "") ? saved.color : defaultBrand.color;
    return {...defaultBrand,name:String(saved.name||defaultBrand.name).slice(0,180),color,
      logo:typeof saved.logo==="string"&&saved.logo.startsWith("data:image/")?saved.logo:"",
      banner:typeof saved.banner==="string"&&saved.banner.startsWith("data:image/")?saved.banner:""};
  } catch {return defaultBrand;}
}
function BrandingEditor({brand,onChange}){
 const [error,setError]=useState("");
 function upload(field,file){
   setError("");
   if(!file)return;
   if(!["image/png","image/jpeg","image/webp"].includes(file.type)){setError("Formats autorisés : PNG, JPEG, WebP.");return;}
   if(file.size>900000){setError("Image trop volumineuse (900 Ko maximum pour cet aperçu).");return;}
   const reader=new FileReader();
   reader.onload=()=>onChange({...brand,[field]:String(reader.result)});
   reader.onerror=()=>setError("Lecture du fichier impossible.");
   reader.readAsDataURL(file);
 }
 return <><PageHeader title="Identité visuelle de l’établissement" subtitle="Personnalisation des pages de l’école et de son personnel — aperçu local"/>
 <div className="yd-branding-grid">
 <Card title="Personnalisation" icon="settings"><p className="yd-muted">Ces réglages concernent uniquement cet aperçu sur ce navigateur. Ils ne sont pas encore enregistrés dans les comptes de l’établissement.</p>
 <label className="yd-brand-field">Nom de l’établissement<input maxLength={180} value={brand.name} onChange={e=>onChange({...brand,name:e.target.value})}/></label>
 <label className="yd-brand-field">Couleur de l’établissement<input type="color" value={brand.color} onChange={e=>onChange({...brand,color:e.target.value})}/></label>
 <label className="yd-brand-field">Logo de l’établissement (PNG, JPG ou WebP)<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>upload("logo",e.target.files?.[0])}/></label>
 <label className="yd-brand-field">Bannière de l’établissement (PNG, JPG ou WebP)<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>upload("banner",e.target.files?.[0])}/></label>
 {error&&<p role="alert" style={{color:"#a02626"}}>{error}</p>}
 <button type="button" className="yd-btn" onClick={()=>onChange(defaultBrand)}>Réinitialiser cet aperçu</button>
 </Card>
 <Card title="Aperçu de l’identité" icon="school"><div className="yd-brand-preview" style={{borderColor:brand.color}}>{brand.banner&&<img className="yd-brand-banner-preview" src={brand.banner} alt="Bannière de l’établissement"/>}
 <div className="yd-brand-preview-text">{brand.logo&&<img src={brand.logo} alt="Logo de l’établissement"/>}<strong>{brand.name||"Votre établissement"}</strong></div></div>
 <p className="yd-muted">Le logo YEM et la mention « Développé par BWETEK Informatyk » restent présents, quelle que soit la couleur choisie.</p>
 </Card></div></>;
}
export default function YemDesktop(){
 const [page,setPage]=useState("dashboard");
 const [brand,setBrand]=useState(getBrand);
 const updateBrand=next=>{setBrand(next);try{window.localStorage.setItem(BRAND_KEY,JSON.stringify(next));}catch{/* aperçu non persistant si stockage plein */}};
 const active = page === "bulletinConfig" ? "bulletins" : page;
 const content = useMemo(()=>({dashboard:<Dashboard/>,students:<Students/>,admissions:<Admissions/>,payments:<Payments/>,arrears:<Arrears/>,bulletins:<Bulletins/>,bulletinConfig:<BulletinConfig/>,absences:<Placeholder title="Absences"/>,parents:<Placeholder title="Parents"/>,staff:<Placeholder title="Personnel"/>,branding:<BrandingEditor brand={brand} onChange={updateBrand}/>})[page],[page]);
 return <div className="yd-app" style={{"--school-primary":brand.color}}><header className="yd-topbar"><div className="yd-logo" aria-label="YEM – Gestion scolaire et universitaire"/><div className="yd-school-select">{brand.logo?<img className="yd-school-logo" src={brand.logo} alt="Logo de l’établissement"/>:<Icon name="school" size={20}/>}<b>{brand.name}</b><span>⌄</span></div><div className="yd-global-search"><Icon name="search" size={18}/><span>Rechercher un élève, une famille, un paiement...</span></div><div className="yd-bell"><Icon name="bell" size={22}/><i>3</i></div><div className="yd-user"><div>●</div><b>Mme la Directrice</b><span>⌄</span></div></header>
 <aside className="yd-sidebar">{nav.map(([id,icon,label])=><button key={id} className={active===id?"active":""} onClick={()=>setPage(id==="settings"?"bulletinConfig":id)}><Icon name={icon} size={22}/><span>{label}</span></button>)}</aside>
 <main className="yd-content"><style>{brand.banner?`.yd-school-banner{background-image:linear-gradient(90deg,#fff0,#ffffff55),url("${brand.banner}")}`:""}</style>{content}<footer className="yd-brand-footer"><span>YEM — Gestion scolaire</span><span>Développé par <strong>BWETEK Informatyk</strong></span></footer></main></div>;
}
