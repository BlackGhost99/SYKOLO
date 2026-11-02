import React, { useEffect, useState } from "react";
import AcademicPanel from "./AcademicPanel.jsx";
import StudentPanel from "./StudentPanel.jsx";
import StaffPanel from "./StaffPanel.jsx";
import CurriculumPanel from "./CurriculumPanel.jsx";
import AssessmentPanel from "./AssessmentPanel.jsx";
import ReportPanel from "./ReportPanel.jsx";
import CouncilPanel from "./CouncilPanel.jsx";

const cookie = () => document.cookie.split("; ").find((x) => x.startsWith("csrftoken="))?.split("=")[1] || "";
async function api(path, data) {
  if (data !== undefined) await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
  const response = await fetch("/api/v1/" + path, {
    method: data === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers: data === undefined ? {} : { "Content-Type": "application/json", "X-CSRFToken": cookie() },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw Error("Service indisponible.");
  const body = await response.json();
  if (!response.ok) throw Error(body.error || "Accès refusé.");
  return body;
}

export default function SchoolPanel() {
  const [organizations, setOrganizations] = useState([]);
  const [schools, setSchools] = useState([]);
  const [selected, setSelected] = useState("");
  const [orgName, setOrgName] = useState("");
  const [schoolName, setSchoolName] = useState("");
  const [orgId, setOrgId] = useState("");
  const [targetUser, setTargetUser] = useState("");
  const [roleCode, setRoleCode] = useState("direction");
  const [roles, setRoles] = useState([]);
  const [configuration, setConfiguration] = useState("");
  const [revision, setRevision] = useState(0);
  const [canEditConfiguration, setCanEditConfiguration] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function reload() {
    const [o, s] = await Promise.all([api("organizations"), api("schools")]);
    setOrganizations(o.organizations || []);
    setSchools(s.schools || []);
    if (!orgId && o.organizations?.length) setOrgId(o.organizations[0].id);
  }

  useEffect(() => { reload().catch((err) => setMessage(err.message)); }, []);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    Promise.all([
      api("schools/" + selected + "/roles").catch(() => ({ roles: [] })),
      api("schools/" + selected + "/settings").catch(() => null),
    ]).then(([r, s]) => {
      if (!active) return;
      setRoles(r.roles || []);
      setCanEditConfiguration(Boolean(s));
      setConfiguration(s ? JSON.stringify(s.effective || {}, null, 2) : "");
      setRevision(s?.layers?.find((x) => Object.keys(x.scope).length === 0)?.revision || 0);
    }).catch((e) => { if (active) setMessage(e.message); });
    return () => { active = false; };
  }, [selected]);

  async function run(action) {
    setBusy(true); setMessage("");
    try { await action(); } catch (err) { setMessage(err.message); }
    finally { setBusy(false); }
  }

  return (
    <section className="card" aria-label="Gestion des établissements" style={{ marginBottom: "1rem" }}>
      <h2>Mes organisations et établissements</h2>
      <p className="hint">Chaque établissement garde ses propres utilisateurs, rôles et paramètres. Un fondateur ne devient pas automatiquement directeur.</p>
      <div className="two">
        <form onSubmit={(e) => { e.preventDefault(); run(async () => {
          const org = await api("organizations", { name: orgName });
          setOrgName(""); await reload(); setOrgId(org.id);
          setMessage("Organisation créée.");
        }); }}>
          <label className="field">Nouvelle organisation
            <input required maxLength={180} value={orgName} onChange={(e) => setOrgName(e.target.value)} />
          </label>
          <button disabled={busy} type="submit">Créer l’organisation</button>
        </form>
        <form onSubmit={(e) => { e.preventDefault(); run(async () => {
          const school = await api("organizations/" + orgId + "/schools", { name: schoolName });
          setSchoolName(""); await reload(); setSelected(school.id);
          setMessage("École créée. Nommez maintenant un directeur.");
        }); }}>
          <label className="field">Organisation propriétaire
            <select required value={orgId} onChange={(e) => setOrgId(e.target.value)}>
              <option value="">Sélectionner…</option>
              {organizations.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </label>
          <label className="field">Nouvel établissement
            <input required maxLength={180} value={schoolName} onChange={(e) => setSchoolName(e.target.value)} />
          </label>
          <button disabled={busy || !orgId} type="submit">Créer l’établissement</button>
        </form>
      </div>
      <label className="field">Établissement actif
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">Choisir une école…</option>
          {schools.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </label>
      {selected && <>
        <form onSubmit={(e) => { e.preventDefault(); run(async () => {
          await api("schools/" + selected + "/members", { username: targetUser, role: roleCode });
          setTargetUser(""); setMessage("Affectation enregistrée pour cette école.");
        }); }}>
          <h3>Affecter un utilisateur existant</h3>
          <label className="field">Identifiant du compte
            <input required value={targetUser} onChange={(e) => setTargetUser(e.target.value)} autoComplete="off" />
          </label>
          <label className="field">Rôle dans cette école
            <select value={roleCode} onChange={(e) => setRoleCode(e.target.value)}>
              {roles.map((r) => <option key={r.id} value={r.code}>{r.label}</option>)}
            </select>
          </label>
          <button disabled={busy || !roles.length} type="submit">Affecter</button>
        </form>
        <div style={{ marginTop: "1rem" }}>
          <h3>Configuration pédagogique institutionnelle</h3>
          {canEditConfiguration ? (
            <form onSubmit={(e) => { e.preventDefault(); run(async () => {
              const values = JSON.parse(configuration);
              const result = await api("schools/" + selected + "/settings", { scope: {}, revision, values });
              setRevision(result.revision);
              setMessage("Paramètres validés et enregistrés.");
            }); }}>
              <p className="hint">Version {revision || "initiale"}. JSON de configuration ; interface métier guidée prévue avec les modules pédagogiques.</p>
              <label className="field">Paramètres de l’école
                <textarea rows={6} value={configuration} onChange={(e) => setConfiguration(e.target.value)} />
              </label>
              <button disabled={busy || configuration.trim() === "{}"} type="submit">Enregistrer les paramètres</button>
            </form>
          ) : <p className="hint">La configuration est réservée aux membres autorisés de l’établissement.</p>}
        </div>
      </>}
      {selected && <AcademicPanel key={selected} schoolId={selected} />}
      {selected && <StudentPanel key={"students-"+selected} schoolId={selected} />}
      {selected && <StaffPanel key={"staff-"+selected} schoolId={selected} />}
      {selected && <CurriculumPanel key={"curriculum-"+selected} schoolId={selected} />}
      {selected && <AssessmentPanel key={"assessments-"+selected} schoolId={selected} />}
      {selected && <ReportPanel key={"reports-"+selected} schoolId={selected} />}
      {selected && <CouncilPanel key={"councils-"+selected} schoolId={selected} />}
      {message && <p role="status" aria-live="polite">{message}</p>}
    </section>
  );
}
