import {ContextTarget} from "./ContextMenu.jsx";
import React, {useEffect, useRef, useState} from "react";

export function PdfLinks({url, label, openText = "Ouvrir", downloadText = "Télécharger", openLabel, downloadLabel, openRef, downloadRef}) {
  const preview = url + (url.includes("?") ? "&" : "?") + "preview=1";
  return <>
    <a ref={openRef} className="yd-link" href={preview} target="_blank" rel="noreferrer"
      aria-label={openLabel ?? `Ouvrir le PDF · ${label}`}>{openText}</a>{" · "}
    <a ref={downloadRef} className="yd-link" href={url} aria-label={downloadLabel ?? `Télécharger le PDF · ${label}`}>{downloadText}</a>
  </>;
}

function DocumentRows({title, items, type}) {
  if (!items.length) return null;
  return <>
    <h4>{title}</h4>
    <ul>
      {items.map(item => <DocumentRow key={item.id} item={item} type={type}/>)}
    </ul>
  </>;
}

function DocumentRow({item,type}) {
  const open=useRef(null),download=useRef(null);
  const reference=item.id.slice(0,8).toUpperCase();
  const label=item.label?`${item.label} · ${reference}`:`${type} · ${reference}`;
  const date=item.date&&new Date(item.date+"T12:00:00").toLocaleDateString("fr-FR");
  const amount=item.amount!=null&&new Intl.NumberFormat("fr-FR",{style:"currency",currency:item.currency}).format(item.amount);
  return <ContextTarget as="li" showTrigger actions={[
    {id:"open",label:"Ouvrir le PDF · "+label,run:()=>open.current?.click()},
    {id:"download",label:"Télécharger le PDF · "+label,run:()=>download.current?.click()},
  ]}>
    <strong>{label}</strong>{date&&` · ${date}`}{amount&&` · ${amount}`}
    {item.voided&&" · Annulé"}{" · "}<PdfLinks url={item.url} label={label} openRef={open} downloadRef={download}/>
  </ContextTarget>;
}

export default function FinancialDocuments({api, path, revision = 0}) {
  const [state, setState] = useState(null);
  useEffect(() => {
    let active = true;
    setState(null);
    api(path).then(data => {
      if (active) setState({data});
    }).catch(error => {
      if (active) setState({error: error.message});
    });
    return () => { active = false; };
  }, [api, path, revision]);

  if (!state) return <p role="status">Chargement des documents…</p>;
  if (state.error) return <p role="alert">Documents indisponibles. {state.error}</p>;
  const {invoices = [], receipts = [], grouped_receipts = []} = state.data;
  if (!invoices.length && !receipts.length && !grouped_receipts.length) {
    return <p>Aucune facture ni aucun reçu disponible.</p>;
  }
  return <>
    <DocumentRows title="Factures scolaires" items={invoices} type="Facture"/>
    <DocumentRows title="Reçus de paiement" items={receipts} type="Reçu"/>
    <DocumentRows title="Reçus groupés" items={grouped_receipts} type="Reçu groupé"/>
  </>;
}
