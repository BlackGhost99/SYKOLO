// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor,fireEvent} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PayrollPanel,{StaffPayrollHistory} from "./PayrollPanel.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});

const salary={
  id:"payrun-1",staff:"staff-1",staff_name:"Mathilde FICTIVE",staff_code:"P-001",
  year:"year-1",period:"2026-11-01",basis:"monthly",
  gross_amount:"120000.00",deductions:"20000.00",net_amount:"100000.00",
  currency:"XAF",note:"",status:"approved",paid:"40000.00",
  balance:"60000.00",revision:2,
};
function fakeGet(){
  return vi.fn(async (url,opts={})=>{
    if(url==="/api/v1/auth/csrf")return Response.json({ok:true});
    if(url.includes("/payroll/staff"))return Response.json({staff:[
      {id:"staff-1",name:"Mathilde FICTIVE",position:"Professeure",active:true}
    ]});
    if(url.includes("/payroll/runs/payrun-1"))return Response.json({run:salary,payments:[]});
    if(url.includes("/payroll/runs"))return Response.json({runs:[salary]});
    return Response.json({error:"API inattendue"},{status:404});
  });
}

test("un lecteur RH voit les rémunérations sans droits de saisie",async()=>{
  const fetch=fakeGet();vi.stubGlobal("fetch",fetch);
  render(<PayrollPanel schoolId="school-1" workingYearId="year-1"/>);
  expect(await screen.findByText("Mathilde FICTIVE")).toBeTruthy();
  expect(screen.getAllByText(/100.000,00/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/60.000,00/).length).toBeGreaterThan(0);
  expect(screen.queryByText("Préparer la rémunération")).toBeNull();
  expect(screen.queryByText("Enregistrer le versement déclaré")).toBeNull();
  expect(fetch).toHaveBeenCalledWith(
    "/api/v1/schools/school-1/payroll/runs?year=year-1",
    expect.objectContaining({method:"GET",credentials:"same-origin"}),
  );
});

test("la comptabilité prépare une paie mais ne la valide pas elle-même",async()=>{
  const fetch=vi.fn(async (url,opts={})=>{
    if(url.endsWith("auth/csrf"))return Response.json({ok:true});
    if(url.includes("/payroll/staff"))return Response.json({staff:[
      {id:"staff-1",name:"Mathilde FICTIVE",position:"Professeure",active:true}
    ]});
    if(opts.method==="POST")return Response.json({...salary,status:"draft",paid:"0.00"}, {status:201});
    return Response.json({runs:[]});
  });
  vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=payroll-test";
  const user=userEvent.setup();
  render(<PayrollPanel schoolId="school-1" workingYearId="year-1" canManage/>);
  await screen.findByText("Préparer la rémunération");
  await user.selectOptions(screen.getByLabelText("Collaborateur"),"staff-1");
  fireEvent.change(screen.getByLabelText("Mois de paie"),{target:{value:"2026-11"}});
  await user.type(screen.getByLabelText("Montant brut"),"120000.00");
  await user.click(screen.getByRole("button",{name:/Préparer la paie de/}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>
    url.endsWith("/payroll/runs")&&opts?.method==="POST"&&
    JSON.parse(opts.body).period==="2026-11-01"&&
    JSON.parse(opts.body).gross_amount==="120000.00"
  )).toBe(true));
  expect(screen.queryByRole("button",{name:"Valider cette paie"})).toBeNull();
});

test("le résumé des salaires dans une fiche exige une requête RH privée",async()=>{
  const fetch=fakeGet();vi.stubGlobal("fetch",fetch);
  render(<StaffPayrollHistory schoolId="school-1" staffId="staff-1" workingYearId="year-1"/>);
  expect(await screen.findByText("Mathilde FICTIVE").catch(()=>null)).toBeNull();
  expect(await screen.findByText(/60.000,00/)).toBeTruthy();
  expect(fetch.mock.calls.some(([url])=>url.includes("staff=staff-1")&&url.includes("year=year-1"))).toBe(true);
});
