// @vitest-environment jsdom
import React from "react";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, test, vi} from "vitest";
import AuthPanel from "./AuthPanel.jsx";

afterEach(()=>{
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

function mockApi({scope="school", role="direction", permissions=[], restricted=false}={}) {
  vi.spyOn(window, "scrollTo").mockImplementation(()=>{});
  const school = {id:"mbele", name:"Lycée Privé MBELE"};
  const student = {id:"student-1", active:true, first_name:"Élève", last_name:"Test", student_code:"001"};
  const guardian = {id:"guardian-1", active:true, full_name:"Responsable Test", relationship:"Mère"};
  const link = {id:"link-1", active:true, revision:1, student_name:"Test Élève", guardian_name:guardian.full_name, username:"famille"};
  const prefix = "/api/v1/schools/mbele";
  const data = {
    "/api/v1/auth/me": {authenticated:true, user:{username:"compte-test"}, login_scope:scope, school_id:scope==="school"?"mbele":null},
    "/api/v1/auth/parents/registration-status": {email_registration_available:true},
    "/api/v1/schools": {schools:[school]},
    [prefix+"/my-access"]: {school, role, permissions, cycle_scope_restricted:restricted},
    [prefix+"/organization/my-appointments"]: {appointments:[]},
    [prefix+"/parent-links"]: {links:[]},
    [prefix+"/students"]: {students:[student]},
    [prefix+"/students/student-1/guardians"]: {guardians:[guardian]},
    "/api/v1/parents/children": {children:[]},
    "/api/v1/parents/family-children": {children:[]},
    "/api/v1/parents/catalog": {schools:[]},
    "/api/v1/parents/applications": {applications:[]},
    "/api/v1/parents/notifications": {notifications:[]},
  };
  const fetch = vi.fn(async (path, {method="GET"}={})=>{
    if (path===prefix+"/parent-links"&&method==="POST") return Response.json(link);
    if (path===prefix+"/parent-links/link-1"&&method==="PATCH") {
      return Response.json({...link, active:false, revision:2});
    }
    return Response.json(data[path]||{});
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

test("une directrice gère les accès dans son école depuis Parents", async ()=>{
  const fetch = mockApi({permissions:["school.parents.manage","school.students.read","school.members.write"]});
  const user = userEvent.setup();
  render(<AuthPanel/>);
  const nav = await screen.findByRole("navigation", {name:"Navigation principale"});
  await user.click(await within(nav).findByRole("button", {name:"Parents", exact:true}));
  expect(await screen.findByRole("heading", {name:"Gestion des accès parents"})).toBeTruthy();
  expect(screen.getByText("Vérifiez les accès des responsables légaux de Lycée Privé MBELE.")).toBeTruthy();
  expect(screen.queryByRole("button", {name:"Installer YEM sur mon téléphone"})).toBeNull();
  expect(screen.queryByRole("button", {name:"Mes demandes"})).toBeNull();
  await screen.findByRole("option", {name:"Test Élève · 001"});
  await user.selectOptions(screen.getByLabelText("Élève", {exact:true}), "student-1");
  await screen.findByRole("option", {name:"Responsable Test (Mère)"});
  await user.selectOptions(screen.getByLabelText("Responsable légal", {exact:true}), "guardian-1");
  await user.type(screen.getByLabelText("Identifiant du compte parent existant"), "famille");
  await user.click(screen.getByRole("button", {name:"Rattacher le compte parent"}));
  expect(fetch).toHaveBeenCalledWith("/api/v1/schools/mbele/members", expect.objectContaining({
    method:"POST", body:JSON.stringify({username:"famille", role:"parent", create_only:true}),
  }));
  await user.click(screen.getByRole("button", {name:"Vérifier et activer l’accès"}));
  const row = await screen.findByRole("row", {name:/Test Élève Responsable Test famille Actif/});
  await user.click(within(row).getByRole("button", {name:/Révoquer l’accès/}));
  expect(await screen.findByText("Révoqué")).toBeTruthy();
  expect(fetch).toHaveBeenCalledWith("/api/v1/schools/mbele/parent-links/link-1", expect.objectContaining({
    method:"PATCH", body:JSON.stringify({revision:1, active:false}),
  }));
  expect(fetch.mock.calls.some(([path])=>path.startsWith("/api/v1/parents/"))).toBe(false);
});

test.each([
  {role:"enseignant", permissions:["school.view"]},
  {role:"direction", permissions:["school.parents.manage"], restricted:true},
])("le menu Parents respecte les autorisations de l’école", async (options)=>{
  const fetch = mockApi(options);
  render(<AuthPanel/>);
  await screen.findByRole("heading", {name:"Tableau de bord"});
  expect(screen.queryByRole("button", {name:"Parents", exact:true})).toBeNull();
  expect(fetch.mock.calls.some(([path])=>path.includes("/parent-links")||path.startsWith("/api/v1/parents/"))).toBe(false);
});

test.each([
  {scope:"parent"},
  {scope:"school", role:"parent", permissions:["school.view"]},
])("un compte parent accède au portail autonome", async (options)=>{
  const fetch = mockApi(options);
  render(<AuthPanel/>);
  await screen.findByRole("navigation", {name:"Navigation du compte parent"});
  expect(screen.getByRole("heading", {name:"Espace parents", exact:true})).toBeTruthy();
  expect(screen.getByRole("button", {name:"Installer YEM sur mon téléphone"})).toBeTruthy();
  expect(screen.queryByRole("navigation", {name:"Navigation principale"})).toBeNull();
  expect(screen.queryByRole("button", {name:"Espace établissement"})).toBeNull();
  expect(fetch.mock.calls.some(([path])=>path.includes("/parent-links"))).toBe(false);
  if (options.scope==="parent") expect(fetch.mock.calls.some(([path])=>path.startsWith("/api/v1/schools"))).toBe(false);
});
