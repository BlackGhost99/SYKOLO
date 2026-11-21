// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ExtrasQuotePreview from "./ExtrasQuotePreview.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const items=[
  {id:"11",active:true,code:"REPAS",label:"Repas du midi",unit_price:"2500.00",
   currency:"XAF",unit:"repas",academic_year:"y1"},
  {id:"22",active:true,code:"BUS",label:"Navette",unit_price:"7000.00",
   currency:"XAF",unit:"mois",academic_year:null},
  {id:"33",active:false,code:"ARCHIVE",label:"Uniforme ancien",unit_price:"4000.00",
   currency:"XAF",unit:"unité",academic_year:null},
  {id:"44",active:true,code:"AUTRE",label:"Session passée",unit_price:"100.00",
   currency:"XAF",unit:"unité",academic_year:"y2"},
];

test("devis sécurisé avec montants serveur et sans paiement",async()=>{
  const request=vi.fn(async(url,options={})=>{
    if(String(url).endsWith("/auth/csrf"))return Response.json({});
    const payload=JSON.parse(options.body);
    expect(payload.academic_year).toBe("y1");
    expect(payload.items).toEqual([{id:"11",quantity:2}]);
    return Response.json({
      lines:[{catalog_item_id:"11",label:"Repas du midi",quantity:2,unit_price:"2500.00",
              line_total:"5000.00",currency:"XAF"}],
      total:"5000.00",currency:"XAF",state:"estimation_non_enregistree",
      recorded_sale:false,recorded_payment:false,payable:false,
      notice:"Devis indicatif, non enregistré : aucun encaissement."
    });
  });
  vi.stubGlobal("fetch",request);
  const user=userEvent.setup();
  render(<ExtrasQuotePreview schoolId="school-a" yearId="y1" catalogRevision={3} items={items}/>);
  await user.click(screen.getByText(/Préparer un panier extrascolaire/));
  expect(screen.queryByLabelText("Quantité de Uniforme ancien")).toBeNull();
  expect(screen.queryByLabelText("Quantité de Session passée")).toBeNull();
  await user.type(screen.getByLabelText("Quantité de Repas du midi"),"2");
  await user.click(screen.getByRole("button",{name:"Calculer le devis (1 article(s))"}));
  const status=await screen.findByRole("status");
  expect(status.textContent).toContain("5000.00 XAF");
  expect(status.textContent).toContain("aucun encaissement");
  expect(screen.queryByRole("button",{name:/Payer|Encaisser/})).toBeNull();
  expect(request.mock.calls.some(([url])=>String(url).includes("/finance/payments"))).toBe(false);
});

test("prix année ancienne exclus et erreur affichée sans comptabiliser",async()=>{
  vi.stubGlobal("fetch",vi.fn(async(url,opts={})=>{
    if(String(url).endsWith("/auth/csrf"))return Response.json({});
    return Response.json({error:"Devis multidevise refusé"},{status:422});
  }));
  const user=userEvent.setup();
  render(<ExtrasQuotePreview schoolId="school-a" yearId="y1" catalogRevision={3} items={items}/>);
  await user.click(screen.getByText(/Préparer un panier extrascolaire/));
  await user.type(screen.getByLabelText("Quantité de Navette"),"1");
  await user.click(screen.getByRole("button",{name:/Calculer le devis/}));
  expect((await screen.findByRole("alert")).textContent).toContain("Devis multidevise refusé");
  expect(screen.queryByRole("status")).toBeNull();
});

test("nouvelle révision efface devis et quantités précédents",async()=>{
  vi.stubGlobal("fetch",vi.fn(async(url)=>{
    if(String(url).endsWith("/auth/csrf"))return Response.json({});
    return Response.json({lines:[],total:"0",currency:"XAF",notice:"Non enregistré"});
  }));
  const user=userEvent.setup();
  const view=render(<ExtrasQuotePreview schoolId="a" yearId="y1" catalogRevision={1} items={items}/>);
  await user.click(screen.getByText(/Préparer un panier extrascolaire/));
  await user.type(screen.getByLabelText("Quantité de Navette"),"3");
  await user.click(screen.getByRole("button",{name:/Calculer le devis/}));
  expect(await screen.findByRole("status")).toBeTruthy();
  view.rerender(<ExtrasQuotePreview schoolId="a" yearId="y1" catalogRevision={2} items={items}/>);
  expect(screen.getByLabelText("Quantité de Navette").value).toBe("");
  expect(screen.queryByRole("status")).toBeNull();
});
