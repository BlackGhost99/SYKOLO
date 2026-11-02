// @vitest-environment jsdom
import React from "react";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, test, expect } from "vitest";
import App from "./App.jsx";

afterEach(cleanup);

test("renders the PC dashboard from the approved YEM mockup", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "Tableau de bord fondateur" })).toBeTruthy();
  expect(screen.getAllByText("8 950 000 FCFA").length).toBeGreaterThan(0);
  expect(screen.getByText("École Privée Les Amandiers")).toBeTruthy();
});

test("navigates between the approved PC screens", async () => {
  const user = userEvent.setup();
  render(<App />);
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
  await user.click(screen.getByRole("button", { name: /Identité visuelle/ }));
  expect(screen.getByRole("heading", { name: /Identité visuelle de l’établissement/ })).toBeTruthy();
  expect(screen.getAllByText(/BWETEK Informatyk/).length).toBeGreaterThan(0);
  await user.clear(screen.getByLabelText("Nom de l’établissement"));
  await user.type(screen.getByLabelText("Nom de l’établissement"), "École Exemple");
  expect(screen.getAllByText("École Exemple").length).toBeGreaterThan(0);
  expect(document.querySelector(".yd-logo")).toBeTruthy();
});
