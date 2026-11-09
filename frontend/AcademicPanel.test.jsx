// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AcademicPanel from "./AcademicPanel.jsx";

vi.mock("./AnnualWorkspace.jsx", () => ({default: () => null}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

test("un établissement peut renommer son niveau primaire sans toucher aux codes ni au cycle", async()=>{
  const level = {id:"level-one",code:"1re-annee",name:"1re année",order:1,
    cycle:"primary-cycle",active:true,revision:4};
  const patchRequests=[];
  const fetchMock=vi.fn(async(url,opts={})=>{
    const path=String(url);
    if(path.endsWith("/auth/csrf"))return {ok:true,headers:{get:()=>"application/json"},json:async()=>({})};
    if(path.endsWith("/academic/levels/level-one") && opts.method==="PATCH"){
      const body=JSON.parse(opts.body);
      patchRequests.push(body);
      level.name=body.name;level.order=body.order;level.revision++;
      return {ok:true,headers:{get:()=>"application/json"},json:async()=>({...level})};
    }
    const resource=path.split("/").pop();
    const list=resource==="levels"?[level]:resource==="cycles"?
      [{id:"primary-cycle",code:"primaire",name:"Primaire",active:true}]:[];
    return {ok:true,headers:{get:()=>"application/json"},json:async()=>({[resource]:list})};
  });
  vi.stubGlobal("fetch",fetchMock);
  const user=userEvent.setup();
  render(<AcademicPanel schoolId="school-a" workingYearId="2026-2027"/>);
  await user.selectOptions(screen.getByLabelText("Élément à gérer"),"levels");
  const button=await screen.findByRole("button",{name:"Modifier ce niveau"});
  await user.click(button);
  expect(screen.getByLabelText("Code").disabled).toBe(true);
  expect(screen.getByLabelText("Cycle").disabled).toBe(true);
  await user.clear(screen.getByLabelText("Intitulé"));
  await user.type(screen.getByLabelText("Intitulé"),"Première année fondamentale");
  await user.click(screen.getByRole("button",{name:"Enregistrer le niveau"}));
  await waitFor(()=>expect(patchRequests).toHaveLength(1));
  expect(patchRequests[0]).toEqual({
    revision:4,name:"Première année fondamentale",order:1,
  });
  await screen.findByText("Première année fondamentale");
});

test("une école peut créer son niveau avec un code et un intitulé libres",async()=>{
  let submitted=null;
  const mock=vi.fn(async(url,opts={})=>{
    const path=String(url),resource=path.split("/").pop();
    if(resource==="csrf")return {ok:true,headers:{get:()=>"application/json"},json:async()=>({})};
    if(resource==="levels"&&opts.method==="POST"){
      submitted=JSON.parse(opts.body);
      return {ok:true,headers:{get:()=>"application/json"},json:async()=>({id:"new",...submitted})};
    }
    const list=resource==="cycles"?
      [{id:"primary-cycle",code:"primaire",name:"Primaire",active:true}]:[];
    return {ok:true,headers:{get:()=>"application/json"},json:async()=>({[resource]:list})};
  });
  vi.stubGlobal("fetch",mock);
  const user=userEvent.setup();
  render(<AcademicPanel schoolId="school-a"/>);
  await user.selectOptions(screen.getByLabelText("Élément à gérer"),"levels");
  await user.type(screen.getByLabelText("Code"),"3e-annee");
  await user.type(screen.getByLabelText("Intitulé"),"Troisième année");
  await user.selectOptions(screen.getByLabelText("Cycle"),"primary-cycle");
  await user.click(screen.getByRole("button",{name:"Ajouter : niveaux"}));
  await waitFor(()=>expect(submitted).toEqual({
    code:"3e-annee",name:"Troisième année",cycle:"primary-cycle",order:0,
  }));
});
