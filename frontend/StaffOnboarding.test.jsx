// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StaffOnboarding from "./StaffOnboarding.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals()});
function mockContext(positions,notice=""){
  vi.stubGlobal("fetch",vi.fn(async(url)=>Response.json(
    String(url).endsWith("/staff/onboard")?{
      school_name:"Lycée test",school_type:"lycee_general",education_cycles:["lycee_general"],
      can_appoint:true,can_create_account:false,can_manage_cycle_access:false,
      actor_access_cycle_ids:null,existing_accounts:[],roles:[],positions,
      position_setup_notice:notice,years:[],classes:[],academic_cycles:[],
    }:{}
  )));
}
async function goToFunctions(){
  const user=userEvent.setup();
  await user.type(await screen.findByLabelText("Prénom(s)"),"Alice");
  await user.type(screen.getByLabelText("Nom"),"NZÉ");
  await user.type(screen.getByLabelText("Poste / métier sur la fiche"),"Professeure");
  await user.click(screen.getByRole("button",{name:"Continuer"}));
  return user;
}
test("les fonctions du lycée sont visibles sans cliquer d'abord sur ajouter une ligne",async()=>{
  mockContext([{code:"proviseur",label:"Proviseur du lycée",family:"Direction",
    scope:"cycle",allowed_cycles:["lycee_general"]}]);
  render(<StaffOnboarding schoolId="school"/>);
  const user=await goToFunctions();
  await user.selectOptions(screen.getByLabelText("Choisir une fonction à ajouter"),"proviseur");
  expect(screen.getByRole("combobox",{name:"Fonction"}).value).toBe("proviseur");
  expect(screen.getByRole("combobox",{name:"Cycle concerné"}).value).toBe("lycee_general");
  expect(screen.getByText(/1 fonction\(s\) sélectionnée/)).toBeTruthy();
});
test("un établissement non classifié explique pourquoi les fonctions sont absentes",async()=>{
  mockContext([],"Le type d'établissement ou ses cycles enseignés ne sont pas configurés.");
  render(<StaffOnboarding schoolId="school"/>);
  await goToFunctions();
  expect(screen.getByRole("alert").textContent).toMatch(/ne sont pas configurés/);
});
