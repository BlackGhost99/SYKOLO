// @vitest-environment jsdom
import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, test, expect } from "vitest";
import App from "./App.jsx";

afterEach(() => { cleanup(); window.localStorage.clear(); });

test("renders the PC dashboard from the approved YEM mockup", async () => {
  render(<App />);
  await userEvent.setup().click(screen.getByRole("button", { name: /Maquettes PC/ }));
  expect(screen.getByRole("heading", { name: "Tableau de bord fondateur" })).toBeTruthy();
  expect(screen.getAllByText("8 950 000 FCFA").length).toBeGreaterThan(0);
  expect(screen.getByText("École Privée Les Amandiers")).toBeTruthy();
});

test("navigates between the approved PC screens", async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole("button", { name: /Maquettes PC/ }));
  await user.click(screen.getByRole("button", { name: /Élèves/ }));
  expect(screen.getByRole("heading", { name: "Gestion des élèves" })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /Admissions/ }));
  expect(screen.getByRole("heading", { name: "Admissions & préinscriptions" })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /Paiements/ }));
  expect(screen.getByRole("heading", { name: "Encaissements et caisse journalière" })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /Impayés & relances/ }));
  expect(screen.getByRole("heading", { name: "Impayés & relances" })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /^Bulletins$/ }));
  expect(screen.getByRole("heading", { name: "Bulletins et résultats scolaires" })).toBeTruthy();
  await user.click(screen.getByRole("button", { name: /Paramètres/ }));
  expect(screen.getByRole("heading", { name: "Paramétrage pédagogique et bulletins" })).toBeTruthy();
});

test("school branding editor keeps YEM and BWETEK visible", async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole("button", { name: /Maquettes PC/ }));
  await user.click(screen.getByRole("button", { name: /École Privée Les Amandiers/ }));
  await user.click(screen.getByRole("menuitem", { name: /Identité visuelle/ }));
  expect(screen.getByRole("heading", { name: /Identité visuelle de l’établissement/ })).toBeTruthy();
  expect(screen.getAllByText(/BWETEK Informatyk/).length).toBeGreaterThan(0);
  await user.clear(screen.getByLabelText("Nom de l’établissement"));
  await user.type(screen.getByLabelText("Nom de l’établissement"), "École Exemple");
  expect(screen.getAllByText("École Exemple").length).toBeGreaterThan(0);
  expect(document.querySelector(".yd-logo")).toBeTruthy();
});

test("sidebar matches the ten entries of the approved mockups", async () => {
  render(<App />);
  await userEvent.setup().click(screen.getByRole("button", { name: /Maquettes PC/ }));
  const nav = screen.getByRole("complementary", { name: "Navigation principale" });
  const labels = [...nav.querySelectorAll("button")].map(b => b.textContent);
  expect(labels).toEqual(["Tableau de bord", "Élèves", "Admissions", "Paiements", "Impayés & relances", "Bulletins", "Absences", "Parents", "Personnel", "Paramètres"]);
});

test("shows the three mobile screens of the approved mockup", async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole("button", { name: /Maquettes PC/ }));
  await user.click(screen.getByRole("button", { name: /École Privée Les Amandiers/ }));
  await user.click(screen.getByRole("menuitem", { name: /Expérience mobile/ }));
  expect(screen.getByRole("heading", { name: "YEM — Expérience mobile" })).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Espace parent" })).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Appel enseignant" })).toBeTruthy();
  expect(screen.getAllByRole("heading", { name: "Reçu de paiement" }).length).toBeGreaterThan(0);
  expect(screen.getByText("N° REÇU : YEM-2027-000458")).toBeTruthy();
});
