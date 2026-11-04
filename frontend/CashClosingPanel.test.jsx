// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import CashClosingPanel from "./CashClosingPanel.jsx";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function setup(permissions){
  vi.stubGlobal("fetch",vi.fn(async path=>({ok:true,headers:{get:()=>"application/json"},json:async()=>String(path).endsWith("my-access")?{permissions}:String(path).endsWith("summary")?{currencies:{}}:{closings:[]}})));
  render(<CashClosingPanel schoolId="school"/>);
}
test("accountant controls cash without collecting or depositing",async()=>{
  setup(["school.finance.read","school.finance.approve"]);
  await screen.findByText("Déclarations récentes");
  expect(screen.queryByText("Soumettre le contrôle de caisse")).toBeNull();
  expect(screen.queryByRole("form",{name:"Remise ou dépôt"})).toBeNull();
});
test("cashier can declare cash and document transfers",async()=>{
  setup(["school.finance.read","school.finance.receive","school.finance.deposit"]);
  expect(await screen.findByText("Soumettre le contrôle de caisse")).toBeTruthy();
  expect(screen.getByRole("form",{name:"Remise ou dépôt"})).toBeTruthy();
});
