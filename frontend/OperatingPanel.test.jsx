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
const catalog=[
  {id:"cat-1",code:"materiel",name:"Matériel",parent:null,suggested_pole:"school",active:true,revision:1},
  {id:"sub-1",code:"laboratoire",name:"Laboratoire",parent:"cat-1",suggested_pole:"",active:true,revision:1},
];
const expense={id:"exp-1",year:"year-1",budget:"bud-1",category:"Énergie",currency:"XAF",
  category_ref:"cat-1",subcategory_ref:"sub-1",expense_category:"Matériel",expense_subcategory:"Laboratoire",
  supplier:"sup-1",supplier_name:"Électricien TEST",label:"Réparation tableau",amount:"60000.00",
  paid:"20000.00",balance:"40000.00",status:"partially_paid",invoice_reference:"FAC-TEST",
  expense_on:"2026-11-10",revision:2};
function fakeBackend(item=expense, listInfo={}){
  return vi.fn(async (url,opts={})=>{
    if(url==="/api/v1/auth/csrf")return Response.json({ok:true});
    if(url.endsWith("/operating/catalog-defaults")&&opts.method==="POST")return Response.json({created_families:20,created_subcategories:211,idempotent:false});
    if(opts.method==="POST")return Response.json({...supplier,id:"sup-2"},{status:201});
    if(opts.method==="PATCH")return Response.json({...catalog[0],revision:2});
    if(url.endsWith("/operating/classification"))return Response.json({
      poles:[
        {code:"school",label:"Scolarité",revision:0,active:true},
        {code:"extraschool",label:"Extrascolarité",revision:0,active:true},
        {code:"common",label:"Administration et charges communes",revision:0,active:true},
        {code:"investment",label:"Investissements",revision:0,active:true},
        {code:"cash_other",label:"Autres sorties de trésorerie",revision:0,active:true},
      ],
      centers:[{id:"center-1",kind:"cost_center",code:"pedagogie",name:"Pédagogie",
        activity_pole:"school",active:true,revision:1}],
      natures:[{id:"nature-1",kind:"accounting_nature",code:"charge",name:"Charge pédagogique",
        activity_pole:"",active:true,revision:1}],
    });
    if(url.includes("/operating/categories"))return Response.json({categories:catalog});
    if(url.includes("/operating/suppliers"))return Response.json({suppliers:[supplier]});
    if(url.includes("/operating/budgets"))return Response.json({budgets:[budget]});
    if(url.includes("/operating/expenses/"))return Response.json({expense:item,payments:[],decisions:[]});
    if(url.includes("/operating/expenses"))return Response.json({expenses:[item], ...listInfo});
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

test("la ventilation et le filtre des sorties restent propres au module dépenses",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  const user=userEvent.setup();
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1"/>);
  expect(await screen.findByText("Ventilation des sorties par activité")).toBeTruthy();
  await user.selectOptions(screen.getByLabelText("Filtrer les dépenses par activité"),"extraschool");
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>
    url.includes("/operating/expenses?year=year-1&activity_pole=extraschool")&&opts?.method==="GET"
  )).toBe(true));
  expect(screen.queryByRole("button",{name:"Enregistrer la classification"})).toBeNull();
});

test("le catalogue des dépenses est consultable sans droits de modification",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1"/>);
  await userEvent.setup().click(screen.getByRole("button",{name:"Configurer les catégories de dépenses"}));
  expect((await screen.findAllByText("Matériel")).length).toBeGreaterThan(0);
  expect(screen.getByText("↳ Laboratoire")).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Ajouter cette catégorie"})).toBeNull();
  expect(screen.queryByRole("button",{name:"Archiver"})).toBeNull();
});

test("le comptable peut ajouter une catégorie sans modifier les entrées",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=operating-test";
  const user=userEvent.setup();
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1" canManage/>);
  await user.click(screen.getByRole("button",{name:"Configurer les catégories de dépenses"}));
  await screen.findAllByText("Matériel");
  await user.type(screen.getByLabelText("Code catégorie / sous-catégorie"),"cantine");
  await user.type(screen.getByLabelText("Nom catégorie / sous-catégorie"),"Cantine");
  await user.selectOptions(screen.getByLabelText("Pôle suggéré"),"extraschool");
  await user.click(screen.getByRole("button",{name:"Ajouter cette catégorie"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>
    url.endsWith("/operating/categories")&&opts?.method==="POST"&&
    JSON.parse(opts.body).code==="cantine"&&JSON.parse(opts.body).suggested_pole==="extraschool"
  )).toBe(true));
  expect(fetch.mock.calls.every(([url])=>!String(url).includes("/finance/charges"))).toBe(true);
});

test("nouvelle dépense vers une administration sans fournisseur fictif",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=operating-test";
  const user=userEvent.setup();
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1" canManage/>);
  await screen.findByText("Réparation tableau");
  await user.selectOptions(screen.getByLabelText("Enveloppe approuvée"),"bud-1");
  await user.selectOptions(screen.getByLabelText("Catégorie de la dépense"),"cat-1");
  await user.selectOptions(screen.getByLabelText("Pôle financier"),"common");
  await user.selectOptions(screen.getByLabelText("Type de bénéficiaire"),"government");
  expect(screen.queryByLabelText("Fournisseur",{exact:true})).toBeNull();
  await user.type(screen.getByLabelText("Nom du bénéficiaire"),"Administration publique TEST");
  await user.type(screen.getByLabelText("Référence interne du bénéficiaire"),"DOSSIER-TEST");
  await user.type(screen.getByLabelText("Objet de l'achat"),"Frais administratifs TEST");
  await user.type(screen.getByLabelText(/Montant demandé/),"15000");
  await user.type(screen.getByLabelText("Référence facture/devis"),"FAC-B3-TEST");
  await user.click(screen.getByRole("button",{name:"Préparer la demande"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,options])=>{
    if(!url.endsWith("/operating/expenses")||options?.method!=="POST")return false;
    const data=JSON.parse(options.body);
    return data.beneficiary_type==="government"&&
      data.beneficiary_name==="Administration publique TEST"&&
      data.supplier===null&&data.category_ref==="cat-1";
  })).toBe(true));
});

test("préparateur : soumission de demande et absence d'autorisation directe",async()=>{
  const item={...expense,status:"draft",workflow_state:"draft",paid:"0.00",balance:"60000.00"};
  const fetch=fakeBackend(item);vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=operating-test";
  const user=userEvent.setup();
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1" canManage/>);
  await user.click(await screen.findByRole("button",{name:"Détail"}));
  await screen.findByText("Dépense — Réparation tableau");
  expect(screen.getByRole("button",{name:"Soumettre pour autorisation"})).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Autoriser la dépense"})).toBeNull();
  await user.click(screen.getByRole("button",{name:"Soumettre pour autorisation"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>
    url.endsWith("/operating/expenses/exp-1/submit")&&opts?.method==="POST"&&
    JSON.parse(opts.body).revision===2
  )).toBe(true));
});

test("contrôleur : refus motivé sans toucher aux encaissements",async()=>{
  const item={...expense,status:"submitted",workflow_state:"submitted",paid:"0.00",balance:"60000.00"};
  const fetch=fakeBackend(item);vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=operating-test";
  const user=userEvent.setup();
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1" canApprove/>);
  await user.click(await screen.findByRole("button",{name:"Détail"}));
  await screen.findByText("Dépense — Réparation tableau");
  expect(screen.getByRole("button",{name:"Autoriser la dépense"})).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Soumettre pour autorisation"})).toBeNull();
  await user.type(screen.getByLabelText(/Motif du refus/),"Facture incomplète à rectifier");
  await user.click(screen.getByRole("button",{name:"Refuser la demande"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>
    url.endsWith("/operating/expenses/exp-1/reject")&&opts?.method==="POST"&&
    JSON.parse(opts.body).reason==="Facture incomplète à rectifier"
  )).toBe(true));
  expect(fetch.mock.calls.every(([url])=>!String(url).includes("/finance/payments"))).toBe(true);
});

test("file des demandes : compteurs par état et pagination sans toucher aux entrées",async()=>{
  const fetch=fakeBackend(expense,{
    total:60,offset:0,has_more:true,
    workflow_counts:{draft:20,submitted:15,rejected:5,approved:20},
  });
  vi.stubGlobal("fetch",fetch);
  const user=userEvent.setup();
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1"/>);
  await screen.findByText("Réparation tableau");
  expect(screen.getByRole("button",{name:"Toutes (60)"})).toBeTruthy();
  await user.click(screen.getByRole("button",{name:"En attente de validation (15)"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>
    url.includes("/operating/expenses?")&&url.includes("workflow_state=submitted")&&
    url.includes("limit=30")&&opts?.method==="GET"
  )).toBe(true));
  await user.click(screen.getByRole("button",{name:"Page suivante"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>
    url.includes("/operating/expenses?")&&url.includes("workflow_state=submitted")&&
    url.includes("offset=30")&&opts?.method==="GET"
  )).toBe(true));
  expect(fetch.mock.calls.every(([url])=>!String(url).includes("/finance/charges"))).toBe(true);
});

test("le comptable peut proposer un fournisseur, sans pouvoir approuver les budgets",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=operating-test";
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1" canManage/>);
  const user=userEvent.setup();
  await screen.findByText("Réparation tableau");
  expect(screen.getByLabelText("Pôle financier")).toBeTruthy();
  await user.selectOptions(screen.getByLabelText("Pôle financier"),"school");
  await user.type(screen.getByLabelText("Nom fournisseur"),"Fournisseur TEST nouveau");
  await user.click(screen.getByRole("button",{name:"Ajouter un fournisseur"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>
    url.endsWith("/operating/suppliers")&&opts?.method==="POST"&&
    JSON.parse(opts.body).name==="Fournisseur TEST nouveau"
  )).toBe(true));
  expect(screen.queryByRole("button",{name:"Approuver"})).toBeNull();
});

test("import explicite du catalogue B01-B20 sans toucher aux recettes",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=operating-test";
  const user=userEvent.setup();
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1" canManage/>);
  await user.click(screen.getByRole("button",{name:"Configurer les catégories de dépenses"}));
  expect(screen.getByRole("button",{name:"Installer les familles B01 à B20"})).toBeTruthy();
  await user.click(screen.getByRole("button",{name:"Installer les familles B01 à B20"}));
  expect(fetch.mock.calls.some(([url,options])=>
    url.endsWith("/operating/catalog-defaults")&&options?.method==="POST"
  )).toBe(false);
  await user.click(screen.getByRole("button",{name:"Confirmer l'installation"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,options])=>{
    if(!url.endsWith("/operating/catalog-defaults")||options?.method!=="POST")return false;
    const data=JSON.parse(options.body);
    return data.include_subcategories===true&&data.families.length===20&&
      data.families.includes("b01")&&data.families.includes("b20");
  })).toBe(true));
  expect(fetch.mock.calls.every(([url])=>!String(url).includes("/finance/charges"))).toBe(true);
});

test("B2 : centres et natures liés au pôle sans modifier les recettes",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=operating-test";
  const user=userEvent.setup();
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1" canManage/>);
  await screen.findByText("Réparation tableau");
  await user.selectOptions(screen.getByLabelText("Enveloppe approuvée"),"bud-1");
  await user.selectOptions(screen.getByLabelText("Catégorie de la dépense"),"cat-1");
  await user.selectOptions(screen.getByLabelText("Pôle financier"),"school");
  await user.selectOptions(screen.getByLabelText("Centre de coûts"),"center-1");
  await user.selectOptions(screen.getByLabelText("Nature comptable"),"nature-1");
  await user.selectOptions(screen.getByLabelText("Fournisseur",{exact:true}),"sup-1");
  await user.type(screen.getByLabelText("Objet de l'achat"),"Achat de livres test");
  await user.type(screen.getByLabelText(/Montant demandé/),"5000");
  await user.type(screen.getByLabelText("Référence facture/devis"),"DEVIS-B2");
  await user.click(screen.getByRole("button",{name:"Préparer la demande"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>{
    if(!url.endsWith("/operating/expenses")||opts?.method!=="POST")return false;
    const p=JSON.parse(opts.body);
    return p.cost_center_ref==="center-1"&&p.accounting_nature_ref==="nature-1"&&p.activity_pole==="school";
  })).toBe(true));
  expect(fetch.mock.calls.every(([url])=>!String(url).includes("/finance/charges"))).toBe(true);
});

test("B2 : configuration des centres visible uniquement au gestionnaire",async()=>{
  const fetch=fakeBackend();vi.stubGlobal("fetch",fetch);
  document.cookie="csrftoken=operating-test";
  const user=userEvent.setup();
  render(<OperatingPanel schoolId="school-1" workingYearId="year-1" canManage/>);
  await user.click(screen.getByRole("button",{name:"Configurer les catégories de dépenses"}));
  expect(screen.getByText("S1 · school")).toBeTruthy();
  await user.type(screen.getByLabelText("Code du centre de coûts"),"bibliotheque");
  await user.type(screen.getByLabelText("Nom du centre de coûts"),"Bibliothèque");
  await user.selectOptions(screen.getByLabelText("Pôle de rattachement"),"school");
  await user.click(screen.getByRole("button",{name:"Ajouter un centre de coûts"}));
  await waitFor(()=>expect(fetch.mock.calls.some(([url,opts])=>{
    if(!url.endsWith("/operating/classification")||opts?.method!=="POST")return false;
    const p=JSON.parse(opts.body);
    return p.kind==="cost_center"&&p.code==="bibliotheque"&&p.activity_pole==="school";
  })).toBe(true));
});
