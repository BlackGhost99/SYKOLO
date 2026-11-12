// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {AdmissionPolicyEditor,AdmissionProofPanel,AdmissionDecisionReadiness} from "./AdmissionRoutesPanel.jsx";

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

test("le concours en attente explique la preuve manquante avant la décision",()=>{
  render(<AdmissionDecisionReadiness application={{
    id:"dossier-1",status:"review",route:"concours",
    acceptance_blocker:"Pièces justificatives à vérifier : concours_result",
  }}/>);
  expect(screen.getByRole("status").textContent).toContain("Justificatif du résultat au concours");
  expect(screen.getByRole("status").textContent).toContain("Admission non prête");
});

test("une admission directe prête ne signifie pas inscription ni paiement",()=>{
  const {rerender}=render(<AdmissionDecisionReadiness application={{
    status:"submitted",route:"direct",acceptance_blocker:null,
  }}/>);
  expect(screen.getByRole("status").textContent).toContain("les frais ou la bourse restent distincts");
  rerender(<AdmissionDecisionReadiness application={{
    status:"accepted",route:"direct",acceptance_blocker:null,
  }}/>);
  expect(screen.queryByRole("status")).toBeNull();
});


test("le secrétariat peut ajouter un justificatif mais pas le certifier",async()=>{
  const app={id:"33333333-3333-3333-3333-333333333333",status:"review",revision:2,
    route:"concours",external_result:"pending",route_reference:"",
    orientation_authority:"",required_documents:["concours_result"],origin_school:""};
  const api=vi.fn(async()=>({revision:2,required_documents:app.required_documents,
    documents:[{id:"44444444-4444-4444-4444-444444444444",code:"concours_result",
      reference:"PV-2026",status:"pending",created_at:"2026-11-12T12:00:00Z"}]}));
  render(<AdmissionProofPanel api={api} base="schools/test/admissions"
    application={app} canDecide={false} canPrepare onUpdated={async()=>{}}/>);
  await screen.findByText(/Référence : PV-2026/);
  expect(screen.getByRole("button",{name:"Enregistrer l'éligibilité"})).toBeTruthy();
  await userEvent.setup().click(screen.getByText(/Options avancées — ajouter une pièce complémentaire/));
  expect(screen.getByRole("button",{name:"Ajouter cette référence"})).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Vérifier"})).toBeNull();
  expect(screen.queryByRole("button",{name:"Non conforme"})).toBeNull();
});

test("le lecteur sans habilitation administrative ne peut pas saisir ni valider les pièces",async()=>{
  const app={id:"33333333-3333-3333-3333-333333333333",status:"review",revision:2,
    route:"concours",external_result:"pending",route_reference:"",
    orientation_authority:"",required_documents:["concours_result"],origin_school:""};
  const api=vi.fn(async()=>({revision:2,required_documents:app.required_documents,documents:[]}));
  render(<AdmissionProofPanel api={api} base="schools/test/admissions"
    application={app} canDecide={false} canPrepare={false} onUpdated={async()=>{}}/>);
  await screen.findByText(/Justificatifs non vérifiés/);
  expect(screen.getByLabelText("Éligibilité déclarée").disabled).toBe(true);
  expect(screen.queryByRole("button",{name:"Enregistrer l'éligibilité"})).toBeNull();
  expect(screen.queryByRole("button",{name:"Ajouter cette référence"})).toBeNull();
});

test("la pièce obligatoire est proposée d'abord, sans rendre obligatoires les autres documents",async()=>{
  const app={id:"33333333-3333-3333-3333-333333333333",status:"submitted",revision:1,
    route:"direct",external_result:"pending",required_documents:["birth_certificate"],origin_school:""};
  const api=vi.fn(async(path,body)=>body?{revision:2,documents:[]}:{revision:1,documents:[]});
  render(<AdmissionProofPanel api={api} base="schools/test/admissions" application={app}
    canPrepare onUpdated={async()=>{}}/>);
  await screen.findByText(/Justificatifs non vérifiés/);
  expect(screen.getAllByRole("combobox",{name:"Type de justificatif"})[0].value).toBe("birth_certificate");
  const user=userEvent.setup();
  await user.type(screen.getAllByLabelText("Référence du justificatif")[0],"Acte 2026 / 123");
  await user.click(screen.getAllByRole("button",{name:"Ajouter cette référence"})[0]);
  await waitFor(()=>expect(api).toHaveBeenCalledWith(
    "schools/test/admissions/"+app.id+"/documents",
    expect.objectContaining({code:"birth_certificate",reference:"Acte 2026 / 123"})
  ));
  expect(screen.getByText(/Options avancées — ajouter une pièce complémentaire/)).toBeTruthy();
});

test("le motif et la référence activent clairement l'enregistrement d'un résultat de concours",async()=>{
  const app={id:"33333333-3333-3333-3333-333333333333",status:"submitted",revision:1,
    route:"concours",external_result:"pending",required_documents:["concours_result"],origin_school:""};
  const api=vi.fn(async(path,body)=>body?{revision:2}:{revision:1,documents:[]});
  render(<AdmissionProofPanel api={api} base="schools/test/admissions" application={app}
    canDecide onUpdated={async()=>{}}/>);
  await screen.findByText(/Justificatifs non vérifiés/);
  const user=userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Éligibilité déclarée"),"eligible");
  await user.type(screen.getByLabelText(/Motif de validation du résultat/),"Procès-verbal du concours contrôlé");
  expect(screen.getByRole("button",{name:"Enregistrer l'éligibilité"}).disabled).toBe(true);
  await user.type(screen.getByLabelText(/Référence du concours/),"PV-C-2026-01");
  expect(screen.getByRole("button",{name:"Enregistrer l'éligibilité"}).disabled).toBe(false);
  await user.click(screen.getByRole("button",{name:"Enregistrer l'éligibilité"}));
  await waitFor(()=>expect(api).toHaveBeenCalledWith(
    "schools/test/admissions/"+app.id+"/eligibility",
    expect.objectContaining({result:"eligible",route_reference:"PV-C-2026-01",reason:"Procès-verbal du concours contrôlé"})
  ));
});

test("les pièces usuelles sont un préréglage modifiable et non une obligation globale",async()=>{
  const api=vi.fn(async(path,body)=>body?{...body,scope_revision:1,scope:"year"}:
    {year:YEAR,level:null,scope:"default",scope_revision:0,
      enabled_routes:["direct","concours","orientation"],
      required_documents:{direct:[],concours:[],orientation:[]}});
  render(<AdmissionPolicyEditor api={api} base="schools/test/admissions" year={YEAR} level={null}
    canDecide/>);
  const user=userEvent.setup();
  await screen.findByText(/Pièces obligatoires selon la voie/);
  await user.click(screen.getByRole("button",{name:/Préremplir les pièces habituelles/}));
  await user.click(screen.getByRole("button",{name:"Enregistrer les règles d'admission"}));
  await waitFor(()=>expect(api).toHaveBeenCalledWith("schools/test/admissions/policy",
    expect.objectContaining({required_documents:expect.objectContaining({
      direct:["birth_certificate"],
      concours:["birth_certificate","previous_reports"],
      orientation:["birth_certificate","previous_reports"]
    })})));
});
