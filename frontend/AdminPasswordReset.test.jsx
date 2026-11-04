// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor,within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdminPasswordReset from "./AdminPasswordReset.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

test("demande une vérification d'identité, un motif et la réauthentification du super-admin",async()=>{
  const calls=[];
  vi.stubGlobal("fetch",vi.fn(async(url,opts)=>{
    calls.push([url,opts]);
    if(String(url).endsWith("/auth/csrf"))return {ok:true};
    return {
      ok:true,
      json:async()=>({
        issued:true,username:"directrice",school:"Lycée test",
        reset_url:"https://yem.example.test/#/reset?uid=abc&token=private",
        expires_in_minutes:30,
      }),
    };
  }));
  const onClose=vi.fn();
  const u=userEvent.setup();
  render(<AdminPasswordReset schoolId="a" member={{id:"b",name:"Directrice Test",username:"directrice"}} onClose={onClose}/>);
  const modal=screen.getByRole("dialog",{name:"Récupération du mot de passe"});
  const submit=within(modal).getByRole("button",{name:"Générer le lien sécurisé"});
  expect(submit.disabled).toBe(true);
  expect(screen.queryByText(/token=private/)).toBeNull();
  await u.type(within(modal).getByRole("textbox",{name:/Motif obligatoire/}),"Identité contrôlée en personne");
  await u.type(within(modal).getByLabelText(/Confirmer votre mot de passe/),"Mot de passe privé");
  await u.click(within(modal).getByRole("checkbox",{name:/J'ai vérifié l'identité/}));
  expect(submit.disabled).toBe(false);
  await u.click(submit);
  expect(await screen.findByText(/Lien généré et opération auditée/)).toBeTruthy();
  expect(calls.some(([url,options])=>String(url).endsWith("/password/admin-reset")&&options.method==="POST")).toBe(true);
  const adminCall=calls.find(([url])=>String(url).endsWith("/password/admin-reset"));
  const body=JSON.parse(adminCall[1].body);
  expect(body).toMatchObject({school_id:"a",member_id:"b",reason:"Identité contrôlée en personne"});
  expect(body.current_password).toBe("Mot de passe privé");
  await u.click(screen.getByRole("button",{name:"Terminer"}));
  expect(onClose).toHaveBeenCalledOnce();
});

test("affiche une erreur sans révéler de lien si le serveur refuse l'opération",async()=>{
  vi.stubGlobal("fetch",vi.fn(async url=>String(url).endsWith("/auth/csrf")?{ok:true}:{
    ok:false,json:async()=>({error:"Confirmation du super-administrateur incorrecte."})
  }));
  const u=userEvent.setup();
  render(<AdminPasswordReset schoolId="a" member={{id:"b",username:"directrice"}} onClose={()=>{}}/>);
  await u.type(screen.getByRole("textbox",{name:/Motif obligatoire/}),"Une demande identifiée");
  await u.type(screen.getByLabelText(/Confirmer votre mot de passe/),"faux");
  await u.click(screen.getByRole("checkbox",{name:/J'ai vérifié l'identité/}));
  await u.click(screen.getByRole("button",{name:"Générer le lien sécurisé"}));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent","Confirmation du super-administrateur incorrecte.");
  expect(screen.queryByText(/Lien généré et opération auditée/)).toBeNull();
});


test("la récupération des parents demande une identité exacte avant de transmettre un lien",async()=>{
  const calls=[];
  vi.stubGlobal("fetch",vi.fn(async(url,options)=>{
    calls.push([url,options]);
    if(String(url).endsWith("/auth/csrf"))return {ok:true};
    return {ok:true,json:async()=>({
      issued:true,username:"parent_ga",expires_in_minutes:30,
      reset_url:"https://yem.example.test/#/reset?uid=parent&token=private",
    })};
  }));
  const u=userEvent.setup();
  render(<AdminPasswordReset parent schoolId="" member={{mode:"parent"}} onClose={()=>{}}/>);
  await u.type(screen.getByRole("textbox",{name:/Identifiant exact du compte parent/}),"parent_ga");
  await u.type(screen.getByRole("textbox",{name:/Adresse e-mail exacte du compte parent/}),"parent_ga@example.test");
  await u.type(screen.getByRole("textbox",{name:/Motif obligatoire/}),"Pièce de vérification présentée");
  await u.type(screen.getByLabelText(/Confirmer votre mot de passe/),"Super mot de passe");
  await u.click(screen.getByRole("checkbox",{name:/J'ai vérifié l'identité/}));
  await u.click(screen.getByRole("button",{name:"Générer le lien sécurisé"}));
  expect(await screen.findByText(/Lien généré et opération auditée/)).toBeTruthy();
  const call=calls.find(([url])=>String(url).endsWith("/password/admin-parent-reset"));
  expect(call).toBeTruthy();
  const body=JSON.parse(call[1].body);
  expect(body).toMatchObject({username:"parent_ga",email:"parent_ga@example.test"});
});
