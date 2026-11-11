/* Bac à sable mémoire pour présenter les VRAIS composants YEM.
 * Toutes les requêtes sont traitées en local : aucun accès HTTP/production.
 * Le jeu est recréé à chaque ouverture, sans persistance navigateur. */
import {createDemoState,DEMO_CURRENT_YEAR,DEMO_YEARS,SCHOOL_ROLES,schoolOf,remaining} from "./demo-data.js";

import {DEMO_ROLES} from "./demo-roles.js";

const demoRoleCatalog=()=>Object.entries(DEMO_ROLES).filter(([code])=>code!=="platform")
  .map(([code,profile])=>({id:"demo-role-"+code,code,...profile,revision:1,available_for_accounts:true}));
const initialOrganizations=()=>[{id:"org-demo",name:"Groupe scolaire (exemple)"}];
const order=DEMO_YEARS.map(y=>({id:y,name:y,status:y==="2025-2026"?"closed":y===DEMO_CURRENT_YEAR?"current":"preparation",active:y!== "2025-2026",start_date:y.slice(0,4)+"-09-07",end_date:y.slice(5)+"-07-10"}));
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
  let role="direction";
  let organizations=initialOrganizations();
  let audit=[];
  let platformAccess=null;
  let assessments={};
  let grades={};
  let reports={};
  let closings=[];
  let payments=[];
  let sessions=[];
  let calendar=[];
  let councils=[];
  let mobilePayments=[];
  let schedules=[];
  let timetable=[];
  let assignments=[];
  let forms={};
  const defaultForm={fields:{},custom_fields:[],documents:[
    {key:"birth_certificate",label:"Acte de naissance",required:true},
    {key:"previous_report",label:"Dernier bulletin",required:false}
  ]};
  let admissions=[];
  let batches=new Map();
  const initialConduct = () => [{id:"conduct-demo",enrollment:"en-s1",kind:"observation",date:"2026-11-04",
    label:"Observation de comportement",message:"Bonne participation aux activités de la classe.",withdrawn:false}];
  let conduct = initialConduct();
  const effectiveRole=id=>role==="platform"&&platformAccess===id?"direction":role;
  const can=(id,permission)=>DEMO_ROLES[effectiveRole(id)].permissions.includes(permission);
  const schoolList=()=>data.schools.filter(s=>s.active!==false&&(role!=="platform"||s.id===platformAccess))
    .map(s=>({id:s.id,name:s.name,school_type:s.type,active:true,login_code:"DEMO-"+s.id.toUpperCase()}));
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
        guardian:s.guardians?.find(row=>row.active&&row.is_primary)||{full_name:s.guardian,phone:s.phone||""},
        enrollment:cls?{id:"en-"+s.id,classroom:{id:cls.id,name:cls.name}}:null,
        finance:{status:billed===0?"sans_frais":paid>=billed?"a_jour":paid>0?"partiel":"impaye",billed,paid,balance:billed-paid}
      };
    });
    return {year:findYear(yr),years:years(),currency:"XAF",currencies:["XAF"],finance_visible:true,
      classes:cc.map(c=>({id:c.id,name:c.name})),students:rows,
      sensitive_visible:can(id,"school.students.sensitive.read"),
      metrics:{active:ss.length,enrolled:rows.filter(s=>s.enrollment).length,
        new_30d:1,new_prev_30d:1,incomplete:0,missing_documents:0,missing_phone:0}};
  };
  // Les mêmes écrans que la production exigent ces structures, même en démonstration.
  const subjectsFor=(id,yr)=>data.subjects.filter(s=>s.school===id&&s.year===yr)
    .map(s=>({...s,active:true,code:s.id}));
  const coursesFor=(id,yr)=>classesFor(id,yr).flatMap(room=>subjectsFor(id,yr)
    .filter(subject=>room.name.startsWith(subject.level+" "))
    .map(subject=>({id:"course-"+room.id+"-"+subject.id,school:id,year:yr,
      classroom:room.id,subject:subject.id,coefficient:subject.coefficient,active:true})));
  const periodsFor=(yr)=>["1er trimestre","2e trimestre","3e trimestre"]
    .map((name,i)=>({id:"period-"+yr+"-"+(i+1),year:yr,name,code:"T"+(i+1),active:true,revision:1,
      start_date:[yr.slice(0,4)+"-09-07",yr.slice(0,4)+"-12-07",yr.slice(5)+"-03-15"][i],
      end_date:[yr.slice(0,4)+"-11-28",yr.slice(5)+"-03-06",yr.slice(5)+"-07-10"][i]}));
  const assessmentFor=(id,courseId,yr)=>{
    if(!assessments[courseId]){
      assessments[courseId]=[{id:"assessment-"+courseId,school:id,course:courseId,year:yr,
        name:"Contrôle continu n°1",assessment_date:"2026-10-15",kind:"devoir",weight:1,
        active:true,published:false,revision:1,
        policy:{name:"Notation sur 20",scale:{kind:"numeric",max:20},bands:[]}}];
    }
    return assessments[courseId];
  };
  const pupilsIn=room=>room?studentsFor(room.school,room.year).filter(s=>s.level===room.name):[];
  const statuses=[{code:"present",label:"Présent",group:"present"},
    {code:"absent",label:"Absent",group:"absent"},{code:"late",label:"En retard",group:"late"}];
  const invoicesFor=(id,yr)=>data.invoices.filter(f=>f.school===id&&f.year===yr);
  const chargesFor=(id,yr)=>invoicesFor(id,yr).map(f=>({id:f.id,enrollment:"en-"+f.student,
    label:f.label,amount:f.total,balance:remaining(f),paid:f.paid,currency:f.currency||"XAF",
    due_date:f.due_date||"2026-11-15",year:yr,active:true}));
  const schedulesFor=(id,yr)=>invoicesFor(id,yr).map(f=>({
    id:"schedule-"+f.id,year:yr,classroom:null,code:"demo-"+f.id,label:f.label,
    amount:f.total,currency:"XAF",due_date:"2026-11-15",active:true}))
    .concat(schedules.filter(row=>row.school===id&&row.year===yr));
  const enrollmentRows=(id,yr)=>studentsFor(id,yr).map(s=>{
    const cl=classesFor(id,yr).find(c=>c.name===s.level);
    return {id:"en-"+s.id,student:s.id,year:yr,year_name:yr,classroom:cl?.id||"",
      classroom_name:cl?.name,enrolled_on:s.enrolled_on||findYear(yr).start_date,
      revision:s.enrollment_revision||1,active:true,status:"Inscrit"};
  }).filter(row=>row.classroom);
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
    const yesterdayTotal=Math.floor(paid*.04);
    const received=payments.filter(p=>p.school===id&&p.year===yr);
    const seedTotal=Math.floor((paid-received.reduce((sum,p)=>sum+p.amount,0))*.1);
    const todayMethods={especes:Math.floor(seedTotal*.35),
      airtel_money:Math.floor(seedTotal*.4),moov_money:seedTotal-Math.floor(seedTotal*.35)-Math.floor(seedTotal*.4)};
    for(const payment of received)todayMethods[payment.method]=(todayMethods[payment.method]||0)+payment.amount;
    const todaysPayments=[...received,...(seedTotal?[{id:"demo-1",student:ss[1]?.name||"Élève",
      classroom:ss[1]?.level||"Classe",amount:seedTotal,method:"especes",recorded_at:today+"T09:15:00+01:00"}]:[])];
    return {year:findYear(yr),years:years(),currency:"XAF",currencies:["XAF"],
      month:{total:paid,previous:Math.floor(paid*.75),by_method:{especes:Math.floor(paid*.35),airtel_money:Math.floor(paid*.4),moov_money:Math.floor(paid*.25)}},
      monthly:["2026-05","2026-06","2026-07","2026-08","2026-09","2026-10"].map((month,i)=>({month,total:Math.round((i+1)*paid/9)})),
      outstanding,active_students:ss.length,families_late:new Set(arrears.map(a=>a.enrollment)).size,
      overdue_total:outstanding,arrears,arrears_by_class:byClass,
      yesterday:{date:"2026-11-08",total:yesterdayTotal,count:paid?1:0},
      today:{date:today,total:todaysPayments.reduce((sum,p)=>sum+p.amount,0),
        count:todaysPayments.length,by_method:todayMethods,payments:todaysPayments}};
  };
  const ownerOverview=(id,yr)=>{
    const school=schoolData(id),ss=studentsFor(id,yr),cc=classesFor(id,yr);
    const fees=invoicesFor(id,yr);
    const billed=fees.reduce((sum,fee)=>sum+fee.total,0);
    const paid=fees.reduce((sum,fee)=>sum+fee.paid,0);
    const team=data.staff.filter(person=>person.school===id);
    const pending=0; // les demandes de la démo peuvent être créées sans droits réels
    return {
      school:{id,name:school.name,type:school.type},as_of:today,
      years:years(),year:findYear(yr),read_only:true,
      schooling:{
        active_students:ss.length,active_classes:cc.length,
        enrollment_by_cycle:[{cycle:school.type,classes:cc.length,students:ss.length}],
        capacities_defined:cc.filter(room=>room.capacity!=null).length,
        total_defined_places:cc.reduce((sum,room)=>sum+(room.capacity||0),0),
        assessments:0,published_assessments:0,published_reports:0,
        absence_marks:0,late_marks:0,
      },
      admissions:{total:pending,pending,accepted:0,rejected:0,enrolled:0},
      staff:{active:team.length,with_account:team.filter(person=>person.hasAccount).length,
        without_account:team.filter(person=>!person.hasAccount).length,
        assigned_to_classes:team.length,active_appointments:team.length},
      finance:{currencies:fees.length?[{currency:"XAF",billed:String(billed),
        paid:String(paid),outstanding:String(billed-paid),overdue:String(billed-paid),
        paid_this_month:String(paid),paid_today:"0",payments_today:0}]:[],
        monthly:fees.length?[{month:"2026-11",currency:"XAF",total:String(paid)}]:[],
        note:"Montants fictifs — démonstration locale, aucun paiement réel."},
      activity:{total_30d:3,by_type:[{label:"Opérations fictives",total:3}],
        days:[{date:today,total:3}]},
    };
  };
  const platformSchool=s=>({id:s.id,name:s.name,
    organization:organizations.find(row=>row.id===(s.organization_id||"org-demo"))?.name,
    active:s.active!==false,school_type:s.school_type||(s.id==="lycee"?"college_lycee":s.id),
    school_type_label:s.type,governance_mode:s.governance_mode||"prive_laique",
    education_cycles:s.education_cycles||(s.id==="lycee"?["college","lycee"]:[s.id]),
    students_count:data.students.filter(x=>x.school===s.id&&x.year===DEMO_CURRENT_YEAR).length,
    members_count:data.staff.filter(x=>x.school===s.id).length});
  const platformSummary=raw=>{
    const schools=data.schools.map(platformSchool);const params=new URLSearchParams(raw);
    const q=(params.get("q")||"").toLowerCase(),organization=params.get("organization");
    const selected=schools.filter(s=>s.name.toLowerCase().includes(q)&&
      (!organization||s.organization===organizations.find(row=>row.id===organization)?.name));
    return {organizations:organizations.length,schools_total:schools.length,
      schools_active:schools.filter(s=>s.active).length,schools_inactive:schools.filter(s=>!s.active).length,
      users_active:data.staff.filter(p=>p.active!==false).length,schools:selected,
      filtered_total:selected.length,page:1,pages:1,per_page:20,organization_options:organizations,
      recent_events:[...audit,{source:"demo",id:"evt-1",actor:"Administrateur fictif",event:"school_provisioned",
        school:schools[0]?.name,at:"2026-11-09T08:15:00+01:00"}]};
  };
  function platformDetail(id){
    const school=schoolData(id),s=platformSchool(school);
    const members=data.staff.filter(x=>x.school===id).map(p=>({
      id:p.id,name:p.name,username:p.username||"demo."+p.id,
      role:p.role,role_code:p.role_code||(p.role==="Proviseur"?"proviseur":p.role==="Directeur"?"direction":"enseignant"),
      email:p.email||"",active:p.active!==false,membership_active:p.active!==false,is_platform_admin:false
    }));
    return {school:s,login_code:"DEMO-"+id.toUpperCase(),members,students_count:s.students_count,
      members_count:members.length,roles:demoRoleCatalog(),
      events:audit.filter(event=>event.school_id===id),members_truncated:false,
      policy:school.policy||{plan_name:"Démonstration",max_users:50,max_students:1000,revision:1}};
  }
  function recordPlatformEvent(school,event,reason=""){
    audit.unshift({source:"demo",id:"evt-demo-"+(audit.length+1),actor:"Administrateur fictif",event,
      school:school.name,school_id:school.id,reason,at:today+"T10:00:00+01:00"});
  }
  function createPlatformUser(id,body){
    const person={id:"p-demo-"+(data.staff.length+1),school:id,year:DEMO_CURRENT_YEAR,
      name:body.last_name+" "+body.first_name,role:DEMO_ROLES[body.role]?.label||body.role,
      role_code:body.role,username:body.username,email:body.email,hasAccount:true};
    data.staff.push(person);
    return person;
  }
  function reportSnapshot(id,yr,rec){
    const st=studentsFor(id,yr).find(s=>"en-"+s.id===rec.enrollment);
    const classroom=classesFor(id,yr).find(c=>c.name===st?.level);
    const names=splitName(st?.name||"Élève fictif");
    const results=coursesFor(id,yr).filter(course=>course.classroom===classroom?.id).map(course=>{
      const marks=(assessments[course.id]||[]).filter(a=>a.published&&(!rec.period||a.period===rec.period))
        .flatMap(a=>(grades[a.id]||[]).filter(g=>g.enrollment===rec.enrollment&&g.score!=null)
          .map(g=>({score:Number(g.score),weight:Number(a.weight)})));
      const weight=marks.reduce((sum,mark)=>sum+mark.weight,0);
      const score=weight?Math.round(marks.reduce((sum,mark)=>sum+mark.score*mark.weight,0)/weight*100)/100:st?.average??null;
      return {course:course.id,subject:subjectsFor(id,yr).find(row=>row.id===course.subject)?.name,
        coefficient:course.coefficient,result:{score,label:"Résultat fictif"}};
    });
    const scored=results.filter(row=>row.result.score!=null);
    const coefficients=scored.reduce((sum,row)=>sum+row.coefficient,0);
    const average=coefficients?Math.round(scored.reduce((sum,row)=>sum+row.result.score*row.coefficient,0)/coefficients*100)/100:st?.average??null;
    return {
      template:{title:"Bulletin scolaire — démonstration",show_score:true,show_label:true},
      student:{...names,code:"DEMO-"+(st?.id||"ELEVE").toUpperCase()},
      class:{name:classroom?.name||st?.level||"Classe"},
      year:{name:yr},
      period:periodsFor(yr).find(p=>p.id===rec.period)||null,
      subjects:results,
      overall:{score:average,label:"Exemple non officiel"}
    };
  }
  function schoolIdOf(path){return path.match(/^schools\/([^/]+)/)?.[1]||"lycee";}
  function fixtureFor(path,search,method,body){
    const id=schoolIdOf(path),school=schoolData(id);
    const yr=findYear(search.get("year")||DEMO_CURRENT_YEAR).id;
    if(path==="auth/csrf")return {};
    if(path==="schools")return {schools:schoolList()};
    if(path==="platform/dashboard")return platformSummary(search);
    if(path==="platform/schools"&&method==="GET"&&search.has("school_type")){
      const roles=demoRoleCatalog();
      const default_role=search.get("governance_mode")==="public"?"direction":"proprietaire";
      return {roles:roles.filter(row=>default_role==="proprietaire"||row.code!=="proprietaire"),default_role};
    }
    if(path==="platform/schools"){
      const profiles=[{code:"primaire",label:"Primaire",allowed_cycles:["primaire"],default_cycles:["primaire"]},
        {code:"maternelle",label:"Maternelle",allowed_cycles:["maternelle"],default_cycles:["maternelle"]},
        {code:"college_lycee",label:"Collège / Lycée",allowed_cycles:["college","lycee"],default_cycles:["college","lycee"]}];
      if(method==="GET")return {schools:data.schools.map(platformSchool),school_profiles:profiles,
        governance_options:[{code:"prive_laique",label:"Privé laïque"},{code:"public",label:"Public"}],
        cycle_labels:{primaire:"Primaire",maternelle:"Maternelle",college:"Collège",lycee:"Lycée"}};
      const organization=organizations.find(row=>row.id===body.organization_id)||
        {id:"org-demo-"+(organizations.length+1),name:body.organization_name};
      if(!organizations.includes(organization))organizations.push(organization);
      const school={id:"ecole-demo-"+(data.schools.length+1),name:body.school_name,
        organization_id:organization.id,type:profiles.find(row=>row.code===body.school_type)?.label||body.school_type,
        school_type:body.school_type,education_cycles:body.education_cycles,
        governance_mode:body.governance_mode,levels:[]};
      data.schools.push(school);
      createPlatformUser(school.id,body);
      recordPlatformEvent(school,"school_provisioned");
      return {id:school.id,name:school.name,username:body.username};
    }
    if(path==="platform/organizations"){
      if(method==="GET")return {organizations:organizations.map(org=>({...org,
        schools_count:data.schools.filter(s=>(s.organization_id||"org-demo")===org.id).length}))};
      const org={id:"org-demo-"+(organizations.length+1),name:body.name};
      organizations.push(org);return org;
    }
    if(path==="platform/audit")return {events:platformSummary("").recent_events};
    if(path==="platform/schools/initial-roles"||path==="platform/initial-roles")
      return {roles:demoRoleCatalog(),default_role:"proprietaire"};
    const platformRoute=path.match(/^platform\/schools\/([^/]+)\/(detail|members|action|admin-access|users)(?:\/([^/]+)\/action)?$/);
    if(platformRoute){
      const school=schoolOf(data,platformRoute[1]);
      if(!school)throw Error("Établissement fictif introuvable.");
      const action=platformRoute[2];
      if(action==="detail")return platformDetail(school.id);
      if(action==="members"){
        if(method==="GET"){
          const q=(search.get("q")||"").toLowerCase();
          const members=platformDetail(school.id).members.filter(row=>
            [row.name,row.username,row.role].some(value=>value?.toLowerCase().includes(q)));
          return {members,total:members.length,page:1,pages:1,per_page:20};
        }
        const member=data.staff.find(row=>row.school===school.id&&row.id===platformRoute[3]);
        if(!member)throw Error("Compte fictif introuvable.");
        if(body.action==="status")member.active=body.active;
        if(body.action==="role"){
          const next=demoRoleCatalog().find(row=>row.id===body.role_id);
          if(!next)throw Error("Rôle fictif introuvable.");
          member.role=next.label;member.role_code=next.code;
        }
        recordPlatformEvent(school,"member_updated",body.reason);
        return platformDetail(school.id);
      }
      if(action==="admin-access"){
        platformAccess=school.id;recordPlatformEvent(school,"school_admin_access");
        return {school:school.id};
      }
      if(action==="users"){
        const person=createPlatformUser(school.id,body);
        recordPlatformEvent(school,"school_user_created");
        return {id:person.id,username:person.username};
      }
      if(action==="action"){
        if(body.action==="rename")school.name=body.name;
        else if(body.action==="status")school.active=body.active;
        else if(body.action==="profile")Object.assign(school,{school_type:body.school_type,
          education_cycles:body.education_cycles,governance_mode:body.governance_mode});
        else if(body.action==="plan")school.policy={plan_name:body.plan_name,max_users:body.max_users,
          max_students:body.max_students,revision:(school.policy?.revision||1)+1};
        else throw Error("Action fictive inconnue.");
        recordPlatformEvent(school,"school_"+body.action,body.reason);
        return platformDetail(school.id);
      }
    }
    if(path.startsWith("platform/")&&method==="GET")return {roles:demoRoleCatalog(),default_role:"proprietaire"};
    if(path===`schools/${id}/my-access`){
      const currentRole=effectiveRole(id);
      return {is_owner:role==="proprietaire",role:currentRole,role_label:DEMO_ROLES[currentRole].label,
        permissions:DEMO_ROLES[currentRole].permissions,school:{id,name:school.name,login_code:"DEMO-"+id.toUpperCase()},
        cycle_scope_restricted:false};
    }
    const schoolRoute=path.slice(`schools/${id}/`.length);

    const roomById=roomId=>data.classes.find(room=>room.school===id&&room.id===roomId);
    if(schoolRoute==="academic/annual-snapshot"){
      const overview=classOverview(id,yr),periods=periodsFor(yr);
      const published=Object.values(reports).filter(row=>row.school===id&&row.year===yr&&row.status==="published");
      const staff=assignments.filter(row=>row.school===id&&row.year===yr);
      return {year:findYear(yr),years:years(),periods,can_edit_year:false,
        classes:overview.classes.map(room=>({...room,level:overview.levels.find(row=>row.id===room.level)?.name,
          cycle:school.type,team:staff.filter(row=>row.classroom===room.id).map(row=>({
            staff_id:row.staff,name:data.staff.find(person=>person.id===row.staff)?.name,duty:row.duty
          }))})),
        stats:{classes:overview.classes.length,periods:periods.length,enrollments:enrollmentRows(id,yr).length,
          staff_assignments:staff.length,published_reports:published.length,
          assessments:Object.values(assessments).flat().filter(row=>row.school===id&&row.year===yr).length}
      };
    }
    if(schoolRoute.startsWith("academic/pedagogical-calendar")){
      const kinds=[{code:"autre",label:"Autre"},{code:"rentree",label:"Rentrée"},
        {code:"vacances",label:"Vacances"},{code:"examen",label:"Examen"}];
      const scopes=[{code:"all",label:"Tout l’établissement"}];
      const eventId=schoolRoute.split("/")[2];
      if(method==="GET")return {kinds,scopes,can_manage:can(id,"school.academic.manage")&&findYear(yr).active,
        events:[...calendar.filter(row=>row.school===id&&row.year===yr),
          {id:"demo-rentree",title:"Rentrée des classes",kind:"rentree",scope:"all",
            start_date:findYear(yr).start_date,end_date:findYear(yr).start_date,active:true}]};
      if(eventId){
        const event=calendar.find(row=>row.school===id&&row.id===eventId);
        if(!event)throw Error("Événement fictif introuvable.");
        Object.assign(event,body,{revision:event.revision+1});return event;
      }
      const event={...body,school:id,id:"demo-event-"+(calendar.length+1),revision:1,active:true};
      calendar.push(event);return event;
    }
    if(schoolRoute==="admissions"){
      if(!admissions.some(row=>row.school===id)){
        const room=classesFor(id,DEMO_CURRENT_YEAR)[0];
        if(room)admissions.push({id:"admission-"+id,school:id,classroom:room.id,year:room.year,
          first_name:"David",last_name:"Obame",guardian_name:"Mme Obame",route:"direct",
          status:"submitted",revision:1,submitted_at:today,required_documents:[],history:[]});
      }
      if(method==="GET")return {applications:admissions.filter(row=>row.school===id)};
      const row={...body,id:"admission-demo-"+(admissions.length+1),school:id,
        status:"submitted",revision:1,submitted_at:today,required_documents:[],history:[]};
      admissions.push(row);return row;
    }
    if(schoolRoute==="admissions/policy"&&method==="GET")return {
      enabled_routes:["direct","concours","orientation"],public_routes:["direct"],
      required_documents:{direct:[],concours:[],orientation:[]},revision:1
    };
    if(schoolRoute.startsWith("admissions/capacity/")){
      const room=roomById(schoolRoute.split("/").at(-1)),occupied=pupilsIn(room).length;
      return {occupied,accepted_pending:0,remaining:room?.capacity==null?null:room.capacity-occupied};
    }
    const admissionRoute=schoolRoute.match(/^admissions\/([^/]+)\/(decide|convert|history|documents)$/);
    if(admissionRoute){
      const row=admissions.find(item=>item.id===admissionRoute[1]&&item.school===id);
      if(!row)throw Error("Candidature fictive introuvable.");
      const action=admissionRoute[2];
      if(action==="history")return {history:row.history};
      if(action==="documents"&&method==="GET")return {documents:[],required_documents:row.required_documents};
      if(method==="POST"&&(action==="decide"||action==="convert")){
        if(row.revision!==body.revision)throw Error("Le dossier a été modifié.");
        if(action==="convert"){
          const room=roomById(row.classroom);
          if(row.status!=="accepted"||!room)throw Error("Le dossier doit être admis dans une classe.");
          data.students.push({id:"s-"+row.id,school:id,year:row.year,level:room.name,
            name:row.last_name+" "+row.first_name,guardian:row.guardian_name,phone:row.guardian_phone,
            average:null,absences:0});
          row.status="enrolled";
        }else{
          row.status=body.status;row.decision_reason=body.reason;
        }
        row.revision++;
        row.history.push({id:"history-"+row.revision,status:row.status,at:today,reason:body.reason||""});
        return row;
      }
    }
    if(schoolRoute==="staff/me/assignments")return {
      assignments:classesFor(id,yr).slice(0,1).map(room=>({classroom:room.id}))
    };
    if(schoolRoute==="attendance/options")return {statuses};
    if(schoolRoute==="attendance/sessions"){
      const room=roomById(body.classroom||search.get("classroom"));
      if(method==="GET")return {sessions:sessions.filter(session=>session.classroom===room?.id)};
      if(!room)throw Error("Classe fictive introuvable.");
      const session={id:"appel-"+(sessions.length+1),classroom:room.id,date:body.date,
        slot:body.slot,label:body.label,revision:1,closed_at:null,marks:{}};
      sessions.push(session);return session;
    }
    const attendanceRoute=schoolRoute.match(/^attendance\/sessions\/([^/]+)(?:\/(marks|close))?$/);
    if(attendanceRoute){
      const session=sessions.find(row=>row.id===attendanceRoute[1]&&roomById(row.classroom));
      if(!session)throw Error("Appel fictif introuvable.");
      if(method==="GET")return {...session,roster:pupilsIn(roomById(session.classroom)).map(student=>({
        enrollment:"en-"+student.id,...splitName(student.name),student_code:"DEMO-"+student.id,
        mark:session.marks["en-"+student.id]||null
      }))};
      if(session.closed_at)throw Error("Cet appel est clôturé.");
      if(attendanceRoute[2]==="marks"){
        for(const mark of body.marks){
          session.marks[mark.enrollment]={...mark,revision:mark.revision+1,
            group:statuses.find(status=>status.code===mark.status)?.group};
        }
        return {marks:Object.values(session.marks),session_revision:++session.revision};
      }
      if(attendanceRoute[2]==="close"){
        session.closed_at=today;session.revision++;return session;
      }
    }
    if(path.endsWith("/owner/overview"))return ownerOverview(id,yr);
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
    if(schoolRoute==="staff"&&method==="POST"){
      const person={id:"p-demo-"+(data.staff.length+1),school:id,year:yr,
        name:body.last_name+" "+body.first_name,role:body.position,hasAccount:Boolean(body.username)};
      data.staff.push(person);return person;
    }
    if(schoolRoute==="staff"&&method==="GET")return {staff:data.staff.filter(s=>s.school===id).map(p=>({
      ...splitName(p.name),id:p.id,staff_code:"DEMO-"+p.id,position:p.role,active:true,
      account_id:p.hasAccount?"compte-"+p.id:null
    }))};
    if(path.endsWith("/academic/years"))return {years:years()};
    if(path.endsWith("/academic/classes"))return {classes:search.has("year")?classOverview(id,yr).classes:order.flatMap(year=>classOverview(id,year.id).classes)};
    if(path.endsWith("/academic/levels"))return {levels:classOverview(id,yr).levels};
    if(path.endsWith("/academic/cycles"))return {cycles:[{id:"cycle-demo",name:school.type,code:"college",active:true}]};
    if(path.endsWith("/academic/terms"))return {terms:periodsFor(yr)};
    if(path.endsWith("/academic/periods"))return {periods:search.has("year")?periodsFor(yr):order.flatMap(year=>periodsFor(year.id))};
    if(schoolRoute==="subjects"&&method==="GET")return {
      subjects:order.flatMap(year=>subjectsFor(id,year.id)),can_manage:can(id,"school.curriculum.manage")
    };
    if(schoolRoute==="courses"&&method==="GET")return {courses:order.flatMap(year=>coursesFor(id,year.id)),
      can_manage:can(id,"school.curriculum.manage")};
    if(schoolRoute==="courses/generate"&&method==="POST"){
      const room=roomById(body.classroom);
      if(!room)throw Error("Classe fictive introuvable.");
      const names=[...new Set(body.names||[])].filter(name=>!coursesFor(id,room.year)
        .some(course=>course.classroom===room.id&&subjectsFor(id,room.year).find(row=>row.id===course.subject)?.name===name));
      const created=names.map((name,index)=>({id:"matiere-demo-"+(data.subjects.length+index+1),school:id,
        year:room.year,name,level:room.name.slice(0,room.name.lastIndexOf(" ")),coefficient:1}));
      data.subjects.push(...created);
      return {created:created.length,courses:coursesFor(id,room.year).filter(row=>row.classroom===room.id)};
    }
    if(path.endsWith("/curriculum/my-courses"))return {
      courses:coursesFor(id,yr).filter(course=>course.classroom===classesFor(id,yr)[0]?.id).slice(0,1)
    };
    const courseAssessments=path.match(/^schools\/[^/]+\/courses\/([^/]+)\/assessments$/);
    if(courseAssessments){
      const courseId=courseAssessments[1];
      if(method!=="GET"){
        const list=assessmentFor(id,courseId,yr);
        const record={id:"assessment-demo-"+(list.length+1)+"-"+courseId,school:id,year:yr,course:courseId,
          name:String(body.name||"Évaluation fictive"),assessment_date:body.assessment_date||today,
          kind:body.kind||"devoir",weight:Number(body.weight)||1,period:body.period||null,
          active:true,published:false,revision:1,
          policy:{name:"Notation sur 20",scale:{kind:"numeric",max:20},bands:[]}};
        list.push(record);return record;
      }
      return {assessments:assessmentFor(id,courseId,yr)};
    }
    const assessmentRoute=path.match(/^schools\/[^/]+\/assessments\/([^/]+)(?:\/(roster|grades|publish))?(?:\/([^/]+))?$/);
    if(assessmentRoute){
      const assessmentId=assessmentRoute[1],section=assessmentRoute[2],gradeId=assessmentRoute[3];
      const course=coursesFor(id,yr).find(x=>assessmentId.includes(x.id));
      const classroom=classesFor(id,yr).find(c=>c.id===course?.classroom);
      const pupils=studentsFor(id,yr).filter(s=>s.level===classroom?.name);
      if(section==="roster")return {students:pupils.map(s=>({
        enrollment_id:"en-"+s.id,...splitName(s.name),student_code:"DEMO-"+s.id.toUpperCase()
      }))};
      if(section==="grades"){
        if(!grades[assessmentId])grades[assessmentId]=pupils.map(s=>({
          id:"grade-"+assessmentId+"-"+s.id,enrollment:"en-"+s.id,score:s.average,
          revision:1,label:s.average===null?"Non évalué":"Résultat fictif"}));
        if(method!=="GET"){
          const existing=grades[assessmentId].find(g=>g.id===gradeId||g.enrollment===body.enrollment);
          if(existing){existing.score=body.score;existing.revision++;return {...existing};}
          const record={id:"grade-"+assessmentId+"-"+(grades[assessmentId].length+1),
            enrollment:body.enrollment,score:body.score,revision:1};
          grades[assessmentId].push(record);return record;
        }
        return {grades:grades[assessmentId]};
      }
      if(section==="publish"){
        const all=Object.values(assessments).flat();
        const found=all.find(a=>a.id===assessmentId);
        if(found){found.published=true;found.revision++;}
        return found||{id:assessmentId,published:true};
      }
    }
    if(path.endsWith("/academic/subjects"))return {subjects:subjectsFor(id,yr)};
    if(path.endsWith("/positions"))return {positions:[]};
    if(path.endsWith("/appointments"))return {appointments:[]};
    if(path.endsWith("/my-appointments"))return {appointments:[],functions:[]};
    if(schoolRoute==="roles"&&method==="GET"){
      return {roles:demoRoleCatalog(),available_permissions:DEMO_ROLES.direction.permissions,functions:[]};
    }
    const seedAssignments=()=>classesFor(id,yr).slice(0,1).map(room=>({
      id:"assignment-"+room.id,staff:data.staff.find(person=>person.school===id&&person.role==="Enseignant")?.id,
      classroom:room.id,year:yr,duty:"enseignement",active:true
    })).filter(row=>row.staff);
    const schoolAssignments=()=>[...seedAssignments(),...assignments.filter(row=>row.school===id)];
    if(schoolRoute==="staff-assignments"){
      if(method==="GET")return {assignments:schoolAssignments()};
      const row={...body,school:id,id:"affectation-demo-"+(assignments.length+1),active:true};
      assignments.push(row);return row;
    }
    const courseInstructors=schoolRoute.match(/^courses\/([^/]+)\/instructors$/);
    const instructorsFor=course=>schoolAssignments().filter(row=>row.classroom===course?.classroom&&row.active)
      .map(row=>({id:"instructor-"+row.id,staff_assignment:row.id,active:true}));
    if(courseInstructors&&method==="GET")return {
      instructors:instructorsFor(coursesFor(id,yr).find(row=>row.id===courseInstructors[1]))
    };
    const timetableRoute=schoolRoute.match(/^timetable\/(rooms|slots|entries)(?:\/([^/]+))?$/);
    if(timetableRoute){
      const [_,kind,entryId]=timetableRoute;
      const seeded=data.timetable.filter(row=>row.school===id&&row.year===yr);
      const rooms=[...new Set(seeded.map(row=>row.room))].map((name,index)=>({
        id:"salle-demo-"+index,name,code:"S"+(index+1),active:true
      }));
      const slots=seeded.map(row=>({id:"creneau-"+row.id,year:row.year,label:row.subject,
        start_time:row.slot.split("–")[0],end_time:row.slot.split("–")[1],active:true}));
      const entries=seeded.map((row,index)=>{
        const classroom=classesFor(id,yr).find(room=>room.name===row.className);
        const subject=subjectsFor(id,yr).find(item=>item.name===row.subject);
        return {id:row.id,year:yr,classroom:classroom?.id,course:"course-"+classroom?.id+"-"+subject?.id,
          room:rooms.find(room=>room.name===row.room)?.id,slot:slots[index].id,weekday:0,teacher:row.teacher,
          start_time:slots[index].start_time,end_time:slots[index].end_time,revision:1,active:true,
          effective_from:findYear(yr).start_date,effective_to:findYear(yr).end_date};
      });
      const rowsFor=key=>{
        const changes=timetable.filter(row=>row.school===id&&row.kind===key);
        return [...({rooms,slots,entries}[key]).filter(row=>!changes.some(change=>change.id===row.id)),...changes];
      };
      const rows=rowsFor(kind);
      if(method==="GET")return {[kind]:rows};
      const existing=rows.find(row=>row.id===entryId);
      if(entryId&&!existing)throw Error("Élément fictif introuvable.");
      const record={...existing,...body,school:id,kind,id:entryId||"horaire-demo-"+(timetable.length+1),
        revision:(existing?.revision||0)+1,active:body.active??true};
      if(kind==="entries"&&record.active){
        const course=coursesFor(id,yr).find(row=>row.id===record.course);
        const slot=rowsFor("slots").find(row=>row.id===record.slot);
        const instructor=instructorsFor(course).find(row=>row.id===record.instructor);
        const staff=schoolAssignments().find(row=>row.id===instructor?.staff_assignment)?.staff;
        if(!course||!slot||!staff)throw Error("Cours, créneau ou enseignant fictif introuvable.");
        Object.assign(record,{year:course.year,classroom:course.classroom,staff,
          teacher:data.staff.find(row=>row.id===staff)?.name,start_time:slot.start_time,end_time:slot.end_time});
        if(rows.some(row=>row.id!==entryId&&row.active&&row.weekday===record.weekday&&
          row.effective_from<=record.effective_to&&row.effective_to>=record.effective_from&&
          row.start_time<record.end_time&&row.end_time>record.start_time&&
          (row.classroom===record.classroom||row.staff===record.staff||(record.room&&row.room===record.room))))
          throw Error("Conflit d’horaires fictif.");
      }
      const index=timetable.findIndex(row=>row.id===record.id&&row.school===id&&row.kind===kind);
      if(index===-1)timetable.push(record);
      else timetable[index]=record;
      return record;
    }
    if(schoolRoute==="council-choices")return {choices:[{code:"passage",label:"Passage en classe supérieure"},
      {code:"encouragements",label:"Encouragements"}]};
    if(schoolRoute==="councils"){
      if(method==="GET")return {councils:councils.filter(item=>item.school===id)};
      if(!roomById(body.classroom))throw Error("Classe fictive introuvable.");
      const council={...body,school:id,id:"conseil-"+(councils.length+1),revision:1,status:"draft",decisions:[]};
      councils.push(council);return council;
    }
    const councilRoute=schoolRoute.match(/^councils\/([^/]+)(?:\/(decisions|close))?$/);
    if(councilRoute){
      const council=councils.find(item=>item.id===councilRoute[1]&&item.school===id);
      if(!council)throw Error("Conseil fictif introuvable.");
      if(method==="GET")return council;
      if(council.status==="closed")throw Error("Conseil clôturé.");
      if(councilRoute[2]==="close"){council.status="closed";council.revision++;return council;}
      if(councilRoute[2]==="decisions"){
        const student=pupilsIn(roomById(council.classroom)).find(row=>"en-"+row.id===body.enrollment);
        const report=reports[body.report];
        if(!student||report?.status!=="published"||report.enrollment!==body.enrollment)
          throw Error("Un bulletin publié pour cet élève est requis.");
        const old=council.decisions.find(item=>item.enrollment===body.enrollment);
        const decision={...body,id:"decision-"+student.id,student_name:student.name,
          label:body.code==="passage"?"Passage en classe supérieure":"Encouragements",revision:(old?.revision||0)+1};
        council.decisions=[...council.decisions.filter(item=>item!==old),decision];council.revision++;
        return decision;
      }
    }
    if(path.endsWith("/members"))return {members:[]};
    if(schoolRoute==="enrollment-form"){
      if(method==="PUT")forms[id]={config:body.config,revision:(forms[id]?.revision||1)+1};
      return {...(forms[id]||{config:defaultForm,revision:1}),years:years(),classes:classOverview(id,yr).classes};
    }
    if(schoolRoute==="students/register"&&method==="POST"){
      const room=roomById(body.enrollment?.classroom);
      if(body.enrollment&&!room)throw Error("Classe fictive introuvable.");
      const studentId="s-demo-"+(data.students.length+1);
      const guardians=(body.guardians||[]).map((row,index)=>({...row,id:studentId+"-g"+(index+1),
        active:true,is_primary:index===0,revision:1}));
      const student={...body.student,id:studentId,school:id,year:room?.year||yr,level:room?.name||"",
        name:body.student.last_name+" "+body.student.first_name,guardian:guardians[0]?.full_name||"",
        guardians,enrolled_on:body.enrollment?.enrolled_on,average:null,absences:0};
      data.students.push(student);
      return {student:studentsOverview(id,student.year).students.find(row=>row.id===studentId),
        enrollment:enrollmentRows(id,student.year).find(row=>row.student===studentId)||null,
        charges_created:0,fees_skipped:Boolean(body.apply_fees)};
    }
    const studentRoute=schoolRoute.match(/^students\/([^/]+)(?:\/(dossier|guardians)(?:\/([^/]+))?)?$/);
    if(studentRoute){
      const student=data.students.find(row=>row.id===studentRoute[1]&&row.school===id);
      if(!student)throw Error("Élève fictif introuvable.");
      if(!student.guardians)student.guardians=student.guardian?[{id:"g-"+student.id,
        full_name:student.guardian,phone:student.phone||"",relationship:"Parent",active:true,is_primary:true,revision:1}]:[];
      const action=studentRoute[2];
      if(action==="guardians"){
        if(method==="GET")return {guardians:student.guardians};
        if(method==="PATCH"){
          const guardian=student.guardians.find(row=>row.id===studentRoute[3]);
          if(!guardian)throw Error("Responsable fictif introuvable.");
          Object.assign(guardian,body,{revision:guardian.revision+1});return guardian;
        }
        const guardian={...body,id:student.id+"-g"+(student.guardians.length+1),revision:1,active:true};
        student.guardians.push(guardian);return guardian;
      }
      if(method==="PATCH"){
        Object.assign(student,body,{revision:(student.revision||1)+1});
        if(body.last_name&&body.first_name)student.name=body.last_name+" "+body.first_name;
      }
      const row=studentsOverview(id,student.year).students.find(item=>item.id===student.id);
      const view={...student,...row,documents:student.documents||{},extra_fields:student.extra_fields||{},revision:student.revision||1};
      if(action!=="dossier")return view;
      const finance_visible=can(id,"school.finance.read");
      const form=forms[id]?.config||defaultForm;
      return {student:view,form,guardians:student.guardians,finance_visible,sensitive_visible:can(id,"school.students.sensitive.read"),
        missing_documents:form.documents.filter(doc=>doc.required&&!view.documents[doc.key]).map(doc=>doc.label),
        enrollments:enrollmentRows(id,student.year).filter(item=>item.student===student.id).map(item=>({
          ...item,finance:finance_visible?{...row.finance,currency:"XAF",
            charges:chargesFor(id,student.year).filter(charge=>charge.enrollment===item.id),payments:[]}:null
        }))};
    }
    if(schoolRoute==="students")return {students:studentsOverview(id,yr).students};
    const classRoster=schoolRoute.match(/^classes\/([^/]+)\/(students|enroll)$/);
    if(classRoster){
      const room=roomById(classRoster[1]);
      if(!room)throw Error("Classe fictive introuvable.");
      if(method==="POST"&&classRoster[2]==="enroll"){
        const enrolled=[],failed=[];
        for(const studentId of body.students||[]){
          const student=data.students.find(row=>row.id===studentId&&row.school===id&&row.year===room.year);
          if(!student||student.level){failed.push({student:studentId,error:"Dossier indisponible ou déjà inscrit."});continue;}
          student.level=room.name;enrolled.push(studentId);
        }
        return {enrolled,failed};
      }
      return {students:studentsOverview(id,room.year).students.filter(row=>row.enrollment?.classroom.id===room.id)};
    }
    if(schoolRoute.startsWith("enrollments/")&&method==="PATCH"){
      const room=roomById(body.classroom);
      const student=data.students.find(row=>row.school===id&&"en-"+row.id===schoolRoute.split("/")[1]);
      if(!room||student?.year!==room.year)throw Error("Classe ou élève indisponible pour ce transfert.");
      student.level=room.name;student.enrollment_revision=(student.enrollment_revision||1)+1;
      return enrollmentRows(id,room.year).find(row=>row.student===student.id);
    }
    if(path.endsWith("/guardians-by-class")){
      const room=search.get("classroom");
      return {families:studentsFor(id,yr).filter(s=>s.level===classesFor(id,yr).find(c=>c.id===room)?.name)
        .map(s=>({student_id:s.id,student_name:s.name,
          guardians:[{id:"g-"+s.id,name:s.guardian,phone:"",email:"",relationship:"Parent"}]}))};
    }
    if(path.endsWith("/parent-links"))return {links:[]};
    if(schoolRoute==="reports"){
      const classroom=roomById(search.get("classroom"));
      const reportYear=classroom?.year||yr;
      const pupils=(classroom?pupilsIn(classroom):studentsFor(id,reportYear)).map(s=>({
        id:"en-"+s.id,name:s.name,year:s.year,student:s.id,can_prepare:findYear(s.year).active
      }));
      if(method!=="GET"){
        const student=data.students.find(row=>row.school===id&&"en-"+row.id===body.enrollment);
        if(!student||!findYear(student.year).active)throw Error("Inscription fictive introuvable ou année clôturée.");
        const reportId="report-"+student.id+"-"+(body.period||"annuel");
        const previous=reports[reportId];
        if(previous?.status==="published")throw Error("Ce bulletin est publié.");
        const rec={id:reportId,school:id,year:student.year,enrollment:body.enrollment,
          period:body.period||null,revision:(previous?.revision||0)+1,status:"draft"};
        rec.snapshot=reportSnapshot(id,student.year,rec);
        reports[rec.id]=rec;
        return rec;
      }
      const selected=Object.values(reports).filter(report=>report.school===id&&
        pupils.some(pupil=>pupil.id===report.enrollment));
      return {reports:selected,pupils};
    }
    const reportPath=path.match(/^schools\/[^/]+\/reports\/([^/]+)(?:\/(publish|pdf))?$/);
    if(reportPath){
      const reportId=reportPath[1],action=reportPath[2];
      const rec=reports[reportId];
      if(!rec||rec.school!==id)throw Error("Bulletin de démonstration introuvable.");
      if(action==="pdf"){
        const snapshot=rec.snapshot;
        return {filename:"bulletin-demo.pdf",lines:["Bulletin scolaire - DEMONSTRATION",
          snapshot.student.last_name+" "+snapshot.student.first_name,snapshot.class.name+" / "+snapshot.year.name,
          snapshot.period?.name||"Année complète",...snapshot.subjects.map(row=>row.subject+" : "+(row.result.score??"—")),
          "Résultat général : "+(snapshot.overall.score??"—")]};
      }
      if(action==="publish"&&method!=="GET"){
        rec.status="published";rec.revision++;
      }
      return rec;
    }
    if(path===`schools/${id}/enrollments`)return {enrollments:enrollmentRows(id,yr)};
    if(path.endsWith("/finance/schedules")){
      if(method!=="GET"){
        if(body.currency!=="XAF")throw Error("Les tarifs fictifs sont disponibles en XAF.");
        const schedule={...body,id:"tarif-demo-"+(schedules.length+1),school:id,active:true};
        schedules.push(schedule);return schedule;
      }
      return {schedules:order.flatMap(year=>schedulesFor(id,year.id)),years:years(),
        classes:order.flatMap(year=>classOverview(id,year.id).classes)};
    }
    if(path.endsWith("/finance/summary")){
      const list=invoicesFor(id,yr),billed=list.reduce((n,f)=>n+f.total,0);
      const paid=list.reduce((n,f)=>n+f.paid,0);
      return {currencies:{XAF:{billed,paid,balance:billed-paid,overdue:billed-paid}}};
    }
    if(schoolRoute==="finance/cash/closings"){
      if(method!=="GET"){
        const expected=body.day===today?financeOverview(id,yr).today.by_method.especes:0;
        const counted=Number(body.counted);
        if(!Number.isFinite(counted)||counted<0)throw Error("Montant compté invalide.");
        const entry={id:"close-demo-"+(closings.length+1),school:id,day:body.day||today,
          currency:body.currency||"XAF",submitted_by:"Économe (simulation)",status:"pending",
          expected,counted,difference:counted-expected,
          adjustment_since_submission:"0.00",transfers:[]};
        closings.push(entry);return entry;
      }
      return {closings:closings.filter(row=>row.school===id)};
    }
    const cashRoute=schoolRoute.match(/^finance\/cash\/closings\/([^/]+)\/(approve|transfers)(?:\/([^/]+)\/approve)?$/);
    if(cashRoute&&method==="POST"){
      const closing=closings.find(row=>row.id===cashRoute[1]&&row.school===id);
      if(!closing)throw Error("Clôture fictive introuvable.");
      if(cashRoute[2]==="approve"){
        if(!can(id,"school.finance.approve"))throw Error("Ce profil ne peut pas contrôler la caisse.");
        closing.status="approved";closing.approved_by=DEMO_ROLES[role].label;return closing;
      }
      if(closing.status!=="approved")throw Error("La clôture doit être validée.");
      if(cashRoute[3]){
        if(!can(id,"school.finance.approve"))throw Error("Ce profil ne peut pas contrôler la remise.");
        const transfer=closing.transfers.find(row=>row.id===cashRoute[3]);
        if(!transfer)throw Error("Justificatif fictif introuvable.");
        transfer.approved_by=DEMO_ROLES[role].label;return transfer;
      }
      if(!can(id,"school.finance.deposit"))throw Error("Ce profil ne peut pas déclarer de remise.");
      const transfer={...body,id:"remise-demo-"+(closing.transfers.length+1)};
      closing.transfers.push(transfer);return transfer;
    }
    if(path.endsWith("/finance/charges")){
      if(method!=="GET"){
        const student=data.students.find(row=>row.school===id&&"en-"+row.id===body.enrollment);
        const schedule=student&&schedulesFor(id,student.year).find(row=>row.id===body.schedule);
        if(!schedule)throw Error("Inscription ou tarif fictif introuvable.");
        const invoice={id:"charge-demo-"+(data.invoices.length+1),student:student.id,school:id,year:student.year,
          schedule:schedule.id,label:schedule.label,total:Number(schedule.amount),paid:0,currency:schedule.currency,
          due_date:schedule.due_date};
        if(data.invoices.some(row=>row.student===student.id&&row.schedule===schedule.id))
          throw Error("Ce tarif est déjà affecté à l’élève.");
        data.invoices.push(invoice);
        return chargesFor(id,student.year).find(row=>row.id===invoice.id);
      }
      const enrollment=search.get("enrollment");
      return {charges:chargesFor(id,yr).filter(f=>!enrollment||f.enrollment===enrollment)};
    }
    if(path.endsWith("/finance/batches")&&method!=="GET"){
      const key=body.idempotency_key && id+":"+body.idempotency_key;
      const fingerprint=JSON.stringify(body);
      if(key&&batches.has(key)){
        const batch=batches.get(key);
        if(batch.fingerprint!==fingerprint)throw Error("Cette référence a déjà été utilisée.");
        return batch.result;
      }
      const lines=Array.isArray(body.lines)?body.lines:[];
      const allocated=new Map();
      const student=data.students.find(s=>s.school===id&&"en-"+s.id===body.enrollment);
      for(const line of lines){
        const invoice=data.invoices.find(f=>f.school===id&&f.id===line.charge&&f.student===student?.id);
        const cents=Math.round(Number(line.amount)*100);
        const total=(allocated.get(invoice)||0)+cents;
        if(!invoice||!Number.isSafeInteger(cents)||cents<=0||total>Math.round(remaining(invoice)*100))
          throw Error("Paiement fictif invalide : frais ou montant incorrect.");
        allocated.set(invoice,total);
      }
      if(!allocated.size)throw Error("Aucun frais sélectionné.");
      for(const [invoice,cents] of allocated)invoice.paid=(Math.round(invoice.paid*100)+cents)/100;
      const total=[...allocated.values()].reduce((sum,cents)=>sum+cents,0)/100;
      const batchId="SIM-"+String(payments.length+1).padStart(4,"0");
      payments.unshift({id:batchId,school:id,year:student.year,student:student.name,
        classroom:student.level,amount:total,method:body.method,recorded_at:today+"T10:30:00+01:00"});
      const result={id:batchId,total,currency:"XAF",simulated:true,
        receipt_url:`/api/v1/schools/${id}/finance/payments/${batchId}/receipt`};
      if(key)batches.set(key,{fingerprint,result});
      return result;
    }
    if(path.endsWith("/finance/payments")&&method==="GET")
      return {payments:payments.filter(payment=>payment.school===id&&payment.year===yr)};
    const receipt=schoolRoute.match(/^finance\/payments\/([^/]+)\/receipt$/);
    if(receipt){
      const payment=financeOverview(id,yr).today.payments.find(row=>row.id===receipt[1]);
      if(!payment)throw Error("Reçu fictif introuvable.");
      return {filename:"recu-demo.pdf",lines:["Reçu de paiement - DEMONSTRATION",
        "Référence "+payment.id,school.name,payment.student+" / "+payment.classroom,
        payment.amount+" XAF",payment.method+" / "+payment.recorded_at.slice(0,10)]};
    }
    const financeStatement=path.match(/^schools\/[^/]+\/finance\/enrollments\/([^/]+)\/statement$/);
    if(financeStatement){
      const list=chargesFor(id,yr).filter(f=>f.enrollment===financeStatement[1]);
      const billed=list.reduce((sum,f)=>sum+f.amount,0),paid=list.reduce((sum,f)=>sum+f.paid,0);
      return {totals:{XAF:{billed,paid,balance:billed-paid}}};
    }
    const conductMatch = path.match(/^schools\/[^/]+\/attendance\/classes\/([^/]+)\/conduct(?:\/([^/]+)\/withdraw)?$/);
    if(conductMatch){
      const room = data.classes.find(row=>row.id===conductMatch[1]&&row.school===id);
      const roster = room ? studentsFor(id,room.year).filter(row=>row.level===room.name)
        .map(row=>({id:"en-"+row.id,name:row.name,matricule:"DEMO-"+row.id})) : [];
      const canEdit = Boolean(room&&findYear(room.year).active);
      const names = new Map(roster.map(row=>[row.id,row.name]));
      const records = conduct.filter(row=>names.has(row.enrollment));
      const withStudent = row=>({...row,student:names.get(row.enrollment)});
      if(method==="GET")return {roster,notices:records.map(withStudent),can_publish:canEdit,can_withdraw:canEdit};
      if(!canEdit)throw Error("Année scolaire clôturée.");
      if(conductMatch[2]){
        const row = records.find(item=>item.id===conductMatch[2]);
        if(!row)throw Error("Communication introuvable.");
        row.withdrawn = true;
        return withStudent(row);
      }
      if(!names.has(body.enrollment))throw Error("Élève introuvable dans cette classe.");
      const row = {id:"conduct-demo-"+conduct.length,enrollment:body.enrollment,date:body.date,
        kind:body.kind,label:body.kind==="sanction"?"Sanction":"Observation de comportement",
        message:body.message,withdrawn:false};
      conduct.push(row);
      return withStudent(row);
    }
    if(path==="parents/children")return {parent_username:"parent-demo",children:data.students.filter(s=>["s1","s4","s7"].includes(s.id)).map(s=>({
      student:s.id,...splitName(s.name),school_name:schoolData(s.school).name,
      matricule_yem:"YEM-"+s.id,student_code:"DEMO-"+s.id}))};
    const parentMatch=path.match(/^parents\/children\/([^/]+)\/([^/]+)/);
    if(parentMatch){
      const child=data.students.find(s=>s.id===parentMatch[1]),kind=parentMatch[2];
      if(kind==="reports"){
        const published=Object.values(reports).filter(row=>row.enrollment==="en-"+child?.id&&row.year===yr&&row.status==="published");
        const pdfId=path.match(/\/reports\/([^/]+)\/pdf$/)?.[1];
        if(pdfId){
          const report=published.find(row=>row.id===pdfId);
          if(!report&&pdfId!=="report-demo")throw Error("Bulletin fictif introuvable.");
          return {filename:"bulletin-demo.pdf",lines:["Bulletin scolaire - DEMONSTRATION",child.name,
            child.level+" / "+child.year,"Résultat : "+(report?.snapshot.overall.score??child.average??"—")]};
        }
        return {reports:published.length?published.map(row=>({id:row.id,year:row.year,
          period:row.snapshot.period?.name||"Année complète",score:row.snapshot.overall.score})):
          child&&child.year===yr?[{id:"report-demo",year:yr,period:"1er trimestre",score:child.average}]:[]};
      }
      if(kind==="enrollments")return {enrollments:child?[{id:"en-"+child.id,year:child.year,year_id:child.year,
        year_status:findYear(child.year).status,classroom:child.level,active:true,status:"inscrit",
        class_size:studentsFor(child.school,child.year).filter(row=>row.level===child.level).length}]:[]};
      if(kind==="grades")return {grades:child?[{id:"grade-"+child.id,
        subject:subjectsFor(child.school,child.year).find(subject=>child.level.startsWith(subject.level+" "))?.name||"Travail de classe",
        assessment:"Contrôle continu",
        date:"2026-11-04",period:"1er trimestre",score:child.average,scale_kind:"numeric",scale_max:20,weight:1}]:[]};
      if(kind==="attendance")return {attendance:[{id:"att-demo",date:"2026-11-04",slot:"Matin",status:"Retard",group:"late",justified:false}],
        totals:{absent:0,late:1,present:0},conduct:conduct.filter(row=>row.enrollment==="en-"+child?.id&&!row.withdrawn)};
      if(kind==="finance"){
        const charges=child?chargesFor(child.school,yr).filter(charge=>charge.enrollment==="en-"+child.id):[];
        return {totals:{XAF:charges.reduce((total,charge)=>({
          billed:total.billed+charge.amount,paid:total.paid+charge.paid,balance:total.balance+charge.balance
        }),{billed:0,paid:0,balance:0})},charges};
      }
      if(kind==="timetable")return {entries:[{id:"t-demo",weekday:0,start:"08:00",end:"09:00",subject:"Mathématiques",teacher:"Mme Mba",room:"Salle 1"}]};
      return {};
    }
    const mobileCharge=path.match(/^parents\/singpay\/charge\/([^/]+)\/(quote|pay)$/);
    if(mobileCharge){
      const invoice=data.invoices.find(row=>row.id===mobileCharge[1]&&["s1","s4","s7"].includes(row.student));
      if(!invoice)throw Error("Frais fictifs introuvables.");
      if(mobileCharge[2]==="quote")return {balance_xaf:remaining(invoice),
        merchant:{active:true,beneficiary:schoolData(invoice.school).name,mode:"test",revision:1,
          fee_basis_points:0,fee_fixed_xaf:0},
        payments:mobilePayments.filter(row=>row.charge===invoice.id)};
      const existing=mobilePayments.find(row=>row.key===body.idempotency_key&&row.charge===invoice.id);
      if(existing)return existing;
      if(!Number.isInteger(body.amount_xaf)||body.amount_xaf<100||body.amount_xaf>remaining(invoice))
        throw Error("Montant fictif invalide.");
      const payment={id:"mobile-demo-"+(mobilePayments.length+1),reference:"SIM-MM-"+(mobilePayments.length+1),
        key:body.idempotency_key,charge:invoice.id,amount_xaf:body.amount_xaf,state:"pending",
        notice:"Transaction fictive. Aucun code ni confirmation sur téléphone n’est nécessaire."};
      mobilePayments.push(payment);return payment;
    }
    const mobileRefresh=path.match(/^parents\/singpay\/payments\/([^/]+)\/refresh$/);
    if(mobileRefresh){
      const payment=mobilePayments.find(row=>row.id===mobileRefresh[1]);
      if(!payment)throw Error("Transaction fictive introuvable.");
      payment.state="test_success";
      payment.notice="Simulation confirmée. Aucun compte Mobile Money débité.";
      return payment;
    }
    if(path.startsWith("parents/")&&method==="GET")return {schools:[],applications:[]};
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
        for(const row of body.class_assignments||[])assignments.push({...row,school:id,staff:newPerson.id,
          id:"affectation-demo-"+(assignments.length+1),active:true});
        return {staff:{...newPerson,...splitName(newPerson.name),staff_code:"DEMO-"+newPerson.id},account_created:Boolean(body.account),appointments:body.appointments||[]};
      }
      return {school_name:school.name,can_create_account:can(id,"school.members.write"),can_appoint:can(id,"school.organization.manage"),can_manage_cycle_access:role==="proprietaire",
        education_cycles:[school.type],academic_cycles:[{id:"cycle-demo",code:"college",name:school.type}],
        actor_access_cycle_ids:null,existing_accounts:[],roles,positions,years:years(),
        classes:classOverview(id,yr).classes};
    }
    if(path.includes("/onboarding")||path.includes("/staff/setup"))return {staff:[],roles:[],functions:[],appointments:[],years:years(),classes:[]};
    if(method!=="GET")throw Error("Cette action n’est pas encore simulée.");
    // Les modules non préparés ne peuvent EN AUCUN CAS contacter une API réelle.
    return {items:[],results:[],students:[],classes:[],members:[],roles:[],functions:[],
      years:years(),year:findYear(yr),schools:schoolList(),groups:[],charges:[],enrollments:[],
      staff:[],settings:{},config:{},permissions:DEMO_ROLES[role].permissions};
  }
  async function fetch(input,options={}){
    const url=String(typeof input==="string"?input:input?.url||"");
    const parsed=new URL(url,"https://demo.yem.invalid");
    const method=(options?.method||"GET").toUpperCase();
    if(!parsed.pathname.startsWith("/api/v1/"))return response({error:"Démonstration hors ligne : accès réseau bloqué."},403);
    const path=parsed.pathname.slice("/api/v1/".length).replace(/\/$/,"");
    let body={};try{if(options.body)body=JSON.parse(options.body)}catch{}
    try{
      const result=fixtureFor(path,parsed.searchParams,method,body);
      return response(structuredClone(result),result.error?400:200);
    }
    catch(error){return response({error:"Données de présentation indisponibles : "+error.message},400)}
  }
  function reset(){data=createDemoState();organizations=initialOrganizations();audit=[];platformAccess=null;assessments={};grades={};reports={};closings=[];payments=[];batches=new Map();sessions=[];calendar=[];councils=[];admissions=[];mobilePayments=[];schedules=[];timetable=[];assignments=[];forms={};conduct=initialConduct();}
  return {fetch,reset,setRole:next=>{role=next;}};
}
