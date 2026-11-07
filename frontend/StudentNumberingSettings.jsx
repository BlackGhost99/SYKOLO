import React, {useEffect, useState} from "react";
import {req} from "./EnrollmentScreens.jsx";
import {Button, Card, PageHeader} from "./yem-ui.jsx";

const initialForm = result => ({
  enabled: result.enabled,
  template: result.template,
  digits: result.digits,
  start_number: result.next_number ?? 1,
  revision: result.revision,
});

export default function StudentNumberingSettings({schoolId, tabs}) {
  const path = `schools/${schoolId}/student-numbering`;
  const [form, setForm] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    req(path).then(result => {
      if (!active) return;
      setForm(initialForm(result));
      setPreview(result);
    }).catch(error => {if (active) setMessage(error.message);});
    return () => {active = false;};
  }, [path]);

  function change(values) {
    setForm(current => ({...current, ...values}));
    setPreview(null);
    setMessage("");
  }

  async function submit(method) {
    setBusy(true);
    setMessage("");
    try {
      const result = await req(path, {...form, digits: Number(form.digits), start_number: Number(form.start_number)}, method);
      setPreview(result);
      if (method === "PUT") {
        setForm(initialForm(result));
        setMessage("Règle enregistrée. Elle s’applique aux prochains matricules.");
      }
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return <>
    <PageHeader title="Matricules des élèves" subtitle="Configurez l’attribution des prochains matricules de votre établissement." banner={false}/>
    {tabs}
    <div className="yd-real-body">
      <Card title="Attribution du matricule local" icon="idcard">
        <p className="hint">Les matricules déjà attribués ou importés sont conservés. L’identifiant permanent YEM sert au suivi entre établissements.</p>
        {message && <p role="status" className="yd-form-msg">{message}</p>}
        {form && <form onSubmit={event => {
          event.preventDefault();
          submit(event.nativeEvent.submitter?.value === "save" ? "PUT" : "POST");
        }}>
          <label className="field">Mode d’attribution
            <select value={form.enabled ? "series" : "yem"} onChange={event => change({enabled: event.target.value === "series"})}>
              <option value="yem">Utiliser l’identifiant automatique YEM</option>
              <option value="series">Poursuivre une série de l’établissement</option>
            </select>
          </label>
          {form.enabled && <div className="two">
            <label className="field">Format du matricule
              <input required maxLength={38} value={form.template} onChange={event => change({template: event.target.value, start_number: 1})}/>
              <small>Placez {"{n}"} à l’endroit du numéro. Exemples : {"{n}"}, {"{n}/A"}, {"ÉL-{n}-2026"}.</small>
            </label>
            <label className="field">Nombre minimal de chiffres
              <input required type="number" min={1} max={15} value={form.digits} onChange={event => change({digits: event.target.value})}/>
            </label>
            <label className="field">Prochain numéro souhaité
              <input required type="number" min={0} max={999999999999999} value={form.start_number} onChange={event => change({start_number: event.target.value})}/>
              <small>YEM avance au-delà des numéros reconnus et des numéros déjà réservés pour cette série.</small>
            </label>
          </div>}
          {preview?.enabled && <p aria-live="polite">
            Plus grand numéro reconnu : <strong>{preview.largest_number ?? "aucun"}</strong><br/>
            Prochain matricule proposé : <strong>{preview.next_code ?? "série épuisée"}</strong>
          </p>}
          <div className="actions">
            {form.enabled && <Button type="submit" disabled={busy}>Vérifier la série</Button>}
            <button type="submit" value="save" disabled={busy}>Enregistrer la règle</button>
          </div>
        </form>}
      </Card>
    </div>
  </>;
}
