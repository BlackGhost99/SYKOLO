// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import SingPayControl from "./SingPayControl.jsx";
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
test("cashier cannot see merchant or reconciliation controls",async()=>{
  const fetch=vi.fn(async()=>({ok:false,status:403}));vi.stubGlobal("fetch",fetch);
  const {container}=render(<SingPayControl schoolId="school"/>);
  await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2));
  expect(container.textContent).toBe("");
});
test("founder prepares school account without an activation control",async()=>{
  vi.stubGlobal("fetch",vi.fn(async path=>({ok:true,json:async()=>String(path).endsWith("merchant")?
    {revision:0,beneficiary:"",fee_basis_points:0,fee_fixed_xaf:0}:{payments:[]}})));
  render(<SingPayControl schoolId="school"/>);
  expect(await screen.findByText("Enregistrer sans activer les paiements")).toBeTruthy();
  expect(screen.getByLabelText("Secret client SingPay").type).toBe("password");
  expect(screen.queryByText("Activer les paiements")).toBeNull();
});
