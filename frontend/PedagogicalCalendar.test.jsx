// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PedagogicalCalendar from "./PedagogicalCalendar.jsx";

vi.mock("./AnnualWorkspace.jsx",()=>({default:()=>null}));
afterEach(()=>{cleanup();vi.unstubAllGlobals()});

function makeResponse(value,status=200) {
  return {ok:status>=200&&status<300,headers:{get:()=>"application/json"},
    json:async()=>value};
}

test("Année 1 peut être renommée sans changer son identifiant ou son code",async()=>{
  const year={id:"annee-uuid",name:"Année 1",code:"annee-1",
    start_date:"2026-09-01",end_date:"2027-07-31",revision:3,
    active:true,status:"current"};
  const patches=[];
  const onYearsUpdated=vi.fn();
  vi.stubGlobal("fetch",vi.fn(async(url,opts={})=>{
    const path=String(url);
    if(path.endsWith("/auth/csrf")) return makeResponse({});
    if(path.endsWith("/academic/years/annee-uuid")&&opts.method==="PATCH") {
      const body=JSON.parse(opts.body);patches.push(body);
      Object.assign(year,{name:body.name,revision:year.revision+1});
      return makeResponse({...year});
    }
    if(path.includes("pedagogical-calendar"))return makeResponse({
      events:[],can_manage:true,kinds:[],scopes:[],
    });
    return makeResponse({year:{...year},years:[{...year}],can_edit_year:true,
      periods:[],classes:[],stats:{}});
  }));
  render(<PedagogicalCalendar schoolId="school" workingYearId="annee-uuid"
    onYearsUpdated={onYearsUpdated} onWorkingYearChange={vi.fn()}/>);
  const user=userEvent.setup();
  await user.click(await screen.findByRole("button",{name:"Corriger le nom ou les dates de cette année"}));
  expect(screen.getByLabelText("Nom de l'année scolaire").value).toBe("Année 1");
  await user.clear(screen.getByLabelText("Nom de l'année scolaire"));
  await user.type(screen.getByLabelText("Nom de l'année scolaire"),"2026-2027");
  await user.click(screen.getByRole("button",{name:"Enregistrer cette année"}));
  await waitFor(()=>expect(patches).toHaveLength(1));
  expect(patches[0]).toEqual({revision:3,name:"2026-2027"});
  expect(onYearsUpdated).toHaveBeenCalled();
  await screen.findByRole("option",{name:"2026-2027 · En cours"});
  expect(screen.getByText("annee-1")).toBeTruthy();
});

test("le calendrier propose les trimestres gabonais sans insertion automatique",async()=>{
  const year={id:"annee",name:"2026-2027",code:"2026-2027",
    start_date:"2026-09-01",end_date:"2027-07-31",revision:1,active:true,status:"current"};
  const periods=[];
  const calls=[];
  vi.stubGlobal("fetch",vi.fn(async(url,opts={})=>{
    const path=String(url);
    if(path.endsWith("/auth/csrf"))return makeResponse({});
    if(path.endsWith("/academic/periods")&&opts.method==="POST") {
      const payload=JSON.parse(opts.body);calls.push(payload);
      periods.push({...payload,id:"t1-uuid",revision:1,active:true});
      return makeResponse({...periods[0]},201);
    }
    if(path.includes("pedagogical-calendar"))return makeResponse({
      events:[],can_manage:true,kinds:[],scopes:[],
    });
    return makeResponse({year,years:[year],can_edit_year:true,
      periods:[...periods],classes:[],stats:{}});
  }));
  render(<PedagogicalCalendar schoolId="school" workingYearId="annee"
    onWorkingYearChange={vi.fn()}/>);
  const user=userEvent.setup();
  await user.click(await screen.findByText(/Référence du Gabon 2026–2027/));
  expect(calls).toHaveLength(0);
  await user.click(screen.getByRole("button",{name:/1er trimestre/}));
  expect(screen.getByLabelText("Début").value).toBe("2026-09-07");
  expect(screen.getByLabelText("Fin").value).toBe("2026-11-28");
  await user.click(screen.getByRole("button",{name:"Enregistrer la période"}));
  await waitFor(()=>expect(calls).toHaveLength(1));
  expect(calls[0]).toEqual({
    code:"t1",name:"1er trimestre",start_date:"2026-09-07",
    end_date:"2026-11-28",year:"annee",
  });
});

test("les événements peuvent être renseignés et un calendrier clôturé est en lecture seule",async()=>{
  const year={id:"annee",name:"2026-2027",code:"2026-2027",
    start_date:"2026-09-01",end_date:"2027-07-31",revision:2,active:true,status:"current"};
  let events=[];
  const sent=[];
  vi.stubGlobal("fetch",vi.fn(async(url,opts={})=>{
    const path=String(url);
    if(path.endsWith("/auth/csrf"))return makeResponse({});
    if(path.endsWith("/academic/pedagogical-calendar")&&opts.method==="POST") {
      const body=JSON.parse(opts.body);sent.push(body);
      events=[{...body,id:"event",revision:1,active:true}];
      return makeResponse(events[0],201);
    }
    if(path.includes("pedagogical-calendar"))return makeResponse({
      events:[...events],can_manage:year.status!=="closed",
      kinds:[{code:"rentree",label:"Rentrée"},{code:"autre",label:"Autre"}],
      scopes:[{code:"all",label:"Tous les cycles"}],
    });
    return makeResponse({year:{...year},years:[{...year}],can_edit_year:year.status!=="closed",
      periods:[],classes:[],stats:{}});
  }));
  const {rerender}=render(<PedagogicalCalendar key="current" schoolId="school" workingYearId="annee"
    onWorkingYearChange={vi.fn()}/>);
  const user=userEvent.setup();
  await user.click(await screen.findByRole("button",{name:"Ajouter un événement"}));
  await user.type(screen.getByLabelText("Intitulé"),"Arrêt des notes");
  await user.click(screen.getByRole("button",{name:"Enregistrer l'événement"}));
  await waitFor(()=>expect(sent).toHaveLength(1));
  expect(sent[0].year).toBe("annee");
  expect(sent[0].title).toBe("Arrêt des notes");
  year.status="closed";year.active=false;
  rerender(<PedagogicalCalendar key="closed" schoolId="school" workingYearId="annee"
    onWorkingYearChange={vi.fn()}/>);
  await screen.findByText("Arrêt des notes");
  expect(screen.queryByRole("button",{name:"Ajouter un événement"})).toBeNull();
});
