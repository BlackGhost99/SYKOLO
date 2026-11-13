// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor,within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TeacherMobileWorkspace from "./TeacherMobileWorkspace.jsx";
import TeacherMobileGrades from "./TeacherMobileGrades.jsx";
import TeacherMobileAttendance from "./TeacherMobileAttendance.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const root="schools/lycee/";
const classA={id:"3a",name:"Troisième A",active:true,year:"2026"};
const course={id:"math",classroom:"3a",year:"2026",subject:"math-subject",active:true};
const subjects=[{id:"math-subject",name:"Mathématiques"}];
const assessment={id:"devoir1",active:true,name:"Devoir 1",assessment_date:"2026-10-22",revision:1,
  published:false,weight:"2",policy:{name:"Barème numérique",scale:{kind:"numeric",max:20}}};
const student={enrollment_id:"enrol1",last_name:"Mba",first_name:"Eva",student_code:"Y-1"};
function apiMock(){
  const fetchMock=vi.fn(async (url,options={})=>{
    const path=String(url).replace(/^\/api\/v1\//,"");
    if(path==="auth/csrf")return Response.json({});
    if(path===root+"courses/math/assessments")return Response.json({assessments:[assessment]});
    if(path===root+"assessments/devoir1/roster")return Response.json({students:[student]});
    if(path===root+"assessments/devoir1/grades")return Response.json({grades:[]});
    if(path===root+"assessments/devoir1/grades/batch")return Response.json({saved:1,grades:[]});
    if(path===root+"courses/math/averages")return Response.json({
      student_count:1,assessment_count:1,calculated_count:1,class_average_on_20:"17.50",
      students:[{enrollment:"enrol1",first_name:"Eva",last_name:"Mba",evaluated:1,expected:1,
        average_on_20:"17.50",complete:true}],
    });
    if(path===root+"attendance/options?classroom=3a")return Response.json({statuses:[
      {code:"present",label:"Présent",group:"present"},
      {code:"absent",label:"Absent",group:"absent"},
      {code:"late",label:"Retard",group:"late"},
    ]});
    if(path===root+"attendance/sessions?classroom=3a")return Response.json({sessions:[
      {id:"session1",date:"2026-11-13",label:"Mathématiques"},
    ]});
    if(path===root+"attendance/sessions/session1")return Response.json({
      id:"session1",date:"2026-11-13",label:"Mathématiques",roster:[
        {enrollment:"enrol1",last_name:"Mba",first_name:"Eva",student_code:"Y-1",mark:null},
      ],
    });
    if(path===root+"attendance/sessions/session1/marks")return Response.json({marks:[{enrollment:"enrol1"}]});
    if(path===root+"curriculum/my-courses")return Response.json({courses:[course]});
    if(path===root+"academic/classes")return Response.json({classes:[classA]});
    if(path===root+"academic/periods")return Response.json({periods:[]});
    if(path===root+"subjects")return Response.json({subjects});
    if(path===root+"staff/me/assignments")return Response.json({assignments:[
      {active:true,year:"2026",classroom:"3a"},
    ]});
    if(path===root+"staff/me/profile")return Response.json({
      staff_id:"staff",first_name:"Paul",last_name:"Mba",staff_code:"P-14",
      position:"Professeur",photo_url:null,revision:1,presentation:"",
    });
    return Response.json({});
  });
  vi.stubGlobal("fetch",fetchMock);
  return fetchMock;
}
test("notes : le professeur enregistre son lot de modifications via l'API atomique",async()=>{
  const fetchMock=apiMock();
  const user=userEvent.setup();
  render(<TeacherMobileGrades schoolId="lycee" courses={[course]} classes={[classA]}
    subjects={subjects} periods={[]} yearId="2026"/>);
  await user.selectOptions(await screen.findByRole("combobox",{name:"Matière enseignée"}),"math");
  await user.selectOptions(await screen.findByRole("combobox",{name:"Évaluation"}),"devoir1");
  const input=await screen.findByRole("spinbutton",{name:"Note de Mba"});
  await user.type(input,"17.5");
  await user.click(screen.getByRole("button",{name:"Enregistrer 1 modification(s)"}));
  await waitFor(()=>expect(fetchMock.mock.calls.some(([url])=>String(url).endsWith("/grades/batch"))).toBe(true));
  const saved=fetchMock.mock.calls.find(([url])=>String(url).endsWith("/grades/batch"));
  expect(JSON.parse(saved[1].body).grades).toEqual([
    {enrollment:"enrol1",revision:0,score:17.5},
  ]);
});
test("moyennes : la vue indique le caractère provisoire et le barème normalisé",async()=>{
  apiMock();const user=userEvent.setup();
  render(<TeacherMobileGrades schoolId="lycee" courses={[course]} classes={[classA]}
    subjects={subjects} periods={[]} yearId="2026" mode="moyennes"/>);
  await user.selectOptions(await screen.findByRole("combobox",{name:"Matière enseignée"}),"math");
  expect(await screen.findByText("17,5 / 20")).toBeTruthy();
  expect(screen.getByText(/Résultats provisoires/)).toBeTruthy();
  expect(screen.getByText(/incomplet|complet/)).toBeTruthy();
});
test("appel : la sélection de présence réutilise les statuts paramétrés de l'école",async()=>{
  const fetchMock=apiMock();const user=userEvent.setup();
  render(<TeacherMobileAttendance schoolId="lycee" classes={[classA]}
    assignments={[{active:true,classroom:"3a",year:"2026"}]} workingYearId="2026"/>);
  await user.selectOptions(screen.getByRole("combobox",{name:"Classe pour l'appel"}),"3a");
  await user.selectOptions(await screen.findByRole("combobox",{name:"Séance d'appel"}),"session1");
  const group=await screen.findByRole("group",{name:"Présence de Mba"});
  await user.click(within(group).getByRole("button",{name:"Absent"}));
  await user.click(screen.getByRole("button",{name:"Enregistrer 1 présence(s)"}));
  await waitFor(()=>expect(fetchMock.mock.calls.some(([url,opts])=>
    String(url).endsWith("/attendance/sessions/session1/marks")&&opts?.method==="POST"
  )).toBe(true));
  const call=fetchMock.mock.calls.find(([url])=>String(url).endsWith("/attendance/sessions/session1/marks"));
  expect(JSON.parse(call[1].body).marks[0].status).toBe("absent");
  expect(JSON.parse(call[1].body).marks[0].revision).toBe(0);
});
test("l'accueil mobile conserve les couleurs YEM et la navigation PWA par professeur",async()=>{
  apiMock();const user=userEvent.setup();vi.spyOn(window,"scrollTo").mockImplementation(()=>{});
  render(<TeacherMobileWorkspace schoolId="lycee" schoolName="Lycée A"
    user={{first_name:"Paul"}} workingYearId="2026" years={[{id:"2026",name:"2026-2027"}]}
    accountView={<span>Paramètres du mot de passe</span>}
    permissions={["school.curriculum.read","school.academic.read"]}/>);
  expect(await screen.findByRole("heading",{name:"Tableau de bord"})).toBeTruthy();
  expect(screen.getByRole("button",{name:"Ajouter YEM à mon téléphone"})).toBeTruthy();
  const nav=screen.getByRole("navigation",{name:"Navigation de l'espace professeur"});
  await user.click(within(nav).getByRole("button",{name:"Moyennes"}));
  expect(await screen.findByText("Moyennes par matière")).toBeTruthy();
  await user.click(within(nav).getByRole("button",{name:"Profil"}));
  expect(await screen.findByText("Ouvrir les paramètres de sécurité")).toBeTruthy();
  await user.click(screen.getByText("Ouvrir les paramètres de sécurité"));
  expect(screen.getByText("Paramètres du mot de passe")).toBeTruthy();
});
