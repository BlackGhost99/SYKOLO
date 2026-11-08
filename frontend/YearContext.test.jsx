// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import {ClassEnrollments, PaymentTracking, StudentForm} from "./EnrollmentScreens.jsx";
import {FamilyDirectory} from "./SchoolDirectories.jsx";

afterEach(() => {cleanup(); vi.unstubAllGlobals();});

test("la consultation des inscriptions suit l'année choisie depuis l'interface", async () => {
  const requested = [];
  vi.stubGlobal("fetch", vi.fn(async url => {
    requested.push(String(url));
    if (String(url).includes("/overview/classes")) return Response.json({
      year: {id:"annee-1",name:"2025-2026"}, years:[], classes:[], can_manage_academic:false,
    });
    if (String(url).includes("/overview/students")) return Response.json({students:[]});
    return Response.json({});
  }));
  const props = {schoolId:"ecole",onNavigate:vi.fn()};
  const {rerender} = render(<ClassEnrollments {...props} workingYearId="annee-1"/>);
  await waitFor(() => expect(requested).toContain("/api/v1/schools/ecole/overview/classes?year=annee-1"));
  rerender(<ClassEnrollments {...props} workingYearId="annee-2"/>);
  await waitFor(() => expect(requested).toContain("/api/v1/schools/ecole/overview/students?year=annee-2"));
});

test("le suivi des paiements charge la même année pour les élèves et les finances", async () => {
  const requested = [];
  vi.stubGlobal("fetch", vi.fn(async url => {
    requested.push(String(url));
    if (String(url).includes("/overview/students")) return Response.json({
      students:[],classes:[],finance_visible:false,
    });
    if (String(url).includes("/overview/finance")) return Response.json({
      year:{id:"annee-1",name:"2025-2026"},year_by_method:{},year_total:"0",
    });
    return Response.json({});
  }));
  const {rerender} = render(<PaymentTracking schoolId="ecole" workingYearId="annee-1"/>);
  await waitFor(() => expect(requested).toContain("/api/v1/schools/ecole/overview/finance?year=annee-1"));
  rerender(<PaymentTracking schoolId="ecole" workingYearId="annee-2"/>);
  await waitFor(() => {
    expect(requested).toContain("/api/v1/schools/ecole/overview/students?year=annee-2");
    expect(requested).toContain("/api/v1/schools/ecole/overview/finance?year=annee-2");
  });
});

test("l'annuaire des parents n'affiche que les classes de l'année consultée", async () => {
  vi.stubGlobal("fetch", vi.fn(async url => {
    if (String(url).includes("academic/years")) return Response.json({
      years:[{id:"annee-1",name:"2025-2026"},{id:"annee-2",name:"2026-2027"}],
    });
    if (String(url).includes("academic/classes")) return Response.json({
      classes:[{id:"classe-1",name:"CM1 A",year:"annee-1"},
               {id:"classe-2",name:"CM2 A",year:"annee-2"}],
    });
    return Response.json({families:[]});
  }));
  const {rerender} = render(<FamilyDirectory schoolId="ecole" workingYearId="annee-1"/>);
  await waitFor(() => expect(screen.getByRole("option",{name:/CM1 A/})).toBeTruthy());
  expect(screen.queryByRole("option",{name:/CM2 A/})).toBeNull();
  rerender(<FamilyDirectory schoolId="ecole" workingYearId="annee-2"/>);
  await waitFor(() => expect(screen.getByRole("option",{name:/CM2 A/})).toBeTruthy());
  expect(screen.queryByRole("option",{name:/CM1 A/})).toBeNull();
});

test("la création d'élève demande les classes de l'année scolaire de travail", async () => {
  const requested = [];
  vi.stubGlobal("fetch", vi.fn(async url => {
    requested.push(String(url));
    if(String(url).includes("/enrollment-form")) return Response.json({config:null});
    if(String(url).includes("/overview/classes")) return Response.json({years:[],classes:[]});
    return Response.json({});
  }));
  render(<StudentForm schoolId="ecole" workingYearId="annee-2" onNavigate={vi.fn()}/>);
  await waitFor(() => expect(requested).toContain("/api/v1/schools/ecole/overview/classes?year=annee-2"));
});
