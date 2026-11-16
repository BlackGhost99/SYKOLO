// @vitest-environment jsdom
import React from "react";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,expect,test,vi} from "vitest";
import PreschoolFollowup from "./PreschoolFollowup.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

test("enregistre une observation dans le groupe et la journée sélectionnés",async()=>{
  const fetchMock=vi.fn(async(url,options={})=>{
    if(String(url).endsWith("/auth/csrf"))return Response.json({});
    if(options.method==="POST")return Response.json({observation:"Lecture",revision:1});
    if(String(url).includes("year="))return Response.json({classrooms:[{id:"a",name:"Crèche A"}]});
    return Response.json({editable:true,students:[
      {enrollment:"1",name:"Ava",revision:0,observation:"",current:true},
      {enrollment:"2",name:"Noé",revision:1,observation:"Activité en groupe",current:false},
    ]});
  });
  vi.stubGlobal("fetch",fetchMock);
  const user=userEvent.setup();
  render(<PreschoolFollowup schoolId="school" yearId="year"/>);
  await user.selectOptions(await screen.findByLabelText("Groupe"),"a");
  fireEvent.change(screen.getByLabelText("Date du suivi"),{target:{value:"2026-10-01"}});
  await user.type(await screen.findByLabelText("Observation de Ava"),"Lecture");
  expect(screen.getByLabelText("Observation de Noé").readOnly).toBe(true);
  await user.click(screen.getByRole("button",{name:"Enregistrer"}));
  await screen.findByText("Observation enregistrée.");
  const [,request]=fetchMock.mock.calls.find(([,options])=>options?.method==="POST");
  expect(JSON.parse(request.body)).toEqual({
    classroom:"a",day:"2026-10-01",action:"observation",enrollment:"1",revision:0,observation:"Lecture",
  });
});
