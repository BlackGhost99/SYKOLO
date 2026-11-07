// @vitest-environment jsdom
import React from "react";
import {afterEach,beforeEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DemoExperience from "./DemoExperience.jsx";
import App from "./App.jsx";

beforeEach(()=>{window.history.replaceState(null,"","/");});
afterEach(()=>{cleanup();vi.unstubAllGlobals();window.history.replaceState(null,"","/");});

test("la route de démonstration ne monte aucune requête API ni authentification réelle",async()=>{
  window.history.replaceState(null,"","/#/demo");
  const fetch=vi.fn(()=>{throw Error("Une requête réelle est interdite dans la démonstration");});
  vi.stubGlobal("fetch",fetch);
  render(<App/>);
  expect(screen.getByText("MODE DÉMONSTRATION")).toBeTruthy();
  expect(screen.getByRole("heading",{name:"Tableau de bord"})).toBeTruthy();
  expect(fetch).not.toHaveBeenCalled();
});

test("l'utilisateur parcourt les trois interfaces sans toucher aux comptes réels",async()=>{
  const user=userEvent.setup();
  render(<DemoExperience/>);
  await user.click(screen.getByRole("button",{name:"Parent d'élève"}));
  expect(screen.getByRole("heading",{name:"Mes enfants"})).toBeTruthy();
  expect(screen.getByText("Essono Grâce")).toBeTruthy();
  await user.click(screen.getByRole("button",{name:"Super-administrateur"}));
  expect(screen.getByRole("heading",{name:"Console de la plateforme YEM"})).toBeTruthy();
  await user.click(screen.getByRole("button",{name:"Direction / établissement"}));
  expect(screen.getByRole("heading",{name:"Tableau de bord"})).toBeTruthy();
});

test("ajouter un élève change la liste localement sans écriture en base",async()=>{
  const user=userEvent.setup();
  render(<DemoExperience/>);
  await user.click(screen.getByRole("button",{name:"Élèves",exact:true}));
  await user.click(screen.getByRole("button",{name:"Nouvel élève"}));
  const modal=screen.getByRole("dialog");
  await user.type(within(modal).getByRole("textbox",{name:"Nom et prénoms"}),"Essai YEM");
  await user.type(within(modal).getByRole("textbox",{name:"Responsable légal"}),"Mme Essai");
  await user.click(within(modal).getByRole("button",{name:"Enregistrer dans la maquette"}));
  expect(screen.getAllByText("Essai YEM").length).toBeGreaterThan(0);
  expect(screen.queryByRole("dialog")).toBeNull();
  await user.click(screen.getByRole("button",{name:/Réinitialiser/}));
  await user.click(screen.getByRole("button",{name:"Élèves",exact:true}));
  expect(screen.queryByText("Essai YEM")).toBeNull();
});

test("l'affectation passe par vérification, admission puis inscription distincte",async()=>{
  const user=userEvent.setup();
  render(<DemoExperience/>);
  await user.click(screen.getByRole("button",{name:"Admissions",exact:true}));
  expect(screen.getByRole("heading",{name:"Admissions & préinscriptions"})).toBeTruthy();
  const approve=screen.getByRole("button",{name:"Accepter"});
  await user.click(approve);
  expect(await screen.findByText(/Vérifiez d'abord l'éligibilité/)).toBeTruthy();
  await user.click(screen.getByRole("button",{name:"Simuler la vérification"}));
  await user.click(screen.getByRole("button",{name:"Accepter"}));
  expect(screen.getAllByText("Accepté").length).toBeGreaterThan(0);
  await user.click(screen.getByRole("button",{name:"Inscrire l'élève"}));
  await user.click(screen.getByRole("button",{name:"Élèves",exact:true}));
  expect(screen.getAllByText("Obame David").length).toBeGreaterThan(0);
});

test("les paiements sont simulés et produisent un reçu explicitement fictif",async()=>{
  const user=userEvent.setup();
  const fetch=vi.fn(()=>{throw Error("Interdiction de contacter SingPay depuis la démo");});
  vi.stubGlobal("fetch",fetch);
  render(<DemoExperience/>);
  await user.click(screen.getByRole("button",{name:"Parent d'élève"}));
  await user.click(screen.getByRole("button",{name:"Frais & paiements"}));
  await user.click(screen.getAllByRole("button",{name:"Simuler paiement"})[0]);
  const dialog=screen.getByRole("dialog");
  expect(within(dialog).getByText(/Aucun appel à SingPay/)).toBeTruthy();
  await user.click(within(dialog).getByRole("button",{name:"Confirmer la simulation"}));
  expect(screen.getByRole("dialog",{name:"Reçu fictif de paiement"})).toBeTruthy();
  expect(screen.getByText(/Aucun argent n'a été transféré/)).toBeTruthy();
  expect(fetch).not.toHaveBeenCalled();
});

test("le profil maternelle affiche des compétences plutôt qu'une moyenne obligatoire sur 20",async()=>{
  const user=userEvent.setup();
  render(<DemoExperience/>);
  await user.selectOptions(screen.getByRole("combobox",{name:"Établissement de démonstration"}),"maternelle");
  await user.click(screen.getByRole("button",{name:"Bulletins",exact:true}));
  expect(screen.getByText("Suivi par compétences")).toBeTruthy();
  expect(screen.getByText(/Motricité : Acquis/)).toBeTruthy();
});

test("un parent peut simuler une préinscription auprès d'un autre établissement",async()=>{
  const user=userEvent.setup();
  render(<DemoExperience/>);
  await user.click(screen.getByRole("button",{name:"Parent d'élève"}));
  await user.click(screen.getByRole("button",{name:"Préinscriptions"}));
  await user.click(screen.getByRole("button",{name:/École Primaire Démonstration/}));
  const modal=screen.getByRole("dialog");
  await user.type(within(modal).getByRole("textbox",{name:"Nom et prénoms du candidat"}),"Adama Test");
  await user.click(within(modal).getByRole("button",{name:"Enregistrer dans la maquette"}));
  expect(screen.getByText("Adama Test")).toBeTruthy();
  expect(screen.getByText(/Candidature créée en mode démonstration/)).toBeTruthy();
});
