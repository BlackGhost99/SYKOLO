// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PrimaryMastery from "./PrimaryMastery.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

test("enregistre la maîtrise et la remédiation de l’élève pour le palier choisi",async()=>{
  const fetchMock=vi.fn(async(url,options={})=>{
    if(String(url).endsWith("/auth/csrf"))return Response.json({});
    if(options.method==="PATCH")return Response.json({criterion:"c",revision:1,
      snapshot:{id:"c",label:"Lire une phrase"},stage:"developing",remediation_status:"ongoing",
      follow_up:"Lecture guidée."});
    if(String(url).includes("classroom="))return Response.json({
      editable:true,criteria:[{id:"c",label:"Lire une phrase",remediation:"Lire à deux."}],
      stages:{developing:"En cours"},remediation_statuses:{ongoing:"En cours"},
      students:[{enrollment:"pupil",name:"Élève A",current:true,marks:[]}],
    });
    return Response.json({classrooms:[{id:"room",name:"CP A"}],milestones:[{id:"p1",name:"Premier palier"}]});
  });
  vi.stubGlobal("fetch",fetchMock);
  const user=userEvent.setup();
  render(<PrimaryMastery schoolId="school" yearId="year"/>);
  await user.selectOptions(await screen.findByLabelText("Classe primaire"),"room");
  await user.selectOptions(screen.getByLabelText("Palier du suivi"),"p1");
  await user.selectOptions(await screen.findByLabelText("Élève"),"pupil");
  await user.selectOptions(screen.getByLabelText("Maîtrise"),"developing");
  await user.selectOptions(screen.getByLabelText("Remédiation"),"ongoing");
  await user.type(screen.getByLabelText("Suivi individuel"),"Lecture guidée.");
  await user.click(screen.getByRole("button",{name:"Enregistrer le suivi"}));
  await screen.findByText("Suivi enregistré.");
  const [,request]=fetchMock.mock.calls.find(([,option])=>option?.method==="PATCH");
  expect(JSON.parse(request.body)).toEqual({year:"year",classroom:"room",milestone:"p1",
    enrollment:"pupil",criterion:"c",revision:0,stage:"developing",remediation_status:"ongoing",
    follow_up:"Lecture guidée."});
});
