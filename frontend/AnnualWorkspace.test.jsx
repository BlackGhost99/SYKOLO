// @vitest-environment jsdom
import React,{useState} from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AnnualWorkspace from "./AnnualWorkspace.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals()});

test("une nouvelle année reprend seulement la structure choisie et change le contexte annuel",async()=>{
  const old={id:"year-old",code:"2026-2027",name:"2026-2027",start_date:"2026-09-01",end_date:"2027-07-31",active:true};
  const next={id:"year-new",code:"2027-2028",name:"2027-2028",start_date:"2027-09-01",end_date:"2028-07-31",active:true};
  const years=[old];
  const posts=[];
  vi.stubGlobal("fetch",vi.fn(async(url,options={})=>{
    if(String(url).endsWith("/auth/csrf"))return Response.json({});
    if(String(url).endsWith("/academic/prepare-year")){
      posts.push(JSON.parse(options.body));years.unshift(next);
      return Response.json({year:next,classes_copied:1},{status:201});
    }
    if(String(url).includes("/academic/annual-snapshot")){
      const selected=String(url).includes("year-new")?next:old;
      return Response.json({
        years,year:selected,can_prepare_year:true,
        classes:[{id:"class",name:"6e A",level:"6e",cycle:"Collège",active:true,
                  enrolled:selected.id===old.id?24:0,staff_assignments:0,published_reports:0}],
        periods:[],stats:{classes:1,periods:0,enrollments:selected.id===old.id?24:0,
          staff_assignments:0,assessments:0,published_reports:0},
      });
    }
    return Response.json({});
  }));
  function Harness(){
    const [year,setYear]=useState("");
    return <AnnualWorkspace schoolId="school" yearId={year} onYearChange={setYear}/>;
  }
  const user=userEvent.setup();
  render(<Harness/>);
  await waitFor(()=>expect(screen.getByLabelText("Bilan de l\u0027année").textContent).toContain("24 · Inscriptions"));
  await user.click(screen.getByRole("button",{name:"Préparer une nouvelle année scolaire"}));
  expect(screen.getByLabelText("Code d'année").value).toBe("2027-2028");
  expect(screen.getByLabelText("Début de l'année").value).toBe("2027-09-01");
  expect(screen.getByLabelText("Fin de l'année").value).toBe("2028-07-31");
  expect(screen.getByRole("checkbox",{name:/Reprendre les classes actives/}).checked).toBe(true);
  await user.click(screen.getByRole("button",{name:"Créer l'année scolaire"}));
  await waitFor(()=>expect(screen.getByLabelText("Bilan de l\u0027année").textContent).toContain("0 · Inscriptions"));
  expect(posts).toHaveLength(1);
  expect(posts[0]).toMatchObject({code:"2027-2028",source_year:"year-old",copy_classes:true});
  expect(screen.getByLabelText("Année scolaire de travail").value).toBe("year-new");
});

test("l'activation exige un motif et actualise le statut sans toucher aux archives",async()=>{
  const year={id:"year-draft",code:"2026-2027",name:"2026-2027",
    start_date:"2026-09-01",end_date:"2027-07-31",active:true,
    status:"preparation",revision:1};
  const posts=[];
  vi.stubGlobal("fetch",vi.fn(async(url,options={})=>{
    if(String(url).endsWith("/auth/csrf"))return Response.json({});
    if(String(url).endsWith("/academic/years/year-draft/activate")){
      const body=JSON.parse(options.body);posts.push(body);
      year.status="current";year.revision+=1;
      return Response.json({year:{...year},message:"Année scolaire activée."});
    }
    return Response.json({years:[{...year}],year:{...year},
      can_prepare_year:true,can_activate_year:year.status==="preparation",
      classes:[],periods:[],stats:{classes:0,periods:0,enrollments:0,
        staff_assignments:0,assessments:0,published_reports:0}});
  }));
  const user=userEvent.setup();
  render(<AnnualWorkspace schoolId="school" yearId="year-draft"/>);
  await user.click(await screen.findByRole("button",{name:"Activer cette année scolaire"}));
  await user.type(screen.getByLabelText("Motif de l'activation"),"Rentrée officiellement ouverte");
  await user.click(screen.getByRole("button",{name:"Confirmer l'activation"}));
  await waitFor(()=>expect(posts).toHaveLength(1));
  expect(posts[0]).toEqual({revision:1,reason:"Rentrée officiellement ouverte"});
  expect(await screen.findByText("Année scolaire activée.")).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Activer cette année scolaire"})).toBeNull();
});
