// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,fireEvent,waitFor} from "@testing-library/react";
import SubscriptionSingPay from "./SubscriptionSingPay.jsx";
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
const quote={merchant:{active:true,beneficiary:"BWETEK",revision:2,mode:"live"},balance_xaf:10000,payments:[]};
test("shows BWETEK beneficiary and preserves operation after timeout",async()=>{
  const fetcher=vi.fn(async(path,options)=>{
    if(options?.method==="POST")throw Error("Connexion perdue");
    return {ok:true,json:async()=>quote};
  });vi.stubGlobal("fetch",fetcher);
  render(<SubscriptionSingPay schoolId="s" subscriptionId={1}/>);
  await screen.findByText(/Bénéficiaire : BWETEK/);
  fireEvent.change(screen.getByLabelText("Téléphone Mobile Money"),{target:{value:"074000000"}});
  const form=screen.getByRole("button",{name:"Payer BWETEK Informatyk"}).closest("form");
  fireEvent.submit(form);await screen.findByText("Connexion perdue");
  fireEvent.submit(form);
  await waitFor(()=>expect(fetcher.mock.calls.filter(c=>c[1]?.method==="POST")).toHaveLength(2));
  const writes=fetcher.mock.calls.filter(c=>c[1]?.method==="POST");
  expect(writes[0][1].body).toBe(writes[1][1].body);
  expect(screen.queryByText("Reçu d’abonnement")).toBeNull();
});
test("inactive platform account cannot initiate payment",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({...quote,merchant:{...quote.merchant,active:false}})})));
  render(<SubscriptionSingPay schoolId="s" subscriptionId={1}/>);
  await screen.findByText(/doit être validé et activé/);
  expect(screen.queryByRole("button",{name:"Payer BWETEK Informatyk"})).toBeNull();
});
