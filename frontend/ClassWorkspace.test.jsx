// @vitest-environment jsdom
import React from "react";
import {cleanup, render, screen, within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, test, vi} from "vitest";
import SchoolDashboard from "./SchoolDashboard.jsx";

afterEach(() => {
  cleanup();
  delete HTMLDialogElement.prototype.showModal;
  delete HTMLDialogElement.prototype.close;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("l'espace établissement permet de créer une classe et de consulter ses élèves", async () => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  const school = {id: "school", name: "Collège de test"};
  const year = {id: "year", name: "2026-2027", active: true};
  const level = {id: "level", name: "Sixième", cycle: "Collège", cycle_code: "college", code: "6e", active: true};
  const classes = [{id: "6a", name: "6e A", enrolled: 1, capacity: 30, active: true, level}];
  const prefix = "/api/v1/schools/school";
  const fetchMock = vi.fn(async (url, options) => {
    if (url === prefix + "/academic/quick-classes" && options.method === "POST") {
      classes.push({id: "6b", name: "6e B", enrolled: 0, capacity: 35, active: true, level});
      return Response.json({classes: [classes[1]]}, {status: 201});
    }
    const data = {
      "/api/v1/schools": {schools: [school]},
      [prefix + "/my-access"]: {school, permissions: ["school.academic.read", "school.students.read"]},
      [prefix + "/overview/classes"]: {year, years: [year], classes, levels: [level], can_manage_classes: true},
      [prefix + "/classes/6a/students"]: {students: [{id: "ada", first_name: "Ada", last_name: "TEST", student_code: "001"}]},
      [prefix + "/classes/6b/students"]: {students: []},
    };
    return Response.json(data[url] || {});
  });
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  render(<SchoolDashboard user={{username: "direction"}}/>);
  const nav = await screen.findByRole("navigation", {name: "Navigation principale"});
  await user.click(await within(nav).findByRole("button", {name: "Classes", exact: true}));
  expect(screen.getByRole("heading", {name: "Classes et niveaux"})).toBeTruthy();
  const existing = await screen.findByRole("button", {name: /6e A, 1 élève \/ 30 places/});
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/classes/6a/students"))).toBe(false);
  await user.click(existing);
  const roster = screen.getByRole("dialog", {name: "Élèves de 6e A"});
  expect(await within(roster).findByRole("button", {name: "TEST Ada"})).toBeTruthy();
  await user.click(within(roster).getByRole("button", {name: "Fermer"}));

  await user.click(screen.getByRole("button", {name: "Créer une classe"}));
  const form = within(screen.getByRole("dialog", {name: "Créer une classe"}));
  expect(form.getByLabelText(/Niveau/).value).toBe("level");
  await user.type(form.getByLabelText(/Nom de la classe/), "6e B");
  await user.type(form.getByLabelText(/Capacité maximale/), "35");
  await user.click(form.getByRole("button", {name: "Enregistrer"}));
  expect(fetchMock).toHaveBeenCalledWith(prefix + "/academic/quick-classes", expect.objectContaining({
    method: "POST", body: JSON.stringify({year: "year", names: ["6e B"], capacity: 35, level: "level"}),
  }));
  await user.click(await screen.findByRole("button", {name: /6e B, 0 élève \/ 35 places/}));
  expect(await screen.findByText("Aucun élève inscrit dans cette classe.")).toBeTruthy();
  await user.click(screen.getByRole("button", {name: "Fermer"}));

  await user.click(within(nav).getByRole("button", {name: "Paramètres"}));
  await user.click(screen.getByRole("button", {name: /Classes de l’établissement/}));
  expect(screen.getByRole("button", {name: "Classes", exact: true, pressed: true})).toBeTruthy();
  expect(screen.getByRole("button", {name: "Structure académique avancée", pressed: false})).toBeTruthy();
});

test.each([true,false])("le raccourci des évaluations respecte les droits et le sous-onglet (accès : %s)", async canReadSettings => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  const school = {id:"school",name:"Établissement test"};
  const root = "/api/v1/schools/school/";
  const permissions = ["school.assessments.read","school.deliberations.read"];
  if (canReadSettings) permissions.push("school.settings.read");
  vi.stubGlobal("fetch", vi.fn(async url => Response.json({
    "/api/v1/schools":{schools:[school]},
    [root+"my-access"]:{school,role:"etudes-personnalise",permissions},
    [root+"organization/my-appointments"]:{appointments:[]},
    [root+"academic/classes"]:{classes:[]},
    [root+"academic/years"]:{years:[]},
    [root+"academic/periods"]:{periods:[]},
    [root+"courses"]:{courses:[]},
    [root+"subjects"]:{subjects:[]},
    [root+"councils"]:{councils:[]},
    [root+"settings?"]:{effective:{}},
  }[url] || {})));
  const user = userEvent.setup();
  render(<SchoolDashboard user={{username:"etudes"}}/>);
  const nav = await screen.findByRole("navigation", {name:"Navigation principale"});
  await user.click(await within(nav).findByRole("button", {name:"Évaluations et notes"}));
  const council = {name:"Conseils et décisions",exact:true};
  await user.click(screen.getByRole("tab", council));
  const shortcut = screen.queryByRole("button", {name:"Paramètres avancés"});
  if (!canReadSettings) {
    expect(shortcut).toBeNull();
    return;
  }
  await user.click(shortcut);
  expect(screen.getByRole("button", {name:"Décisions du conseil",pressed:true})).toBeTruthy();
  await user.click(screen.getByRole("button", {name:"Retour au module"}));
  expect(screen.getByRole("tab", {...council,selected:true})).toBeTruthy();
});
