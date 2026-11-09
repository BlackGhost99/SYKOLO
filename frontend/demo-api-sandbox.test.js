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
  const periods=await load(backend,"schools/lycee/academic/periods");
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
