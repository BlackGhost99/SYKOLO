// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SchoolExpenseRequestsPanel from "./SchoolExpenseRequestsPanel.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const root="/api/v1/schools/school-b3/operating/school-requests";
const id="00000000-0000-4000-8000-000000000088";
const draft={
  id,year:"year-b3",requester:"teacher-id",is_mine:false,
  requester_name:"Professeur B3",requester_function:"Enseignant",
  service:"Pédagogie",reason:"Manuels de mathématiques",
  description:"Manuels scolaires",category:"cat-b3",subcategory:null,
  category_label:"Matériel pédagogique",subcategory_label:"",
  cost_center:null,cost_center_label:"",supplier:null,
  beneficiary_name:"À identifier",quantity:"2.00",
  estimated_unit_price:"6000.00",estimated_amount:"12000.00",
  currency:"XAF",urgency:"high",desired_on:"2026-12-02",
  supporting_reference:"DEVIS-B3",status:"submitted",revision:2,
};
function fakeBackend(rows=[]){
  return vi.fn(async (url,options={})=>{
    if(url==="/api/v1/auth/csrf")return Response.json({ok:true});
    if(url===root+"/options")return Response.json({
      categories:[{id:"cat-b3",name:"Matériel pédagogique",code:"b07",parent:null}],
      centers:[],urgencies:[{code:"high",label:"Prioritaire"}],
    });
    if(url.startsWith(root+"?"))return Response.json({
      requests:rows,total:rows.length,offset:0,has_more:false,
      reviewer:rows.length>0,
    });
    if(url===root&&options.method==="POST")return Response.json({
      ...draft,id,revision:1,status:"draft",is_mine:true,
    },{status:201});
    if(url===root+"/"+id&&options.method==="GET")return Response.json({
      request:rows[0],history:[{
        action:"submitted",revision:2,actor:"teacher-id",
        reason:"",happened_at:"2026-11-21T10:00:00+00:00",
      }],
    });
    if(url===root+"/"+id+"/review"&&options.method==="POST")return Response.json({
      ...draft,status:"in_review",revision:3,
    });
    return Response.json({error:"Route inconnue"},{status:404});
  });
}

test("enseignant crée un brouillon sans accès aux finances scolaires",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  vi.stubGlobal("crypto",{randomUUID:()=>id});
  document.cookie="csrftoken=req-b3";
  const user=userEvent.setup();
  render(<SchoolExpenseRequestsPanel schoolId="school-b3"
    workingYearId="year-b3" canCreate/>);
  await screen.findByRole("heading",{name:"Nouvelle demande scolaire"});
  await user.type(screen.getByLabelText("Service demandeur"),"Pédagogie");
  await user.type(screen.getByLabelText("Objet de la demande"),"Manuels de sciences");
  await user.selectOptions(screen.getByLabelText("Catégorie"),"cat-b3");
  await user.type(screen.getByLabelText("Prix unitaire estimé (facultatif)"),"6000");
  await user.type(screen.getByLabelText("Fournisseur ou bénéficiaire pressenti"),"À identifier");
  await user.selectOptions(screen.getByLabelText("Urgence"),"high");
  await user.type(screen.getByLabelText("Date souhaitée"),"2026-12-02");
  await user.type(screen.getByLabelText("Motif détaillé"),"Équipement de laboratoire demandé");
  await user.click(screen.getByRole("button",{name:"Créer le brouillon"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,options])=>{
    if(url!==root||options?.method!=="POST")return false;
    const body=JSON.parse(options.body);
    return body.year==="year-b3"&&body.category==="cat-b3"&&
      body.urgency==="high"&&body.estimated_amount==="6000.00"&&
      body.quantity==="1.00"&&body.idempotency_key===id;
  })).toBe(true));
  expect(fetch.mock.calls.every(([url])=>
    !String(url).includes("/operating/budgets")&&
    !String(url).includes("/finance/")&&
    !String(url).includes("/operating/expenses")
  )).toBe(true);
});

test("lecteur sans pouvoir de modification ne voit pas le formulaire",async()=>{
  vi.stubGlobal("fetch",fakeBackend([]));
  render(<SchoolExpenseRequestsPanel schoolId="school-b3" workingYearId="year-b3"/>);
  expect(await screen.findByText(/0 demande/)).toBeTruthy();
  expect(screen.queryByText("Nouvelle demande scolaire")).toBeNull();
  expect(screen.queryByRole("button",{name:"Valider pour instruction budgétaire"})).toBeNull();
});

test("contrôleur examine une demande sans mouvement d'argent",async()=>{
  const fetch=fakeBackend([draft]);vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=req-b3";
  const user=userEvent.setup();
  render(<SchoolExpenseRequestsPanel schoolId="school-b3"
    workingYearId="year-b3" canReview/>);
  await screen.findByText("Manuels scolaires");
  await user.click(screen.getByRole("button",{name:"Détails"}));
  expect(await screen.findByRole("button",{name:"Mettre en examen"})).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Corriger le brouillon"})).toBeNull();
  await user.click(screen.getByRole("button",{name:"Mettre en examen"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,options])=>{
    if(url!==root+"/"+id+"/review"||options?.method!=="POST")return false;
    const payload=JSON.parse(options.body);
    return payload.decision==="in_review"&&payload.revision===2;
  })).toBe(true));
  expect(fetch.mock.calls.every(([url])=>!String(url).includes("/finance/payments"))).toBe(true);
});
