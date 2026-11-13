// @vitest-environment jsdom
import React from "react";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,expect,test,vi} from "vitest";
import TeacherProfile from "./TeacherProfile.jsx";
import TeacherHome from "./TeacherHome.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
test("l'écran professeur emploie le thème YEM et donne accès à la PWA, aux notes et à l'appel",()=>{
  render(<TeacherHome schoolName="Lycée A" onNavigate={()=>{}} canNotes canAttendance canClasses/>);
  expect(screen.getByRole("heading",{name:"Tableau de bord"})).toBeTruthy();
  expect(screen.getByRole("button",{name:"Installer YEM sur mon téléphone"})).toBeTruthy();
  expect(screen.getByRole("button",{name:"Saisir les notes et consulter les moyennes"})).toBeTruthy();
  expect(screen.getByRole("button",{name:"Faire l'appel"})).toBeTruthy();
});
test("le professeur ne modifie que sa présentation et sa photo, jamais le matricule ou la fonction",async()=>{
  const prefix="/api/v1/schools/school/staff/me/profile";
  const profile={staff_id:"employee",first_name:"Alice",last_name:"Nze",staff_code:"PROF-1",
    position:"Enseignante",presentation:"",revision:1,photo_url:null};
  const fetchMock=vi.fn(async (url, options={})=>{
    if(url==="/api/v1/auth/csrf")return Response.json({});
    if(url===prefix&&options.method==="PATCH"){
      const payload=JSON.parse(options.body);
      return Response.json({...profile,presentation:payload.presentation,revision:2});
    }
    return Response.json(profile);
  });
  vi.stubGlobal("fetch",fetchMock);
  const user=userEvent.setup();
  render(<TeacherProfile schoolId="school"/>);
  expect(await screen.findByText("PROF-1",{exact:false})).toBeTruthy();
  expect(screen.getByText("Enseignante")).toBeTruthy();
  expect(screen.queryByLabelText("Matricule")).toBeNull();
  await user.type(screen.getByRole("textbox",{name:/Présentation professionnelle/}),"Professeure de sciences");
  await user.click(screen.getByRole("button",{name:"Enregistrer mon profil"}));
  await waitFor(()=>expect(fetchMock.mock.calls.some(([url,o])=>url===prefix&&o?.method==="PATCH")).toBe(true));
  const payload=JSON.parse(fetchMock.mock.calls.find(([url,o])=>url===prefix&&o?.method==="PATCH")[1].body);
  expect(Object.keys(payload).sort()).toEqual(["presentation","revision"]);
});
