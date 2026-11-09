// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RealDemoExperience from "./RealDemoExperience.jsx";

const nativeFetch=globalThis.fetch;
afterEach(()=>{cleanup();globalThis.fetch=nativeFetch;vi.unstubAllGlobals();});

test("la démonstration monte le vrai Shell de direction et les vraies rubriques",async()=>{
  const network=vi.fn(()=>{throw Error("Une requête HTTP réelle est interdite");});
  vi.stubGlobal("fetch",network);
  render(<RealDemoExperience/>);
  expect(await screen.findByRole("heading",{name:"Tableau de bord"})).toBeTruthy();
  expect(screen.getByRole("navigation",{name:"Navigation principale"})).toBeTruthy();
  expect(screen.getByText("Encaissé ce mois")).toBeTruthy();
  expect(screen.getByRole("button",{name:"Paramètres avancés"})).toBeTruthy();
  expect(network).not.toHaveBeenCalled();
});

test("la console administrateur est exactement la console réelle avec des données fictives",async()=>{
  const network=vi.fn(()=>{throw Error("Réseau interdit");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  await user.click(screen.getByRole("button",{name:"Super-administrateur"}));
  expect(await screen.findByRole("heading",{name:"Console d'administration YEM"})).toBeTruthy();
  expect(screen.getByRole("navigation",{name:"Administration YEM"})).toBeTruthy();
  expect(network).not.toHaveBeenCalled();
});

test("la vue parent reprend le vrai composant parent et aucun appel de production",async()=>{
  const network=vi.fn(()=>{throw Error("Réseau interdit");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  await user.click(screen.getByRole("button",{name:"Parent d'élève"}));
  expect(await screen.findByRole("heading",{name:"Espace parents"})).toBeTruthy();
  expect(screen.getByText("Suivi scolaire de mes enfants")).toBeTruthy();
  expect(network).not.toHaveBeenCalled();
});

test("réinitialiser ne fait jamais de requête réseau",async()=>{
  const network=vi.fn(()=>{throw Error("Réseau interdit");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  await user.click(screen.getByRole("button",{name:"Réinitialiser"}));
  expect(screen.getByText("Données de visite réinitialisées.")).toBeTruthy();
  expect(network).not.toHaveBeenCalled();
});
