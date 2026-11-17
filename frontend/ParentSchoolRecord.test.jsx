// @vitest-environment jsdom
import React from "react";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, test, vi} from "vitest";
import ParentPortal from "./ParentPortal.jsx";

vi.mock("./ParentDiscovery.jsx", () => ({default: () => null}));
vi.mock("./PWAInstall.jsx", () => ({default: () => null}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderPortal(responses) {
  const fetch = vi.fn(async path => Response.json(responses[path] || {}));
  vi.stubGlobal("fetch", fetch);
  render(<ParentPortal/>);
  return fetch;
}

test("le parent retrouve l’identifiant à donner à l’école pendant le rattachement", async () => {
  const path = "/api/v1/parents/children";
  const fetch = renderPortal({[path]:{children:[], parent_username:"compte-test"}});
  await screen.findByRole("heading", {name:"Commençons le suivi de votre enfant"});
  expect(screen.getAllByText("compte-test").length).toBeGreaterThan(0);
  expect(screen.getByRole("heading", {name:"Commençons le suivi de votre enfant"})).toBeTruthy();
  expect(screen.queryByRole("heading", {name:"Dernières notes"})).toBeNull();
  expect(screen.queryByRole("heading", {name:"Situation financière"})).toBeNull();
  expect(screen.queryByRole("button", {name:"Payer en ligne"})).toBeNull();
  await userEvent.setup().click(screen.getByRole("button", {name:"Actualiser mes enfants"}));
  await screen.findByRole("heading", {name:"Commençons le suivi de votre enfant"});
  expect(fetch.mock.calls.filter(([url]) => url === path)).toHaveLength(2);
});

test("la fiche affiche la classe, les notes et la vie scolaire de l’année choisie", async () => {
  const path = "/api/v1/parents/children";
  const child = path + "/child-1";
  renderPortal({
    [path]:{children:[{student:"child-1", first_name:"Lina", last_name:"Nkomo", school_name:"École test", student_code:"001"}]},
    [child+"/enrollments"]:{enrollments:[
      {id:"en-1", year:"2026–2027", year_id:"year-1", year_status:"current", classroom:"CM1 A", class_size:24, active:true, status:"inscrit"},
      {id:"en-2", year:"2025–2026", year_id:"year-2", year_status:"closed", classroom:"CE2 B", class_size:18, active:true, status:"inscrit"},
    ]},
    [child+"/grades?year=year-1"]:{grades:[{id:"grade-1", subject:"Mathématiques", assessment:"Contrôle 1", date:"2026-10-13",
      score:0, scale_kind:"numeric", scale_max:15, weight:"1.000"}]},
    [child+"/attendance?year=year-1"]:{totals:{absent:0,late:1,present:0}, attendance:[
      {id:"mark-1", date:"2026-10-14", slot:"Matin", group:"late", status:"Retard", justified:true},
    ], conduct:[{id:"conduct-1", date:"2026-10-14", label:"Sanction", message:"Travail de rattrapage mercredi."}]},
    [child+"/attendance?year=year-2"]:{totals:{absent:0,late:0,present:0}, attendance:[], conduct:[]},
  });
  const user = userEvent.setup();
  expect(await screen.findByRole("heading", {name:"Lina Nkomo"})).toBeTruthy();
  expect(await screen.findByText("CM1 A")).toBeTruthy();
  await user.click(within(screen.getByRole("navigation", {name:"Navigation YEM Familles"})).getByRole("button", {name:"Scolarité"}));
  expect(await screen.findByText("0 / 15")).toBeTruthy();
  await user.click(screen.getByRole("button", {name:"Vie scolaire"}));
  expect(await screen.findByText("Travail de rattrapage mercredi.")).toBeTruthy();
  expect(screen.getAllByText("1").length).toBeGreaterThan(0);
  await user.selectOptions(screen.getByLabelText("Année scolaire"), "year-2");
  expect(screen.getByText("CE2 B")).toBeTruthy();
  expect(await screen.findByText(/Aucune observation ni sanction communiquée/)).toBeTruthy();
  expect(screen.queryByText("Travail de rattrapage mercredi.")).toBeNull();
});

test("un compte sans enfant ouvre directement les profils et garde les démarches accessibles", async () => {
  const path = "/api/v1/parents/children";
  renderPortal({[path]:{children:[],parent_username:"parent-pilote"}});
  const user = userEvent.setup();
  expect(await screen.findByRole("heading",{name:"Commençons le suivi de votre enfant"})).toBeTruthy();
  await user.click(screen.getByRole("button",{name:"Ajouter un enfant"}));
  expect(screen.getByRole("navigation",{name:"Démarches des familles"})).toBeTruthy();
  expect(screen.getByRole("button",{name:"Profils enfants"}).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByText(/Aucun dossier scolaire encore rattaché/)).toBeTruthy();
  expect(screen.queryByRole("heading",{name:"Commençons le suivi de votre enfant"})).toBeNull();
  await user.click(screen.getByRole("button",{name:"Mes demandes"}));
  expect(screen.getByRole("button",{name:"Mes demandes"}).getAttribute("aria-pressed")).toBe("true");
});


test("la famille retrouve les messages publiés dans le carnet de liaison", async () => {
  const path = "/api/v1/parents/children";
  const child = path + "/child-1";
  renderPortal({
    [path]:{children:[{student:"child-1",first_name:"Lina",last_name:"Nkomo",school_name:"École",student_code:"001"}]},
    [child+"/enrollments"]:{enrollments:[
      {id:"en-1",year:"2026-2027",year_id:"year-1",year_status:"current",
       classroom:"Crèche A",class_size:12,active:true,status:"inscrit",preschool_liaison:true},
    ]},
    [child+"/liaison?year=year-1"]:{messages:[{id:"entry",day:"2026-10-01",message:"Lecture vendredi."}]},
  });
  const user=userEvent.setup();
  await screen.findByText("Crèche A");
  await user.click(within(screen.getByRole("navigation",{name:"Navigation YEM Familles"})).getByRole("button",{name:"Scolarité"}));
  await user.click(screen.getByRole("button",{name:"Carnet de liaison"}));
  expect(await screen.findByText("Lecture vendredi.")).toBeTruthy();
});

test("le cahier de textes est accessible depuis l'accueil parent et ne montre pas les bulletins à sa place", async()=>{
  const path="/api/v1/parents/children";
  const child=path+"/child-1";
  const fetch=renderPortal({
    [path]:{children:[{student:"child-1",first_name:"Lina",last_name:"Nkomo",school_name:"École",student_code:"001"}]},
    [child+"/enrollments"]:{enrollments:[{id:"en-1",year:"2026-2027",year_id:"year-1",year_status:"current",classroom:"6e A",class_size:24,active:true,status:"inscrit"}]},
    [child+"/diary?year=year-1"]:{entries:[{id:"one",day:"2026-11-17",subject:"Mathématiques",classroom:"6e A",title:"Fractions",lesson:"Comparer les fractions",homework:"Exercice 1"}]},
  });
  const user=userEvent.setup();
  await screen.findByText("6e A");
  await user.click(screen.getByRole("button",{name:"Cahier de textes"}));
  expect(await screen.findByText("Comparer les fractions")).toBeTruthy();
  expect(screen.getByText("Exercice 1")).toBeTruthy();
  expect(screen.queryByText("Bulletins officiels publiés")).toBeNull();
  expect(fetch.mock.calls.some(([url])=>url===child+"/diary?year=year-1")).toBe(true);
});
