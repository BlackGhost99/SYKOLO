import React, {useEffect, useState} from "react";
import {ClassField, useSchoolData} from "./SchoolSettings.jsx";
import {Button, Card, Status, Table} from "./yem-ui.jsx";
import "./school-staff-photos.css";

export function FamilyDirectory({schoolId, onNavigate, workingYearId = ""}) {
  const root = "schools/" + schoolId + "/";
  const {data, error} = useSchoolData(root, "academic/years academic/classes");
  const [room, setRoom] = useState("");
  useEffect(() => setRoom(""), [schoolId, workingYearId]);
  const classes = (data?.classes || []).filter(item => !workingYearId || item.year === workingYearId);
  return <>
    <Card title="Parents par classe" icon="users" subtitle="Retrouvez les responsables légaux enregistrés dans le dossier de chaque élève.">
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Chargement des classes…</p>}
      {data && <ClassField classes={classes} years={data.years} value={room} onChange={setRoom}/>}
      {data && classes.length === 0 && <p>Aucune classe disponible pour cette année scolaire.</p>}
    </Card>
    {room && <ClassFamilies key={room} root={root} room={room} onNavigate={onNavigate}/>}
  </>;
}

function ClassFamilies({root, room, onNavigate}) {
  const {data, error} = useSchoolData(root, "guardians-by-class?classroom=" + encodeURIComponent(room));
  return <Card title="Élèves et responsables légaux" icon="users">
    {error && <p role="alert">{error}</p>}
    {!data && !error && <p role="status">Chargement des familles…</p>}
    {data?.families.length === 0 && <p>Aucun élève inscrit dans cette classe.</p>}
    {data?.families.length > 0 && <Table headers={["Élève", "Responsables légaux", "Contact", "Dossier"]}
      rows={data.families.map(student => [
        student.student_name,
        student.guardians.length ? student.guardians.map(guardian => <div key={guardian.id}>
          {guardian.name}{guardian.relationship && " · " + guardian.relationship}
        </div>) : "Aucun responsable renseigné",
        student.guardians.map(guardian => <div key={guardian.id}>
          {[guardian.phone, guardian.email].filter(Boolean).join(" · ") || "—"}
        </div>),
        <Button className="small" ariaLabel={"Ouvrir la fiche de " + student.student_name} onClick={() =>
          onNavigate("students", "fiche", {student: student.student_id})}>Ouvrir la fiche</Button>,
      ])}/>}
  </Card>;
}

export function StaffDirectory({schoolId, onAdd, onAssign}) {
  const {data, error} = useSchoolData("schools/" + schoolId + "/", "staff");
  const [search, setSearch] = useState("");
  const query = search.trim().toLocaleLowerCase("fr");
  const staff = data?.staff.filter(person =>
    person.active && [person.first_name, person.last_name, person.position, person.staff_code]
      .join(" ").toLocaleLowerCase("fr").includes(query)) || [];
  return <Card title="Personnel de l’établissement" icon="idcard">
    <div className="actions">
      {onAdd && <Button primary icon="adduser" onClick={onAdd}>Ajouter un collaborateur</Button>}
      {onAssign && <Button onClick={onAssign}>Affecter à une classe</Button>}
    </div>
    {error && <p role="alert">{error}</p>}
    {!data && !error && <p role="status">Chargement du personnel…</p>}
    {data && <>
      <label className="field">Rechercher un nom ou une fonction
        <input type="search" value={search} onChange={event => setSearch(event.target.value)}/>
      </label>
      {staff.length === 0 ? <p>{query ? "Aucun résultat pour cette recherche." : "Aucun collaborateur enregistré."}</p> :
        <Table headers={["Nom", "Poste", "Matricule", "Accès YEM"]} rows={staff.map(person => [
          <span className="yd-staff-person">
            {person.photo_url?<img className="yd-staff-avatar" src={person.photo_url} alt={"Photo de "+person.first_name+" "+person.last_name} loading="lazy"/>:
              <span className="yd-staff-avatar empty" aria-hidden="true">●</span>}
            <span><strong>{person.first_name} {person.last_name}</strong>
              {person.presentation&&<small style={{display:"block"}}>{person.presentation}</small>}
            </span>
          </span>, person.position, person.staff_code,
          <Status tone={person.account_id ? "green" : "gray"}>{person.account_id ? "Compte lié" : "Sans compte"}</Status>,
        ])}/>}
    </>}
  </Card>;
}
