// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import IncomeFeeCategoryPanel from "./IncomeFeeCategoryPanel.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const fee={id:"schedule-a",year:"year",code:"option-perso",label:"Atelier",currency:"XAF"};
test("un classement est historisé sans mutation des paiements",async()=>{
  const fetcher=vi.fn(async (url,options={})=>{
    const key=String(url);
    if(key.endsWith("/auth/csrf"))return Response.json({});
    if(options.method==="PATCH"){
      const posted=JSON.parse(options.body);
      expect(posted).toMatchObject({schedule:"schedule-a",category:"extrascolaire",revision:0,
        acknowledge_history:true});
      expect(posted.reason.length).toBeGreaterThanOrEqual(10);
      return Response.json({category:"extrascolaire",revision:1,unchanged:false});
    }
    return Response.json({revision:fetcher.mock.calls.some(([,opts])=>opts?.method==="PATCH")?1:0,
      assignments:fetcher.mock.calls.some(([,opts])=>opts?.method==="PATCH")?{"schedule-a":"extrascolaire"}:{},
      categories:[{code:"scolarite",label:"Scolarité"},{code:"extrascolaire",label:"Extrascolaire"}]});
  });
  vi.stubGlobal("fetch",fetcher);
  const user=userEvent.setup();
  render(<IncomeFeeCategoryPanel schoolId="school" schedules={[fee]} yearId="year"/>);
  await screen.findByRole("option",{name:"option-perso — Atelier (XAF)"});
  await user.selectOptions(screen.getByLabelText("Tarif à classer"),"schedule-a");
  await user.selectOptions(screen.getByLabelText("Catégorie"),"extrascolaire");
  await user.type(screen.getByLabelText("Justification de la classification"),
    "Atelier optionnel déclaré.");
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button",{name:"Enregistrer et historiser"}));
  await screen.findByText(/Classement enregistré et journalisé/);
  expect(fetcher.mock.calls.filter(([,opts])=>opts?.method==="PATCH")).toHaveLength(1);
  await user.click(screen.getByText(/Consulter les classements/));
  await waitFor(()=>expect(screen.getByRole("cell",{name:"Extrascolaire"})).toBeTruthy());
});

test("un membre ne peut pas masquer les catégories sans année et un échec reste visible",async()=>{
  const fetcher=vi.fn(async (url,options={})=>{
    if(options.method==="PATCH")return Response.json({error:"Classement verrouillé"}, {status:409});
    if(String(url).endsWith("/auth/csrf"))return Response.json({});
    return Response.json({revision:1,assignments:{},
      categories:[{code:"scolarite",label:"Scolarité"}]});
  });
  vi.stubGlobal("fetch",fetcher);
  const user=userEvent.setup();
  render(<IncomeFeeCategoryPanel schoolId="school" schedules={[fee]} yearId="year"/>);
  await screen.findByRole("option",{name:"option-perso — Atelier (XAF)"});
  await user.selectOptions(screen.getByLabelText("Tarif à classer"),"schedule-a");
  await user.type(screen.getByLabelText("Justification de la classification"),"Écriture historique justifiée");
  await user.click(screen.getByRole("button",{name:"Enregistrer et historiser"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("Classement verrouillé");
});
