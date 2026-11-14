// @vitest-environment jsdom
import React from "react";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, test, vi} from "vitest";
import SchoolNotificationCenter from "./SchoolNotificationCenter.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

test("la cloche permet d'accepter un rattachement sans naviguer dans Paramètres", async()=>{
  const user=userEvent.setup();
  const prefix="/api/v1/schools/awassi";
  let accepted=false;
  const payloads=[];
  const request={id:"req-1",student_code:"AWA-26-0046",first_name:"Amadou",last_name:"NDONG",
    guardian_name:"Sylvie NDONG",account_name:"Sylvie NDONG",
    username:"Sylvie",contact_phone:"+241062308363",school_name:"Lycée AWASSI"};
  const fetch=vi.fn(async(url,options={})=>{
    if(url==="/api/v1/auth/csrf")return Response.json({});
    if(url===prefix+"/notification-inbox" && options.method==="GET")
      return Response.json({requests:accepted?[]:[request],messages:[],unread:accepted?0:1});
    if(url===prefix+"/notification-inbox/requests/req-1/candidates")
      return Response.json({candidates:[{student:"student-1",student_code:"AWA-26-0046",
        student_name:"Amadou NDONG",guardians:[{id:"guardian-1",name:"Sylvie NDONG",relationship:"Mère"}]}]});
    if(url===prefix+"/parent-links"&&options.method==="POST"){
      payloads.push(JSON.parse(options.body));accepted=true;
      return Response.json({id:"link-1",active:true},{status:201});
    }
    return Response.json({error:"Unexpected "+url},{status:404});
  });
  vi.stubGlobal("fetch",fetch);
  render(<SchoolNotificationCenter schoolId="awassi" onUnread={vi.fn()}/>);
  const examine=await screen.findByRole("button",{name:"Examiner et accepter"});
  expect(screen.getByText(/AWA-26-0046/)).toBeTruthy();
  await user.click(examine);
  await user.selectOptions(await screen.findByLabelText("Élève et responsable vérifié"),"guardian-1");
  const accept=screen.getByRole("button",{name:"Accepter et activer l’accès"});
  expect(accept.disabled).toBe(true);
  await user.click(screen.getByRole("checkbox",{name:/Je confirme avoir vérifié l'identité/}));
  await user.click(accept);
  expect(payloads).toEqual([{guardian:"guardian-1",username:"Sylvie",identity_verified:true,request_id:"req-1"}]);
  expect(await screen.findByText(/accès parent activé/)).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Examiner et accepter"})).toBeNull();
});

test("la direction peut répondre à un parent depuis la notification reçue",async()=>{
  const user=userEvent.setup();
  const prefix="/api/v1/schools/awassi";
  const sent=[];
  const fetch=vi.fn(async(url,options={})=>{
    if(url==="/api/v1/auth/csrf")return Response.json({});
    if(url===prefix+"/notification-inbox" && options.method==="GET")
      return Response.json({requests:[],messages:[{
        id:"msg-1",kind:"family_message",origin:"parent",destination:"school",
        parent_username:"Sylvie",request_id:"req-1",read:false,message:"Bonjour la direction",
        at:"2026-11-14T10:00:00Z",
      }],unread:1});
    if(url===prefix+"/notification-inbox" && options.method==="POST"){
      sent.push(JSON.parse(options.body));
      return Response.json({id:"msg-2"},{status:201});
    }
    return Response.json({});
  });
  vi.stubGlobal("fetch",fetch);
  render(<SchoolNotificationCenter schoolId="awassi"/>);
  await screen.findByText("Bonjour la direction", {exact:false});
  await user.click(screen.getByRole("button",{name:"Répondre"}));
  const form=screen.getByRole("button",{name:"Envoyer la notification"}).closest("form");
  expect(within(form).getByLabelText("Identifiant du compte parent").value).toBe("Sylvie");
  await user.type(within(form).getByLabelText("Message"),"Bonjour, nous vérifions votre dossier.");
  await user.click(within(form).getByRole("button",{name:"Envoyer la notification"}));
  expect(sent).toEqual([{username:"Sylvie",message:"Bonjour, nous vérifions votre dossier.",request_id:"req-1"}]);
});
