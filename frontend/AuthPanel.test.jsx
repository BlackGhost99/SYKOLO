// @vitest-environment jsdom
import React from "react";
import {render,screen,cleanup} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {it,expect,vi,afterEach} from "vitest";
import AuthPanel from "./AuthPanel.jsx";
vi.mock("./SchoolDashboard.jsx",()=>({default:()=> <p>Espace scolaire ouvert</p>}));
vi.mock("./PlatformConsole.jsx",()=>({default:()=> <p>Console plateforme ouverte</p>}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();window.history.replaceState(null,"","/");});
function setup(registrationStatus={email_registration_available:false}){
 const calls=[];vi.stubGlobal("fetch",vi.fn(async(url,options={})=>{
  calls.push([url,options]);return {ok:true,headers:new Headers({"content-type":"application/json"}),json:async()=>url.endsWith("registration-status")?registrationStatus:{authenticated:false}};
 }));return calls;
}
it("demande le code école avant les identifiants et envoie la portée choisie",async()=>{
 const calls=setup();render(<AuthPanel/>);const ui=userEvent.setup();
 const identifier=await screen.findByLabelText("Identifiant");expect(identifier.disabled).toBe(true);
 await ui.type(screen.getByLabelText("Code de l'établissement"),"school-a");
 await ui.type(identifier,"directeur1");await ui.type(screen.getByLabelText("Mot de passe",{exact:true}),"secret");await ui.click(screen.getByRole("button",{name:"Se connecter",exact:true}));
 expect(JSON.parse(calls.find(([url])=>url.endsWith("/login"))[1].body)).toMatchObject({scope:"school",school_code:"school-a",username:"directeur1"});
});
it("propose une connexion plateforme séparée",async()=>{
 const calls=setup();window.history.replaceState(null,"","/#/admin");render(<AuthPanel/>);const ui=userEvent.setup();
 await ui.type(await screen.findByLabelText("Identifiant"),"admin");
 expect(screen.queryByLabelText("Code de l'établissement")).toBeNull();
 await ui.type(screen.getByLabelText("Mot de passe",{exact:true}),"secret");await ui.click(screen.getByRole("button",{name:"Se connecter",exact:true}));
 expect(JSON.parse(calls.find(([url])=>url.endsWith("/login"))[1].body).scope).toBe("platform");
});
it("ouvre directement la connexion familles sur le lien parents",async()=>{
 const calls=setup();window.history.replaceState(null,"","/#/parents");render(<AuthPanel/>);const ui=userEvent.setup();
 await ui.type(await screen.findByLabelText("Identifiant"),"famille");
 expect(screen.queryByLabelText("Code de l'établissement")).toBeNull();
 await ui.type(screen.getByLabelText("Mot de passe",{exact:true}),"secret");await ui.click(screen.getByRole("button",{name:"Se connecter",exact:true}));
 expect(JSON.parse(calls.find(([url])=>url.endsWith("/login"))[1].body).scope).toBe("parent");
});
it("affiche la restriction du mode test avant la création d’un compte parent",async()=>{
 setup({email_registration_available:true,email_test_mode:true});
 render(<AuthPanel/>);
 const ui=userEvent.setup();
 await ui.click(screen.getByRole("button",{name:"Créer un compte parent",exact:true}));
 expect(await screen.findByText(/Mode test Resend/)).toBeTruthy();
 expect(screen.getByText(/domaine d’envoi vérifié/)).toBeTruthy();
 expect(screen.getByRole("button",{name:"Créer mon compte parent"}).disabled).toBe(false);
});
