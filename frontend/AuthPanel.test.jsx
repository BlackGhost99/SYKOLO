// @vitest-environment jsdom
import React from "react";
import {render,screen,cleanup,fireEvent} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {it,expect,vi,afterEach} from "vitest";
import AuthPanel from "./AuthPanel.jsx";
import loginArtwork from "./assets/yem-login-original.png";
vi.mock("./SchoolDashboard.jsx",()=>({default:()=> <p>Espace scolaire ouvert</p>}));
vi.mock("./PlatformConsole.jsx",()=>({default:()=> <p>Console plateforme ouverte</p>}));
vi.mock("./ParentPortal.jsx",()=>({FamilyWorkspace:()=> <p>Espace famille ouvert</p>}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();window.history.replaceState(null,"","/");});
function setup(registrationStatus = {email_registration_available: false}, loginStatus = 200) {
  const calls = [];
  let session = {authenticated: false};
  vi.stubGlobal("fetch", vi.fn(async (url, options = {}) => {
    calls.push([url, options]);
    let status = 200;
    let data = {};
    if (url.endsWith("/registration-status")) data = registrationStatus;
    if (url.endsWith("/register")) {
      data = {message: "Demande traitée.", email_verification_required: registrationStatus.email_verification_required};
    }
    if (url.endsWith("/login")) {
      status = loginStatus;
      if (status === 200) {
        const {username, scope} = JSON.parse(options.body);
        session = {authenticated: true, login_scope: scope, user: {username, is_platform_admin: scope === "platform"}};
      }
      data = status === 200 ? {authenticated: true} : {error: "Identifiants invalides."};
    }
    if (url.endsWith("/me")) data = session;
    return {ok: status === 200, status, headers: new Headers({"content-type": "application/json"}), json: async () => data};
  }));
  return calls;
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
 setup({email_registration_available:true,email_verification_required:true,email_test_mode:true});
 render(<AuthPanel/>);
 const ui=userEvent.setup();
 await ui.click(screen.getByRole("button",{name:"Créer un compte parent",exact:true}));
 expect(await screen.findByText(/Mode test Resend/)).toBeTruthy();
 expect(screen.getByText(/domaine d’envoi vérifié/)).toBeTruthy();
 expect(screen.getByRole("button",{name:"Créer mon compte parent"}).disabled).toBe(false);
});

const pilot = {email_registration_available: true, email_verification_required: false, email_test_mode: false};
const parentPassword = "Test compte parent sécurisé 2026!";

async function submitParentRegistration(ui) {
  await ui.type(screen.getByLabelText("Prénom"), "Diane");
  await ui.type(screen.getByLabelText("Nom"), "Nze");
  await ui.type(screen.getByLabelText("Identifiant"), "diane-nze");
  await ui.type(screen.getByLabelText("Adresse e-mail"), "diane@example.test");
  await ui.type(screen.getByLabelText("Mot de passe (au moins 12 caractères)"), parentPassword);
  await ui.click(screen.getByRole("button", {name: "Créer mon compte parent"}));
}

it("ouvre l’espace parent après l’inscription en mode pilote", async () => {
  const calls = setup(pilot);
  render(<AuthPanel/>);
  const ui = userEvent.setup();
  await ui.click(screen.getByRole("button", {name: "Créer un compte parent", exact: true}));
  expect(await screen.findByText(/aucun e-mail d’activation n’est envoyé/)).toBeTruthy();
  expect(screen.queryByRole("button", {name: "Renvoyer mon lien d'activation"})).toBeNull();
  await submitParentRegistration(ui);
  expect(await screen.findByText("Espace famille ouvert")).toBeTruthy();
  expect(JSON.parse(calls.find(([url]) => url.endsWith("/login"))[1].body)).toMatchObject({
    scope: "parent", username: "diane-nze", password: parentPassword,
  });
  expect(window.location.hash).toBe("#/parents");
});

it("laisse corriger l’inscription pilote quand la connexion est refusée", async () => {
  setup(pilot, 401);
  render(<AuthPanel/>);
  const ui = userEvent.setup();
  await ui.click(screen.getByRole("button", {name: "Créer un compte parent", exact: true}));
  await submitParentRegistration(ui);
  expect(await screen.findByText(/essayez un autre identifiant et une autre adresse e-mail/)).toBeTruthy();
  expect(screen.getByLabelText("Identifiant").value).toBe("diane-nze");
  expect(screen.getByLabelText("Adresse e-mail").value).toBe("diane@example.test");
  expect(screen.getByRole("button", {name: "Créer mon compte parent"}).disabled).toBe(false);
  expect(screen.queryByText("Espace famille ouvert")).toBeNull();
  await ui.click(screen.getByRole("button", {name: "Connexion", exact: true}));
  expect(screen.getByRole("heading", {name: "Espace parents"})).toBeTruthy();
});

it("conserve les trois parcours de connexion dans la nouvelle interface YEM", async () => {
  setup();
  render(<AuthPanel />);
  const ui = userEvent.setup();
  expect(await screen.findByRole("heading", { name: "Accès sécurisé à YEM" })).toBeTruthy();
  const scopes = screen.getByRole("group", { name: "Choisir votre espace de connexion" });
  const school = scopes.querySelector('button[aria-pressed="true"]');
  expect(school?.textContent).toBe("Établissement");
  await ui.click(screen.getByRole("button", { name: "Parents", exact: true }));
  expect(screen.queryByLabelText("Code de l'établissement")).toBeNull();
  expect(screen.getByRole("heading", { name: "Espace parents" })).toBeTruthy();
  await ui.click(screen.getByRole("button", { name: "Administration plateforme", exact: true }));
  expect(screen.getByRole("heading", { name: "Administration YEM" })).toBeTruthy();
  await ui.click(screen.getByRole("button", { name: "Établissement", exact: true }));
  expect(screen.getByLabelText("Code de l'établissement")).toBeTruthy();
});


it("utilise directement l'image originale et conserve les vrais champs de connexion", async () => {
  setup();
  render(<AuthPanel />);
  const picture = document.querySelector(".yem-original-login__image");
  expect(picture?.getAttribute("src")).toBe(loginArtwork);
  expect(document.querySelector(".yem-original-login--exact")).toBeNull();
  fireEvent.load(picture);
  expect(document.querySelector(".yem-original-login--exact")).toBeTruthy();
  expect(screen.getByLabelText("Code de l'établissement")).toBeTruthy();
  expect(screen.getByRole("button", {name:"Se connecter",exact:true})).toBeTruthy();
  expect(document.querySelector(".yem-login-story")).toBeNull();
});

it("conserve la récupération de mot de passe sans confondre l'image et le formulaire",async()=>{
  setup();
  render(<AuthPanel/>);
  const ui=userEvent.setup();
  await ui.click(screen.getByRole("button",{name:"Mot de passe oublié",exact:true}));
  expect(screen.getByLabelText("Adresse email du compte")).toBeTruthy();
  expect(document.querySelector(".yem-original-login__image")?.getAttribute("src")).toBe(loginArtwork);
});

it("laisse le formulaire utilisable si l’illustration ne se charge pas", async () => {
  setup();
  render(<AuthPanel />);
  fireEvent.error(document.querySelector(".yem-original-login__image"));
  expect(document.querySelector(".yem-original-login__image")).toBeNull();
  expect(document.querySelector(".yem-original-login--exact")).toBeNull();
  expect(await screen.findByRole("heading", { name: "Connexion établissement" })).toBeTruthy();
  expect(screen.getByLabelText("Code de l'établissement")).toBeTruthy();
});
