/* Données exclusivement fictives. Cette couche n'importe ni session ni API YEM. */
export const demoSchools = [
  {id:"lycee",name:"Lycée Démonstration de Libreville",type:"Collège / Lycée",city:"Libreville",
   levels:["6e","5e","4e","3e","2nde","1ère","Tle"],head:"Mme N. Obame",fee:75000},
  {id:"primaire",name:"École Primaire Démonstration",type:"Primaire",city:"Owendo",
   levels:["1ère année","2e année","3e année","4e année","5e année"],head:"M. A. Mba",fee:45000},
  {id:"maternelle",name:"Maternelle Démonstration",type:"Maternelle",city:"Akanda",
   levels:["Petite section","Moyenne section","Grande section"],head:"Mme B. Nguema",fee:35000},
];
const SEED_STUDENTS = [
  {id:"s1",school:"lycee",name:"Essono Grâce",level:"6e A",guardian:"Mme Essono",phone:"+241 06 00 00 01",status:"Inscrit",average:14.5,absences:1},
  {id:"s2",school:"lycee",name:"Minko Alain",level:"5e B",guardian:"M. Minko",phone:"+241 06 00 00 02",status:"Inscrit",average:12.2,absences:2},
  {id:"s3",school:"lycee",name:"Nze Carine",level:"3e A",guardian:"Mme Nze",phone:"+241 06 00 00 03",status:"Inscrit",average:15.1,absences:0},
  {id:"s4",school:"primaire",name:"Mba Junior",level:"4e année A",guardian:"Mme Essono",phone:"+241 06 00 00 01",status:"Inscrit",average:16.0,absences:0},
  {id:"s5",school:"primaire",name:"Biyogo Sarah",level:"2e année B",guardian:"M. Biyogo",phone:"+241 06 00 00 04",status:"Inscrit",average:13.3,absences:1},
  {id:"s6",school:"maternelle",name:"Onguene Léa",level:"Moyenne section A",guardian:"Mme Onguene",phone:"+241 06 00 00 05",status:"Inscrit",average:null,absences:0},
  {id:"s7",school:"maternelle",name:"Mba Alicia",level:"Grande section A",guardian:"Mme Essono",phone:"+241 06 00 00 01",status:"Inscrit",average:null,absences:1},
];
const SEED_APPLICATIONS = [
  {id:"a1",school:"lycee",name:"Obame David",level:"6e",route:"orientation",status:"En étude",eligible:false,documents:false,origin:"École primaire de départ"},
  {id:"a2",school:"lycee",name:"Ntsame Chloé",level:"2nde",route:"concours",status:"En étude",eligible:false,documents:false,origin:"Collège précédent"},
  {id:"a3",school:"primaire",name:"Mengue Paul",level:"3e année",route:"direct",status:"En attente",eligible:true,documents:true,origin:""},
  {id:"a4",school:"maternelle",name:"Nze Emma",level:"Petite section",route:"direct",status:"En étude",eligible:true,documents:true,origin:""},
];
const SEED_INVOICES = [
  {id:"f1",student:"s1",school:"lycee",label:"Scolarité — trimestre 2",total:75000,paid:0},
  {id:"f2",student:"s1",school:"lycee",label:"Cantine — trimestre 2",total:25000,paid:0},
  {id:"f3",student:"s2",school:"lycee",label:"Scolarité — trimestre 2",total:75000,paid:50000},
  {id:"f4",student:"s3",school:"lycee",label:"Scolarité — trimestre 2",total:75000,paid:75000},
  {id:"f5",student:"s4",school:"primaire",label:"Scolarité — trimestre 2",total:45000,paid:0},
  {id:"f6",student:"s5",school:"primaire",label:"Frais scolaires — trimestre 2",total:45000,paid:30000},
  {id:"f7",student:"s6",school:"maternelle",label:"Scolarité — trimestre 2",total:35000,paid:0},
  {id:"f8",student:"s7",school:"maternelle",label:"Scolarité — trimestre 2",total:35000,paid:35000},
];
const SEED_CLASSES = [
  {id:"c1",school:"lycee",name:"6e A",capacity:40},
  {id:"c2",school:"lycee",name:"5e B",capacity:38},
  {id:"c3",school:"lycee",name:"3e A",capacity:36},
  {id:"c4",school:"primaire",name:"4e année A",capacity:32},
  {id:"c5",school:"primaire",name:"2e année B",capacity:34},
  {id:"c6",school:"maternelle",name:"Moyenne section A",capacity:25},
  {id:"c7",school:"maternelle",name:"Grande section A",capacity:25},
];
const SEED_STAFF = [
  {id:"p1",school:"lycee",name:"Mme N. Obame",role:"Proviseur"},
  {id:"p2",school:"lycee",name:"M. A. Nzeng",role:"Censeur des études"},
  {id:"p3",school:"lycee",name:"Mme C. Mba",role:"Enseignant"},
  {id:"p4",school:"primaire",name:"M. A. Mba",role:"Directeur"},
  {id:"p5",school:"primaire",name:"Mme R. Ekua",role:"Enseignant"},
  {id:"p6",school:"maternelle",name:"Mme B. Nguema",role:"Directrice"},
  {id:"p7",school:"maternelle",name:"Mme P. Ella",role:"Éducatrice"},
];
export const ROUTE_LABELS = {direct:"Inscription directe",concours:"Concours / test",orientation:"Affectation / orientation"};
export function createDemoState(){
  return {
    schools:demoSchools.map(s=>({...s,levels:[...s.levels]})),
    students:SEED_STUDENTS.map(s=>({...s})),
    applications:SEED_APPLICATIONS.map(a=>({...a})),
    invoices:SEED_INVOICES.map(f=>({...f})),
    classes:SEED_CLASSES.map(c=>({...c})),
    staff:SEED_STAFF.map(p=>({...p})),
    marks:{},events:[],routes:{},
  };
}
export const fcfa = v => `${new Intl.NumberFormat("fr-FR").format(v)} FCFA`;
export const remaining = f => Math.max(0,f.total-f.paid);
export const schoolOf = (state,id) => state.schools.find(s=>s.id===id);
export const availableRoutes = (state,school) => state.routes[school]||["direct","concours","orientation"];
export const fakeId = (prefix,items)=>prefix+String(items.length+1);
