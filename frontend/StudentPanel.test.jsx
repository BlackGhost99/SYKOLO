// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StudentPanel from "./StudentPanel.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("M2.6 : la fiche élève distingue les matricules YEM et établissement", async () => {
  const root = "/api/v1/schools/school-1/";
  const fixtures = {
    students: {students: [{
      id: "student-1", first_name: "Aïcha", last_name: "Fictive",
      matricule_yem: "YEM-0123456789ABCDEF0123456789ABCDEF",
      student_code: "ECOLE-00021",
    }]},
    "academic/years": {years: [{id: "year-1", name: "2026-2027", active: true}]},
    "academic/classes": {classes: []},
    enrollments: {enrollments: []},
  };
  vi.stubGlobal("fetch", vi.fn(async url => {
    const key = String(url).replace(root, "");
    if (!Object.hasOwn(fixtures, key)) throw Error("URL inattendue: " + url);
    return Response.json(fixtures[key]);
  }));

  render(<StudentPanel schoolId="school-1"/>);
  await userEvent.setup().selectOptions(await screen.findByLabelText("Élève sélectionné"), "student-1");

  const card = screen.getByRole("region", {name: "Matricules de l'élève"});
  expect(card.textContent).toContain("YEM-0123456789ABCDEF0123456789ABCDEF");
  expect(card.textContent).toContain("ECOLE-00021");
  expect(card.textContent).toContain("Seule une inscription officielle");
});
