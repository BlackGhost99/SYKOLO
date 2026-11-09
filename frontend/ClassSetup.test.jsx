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
  await user.click(screen.getByText("Options de génération"));
  await user.selectOptions(screen.getByLabelText("Format des noms"), "numbers");
  await user.click(screen.getByRole("button", {name: "Générer les classes"}));
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

test("la maternelle complète les classes standards et duplique une division renommable", async () => {
  const year = {id: "y-presco", name: "2026-2027", active: true};
  const data = {
    year, years: [year], levels: [
      {id: "ps", name: "Petite section (3 ans)", cycle: "Maternelle",
        code: "ps", cycle_code: "prescolaire", active: true},
    ],
    can_manage_classes: true, can_manage_academic: true,
    standard_cycles_available: [{code: "prescolaire", name: "Maternelle / préscolaire", level_count: 4}],
    class_management_cycles: ["prescolaire"],
    class_level_options: {},
    classes: [{id: "class-a", name: "Petite section A", code: "ps-a",
      revision: 1, active: true, enrolled: 2, capacity: 25,
      level: {id: "ps", name: "Petite section (3 ans)", cycle_code: "prescolaire"}}],
  };
  const fetchMock = vi.fn(async url => ({
    ok: true, headers: {get: () => "application/json"},
    json: async () => url.endsWith("/standard-classes")
      ? {created: 3, classes: [{name: "Crèche A"}, {name: "Moyenne section A"}, {name: "Grande section A"}]}
      : url.endsWith("/clone") ? {id: "class-b", name: "Petite section Papillons"} : data,
  }));
  vi.stubGlobal("fetch", fetchMock);
  render(<ClassSetup schoolId="school"/>);
  const user = userEvent.setup();
  await screen.findByText("Petite section A");
  await user.click(screen.getByRole("button", {name: "Compléter les classes standards"}));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/standard-classes"),
    expect.objectContaining({body: JSON.stringify({year: "y-presco"})}),
  ));
  await user.click(await screen.findByRole("button", {name: "Dupliquer Petite section A"}));
  const newName = await screen.findByLabelText(/Nom de la nouvelle classe/);
  expect(newName.value).toBe("Petite section B");
  await user.clear(newName);
  await user.type(newName, "Petite section Papillons");
  await user.click(screen.getByRole("button", {name: "Créer la copie"}));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("classes/class-a/clone"),
    expect.objectContaining({body: JSON.stringify({name: "Petite section Papillons"})}),
  ));
});

test("un complexe scolaire présente tous ses cycles avant de compléter les classes", async () => {
  const year = {id: "annee", name: "2026-2027", active: true};
  const data = {
    year, years: [year], levels: [], classes: [], can_manage_classes: true,
    standard_cycles_available: [
      {code: "primaire", name: "Primaire", level_count: 5},
      {code: "college", name: "Collège", level_count: 4},
      {code: "lycee_general", name: "Lycée général", level_count: 3},
    ],
    class_management_cycles: null, class_level_options: {},
  };
  const fetchMock = vi.fn(async url => ({
    ok: true, headers: {get: () => "application/json"},
    json: async () => url.endsWith("/standard-classes")
      ? {created: 12, classes: []} : data,
  }));
  vi.stubGlobal("fetch", fetchMock);
  render(<ClassSetup schoolId="school"/>);
  const user = userEvent.setup();
  expect(await screen.findByText(/12 niveaux disponibles/)).toBeTruthy();
  expect(screen.getByText(/Primaire · Collège · Lycée général/)).toBeTruthy();
  await user.click(screen.getByRole("button", {name: "Compléter les classes standards"}));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("schools/school/academic/standard-classes"),
    expect.objectContaining({body: JSON.stringify({year: "annee"})}),
  ));
});

test("un cycle sans délégation ne propose pas la génération des classes standards", async () => {
  const year = {id: "annee", name: "2026-2027", active: true};
  const data = {
    year, years: [year], levels: [], classes: [], can_manage_classes: false,
    standard_cycles_available: [], class_management_cycles: [],
    class_level_options: {}, can_manage_academic: false,
  };
  vi.stubGlobal("fetch", vi.fn(async () => ({
    ok: true, headers: {get: () => "application/json"},
    json: async () => data,
  })));
  render(<ClassSetup schoolId="school"/>);
  expect(await screen.findByText("Aucune classe pour cette année.")).toBeTruthy();
  expect(screen.queryByRole("button", {name: "Compléter les classes standards"})).toBeNull();
});

test("le lycée choisit la série S et renomme sa division SU avant ouverture", async () => {
  const year = {id:"year", name:"2026-2027", active:true};
  const data = {
    year, years:[year], levels:[], classes:[], can_manage_classes:true,
    can_manage_academic:true, standard_cycles_available:[],
    secondary_series_options:[{
      level:"sec", level_name:"Seconde", level_code:"seconde", cycle:"lycee_general",
      series:[{code:"LE",name:"Littéraire"}, {code:"S",name:"Scientifique (S)"}],
    }],
    archived_reusable:[], class_management_cycles:null, class_level_options:{},
  };
  const fetchMock = vi.fn(async url => ({
    ok:true, headers:{get:()=>"application/json"},
    json:async () => url.endsWith("series-classes")
      ? {series:{code:"s"}, classes:[{name:"Seconde S1"},{name:"Seconde SU"}]} : data,
  }));
  vi.stubGlobal("fetch",fetchMock);
  render(<ClassSetup schoolId="school"/>);
  const user = userEvent.setup();
  await screen.findByText("Ouvrir les séries du lycée");
  await user.selectOptions(screen.getByLabelText(/Niveau du lycée/),"sec");
  await user.type(screen.getByLabelText(/Série ou spécialité/),"S");
  const count = screen.getByLabelText("Nombre de divisions");
  await user.clear(count);
  await user.type(count,"2");
  await user.click(screen.getByRole("button",{name:"Préparer les divisions"}));
  expect(screen.getByLabelText(/Nom de division 1/).value).toBe("Seconde S1");
  const second = screen.getByLabelText(/Nom de division 2/);
  await user.clear(second);
  await user.type(second,"Seconde SU");
  await user.click(screen.getByRole("button",{name:"Ouvrir 2 classe(s)"}));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("academic/series-classes"),
    expect.objectContaining({
      body:JSON.stringify({
        year:"year",level:"sec",series:"S",
        names:["Seconde S1","Seconde SU"],capacity:null,
      }),
    }),
  ));
});

test("l'archive retire la classe active et une ancienne archive peut être reprise", async () => {
  const year = {id:"next", name:"2027-2028", active:true};
  const data = {
    year,years:[year],levels:[],classes:[{
      id:"old",name:"Seconde A",active:true,revision:1,capacity:null,enrolled:0,
      level:{id:"seconde",name:"Seconde",cycle_code:"lycee_general"},
    }],
    can_manage_classes:true, can_manage_academic:true,
    standard_cycles_available:[], secondary_series_options:[],
    archived_reusable:[{id:"prior",name:"Première ACC1",year:"2026-2027",cycle:"lycee_technique"}],
    class_management_cycles:null,class_level_options:{},
  };
  const fetchMock = vi.fn(async (url,opts) => ({
    ok:true,headers:{get:()=>"application/json"},
    json:async () => url.endsWith("carry-forward") ? {name:"Première ACC1"} :
      opts?.method==="PATCH" ? {name:"Seconde A",active:false,revision:2} : data,
  }));
  vi.stubGlobal("fetch",fetchMock);
  vi.spyOn(window,"confirm").mockReturnValue(true);
  render(<ClassSetup schoolId="school"/>);
  const user = userEvent.setup();
  await screen.findByText("Seconde A");
  await user.click(screen.getByRole("button",{name:"Archiver Seconde A"}));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("academic/classes/old"),
    expect.objectContaining({
      method:"PATCH",body:JSON.stringify({revision:1,active:false}),
    }),
  ));
  await user.selectOptions(screen.getByLabelText(/Classe archivée à reprendre/),"prior");
  await user.click(screen.getByRole("button",{name:"Réouvrir dans cette année"}));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("academic/classes/prior/carry-forward"),
    expect.objectContaining({body:JSON.stringify({year:"next"})}),
  ));
  vi.restoreAllMocks();
});
