// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SchoolBrandingSettings from "./SchoolBrandingSettings.jsx";
import {BrandContext,PageHeader,YemLogo} from "./yem-ui.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

test("la bannière d'une école ne remplace jamais le logo officiel de YEM",()=>{
  render(<BrandContext.Provider value={{name:"Lycée Alpha",city:"Libreville",
    banner:"/api/v1/schools/a/branding/banner?v=2",logo:"/api/v1/schools/a/branding/logo?v=2"}}>
    <YemLogo/>
    <PageHeader title="Encaissements" subtitle="Caisse de l'établissement"/>
  </BrandContext.Provider>);
  expect(screen.getByRole("img",{name:/YEM – Gestion scolaire/})).toBeTruthy();
  expect(screen.getByText("Lycée Alpha")).toBeTruthy();
  expect(screen.getByText("Libreville")).toBeTruthy();
  expect(screen.getByAltText("Logo de l'établissement").getAttribute("src")).toContain("/branding/logo");
  expect(screen.getByRole("heading",{name:"Encaissements"})).toBeTruthy();
});

test("un économe voit l'identité sans pouvoir changer les images",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>Response.json({
    school_id:"a",name:"Lycée Alpha",city:"Libreville",tagline:"",revision:1,
    logo_url:"/api/v1/schools/a/branding/logo?v=1",banner_url:null,
  })));
  render(<SchoolBrandingSettings schoolId="a" canEdit={false}/>);
  expect(await screen.findByText("Lycée Alpha")).toBeTruthy();
  expect(screen.getByDisplayValue("Libreville").disabled).toBe(true);
  expect(screen.queryByLabelText("Choisir le logo de l'établissement")).toBeNull();
  expect(screen.queryByLabelText("Choisir la bannière de l'établissement")).toBeNull();
});

test("le directeur met à jour la ville avec contrôle de révision et diffusion",async()=>{
  const updated=vi.fn();
  const fetchMock=vi.fn(async(url,options={})=>{
    if(url==="/api/v1/auth/csrf")return Response.json({});
    if(options.method==="POST"){
      const payload=JSON.parse(options.body);
      return Response.json({school_id:"a",name:"Lycée Alpha",city:payload.city,
        tagline:payload.tagline,revision:2,logo_url:null,banner_url:null});
    }
    return Response.json({school_id:"a",name:"Lycée Alpha",city:"",tagline:"",
      revision:1,logo_url:null,banner_url:null});
  });
  vi.stubGlobal("fetch",fetchMock);
  render(<SchoolBrandingSettings schoolId="a" canEdit onUpdated={updated}/>);
  const city=await screen.findByRole("textbox",{name:/Ville/});
  const user=userEvent.setup();
  await user.type(city,"Libreville");
  await user.click(screen.getByRole("button",{name:"Enregistrer les informations"}));
  await waitFor(()=>expect(updated).toHaveBeenCalledWith(expect.objectContaining({
    city:"Libreville",revision:2,
  })));
  const req=fetchMock.mock.calls.find(([url,options])=>url.endsWith("/branding")&&options?.method==="POST");
  expect(JSON.parse(req[1].body)).toEqual({revision:1,city:"Libreville",tagline:""});
  expect(screen.getByDisplayValue("Lycée Alpha").readOnly).toBe(true);
});
