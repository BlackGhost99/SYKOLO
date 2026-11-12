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

test("la candidature affiche les exigences propres à l'établissement et transmet les réponses", async () => {
  const user=userEvent.setup();
  const schema={
    school_name:school.name,revision:3,configured:true,
    fields:[{key:"date_of_birth",label:"Date de naissance",type:"date",required:true,max_length:10}],
    custom_fields:[{key:"transport",label:"Transport scolaire",type:"select",options:["Oui","Non"],required:true,section:"eleve"}],
    documents:[{key:"acte_naissance",label:"Acte de naissance",required:true}],
  };
  const fetch=showParent({
    "/api/v1/parents/catalog":{schools:[school]},
    "/api/v1/parents/family-children":{children:[child]},
    "/api/v1/parents/applications":{applications:[]},
    "/api/v1/parents/notifications":{notifications:[]},
    "/api/v1/parents/admission-form?classroom=class-1&route=direct":schema,
  });
  await user.click(await screen.findByRole("button",{name:"Voir les classes et candidater"}));
  await user.selectOptions(screen.getByLabelText("Enfant"),"child-1");
  await user.selectOptions(screen.getByLabelText("Classe souhaitée"),"class-1");
  expect(await screen.findByRole("heading",{name:"Fiche demandée par École de recette"})).toBeTruthy();
  expect(screen.getByText("Acte de naissance")).toBeTruthy();
  await user.selectOptions(screen.getByLabelText(/Transport scolaire/),"Oui");
  await user.type(screen.getByLabelText("Votre téléphone"),"+241066667777");
  await user.click(screen.getByRole("button",{name:"Déposer ma demande"}));
  const call=fetch.mock.calls.find(([url,opts])=>url==="/api/v1/parents/applications"&&opts?.method==="POST");
  expect(call).toBeTruthy();
  const posted=JSON.parse(call[1].body);
  expect(posted.form_revision).toBe(3);
  expect(posted.custom_answers.transport).toBe("Oui");
});

test("un profil enfant permet l'ajout d'une photo privée et la personnalisation",async()=>{
  const user=userEvent.setup();
  showParent({
    "/api/v1/parents/catalog":{schools:[]},
    "/api/v1/parents/family-children":{children:[{...child,revision:1,profile:{gender:"F"}}]},
    "/api/v1/parents/applications":{applications:[]},
    "/api/v1/parents/notifications":{notifications:[]},
  });
  await user.click(screen.getByRole("button",{name:"Mes enfants"}));
  expect(await screen.findByText("Photo de profil")).toBeTruthy();
  await user.click(screen.getByRole("button",{name:"Personnaliser le profil"}));
  expect(screen.getByLabelText("Nationalité")).toBeTruthy();
  expect(screen.getByRole("button",{name:"Enregistrer les modifications"})).toBeTruthy();
});
