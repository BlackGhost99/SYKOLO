// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {StaffDirectory} from "./SchoolDirectories.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const staff=[
  {id:"a",first_name:"Alice",last_name:"Test",position:"Professeure de mathématiques",active:true,staff_code:"A",category:""},
  {id:"b",first_name:"Bruno",last_name:"Test",position:"Économe",active:true,staff_code:"B",category:""},
  {id:"c",first_name:"Claire",last_name:"Test",position:"Gardienne",active:true,staff_code:"C",category:""},
  {id:"d",first_name:"David",last_name:"Test",position:"Agent",active:true,staff_code:"D",category:"Intervenants spécialisés"},
];
function setup(){
  vi.stubGlobal("fetch",vi.fn(async url=>{
    if(url.endsWith("/staff/a/dossier"))return Response.json({
      staff:staff[0],professional:{revision:1,category:"Enseignants"},functions:[],class_assignments:[],can_edit:false,
    });
    if(url.includes("/payroll/staff"))return Response.json({staff:[{id:"a",name:"Alice Test",active:true}]});
    if(url.includes("/payroll/runs"))return Response.json({runs:[]});
    return Response.json({staff});
  }));
}
test("catégories, filtre et ouverture directe du dossier individuel avec retour",async()=>{
  setup();
  const user=userEvent.setup();
  render(<StaffDirectory schoolId="school" canReadDossiers canReadPayroll workingYearId="year"/>);
  await screen.findByRole("button",{name:"Alice Test"});
  await user.selectOptions(screen.getByLabelText("Catégorie du personnel"),"Enseignants");
  expect(screen.queryByRole("button",{name:"Bruno Test"})).toBeNull();
  expect(screen.queryByRole("button",{name:"Claire Test"})).toBeNull();
  await user.click(screen.getByRole("button",{name:"Alice Test"}));
  await screen.findByText("Matricule du personnel");
  expect(screen.queryByRole("button",{name:"Consulter la fiche"})).toBeNull();
  await user.click(screen.getByRole("button",{name:"Rémunérations et versements"}));
  await screen.findByText("Rémunérations du personnel — accès confidentiel");
  expect(screen.getByLabelText("Collaborateur").disabled).toBe(true);
  expect(fetch.mock.calls.some(([url])=>url.includes("/payroll/runs?")&&url.includes("staff=a"))).toBe(true);
  await user.click(screen.getByRole("button",{name:"Retour au personnel"}));
  expect(screen.getByRole("button",{name:"Alice Test"})).toBeTruthy();
});
test("un lecteur d'annuaire sans permission dossier ne peut ouvrir les données RH",async()=>{
  setup();render(<StaffDirectory schoolId="school"/>);
  await screen.findByText("Alice Test");
  expect(screen.queryByRole("button",{name:"Alice Test"})).toBeNull();
  expect(screen.queryByRole("button",{name:"Consulter la fiche"})).toBeNull();
  expect(screen.queryByRole("button",{name:"Rémunérations et versements"})).toBeNull();
});
