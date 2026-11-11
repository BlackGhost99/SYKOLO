// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor,within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RealDemoExperience from "./RealDemoExperience.jsx";

const nativeFetch=globalThis.fetch;
const chooseRole=(user,role)=>user.selectOptions(screen.getByRole("combobox",{name:"Profil de démonstration"}),role);
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
  await chooseRole(user,"platform");
  expect(await screen.findByRole("heading",{name:"Console d'administration YEM"})).toBeTruthy();
  expect(screen.getByRole("navigation",{name:"Administration YEM"})).toBeTruthy();
  expect(network).not.toHaveBeenCalled();
});

test("la vue parent reprend le vrai composant parent et aucun appel de production",async()=>{
  const network=vi.fn(()=>{throw Error("Réseau interdit");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  await chooseRole(user,"parent");
  expect(await screen.findByRole("heading",{name:"Espace parents"})).toBeTruthy();
  expect(screen.getByText("Suivi scolaire de mes enfants")).toBeTruthy();
  expect(await screen.findByText("1 élève inscrit")).toBeTruthy();
  expect(await screen.findByText("14,5 / 20")).toBeTruthy();
  await user.click(screen.getByRole("button",{name:"Vie scolaire"}));
  expect(await screen.findByText("Bonne participation aux activités de la classe.")).toBeTruthy();
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

test("la caisse fictive enregistre un paiement partiel et met à jour le journal",async()=>{
  const network=vi.fn(()=>{throw Error("Réseau interdit");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  await chooseRole(user,"econome");
  const nav=await screen.findByRole("navigation",{name:"Navigation principale"});
  await user.click(await within(nav).findByRole("button",{name:"Paiements"}));
  expect(await screen.findByText("Encaissé aujourd’hui")).toBeTruthy();
  await user.selectOptions(screen.getByRole("combobox",{name:/^Élève/}),"en-s1");
  const amount=screen.getByLabelText(/Montant saisi/);
  await waitFor(()=>expect(amount.disabled).toBe(false));
  await user.clear(amount);
  await user.type(amount,"1500");
  await user.click(screen.getByRole("button",{name:/Valider|Enregistrer l.encaissement|Encaisser/i}));
  expect(await screen.findByText(/encaissement de.*enregistré/i)).toBeTruthy();
  expect(screen.getByRole("link",{name:"Télécharger le reçu groupé PDF"})).toBeTruthy();
  expect(await screen.findByRole("link",{name:"R-SIM-0001"})).toBeTruthy();
  expect(network).not.toHaveBeenCalled();
});

test("Évaluations et notes charge cours, élèves et notes d'un vrai écran YEM",async()=>{
  const network=vi.fn(()=>{throw Error("Une requête réseau réelle est interdite");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  const nav=await screen.findByRole("navigation",{name:"Navigation principale"});
  await user.click(await within(nav).findByRole("button",{name:"Évaluations et notes"}));
  const section=await screen.findByRole("region",{name:"Évaluations et notes"});
  expect(within(section).getByText("Évaluations et saisie des notes")).toBeTruthy();
  await user.selectOptions(within(section).getByRole("combobox",{name:"Classe"}),"c1");
  const subject=await within(section).findByRole("combobox",{name:"Matière"});
  await user.selectOptions(subject,"course-c1-m1");
  const assessment=await within(section).findByRole("combobox",{name:"Évaluation"});
  await user.selectOptions(assessment,"assessment-course-c1-m1");
  expect(await within(section).findByText("Notes de l'évaluation : Contrôle continu n°1")).toBeTruthy();
  const score=within(section).getByRole("spinbutton",{name:/Note de Essono/});
  await user.clear(score);
  await user.type(score,"17");
  await user.click(within(score.closest("form")).getByRole("button",{name:"Enregistrer cette note"}));
  expect(await screen.findByText("Note enregistrée.")).toBeTruthy();
  await user.click(within(section).getByRole("button",{name:"Publier les résultats"}));
  expect(await screen.findByText("Évaluation publiée.")).toBeTruthy();
  expect(screen.queryByText(/Cette rubrique de démonstration ne peut pas s'afficher/)).toBeNull();
  expect(network).not.toHaveBeenCalled();
});

test("Bulletins reste visitable et affiche des exemples de résultats",async()=>{
  const network=vi.fn(()=>{throw Error("Une requête réseau réelle est interdite");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  const nav=await screen.findByRole("navigation",{name:"Navigation principale"});
  await user.click(await within(nav).findByRole("button",{name:"Évaluations et notes"}));
  await user.click(screen.getByRole("tab",{name:"Bulletins"}));
  const section=await screen.findByRole("region",{name:"Bulletins et résultats"});
  expect(within(section).getByText("Bulletins et résultats")).toBeTruthy();
  await user.selectOptions(within(section).getByRole("combobox",{name:"Classe"}),"c1");
  await user.selectOptions(await within(section).findByLabelText("Élève inscrit"),"en-s1");
  await user.click(within(section).getByRole("button",{name:"Préparer le bulletin"}));
  expect(await screen.findByText(/Bulletin scolaire — démonstration · Brouillon/)).toBeTruthy();
  await user.click(within(section).getByRole("button",{name:"Publier le bulletin"}));
  expect(await screen.findByText("Bulletin publié et verrouillé.")).toBeTruthy();
  const blobUrl=vi.fn(()=>"blob:demo-bulletin");
  const OriginalURL=globalThis.URL;
  vi.stubGlobal("URL",class extends OriginalURL {
    static createObjectURL=blobUrl;
    static revokeObjectURL=vi.fn();
  });
  const download=vi.spyOn(HTMLAnchorElement.prototype,"click").mockImplementation(function(){
    expect(this.download).toBe("bulletin-demo.pdf");
  });
  try{
    await user.click(screen.getByRole("link",{name:"Exporter le bulletin PDF (A4)"}));
    expect(await screen.findByText("Document fictif téléchargé.")).toBeTruthy();
    expect(blobUrl.mock.calls[0][0].type).toBe("application/pdf");
    expect(download).toHaveBeenCalledOnce();
  }finally{download.mockRestore();}
  expect(screen.queryByText(/Cette rubrique de démonstration ne peut pas s'afficher/)).toBeNull();
  expect(network).not.toHaveBeenCalled();
});

test("les menus des vrais espaces suivent les profils choisis",async()=>{
  const network=vi.fn(()=>{throw Error("Réseau interdit");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  await chooseRole(user,"proprietaire");
  expect(await screen.findByRole("heading",{name:"Pilotage du propriétaire"})).toBeTruthy();
  await chooseRole(user,"secretariat");
  let nav=await screen.findByRole("navigation",{name:"Navigation principale"});
  expect(await within(nav).findByRole("button",{name:"Admissions"})).toBeTruthy();
  expect(within(nav).queryByRole("button",{name:"Paiements"})).toBeNull();
  await chooseRole(user,"enseignant");
  nav=await screen.findByRole("navigation",{name:"Navigation principale"});
  await user.click(await within(nav).findByRole("button",{name:"Évaluations et notes"}));
  const section=await screen.findByRole("region",{name:"Évaluations et notes"});
  await user.selectOptions(await within(section).findByLabelText("Classe"),"c1");
  const subject=within(section).getByLabelText("Matière");
  await waitFor(()=>expect([...subject.options].map(item=>item.value)).toEqual(["","course-c1-m1"]));
  expect(network).not.toHaveBeenCalled();
});
test("la direction accepte une candidature puis le secrétariat confirme l’inscription",async()=>{
  const network=vi.fn(()=>{throw Error("Réseau interdit");});
  vi.stubGlobal("fetch",network);
  const user=userEvent.setup();
  render(<RealDemoExperience/>);
  const openApplication=async()=>{
    const nav=await screen.findByRole("navigation",{name:"Navigation principale"});
    await user.click(await within(nav).findByRole("button",{name:"Admissions"}));
    const application=await screen.findByRole("combobox",{name:"Candidature"});
    await within(application).findByRole("option",{name:/Obame David/});
    await user.selectOptions(application,"admission-lycee");
  };
  await openApplication();
  await user.type(screen.getByRole("textbox",{name:/Motif de la décision/}),"Dossier complet");
  await user.click(screen.getByRole("button",{name:/Accepter la candidature/}));
  expect(await screen.findByRole("button",{name:"Confirmer l’inscription définitive"})).toBeTruthy();
  await chooseRole(user,"secretariat");
  await openApplication();
  await user.click(screen.getByRole("button",{name:"Confirmer l’inscription définitive"}));
  expect(await screen.findByText("Inscription confirmée")).toBeTruthy();
  const nav=screen.getByRole("navigation",{name:"Navigation principale"});
  await user.click(within(nav).getByRole("button",{name:"Élèves"}));
  expect(await screen.findByText("Obame David")).toBeTruthy();
  await user.click(screen.getByText("Obame David"));
  await user.click(screen.getByRole("button",{name:"Voir la fiche"}));
  expect(await screen.findByRole("heading",{name:"Obame David"})).toBeTruthy();
  expect(screen.getByText("Mme Obame")).toBeTruthy();
  expect(network).not.toHaveBeenCalled();
});
