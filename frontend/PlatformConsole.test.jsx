// @vitest-environment jsdom
import React from "react";
import {afterEach, beforeEach, expect, test, vi} from "vitest";
import {cleanup, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PlatformConsole from "./PlatformConsole.jsx";

vi.mock("./SchoolDashboard.jsx", () => ({
  default: () => <div data-testid="school-workspace">Espace scolaire indépendant</div>,
}));
const school = {id:"11111111-1111-1111-1111-111111111111",name:"Collège Test",organization:"Groupe Test",members_count:3,active:true};
function reply(data) {
  return {ok:true, headers:{get:()=>"application/json"}, json: async()=>data};
}
beforeEach(() => {
  vi.stubGlobal("confirm", () => true);
  vi.stubGlobal("fetch", vi.fn(async url => {
    if (String(url).endsWith("/api/v1/platform/schools")) return reply({schools:[school],total:1,organizations:1,users:3,organization_options:[{id:"22222222-2222-2222-2222-222222222222",name:"Groupe Test"}]});
    if (String(url).includes("/admin-access")) return reply({school_id:school.id,access:"direction"});
    return reply({});
  }));
});
afterEach(() => {cleanup();vi.unstubAllGlobals();});

test("la console plateforme ne contient plus de tableau de bord scolaire imbriqué", async () => {
  const u = userEvent.setup();
  render(<PlatformConsole user={{username:"superadmin"}} mfaEnabled accountView={<div>Sécurité du compte YEM</div>} onLogout={()=>{}}/>);
  expect(await screen.findByText("Collège Test")).toBeTruthy();
  expect(screen.queryByTestId("school-workspace")).toBeNull();
  await u.click(screen.getByRole("button", {name:/Collège Test/}));
  expect(screen.getByRole("heading", {name:"Administration par établissement"})).toBeTruthy();
  expect(screen.queryByTestId("school-workspace")).toBeNull();
  await u.click(screen.getByRole("button", {name:/Ouvrir l'espace scolaire/}));
  expect(await screen.findByTestId("school-workspace")).toBeTruthy();
  expect(document.querySelector(".pc-shell")).toBeNull();
  await u.click(screen.getByRole("button", {name:/Retour à la console plateforme/}));
  expect(screen.queryByTestId("school-workspace")).toBeNull();
});

test("la page de gestion permet de rechercher les établissements", async () => {
  const u = userEvent.setup();
  render(<PlatformConsole user={{username:"superadmin"}} mfaEnabled accountView={<div>Sécurité du compte YEM</div>} onLogout={()=>{}}/>);
  await screen.findByText("Collège Test");
  await u.click(screen.getByRole("button", {name:/Établissements/}));
  const search = screen.getByRole("searchbox");
  await u.type(search, "inexistant");
  expect(screen.getByText(/Aucun établissement ne correspond/)).toBeTruthy();
  await u.clear(search);
  await u.type(search, "collège");
  expect(screen.getByRole("button", {name:/Voir la fiche/})).toBeTruthy();
});

test("la console bloquée par MFA affiche les réglages de sécurité", () => {
  render(<PlatformConsole user={{username:"superadmin"}} mfaEnabled={false} accountView={<div>Formulaire MFA</div>} onLogout={()=>{}}/>);
  expect(screen.getByText(/Activation MFA obligatoire/)).toBeTruthy();
  expect(screen.getByText("Formulaire MFA")).toBeTruthy();
  expect(screen.queryByRole("button", {name:/Nouvel établissement/})).toBeNull();
});
