// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {StudentFile} from "./EnrollmentScreens.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function setup({sensitiveVisible=false,financeVisible=false}={}) {
  let current = "class-a";
  let revision = 1;
  const base = "/api/v1/schools/school-1/";
  const fetchMock = vi.fn(async (url, options={}) => {
    if (url === "/api/v1/auth/csrf") return Response.json({});
    if (url === base + "students/student-1/dossier") return Response.json({
      student: {id:"student-1", first_name:"Ada", last_name:"Fictive",
        student_code:"ECOLE-001", matricule_yem:"YEM-0123456789ABCDEF0123456789ABCDEF"},
      enrollments: [{id:"enrollment-1", student:"student-1", year:"year-1",
        year_name:"2026–2027", classroom:current,
        classroom_name:current==="class-a"?"6e A":current==="class-b"?"6e B":"6e C",
        enrolled_on:"2026-10-01", active:true, status:"inscrit", revision,
        ...(financeVisible ? {finance:{billed:"150000",paid:"100000",balance:"50000",currency:"XAF",status:"partiel",charges:[],payments:[]}} : {})}],
      sensitive_visible:sensitiveVisible, finance_visible:financeVisible,
      form:{custom_fields:[],documents:[]}, missing_documents:[],
      guardians:sensitiveVisible
        ? [{id:"guardian-1",full_name:"Claudine Fictive",relationship:"Mère",active:true,is_primary:true},
          {id:"guardian-2",full_name:"Paul Fictive",relationship:"Père",active:true,is_primary:false}]
        : [],
    });
    if (url === base + "overview/classes?year=year-1") return Response.json({
      year:{id:"year-1", name:"2026–2027", active:true}, years:[],
      classes:[{id:"class-a", name:"6e A"}, {id:"class-b", name:"6e B"}, {id:"class-c", name:"6e C"}],
    });
    if (url === base + "enrollments/enrollment-1/assignment" && options.method==="POST") {
      const data = JSON.parse(options.body);
      expect(data.revision).toBe(revision);
      current = data.mode==="automatic"?"class-c":data.classroom;
      revision++;
      return Response.json({enrollment:{revision},assignment:{
        from_class:"class-a",to_class:current,
        class_name:current==="class-b"?"6e B":"6e C",mode:data.mode,reason:data.reason,
      }});
    }
    if (url === base + "enrollments/enrollment-1/assignment") return Response.json({
      enrollment:"enrollment-1",revision,year:"year-1",
      current_classroom:current,read_only:false,
      divisions:[{id:"class-b",name:"6e B",capacity:30,occupied:0,remaining:30},
        {id:"class-c",name:"6e C",capacity:30,occupied:0,remaining:30}]
        .filter(x=>x.id!==current),
    });
    if (url === base + "enrollments/enrollment-1/history") return Response.json({history:[]});
    throw new Error("Unexpected API request: "+url);
  });
  vi.stubGlobal("fetch",fetchMock);
  render(<StudentFile schoolId="school-1" params={{student:"student-1"}}
    canManage={true} canEditAdministration={false} canIssueTransfer={false}
    canReceive={false} onNavigate={()=>{}} workingYearId="year-1"/>);
  return fetchMock;
}

test("M2.7 : changement manuel sécurisé avec un motif obligatoire", async () => {
  const fetchMock = setup();
  const user = userEvent.setup();
  expect(screen.queryByLabelText("Nouvelle division")).toBeNull();
  await user.click(await screen.findByRole("button",{name:"Changer de classe"}));
  const select = await screen.findByLabelText("Nouvelle division");
  await screen.findByRole("option", {name: /6e B/});
  await user.selectOptions(select, "class-b");
  const submit = screen.getByRole("button", {name:"Confirmer l'affectation"});
  expect(submit.disabled).toBe(true);
  await user.type(screen.getByLabelText("Motif du changement de classe"), "Répartition pédagogique");
  await waitFor(()=>expect(submit.disabled).toBe(false));
  await user.click(submit);
  await waitFor(()=>expect(fetchMock.mock.calls.some(([url, opts])=>(
    url.endsWith("/enrollment-1/assignment") && opts?.method==="POST" &&
    JSON.parse(opts.body).mode==="manual" &&
    JSON.parse(opts.body).classroom==="class-b" &&
    JSON.parse(opts.body).reason==="Répartition pédagogique"
  ))).toBe(true));
});

test("M2.7 : répartition automatique sans choix manuel de division", async () => {
  const fetchMock = setup();
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button",{name:"Changer de classe"}));
  await user.selectOptions(await screen.findByLabelText("Mode d'affectation"),"automatic");
  expect(screen.queryByLabelText("Nouvelle division")).toBeNull();
  await user.type(screen.getByLabelText("Motif du changement de classe"), "Équilibrer les effectifs");
  const submit=screen.getByRole("button",{name:"Confirmer l'affectation"});
  await waitFor(()=>expect(submit.disabled).toBe(false));
  await user.click(submit);
  await waitFor(()=>expect(fetchMock.mock.calls.some(([url,opts])=>(
    url.endsWith("/enrollment-1/assignment") && opts?.method==="POST" &&
    JSON.parse(opts.body).mode==="automatic" &&
    !("classroom" in JSON.parse(opts.body))
  ))).toBe(true));
});

test("Fiche élève : la synthèse présente les parents et les sommes dues sans ouvrir le formulaire d'affectation", async () => {
  setup({sensitiveVisible:true,financeVisible:true});
  await screen.findByText("Fiche technique de l’élève");
  expect(screen.getByText("Parents / responsables légaux")).toBeTruthy();
  expect(screen.getByText("Claudine Fictive")).toBeTruthy();
  expect(screen.getByText("Paul Fictive")).toBeTruthy();
  expect(screen.getByText("Situation financière")).toBeTruthy();
  expect(screen.getAllByText("50 000 FCFA").length).toBeGreaterThan(0);
  expect(screen.queryByLabelText("Mode d'affectation")).toBeNull();
});

test("Fiche élève : les informations sensibles restent masquées sans droits", async () => {
  setup();
  await screen.findByText("Fiche technique de l’élève");
  expect(screen.queryByText("Parents / responsables légaux")).toBeNull();
  expect(screen.queryByText("Situation financière")).toBeNull();
  expect(screen.getByRole("button",{name:"Changer de classe"})).toBeTruthy();
});
