import {expect,test} from "vitest";
import {createOfflineDemoBackend} from "./demo-api-sandbox.js";

const load=async (backend,path,options)=>{
  const response=await backend.fetch("/api/v1/"+path,options);
  expect(response.ok).toBe(true);
  return response.json();
};

test("la caisse fictive fournit les totaux de la veille et les méthodes de paiement",async()=>{
  const backend=createOfflineDemoBackend();
  const finance=await load(backend,"schools/lycee/overview/finance?year=2026-2027");
  expect(finance.yesterday).toEqual(expect.objectContaining({total:expect.any(Number),count:expect.any(Number)}));
  expect(finance.today.by_method).toEqual(expect.objectContaining({especes:expect.any(Number)}));
  expect(Array.isArray(finance.today.payments)).toBe(true);
  expect((await load(backend,"schools/lycee/finance/charges?enrollment=en-s1")).charges.length).toBeGreaterThan(0);
});

test("les cours, périodes, évaluations, effectifs et notes sont fournis au module réel",async()=>{
  const backend=createOfflineDemoBackend();
  const courses=await load(backend,"schools/lycee/courses");
  const periods=await load(backend,"schools/lycee/academic/periods?year=2026-2027");
  const subjects=await load(backend,"schools/lycee/subjects");
  expect(courses.courses.some(c=>c.classroom==="c1")).toBe(true);
  expect(periods.periods).toHaveLength(3);
  expect(subjects.subjects.some(s=>s.name==="Mathématiques")).toBe(true);
  const list=await load(backend,"schools/lycee/courses/course-c1-m1/assessments");
  expect(list.assessments[0].policy.scale.max).toBe(20);
  const roster=await load(backend,"schools/lycee/assessments/assessment-course-c1-m1/roster");
  const grades=await load(backend,"schools/lycee/assessments/assessment-course-c1-m1/grades");
  expect(roster.students.some(s=>s.last_name==="Essono")).toBe(true);
  expect(grades.grades.some(g=>g.enrollment==="en-s1")).toBe(true);
});

test("les encaissements simulés ne peuvent jamais sortir du bac à sable",async()=>{
  const backend=createOfflineDemoBackend();
  const original=(await load(backend,"schools/lycee/finance/charges?enrollment=en-s1")).charges;
  const transaction=await load(backend,"schools/lycee/finance/batches",{
    method:"POST",
    body:JSON.stringify({enrollment:"en-s1",method:"especes",
      lines:[{charge:"f1",amount:"1000.00"}],idempotency_key:"test-fictif"})
  });
  expect(transaction.simulated).toBe(true);
  expect(transaction.currency).toBe("XAF");
  const after=(await load(backend,"schools/lycee/finance/charges?enrollment=en-s1")).charges;
  expect(after[0].balance).toBe(original[0].balance-1000);
  const fresh=createOfflineDemoBackend();
  const newData=(await load(fresh,"schools/lycee/finance/charges?enrollment=en-s1")).charges;
  expect(newData[0].balance).toBe(original[0].balance);
});
test("un encaissement répété ou refusé conserve le solde et le journal cohérents",async()=>{
  const backend=createOfflineDemoBackend();
  const payload={enrollment:"en-s1",method:"especes",idempotency_key:"demo-unique",
    lines:[{charge:"f1",amount:"1500.25"}]};
  const pay=data=>backend.fetch("/api/v1/schools/lycee/finance/batches",{
    method:"POST",body:JSON.stringify(data)
  });
  const first=await (await pay(payload)).json();
  expect(await (await pay(payload)).json()).toEqual(first);
  const refused=await pay({...payload,idempotency_key:"demo-invalid",
    lines:[{charge:"f1",amount:"50000"},{charge:"f1",amount:"50000"}]});
  expect(refused.ok).toBe(false);
  expect((await load(backend,"schools/lycee/finance/charges?enrollment=en-s1")).charges[0].balance).toBe(73499.75);
  const journal=await load(backend,"schools/lycee/overview/finance");
  expect(journal.today.payments.filter(row=>row.id===first.id)).toHaveLength(1);
  const receipt=await load(backend,first.receipt_url.replace("/api/v1/",""));
  expect(receipt.lines).toContain("1500.25 XAF");
  backend.reset();
  expect((await load(backend,"schools/lycee/finance/charges?enrollment=en-s1")).charges[0].balance).toBe(75000);
});

test("le paiement mobile simulé ne débite aucun solde scolaire",async()=>{
  const backend=createOfflineDemoBackend();
  const path="parents/singpay/charge/f1";
  const initial=await load(backend,path+"/quote");
  expect(initial.merchant.mode).toBe("test");
  const payment=await load(backend,path+"/pay",{method:"POST",
    body:JSON.stringify({amount_xaf:1000,idempotency_key:"mobile-fictif"})});
  expect(payment.state).toBe("pending");
  const confirmation=await load(backend,"parents/singpay/payments/"+payment.id+"/refresh",
    {method:"POST",body:"{}"});
  expect(confirmation.state).toBe("test_success");
  expect((await load(backend,path+"/quote")).balance_xaf).toBe(initial.balance_xaf);
});
test("la console provisionne un établissement fictif et ouvre son espace scolaire",async()=>{
  const backend=createOfflineDemoBackend();
  backend.setRole("platform");
  const post=body=>({method:"POST",body:JSON.stringify(body)});
  const school=await load(backend,"platform/schools",post({school_name:"Collège des Manguiers",
    organization_id:"org-demo",school_type:"college_lycee",education_cycles:["college"],
    governance_mode:"prive_laique",username:"direction.test",first_name:"Ariane",last_name:"Exemple",
    role:"direction"}));
  expect((await load(backend,"platform/schools/"+school.id+"/detail")).members[0].username).toBe("direction.test");
  await load(backend,"platform/schools/"+school.id+"/admin-access",post({}));
  expect((await load(backend,"schools")).schools.map(row=>row.id)).toEqual([school.id]);
  const access=await load(backend,"schools/"+school.id+"/my-access");
  expect(access.role).toBe("direction");
  expect((await load(backend,"platform/audit")).events[0].school).toBe("Collège des Manguiers");
});

test("une preuve de concours doit être vérifiée avant l’admission fictive",async()=>{
  const backend=createOfflineDemoBackend();
  const base="schools/lycee/admissions";
  const post=body=>({method:"POST",body:JSON.stringify(body)});
  const application=await load(backend,base,post({classroom:"c1",year:"2026-2027",route:"concours",
    first_name:"Aurore",last_name:"Exemple",guardian_name:"M. Exemple"}));
  const path=base+"/"+application.id;
  expect((await backend.fetch("/api/v1/"+path+"/decide",post({revision:1,status:"accepted",reason:"Test"}))).ok).toBe(false);
  const eligible=await load(backend,path+"/eligibility",post({revision:1,result:"eligible",reason:"Résultat vérifié"}));
  const evidence=await load(backend,path+"/documents",post({revision:eligible.revision,code:"concours_result",reference:"SIM-2026"}));
  const review=await load(backend,path+"/documents/"+evidence.documents[0].id+"/review",post({
    revision:evidence.revision,status:"verified",reason:"Pièce conforme"
  }));
  expect(review.documents[0].status).toBe("verified");
  expect((await load(backend,path+"/decide",post({revision:review.revision,status:"accepted",reason:"Dossier complet"}))).status).toBe("accepted");
});

test("le propriétaire enregistre un périmètre et peut déléguer puis retirer une attribution",async()=>{
  const backend=createOfflineDemoBackend();
  backend.setRole("proprietaire");
  const base="schools/lycee";
  const send=(method,body)=>({method,body:JSON.stringify(body)});
  const staff=await load(backend,base+"/staff/onboard");
  const member=staff.existing_accounts[0];
  const scope=[staff.academic_cycles[0].id];
  await load(backend,base+"/members/"+member.member_id+"/cycle-access",send("PATCH",{access_cycle_ids:scope,reason:"Affectation fictive"}));
  expect((await load(backend,base+"/staff/onboard")).existing_accounts[0].access_cycle_ids).toEqual(scope);
  const grant=await load(backend,base+"/delegations",send("POST",{
    user_id:member.user_id,permissions:["school.classes.manage"],class_cycle:staff.academic_cycles[0].code,
    reason:"Remplacement temporaire"
  }));
  const revoked=await load(backend,base+"/delegations/"+grant.id,send("DELETE",{reason:"Retour du titulaire"}));
  expect(revoked.revocation_reason).toBe("Retour du titulaire");
  backend.reset();
  expect((await load(backend,base+"/staff/onboard")).existing_accounts[0].access_cycle_ids).toBeNull();
});

test("un rectificatif publié garde le bulletin original et génère son propre PDF fictif",async()=>{
  const backend=createOfflineDemoBackend();
  const base="schools/lycee/reports";
  const post=body=>({method:"POST",body:JSON.stringify(body)});
  const report=await load(backend,base,post({enrollment:"en-s1"}));
  const path=base+"/"+report.id;
  const original=await load(backend,path+"/publish",post({revision:report.revision}));
  const corrected=await load(backend,path+"/amendments",post({
    course:original.snapshot.subjects[0].course,percent:86,reason:"Erreur de transcription",revision:0
  }));
  expect((await load(backend,path)).snapshot).toEqual(original.snapshot);
  expect((await load(backend,path+"/amendments")).amendments).toEqual([corrected]);
  const pdf=await load(backend,path+"/amendments/"+corrected.id+"/pdf");
  expect(pdf.lines).toContain("Mathématiques : 72.5 % / 86 %");
});

test("le fichier CSV fictif est prévisualisé avant l’écriture et un nouvel envoi reste sans doublon",async()=>{
  const backend=createOfflineDemoBackend();
  const base="schools/lycee/imports/students/";
  const file=new File(["Nom;Prénoms;Classe\nKassa;Nadia;6e A"],"eleves-fictifs.csv",{type:"text/csv"});
  const form=new FormData();
  form.set("file",file);
  form.set("header_row","1");
  const post={method:"POST",body:form};
  const info=await load(backend,base+"inspect",post);
  expect(info.suggested_mapping).toEqual({"0":"last_name","1":"first_name","2":"classroom"});
  form.set("mapping",JSON.stringify(info.suggested_mapping));
  form.set("year","2026-2027");
  const preview=await load(backend,base+"preview",post);
  expect(preview.valid).toBe(1);
  expect((await load(backend,"schools/lycee/students")).students.some(row=>row.last_name==="Kassa")).toBe(false);
  form.set("token",preview.token);
  form.set("template_name","Exemple fictif");
  expect((await load(backend,base+"commit",post)).imported).toBe(1);
  expect((await load(backend,base+"commit",post)).already_imported).toBe(true);
  const students=(await load(backend,"schools/lycee/students")).students.filter(row=>row.last_name==="Kassa");
  expect(students).toHaveLength(1);
  expect(students[0].enrollment.classroom.id).toBe("c1");
  const exported=await backend.fetch("/api/v1/"+base+"export",{method:"POST",body:JSON.stringify({year:"2026-2027"})});
  expect(await exported.text()).toContain("Kassa;Nadia");
});

test("la comptabilité annule un encaissement fictif en conservant son historique",async()=>{
  const backend=createOfflineDemoBackend();
  const base="schools/lycee/finance/";
  const post=body=>({method:"POST",body:JSON.stringify(body)});
  backend.setRole("econome");
  const payment=await load(backend,base+"payments",post({charge:"f1",amount:"500.25",method:"especes",idempotency_key:"reverse"}));
  expect((await load(backend,base+"charges?enrollment=en-s1")).charges[0].balance).toBe(74499.75);
  backend.setRole("comptabilite");
  const result=await load(backend,base+"payments/"+payment.id+"/void",post({reason:"Erreur de saisie fictive"}));
  expect(result.voided).toBe(true);
  expect((await load(backend,base+"charges?enrollment=en-s1")).charges[0].balance).toBe(75000);
  expect((await load(backend,base+"payments?charge=f1")).payments[0].voided).toBe(true);
  expect((await load(backend,"schools/lycee/overview/finance")).today.payments.some(row=>row.id===payment.id)).toBe(false);
});
