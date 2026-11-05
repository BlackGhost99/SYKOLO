// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,fireEvent,waitFor} from "@testing-library/react";
import SingPayPayment from "./SingPayPayment.jsx";
afterEach(cleanup);
const quote={merchant:{active:true,revision:3,beneficiary:"École A",mode:"live",fee_basis_points:250,fee_fixed_xaf:25},balance_xaf:"10000",payments:[]};
test("shows direct beneficiary and school-borne fee before payment",async()=>{
  const api=vi.fn(async()=>quote);
  render(<SingPayPayment kind="charge" objectId="fee" api={api} partial/>);
  expect(await screen.findByText("École A")).toBeTruthy();
  expect(screen.getByText(/Net estimé pour l'école : 9725 XAF/)).toBeTruthy();
  expect(api.mock.calls.every(call=>call[1]===undefined)).toBe(true);
});
test("keeps same operation after network error and never claims browser success",async()=>{
  const api=vi.fn(async(path,body)=>{if(body)throw Error("Connexion perdue");return quote});
  render(<SingPayPayment kind="charge" objectId="fee" api={api} partial/>);
  await screen.findByText("École A");
  fireEvent.change(screen.getByLabelText("Téléphone Mobile Money"),{target:{value:"074000000"}});
  fireEvent.submit(screen.getByRole("button",{name:"Payer à l'établissement"}).closest("form"));
  await screen.findByText("Connexion perdue");
  fireEvent.submit(screen.getByRole("button",{name:"Payer à l'établissement"}).closest("form"));
  await waitFor(()=>expect(api.mock.calls.filter(call=>call[1]).length).toBe(2));
  const writes=api.mock.calls.filter(call=>call[1]);
  expect(writes[0][1]).toEqual(writes[1][1]);
  expect(screen.queryByText("Reçu vérifié")).toBeNull();
});
test("disabled merchant exposes no debit button",async()=>{
  const api=vi.fn(async()=>({...quote,merchant:{...quote.merchant,active:false}}));
  render(<SingPayPayment kind="admission" objectId="application" api={api}/>);
  await screen.findByText(/SingPay sera proposé/);
  expect(screen.queryByRole("button",{name:"Payer à l'établissement"})).toBeNull();
});
