import React, {useEffect, useState} from "react";
import StaffProfessionalDossier from "./StaffProfessionalDossier.jsx";
import PayrollPanel from "./PayrollPanel.jsx";
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
    {data?.families.length > 0 && <Table rowKey={(_,i)=>data.families[i].student_id}
      rowActions={(_,i)=>[{id:"file",label:"Ouvrir le dossier élève",run:()=>onNavigate("students","fiche",{student:data.families[i].student_id})}]} headers={["Élève", "Responsables légaux", "Contact", "Dossier"]}
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

const BASE_CATEGORIES=["Personnel administratif","Enseignants","Autres employés"];
const normalize=value=>String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("fr").trim();
export function suggestedStaffCategory(position){
  const text=normalize(position);
  if(/professeur|enseignant|instituteur|maitresse|educateur|formateur|vacataire/.test(text))return BASE_CATEGORIES[1];
  if(/proviseur|principal|directeur|direction|censeur|secretaire|econome|comptable|surveillant|gestionnaire|responsable|administrati|intendant|caissier/.test(text))return BASE_CATEGORIES[0];
  if(/gardien|securite|entretien|menage|chauffeur|cuisinier|technicien|maintenance|jardinier/.test(text))return BASE_CATEGORIES[2];
  return "À classer";
}

export function StaffDirectory({schoolId,onAdd,onAssign,canReadDossiers=false,canReadPayroll=false,
  canManagePayroll=false,canApprovePayroll=false,canPayPayroll=false,canReversePayroll=false,
  workingYearId="",initialStaffId=""}){
  const [selectedStaff,setSelectedStaff]=useState(initialStaffId);
  const [tab,setTab]=useState("professional");
  const [category,setCategory]=useState("");
  const [search,setSearch]=useState("");
  const [updatedCategories,setUpdatedCategories]=useState({});
  useEffect(()=>{setSelectedStaff(initialStaffId);setTab("professional");},[schoolId,initialStaffId]);
  useEffect(()=>{setUpdatedCategories({});setCategory("");setSearch("");},[schoolId]);
  const {data,error}=useSchoolData("schools/"+schoolId+"/","staff");
  const all=(data?.staff||[]).filter(p=>p.active).map(person=>{
    const explicit=updatedCategories[person.id]??person.category??"";
    return {...person,category:explicit,displayCategory:explicit||suggestedStaffCategory(person.position)};
  });
  const categories=[...new Set([...BASE_CATEGORIES,...all.map(p=>p.displayCategory),"À classer"])];
  const staff=all.filter(person=>(!category||person.displayCategory===category)&&normalize(
    [person.first_name,person.last_name,person.position,person.staff_code,person.displayCategory].join(" ")
  ).includes(normalize(search)));
  const open=(id,nextTab="professional")=>{setSelectedStaff(id);setTab(nextTab);};
  const close=()=>{setSelectedStaff("");setTab("professional");};
  const selected=all.find(p=>p.id===selectedStaff);
  if(canReadDossiers&&selectedStaff)return <section aria-label="Fiche individuelle du personnel">
    <Card title={selected?selected.first_name+" "+selected.last_name:"Fiche individuelle"} icon="idcard">
      <div className="actions">
        <Button onClick={close}>Retour au personnel</Button>
        <Button primary={tab==="professional"} onClick={()=>setTab("professional")}>Fiche professionnelle</Button>
        {canReadPayroll&&<Button primary={tab==="payroll"} onClick={()=>setTab("payroll")}>Rémunérations et versements</Button>}
      </div>
    </Card>
    {tab==="professional"&&<StaffProfessionalDossier key={selectedStaff} schoolId={schoolId} staffId={selectedStaff}
      onUpdated={profile=>setUpdatedCategories(old=>({...old,[selectedStaff]:profile.category||""}))}/>}
    {tab==="payroll"&&canReadPayroll&&<PayrollPanel key={schoolId+":"+selectedStaff+":"+workingYearId}
      schoolId={schoolId} staffId={selectedStaff} workingYearId={workingYearId}
      canManage={canManagePayroll} canApprove={canApprovePayroll} canPay={canPayPayroll} canReverse={canReversePayroll}/>}
  </section>;
  return <Card title="Personnel de l’établissement" icon="idcard">
    <div className="actions">
      {onAdd&&<Button primary icon="adduser" onClick={onAdd}>Ajouter un collaborateur</Button>}
      {onAssign&&<Button onClick={onAssign}>Affecter à une classe</Button>}
    </div>
    {error&&<p role="alert">{error}</p>}
    {!data&&!error&&<p role="status">Chargement du personnel…</p>}
    {data&&<>
      <div className="two">
        <label className="field">Rechercher un nom ou une fonction
          <input type="search" value={search} onChange={event=>setSearch(event.target.value)}/>
        </label>
        <label className="field">Catégorie du personnel
          <select value={category} onChange={event=>setCategory(event.target.value)}>
            <option value="">Tout le personnel ({all.length})</option>
            {categories.map(c=><option key={c} value={c}>{c} ({all.filter(p=>p.displayCategory===c).length})</option>)}
          </select>
        </label>
      </div>
      <p className="hint">Les catégories suggérées à partir des postes existants restent à confirmer dans la fiche professionnelle.</p>
      {!staff.length?<p>Aucun collaborateur pour ce filtre.</p>:<Table rowKey={(_,i)=>staff[i].id}
        rowActions={(_,i)=>canReadDossiers?[{id:"file",label:"Consulter la fiche professionnelle",run:()=>open(staff[i].id)},
          ...(canReadPayroll?[{id:"payroll",label:"Rémunérations et versements",run:()=>open(staff[i].id,"payroll")}]:[])]:[]}
        headers={["Nom","Poste","Catégorie","Matricule","Accès YEM","Fiche technique"]}
        rows={staff.map(person=>[
          <span className="yd-staff-person">
            {person.photo_url?<img className="yd-staff-avatar" src={person.photo_url} alt={"Photo de "+person.first_name+" "+person.last_name} loading="lazy"/>:
              <span className="yd-staff-avatar empty" aria-hidden="true">●</span>}
            <span>{canReadDossiers?<button className="yd-btn small" type="button" onClick={()=>open(person.id)}>{person.first_name} {person.last_name}</button>:
              <strong>{person.first_name} {person.last_name}</strong>}
              {person.presentation&&<small style={{display:"block"}}>{person.presentation}</small>}
            </span>
          </span>,
          person.position,<span>{person.displayCategory}{!person.category&&person.displayCategory!=="À classer"&&<small style={{display:"block"}}>À confirmer</small>}</span>,person.staff_code,
          <Status tone={person.account_id?"green":"gray"}>{person.account_id?"Compte lié":"Sans compte"}</Status>,
          canReadDossiers?<Button className="small" onClick={()=>open(person.id)}>Consulter la fiche</Button>:"Accès réservé",
        ])}/>}
    </>}
  </Card>;
}
