// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {LivePayments,fmtMoney} from "./LiveScreens.jsx";
vi.mock("./CashClosingPanel.jsx",()=>({default:()=>null}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test("cashier selection never adds EUR and XAF balances",async()=>{
  const report={currency:"XAF",currencies:["XAF","EUR"],year:{id:"year",name:"Année"},years:[{id:"year",name:"Année"}],today:{total:"0",count:0,by_method:{},payments:[]},yesterday:{total:"0",count:0}};
  const fetchMock=vi.fn(async path=>({ok:true,headers:{get:()=>"application/json"},json:async()=>String(path).includes("overview/students")?{students:[{id:"student",active:true,last_name:"Essai",first_name:"Lina",enrollment:{id:"enrollment",classroom:{name:"CM1"}}}]}:String(path).includes("finance/charges")?{charges:[{id:"xaf",label:"Scolarité",balance:"50000",currency:"XAF"},{id:"eur",label:"Option euro",balance:"12.50",currency:"EUR"}]}:report}));
  vi.stubGlobal("fetch",fetchMock);
  render(<LivePayments schoolId="school" canReceive/>);
  const user=userEvent.setup();
  await screen.findByRole("option",{name:/Essai Lina/});
  await user.selectOptions(screen.getByLabelText(/Élève/),"enrollment");
  await screen.findByRole("button",{name:/Option euro/});
  expect(screen.getByLabelText(/Montant saisi/).value).toBe("50 000");
  await user.click(screen.getByRole("button",{name:/Option euro/}));
  expect(screen.getByLabelText(/Montant saisi/).value).toBe("12,5");
  expect(screen.getByText("0 EUR")).toBeTruthy();
  expect(screen.getByRole("button",{name:/Scolarité/}).className).not.toContain("active");
  await user.selectOptions(screen.getByLabelText("Devise de consultation"),"EUR");
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("overview/finance?currency=EUR"),expect.anything()));
  expect(fmtMoney("12.50","EUR")).toBe("12,5 EUR");
});
