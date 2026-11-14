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

test.each([["50000","50000.00"],["10000","10000.00"]])(
  "la caisse valide les espèces avec un montant saisi de %s sans bascule de paiement partiel",
  async (amount, expected) => {
    const report = {currency:"XAF", today:{date:"2026-11-11",total:"0",count:0,by_method:{},payments:[]},
      yesterday:{total:"0",count:0}};
    const fetchMock = vi.fn(async (path, options) => {
      if (path.includes("finance/batches")) {
        expect(JSON.parse(options.body)).toMatchObject({enrollment:"enrollment",method:"especes",
          lines:[{charge:"charge",amount:expected}]});
        return Response.json({id:"payment-123",total:expected,currency:"XAF",receipt_url:"/recu"});
      }
      if (path.includes("overview/students")) return Response.json({students:[{id:"student",active:true,
        last_name:"Essai",first_name:"Lina",enrollment:{id:"enrollment",classroom:{name:"CM1"}}}]});
      if (path.includes("finance/charges")) return Response.json({charges:[{id:"charge",label:"Scolarité",balance:"50000",currency:"XAF"}]});
      return Response.json(report);
    });
    vi.stubGlobal("fetch",fetchMock);
    render(<LivePayments schoolId="school" canReceive/>);
    const user = userEvent.setup();
    await screen.findByRole("option",{name:/Essai Lina/});
    await user.selectOptions(screen.getByLabelText(/Élève/),"enrollment");
    const field = screen.getByLabelText(/Montant saisi/);
    const validate = screen.getByRole("button",{name:"Valider le paiement"});
    await waitFor(()=>expect(field.disabled).toBe(false));
    expect(validate.disabled).toBe(false);
    await user.clear(field);
    await user.type(field,"50001");
    expect(validate.disabled).toBe(true);
    await user.clear(field);
    await user.type(field,amount);
    expect(validate.disabled).toBe(false);
    await user.click(validate);
    expect((await screen.findByRole("link",{name:/Télécharger le reçu groupé/})).getAttribute("href")).toBe("/recu");
  },
);

test("la caisse affiche les écritures historiques cash à rapprocher",async()=>{
  const report = {
    currency:"XAF",currencies:["XAF"],year:{id:"year",name:"Année"},
    years:[{id:"year",name:"Année"}],revenue_certified:false,
    evidence:{explicit_demo:"175000.00",legacy_cash_unverified:"77900000.00",other_declared:"600000.00"},
    today:{total:"0",count:0,by_method:{},payments:[]},yesterday:{total:"0",count:0},
  };
  vi.stubGlobal("fetch",vi.fn(async (path)=>{
    if(String(path).includes("overview/students"))return Response.json({students:[]});
    if(String(path).includes("finance/charges"))return Response.json({charges:[]});
    return Response.json(report);
  }));
  render(<LivePayments schoolId="school" canReceive={false}/>);
  const warning=await screen.findByText(/ancien cash à rapprocher/i);
  expect(warning.textContent).toContain("77 900 000");
  expect(warning.textContent).toContain("175 000");
});
