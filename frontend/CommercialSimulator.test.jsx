// @vitest-environment jsdom
import React from "react";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,expect,test,vi} from "vitest";
import CommercialSimulator from "./CommercialSimulator.jsx";
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const fixture=(students=2,contracted=false)=>({school:{name:"Complexe A",type_label:"Complexe scolaire"},years:[{id:"y",name:"2026–2027"}],year_id:"y",contracted,billing_activated_on:contracted?"2026-11-17":null,first_contract_due:contracted?"2026-11-17":null,simulation:{policy_revision:1,lines:[{cycle:"primaire",label:"Primaire",students,rate_xaf:1500,amount_xaf:students*1500}],options:Object.fromEntries([["annuel",1],["semestriel",2],["trimestriel",4],["mensuel",12]].map(([p,n])=>[p,{student_count:students,gross_xaf:students*1500,minimum_xaf:75000,minimum_adjustment_xaf:Math.max(0,75000-students*1500),annual_xaf:Math.max(75000,students*1500),schedule:Array.from({length:n},(_,i)=>({number:i+1,amount_xaf:Math.max(75000,students*1500)/n}))}]))}});
test("live estimate is read-only and shows no payment dates before activation",async()=>{
  vi.spyOn(document,"hidden","get").mockReturnValue(false);
  const fetcher=vi.fn(async()=>Response.json(fixture()));vi.stubGlobal("fetch",fetcher);
  render(<CommercialSimulator schoolId="a" yearId="y"/>);
  await screen.findByText("Service gratuit · facturation inactive");
  expect(screen.queryByRole("spinbutton")).toBeNull();
  expect(screen.getByText(/Aucune échéance avant/)).toBeTruthy();
  await userEvent.selectOptions(screen.getByLabelText("Modalité indicative"),"trimestriel");
  expect(screen.getByText(/4 versement/)).toBeTruthy();
  expect(fetcher.mock.calls.every(([url,options])=>url.includes("/schools/a/owner/subscription-simulation?year_id=y")&&!options.method)).toBe(true);
});
test("platform uses the real-count endpoint and displays access errors",async()=>{
  const api=vi.fn(async()=>{throw Error("Accès refusé");});
  render(<CommercialSimulator schoolId="a" platform api={api}/>);
  expect(await screen.findByRole("alert")).toHaveProperty("textContent","Accès refusé");
  await waitFor(()=>expect(api).toHaveBeenCalledWith("platform/schools/a/subscription-simulation"));
});
test("counts and activation status refresh from server without entering any number",async()=>{
  vi.spyOn(document,"hidden","get").mockReturnValue(false);
  let next=false;
  const fetcher=vi.fn(async()=>Response.json(fixture(next?80:2,next)));vi.stubGlobal("fetch",fetcher);
  render(<CommercialSimulator schoolId="a" yearId="y"/>);
  await screen.findByText(/2 élève/);
  next=true;
  window.dispatchEvent(new Event("focus"));
  await screen.findByText(/80 élève/);
  expect(screen.getByText("Service payant activé")).toBeTruthy();
  expect(screen.getByText(/Activation : 17\/11\/2026/)).toBeTruthy();
  expect(fetcher.mock.calls.every(([url])=>!url.includes("effectif_"))).toBe(true);
});
