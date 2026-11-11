// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StaffProfessionalDossier from "./StaffProfessionalDossier.jsx";

afterEach(()=>{
  cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();
});

const dossier = {
  staff:{id:"staff-test",staff_code:"ENS-109",first_name:"Sonia",last_name:"Obame",
    position:"Professeure",hired_on:"2025-09-01",active:true,has_account:true},
  professional:{revision:1,qualification:"Licence",specialty:"Mathématiques",
    employment_status:"Vacataire",workload:"14 h",professional_email:"",
    professional_phone:""},
  functions:[{id:"appointment",label:"Enseignant",cycle_label:"Collège",
    starts_on:null,ends_on:null,active:true,effective:true}],
  class_assignments:[{id:"assignment",year:"2026-2027",cycle:"Collège",
    classroom:"Sixième A",duty:"enseignant",active:true}],
  can_edit:true,is_own_dossier:false,
};

test("La direction consulte et corrige une fiche professionnelle avec contrôle de révision",async()=>{
  const fetch=vi.fn(async(url,config={})=>{
    if(url==="/api/v1/auth/csrf")return Response.json({ok:true});
    if(config.method==="PATCH")return Response.json({
      ...dossier,professional:{...dossier.professional,...JSON.parse(config.body),revision:2},
    });
    return Response.json(dossier);
  });
  vi.stubGlobal("fetch",fetch);
  const user=userEvent.setup();
  render(<StaffProfessionalDossier schoolId="college-1" staffId="staff-test"/>);
  expect(await screen.findByText("Mathématiques")).toBeTruthy();
  expect(screen.getByText("Sixième A")).toBeTruthy();
  expect(screen.getByText("Enseignant")).toBeTruthy();
  await user.click(screen.getByRole("button",{name:"Modifier les informations professionnelles"}));
  await user.clear(screen.getByLabelText("Spécialité ou discipline"));
  await user.type(screen.getByLabelText("Spécialité ou discipline"),"Physique");
  await user.click(screen.getByRole("button",{name:"Enregistrer la fiche"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,config])=>
    url.includes("/staff/staff-test/dossier") && config?.method==="PATCH" &&
    JSON.parse(config.body).revision===1 && JSON.parse(config.body).specialty==="Physique"
  )).toBe(true));
  expect(await screen.findByText("Fiche professionnelle actualisée.")).toBeTruthy();
});

test("Un enseignant ne modifie pas sa propre fiche et ne consulte aucun collègue",async()=>{
  const fetch=vi.fn(async()=>Response.json({...dossier,can_edit:false,is_own_dossier:true}));
  vi.stubGlobal("fetch",fetch);
  render(<StaffProfessionalDossier schoolId="college-1" own/>);
  expect(await screen.findByText("Mathématiques")).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Modifier les informations professionnelles"})).toBeNull();
  expect(fetch).toHaveBeenCalledWith("/api/v1/schools/college-1/staff/me/dossier",
    expect.objectContaining({credentials:"same-origin"}));
});
