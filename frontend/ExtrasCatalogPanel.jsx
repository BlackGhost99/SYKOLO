import React, {useEffect, useState} from "react";

const EMPTY = {
  code: "", group: "B03", kind: "produit", label: "",
  subcategory: "", variant: "", unit: "unité",
  unit_price: "", currency: "XAF", academic_year: null, active: true,
};
const endpoint = schoolId => "/api/v1/schools/" + schoolId + "/finance/extras/catalog";

async function readCatalog(schoolId) {
  const response = await fetch(endpoint(schoolId), {credentials: "same-origin", cache: "no-store"});
  const json = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(json.error || "Catalogue extrascolaire indisponible.");
  return json;
}
async function saveCatalog(schoolId, payload) {
  const tokenResult = await fetch("/api/v1/auth/csrf", {credentials: "same-origin"});
  if (!tokenResult.ok) throw Error("Session de sécurité indisponible.");
  const token = document.cookie.split("; ").find(x => x.startsWith("csrftoken="))?.split("=")[1] || "";
  const response = await fetch(endpoint(schoolId), {
    method: "POST", credentials: "same-origin", cache: "no-store",
    headers: {"Content-Type": "application/json", "X-CSRFToken": token},
    body: JSON.stringify(payload),
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(json.error || "Modification du catalogue refusée.");
  return json;
}

export default function ExtrasCatalogPanel({schoolId, yearId = ""}) {
  const [catalog, setCatalog] = useState(null);
  const [form, setForm] = useState({...EMPTY});
  const [reason, setReason] = useState("");
  const [currentId, setCurrentId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  useEffect(() => {
    let active = true;
    setCatalog(null); setCurrentId(""); setError(""); setMessage("");
    setForm({...EMPTY, academic_year: yearId || null});
    readCatalog(schoolId)
      .then(data => {if (active) setCatalog(data);})
      .catch(e => {if (active) setError(e.message);});
    return () => {active = false;};
  }, [schoolId, yearId]);

  function choose(item) {
    setCurrentId(item.id);
    setForm({...item});
    setReason("");
    setError("");
    setMessage("");
  }
  function reset() {
    setCurrentId("");
    setForm({...EMPTY, academic_year: yearId || null});
    setReason("");
  }
  async function commit(action, item) {
    if (!catalog || busy || reason.trim().length < 10) return;
    setBusy(true); setMessage(""); setError("");
    try {
      const result = await saveCatalog(schoolId, {
        revision: catalog.revision,
        reason: reason.trim(),
        action,
        item,
      });
      setCatalog(await readCatalog(schoolId));
      setMessage(result.unchanged ? "Aucun changement nécessaire." :
        "Catalogue mis à jour et modification journalisée. Aucune vente n'a été créée.");
      reset();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const update = (key, value) => setForm(row => ({...row, [key]: value}));
  const visible = (catalog?.items || []).filter(item => showInactive || item.active);
  const columns = {display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 12};
  return <section className="card" aria-label="Catalogue des prestations extrascolaires" style={{marginBlock: 16}}>
    <h3>Catalogue des recettes extrascolaires</h3>
    <p className="hint">Uniformes, fournitures, cantine, transport, activités, cours complémentaires, internat
      et services administratifs. Les prix sont propres à l'établissement.</p>
    <p className="hint"><strong>Catalogue uniquement :</strong> aucune vente, créance, facture, réception d'argent
      ou sortie de stock n'est créée ici. Les impayés de ces prestations ne bloquent pas l'inscription scolaire.</p>
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!catalog ? <p>Chargement du catalogue…</p> : <>
      <form onSubmit={e => {e.preventDefault(); commit("upsert", {
        ...form, ...(currentId ? {id: currentId} : {}),
        academic_year: form.academic_year || null,
      });}}>
        <div style={columns}>
          <label>Code article
            <input required maxLength={30} value={form.code}
              disabled={Boolean(currentId)}
              onChange={e => update("code", e.target.value.toUpperCase())}
              placeholder="CANTINE-REPAS"/>
          </label>
          <label>Famille
            <select value={form.group} disabled={Boolean(currentId)}
              onChange={e => update("group", e.target.value)}>
              {catalog.groups.map(g => <option key={g.code} value={g.code}>{g.label}</option>)}
            </select>
          </label>
          <label>Type
            <select value={form.kind} onChange={e => update("kind", e.target.value)}>
              <option value="produit">Produit</option><option value="service">Service</option>
            </select>
          </label>
          <label>Désignation
            <input required maxLength={120} value={form.label}
              onChange={e => update("label", e.target.value)} placeholder="Repas du midi"/>
          </label>
          <label>Sous-catégorie
            <input maxLength={80} value={form.subcategory}
              onChange={e => update("subcategory", e.target.value)}/>
          </label>
          <label>Variante / taille
            <input maxLength={80} value={form.variant}
              onChange={e => update("variant", e.target.value)} placeholder="Taille M"/>
          </label>
          <label>Unité
            <input required maxLength={30} value={form.unit}
              onChange={e => update("unit", e.target.value)} placeholder="repas"/>
          </label>
          <label>Prix unitaire
            <input required inputMode="decimal" pattern="[0-9]+([.][0-9]{1,2})?"
              value={form.unit_price}
              onChange={e => update("unit_price", e.target.value)} placeholder="2500.00"/>
          </label>
          <label>Devise
            <input required maxLength={3} value={form.currency}
              onChange={e => update("currency", e.target.value.toUpperCase())}/>
          </label>
          <label>Année scolaire
            <select value={form.academic_year || ""} onChange={e => update("academic_year", e.target.value || null)}>
              <option value="">Toutes les années</option>
              {yearId && <option value={yearId}>Année en cours</option>}
            </select>
          </label>
        </div>
        <label style={{display: "block", marginTop: 10}}>
          <input type="checkbox" checked={form.active} onChange={e => update("active", e.target.checked)}/>
          Article actif
        </label>
        <label style={{display: "block", marginTop: 10}}>Justification de la modification
          <input required minLength={10} maxLength={240} style={{width: "100%"}}
            value={reason} onChange={e => setReason(e.target.value)}
            placeholder="Ex. Tarif cantine validé pour l'année scolaire"/>
        </label>
        <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBlock: 12}}>
          <button type="submit" disabled={busy || reason.trim().length < 10}>
            {busy ? "Enregistrement…" : currentId ? "Enregistrer les changements" : "Créer l'article"}
          </button>
          {currentId && <button type="button" onClick={reset}>Annuler la modification</button>}
          {currentId && form.active && <button type="button" disabled={busy || reason.trim().length < 10}
            onClick={() => commit("archive", {id: currentId})}>Archiver l'article</button>}
        </div>
      </form>
      <details style={{marginTop: 12}} open>
        <summary>Articles du catalogue ({visible.length})</summary>
        <label style={{display: "block", marginTop: 8}}>
          <input type="checkbox" checked={showInactive} onChange={e => setShowInactive(e.target.checked)}/>
          Afficher aussi les articles archivés
        </label>
        <div style={{overflowX: "auto"}}>
          <table className="dense">
            <thead><tr><th>Code</th><th>Produit ou service</th><th>Prix unitaire</th><th>État</th><th>Gestion</th></tr></thead>
            <tbody>{visible.map(item => <tr key={item.id}>
              <td>{item.code}</td>
              <td>{item.label}{item.variant ? " — " + item.variant : ""}</td>
              <td>{item.unit_price} {item.currency} / {item.unit}</td>
              <td>{item.active ? "Actif" : "Archivé"}</td>
              <td><button type="button" onClick={() => choose(item)}>Modifier</button></td>
            </tr>)}</tbody>
          </table>
        </div>
        {visible.length === 0 && <p>Aucun article configuré.</p>}
      </details>
    </>}
  </section>;
}
