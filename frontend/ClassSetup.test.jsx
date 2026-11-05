// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {ClassSetup} from "./EnrollmentScreens.jsx";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("a batch proposes available numbers and submits the edited names", async () => {
  const year = {id: "year", name: "2026-2027", active: true};
  const data = {
    year, years: [year], levels: [], can_manage_classes: true,
    class_management_cycles: ["college"],
    class_level_options: {
      "college:6e": {cycle: "college", cycle_name: "Collège", code: "6e", name: "6e"},
      "lycee_general:seconde": {cycle: "lycee_general", cycle_name: "Lycée", code: "seconde", name: "Seconde"},
    },
    classes: [{id: "existing", name: "6e 1", active: true, enrolled: 0,
      level: {name: "6e", cycle_code: "college"}}],
  };
  const fetchMock = vi.fn(async (url) => ({
    ok: true, headers: {get: () => "application/json"},
    json: async () => url.endsWith("quick-classes")
      ? {level: {id: "level"}, classes: [{name: "6e 2"}, {name: "6e 13"}]}
      : data,
  }));
  vi.stubGlobal("fetch", fetchMock);
  render(<ClassSetup schoolId="school"/>);
  const user = userEvent.setup();
  const level = await screen.findByLabelText(/Niveau/);
  expect(screen.queryByRole("option", {name: /Seconde/})).toBeNull();
  await user.selectOptions(level, "college:6e");
  const quantity = screen.getByLabelText("Nombre de classes");
  await user.clear(quantity);
  await user.type(quantity, "2");
  await user.selectOptions(screen.getByLabelText("Format des noms"), "numbers");
  await user.click(screen.getByRole("button", {name: "Générer les noms"}));
  expect(screen.getByLabelText(/Nom de la classe 1/).value).toBe("6e 2");
  const second = screen.getByLabelText(/Nom de la classe 2/);
  await user.clear(second);
  await user.type(second, "6e 13");
  await user.click(screen.getByRole("button", {name: "Créer les 2 classes"}));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("quick-classes"),
    expect.objectContaining({
      body: JSON.stringify({year: "year", names: ["6e 2", "6e 13"], capacity: null, preset: "college:6e"}),
    }),
  ));
});
