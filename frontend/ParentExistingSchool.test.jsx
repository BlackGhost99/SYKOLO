// @vitest-environment jsdom
import React from "react";
import {cleanup, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, test, vi} from "vitest";
import ParentDiscovery from "./ParentDiscovery.jsx";
import {SchoolParentAccess} from "./ParentPortal.jsx";

afterEach(()=>{
  cleanup();
  vi.unstubAllGlobals();
});

test("parent sans enfant rattaché retrouve une école non publiée et dépose une demande sans admission",async()=>{
  const user=userEvent.setup();
  const calls=[];
  let requests=[];
  const fetch=vi.fn(async (url,options={})=>{
    calls.push([url,options]);
    if(url==="/api/v1/auth/csrf")return Response.json({});
    if(url==="/api/v1/parents/existing-schools"||url==="/api/v1/parents/existing-schools?q=")
      return Response.json({schools:[{id:"awassi",name:"Lycée AWASSI"}]});
    if(url==="/api/v1/parents/existing-requests"&&options.method==="POST"){
      const body=JSON.parse(options.body);
      requests=[{id:"request-1",school:body.school,school_name:"Lycée AWASSI",
        ...body,status:"pending",created_at:"2026-11-14T10:00:00Z"}];
      return Response.json(requests[0],{status:201});
    }
    if(url==="/api/v1/parents/existing-requests")return Response.json({requests});
    if(url==="/api/v1/parents/catalog")return Response.json({schools:[]});
    if(url==="/api/v1/parents/family-children")return Response.json({children:[]});
    if(url==="/api/v1/parents/applications")return Response.json({applications:[]});
    if(url==="/api/v1/parents/notifications")return Response.json({notifications:[]});
    return Response.json({});
  });
  vi.stubGlobal("fetch",fetch);
  render(<ParentDiscovery/>);
  await user.click(screen.getByRole("button",{name:"Enfant déjà inscrit",exact:true}));
  await user.selectOptions(await screen.findByLabelText("Établissement de l'enfant"),"awassi");
  await user.type(screen.getByLabelText("Prénom de l'enfant"),"Malia");
  await user.type(screen.getByLabelText("Nom de l'enfant"),"Ondo");
  await user.type(screen.getByLabelText(/Matricule scolaire/),"AWA-0001");
  await user.type(screen.getByLabelText(/Votre nom tel qu'enregistré/),"Marie Ondo");
  await user.click(screen.getByRole("button",{name:"Demander le rattachement"}));
  expect(await screen.findByText(/En cours de vérification/)).toBeTruthy();
  const req=calls.find(([url,opts])=>url==="/api/v1/parents/existing-requests"&&opts.method==="POST");
  expect(JSON.parse(req[1].body)).toMatchObject({
    school:"awassi",first_name:"Malia",last_name:"Ondo",
    student_code:"AWA-0001",guardian_name:"Marie Ondo",
  });
  expect(calls.some(([url])=>url.includes("/applications")&&url!=="/api/v1/parents/applications")).toBe(false);
  expect(screen.queryByText("Inscription confirmée")).toBeNull();
});

test("la direction choisit la demande et confirme séparément le responsable légal",async()=>{
  const user=userEvent.setup();
  const prefix="/api/v1/schools/awassi";
  const request={id:"request-1",school:"awassi",school_name:"Lycée AWASSI",
    first_name:"Malia",last_name:"Ondo",student_code:"AWA-0001",
    guardian_name:"Marie Ondo",contact_phone:"",username:"marie-parents",status:"pending"};
  const calls=[];
  let complete=false;
  const fetch=vi.fn(async(url,opts={})=>{
    calls.push([url,opts]);
    if(url==="/api/v1/auth/csrf")return Response.json({});
    if(url===prefix+"/parent-existing-requests")return Response.json({requests:complete?[]:[request]});
    if(url===prefix+"/parent-links"&&opts.method==="POST"){
      complete=true;
      return Response.json({id:"link-1",active:true,revision:1,
        student_name:"Ondo Malia",guardian_name:"Marie Ondo",username:"marie-parents"});
    }
    if(url===prefix+"/parent-links")return Response.json({links:[]});
    if(url===prefix+"/students")return Response.json({students:[
      {id:"student-1",first_name:"Malia",last_name:"Ondo",student_code:"AWA-0001",active:true},
    ]});
    if(url===prefix+"/students/student-1/guardians")return Response.json({guardians:[
      {id:"guardian-1",full_name:"Marie Ondo",relationship:"Mère",active:true},
    ]});
    return Response.json({});
  });
  vi.stubGlobal("fetch",fetch);
  render(<SchoolParentAccess schoolId="awassi" canReadStudents canAssignRole/>);
  await user.click(await screen.findByRole("button",{name:"Examiner et rattacher"}));
  const username=screen.getByLabelText("Identifiant du compte parent existant");
  expect(username.value).toBe("marie-parents");
  expect(screen.getByLabelText("Élève",{exact:true}).value).toBe("student-1");
  await user.selectOptions(await screen.findByLabelText("Responsable légal",{exact:true}),"guardian-1");
  const activate=screen.getByRole("button",{name:"Vérifier et activer l’accès"});
  expect(activate.disabled).toBe(true);
  await user.click(screen.getByRole("checkbox",{name:/J’ai vérifié que ce compte appartient/}));
  await user.click(activate);
  const call=calls.find(([url,opts])=>url===prefix+"/parent-links"&&opts.method==="POST");
  expect(JSON.parse(call[1].body)).toEqual({
    guardian:"guardian-1",username:"marie-parents",identity_verified:true,request_id:"request-1",
  });
  expect(await screen.findByText("Accès familial vérifié et activé.")).toBeTruthy();
});
