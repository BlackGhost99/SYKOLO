// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,within} from "@testing-library/react";
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
  expect(await screen.findByText("Encaissé ce mois")).toBeTruthy();
  await userEvent.setup().click(screen.getByRole("button",{name:"Élèves",exact:true}));
  expect(await screen.findByRole("button",{name:"Paramètres avancés"})).toBeTruthy();
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

test("Paiements affiche les statistiques de caisse et le formulaire sans page blanche",async()=>{
  const network=vi.fn(()=>{throw Error("Une requête réseau réelle est interdite");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  const nav=await screen.findByRole("navigation",{name:"Navigation principale"});
  await user.click(within(nav).getByRole("button",{name:"Paiements"}));
  expect(await screen.findByText("Encaissé aujourd’hui")).toBeTruthy();
  expect(screen.getByText("Nombre de paiements")).toBeTruthy();
  expect(screen.getByText("Nouvel encaissement")).toBeTruthy();
  expect(screen.queryByText(/Cette rubrique de démonstration ne peut pas s'afficher/)).toBeNull();
  expect(network).not.toHaveBeenCalled();
});

test("Évaluations et notes charge cours, élèves et notes d'un vrai écran YEM",async()=>{
  const network=vi.fn(()=>{throw Error("Une requête réseau réelle est interdite");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  const nav=await screen.findByRole("navigation",{name:"Navigation principale"});
  await user.click(within(nav).getByRole("button",{name:"Évaluations et notes"}));
  const section=await screen.findByRole("region",{name:"Évaluations et notes"});
  expect(within(section).getByText("Évaluations et saisie des notes")).toBeTruthy();
  await user.selectOptions(within(section).getByRole("combobox",{name:"Classe"}),"c1");
  const subject=await within(section).findByRole("combobox",{name:"Matière"});
  await user.selectOptions(subject,"course-c1-m1");
  const assessment=await within(section).findByRole("combobox",{name:"Évaluation"});
  await user.selectOptions(assessment,"assessment-course-c1-m1");
  expect(await within(section).findByText("Notes de l'évaluation : Contrôle continu n°1")).toBeTruthy();
  expect(within(section).getByRole("spinbutton",{name:/Note de Essono/})).toBeTruthy();
  expect(screen.queryByText(/Cette rubrique de démonstration ne peut pas s'afficher/)).toBeNull();
  expect(network).not.toHaveBeenCalled();
});

test("Bulletins reste visitable et affiche des exemples de résultats",async()=>{
  const network=vi.fn(()=>{throw Error("Une requête réseau réelle est interdite");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  const nav=await screen.findByRole("navigation",{name:"Navigation principale"});
  await user.click(within(nav).getByRole("button",{name:"Évaluations et notes"}));
  await user.click(screen.getByRole("tab",{name:"Bulletins"}));
  const section=await screen.findByRole("region",{name:"Bulletins et résultats"});
  expect(within(section).getByText("Bulletins et résultats")).toBeTruthy();
  await user.selectOptions(within(section).getByRole("combobox",{name:"Classe"}),"c1");
  expect(await within(section).findByText("Élève inscrit")).toBeTruthy();
  expect(screen.queryByText(/Cette rubrique de démonstration ne peut pas s'afficher/)).toBeNull();
  expect(network).not.toHaveBeenCalled();
});
