// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OperatingPanel from "./OperatingPanel.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const supplier={id:"sup-1",name:"Électricien TEST",contact:"Agence TEST",phone:"000",email:"",active:true,revision:1};
const budget={id:"bud-1",year:"year-1",category:"Énergie",currency:"XAF",ceiling:"100000.00",
  committed:"60000.00",available:"40000.00",paid:"20000.00",revision:2,approved:true};
const expense={id:"exp-1",year:"year-1",budget:"bud-1",category:"Énergie",currency:"XAF",
  supplier:"sup-1",supplier_name:"Électricien TEST",label:"Réparation tableau",amount:"60000.00",
  paid:"20000.00",balance:"40000.00",status:"partially_paid",invoice_reference:"FAC-TEST",
  expense_on:"2026-11-10",revision:2};
function fakeBackend(){
  return vi.fn(async (url,opts={})=>{
    if(url==="/api/v1/auth/csrf")return Response.json({ok:true});
    if(opts.method==="POST")return Response.json({...supplier,id:"sup-2"},{status:201});
    if(url.includes("/operating/suppliers"))return Response.json({suppliers:[supplier]});
    if(url.includes("/operating/budgets"))return Response.json({budgets:[budget]});
    if(url.includes("/operating/expenses/"))return Response.json({expense,payments:[]});
    if(url.includes("/operating/expenses"))return Response.json({expenses:[expense]});
    if(url.includes("/operating/summary"))return Response.json({
      year:"year-1",budgets:[budget],totals:{XAF:{
        ceiling:"100000.00",committed:"60000.00",paid:"20000.00",remaining:"40000.00",
      }},
    });
    return Response.json({error:"Route inattendue"},{status:404});
  });
}

test("lecteur dépenses : budgets et règlements visibles, boutons de mutation masqués",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1"/>);
  expect(await screen.findByText("Réparation tableau")).toBeTruthy();
  expect(screen.getAllByText("Électricien TEST").length).toBeGreaterThan(0);
  expect(screen.getAllByText(/40.000,00/).length).toBeGreaterThan(0);
  expect(screen.queryByRole("button",{name:"Ajouter un fournisseur"})).toBeNull();
  expect(screen.queryByRole("button",{name:"Enregistrer le règlement déclaré"})).toBeNull();
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/schools/school-1/operating/summary?year=year-1",
    expect.objectContaining({method:"GET",credentials:"same-origin"}),
  );
});

test("le comptable peut proposer un fournisseur, sans pouvoir approuver les budgets",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=operating-test";
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1" canManage/>);
  const user=userEvent.setup();
  await screen.findByText("Réparation tableau");
  await user.type(screen.getByLabelText("Nom fournisseur"),"Fournisseur TEST nouveau");
  await user.click(screen.getByRole("button",{name:"Ajouter un fournisseur"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>
    url.endsWith("/operating/suppliers")&&opts?.method==="POST"&&
    JSON.parse(opts.body).name==="Fournisseur TEST nouveau"
  )).toBe(true));
  expect(screen.queryByRole("button",{name:"Approuver"})).toBeNull();
});
