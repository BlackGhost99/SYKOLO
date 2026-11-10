// @vitest-environment jsdom
import React from "react";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, test, vi} from "vitest";
import {FinancePolicyEditor, GovernmentScholarshipPanel} from "./AdmissionFinance.jsx";

afterEach(()=>{
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test.each([390, 1366])("écran %ipx : la direction règle le paiement obligatoire par niveau",async width=>{
  Object.defineProperty(window,"innerWidth",{configurable:true,value:width});
  const school="yem-test";
  const year="2026-27", level="seconde";
  const api="/api/v1/schools/"+school+"/admissions/finance-policy";
  const getUrl=api+"?year="+year+"&level="+level;
  let posted=null;
  const fetchMock=vi.fn(async (url,init)=>{
    if(url==="/api/v1/auth/csrf")return Response.json({});
    if(url===getUrl)return Response.json({
      revision:0,override:null,
      effective:{require_payment:true,allow_government_scholarship:true,configured:false},
    });
    if(url===api&&init?.method==="POST"){
      posted=JSON.parse(init.body);
      return Response.json({revision:1,effective:{
        require_payment:posted.require_payment,
        allow_government_scholarship:posted.allow_government_scholarship,
        configured:true,
      }});
    }
    return Response.json({error:"Route inattendue"}, {status:404});
  });
  vi.stubGlobal("fetch",fetchMock);
  const user=userEvent.setup();
  render(<FinancePolicyEditor schoolId={school} year={year} level={level} canManage={true}/>);
  const required=await screen.findByLabelText(/Bloquer l'inscription officielle/);
  expect(required.checked).toBe(true);
  const scholarship=screen.getByLabelText(/Autoriser les bourses gouvernementales/);
  expect(scholarship.checked).toBe(true);
  await user.click(scholarship);
  await user.click(screen.getByRole("button",{name:"Enregistrer ces règles"}));
  await waitFor(()=>expect(posted).not.toBeNull());
  expect(posted.require_payment).toBe(true);
  expect(posted.allow_government_scholarship).toBe(false);
  expect(await screen.findByText("Règle de paiement et d'exonération enregistrée.")).toBeTruthy();
});

test.each([390,1366])("écran %ipx : seule la direction approuve la bourse",async width=>{
  Object.defineProperty(window,"innerWidth",{configurable:true,value:width});
  const app={
    id:"application-test",status:"accepted",
    finance:{require_payment:true,blocker:"Paiement attendu",scholarship:null},
  };
  const fetchMock=vi.fn(async(url,init)=>{
    if(url==="/api/v1/auth/csrf")return Response.json({});
    return Response.json({ready_for_enrollment:true,
      scholarship:{coverage:"all",official_reference:"ÉTAT-GABON-2026",revision:1}});
  });
  vi.stubGlobal("fetch",fetchMock);
  const user=userEvent.setup();
  const changed=vi.fn(async()=>{});
  const {rerender}=render(<GovernmentScholarshipPanel
    schoolId="lycee2" application={app} canApprove={false} onUpdated={changed}/>);
  expect(screen.queryByRole("button",{name:"Valider la bourse d'État"})).toBeNull();
  rerender(<GovernmentScholarshipPanel schoolId="lycee2"
    application={app} canApprove={true} onUpdated={changed}/>);
  const ref=screen.getByLabelText(/Référence de la décision officielle/);
  await user.type(ref,"ÉTAT-GABON-2026");
  await user.click(screen.getByRole("button",{name:"Valider la bourse d'État"}));
  await waitFor(()=>expect(changed).toHaveBeenCalledTimes(1));
  const approvals=fetchMock.mock.calls.filter(([url,options])=>
    url.endsWith("/scholarship")&&options?.method==="POST");
  expect(approvals).toHaveLength(1);
  expect(JSON.parse(approvals[0][1].body)).toEqual({
    action:"approve",coverage:"all",reference:"ÉTAT-GABON-2026",revision:0,
  });
});
