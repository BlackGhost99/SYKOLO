// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, render, screen, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdmissionsPanel from "./AdmissionsPanel.jsx";

vi.mock("./AdmissionRoutesPanel.jsx", () => ({
  AdmissionPolicyEditor: () => null,
  AdmissionProofPanel: () => null,
  AdmissionDecisionReadiness: () => null,
  ROUTES: {direct: "Inscription directe", concours: "Concours", orientation: "Orientation"},
}));
vi.mock("./AdmissionFinance.jsx", () => ({
  FinancePolicyEditor: () => null,
  GovernmentScholarshipPanel: () => null,
}));
vi.mock("./AdmissionCashDesk.jsx", () => ({
  default: () => null,
  librevilleToday: () => "2026-11-12",
}));
vi.mock("./ParentDiscovery.jsx", () => ({SchoolCatalogSettings: () => null}));
vi.mock("./SchoolPaymentSetup.jsx", () => ({default: () => null}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderAdmissions({canPrepare=false, canDecide=false, canCreate=true, canEnroll=false, initialStatus="submitted", financeBlocker=null}={}) {
  let application = {
    id: "app-1", revision: 1, first_name: "Aïcha", last_name: "Fictive",
    status: initialStatus, route: "direct", year: "year-1",
    classroom: "class-1", source: "guichet", guardian_name: "Parent fictif",
    submitted_at: "2026-11-12T09:00:00Z", decision_reason: "",
    finance: {blocker: financeBlocker}, acceptance_blocker: null,
  };
  const base = "/api/v1/schools/school-1/";
  const fetchMock = vi.fn(async (url, options={}) => {
    if (url === "/api/v1/auth/csrf") return Response.json({});
    if (url === base + "admissions" && options.method === "POST") {
      return Response.json({error: "Création hors de ce test"}, {status: 422});
    }
    if (url === base + "admissions/app-1/decide" && options.method === "POST") {
      const data = JSON.parse(options.body);
      application = {...application, status: data.status, revision: application.revision + 1};
      return Response.json(application);
    }
    if (url === base + "admissions/app-1/convert" && options.method === "POST") {
      application = {...application, status: "enrolled", revision: application.revision + 1,
        enrollment: "enrollment-1",
        official_enrollment: {
          id: "enrollment-1", student: "student-1",
          matricule_yem: "YEM-0123456789ABCDEF0123456789ABCDEF",
          student_code: "ECOLE-00021",
          year: "year-1", classroom: "class-1",
          enrolled_on: "2026-11-12", status: "inscrit",
        },
      };
      return Response.json(application, {status: 201});
    }
    if (url === base + "admissions") return Response.json({applications: [application]});
    if (url === base + "academic/years") return Response.json({years: [
      {id: "year-1", name: "2026–2027", active: true},
    ]});
    if (url === base + "academic/classes") return Response.json({classes: [
      {id: "class-1", name: "Sixième A", year: "year-1", level: "level-1", active: true},
    ]});
    if (url === base + "students") return Response.json({students: []});
    if (url.endsWith("/capacity/class-1")) return Response.json({
      occupied: 0, accepted_pending: 0, remaining: 10,
    });
    throw new Error("Unexpected API request: " + url);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<AdmissionsPanel
    schoolId="school-1" canPrepare={canPrepare} canDecide={canDecide}
    canCreate={canCreate} canEnroll={canEnroll} canReceive={false}
  />);
  return fetchMock;
}

async function selectFile() {
  const user = userEvent.setup();
  await user.selectOptions(await screen.findByLabelText("Candidature"), "app-1");
  expect(await screen.findByText("Fictive Aïcha")).toBeTruthy();
  return user;
}

test("le secrétariat ouvre l'étude sans voir accepter ou refuser", async () => {
  const fetchMock = renderAdmissions({canPrepare: true, canDecide: false});
  const user = await selectFile();
  expect(screen.getByText(/La direction conserve seule la décision/)).toBeTruthy();
  expect(screen.queryByRole("button", {name:/Accepter la candidature/})).toBeNull();
  expect(screen.queryByRole("button", {name:/Refuser la candidature/})).toBeNull();

  await user.click(screen.getByRole("button", {name:"Passer en étude (secrétariat)"}));
  await waitFor(() => expect(fetchMock.mock.calls.some(([url, options]) =>
    url.endsWith("/app-1/decide") && options?.method === "POST" &&
    JSON.parse(options.body).status === "review"
  )).toBe(true));
  expect(await screen.findByRole("option", {name:/En étude/})).toBeTruthy();
  expect(screen.queryByRole("button", {name:"Passer en étude (secrétariat)"})).toBeNull();
});

test("la direction conserve seule les actions d'admission ou de refus", async () => {
  renderAdmissions({canPrepare: false, canDecide: true, canCreate: false});
  await selectFile();
  expect(screen.getByRole("button", {name:"Accepter la candidature (direction)"})).toBeTruthy();
  expect(screen.getByRole("button", {name:"Refuser la candidature (direction)"})).toBeTruthy();
  expect(screen.queryByRole("button", {name:"Passer en étude (secrétariat)"})).toBeNull();
});

test("un lecteur des admissions ne voit aucune action d'étude ou décision", async () => {
  renderAdmissions({canPrepare: false, canDecide: false, canCreate: false});
  await selectFile();
  expect(screen.queryByRole("button", {name:"Passer en étude (secrétariat)"})).toBeNull();
  expect(screen.queryByRole("button", {name:/Accepter la candidature/})).toBeNull();
  expect(screen.queryByRole("button", {name:/Refuser la candidature/})).toBeNull();
});

test("M2.6 : la confirmation montre les deux matricules officiels sans les anticiper", async () => {
  const fetchMock = renderAdmissions({initialStatus: "accepted", canEnroll: true, canCreate: false});
  const user = await selectFile();
  expect(screen.queryByText("ECOLE-00021")).toBeNull();
  await user.click(screen.getByRole("button", {name: "Confirmer l’inscription définitive"}));
  expect(await screen.findByText("ECOLE-00021")).toBeTruthy();
  expect(screen.getByText("YEM-0123456789ABCDEF0123456789ABCDEF")).toBeTruthy();
  expect(screen.getByRole("region", {name: "Inscription définitive confirmée"})).toBeTruthy();
  expect(screen.queryByRole("button", {name: "Confirmer l’inscription définitive"})).toBeNull();
  expect(fetchMock.mock.calls.filter(([url, options]) =>
    url.endsWith("/app-1/convert") && options?.method === "POST"
  )).toHaveLength(1);
});

test("M2.6 : le paiement manquant désactive la finalisation", async () => {
  const fetchMock = renderAdmissions({
    initialStatus: "accepted", canEnroll: true, canCreate: false,
    financeBlocker: "Paiement requis à la caisse.",
  });
  await selectFile();
  const button = screen.getByRole("button", {name: "Confirmer l’inscription définitive"});
  expect(button.disabled).toBe(true);
  expect(screen.getByText(/Paiement requis à la caisse/)).toBeTruthy();
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/app-1/convert"))).toBe(false);
});
