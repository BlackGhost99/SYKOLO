import React, {useEffect, useState} from "react";

export default function SchoolConductPanel({path, request}) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [enrollment, setEnrollment] = useState("");
  const [date, setDate] = useState("");
  const [kind, setKind] = useState("observation");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setError("");
    request(path).then(result => { if (active) setData(result); })
      .catch(failure => { if (active) setError(failure.message); });
    return () => { active = false; };
  }, [open, path, request]);

  async function run(action) {
    setBusy(true);
    setError("");
    setStatus("");
    try { await action(); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }

  return <details onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Comportement et discipline</summary>
    {open && !data && !error && <p role="status">Chargement des communications…</p>}
    {error && <p role="alert">{error}</p>}
    {status && <p role="status">{status}</p>}
    {data?.can_publish && data.roster.length > 0 && <form onSubmit={event => {
      event.preventDefault();
      run(async () => {
        const published = await request(path, {enrollment, date, kind, message});
        setData(previous => ({...previous, notices: [published, ...previous.notices.filter(row => row.id !== published.id)]}));
        setMessage("");
        setStatus("Communication publiée dans la fiche parent de l’élève.");
      });
    }}>
      <div className="two">
        <label className="field">Élève concerné
          <select required value={enrollment} disabled={busy} onChange={event => setEnrollment(event.target.value)}>
            <option value="">Choisir un élève…</option>
            {data.roster.map(row => <option key={row.id} value={row.id}>{row.name} · {row.matricule}</option>)}
          </select>
        </label>
        <label className="field">Date de l’événement
          <input type="date" required value={date} disabled={busy} onChange={event => setDate(event.target.value)}/>
        </label>
      </div>
      <label className="field">Type de communication
        <select value={kind} disabled={busy} onChange={event => setKind(event.target.value)}>
          <option value="observation">Observation de comportement</option>
          <option value="sanction">Sanction</option>
        </select>
      </label>
      <label className="field">Message aux responsables légaux
        <textarea required maxLength={500} value={message} disabled={busy} onChange={event => setMessage(event.target.value)}/>
      </label>
      <button type="submit" disabled={busy || !message.trim()}>Publier aux parents</button>
    </form>}
    {data && (data.notices.length > 0 ? <ul>{data.notices.map(row => <li key={row.id}>
      <strong>{row.student}</strong> · {row.date} · {row.label}{row.withdrawn ? " · Retirée" : ""}
      <p>{row.message}</p>
      {!row.withdrawn && data.can_withdraw && <button type="button" disabled={busy} onClick={() => run(async () => {
        const withdrawn = await request(path + "/" + row.id + "/withdraw", {});
        setData(previous => ({...previous, notices: previous.notices.map(item => item.id === row.id ? withdrawn : item)}));
        setStatus("Communication retirée de la fiche parent.");
      })}>Retirer de la fiche parent</button>}
    </li>)}</ul> : <p>Aucune communication enregistrée pour cette classe.</p>)}
  </details>;
}
