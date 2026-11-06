import React, {useEffect, useRef, useState} from "react";
import {req} from "./EnrollmentScreens.jsx";
import {Button, Card, Status, TableScroll} from "./yem-ui.jsx";

const MODELS = {
  "Maternelle": ["Langage", "Activités artistiques", "Motricité", "Découverte du monde"],
  "Primaire": ["Français", "Mathématiques", "Sciences", "Histoire-Géographie", "Éducation physique"],
  "Secondaire": ["Français", "Mathématiques", "Anglais", "Histoire-Géographie", "Sciences de la vie et de la Terre", "Physique-Chimie", "Éducation physique"],
};
const namesFrom = text => text.split(/[,;\n]/).map(name => name.trim()).filter(Boolean);
const codeFrom = (name, fallback) => name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
  .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 50) || fallback;

export default function CurriculumPanel({schoolId}) {
  const base = `schools/${schoolId}/`;
  const [data, setData] = useState(null);
  const [classroom, setClassroom] = useState("");
  const [names, setNames] = useState("");
  const [editing, setEditing] = useState(null);
  const editor = useRef(null);
  const [course, setCourse] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function load() {
    const [catalog, program, years, classes] = await Promise.all(
      ["subjects", "courses", "academic/years", "academic/classes"].map(path => req(base + path)),
    );
    return {...catalog, ...program, ...years, ...classes};
  }
  useEffect(() => {
    let active = true;
    load().then(result => {if (active) setData(result);})
      .catch(error => {if (active) setMessage(error.message);});
    return () => {active = false;};
  }, [schoolId]);

  useEffect(() => {
    if (editing) editor.current?.scrollIntoView?.({block: "nearest"});
  }, [editing?.item.id, editing?.kind]);

  async function run(operation) {
    setBusy(true);
    setMessage("");
    try {
      setMessage(await operation());
      setData(await load());
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }
  function edit(kind, item) {
    setMessage("");
    setEditing({kind, item: {...item}});
  }
  function change(key, value) {
    setEditing(old => ({...old, item: {...old.item, [key]: value}}));
  }
  const classOptions = data?.classes.map(row => {
    const year = data.years.find(y => y.id === row.year);
    return {...row, yearName: year?.name, available: row.active && year?.active};
  }) || [];
  const activeClasses = classOptions.filter(row => row.available);
  const currentClass = classOptions.find(row => row.id === classroom) || (activeClasses.length === 1 ? activeClasses[0] : null);
  const rows = data?.courses.filter(row => row.classroom === currentClass?.id) || [];
  const selectedCourse = rows.find(row => row.id === course);
  const subjects = new Map(data?.subjects.map(row => [row.id, row]));
  const isSubject = editing?.kind === "subjects";
  const draft = editing?.item;
  const path = draft && `${base}${editing.kind}${draft.id ? "/" + draft.id : ""}`;

  return <section aria-label="Matières et programmes">
    <Card title="Matières par classe" icon="school" subtitle="Choisissez une classe pour ajouter ou modifier ses matières.">
      {message && !editing && <p role="status" className="yd-form-msg">{message}</p>}
      {!data ? <p>{message ? "La liste n’a pas pu être chargée." : "Chargement…"}</p> : <>
        <label className="field">Classe
          <select value={currentClass?.id || ""} onChange={event => {setClassroom(event.target.value); setEditing(null); setCourse(""); setNames(""); setMessage("");}}>
            <option value="">Choisir une classe…</option>
            {classOptions.map(row => <option key={row.id} value={row.id}>{row.name} · {row.yearName}{row.available ? "" : " (archivée)"}</option>)}
          </select>
        </label>
        {classOptions.length === 0 && <p>Créez d’abord une classe dans l’onglet Classes.</p>}
        {data.can_manage && currentClass?.available && <form onSubmit={event => {
          event.preventDefault();
          run(async () => {
            const result = await req(base + "courses/generate", {classroom: currentClass.id, names: namesFrom(names)});
            setNames("");
            return [`${result.created.length} matière(s) ajoutée(s).`,
              result.existing.length ? `${result.existing.length} déjà présente(s).` : "",
              result.archived.length ? `Archivée(s), à réactiver si besoin · ${result.archived.join(", ")}.` : "",
            ].filter(Boolean).join(" ");
          });
        }}>
          <label className="field">Matières à ajouter
            <textarea required rows={4} value={names} onChange={event => setNames(event.target.value)} placeholder={"Français\nMathématiques"}/>
          </label>
          <div className="yf-inline-form">
            <label className="field">Liste de départ (facultative)
              <select value="" onChange={event => {
                const model = MODELS[event.target.value];
                if (model) setNames(old => [...new Set([...namesFrom(old), ...model])].join("\n"));
              }}>
                <option value="">Proposer des matières…</option>
                {Object.keys(MODELS).map(model => <option key={model}>{model}</option>)}
              </select>
            </label>
            <Button primary type="submit" disabled={busy || !namesFrom(names).length || namesFrom(names).length > 30}>Ajouter les matières</Button>
          </div>
          <p className="hint">Un nom par ligne. Les listes proposées sont modifiables et les nouvelles matières démarrent avec un coefficient de 1.</p>
        </form>}
        {currentClass && <>
          <h3>Matières de {currentClass.name}</h3>
          {rows.length === 0 ? <p>Aucune matière dans cette classe.</p> :
            <TableScroll label="Matières de la classe"><table><thead><tr><th>Matière</th><th>Coefficient</th><th>Statut</th><th>Actions</th></tr></thead>
              <tbody>{rows.map(row => {
                const subject = subjects.get(row.subject);
                return <tr key={row.id}><td>{subject?.name || "Matière"}</td><td>{Number(row.coefficient)}</td>
                  <td><Status tone={row.active ? "green" : "gray"}>{row.active ? "Active" : "Archivée"}</Status></td>
                  <td>{data.can_manage && <button type="button" onClick={() => edit("courses", row)}>Modifier</button>}{" "}
                    <button type="button" aria-expanded={course === row.id} onClick={() => setCourse(course === row.id ? "" : row.id)}>Programme</button></td></tr>;
              })}</tbody>
            </table></TableScroll>}
        </>}
      </>}
    </Card>
    {draft && <Card title={isSubject ? (draft.id ? "Modifier la matière du catalogue" : "Créer une matière dans le catalogue") : "Modifier la matière dans cette classe"} icon="file">
      {message && <p role="status" className="yd-form-msg">{message}</p>}
      <form ref={editor} onSubmit={event => {
        event.preventDefault();
        run(async () => {
          const values = isSubject
            ? {name: draft.name, description: draft.description, active: draft.active}
            : {coefficient: draft.coefficient, active: draft.active};
          await req(path, draft.id ? {...values, revision: draft.revision} : {...values, code: draft.code || codeFrom(draft.name, "matiere")}, draft.id ? "PATCH" : "POST");
          setEditing(null);
          return "Modification enregistrée.";
        });
      }}>
        {isSubject ? <>
          <label className="field">Nom de la matière<input required maxLength={120} value={draft.name} onChange={e => change("name", e.target.value)}/></label>
          <label className="field">Description<textarea maxLength={500} value={draft.description} onChange={e => change("description", e.target.value)}/></label>
        </> : <label className="field">Coefficient<input required type="number" min="0.001" max="1000" step="0.001" value={draft.coefficient} onChange={e => change("coefficient", e.target.value)}/></label>}
        <label className="field">Statut<select value={draft.active ? "active" : "archived"} onChange={e => change("active", e.target.value === "active")}>
          <option value="active">Active</option><option value="archived">Archivée</option>
        </select></label>
        <div className="yf-inline-form">
          <Button primary type="submit" disabled={busy}>Enregistrer</Button>
          <Button type="button" disabled={busy} onClick={() => setEditing(null)}>Annuler</Button>
          {!isSubject && subjects.has(draft.subject) && <Button type="button" disabled={busy}
            onClick={() => edit("subjects", subjects.get(draft.subject))}>Renommer dans toutes les classes</Button>}
          {draft.id && <Button type="button" disabled={busy} onClick={() => {
            if (!window.confirm(isSubject ? `Supprimer « ${subjects.get(draft.id)?.name} » du catalogue ?` : "Retirer définitivement cette matière de la classe ?")) return;
            run(async () => {
              await req(path, {revision: draft.revision}, "DELETE");
              setEditing(null);
              return "Matière supprimée.";
            });
          }}>{isSubject ? "Supprimer du catalogue" : "Retirer de la classe"}</Button>}
        </div>
      </form>
    </Card>}
    {selectedCourse && <CourseProgram key={selectedCourse.id} base={base} course={selectedCourse} title={subjects.get(selectedCourse.subject)?.name} canManage={data.can_manage}/>}
    {data && <Card title="Catalogue de l’établissement" icon="file">
      <details>
        <summary>Voir les matières et leurs noms</summary>
        <p className="hint">Un nom modifié ici est repris par toutes les classes qui utilisent la matière.</p>
        {data.can_manage && <Button type="button" onClick={() => edit("subjects", {name: "", description: "", active: true})}>Créer une matière au catalogue</Button>}
        <ul>{data.subjects.map(row => <li key={row.id}>{row.name}{row.active ? "" : " (archivée)"}{" "}
          {data.can_manage && <button type="button" aria-label={`Modifier ${row.name} dans le catalogue`} onClick={() => edit("subjects", row)}>Modifier</button>}
        </li>)}</ul>
      </details>
    </Card>}
  </section>;
}

const blankUnit = {title: "", objectives: "", active: true};

function CourseProgram({base, course, title, canManage}) {
  const path = `${base}courses/${course.id}/`;
  const [data, setData] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [draft, setDraft] = useState(blankUnit);
  const [instructor, setInstructor] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    req(path + "units").then(result => {if (active) setData(result);}).catch(e => {if (active) setMessage(e.message);});
    if (canManage) req(base + "staff-assignments").then(result => {
      if (active) setAssignments(result.assignments.filter(row => row.active && row.classroom === course.classroom));
    }).catch(() => {});
    return () => {active = false;};
  }, [path, canManage, base, course.classroom]);
  async function run(action) {
    setBusy(true);
    setMessage("");
    try {
      await action();
      setData(await req(path + "units"));
      setMessage("Enregistré.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }
  return <Card title={`Programme · ${title || "Matière"}`} icon="file">
    {message && <p role="status">{message}</p>}
    {data && <>
      <ul>{data.units.map(row => <li key={row.id}>{row.title}{row.active ? "" : " (archivée)"}{" "}
        {data.can_manage && <button type="button" onClick={() => setDraft(row)}>Modifier l’unité</button>}
      </li>)}</ul>
      {data.can_manage && <form onSubmit={event => {
        event.preventDefault();
        run(async () => {
          const values = {title: draft.title, objectives: draft.objectives, active: draft.active};
          if (draft.id) await req(path + "units/" + draft.id, {...values, revision: draft.revision}, "PATCH");
          else await req(path + "units", {...values, code: codeFrom(draft.title, "unite")});
          setDraft(blankUnit);
        });
      }}>
        <label className="field">Titre de l’unité<input required maxLength={180} value={draft.title} onChange={e => setDraft({...draft, title: e.target.value})}/></label>
        <label className="field">Objectifs<textarea maxLength={2000} value={draft.objectives} onChange={e => setDraft({...draft, objectives: e.target.value})}/></label>
        {draft.id && <label><input type="checkbox" checked={draft.active} onChange={e => setDraft({...draft, active: e.target.checked})}/> Unité active</label>}
        <div className="yf-inline-form"><Button type="submit" disabled={busy}>{draft.id ? "Enregistrer l’unité" : "Ajouter l’unité"}</Button>
          {draft.id && <Button type="button" onClick={() => setDraft(blankUnit)}>Annuler</Button>}</div>
      </form>}
    </>}
    {canManage && assignments.length > 0 && <form onSubmit={event => {
      event.preventDefault();
      run(async () => {await req(path + "instructors", {staff_assignment: instructor}); setInstructor("");});
    }}>
      <label className="field">Enseignant affecté à cette classe<select required value={instructor} onChange={e => setInstructor(e.target.value)}>
        <option value="">Choisir…</option>
        {assignments.map(row => <option key={row.id} value={row.id}>{row.duty} · {row.staff.slice(0, 8)}</option>)}
      </select></label>
      <Button type="submit" disabled={busy}>Associer au cours</Button>
    </form>}
  </Card>;
}
