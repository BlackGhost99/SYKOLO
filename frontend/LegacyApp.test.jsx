// @vitest-environment jsdom
import React from "react";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, test, expect, vi } from "vitest";
import App from "./LegacyApp.jsx";
import presets from "../backend/pedagogy/presets.json";
let calls = [];
beforeEach(() => {
  calls = [];
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path, opts = {}) => {
      const data = opts.body ? JSON.parse(opts.body) : undefined;
      calls.push({ path, data });
      let body = path === "/api/v1/auth/me"
        ? { authenticated: false }
        : path.endsWith("/auth/csrf")
          ? { csrf: "ready" }
          : path.endsWith("/presets")
        ? presets
        : path === "/healthz"
          ? { version: "0.2.0", commit: "testsha" }
          : path.endsWith("/validate")
            ? { valid: true }
            : {
                status: "calculated",
                score: 15.33,
                percent: 76.6667,
                label: "Bien",
                notification: null,
              };
      return {
        ok: true,
        headers: { get: () => "application/json" },
        json: async () => body,
      };
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
test("loads the API models and displays the simulated result", async () => {
  render(<App />);
  await screen.findByLabelText("Nom du profil");
  await screen.findByText("Bien");
  expect(screen.getByText("8 points de départ")).toBeTruthy();
  expect(calls.some((x) => x.path === "/api/v1/evaluate")).toBe(true);
});
test("saves only after server validation and reopens a local profile", async () => {
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Nom du profil");
  await user.clear(screen.getByLabelText("Nom du profil"));
  await user.type(
    screen.getByLabelText("Nom du profil"),
    "Primaire personnalisé",
  );
  await user.click(
    screen.getByRole("button", { name: /Enregistrer le profil/ }),
  );
  await waitFor(() =>
    expect(
      JSON.parse(localStorage.getItem("sykolo.policies.v1"))[0].policy.name,
    ).toBe("Primaire personnalisé"),
  );
  expect(calls.some((x) => x.path.endsWith("/validate"))).toBe(true);
});
test("passes custom coefficients to Django", async () => {
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Coefficient évaluation 1");
  await user.clear(screen.getByLabelText("Coefficient évaluation 1"));
  await user.type(screen.getByLabelText("Coefficient évaluation 1"), "3");
  await waitFor(() =>
    expect(
      calls.filter((x) => x.path.endsWith("/evaluate")).at(-1)?.data.entries[0]
        .weight,
    ).toBe(3),
  );
});
test("switches to letters without keeping numeric scores", async () => {
  const user = userEvent.setup();
  render(<App />);
  await screen.findByLabelText("Partir d’un modèle");
  await user.selectOptions(
    screen.getByLabelText("Partir d’un modèle"),
    "letters",
  );
  expect(screen.getByLabelText("Niveau évaluation 1")).toBeTruthy();
  await waitFor(() =>
    expect(
      calls.filter((x) => x.path.endsWith("/evaluate")).at(-1)?.data.policy
        .scale.kind,
    ).toBe("letters"),
  );
  expect(
    typeof calls.filter((x) => x.path.endsWith("/evaluate")).at(-1).data
      .entries[0].score,
  ).toBe("string");
});
test("renders edited content as text", async () => {
  const user = userEvent.setup();
  const { container } = render(<App />);
  await screen.findByLabelText("Nom du profil");
  await user.clear(screen.getByLabelText("Nom du profil"));
  await user.type(
    screen.getByLabelText("Nom du profil"),
    "<img src=x onerror=alert(1)>",
  );
  // Le logo YEM officiel est légitime ; vérifier seulement que le HTML injecté ne crée aucune image.
  expect(container.querySelector('img[src="x"], img[onerror]')).toBeNull();
  expect(
    screen.getByRole("heading", { name: "<img src=x onerror=alert(1)>" }),
  ).toBeTruthy();
});
