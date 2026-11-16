// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PrimaryCriteria from "./PrimaryCriteria.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

test("enregistre un critère et sa piste de remédiation pour le niveau choisi",async()=>{
  const requests=[];
  vi.stubGlobal("fetch",vi.fn(async(url,options={})=>{
    if(String(url).endsWith("/auth/csrf"))return Response.json({});
    if(options.method==="PATCH"){
      const body=JSON.parse(options.body);
      requests.push(body);
      return Response.json({criteria:body.criteria,revision:1,editable:true});
    }
    if(String(url).includes("level="))return Response.json({criteria:[],revision:0,editable:true});
    return Response.json({levels:[{id:"cp",name:"CP"},{id:"ce1",name:"CE1"}]});
  }));
  const user=userEvent.setup();
  render(<PrimaryCriteria schoolId="school" yearId="year"/>);
  await user.selectOptions(await screen.findByLabelText("Niveau primaire"),"cp");
  await user.click(await screen.findByRole("button",{name:"Ajouter un critère"}));
  await user.type(screen.getByLabelText("Critère de maîtrise"),"Lire une phrase");
  await user.type(screen.getByLabelText("Piste de remédiation"),"Relire à deux.");
  await user.click(screen.getByRole("button",{name:"Enregistrer le référentiel"}));
  await screen.findByText("Référentiel enregistré.");
  expect(requests[0]).toMatchObject({year:"year",level:"cp",revision:0,
    criteria:[{label:"Lire une phrase",remediation:"Relire à deux."}]});
});
