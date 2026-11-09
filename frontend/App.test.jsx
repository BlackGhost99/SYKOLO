// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();window.history.replaceState(null,"","/");});

test("la page d'accueil propose uniquement les espaces réel et démonstration",()=>{
  window.history.replaceState(null,"","/");
  render(<App/>);
  const nav=screen.getByRole("navigation",{name:"Mode d'application YEM"});
  expect(nav.querySelectorAll("button")).toHaveLength(2);
  expect(screen.getByRole("button",{name:"Espace de gestion réel"})).toBeTruthy();
  expect(screen.getByRole("button",{name:/Démonstration interactive/})).toBeTruthy();
  expect(screen.queryByText(/Maquettes PC \(référence statique\)/)).toBeNull();
});

test("le bouton démonstration ouvre un parcours fictif isolé",async()=>{
  window.history.replaceState(null,"","/");
  const fetch=vi.fn(()=>{throw Error("API inaccessible dans ce test");});
  vi.stubGlobal("fetch",fetch);
  render(<App/>);
  await userEvent.setup().click(screen.getByRole("button",{name:/Démonstration interactive/}));
  expect(window.location.hash).toBe("#/demo");
  expect(await screen.findByRole("button",{name:/MODE DÉMONSTRATION/})).toBeTruthy();
  expect(await screen.findByRole("heading",{name:"Tableau de bord"})).toBeTruthy();
});
