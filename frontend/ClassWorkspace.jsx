import React, {useEffect, useId, useLayoutEffect, useRef, useState} from "react";
import {Empty, Field, Loading, Msg, req, useLoad} from "./EnrollmentScreens.jsx";
import {Button, Card, Icon, PageHeader, Status, TableScroll} from "./yem-ui.jsx";

function availableLevels(data) {
  const allowsCycle = code => data.class_management_cycles?.includes(code) ?? true;
  const levels = data.levels.filter(level => level.active && allowsCycle(level.cycle_code));
  const presets = Object.entries(data.class_level_options || {}).filter(([, preset]) =>
    allowsCycle(preset.cycle) && !data.levels.some(level => level.cycle_code === preset.cycle && level.code === preset.code));
  return [
    ...levels.map(level => ({id: level.id, label: `${level.name} (${level.cycle})`, target: {level: level.id}})),
    ...presets.map(([id, preset]) => ({id, label: `${preset.name} (${preset.cycle_name})`, target: {preset: id}})),
  ];
}

function ClassDialog({title, subtitle, busy = false, onClose, children}) {
  const ref = useRef(null);
  const titleId = useId();
  useLayoutEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    dialog.querySelector("input")?.focus();
    return () => dialog.close();
  }, []);
  return <dialog ref={ref} className="ycl-dialog" aria-labelledby={titleId} onCancel={event => {
    event.preventDefault();
    if (!busy) onClose();
  }}>
    <div className="ycl-dialog-head">
      <div><h2 id={titleId}>{title}</h2><p>{subtitle}</p></div>
      <Button className="small" icon="close" ariaLabel="Fermer" disabled={busy} onClick={onClose}/>
    </div>
    {children}
  </dialog>;
}

function CreateClassDialog({schoolId, year, levels, onClose, onCreated}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = form.get("name").trim();
    const level = levels.find(option => option.id === form.get("level"));
    if (!name || !level) {
      setError("Indiquez le nom et le niveau de la classe.");
      return;
    }
    const capacity = form.get("capacity");
    setBusy(true);
    setError("");
    try {
      const result = await req(`schools/${schoolId}/academic/quick-classes`, {
        year: year.id, names: [name], capacity: capacity === "" ? null : Number(capacity), ...level.target,
      });
      onCreated(result.classes[0]);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }
  return <ClassDialog title="Créer une classe" subtitle={year.name} busy={busy} onClose={onClose}>
    <form className="ycl-form" onSubmit={submit} onChange={() => setError("")}>
      <Field label="Nom de la classe" required><input name="name" required maxLength={120} placeholder="Ex. 6e C" disabled={busy}/></Field>
      <Field label="Niveau" required><select name="level" required defaultValue={levels.length === 1 ? levels[0].id : ""} disabled={busy}>
        <option value="" disabled>Choisir le niveau</option>
        {levels.map(level => <option key={level.id} value={level.id}>{level.label}</option>)}
      </select></Field>
      <Field label="Capacité maximale" hint="Facultative"><input name="capacity" type="number" min={1} max={5000} placeholder="Ex. 35" disabled={busy}/></Field>
      <Msg text={error} error/>
      <div className="ycl-dialog-actions">
        <Button onClick={onClose} disabled={busy}>Annuler</Button>
        <Button primary type="submit" icon="check" disabled={busy}>{busy ? "Enregistrement…" : "Enregistrer"}</Button>
      </div>
    </form>
  </ClassDialog>;
}

function ClassRoster({schoolId, year, classroom, onClose, onStudent, canOpenStudentFile}) {
  const roster = useLoad(`schools/${schoolId}/classes/${classroom.id}/students`);
  const students = roster.data?.students;
  return <ClassDialog title={`Élèves de ${classroom.name}`} subtitle={year.name} onClose={onClose}>
    <Loading state={roster}>{students?.length ? <TableScroll label={`Élèves de ${classroom.name}`}>
      <table className="xs"><thead><tr><th>Élève</th><th>Matricule</th></tr></thead>
        <tbody>{students.map(student => <tr key={student.id}>
          <td>{canOpenStudentFile ? <button type="button" className="yf-link" onClick={() => onStudent(student.id)}>{student.last_name} {student.first_name}</button> : <span>{student.last_name} {student.first_name}</span>}</td>
          <td>{student.student_code}</td>
        </tr>)}</tbody>
      </table>
    </TableScroll> : <Empty>Aucun élève inscrit dans cette classe.</Empty>}</Loading>
  </ClassDialog>;
}

export default function ClassWorkspace({schoolId, canReadStudents, canReadRoster = canReadStudents, onNavigate, advancedSettings, workingYearId="", onWorkingYearChange}) {
  const [year, setYear] = useState(workingYearId);
  useEffect(()=>{setYear(workingYearId);setSelected(null);setCreating(false);},[workingYearId,schoolId]);
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState(null);
  const [message, setMessage] = useState("");
  const overview = useLoad(`schools/${schoolId}/overview/classes${year ? `?year=${year}` : ""}`);
  const data = overview.data;
  const currentYear = data?.year;
  const switchingYear = Boolean(year && currentYear && year !== currentYear.id);
  const levels = data?.can_manage_classes ? availableLevels(data) : [];
  const canCreate = currentYear?.active && levels.length > 0;
  const needsSetup = !currentYear || (currentYear.active && data?.can_manage_classes && !levels.length);

  return <>
    <PageHeader title="Classes et niveaux" subtitle="Retrouvez les classes et leurs effectifs par année scolaire." banner={false} actions={<>
      {data?.years.length > 0 && <label className="yd-select plain">
        <select aria-label="Année scolaire" value={year || currentYear?.id || ""} onChange={event => {
          setYear(event.target.value);
          onWorkingYearChange?.(event.target.value);
          setMessage("");
        }}>{data.years.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        <Icon name="chevron" size={18} className="chev"/>
      </label>}
      {advancedSettings}
      {canCreate && <Button primary icon="plus" disabled={switchingYear || overview.loading} onClick={() => setCreating(true)}>Créer une classe</Button>}
    </>}/>
    <Msg text={message}/>
    <Loading state={overview}>{switchingYear ? <p role="status">Chargement de l’année…</p> : data && <>
      {needsSetup && <Card title={currentYear ? "Aucun niveau disponible pour la création" : "Aucune année scolaire"} icon="school">
        {data.can_manage_academic
          ? <Button onClick={() => onNavigate("settings", "classes")}>Ouvrir les paramètres des classes</Button>
          : <Empty>La direction peut compléter la structure scolaire.</Empty>}
      </Card>}
      {!needsSetup && !data.classes.length && <Card title="Aucune classe pour cette année" icon="layers"/>}
      <div className="ycl-grid">{data.classes.map(classroom => {
        const Tile = canReadRoster ? "button" : "div";
        const count = `${classroom.enrolled} élève${classroom.enrolled > 1 ? "s" : ""}`;
        const enrollmentSummary = classroom.capacity == null ? `${count} dans la classe` : `${count} / ${classroom.capacity} places`;
        return <Tile key={classroom.id} className="ycl-tile" {...(canReadRoster ? {
          type: "button", "aria-haspopup": "dialog",
          "aria-label": `${classroom.name}, ${enrollmentSummary}${classroom.active ? "" : ", classe archivée"}. Consulter les élèves`,
          onClick: () => setSelected(classroom),
        } : {})}>
          <span className="ycl-tile-head"><Icon name="layers" size={26}/>{!classroom.active && <Status tone="gray">Archivée</Status>}</span>
          <b>{classroom.name}</b>
          <small>{enrollmentSummary}</small>
          {canReadRoster && <span className="ycl-tile-link">Consulter les élèves <Icon name="chevronright" size={16}/></span>}
        </Tile>;
      })}</div>
    </>}</Loading>
    {creating && <CreateClassDialog schoolId={schoolId} year={currentYear} levels={levels}
      onClose={() => setCreating(false)} onCreated={classroom => {
        setCreating(false);
        setMessage(`Classe « ${classroom.name} » créée.`);
        overview.reload();
      }}/>}
    {selected && <ClassRoster schoolId={schoolId} year={currentYear} classroom={selected}
      onClose={() => setSelected(null)} canOpenStudentFile={canReadStudents} onStudent={student => onNavigate("students", "fiche", {student})}/>}
  </>;
}
