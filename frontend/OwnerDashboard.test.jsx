// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OwnerDashboard from "./OwnerDashboard.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});

const dashboard={
  school:{id:"ecole-1",name:"École YEM",type:"college"},
  as_of:"2026-11-11",
  years:[
    {id:"year-2026",name:"2026–2027",status:"current"},
    {id:"year-2025",name:"2025–2026",status:"closed"},
  ],
  year:{id:"year-2026",name:"2026–2027",status:"current"},
  schooling:{active_students:123,active_classes:7,published_reports:88,
    assessments:12,published_assessments:9,absence_marks:16,late_marks:3,
    enrollment_by_cycle:[{cycle:"Collège",classes:7,students:123}],
    capacities_defined:7,total_defined_places:210},
  admissions:{total:14,pending:4,accepted:5,enrolled:4,rejected:1},
  staff:{active:19,with_account:13,without_account:6,assigned_to_classes:11,
    active_appointments:17},
  finance:{currencies:[{currency:"XAF",billed:"1200000.00",
    paid:"800000.00",outstanding:"400000.00",overdue:"100000.00",
    paid_this_month:"150000.00",paid_today:"50000.00",payments_today:2,
    evidence:{explicit_demo:"5000.00",legacy_cash_unverified:"25000.00",other_declared:"770000.00"}}],
    monthly:[{month:"2026-11",currency:"XAF",total:"150000.00"}],
    note:"Montants enregistrés sans annulations"},
  activity:{total_30d:8,
    by_type:[{label:"Fiches élèves créées",total:5}],
    days:[{date:"2026-11-11",total:8}]},
  read_only:true,
};

test("Le propriétaire voit le pilotage et les indicateurs sans données nominatives",async()=>{
  const fetch=vi.fn(async()=>Response.json(dashboard));
  vi.stubGlobal("fetch",fetch);
  const user=userEvent.setup();
  const onNavigate=vi.fn();
  render(<OwnerDashboard schoolId="ecole-1" schoolName="École YEM" onNavigate={onNavigate}/>);
  expect((await screen.findAllByText("123")).length).toBeGreaterThan(0);
  expect(screen.getByText("Collège")).toBeTruthy();
  expect(screen.getByText("400 000 XAF")).toBeTruthy();
  expect(screen.getByText("Lecture seule — chiffres consolidés")).toBeTruthy();
  expect(screen.queryByText("Encaisser")).toBeNull();
  await user.click(screen.getByRole("tab",{name:"Activité"}));
  expect(screen.getByText("Fiches élèves créées")).toBeTruthy();
  expect(screen.queryByText("MineurSecret")).toBeNull();
  expect(fetch).toHaveBeenCalledWith("/api/v1/schools/ecole-1/owner/overview",
    expect.objectContaining({credentials:"same-origin"}));
  await user.click(screen.getByRole("button",{name:"Gérer les comptes et les droits"}));
  expect(onNavigate).toHaveBeenCalledWith("settings","roles");
});

test("Un propriétaire consulte une année historique distincte",async()=>{
  const fetch=vi.fn(async()=>Response.json(dashboard));
  vi.stubGlobal("fetch",fetch);
  const user=userEvent.setup();
  render(<OwnerDashboard schoolId="ecole-1"/>);
  await screen.findByRole("tab",{name:"Finances"});
  await user.selectOptions(screen.getByLabelText("Année scolaire du pilotage"),"year-2025");
  expect(fetch).toHaveBeenCalledWith("/api/v1/schools/ecole-1/owner/overview?year=year-2025",
    expect.objectContaining({credentials:"same-origin"}));
});

test("Le propriétaire distingue les écritures historiques des recettes vérifiées",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>Response.json(dashboard)));
  const user=userEvent.setup();
  render(<OwnerDashboard schoolId="ecole-1"/>);
  await screen.findByRole("tab",{name:"Finances"});
  await user.click(screen.getByRole("tab",{name:"Finances"}));
  expect(screen.getByText("Contrôle des écritures enregistrées")).toBeTruthy();
  expect(screen.getByText("25 000 XAF")).toBeTruthy();
  expect(screen.getByText("5 000 XAF")).toBeTruthy();
  expect(screen.getByText(/pas un état de recettes certifiées/i)).toBeTruthy();
});
