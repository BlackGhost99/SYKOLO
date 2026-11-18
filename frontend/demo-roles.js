// Profils fictifs alignés sur les modèles de rôles de backend/institutions/services.py.
export const DEMO_ROLES = {
  platform: {label: "Super-administrateur", permissions: []},
  proprietaire: {label: "Propriétaire de l’établissement", permissions: [
    "school.view", "school.members.read", "school.members.write", "school.roles.read",
    "school.roles.manage", "school.audit.read",
  ]},
  direction: {label: "Directeur / Directrice", permissions: [
    "school.academic.manage", "school.academic.read", "school.admissions.decide", "school.admissions.enroll",
    "school.admissions.manage", "school.admissions.read", "school.assessments.manage", "school.assessments.read",
    "school.attendance.assigned", "school.attendance.finalize", "school.attendance.read", "school.attendance.write",
    "school.audit.read", "school.classes.manage", "school.curriculum.manage", "school.curriculum.read",
    "school.deliberations.finalize", "school.deliberations.manage", "school.deliberations.read", "school.finance.approve",
    "school.finance.read", "school.members.read", "school.members.write", "school.organization.manage",
    "school.organization.read", "school.parents.manage", "school.reports.amend", "school.reports.manage",
    "school.reports.publish", "school.reports.read", "school.roles.manage", "school.roles.read",
    "school.settings.read", "school.settings.write", "school.staff.manage", "school.staff.read",
    "school.students.manage", "school.students.read",
    "school.students.profile.read", "school.students.admin.write", "school.students.sensitive.read", "school.students.finance.read", "school.timetable.manage", "school.timetable.read",
    "school.view",
  ]},
  secretariat: {label: "Secrétariat", permissions: [
    "school.view", "school.members.read", "school.settings.read", "school.academic.read",
    "school.students.read", "school.students.manage", "school.admissions.read", "school.admissions.manage",
    "school.students.profile.read", "school.students.admin.write", "school.students.sensitive.read",
    "school.admissions.enroll", "school.staff.read", "school.staff.manage", "school.organization.read",
    "school.curriculum.read", "school.curriculum.manage", "school.reports.read", "school.deliberations.read",
    "school.attendance.read", "school.attendance.write", "school.timetable.read", "school.timetable.manage",
  ]},
  enseignant: {label: "Enseignant", permissions: [
    "school.view", "school.settings.read", "school.academic.read", "school.curriculum.read",
    "school.timetable.read", "school.attendance.assigned",
  ]},
  comptabilite: {label: "Comptabilité", permissions: [
    "school.view", "school.students.finance.read", "school.academic.read", "school.finance.read",
    "school.finance.approve", "school.finance.reverse",
  ]},
  econome: {label: "Économe / Caissier", permissions: [
    "school.view", "school.students.finance.read", "school.academic.read", "school.finance.read",
    "school.finance.receive", "school.finance.deposit",
  ]},
  tarification: {label: "Responsable des tarifs", permissions: [
    "school.view", "school.finance.read", "school.finance.manage",
  ]},
  parent: {label: "Parent d’élève", permissions: [
    "school.view",
  ]},
};

const studies=["school.view","school.academic.read","school.curriculum.read","school.curriculum.manage","school.staff.read","school.timetable.read","school.timetable.manage","school.assessments.read","school.reports.read","school.deliberations.read"];
const attendance=["school.view","school.academic.read","school.attendance.read","school.attendance.write"];
Object.assign(DEMO_ROLES,{
 proviseur:{...DEMO_ROLES.direction,label:"Proviseur"},
 principal:{...DEMO_ROLES.direction,label:"Principal"},
 etudes:{label:"Censeur des études",permissions:studies},
 censeur_principal:{label:"Censeur principal",permissions:[...studies,"school.attendance.read"]},
 vie_scolaire:{label:"Censeur de la vie scolaire",permissions:[...attendance,"school.attendance.finalize"]},
 surveillance_generale:{label:"Surveillant général",permissions:attendance},
 surveillance:{label:"Surveillant",permissions:["school.view","school.academic.read","school.attendance.assigned"]},
 secretariat_pedagogique:{label:"Secrétaire pédagogique",permissions:["school.view","school.academic.read","school.students.read","school.students.profile.read","school.curriculum.read","school.timetable.read","school.assessments.read","school.reports.read"]},
 chef_travaux:{label:"Chef de travaux",permissions:["school.view","school.academic.read","school.curriculum.read"]}
});
