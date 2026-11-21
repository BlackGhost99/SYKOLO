// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,waitFor,within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {LiveArrears,LivePayments,fmtMoney} from "./LiveScreens.jsx";
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

test("WhatsApp prepares a reminder for the selected family alongside the YEM action", async () => {
  const report = {
    currency:"XAF", outstanding:"1350000", overdue_total:"300000", families_late:2,
    month:{total:"0", previous:"0"}, arrears_by_class:[],
    arrears:[
      {enrollment:"e1", student:"Élève A", guardian:"Responsable A", phone:"077 12 34 56", amount_due:"300000", due_date:"2026-10-05"},
      {enrollment:"e2", student:"Élève B", phone:"", amount_due:"150000"},
    ],
  };
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(report)));
  render(<LiveArrears schoolId="school" canRemind/>);
  const user = userEvent.setup();
  const row = await screen.findByRole("row", {name:/Élève A/});
  await user.click(within(row).getByRole("cell", {name:"300 000 FCFA"}));
  expect(within(row).getByRole("button", {name:"Élève A"}).getAttribute("aria-pressed")).toBe("true");
  const url = new URL(screen.getByRole("link", {name:"Préparer la relance WhatsApp"}).href);
  expect(url.origin + url.pathname).toBe("https://wa.me/24177123456");
  expect(url.searchParams.get("text")).toContain("300 000 FCFA");
  expect(url.searchParams.get("text")).toContain("plus ancienne échéance");
  expect(screen.getByRole("button", {name:"Envoyer la relance dans YEM"}).disabled).toBe(false);
  screen.getByRole("button", {name:"Élève B"}).focus();
  await user.keyboard("{Enter}");
  expect(screen.getByRole("button", {name:"Préparer la relance WhatsApp"}).disabled).toBe(true);
});

test("la caisse affecte d’abord le montant à la mensualité la plus ancienne", async () => {
  const october = {id:"october", label:"Octobre", balance:"10000", currency:"XAF", due_date:"2026-10-05", monthly:true};
  const january = {id:"january", label:"Janvier", balance:"20000", currency:"XAF", due_date:"2027-01-05", monthly:true};
  const report = {currency:"XAF", today:{date:"2026-11-15", total:"0", count:0, by_method:{}, payments:[]},
    yesterday:{total:"0", count:0}};
  const fetchMock = vi.fn(async (path, options) => {
    if (path.includes("finance/batches")) return Response.json({id:"batch", total:"15000", currency:"XAF"});
    if (path.includes("overview/students")) return Response.json({students:[{id:"student", active:true,
      last_name:"Essai", first_name:"Lina", enrollment:{id:"enrollment", classroom:{name:"CM1"}}}]});
    if (path.includes("finance/charges")) return Response.json({charges:[january, october]});
    return Response.json(report);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<LivePayments schoolId="school" canReceive/>);
  const user = userEvent.setup();
  await screen.findByRole("option", {name:/Essai Lina/});
  await user.selectOptions(screen.getByLabelText(/Élève/), "enrollment");
  const octoberButton = await screen.findByRole("button", {name:/Octobre/});
  expect(octoberButton.className).toContain("active");
  await user.click(screen.getByRole("button", {name:/Janvier/}));
  const amount = screen.getByLabelText(/Montant saisi/);
  await user.clear(amount);
  await user.type(amount, "15000");
  await user.click(screen.getByRole("button", {name:"Valider le paiement"}));
  const [, request] = fetchMock.mock.calls.find(([path]) => path.includes("finance/batches"));
  expect(JSON.parse(request.body).lines).toEqual([
    {charge:"october", amount:"10000.00"},
    {charge:"january", amount:"5000.00"},
  ]);
});

test("la caisse recherche le matricule avec les zéros initiaux et filtre par classe", async () => {
  const report={currency:"XAF",today:{date:"2026-11-20",total:"0",count:0,by_method:{},payments:[]},yesterday:{total:"0",count:0}};
  const pupil={id:"pupil",active:true,last_name:"NZE",first_name:"Lina",student_code:"00042",
    enrollment:{id:"target",classroom:{id:"class-a",name:"6e A"}},guardian:{full_name:"Parent essai"}};
  const fetchMock=vi.fn(async path=>{
    if(path.includes("overview/students")){
      const params=new URLSearchParams(path.split("?")[1]);
      return Response.json({classes:[{id:"class-a",name:"6e A"}],
        students:params.get("q")==="00042"?[pupil]:[],selected:params.get("selected")==="target"?pupil:null,
        total:params.get("q")==="00042"?1:0,page:1,page_size:25});
    }
    if(path.includes("finance/charges"))return Response.json({charges:[]});
    return Response.json(report);
  });
  vi.stubGlobal("fetch",fetchMock);
  render(<LivePayments schoolId="school" workingYearId="year" canReceive/>);
  const user=userEvent.setup();
  await screen.findByRole("option",{name:"6e A"});
  await user.selectOptions(screen.getByLabelText("Classe — un élève"),"class-a");
  await user.type(screen.getByLabelText("Rechercher un élève"),"00042");
  await screen.findByRole("option",{name:/NZE Lina.*00042/});
  await user.selectOptions(screen.getByLabelText(/Élève/),"target");
  await screen.findByText("Parent essai");
  expect(fetchMock.mock.calls.some(([path])=>path.includes("q=00042")&&path.includes("classroom=class-a"))).toBe(true);
  await user.clear(screen.getByLabelText("Rechercher un élève"));
  expect(screen.getByRole("button",{name:"Valider le paiement"}).disabled).toBe(true);
});

test("les impayés recherchent côté serveur et conservent les indicateurs globaux", async () => {
  const report={currency:"XAF",outstanding:"1350000",overdue_total:"300000",families_late:140,
    month:{total:"0",previous:"0"},arrears_by_class:[],arrears_classes:[{id:"class-b",name:"6e B"}]};
  const target={enrollment:"late-target",student:"MINKO Alice",student_code:"00900",classroom:"6e B",amount_due:"50000",due_date:"2026-10-05",overdue_items:[]};
  const fetchMock=vi.fn(async path=>{
    const params=new URLSearchParams(path.split("?")[1]);
    return Response.json({...report,arrears:params.get("q")==="00900"?[target]:[],
      arrears_total:params.get("q")==="00900"?1:140,arrears_page:1,arrears_page_size:25});
  });
  vi.stubGlobal("fetch",fetchMock);
  render(<LiveArrears schoolId="school" canRemind/>);
  const user=userEvent.setup();
  await screen.findByRole("option",{name:"6e B"});
  await user.selectOptions(screen.getByLabelText("Classe — un impayé"),"class-b");
  await user.type(screen.getByLabelText("Rechercher un impayé"),"00900");
  await screen.findByRole("button",{name:"MINKO Alice"});
  expect(screen.getByText("00900")).toBeTruthy();
  expect(fetchMock.mock.calls.some(([path])=>path.includes("q=00900")&&path.includes("classroom=class-b"))).toBe(true);
  expect(screen.getByText("140")).toBeTruthy();
});

test("le comptable et l'économe consultent les catégories sans additionner les admissions",async()=>{
  const report={
    currency:"XAF", currencies:["XAF"],
    year:{id:"year",name:"2026–2027"}, years:[{id:"year",name:"2026–2027"}],
    today:{total:"0",count:0,by_method:{},payments:[]},yesterday:{total:"0",count:0},
  };
  const income={
    entry_categories:{
      rows:[
        {category:"scolarite",label:"Scolarité",currency:"XAF",billed:"120000",paid:"50000",payments:2},
        {category:"extrascolaire",label:"Extrascolaire",currency:"XAF",billed:"20000",paid:"5000",payments:1},
      ],
      details:[
        {category:"scolarite",currency:"XAF",fee_code:"SCOL-202611",billed:"120000",paid:"50000"},
        {category:"extrascolaire",currency:"XAF",fee_code:"transport",billed:"20000",paid:"5000"},
      ],
      receivables:{
        revenue_certified:false,
        note:"Échéances catégorisées, sans regroupement avec la caisse.",
        rows:[
          {category:"scolarite",label:"Scolarité",currency:"XAF",billed_net:"120000",
            paid_declared:"50000",outstanding:"70000",overdue:"25000",
            due_today:"5000",future:"40000",without_due_date:"0",overpayment_review:"0"},
          {category:"extrascolaire",label:"Extrascolaire",currency:"XAF",billed_net:"20000",
            paid_declared:"5000",outstanding:"15000",overdue:"0",
            due_today:"0",future:"15000",without_due_date:"0",overpayment_review:"0"},
        ],
      },
    },
    admission_cash:{total:"15000.00",count:1},
  };
  const fetchMock=vi.fn(async path=>{
    if(String(path).includes("finance/summary?year=year"))return Response.json(income);
    if(String(path).includes("overview/students"))return Response.json({students:[]});
    return Response.json(report);
  });
  vi.stubGlobal("fetch",fetchMock);
  render(<LivePayments schoolId="school" workingYearId="year" canReceive={false}/>);
  const title=await screen.findByText("Ventilation des entrées — année scolaire");
  expect(title).toBeTruthy();
  const user=userEvent.setup();
  const arrears=screen.getByText(/Créances scolaires et extrascolaires : consulter les impayés par échéance/);
  expect(arrears.closest("details").open).toBe(false);
  await user.click(arrears);
  expect(arrears.closest("details").open).toBe(true);
  expect(within(arrears.closest("details")).getByText(/Échéances catégorisées/)).toBeTruthy();
  expect(within(arrears.closest("details")).getAllByText(/25 000 FCFA/).length).toBeGreaterThan(0);
  expect(within(arrears.closest("details")).getAllByText(/15 000 FCFA/).length).toBeGreaterThan(0);
  expect(screen.getByText(/Inscriptions encaissées à la caisse/)).toBeTruthy();
  expect(screen.getAllByText(/15 000 FCFA/).length).toBeGreaterThan(0);
  expect(screen.getByText(/sans rapprochement/)).toBeTruthy();
  const drill=screen.getByText(/Scolarité \(XAF\) : consulter 1 code\(s\) tarifaire\(s\)/);
  expect(drill.closest("details").open).toBe(false);
  await user.click(drill);
  expect(drill.closest("details").open).toBe(true);
  expect(within(drill.closest("details")).getByText("SCOL-202611")).toBeTruthy();
  await user.click(screen.getByRole("button",{name:"Actualiser la ventilation des entrées"}));
  await waitFor(()=>expect(fetchMock.mock.calls.filter(([path])=>String(path).includes("finance/summary?year=year")).length).toBe(2));
});
