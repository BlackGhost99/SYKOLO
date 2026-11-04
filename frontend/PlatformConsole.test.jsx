// @vitest-environment jsdom
import React from "react";
import {afterEach,beforeEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,within,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PlatformConsole from "./PlatformConsole.jsx";

vi.mock("./SchoolDashboard.jsx",()=>({default:()=> <div data-testid="school-workspace">Établissement indépendant</div>}));
const schoolId="11111111-1111-1111-1111-111111111111";
const memberId="22222222-2222-2222-2222-222222222222";
const roleId="33333333-3333-3333-3333-333333333333";
const school={id:schoolId,name:"Lycée Test",organization:"Groupe Test",organization_id:"44444444-4444-4444-4444-444444444444",members_count:1,students_count:2,active:true};
const detail={
  school:{id:schoolId,name:"Lycée Test",organization:"Groupe Test",active:true},
  members_count:1,students_count:2,
  roles:[{id:roleId,label:"Direction",code:"direction"}],
  members:[{id:memberId,username:"direction1",name:"Directrice Test",email:"test@example.ga",active:true,membership_active:true,role_id:roleId,role:"Direction",role_code:"direction",is_platform_admin:false}],
  policy:{max_users:10,max_students:50,plan_name:"Essai",revision:1},
  events:[],
};
const dashboard={
  schools:[school],schools_total:1,schools_active:1,schools_inactive:0,
  organizations:1,users_active:1,filtered_total:1,page:1,pages:1,per_page:5,
  recent_events:[],organization_options:[{id:school.organization_id,name:"Groupe Test",schools_count:1}],
};
const json=data=>({ok:true,headers:{get:()=>"application/json"},json:async()=>data});
beforeEach(()=>{
  vi.stubGlobal("confirm",()=>true);
  vi.stubGlobal("scrollTo",()=>{});
  vi.stubGlobal("fetch",vi.fn(async (url, options)=>{
    const value=String(url);
    if(value.includes("/platform/dashboard")) {
      const params=new URL(value,"https://yem.local").searchParams;
      if(params.get("q")==="absente") return json({...dashboard,schools:[],filtered_total:0});
      return json(dashboard);
    }
    if(value.includes("/platform/audit"))return json({events:[]});
    if(value.includes("/platform/organizations"))return json({organizations:[{id:school.organization_id,name:"Groupe Test",schools_count:1}]});
    if(value.includes("/platform/schools/")&&value.endsWith("/detail"))return json(detail);
    if(value.includes("/platform/schools/")&&value.endsWith("/action"))return json(detail);
    if(value.includes("/platform/schools/")&&value.endsWith("/admin-access"))return json({access:"direction"});
    if(value.includes("/platform/schools/")&&value.includes("/members/"))return json(detail);
    return json({});
  }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

function mount(mfaEnabled=true) {return render(<PlatformConsole user={{username:"superadmin"}} mfaEnabled={mfaEnabled} accountView={<div>Formulaire MFA</div>} onLogout={()=>{}}/>);}

test("affiche uniquement les vraies informations de la console super-administrateur",async()=>{
  mount();
  expect(await screen.findByText("Lycée Test")).toBeTruthy();
  expect(screen.getByRole("heading",{name:"Console d'administration YEM"})).toBeTruthy();
  expect(screen.getByText("Structures propriétaires")).toBeTruthy();
  expect(screen.getByText("Comptes des écoles actives")).toBeTruthy();
  expect(screen.queryByTestId("school-workspace")).toBeNull();
  expect(document.querySelector(".ya-brand img")).toBeTruthy();
});

test("filtres, recherche et pagination pilotent réellement le répertoire",async()=>{
  mount();
  await screen.findByText("Lycée Test");
  const u=userEvent.setup();
  await u.type(screen.getByRole("searchbox",{name:"Rechercher un établissement"}),"absente");
  await waitFor(()=>expect(screen.getByText(/Aucun établissement ne correspond/)).toBeTruthy());
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("q=absente"),expect.anything());
});

test("l'ouverture d'un établissement est explicite et séparée de la plateforme",async()=>{
  mount();
  await screen.findByText("Lycée Test");
  const u=userEvent.setup();
  await u.click(screen.getByRole("button",{name:/Ouvrir l'école/}));
  await screen.findByTestId("school-workspace");
  expect(document.querySelector(".ya-root")).toBeNull();
  await u.click(screen.getByRole("button",{name:/Retour à la console super-admin/}));
  expect(screen.queryByTestId("school-workspace")).toBeNull();
});

test("un changement de statut exige un motif",async()=>{
  mount();
  await screen.findByText("Lycée Test");
  const u=userEvent.setup();
  await u.click(screen.getByRole("button",{name:"Suspendre"}));
  const dialog=screen.getByRole("dialog");
  const confirm=within(dialog).getByRole("button",{name:"Confirmer"});
  expect(confirm.disabled).toBe(true);
  await u.type(within(dialog).getByRole("textbox",{name:"Motif obligatoire"}),"Établissement temporairement fermé");
  expect(confirm.disabled).toBe(false);
  await u.click(confirm);
  await waitFor(()=>expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/action"),expect.objectContaining({method:"POST"})));
});

test("le MFA bloque totalement la console",()=>{
  mount(false);
  expect(screen.getByText(/Activez la double authentification/)).toBeTruthy();
  expect(screen.getByText("Formulaire MFA")).toBeTruthy();
  expect(screen.queryByRole("heading",{name:"Console d'administration YEM"})).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
});
