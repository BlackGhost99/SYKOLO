import React, {useEffect, useMemo, useState} from "react";

/** A6b1: build a server-repriced estimate, never a payable order. */
export default function ExtrasQuotePreview({schoolId, yearId = "", catalogRevision = 0, items = []}) {
  const [quantities, setQuantities] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setQuantities({});
    setResult(null);
    setError("");
  }, [schoolId, yearId, catalogRevision]);
  const eligible = useMemo(
    () => items.filter(row => row.active && (!row.academic_year || row.academic_year === yearId)),
    [items, yearId],
  );
  const count = eligible.filter(row => Number(quantities[row.id] || 0) > 0).length;
  function change(id, text) {
    setResult(null); setError("");
    setQuantities(current => ({...current, [id]: text}));
  }
  async function preview(event) {
    event.preventDefault();
    if (busy) return;
    const selected = eligible
      .filter(row => Number(quantities[row.id] || 0) > 0)
      .map(row => ({id: row.id, quantity: Number(quantities[row.id])}));
    if (!selected.length) {
      setError("Sélectionnez au moins un article.");
      return;
    }
    setBusy(true); setError(""); setResult(null);
    try {
      const csrf = await fetch("/api/v1/auth/csrf", {credentials: "same-origin"});
      if (!csrf.ok) throw Error("Session de sécurité indisponible.");
      const token = document.cookie.split("; ").find(s => s.startsWith("csrftoken="))?.split("=")[1] || "";
      const response = await fetch("/api/v1/schools/" + schoolId + "/finance/extras/quote", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: {"Content-Type": "application/json", "X-CSRFToken": token},
        body: JSON.stringify({academic_year: yearId || null, items: selected}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw Error(data.error || "Calcul du panier impossible.");
      setResult(data);
    } catch (ex) {
      setError(ex.message);
    } finally {
      setBusy(false);
    }
  }
  return <details style={{marginBlock:16}} aria-label="Préparer un panier extrascolaire">
    <summary><strong>Préparer un panier extrascolaire (sans encaissement)</strong></summary>
    <p className="hint">Simulation du montant à facturer. Aucun règlement, facture, dette ou stock
      n'est enregistré. Les prix sont contrôlés sur le serveur, par établissement.</p>
    {eligible.length === 0 ? <p>Aucune prestation active pour l'année sélectionnée.</p> :
      <form onSubmit={preview}>
        <div style={{overflowX:"auto"}}>
          <table className="dense">
            <thead><tr><th>Article</th><th>Prix catalogue</th><th>Quantité</th></tr></thead>
            <tbody>{eligible.map(row => <tr key={row.id}>
              <td>{row.label}{row.variant ? " — " + row.variant : ""}</td>
              <td>{row.unit_price} {row.currency} / {row.unit}</td>
              <td>
                <input type="number" inputMode="numeric" min="0" max="1000" step="1"
                  aria-label={"Quantité de " + row.label} style={{width:94}}
                  value={quantities[row.id] ?? ""}
                  onChange={event => change(row.id, event.target.value)} placeholder="0"/>
              </td>
            </tr>)}</tbody>
          </table>
        </div>
        <button type="submit" disabled={busy || count === 0}>
          {busy ? "Calcul en cours…" : "Calculer le devis (" + count + " article(s))"}
        </button>
      </form>}
    {error && <p role="alert">{error}</p>}
    {result && <section role="status" aria-label="Devis extrascolaire non enregistré">
      <h4>Estimation extrascolaire</h4>
      <table className="dense">
        <thead><tr><th>Prestation</th><th>Quantité</th><th>Prix unitaire</th><th>Montant</th></tr></thead>
        <tbody>{result.lines.map(line => <tr key={line.catalog_item_id}>
          <td>{line.label}</td><td>{line.quantity}</td>
          <td>{line.unit_price} {line.currency}</td><td>{line.line_total} {line.currency}</td>
        </tr>)}</tbody>
      </table>
      <p><strong>Total indicatif : {result.total} {result.currency}</strong></p>
      <p className="hint">{result.notice}</p>
      <p className="hint">État : devis non enregistré. Aucun bouton de paiement n'est activé.</p>
    </section>}
  </details>;
}
