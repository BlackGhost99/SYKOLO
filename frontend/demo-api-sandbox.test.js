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
