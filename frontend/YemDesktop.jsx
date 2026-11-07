import React, { useEffect, useMemo, useState } from "react";
import { MobileApp, MobileShowcase, useIsMobile } from "./YemMobile.jsx";
import { Icon, Button, Status, Metric, Card, Table, InfoRow, Note, SelectBox, SearchBox, Toggle, Check, Donut, LineChart, BarList, PageHeader, QrCode, Signature, Shell, NAV, BrandContext } from "./yem-ui.jsx";
import admissionPhoto from "./assets/yem-admission-photo.jpg";
import "./yem-desktop.css";

/* Maquettes PC de référence : docs/maquettes/01 à 07. Données fictives de démonstration. */

const Dots = () => <button type="button" className="yd-dots" aria-label="Actions"><Icon name="dots" size={22}/></button>;
const sup = (n, s) => <>{n}<sup>{s}</sup></>;
const cls = (n, s, l) => <>{n}<sup>{s}</sup>{l ? " " + l : ""}</>;

function Dashboard() {
  return <>
    <PageHeader title="Tableau de bord fondateur" subtitle="Vue de pilotage de l’établissement — janvier 2027" badge="Vue Fondateur" badgeIcon="crown"/>
    <div className="yd-metrics five">
      <Metric icon="coins" label="Encaissé ce mois" value="8 950 000 FCFA" trend="up" trendValue="+12,6 %" trendLabel="vs. déc. 2026"/>
      <Metric icon="file" label="Restant dû" value="3 240 000 FCFA" trend="down" trendValue="−18,4 %" trendLabel="vs. déc. 2026"/>
      <Metric icon="users" label="Élèves actifs" value="352" trend="up" trendValue="+2,0 %" trendLabel="vs. déc. 2026"/>
      <Metric icon="alert" label="Familles en retard" value="41" trend="down" trendValue="−6 familles" trendLabel="vs. déc. 2026"/>
      <Metric icon="layers" label="Dépenses à approuver" value="3" trend="flat" trendLabel="stable  vs. déc. 2026"/>
    </div>
    <div className="yd-grid dash-main">
      <Card title="Évolution des encaissements" icon="barchart" subtitle="Montants encaissés (FCFA) sur les 6 derniers mois">
        <LineChart points={[5980000, 6520000, 7210000, 7640000, 7950000, 8950000]} labels={["août 2026", "sept. 2026", "oct. 2026", "nov. 2026", "déc. 2026", "janv. 2027"]}/>
      </Card>
      <Card title="Répartition des moyens de paiement" icon="wallet">
        <Donut size={160} values={[42, 28, 18, 12]} centerTop="8 950 000" centerBottom={"FCFA\nencaissés"} legend={[["Airtel Money : 42 %", "(3 759 000 FCFA)"], ["Moov Money : 28 %", "(2 506 000 FCFA)"], ["Espèces : 18 %", "(1 611 000 FCFA)"], ["Virement : 12 %", "(1 074 000 FCFA)"]]}/>
      </Card>
      <Card title="Actions rapides" icon="bolt" className="quick">
        <Button primary icon="card">Nouvel encaissement</Button>
        <Button icon="mail">Envoyer les relances</Button>
        <Button icon="checkcircle">Valider les dépenses</Button>
        <Button icon="file">Générer les bulletins</Button>
      </Card>
    </div>
    <div className="yd-grid dash-bottom">
      <Card title="Retardataires prioritaires" icon="users">
        <Table align={{ 1: "nowrap", 3: "nowrap" }} headers={["#", "Élève", "Classe", "Montant dû", "Statut"]} rows={[
          ["1", "MOUKAGNI Loïc", cls(3, "e", "A"), "125 000 FCFA", <Status>En retard</Status>],
          ["2", "NDONG Alida", cls(4, "e", "B"), "95 000 FCFA", <Status>À relancer</Status>],
          ["3", "BITEGHE Mathis", cls(5, "e", "A"), "80 000 FCFA", <Status>En retard</Status>],
          ["4", "OBAME Chloé", cls(6, "e", "B"), "60 000 FCFA", <Status>À relancer</Status>],
          ["5", "MINKO Steeve", cls(2, "nde", "A"), "45 000 FCFA", <Status>En retard</Status>]]}/>
      </Card>
      <Card title="Dépenses en attente d’approbation" icon="layers">
        <Table align={{ 2: "nowrap", 3: "nowrap" }} headers={["#", "Libellé", "Montant", "Date", "Demandée par"]} rows={[
          ["1", <>Achat de manuels scolaires<br/>(2<sup>e</sup> trimestre)</>, "1 250 000 FCFA", "12 janv. 2027", <>Responsable<br/>pédagogique</>],
          ["2", <>Entretien et maintenance<br/>des climatisations</>, "480 000 FCFA", "13 janv. 2027", <>Responsable<br/>logistique</>],
          ["3", <>Fournitures de bureau<br/>(secrétariat)</>, "175 000 FCFA", "14 janv. 2027", <>Secrétaire<br/>administrative</>]]}/>
      </Card>
    </div>
  </>;
}

const STUDENTS = [
  ["NZE Aaron", cls(6, "e", "B"), "NZE Sylvie", "+241 77 43 21 08", "Partiel", "yellow", "Partiel"],
  ["MBOUMBA Alicia", "CE2 A", "MBOUMBA Rodrigue", "+241 66 28 54 17", "À jour", "green", "À jour"],
  ["OBIANG Thiery", "CM1", "OBIANG Clarisse", "+241 74 19 03 21", "Impayé", "red", "Impayé"],
  ["MINKO Grace", cls(3, "e", "A"), "MINKO Patrick", "+241 77 91 44 06", "Partiel", "yellow", "Partiel"],
  ["BIBANG Yann", "CE2 A", "BIBANG Estelle", "+241 62 85 76 33", "À jour", "green", "À jour"],
  ["NGUEMA Élodie", "CM1", "NGUEMA Joseph", "+241 74 37 60 90", "À jour", "green", "À jour"],
  ["EKOMIE David", cls(6, "e", "B"), "EKOMIE Mireille", "+241 66 14 88 27", "Pré-inscrit", "gray", "Pré-inscrit"],
  ["ISSANI Maëlle", cls(3, "e", "A"), "ISSANI Arnaud", "+241 77 05 29 16", "Impayé", "red", "Impayé"],
];
function Students() {
  const [selected, setSelected] = useState(0);
  const [query, setQuery] = useState("");
  const visible = STUDENTS.map((s, i) => [s, i]).filter(([s]) => (s[0] + s[2]).toLowerCase().includes(query.toLowerCase()));
  return <>
    <PageHeader title="Gestion des élèves" subtitle="Inscriptions, classes, responsables et suivi administratif"/>
    <div className="yd-toolbar students">
      <SearchBox placeholder="Rechercher un élève (nom, prénom, matricule...)" value={query} onChange={e => setQuery(e.target.value)}/>
      <SelectBox value="Toutes les classes" className="plain"/>
      <SelectBox value="Tous les statuts" className="plain"/>
      <Button primary icon="adduser">Nouvel élève</Button>
      <Button icon="excel">Importer Excel</Button>
    </div>
    <div className="yd-metrics four">
      <Metric icon="users" label="Élèves actifs" value="352" trend="up" trendValue="+2,0 %" trendLabel="vs. déc. 2026"/>
      <Metric icon="cap" label="Nouveaux inscrits" value="24" trend="up" trendValue="+9,1 %" trendLabel="vs. déc. 2026"/>
      <Metric icon="alert" label="Dossiers incomplets" value="13" trend="down" trendValue="−18,8 %" trendLabel="vs. déc. 2026"/>
      <Metric icon="whatsapp" label="Parents sans numéro WhatsApp" value="9" trend="down" trendValue="−10,0 %" trendLabel="vs. déc. 2026"/>
    </div>
    <div className="yd-grid students-grid">
      <Card title="Liste des élèves" count="(352)" icon="users">
        <div className="yd-table-wrap"><table className="clickable nowrap dense"><thead><tr>{["#", "Élève", "Classe", "Parent / Tuteur", "Téléphone", <>Situation<br/>financière</>, "Statut", "Actions"].map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
          <tbody>{visible.map(([s, i]) => <tr key={i} className={selected === i ? "selected" : ""} onClick={() => setSelected(i)}><td>{i + 1}</td><td><b>{s[0]}</b></td><td>{s[1]}</td><td>{s[2]}</td><td>{s[3]}</td><td>{s[4]}</td><td><Status tone={s[5]}>{s[6]}</Status></td><td><Dots/></td></tr>)}</tbody></table></div>
      </Card>
      <StudentPreview s={STUDENTS[selected]} index={selected}/>
    </div>
  </>;
}
function StudentPreview({ s, index }) {
  const totals = [["425 000 FCFA", "300 000 FCFA", "125 000 FCFA"], ["380 000 FCFA", "380 000 FCFA", "0 FCFA"]];
  const t = s[5] === "green" ? totals[1] : totals[0];
  return <Card title="Aperçu de l’élève" icon="user" className="student-preview">
    <div className="yd-person"><div className="yd-avatar big"><Icon name="user" size={46} strokeWidth={0} className="filled"/></div><div><h3>{s[0]}</h3><span>Classe : {s[1]}</span><span>Matricule : ELA{String(458 + index).padStart(6, "0")}</span></div></div>
    <div className="yd-info-list">
      <InfoRow icon="user" k="Parent / Tuteur" v={s[2]}/>
      <InfoRow icon="whatsapp" k="Téléphone" v={s[3]} vIcon="whatsapp"/>
      <InfoRow icon="coins" k="Total annuel" v={t[0]}/>
      <InfoRow icon="wallet" k="Montant payé" v={t[1]}/>
      <InfoRow icon="scale" k="Reste à payer" v={t[2]} highlight/>
    </div>
    <div className="yd-btn-stack"><Button primary icon="file">Voir la fiche</Button><Button icon="coins">Encaisser</Button><Button icon="whatsapp">Contacter le parent</Button></div>
  </Card>;
}

const ADMISSIONS = [
  ["MOUKAGNI Loïc", sup(3, "e"), "M. Moukagni Eric", 1, 1, ["green", "Paiement confirmé"], "—"],
  ["NDONG Aïda", sup(4, "e"), "Mme Ndong Clarisse", 1, 0, ["yellow", "En étude"], "—"],
  ["BITEGHE Mathis", sup(5, "e"), "M. Biteghe Patrick", 1, 0, ["green", "Admis sous réserve"], "—"],
  ["OBAME Chloé", sup(6, "e"), "Mme Obame Sandrine", 1, 1, ["green", "Paiement confirmé"], "Réservation expire le 17 janv. 2027"],
  ["MINKO Steeve", sup(2, "nde"), "M. Minko Jean", 0, 0, ["yellow", "En attente"], "—"],
  ["BOVOUNGOU Eva", "CP1", "Mme Bovoungou Marie", 1, 2, ["green", "Paiement confirmé"], "—"],
  ["NZE Paul", "CE2", "M. Nze Armand", 1, 0, ["red", "Liste d’attente"], "—"],
  ["MEBIYO Sara", sup(6, "e"), "Mme Mebiyo Élise", 1, 1, ["green", "Admis sous réserve"], "—"],
];
function Admissions() {
  const pay = p => p === 1 ? <span className="yd-ok"><Icon name="check" size={16} strokeWidth={2.4}/>Confirmé</span> : p === 2 ? <span className="yd-ok exo"><Icon name="shield" size={16}/>Exonération<br/>validée</span> : <span className="yd-ko"><Icon name="close" size={16} strokeWidth={2.4}/>Non payé</span>;
  const dossier = d => d ? <span className="yd-ok"><Icon name="check" size={16} strokeWidth={2.4}/>Complet</span> : <span className="yd-ko"><Icon name="file" size={16}/>Incomplet</span>;
  return <>
    <PageHeader title="Admissions & préinscriptions" subtitle="Demandes en ligne, inscriptions au secrétariat, capacité d’accueil et paiement"/>
    <div className="yd-grid admissions-grid">
      <div className="yd-stack">
        <Card title="Capacité d’accueil" icon="layers" className="capacity-card" count="(extraits des classes principales)" right={<button type="button" className="yd-chip-link">Voir toutes les classes <Icon name="chevronright" size={16}/></button>}>
          <div className="capacity-row">{[["CP1 A", "35 / 40", "5 places restantes", 87], ["CE2 A", "33 / 35", "2 places restantes", 94], [cls(6, "e", "B"), "42 / 45", "3 places restantes", 93], [cls(2, "nde", "A"), "38 / 40", "2 places restantes", 95]].map((x, i) => <div className="capacity" key={i}>
            <div className="cap-top"><Icon name="users" size={24}/><div><b>{x[0]}</b><strong>{x[1]}</strong></div><em>{x[2].split(" ").slice(0, 2).join(" ")}<br/>restantes</em></div>
            <svg className="cap-bar" viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true"><rect width="100" height="6" rx="3" className="bg"/><rect width={x[3]} height="6" rx="3"/></svg></div>)}</div>
        </Card>
        <div className="yd-metrics four compact">
          <Metric icon="list" label="Demandes reçues" value="86" trend="up" trendValue="+12,4 %" trendLabel="vs. déc. 2026"/>
          <Metric icon="checkcircle" label="Dossiers complets" value="54" trend="up" trendValue="+17,4 %" trendLabel="vs. déc. 2026"/>
          <Metric icon="users" label="Places réservées" value="18" trend="up" trendValue="+20,0 %" trendLabel="vs. déc. 2026"/>
          <Metric icon="hourglass" label="Liste d’attente" value="7" trend="flat" trendValue="+0" trendLabel="vs. déc. 2026"/>
        </div>
        <div className="yd-filter-card">{[["calendar", "Année scolaire", "2026 – 2027"], ["layers", "Niveau", "Tous les niveaux"], ["users", "Classe", "Toutes les classes"], ["filter", "Statut", "Tous les statuts"]].map(([ic, l, v]) => <div key={l}><span><Icon name={ic} size={20}/>{l}</span><SelectBox value={v} className="plain small"/></div>)}</div>
        <Card title="Demandes d’admission" icon="users" right={<span className="yd-card-right"><span className="yd-muted">86 demandes</span><Button icon="download" className="small">Exporter</Button></span>}>
          <Table className="xs nowrap" align={{ 7: "wrap" }} headers={["#", "Candidat", "Niveau demandé", "Responsable", "Dossier", "Paiement", "Statut", "Réservation", "Actions"]}
            rows={ADMISSIONS.map((a, i) => [i + 1, <b>{a[0]}</b>, a[1], a[2], dossier(a[3]), pay(a[4]), <Status tone={a[5][0]}>{a[5][1]}</Status>, a[6].startsWith("Réservation") ? <span className="yd-resa"><Icon name="calendar" size={16}/>{a[6]}</span> : a[6], <Dots/>])}/>
          <Note>Une demande n’est confirmée qu’après validation administrative et paiement confirmé.</Note>
        </Card>
      </div>
      <Card title="Aperçu du dossier" icon="file" className="admission-preview">
        <div className="yd-person photo"><img src={admissionPhoto} alt="Photo du candidat" width="120" height="120"/><div><h3>OBAME Chloé</h3><span>N° de demande : ADM-2027-0042</span><Status>Admis sous réserve</Status></div></div>
        <InfoRow icon="cap" k="Classe demandée" v={sup(6, "e")}/>
        <div className="yd-info-row tall"><span><Icon name="users" size={20}/>Responsable</span><b>Mme Obame Sandrine<small><Icon name="phone" size={14}/>+241 06 23 45 67</small><small><Icon name="mail" size={14}/>sandrine.obame@email.com</small></b></div>
        <div className="yd-docs"><b><Icon name="paperclip" size={20}/>Pièces fournies (4/4)</b>{["Acte de naissance", "2 photos d’identité", "Dernier bulletin", "Pièce d’identité du responsable"].map(d => <span key={d}><Check/>{d}</span>)}</div>
        <InfoRow icon="coins" k="Montant inscription" v="50 000 FCFA"/>
        <div className="yd-info-row"><span><Icon name="card" size={20}/>Paiement</span><Status tone="red">Non confirmé</Status></div>
        <div className="yd-btn-stack"><Button primary icon="checkcircle">Valider le dossier</Button><Button icon="mail">Envoyer le lien de paiement</Button><Button icon="list">Placer en liste d’attente</Button></div>
      </Card>
    </div>
  </>;
}

function Payments() {
  const [mode, setMode] = useState("Airtel Money");
  const [partial, setPartial] = useState(true);
  const [debts, setDebts] = useState([true, false, false]);
  const items = [[<>Scolarité – 2<sup>e</sup> trimestre</>, 75000], ["Cantine – Janvier", 20000], [<>Activités pédagogiques – 2<sup>e</sup> trimestre</>, 15000]];
  const modeIcon = { "Airtel Money": "mobile", "Moov Money": "mobile", "Espèces": "cash", "Virement": "transfer" };
  const rows = [["R-2027-001284", "MOUKAGNI Loïc", cls(3, "e", "A"), "125 000 FCFA", "Airtel Money", "10:24"], ["R-2027-001285", "NDONG Aïda", cls(4, "e", "B"), "75 000 FCFA", "Espèces", "10:47"], ["R-2027-001286", "BITEGHE Mathis", cls(5, "e", "A"), "150 000 FCFA", "Moov Money", "11:06"], ["R-2027-001287", "OBAME Chloé", cls(6, "e", "B"), "100 000 FCFA", "Virement", "11:32"], ["R-2027-001288", "MINKO Steeve", cls(2, "nde", "A"), "50 000 FCFA", "Airtel Money", "12:05"], ["R-2027-001289", "BEKA Élise", cls(1, "ère", "C"), "75 000 FCFA", "Espèces", "12:28"]];
  return <>
    <PageHeader title="Encaissements et caisse journalière" subtitle="Suivi des paiements, reçus et méthodes d’encaissement" badge="Économe" badgeIcon="coins"/>
    <div className="yd-metrics four">
      <Metric icon="coins" label="Encaissé aujourd’hui" value="1 275 000 FCFA" trend="up" trendValue="+8,6 %" trendLabel="vs. hier (1 174 000 FCFA)"/>
      <Metric icon="file" label="Nombre de paiements" value="18" trend="up" trendValue="+20,0 %" trendLabel="vs. hier (15)"/>
      <Metric icon="cash" label="Espèces" value="390 000 FCFA" trendValue="30,6 %" trendLabel="du total" trend="none"/>
      <Metric icon="mobile" label="Mobile money" value="885 000 FCFA" trendValue="69,4 %" trendLabel="du total" trend="none"/>
    </div>
    <div className="yd-grid payments-grid">
      <Card title="Nouvel encaissement" icon="card" className="payment-form">
        <label className="yd-label">Élève <i>*</i></label>
        <div className="yd-input"><Icon name="user" size={20}/><span>NGOMA Junior</span><em><span>{cls(5, "e", "A")}</span></em><Icon name="chevron" size={18}/></div>
        <label className="yd-label">Parent <i>*</i></label>
        <div className="yd-input"><Icon name="users" size={20}/><span>NGOMA Paul (Père)</span><em><Icon name="phone" size={16}/>+241 77 23 45 67</em></div>
        <label className="yd-label">Impayés sélectionnés <i>*</i></label>
        <div className="yd-debts">{items.map(([l, v], i) => <button type="button" key={i} className={debts[i] ? "active" : ""} onClick={() => setDebts(d => d.map((x, j) => j === i ? !x : x))}><Check on={debts[i]}/><span>{l}</span><b>{v.toLocaleString("fr-FR").replace(/ | /g, " ")} FCFA</b></button>)}</div>
        <label className="yd-label">Mode de paiement <i>*</i></label>
        <div className="yd-paymodes">{Object.keys(modeIcon).map(m => <Button key={m} primary={mode === m} icon={modeIcon[m]} onClick={() => setMode(m)}>{m}</Button>)}</div>
        <label className="yd-label">Montant saisi <i>*</i></label>
        <div className="yd-amount-row"><div className="yd-amount"><span>75 000</span><em>FCFA</em></div><button type="button" className="yd-toggle-btn" aria-pressed={partial} onClick={() => setPartial(p => !p)}><Toggle on={partial}/>Paiement partiel</button></div>
        <div className="yd-balance"><span><Icon name="coins" size={22}/>Solde après paiement</span><strong>50 000 FCFA</strong></div>
        <Button primary icon="check" className="wide">Valider le paiement</Button>
      </Card>
      <div className="yd-stack">
        <Card title="Derniers paiements du jour" icon="receipt">
          <Table className="nowrap xs" headers={["# Reçu", "Élève", "Classe", "Montant", "Mode", "Heure"]} rows={rows.map(r => [r[0], r[1], r[2], r[3], <span className="yd-mode"><Icon name={modeIcon[r[4]]} size={18}/>{r[4]}</span>, r[5]])}/>
        </Card>
        <Card title="Caisse du jour" icon="layers">
          <div className="cash-row">
            <Donut size={180} values={[630, 255, 390, 0]} centerTop="1 275 000" centerBottom={"FCFA\nencaissés"} legend={[["Airtel Money : 630 000 FCFA", "(49,4 %)"], ["Moov Money : 255 000 FCFA", "(20,0 %)"], ["Espèces : 390 000 FCFA", "(30,6 %)"], ["Virement : 0 FCFA", "(0,0 %)"]]}/>
            <div className="cash-total"><div><span>Total encaissé</span><strong>1 275 000 FCFA</strong></div><Button primary icon="lock">Clôturer la caisse</Button></div>
          </div>
        </Card>
      </div>
    </div>
  </>;
}

const ARREARS = [
  ["NZE Kévin", cls(4, "e", "B"), "M. NZE Martin", "12 janv. 2027", "75 000 FCFA", "11 janv. 2027", "whatsapp", ["red", "En retard"]],
  ["MBOUI Emma", cls(3, "e", "A"), <>Mme MBOUI<br/>Clarisse</>, "10 janv. 2027", "125 000 FCFA", "10 janv. 2027", "message", ["yellow", "À relancer"]],
  ["ONDO Thierry", cls(6, "e", "B"), "M. ONDO Jacques", "14 janv. 2027", "60 000 FCFA", "09 janv. 2027", "whatsapp", ["green", <>Promesse de<br/>paiement</>]],
  ["AYANG Lucie", cls(5, "e", "A"), <>Mme AYANG<br/>Patricia</>, "13 janv. 2027", "45 000 FCFA", "—", null, ["gray", "Sans réponse"]],
  ["MINKO Steve", cls(2, "nde", "A"), "M. MINKO Daniel", "12 janv. 2027", "95 000 FCFA", "11 janv. 2027", "message", ["red", "En retard"]],
  ["NGOULOU Sara", cls(3, "e", "B"), <>Mme NGOULOU<br/>Émilie</>, "15 janv. 2027", "80 000 FCFA", "13 janv. 2027", "whatsapp", ["yellow", "À relancer"]],
  ["BITEGHE Liam", cls(6, "e", "A"), "M. BITEGHE Alain", "12 janv. 2027", "50 000 FCFA", "10 janv. 2027", "message", ["gray", "Sans réponse"]],
  ["OBAME Chloé", cls(5, "e", "B"), <>Mme OBAME<br/>Sandra</>, "14 janv. 2027", "110 000 FCFA", "12 janv. 2027", "whatsapp", ["green", <>Promesse de<br/>paiement</>]],
];
function Arrears() {
  const [channel, setChannel] = useState("WhatsApp");
  return <>
    <PageHeader banner={false} title="Impayés & relances" subtitle="Suivi des échéances, retards et messages aux familles" actions={<><Button primary icon="send">Envoyer les relances</Button><Button icon="whatsapp">WhatsApp</Button><Button icon="message">SMS</Button><Button icon="download">Exporter</Button></>}/>
    <div className="yd-grid arrears-layout">
      <div className="yd-stack">
        <div className="yd-metrics four">
          <Metric icon="coins" label="Total restant dû" value="3 240 000 FCFA" trend="up" trendValue="−18,4 %" trendLabel="vs. déc. 2026"/>
          <Metric icon="alert" label="Familles en retard" value="41" trend="down" trendValue="−6 familles" trendLabel="vs. déc. 2026"/>
          <Metric icon="send" label="Relances envoyées aujourd’hui" value="12" trend="up" trendValue="+20,0 %" trendLabel="vs. hier"/>
          <Metric icon="users" label="Promesses de paiement" value="7" trend="up" trendValue="+2" trendLabel="vs. déc. 2026"/>
        </div>
        <Card title="Liste des familles en impayé" count="(41)" icon="users">
          <Table className="xs" align={{ 1: "nowrap", 4: "nowrap", 5: "nowrap", 6: "nowrap" }} headers={["", "Élève", "Classe", "Responsable", "Échéance", "Montant dû", <>Dernière<br/>relance</>, "Canal", "Statut", "Actions"]}
            rows={ARREARS.map((a, i) => [i + 1, <b>{a[0]}</b>, a[1], a[2], a[3], <b>{a[4]}</b>, a[5], a[6] ? <Icon name={a[6]} size={22} className="channel"/> : "—", <Status tone={a[7][0]}>{a[7][1]}</Status>, <Dots/>])}/>
        </Card>
      </div>
      <div className="yd-stack">
        <Card title="Aperçu du message" icon="message">
          <div className="yd-channel-tabs" role="tablist">{[["WhatsApp", "whatsapp"], ["SMS", "message"], ["Email", "mail"]].map(([c, ic]) => <button type="button" role="tab" aria-selected={channel === c} key={c} className={channel === c ? "active" : ""} onClick={() => setChannel(c)}><Icon name={ic} size={18}/>{c}</button>)}</div>
          <div className="yd-message-preview"><p>Bonjour M. NZE Martin,</p><p>Nous vous rappelons que les frais de scolarité de votre enfant <b>NZE Kévin</b> (4<sup>e</sup> B) s’élèvent à <b>75 000 FCFA</b>, échus le 12 janv. 2027.</p><p>Nous vous invitons à régulariser cette situation dans les meilleurs délais.</p><p>L’École Privée Les Amandiers vous remercie pour votre diligence.</p><small>10:24 <Icon name="check" size={14}/></small></div>
        </Card>
        <Card title="Répartition des impayés par classe" icon="barchart">
          <BarList items={[["3ᵉ A", 8], ["4ᵉ B", 7], ["5ᵉ A", 6], ["6ᵉ B", 5], ["3ᵉ B", 4], ["2ⁿᵈᵉ A", 4], ["6ᵉ A", 3], ["5ᵉ B", 3]]} max={8.6}/>
        </Card>
      </div>
    </div>
  </>;
}

const BULLETIN_ROWS = [["MOUKAGNI Loïc", "15,62", sup(1, "er"), "Très bien", "0 jour", "green"], ["BITEGHE Mathis", "14,90", sup(2, "e"), "Très bien", "1 jour", "green"], ["OBAME Chloé", "14,86", sup(3, "e"), "Bien", "0 jour", "green"], ["MINKO Steeve", "14,20", sup(4, "e"), "Bien", "2 jours", "green"], ["NDONG Éléonore", "13,84", sup(5, "e"), "Très bien", "2 jours", "green"], ["OKOUMBA Daniel", "13,56", sup(6, "e"), "Bien", "1 jour", "green"], ["ESSONO Aïcha", "13,20", sup(7, "e"), "Bien", "3 jours", "yellow"], ["NGUEMA Paul", "12,96", sup(8, "e"), "Assez bien", "2 jours", "green"]];
function Bulletins() {
  return <>
    <PageHeader title="Bulletins et résultats scolaires" subtitle="Préparation, contrôle et génération des bulletins du trimestre"/>
    <div className="yd-toolbar bulletins">
      <SelectBox icon="users" label="Classe" value={cls(6, "e", "B")}/>
      <SelectBox icon="calendar" label="Période" value={<>1<sup>er</sup> trimestre</>}/>
      <span className="grow"/>
      <Button primary icon="printer">Générer les bulletins</Button>
      <Button icon="download">Exporter PDF</Button>
    </div>
    <div className="yd-metrics four">
      <Metric icon="users" label="Élèves évalués" value="35" trend="up" trendValue="+0" trendLabel="vs. période précédente"/>
      <Metric icon="file" label="Bulletins générés" value="32" trend="up" trendValue="+6" trendLabel="vs. période précédente"/>
      <Metric icon="alert" label="Bulletins en attente" value="3" trend="down" trendValue="−6" trendLabel="vs. période précédente"/>
      <Metric icon="coins" label="Paiements à jour" value="29" trend="up" trendValue="+4" trendLabel="vs. période précédente"/>
    </div>
    <div className="yd-grid bulletins-grid">
      <Card title={<>Élèves de la classe 6<sup>e</sup> B (35)</>} icon="users">
        <SearchBox placeholder="Rechercher un élève..." className="full"/>
        <Table className="xs nowrap" selected={4} headers={["#", "Élève", <>Moyenne<br/>générale</>, "Rang", "Conduite", "Absences", "Paiement"]} rows={BULLETIN_ROWS.map((r, i) => [i + 1, r[0], `${r[1]} / 20`, r[2], r[3], r[4], <Status tone={r[5]}>{r[5] === "green" ? "À jour" : "En attente"}</Status>])}/>
      </Card>
      <ReportCard/>
    </div>
  </>;
}
export function ReportCard() {
  const subjects = [["Français", "14,00", "12,36", "Bien"], ["Mathématiques", "13,50", "11,72", "Bien"], ["Anglais", "15,00", "13,08", "Très bien"], ["Histoire-Géographie", "12,50", "11,64", "Assez bien"], ["SVT", "14,00", "12,90", "Bien"], ["Physique-Chimie", "13,00", "12,15", "Bien"], ["ECM", "16,00", "14,02", "Très bien"], ["Éducation Artistique", "15,50", "14,33", "Très bien"], ["EPS", "17,00", "15,24", "Très bien"]];
  return <article className="report-sheet" aria-label="Bulletin de notes">
    <div className="report-brand"><div className="report-school"><span className="report-book" aria-hidden="true"><svg viewBox="0 0 64 50" width="52" height="40"><path d="M4 9.5c9-1.5 18 .5 26.5 6.8V47C22 41 13 39.4 4 40.6Z" fill="#2f7a35"/><path d="M60 9.5c-9-1.5-18 .5-26.5 6.8V47C42 41 51 39.4 60 40.6Z" fill="#2f7a35"/><path d="M1 13.5v31.5c10-1.6 20.5.4 31 5 10.5-4.6 21-6.6 31-5V13.5" fill="none" stroke="#1f5a26" strokeWidth="2.6"/></svg></span><div><b>École Privée<br/>Les Amandiers</b><small>Libreville – Gabon</small></div></div>
      <div className="report-title"><h2>BULLETIN DE NOTES</h2><span>1<sup>er</sup> trimestre – Année scolaire 2026 – 2027</span></div></div>
    <div className="report-person"><div className="yd-avatar"><Icon name="user" size={30} strokeWidth={0} className="filled"/></div><div className="who"><span>Élève : <b>NDONG Éléonore</b></span><span>Classe : 6<sup>e</sup> B</span><span>Matricule : 6B-023</span></div><div className="meta"><span>Effectif de la classe : 35</span><span>Période : 1<sup>er</sup> trimestre</span><span>Date d’édition : 12 janv. 2027</span></div></div>
    <table className="report-table"><thead><tr><th>Matière</th><th>Note / 20</th><th>Moy. de classe / 20</th><th>Appréciation</th></tr></thead><tbody>{subjects.map(s => <tr key={s[0]}><td>{s[0]}</td><td><b>{s[1]}</b></td><td>{s[2]}</td><td>{s[3]}</td></tr>)}</tbody></table>
    <div className="report-summary"><div><span>Moyenne générale</span><strong>13,84 <small>/ 20</small></strong></div><div><span>Rang</span><strong>5<sup>e</sup> <small>/ 35</small></strong></div><div><span>Conduite</span><Status>Très bien</Status></div><div><span>Absences</span><strong>2 jours</strong></div></div>
    <div className="report-foot"><QrCode size={74} seed={3}/><div className="auth"><b>Authenticité du bulletin</b><span>Scannez ce QR code pour vérifier la conformité du document.</span></div><div className="sign"><b>Le Professeur principal</b><Signature/></div><div className="sign"><b>La Directrice</b><Signature variant={1}/></div></div>
  </article>;
}

function BulletinConfig() {
  const systems = [["Sur 20", "Barème : 0 à 20 · Pas : 0,25", true], ["Sur 10", "Barème : 0 à 10 · Pas : 0,5", true], ["Sur 100", "Barème : 0 à 100 · Pas : 1", true], ["Pourcentage", "Barème : 0 % à 100 % · Pas : 1 %", true], ["Lettres (A+, A, B, C)", "Échelle : A+, A, B, C, D, E", true], [<>Mentions <small>(Excellent, Très bien, Bien)</small></>, "Échelle : Excellent, Très bien, Bien, Assez bien, Passable, Insuffisant", true], ["Compétences", "Niveaux : Maîtrisée, En cours, Non maîtrisée", false]];
  const [on, setOn] = useState(systems.map(s => s[2]));
  const [rules, setRules] = useState({ rank: true, coef: true });
  return <>
    <PageHeader title="Paramétrage pédagogique et bulletins" subtitle="Barèmes, types d’évaluations, modèles de bulletins et règles de publication"/>
    <div className="yd-toolbar config">
      <SelectBox icon="calendar" label="Année scolaire" value="2026 – 2027"/><span className="vsep"/>
      <SelectBox icon="cap" label="Cycle" value="Collège"/>
      <SelectBox icon="layers" label="Niveau" value={sup(5, "e")}/>
      <SelectBox icon="users" label="Classe" value={cls(5, "e", "A")}/>
    </div>
    <div className="yd-metrics three"><Metric icon="sliders" label="Systèmes de notation actifs" value="4"/><Metric icon="file" label="Modèles de bulletins" value="3"/><Metric icon="layers" label="Configurations publiées" value="12"/></div>
    <div className="yd-grid config-grid">
      <Card title="Systèmes de notation" icon="scale" subtitle="Choisissez et paramétrez les systèmes de notation disponibles pour ce cycle / niveau.">
        <div className="notation-list">{systems.map((x, i) => <div key={i}><button type="button" className="yd-check-btn" aria-pressed={on[i]} aria-label={`Activer ${typeof x[0] === "string" ? x[0] : "Mentions"}`} onClick={() => setOn(o => o.map((v, j) => j === i ? !v : v))}><Check on={on[i]}/></button><div><b>{x[0]}</b><small>{x[1]}</small></div><Button icon="settings" className="small soft">Configurer</Button></div>)}</div>
        <Note><b>Paramétrable et flexible :</b> activez les systèmes utiles, modifiez les barèmes, les pas, les échelles et les mentions selon vos besoins.</Note>
      </Card>
      <div className="yd-stack">
        <Card title="Types d’évaluations et pondérations" icon="layers" subtitle="Définissez les types d’évaluations et leurs pondérations dans la moyenne.">
          <table className="weights"><thead><tr><th>-</th><th>Type d’évaluation</th><th>Pondération</th><th/><th/></tr></thead><tbody>{[["Devoir de classe", "30 %"], ["Interrogation", "20 %"], ["Composition", "50 %"]].map(r => <tr key={r[0]}><td><Icon name="grip" size={18}/></td><td>{r[0]}</td><td><span className="yd-mini-input">{r[1]}</span></td><td><Icon name="edit" size={18}/></td><td><Icon name="trash" size={18}/></td></tr>)}</tbody></table>
          <Button icon="plus" className="center soft">Ajouter un type</Button>
        </Card>
        <Card title="Règles de calcul" icon="calculator" subtitle="Paramétrez la manière dont les moyennes et les résultats sont calculés.">
          <div className="rule-list">
            <div><span>Arrondi des moyennes <Icon name="info" size={16}/></span><SelectBox value="À 2 décimales" className="plain small"/></div>
            <div><span>Classement des élèves <Icon name="info" size={16}/></span><button type="button" className="yd-toggle-btn" aria-pressed={rules.rank} onClick={() => setRules(r => ({ ...r, rank: !r.rank }))}><Toggle on={rules.rank}/>{rules.rank ? "Activé" : "Désactivé"}</button></div>
            <div><span>Calcul par coefficient <Icon name="info" size={16}/></span><button type="button" className="yd-toggle-btn" aria-pressed={rules.coef} onClick={() => setRules(r => ({ ...r, coef: !r.coef }))}><Toggle on={rules.coef}/>{rules.coef ? "Activé" : "Désactivé"}</button></div>
            <div><span>Notes absentes <Icon name="info" size={16}/></span><SelectBox value="Non comptées" className="plain small"/></div>
          </div>
        </Card>
      </div>
      <Card title="Modèle de bulletin" icon="file" className="bulletin-model" subtitle="Configurez le modèle de bulletin et les sections à inclure.">
        <div className="model-grid"><div className="section-checks"><b>Sections à inclure</b>{["Photo de l’élève", "Rang", "Conduite", "Absences", "Signatures", "QR code", "Appréciation générale"].map(x => <span key={x}><Check/>{x}</span>)}</div><MiniBulletin/></div>
        <Note><b>Modèles personnalisables :</b> choisissez les informations, leur ordre et la présentation (logo, entête, pied de page, etc.).</Note>
      </Card>
    </div>
    <div className="yd-footer-actions"><Button icon="calculator">Tester le calcul</Button><Button icon="file">Enregistrer en brouillon</Button><Button primary icon="send">Publier la configuration</Button></div>
  </>;
}
function MiniBulletin() {
  return <div className="mini-bulletin" aria-hidden="true">
    <div className="mini-head"><span><svg viewBox="0 0 64 50" width="22" height="17"><path d="M4 9.5c9-1.5 18 .5 26.5 6.8V47C22 41 13 39.4 4 40.6Z" fill="#2f7a35"/><path d="M60 9.5c-9-1.5-18 .5-26.5 6.8V47C42 41 51 39.4 60 40.6Z" fill="#2f7a35"/></svg><small>École Privée<br/>Les Amandiers</small></span><b>Bulletin de notes<small>Année scolaire 2026 – 2027</small></b></div>
    <div className="mini-person"><div className="ph"><Icon name="user" size={26} strokeWidth={0} className="filled"/></div><div><small>Nom : <i/></small><small>Classe : 5e A</small><small>Rang : 3e / 28</small></div><div className="lines"><i/><i/><i/></div></div>
    <div className="mini-table"><div className="h"><span>Matière</span><span>Moy.</span><span>Appréciation</span></div>{Array.from({ length: 6 }).map((_, i) => <div key={i}><i/><i/><i/></div>)}</div>
    <div className="mini-app"><small>Appréciation générale</small><i/><i/></div>
    <div className="mini-foot"><QrCode size={30} seed={5}/><small>Signatures</small></div>
  </div>;
}

function Absences() {
  const rows = [["ABOGA Samuel", "CM1 A", "Présent", "green"], ["BIKOE Emma", "CM1 A", "Présent", "green"], ["NDONG Kevin", "CM1 A", "Absent", "red"], ["OBAME Lucie", "CM1 A", "Présent", "green"], ["MINKO David", "CM1 A", "Retard", "yellow"], ["NZE Carla", "CM1 A", "Présent", "green"]];
  return <>
    <PageHeader title="Absences et retards" subtitle="Appels, absences, retards et justificatifs des élèves"/>
    <div className="yd-toolbar bulletins"><SelectBox icon="users" label="Classe" value="CM1 A"/><SelectBox icon="calendar" label="Date" value="12 janv. 2027"/><span className="grow"/><Button primary icon="check">Valider l’appel</Button><Button icon="download">Exporter</Button></div>
    <div className="yd-metrics four"><Metric icon="users" label="Élèves attendus" value="6"/><Metric icon="checkcircle" label="Présents" value="4"/><Metric icon="alert" label="Absents" value="1"/><Metric icon="clock" label="Retards" value="1"/></div>
    <Card title="Appel du jour" icon="calendar"><Table headers={["#", "Élève", "Classe", "Statut"]} rows={rows.map((r, i) => [i + 1, <b>{r[0]}</b>, r[1], <Status tone={r[3]}>{r[2]}</Status>])}/></Card>
  </>;
}
function Staff() {
  const rows = [["Mme ESSONO Clarisse", "Directrice", "Direction", "+241 77 10 20 30"], ["M. OBIANG Paul", "Professeur principal 6ᵉ B", "Enseignement", "+241 66 11 22 33"], ["Mme MOUSSAVOU Rita", "Économe", "Comptabilité", "+241 74 55 66 77"], ["M. NDONG Hervé", "Secrétaire administratif", "Secrétariat", "+241 62 44 33 22"]];
  return <>
    <PageHeader title="Personnel" subtitle="Équipe pédagogique et administrative, affectations et responsabilités"/>
    <div className="yd-metrics four"><Metric icon="idcard" label="Membres du personnel" value="38"/><Metric icon="cap" label="Enseignants" value="27"/><Metric icon="settings" label="Administration" value="8"/><Metric icon="users" label="Classes couvertes" value="14"/></div>
    <Card title="Liste du personnel" icon="idcard"><Table headers={["#", "Nom", "Fonction", "Service", "Téléphone"]} rows={rows.map((r, i) => [i + 1, <b>{r[0]}</b>, r[1], r[2], r[3]])}/></Card>
  </>;
}

const BRAND_KEY = "yem.preview.branding.v1";
const defaultBrand = { name: "École Privée Les Amandiers", color: "#2f6b37", logo: "", banner: "" };
function getBrand() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(BRAND_KEY) || "null");
    if (!saved || typeof saved !== "object") return defaultBrand;
    const color = /^#[0-9a-fA-F]{6}$/.test(saved.color || "") ? saved.color : defaultBrand.color;
    return { ...defaultBrand, name: String(saved.name || defaultBrand.name).slice(0, 180), color,
      logo: typeof saved.logo === "string" && saved.logo.startsWith("data:image/") ? saved.logo : "",
      banner: typeof saved.banner === "string" && saved.banner.startsWith("data:image/") ? saved.banner : "" };
  } catch { return defaultBrand; }
}
function BrandingEditor({ brand, onChange }) {
  const [error, setError] = useState("");
  function upload(field, file) {
    setError("");
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) { setError("Formats autorisés : PNG, JPEG, WebP."); return; }
    if (file.size > 900000) { setError("Image trop volumineuse (900 Ko maximum pour cet aperçu)."); return; }
    const reader = new FileReader();
    reader.onload = () => onChange({ ...brand, [field]: String(reader.result) });
    reader.onerror = () => setError("Lecture du fichier impossible.");
    reader.readAsDataURL(file);
  }
  return <>
    <PageHeader title="Identité visuelle de l’établissement" subtitle="Personnalisation des pages de l’école et de son personnel — aperçu local"/>
    <div className="yd-grid two-cols">
      <Card title="Personnalisation" icon="palette">
        <p className="yd-card-sub">Ces réglages concernent uniquement cet aperçu sur ce navigateur. Ils ne sont pas encore enregistrés dans les comptes de l’établissement.</p>
        <label className="yd-brand-field">Nom de l’établissement<input maxLength={180} value={brand.name} onChange={e => onChange({ ...brand, name: e.target.value })}/></label>
        <label className="yd-brand-field">Couleur de l’établissement<input type="color" value={brand.color} onChange={e => onChange({ ...brand, color: e.target.value })}/></label>
        <label className="yd-brand-field">Logo de l’établissement (PNG, JPG ou WebP)<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e => upload("logo", e.target.files?.[0])}/></label>
        <label className="yd-brand-field">Bannière de l’établissement (PNG, JPG ou WebP)<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e => upload("banner", e.target.files?.[0])}/></label>
        {error && <p role="alert" className="yd-error">{error}</p>}
        <Button onClick={() => onChange(defaultBrand)}>Réinitialiser cet aperçu</Button>
      </Card>
      <Card title="Aperçu de l’identité" icon="school">
        <div className="yd-brand-preview">{brand.banner && <img className="yd-brand-banner-preview" src={brand.banner} alt="Bannière de l’établissement"/>}
          <div className="yd-brand-preview-text">{brand.logo && <img src={brand.logo} alt="Logo de l’établissement"/>}<strong>{brand.name || "Votre établissement"}</strong></div></div>
        <p className="yd-card-sub">Le logo YEM et la mention « Développé par BWETEK Informatyk » restent présents, quelle que soit la couleur choisie.</p>
      </Card>
    </div>
  </>;
}

export function SchoolMenu({ name, logo, items, value, onSelect }) {
  const [open, setOpen] = useState(false);
  return <div className="yd-school-select-wrap">
    <button type="button" className="yd-school-select" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(o => !o)}>
      {logo ? <img className="yd-school-logo" src={logo} alt=""/> : <Icon name="school" size={24}/>}<b>{name}</b><Icon name="chevron" size={18} className="chev"/>
    </button>
    {open && <div className="yd-menu" role="menu">{items.map(it => <button type="button" role="menuitem" key={it.key} className={value === it.key ? "active" : ""} onClick={() => { setOpen(false); onSelect(it.key); }}>{it.icon && <Icon name={it.icon} size={18}/>}{it.label}</button>)}</div>}
  </div>;
}

function useBrandStyle(brand) {
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--school-primary", brand.color);
    return () => root.style.removeProperty("--school-primary");
  }, [brand.color]);
}

export default function YemDesktop() {
  const isMobile = useIsMobile();
  const [page, setPage] = useState("dashboard");
  const [brand, setBrand] = useState(getBrand);
  useBrandStyle(brand);
  const updateBrand = next => { setBrand(next); try { window.localStorage.setItem(BRAND_KEY, JSON.stringify(next)); } catch { /* aperçu non persistant si stockage plein */ } };
  const content = useMemo(() => ({ dashboard: <Dashboard/>, students: <Students/>, admissions: <Admissions/>, payments: <Payments/>, arrears: <Arrears/>, bulletins: <Bulletins/>, settings: <BulletinConfig/>, absences: <Absences/>, parents: <MobileShowcase/>, staff: <Staff/>, branding: <BrandingEditor brand={brand} onChange={updateBrand}/>, mobile: <MobileShowcase/> })[page], [page, brand]);
  if (isMobile) return <MobileApp/>;
  const nav = NAV;
  const active = page === "branding" ? "settings" : page;
  return <BrandContext.Provider value={brand}><Shell active={active} onNavigate={setPage} nav={nav}
    schoolSelector={<SchoolMenu name={brand.name} logo={brand.logo} value={page} onSelect={setPage} items={[{ key: "dashboard", label: brand.name, icon: "school" }, { key: "branding", label: "Identité visuelle", icon: "palette" }, { key: "mobile", label: "Expérience mobile", icon: "mobile" }]}/>}>
    {content}
    <footer className="yd-brand-footer"><span>YEM — Gestion scolaire &amp; universitaire</span><span>Développé par <strong>BWETEK Informatyk</strong></span></footer>
  </Shell></BrandContext.Provider>;
}
