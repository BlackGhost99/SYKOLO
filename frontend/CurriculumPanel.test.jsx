// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CurriculumPanel from "./CurriculumPanel.jsx";

afterEach(() => {cleanup(); vi.unstubAllGlobals();});

test("adds a list to the chosen class without asking for codes or a separate year", async () => {
  const api = vi.fn(async url => {
    const path = url.split("/").slice(5).join("/");
    const data = {
      subjects: {subjects: [], can_manage: true},
      courses: {courses: []},
      "academic/years": {years: [{id: "year", name: "2026-2027", active: true}]},
      "academic/classes": {classes: [{id: "6a", year: "year", name: "6e A", active: true}]},
      "courses/generate": {created: ["Français", "Anglais"], existing: [], archived: []},
    }[path] || {};
    return {ok: true, headers: {get: () => "application/json"}, json: async () => data};
  });
  vi.stubGlobal("fetch", api);
  render(<CurriculumPanel schoolId="school"/>);
  const user = userEvent.setup();
  const input = await screen.findByLabelText("Matières à ajouter");
  await user.type(input, "Français{enter}Anglais");
  await user.click(screen.getByRole("button", {name: "Ajouter les matières"}));
  await waitFor(() => expect(api).toHaveBeenCalledWith(
    "/api/v1/schools/school/courses/generate",
    expect.objectContaining({body: JSON.stringify({classroom: "6a", names: ["Français", "Anglais"]})}),
  ));
  expect((await screen.findByRole("status")).textContent).toContain("2 matière(s) ajoutée(s)");
});
