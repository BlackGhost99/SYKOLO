// @vitest-environment jsdom
import React from "react";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,expect,test,vi} from "vitest";
import CommercialSimulator from "./CommercialSimulator.jsx";
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const fixture=()=>({school:{name:"Complexe A",type_label:"Complexe scolaire"},years:[{id:"y",name:"2026–2027"}],year_id:"y",contracted:true,simulation:{policy_revision:1,setup_suggested_xaf:50000,lines:[{cycle:"primaire",label:"Primaire",students:2,rate_xaf:1500,amount_xaf:3000}],options:Object.fromEntries([["annuel",1],["semestriel",2],["trimestriel",4],["mensuel",12]].map(([p,n])=>[p,{student_count:2,gross_xaf:3000,minimum_xaf:75000,minimum_adjustment_xaf:72000,annual_xaf:75000,schedule:Array.from({length:n},(_,i)=>({number:i+1,due_date:"2026-11-17",amount_xaf:75000/n}))}]))}});
test("school sees real estimate before issuing anything and can compare periods",async()=>{
  vi.spyOn(document,"hidden","get").mockReturnValue(false);
  const fetcher=vi.fn(async()=>Response.json(fixture()));vi.stubGlobal("fetch",fetcher);
  render(<CommercialSimulator schoolId="a" yearId="y"/>);
  await screen.findByText(/Abonnement annuel estimé/);
  await userEvent.click(screen.getByText("Voir les 12 échéances"));
  expect(screen.getAllByRole("listitem")).toHaveLength(12);
  await userEvent.selectOptions(screen.getByLabelText("Fractionnement de l’estimation"),"trimestriel");
  expect(screen.getAllByRole("listitem")).toHaveLength(4);
  expect(screen.getByText(/Un contrat existe/)).toBeTruthy();
  await userEvent.click(screen.getByLabelText(/Inclure la mise en service/));
  expect(screen.getByText(/Total estimé avec les options choisies/).textContent).toMatch(/125\s*000/);
  expect(fetcher.mock.calls.every(([url,options])=>url.includes("/schools/a/owner/subscription-simulation?year_id=y")&&!options.method)).toBe(true);
});
test("platform uses the same read-only simulation and handles access refusal",async()=>{
  vi.spyOn(document,"hidden","get").mockReturnValue(false);
  const api=vi.fn(async()=>{throw Error("Accès refusé");});
  render(<CommercialSimulator schoolId="a" platform api={api}/>);
  expect(await screen.findByRole("alert")).toHaveProperty("textContent","Accès refusé");
  await waitFor(()=>expect(api).toHaveBeenCalledWith("platform/schools/a/subscription-simulation"));
});
test("direction can project a cycle and return to registered counts",async()=>{
  vi.spyOn(document,"hidden","get").mockReturnValue(false);
  const fetcher=vi.fn(async url=>{
    const data=fixture();
    data.actual_counts={primaire:2};
    if(url.includes("effectif_primaire=80"))data.simulation.lines[0].students=80;
    return Response.json(data);
  });
  vi.stubGlobal("fetch",fetcher);
  render(<CommercialSimulator schoolId="a" yearId="y"/>);
  const input=await screen.findByRole("spinbutton");
  await userEvent.clear(input);
  await userEvent.type(input,"80");
  await userEvent.click(screen.getByText("Calculer la projection"));
  await screen.findByText("Projection sur effectifs simulés");
  expect(screen.getByRole("spinbutton").value).toBe("80");
  await userEvent.click(screen.getByText("Revenir aux effectifs réels"));
  await screen.findByText("Estimation sur effectifs réels");
  expect(screen.getByRole("spinbutton").value).toBe("2");
});
