// @vitest-environment jsdom
import React from "react";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,expect,test,vi} from "vitest";
import PlatformSubscriptions from "./PlatformSubscriptions.jsx";
import OwnerSubscription from "./OwnerSubscription.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
test("monthly commercial quote is selected and issued with exact total",async()=>{
  const api=vi.fn(async(path,body)=>{
    if(!body)return {years:[{id:"y",name:"2026–2027"}],suggested_year:"y"};
    if(body.action==="quote")return {counts:{primaire:100},rates:{primaire:1500},labels:{primaire:"Primaire"},policy_revision:1,terms:{gross_xaf:150000,minimum_xaf:75000,student_count:100},first_due:"2026-11-17",setup_suggested_xaf:50000,can_issue:true};
    return {subscription:{lines:[],total_xaf:150000,paid_xaf:0,balance_xaf:150000,payments:[],terms:{period:"mensuel",annual_xaf:150000,minimum_xaf:75000,discount_xaf:0,setup_xaf:0},schedule:[]}};
  });
  const user=userEvent.setup();
  render(<PlatformSubscriptions schoolId="school-a" api={api}/>);
  await user.selectOptions(await screen.findByLabelText("Modalité de règlement"),"mensuel");
  await user.type(screen.getByLabelText(/Motif \/ référence du contrat/),"Contrat mensuel");
  await user.click(screen.getByRole("button",{name:"Enregistrer l’abonnement annuel"}));
  await waitFor(()=>expect(api).toHaveBeenCalledWith("platform/schools/school-a/subscriptions",expect.objectContaining({action:"issue",period:"mensuel",expected_total_xaf:150000,expected_counts:{primaire:100}})));
  expect(await screen.findByText("Contrat annuel enregistré")).toBeTruthy();
});
test("management reads refreshed balances from the school endpoint",async()=>{
  const contract={id:1,year:"2026–2027",year_id:"y",lines:[],total_xaf:150000,paid_xaf:0,balance_xaf:150000,terms:{period:"mensuel",minimum_xaf:75000,discount_xaf:0,setup_xaf:0},schedule:[]};
  const fetcher=vi.fn().mockResolvedValueOnce(Response.json({subscriptions:[contract]})).mockResolvedValue(Response.json({subscriptions:[{...contract,paid_xaf:12500,balance_xaf:137500}]}));
  vi.stubGlobal("fetch",fetcher);
  const hidden=vi.spyOn(document,"hidden","get").mockReturnValue(false);
  render(<OwnerSubscription schoolId="school-a" yearId="y"/>);
  await screen.findByText(/Total contractuel/);
  window.dispatchEvent(new Event("focus"));
  await waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(2));
  expect(await screen.findByText(/137[\s\u202f]500 FCFA/)).toBeTruthy();
  expect(fetcher).toHaveBeenLastCalledWith("/api/v1/schools/school-a/owner/subscriptions",{credentials:"same-origin",cache:"no-store"});
  hidden.mockRestore();
});
