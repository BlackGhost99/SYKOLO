// @vitest-environment jsdom
import React from "react";
import {cleanup, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, test, vi} from "vitest";
import ParentDiscovery from "./ParentDiscovery.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function showParent(responses) {
  const fetch = vi.fn(async (url) => {
    if (url === "/api/v1/auth/csrf") return Response.json({});
    return Response.json(responses[url] || {});
  });
  vi.stubGlobal("fetch", fetch);
  render(<ParentDiscovery />);
  return fetch;
}

const child = {id:"child-1", first_name:"Aïcha", last_name:"Mavoungou", date_of_birth:"2018-01-17"};
const school = {
  id:"school-1", name:"École de recette", city:"Libreville", district:"",
  school_type_label:"Primaire", description:"", phone:"",
  cash_at_school:true,
  classes:[{id:"class-1", name:"Première année A", year:"2026–2027",
    remaining:12, routes:["direct"], online_payment_available:false,
    fee_amount_xaf:1500}],
};

test("un parent peut sélectionner son enfant avant de rechercher une école", async () => {
  const user = userEvent.setup();
  showParent({
    "/api/v1/parents/catalog": {schools:[school]},
    "/api/v1/parents/family-children": {children:[child]},
    "/api/v1/parents/applications": {applications:[]},
    "/api/v1/parents/notifications": {notifications:[]},
  });
  await user.click(screen.getByRole("button", {name:"Mes enfants"}));
  const select = await screen.findByRole("button", {name:"Chercher une école pour Aïcha"});
  await user.click(select);
  expect(screen.getByText(/Choisissez un établissement pour Aïcha Mavoungou/)).toBeTruthy();
  await user.click(screen.getByRole("button", {name:"Voir les classes et candidater"}));
  expect(screen.getByLabelText("Enfant").value).toBe("child-1");
});

test("le suivi indique l'enfant et le rattachement scolaire après inscription", async () => {
  const user = userEvent.setup();
  showParent({
    "/api/v1/parents/catalog": {schools:[school]},
    "/api/v1/parents/family-children": {children:[child]},
    "/api/v1/parents/applications": {applications:[{
      id:"application-1", child:"child-1", child_name:"Aïcha Mavoungou",
      school:"school-1", school_name:school.name,
      classroom:"class-1", classroom_name:"Première année A",
      year:"2026–2027", route:"direct", status:"enrolled",
      payment_choice:"cash", fee_amount_xaf:1500, is_demo_cash:true,
      payment_status:"simule", scholarship:null,
    }]},
    "/api/v1/parents/notifications": {notifications:[]},
  });
  await user.click(screen.getByRole("button", {name:"Mes demandes"}));
  expect(await screen.findByText("Aïcha Mavoungou · École de recette")).toBeTruthy();
  expect(screen.getByText("Inscription confirmée")).toBeTruthy();
  expect(screen.getByText(/faire vérifier le rattachement au dossier scolaire/)).toBeTruthy();
});
