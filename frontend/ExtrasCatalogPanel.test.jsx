// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ExtrasCatalogPanel from "./ExtrasCatalogPanel.jsx";

afterEach(() => {cleanup(); vi.unstubAllGlobals();});

test("le catalogue est paramétrable et aucun encaissement n'est généré", async () => {
  let revision = 0;
  let items = [];
  const posted = [];
  vi.stubGlobal("fetch", vi.fn(async (url, options = {}) => {
    if (String(url).endsWith("/auth/csrf")) return Response.json({});
    if (options.method === "POST") {
      const data = JSON.parse(options.body);
      posted.push(data);
      expect(data.action).toBe("upsert");
      expect(data.revision).toBe(revision);
      const item = {...data.item, id: "e3b5f2c0-7767-4a0a-916a-555a2d75a160",
        unit_price: "2500.00", active: true};
      items = [item]; revision++;
      return Response.json({revision,item,unchanged:false},{status:201});
    }
    return Response.json({revision,items,source:"extras_catalog_config",
      sales_recorded:false,groups:[
        {code:"B03",label:"Cantine et restauration"},
        {code:"B04",label:"Transport scolaire"},
      ]});
  }));
  const user = userEvent.setup();
  render(<ExtrasCatalogPanel schoolId="school-a" yearId="year-a"/>);
  await screen.findByText(/aucune vente, créance, facture/);
  await user.type(screen.getByLabelText("Code article"),"CANTINE-REPAS");
  await user.type(screen.getByLabelText("Désignation"),"Repas du midi");
  await user.type(screen.getByLabelText("Prix unitaire"),"2500.00");
  await user.type(screen.getByLabelText("Justification de la modification"),"Tarif validé en conseil scolaire");
  await user.click(screen.getByRole("button",{name:"Créer l'article"}));
  await screen.findByRole("status");
  expect(posted).toHaveLength(1);
  expect(posted[0].item).toMatchObject({
    code:"CANTINE-REPAS",group:"B03",kind:"produit",
    unit_price:"2500.00",academic_year:"year-a"
  });
  expect(screen.getByText("Repas du midi")).toBeTruthy();
  expect(screen.getByText(/Catalogue mis à jour/)).toBeTruthy();
  expect(vi.mocked(fetch).mock.calls.some(([url])=>String(url).includes("/finance/payments"))).toBe(false);
});

test("les catalogues ne sont pas affichés si la permission de lecture est refusée",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>Response.json({error:"Accès financier refusé"},{status:403})));
  render(<ExtrasCatalogPanel schoolId="school-b"/>);
  expect((await screen.findByRole("alert")).textContent).toContain("Accès financier refusé");
  expect(screen.queryByRole("button",{name:"Créer l'article"})).toBeNull();
});

test("une révision concurrente refuse une modification sans effacer les données",async()=>{
  let sendCount=0;
  vi.stubGlobal("fetch",vi.fn(async (url,options={})=>{
    if(String(url).endsWith("/auth/csrf"))return Response.json({});
    if(options.method==="POST"){
      sendCount++;
      return Response.json({error:"Le catalogue a été modifié ailleurs.",revision:2},{status:409});
    }
    return Response.json({revision:1,items:[],groups:[{code:"B03",label:"Cantine"}]});
  }));
  const user=userEvent.setup();
  render(<ExtrasCatalogPanel schoolId="school-a"/>);
  await screen.findByRole("button",{name:"Créer l'article"});
  await user.type(screen.getByLabelText("Code article"),"CANTINE-REPAS");
  await user.type(screen.getByLabelText("Désignation"),"Repas du midi");
  await user.type(screen.getByLabelText("Prix unitaire"),"2000");
  await user.type(screen.getByLabelText("Justification de la modification"),"Justification du prix");
  await user.click(screen.getByRole("button",{name:"Créer l'article"}));
  expect((await screen.findByRole("alert")).textContent).toContain("Le catalogue a été modifié ailleurs.");
  expect(sendCount).toBe(1);
  expect(screen.getByLabelText("Désignation").value).toBe("Repas du midi");
});
