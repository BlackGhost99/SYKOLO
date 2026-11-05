// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {AdmissionPolicyEditor,AdmissionProofPanel} from "./AdmissionRoutesPanel.jsx";

afterEach(cleanup);
const YEAR="11111111-1111-1111-1111-111111111111";
const LEVEL="22222222-2222-2222-2222-222222222222";

test("l'établissement configure les voies par niveau sans autoriser une admission automatique",async()=>{
  const api=vi.fn(async(path,body)=>{
    if(body!==undefined)return {...body,scope_revision:1,scope:"level"};
    return {year:YEAR,level:LEVEL,scope:"default",scope_revision:0,
      enabled_routes:["direct","concours","orientation"],
      required_documents:{direct:[],concours:[],orientation:[]}};
  });
  render(<AdmissionPolicyEditor api={api} base="schools/test/admissions" year={YEAR} level={LEVEL} canDecide/>);
  const u=userEvent.setup();
  await screen.findAllByText("Concours ou test d'admission");
  expect(screen.getByText(/preuve d'un concours ou d'une affectation reste obligatoire/)).toBeTruthy();
  await u.click(screen.getAllByLabelText("Acte de naissance")[0]);
  await u.click(screen.getByRole("button",{name:"Enregistrer les règles d'admission"}));
  await waitFor(()=>expect(api).toHaveBeenCalledWith("schools/test/admissions/policy",
    expect.objectContaining({year:YEAR,level:LEVEL,revision:0})));
});

test("les preuves de concours affichent l'éligibilité et la vérification séparément",async()=>{
  const app={id:"33333333-3333-3333-3333-333333333333",status:"submitted",revision:1,
    route:"concours",external_result:"pending",route_reference:"",
    orientation_authority:"",required_documents:["concours_result"],origin_school:"Primaire A"};
  const api=vi.fn(async()=>({revision:1,documents:[],required_documents:app.required_documents}));
  render(<AdmissionProofPanel api={api} base="schools/test/admissions" application={app} canDecide onUpdated={async()=>{}}/>);
  await screen.findByText(/Justificatifs non vérifiés/);
  expect(screen.getByText(/Éligibilité déclarée/)).toBeTruthy();
  expect(screen.getByText(/Une déclaration d'éligibilité ne vaut pas admission/)).toBeTruthy();
  expect(screen.getByRole("button",{name:"Enregistrer l'éligibilité"}).disabled).toBe(true);
});

test("le secrétariat ne voit pas les boutons de validation des preuves",async()=>{
  const app={id:"33333333-3333-3333-3333-333333333333",status:"submitted",revision:2,
    route:"orientation",external_result:"eligible",route_reference:"AFF-1",
    orientation_authority:"Commission",required_documents:["orientation_decision"],origin_school:"Primaire A"};
  const api=vi.fn(async()=>({revision:2,required_documents:app.required_documents,
    documents:[{id:"44444444-4444-4444-4444-444444444444",code:"orientation_decision",
      reference:"ATTEST-1",status:"pending",created_at:"2026-11-01T12:00:00"}]}));
  render(<AdmissionProofPanel api={api} base="schools/test/admissions" application={app} canDecide={false} onUpdated={async()=>{}}/>);
  await screen.findByText(/Référence : ATTEST-1/);
  expect(screen.queryByRole("button",{name:"Vérifier"})).toBeNull();
  expect(screen.queryByRole("button",{name:"Non conforme"})).toBeNull();
});
