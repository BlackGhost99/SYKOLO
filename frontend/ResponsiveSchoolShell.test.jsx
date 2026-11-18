// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,fireEvent,render,screen,within} from "@testing-library/react";
import {Shell} from "./yem-ui.jsx";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const nav=[["dashboard","home","Tableau de bord"],["students","users","Élèves"],["diary","file","Cahier de textes"]];
function viewport(matches){
  vi.stubGlobal("matchMedia",vi.fn(()=>({matches,addEventListener:vi.fn(),removeEventListener:vi.fn()})));
}
test("ordinateur : un seul menu, navigation groupée et rétractable",()=>{
  viewport(false);
  const go=vi.fn();
  render(<Shell className="yd-operational-compact" nav={nav} active="dashboard" onNavigate={go}><p>Contenu</p></Shell>);
  expect(screen.queryByRole("navigation",{name:"Navigation mobile"})).toBeNull();
  const main=screen.getByRole("navigation",{name:"Navigation principale"});
  fireEvent.click(within(main).getByRole("button",{name:"Réduire la navigation"}));
  expect(within(main).getByRole("button",{name:"Développer la navigation"})).toBeTruthy();
  fireEvent.click(within(main).getByRole("button",{name:"Élèves"}));
  expect(go).toHaveBeenCalledWith("students");
});
test("mobile : accès fixes autorisés, bannière conservée, menu Fermer via Échap",()=>{
  viewport(true);
  const go=vi.fn();
  render(<Shell className="yd-operational-compact" nav={nav} active="dashboard" onNavigate={go}
    headerBanner={<img src="/school-banner.png" alt="Bannière école"/>}><p>Contenu</p></Shell>);
  expect(screen.getByRole("img",{name:"Bannière école"}).getAttribute("src")).toBe("/school-banner.png");
  const mobile=screen.getByRole("navigation",{name:"Navigation mobile"});
  expect(within(mobile).queryByRole("button",{name:"Finances"})).toBeNull();
  expect(screen.queryByRole("navigation",{name:"Navigation principale"})).toBeNull();
  fireEvent.click(within(mobile).getByRole("button",{name:"Élèves"}));
  expect(go).toHaveBeenCalledWith("students");
  const plus=within(mobile).getByRole("button",{name:"Plus"});
  fireEvent.click(plus);
  const drawer=screen.getByRole("navigation",{name:"Navigation principale"});
  expect(within(drawer).getByRole("button",{name:"Cahier de textes"})).toBeTruthy();
  fireEvent.keyDown(drawer,{key:"Escape"});
  expect(screen.queryByRole("navigation",{name:"Navigation principale"})).toBeNull();
  expect(plus.getAttribute("aria-expanded")).toBe("false");
});
