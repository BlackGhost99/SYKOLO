/* Bac à sable mémoire pour présenter les VRAIS composants YEM.
 * Toutes les requêtes sont traitées en local : aucun accès HTTP/production.
 * Le jeu est recréé à chaque ouverture, sans persistance navigateur. */
import {createDemoState,DEMO_CURRENT_YEAR,DEMO_YEARS,SCHOOL_ROLES,schoolOf,remaining} from "./demo-data.js";

const SCHOOL_IDS=["lycee","primaire","maternelle"];
const PERMISSIONS=[
"school.academic.read","school.academic.manage","school.students.read","school.students.manage",
"school.admissions.read","school.admissions.manage","school.admissions.enroll","school.admissions.decide",
"school.finance.read","school.finance.receive","school.finance.manage",
"school.staff.read","school.staff.manage","school.organization.read","school.organization.manage",
"school.roles.read","school.roles.manage","school.curriculum.read","school.curriculum.manage",
"school.timetable.read","school.timetable.manage","school.assessments.read","school.assessments.manage",
"school.reports.read","school.reports.manage","school.reports.publish",
"school.deliberations.read","school.deliberations.manage","school.deliberations.finalize",
"school.attendance.read","school.attendance.write","school.attendance.finalize",
"school.settings.read","school.settings.write","school.parents.manage","school.members.write"
];
const order=DEMO_YEARS.map(y=>({id:y,name:y,status:y==="2025-2026"?"closed":y===DEMO_CURRENT_YEAR?"current":"preparation",active:y!== "2025-2026"}));
const response=(data,status=200)=>Promise.resolve({
  ok:status>=200&&status<300,status,
  headers:{get:key=>key?.toLowerCase()==="content-type"?"application/json; charset=utf-8":null},
  json:async()=>data,
  text:async()=>JSON.stringify(data),
});
const splitName=name=>{const parts=(name||"Élève").trim().split(/\s+/);return {last_name:parts[0]||"",first_name:parts.slice(1).join(" ")||"—"};};
const today="2026-11-09";
export function createOfflineDemoBackend(){
  let data=createDemoState();
  const schoolList=()=>data.schools.map(s=>({id:s.id,name:s.name,school_type:s.type,active:true,login_code:"DEMO-"+s.id.toUpperCase()}));
  const years=()=>order.map(y=>({...y}));
  const findYear=raw=>order.find(y=>y.id===raw)||order[1];
  const schoolData=(id)=>schoolOf(data,id)||data.schools[0];
  const studentsFor=(id,yr)=>data.students.filter(s=>s.school===id&&s.year===yr);
  const classesFor=(id,yr)=>data.classes.filter(s=>s.school===id&&s.year===yr);
  const studentsOverview=(id,yr)=>{
    const ss=studentsFor(id,yr), cc=classesFor(id,yr);
    const rows=ss.map(s=>{
      const cls=cc.find(c=>c.name===s.level);
      const invoices=data.invoices.filter(i=>i.student===s.id&&i.year===yr);
      const billed=invoices.reduce((v,i)=>v+i.total,0),paid=invoices.reduce((v,i)=>v+i.paid,0);
      return {...splitName(s.name),id:s.id,student_code:"YEM-"+s.id.toUpperCase().padStart(6,"0"),
        matricule_yem:"DEMO-"+s.id.toUpperCase(),active:true,
        guardian:{full_name:s.guardian,phone:s.phone||""},
        enrollment:cls?{id:"en-"+s.id,classroom:{id:cls.id,name:cls.name}}:null,
        finance:{status:billed===0?"sans_frais":paid>=billed?"a_jour":paid>0?"partiel":"impaye",billed,paid,balance:billed-paid}
      };
    });
    return {year:findYear(yr),years:years(),currency:"XAF",currencies:["XAF"],finance_visible:true,
      classes:cc.map(c=>({id:c.id,name:c.name})),students:rows,
      metrics:{active:ss.length,enrolled:rows.filter(s=>s.enrollment).length,
        new_30d:1,new_prev_30d:1,incomplete:0,missing_documents:0,missing_phone:0}};
  };
  const classOverview=(id,yr)=>{
    const school=schoolData(id),cc=classesFor(id,yr),ss=studentsFor(id,yr);
    const cycle=school.type==="Maternelle"?"maternelle":school.type==="Primaire"?"primaire":"college";
    const levels=school.levels.map((name,i)=>({id:"level-"+id+"-"+i,name,code:String(i+1),
      cycle_code:cycle,cycle:school.type,active:true}));
    return {year:findYear(yr),years:years(),can_manage_academic:true,can_manage_classes:true,
      class_management_cycles:[cycle],class_level_options:{},levels,
      classes:cc.map(c=>({...c,level:levels.find(x=>c.name.startsWith(x.name))?.id||levels[0].id,
        enrolled:ss.filter(s=>s.level===c.name).length,active:true}))};
  };
  const financeOverview=(id,yr)=>{
    const ss=studentsFor(id,yr),cc=classesFor(id,yr),invs=data.invoices.filter(f=>f.school===id&&f.year===yr);
    const outstanding=invs.reduce((sum,f)=>sum+remaining(f),0), paid=invs.reduce((sum,f)=>sum+f.paid,0);
    const arrears=invs.filter(f=>remaining(f)>0).map(f=>{
      const st=ss.find(x=>x.id===f.student),cls=cc.find(x=>x.name===st?.level);
      return {enrollment:"en-"+f.student,student:st?.name||"Élève fictif",
        classroom:cls?.name||st?.level||"—",guardian:st?.guardian||"Parent",
        phone:"",due_date:"2026-10-15",amount_due:remaining(f),last_payment:f.paid?"2026-10-10":null};
    });
    const byClass=Object.values(arrears.reduce((o,a)=>{
      const k=a.classroom;if(!o[k])o[k]={classroom:k,families:0};o[k].families++;return o;},{}));
    return {year:findYear(yr),years:years(),currency:"XAF",currencies:["XAF"],
      month:{total:paid,previous:Math.floor(paid*.75),by_method:{especes:Math.floor(paid*.35),airtel_money:Math.floor(paid*.4),moov_money:Math.floor(paid*.25)}},
      monthly:["2026-05","2026-06","2026-07","2026-08","2026-09","2026-10"].map((month,i)=>({month,total:Math.round((i+1)*paid/9)})),
      outstanding,active_students:ss.length,families_late:new Set(arrears.map(a=>a.enrollment)).size,
      overdue_total:outstanding,arrears,arrears_by_class:byClass,
      today:{date:today,total:Math.floor(paid*.1),count:paid?2:0,
        payments:paid?[{id:"demo-1",student:ss[0]?.name||"Élève",classroom:ss[0]?.level||"6e A",amount:Math.floor(paid*.1),method:"especes",recorded_at:"2026-11-09T09:15:00+01:00"}]:[]}};
  };
  const platformSchool=s=>({id:s.id,name:s.name,organization:"Groupe scolaire (exemple)",active:true,
    school_type_label:s.type,education_cycles:[s.type==="Maternelle"?"maternelle":s.type==="Primaire"?"primaire":"college"],
    students_count:data.students.filter(x=>x.school===s.id&&x.year===DEMO_CURRENT_YEAR).length,
    members_count:data.staff.filter(x=>x.school===s.id).length});
  const platformSummary=raw=>{
    const schools=data.schools.map(platformSchool);const params=new URLSearchParams(raw);
    const q=(params.get("q")||"").toLowerCase();
    const selected=schools.filter(s=>s.name.toLowerCase().includes(q));
    return {organizations:1,schools_total:schools.length,schools_active:schools.length,schools_inactive:0,
      users_active:data.staff.length,schools:selected,filtered_total:selected.length,page:1,pages:1,per_page:5,
      organization_options:[{id:"org-demo",name:"Groupe scolaire (exemple)"}],
      recent_events:[{source:"demo",id:"evt-1",actor:"Administrateur fictif",event:"school_provisioned",
        school:schools[0]?.name,at:"2026-11-09T08:15:00+01:00"}]};
  };
  function platformDetail(id){
    const s=platformSchool(schoolData(id));const staff=data.staff.filter(x=>x.school===id);
    const members=staff.map(p=>({id:p.id,name:p.name,role:p.role,role_code:p.role==="Proviseur"?"proviseur":p.role==="Directeur"?"direction":"enseignant",
      email:"",active:true,is_platform_admin:false}));
    return {school:s,login_code:"DEMO-"+id.toUpperCase(),members,students_count:s.students_count,
      members_count:members.length,roles:[{id:"role-directeur",label:"Directeur"}],
      events:[],members_truncated:false,policy:{plan_name:"Démonstration",max_users:50,max_students:1000,revision:1}};
  }
  function schoolIdOf(path){return path.match(/^schools\/([^/]+)/)?.[1]||"lycee";}
  function fixtureFor(path,search,method,body){
    const id=schoolIdOf(path),school=schoolData(id);
    const yr=findYear(search.get("year")||DEMO_CURRENT_YEAR).id;
    if(path==="auth/csrf")return {};
    if(path==="schools")return {schools:schoolList()};
    if(path==="platform/dashboard")return platformSummary(search);
    if(path==="platform/schools")return {schools:data.schools.map(platformSchool),
      school_profiles:[{code:"primaire",label:"Primaire",allowed_cycles:["primaire"]},
        {code:"maternelle",label:"Maternelle",allowed_cycles:["maternelle"]},
        {code:"college_lycee",label:"Collège / Lycée",allowed_cycles:["college","lycee"]}],
      cycle_labels:{primaire:"Primaire",maternelle:"Maternelle",college:"Collège",lycee:"Lycée"}};
    if(path==="platform/organizations")return {organizations:[{id:"org-demo",name:"Groupe scolaire (exemple)",schools_count:data.schools.length}]};
    if(path==="platform/audit")return {events:platformSummary("").recent_events};
    if(/^platform\/schools\/[^/]+\/detail$/.test(path))return platformDetail(path.split("/")[2]);
    if(/^platform\/schools\/[^/]+\/members$/.test(path))return {members:platformDetail(path.split("/")[2]).members,total:3,page:1,pages:1,per_page:20};
    if(path.startsWith("platform/"))return {roles:[{code:"proprietaire",label:"Propriétaire / Fondateur"}],default_role:"proprietaire",ok:true};
    if(path===`schools/${id}/my-access`)return {is_owner:true,role:"proprietaire",role_label:"Propriétaire / Fondateur",
      permissions:PERMISSIONS,school:{id,name:school.name,login_code:"DEMO-"+id.toUpperCase()},cycle_scope_restricted:false};
    if(path.endsWith("/academic/annual-snapshot"))return {year:findYear(yr),years:years(),classes:classesFor(id,yr),students:studentsFor(id,yr)};
    if(path.endsWith("/overview/students"))return studentsOverview(id,yr);
    if(path.endsWith("/overview/finance"))return financeOverview(id,yr);
    if(path.endsWith("/overview/classes"))return classOverview(id,yr);
    if(path.endsWith("/academic/quick-classes")&&method!=="GET"){
      const names=body.names||[],base=classOverview(id,yr),made=[];
      for(const name of names){if(data.classes.some(c=>c.name===name&&c.school===id&&c.year===yr))continue;
        const classroom={id:"c-demo-"+(data.classes.length+1),school:id,name,year:yr,
          capacity:body.capacity??35};
        data.classes.push(classroom);made.push({...classroom,active:true,enrolled:0});}
      return {classes:made.length?made:[base.classes[0]].filter(Boolean)};
    }
    if(path.endsWith("/staff"))return {staff:data.staff.filter(s=>s.school===id).map(p=>({
      ...splitName(p.name),id:p.id,staff_code:"DEMO-"+p.id,position:p.role,active:true,
      account_id:p.hasAccount?"compte-"+p.id:null
    }))};
    if(path.endsWith("/academic/years"))return {years:years()};
    if(path.endsWith("/academic/classes"))return {classes:classOverview(id,yr).classes};
    if(path.endsWith("/academic/levels"))return {levels:classOverview(id,yr).levels};
    if(path.endsWith("/academic/cycles"))return {cycles:[{id:"cycle-demo",name:school.type,code:"college",active:true}]};
    if(path.endsWith("/academic/terms"))return {terms:[]};
    if(path.endsWith("/academic/subjects"))return {subjects:data.subjects.filter(s=>s.school===id)};
    if(path.endsWith("/positions"))return {positions:[]};
    if(path.endsWith("/appointments"))return {appointments:[]};
    if(path.endsWith("/my-appointments"))return {appointments:[],functions:[]};
    if(path.endsWith("/roles"))return {roles:[{code:"proprietaire",label:"Propriétaire"}],functions:[]};
    if(path.endsWith("/members"))return {members:[]};
    if(path.endsWith("/enrollment-form"))return {config:{},years:years(),fields:[],categories:[],classes:classOverview(id,yr).classes};
    if(path.includes("/classes/")&&path.endsWith("/students"))return {students:studentsOverview(id,yr).students};
    if(path.endsWith("/students"))return {students:studentsOverview(id,yr).students};
    if(path.endsWith("/guardians-by-class")){
      const room=search.get("classroom");
      return {families:studentsFor(id,yr).filter(s=>s.level===classesFor(id,yr).find(c=>c.id===room)?.name)
        .map(s=>({student_id:s.id,student_name:s.name,
          guardians:[{id:"g-"+s.id,name:s.guardian,phone:"",email:"",relationship:"Parent"}]}))};
    }
    if(path.endsWith("/parent-links"))return {links:[]};
    if(path.endsWith("/finance/charges"))return {charges:[]};
    if(path==="parents/children")return {children:data.students.filter(s=>["s1","s4","s7"].includes(s.id)).map(s=>({
      student:s.id,...splitName(s.name),school_name:schoolData(s.school).name,
      matricule_yem:"YEM-"+s.id,student_code:"DEMO-"+s.id}))};
    const parentMatch=path.match(/^parents\/children\/([^/]+)\/([^/]+)/);
    if(parentMatch){
      const child=data.students.find(s=>s.id===parentMatch[1]),kind=parentMatch[2];
      if(kind==="reports")return {reports:[{id:"report-demo",year:DEMO_CURRENT_YEAR,period:"1er trimestre",score:(child?.average||14)+"/20"}]};
      if(kind==="enrollments")return {enrollments:[{id:"en-demo",year:DEMO_CURRENT_YEAR,classroom:child?.level||"6e A",status:"Inscrit"}]};
      if(kind==="attendance")return {attendance:[{date:"2026-11-04",slot:"Matin",status:"Présent",justified:false}]};
      if(kind==="finance")return {totals:{XAF:{billed:75000,paid:50000,balance:25000}},charges:[]};
      if(kind==="timetable")return {entries:[{id:"t-demo",weekday:0,start:"08:00",end:"09:00",subject:"Mathématiques",teacher:"Mme Mba",room:"Salle 1"}]};
      return {};
    }
    if(path.startsWith("parents/"))return {schools:[],applications:[]};
    if(path.endsWith("/staff/onboard")){
      const labels=SCHOOL_ROLES[school.type]||SCHOOL_ROLES["Collège / Lycée"];
      const codeFor=label=>label.toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g,"").replace(/[^a-z0-9]+/g,"_").replace(/^_|_$/g,"");
      const positions=labels.map(label=>({code:codeFor(label),label,scope:"school",allowed_cycles:[]}));
      const roles=labels.map(label=>({code:codeFor(label),label,permissions:[],available_for_accounts:true}));
      if(method!=="GET"){
        const p=body.staff||{};
        const newPerson={id:"p-demo-"+(data.staff.length+1),school:id,year:yr,name:p.last_name+" "+p.first_name,
          role:p.position||"Enseignant",hasAccount:Boolean(body.account)};
        data.staff.push(newPerson);
        return {staff:newPerson,account_created:Boolean(body.account),appointments:body.appointments||[]};
      }
      return {school_name:school.name,can_create_account:true,can_manage_cycle_access:true,
        education_cycles:[school.type],academic_cycles:[{id:"cycle-demo",code:"college",name:school.type}],
        actor_access_cycle_ids:null,existing_accounts:[],roles,positions,years:years(),
        classes:classOverview(id,yr).classes};
    }
    if(path.includes("/onboarding")||path.includes("/staff/setup"))return {staff:[],roles:[],functions:[],appointments:[],years:years(),classes:[]};
    // Les modules non préparés ne peuvent EN AUCUN CAS contacter une API réelle.
    return {items:[],results:[],students:[],classes:[],members:[],roles:[],functions:[],
      years:years(),year:findYear(yr),schools:schoolList(),groups:[],charges:[],enrollments:[],
      staff:[],settings:{},config:{},permissions:PERMISSIONS};
  }
  async function fetch(input,options={}){
    const url=String(typeof input==="string"?input:input?.url||"");
    const parsed=new URL(url,"https://demo.yem.invalid");
    const method=(options?.method||"GET").toUpperCase();
    if(!parsed.pathname.startsWith("/api/v1/"))return response({error:"Démonstration hors ligne : accès réseau bloqué."},403);
    const path=parsed.pathname.slice("/api/v1/".length).replace(/\/$/,"");
    let body={};try{if(options.body)body=JSON.parse(options.body)}catch{}
    try{return response(fixtureFor(path,parsed.searchParams,method,body))}
    catch(error){return response({error:"Données de présentation indisponibles : "+error.message},400)}
  }
  function reset(){data=createDemoState();}
  return {fetch,reset};
}
