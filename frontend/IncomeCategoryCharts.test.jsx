// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test} from "vitest";
import {cleanup,render,screen,within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import IncomeCategoryCharts from "./IncomeCategoryCharts.jsx";

afterEach(()=>cleanup());
const base={
  rows:[
    {category:"scolarite",label:"Scolarité",currency:"XAF",billed:"50000.00",paid:"20000.00"},
    {category:"extrascolaire",label:"Extrascolaire",currency:"XAF",billed:"10000.00",paid:"5000.00"},
    {category:"demo",label:"Démonstration",currency:"XAF",billed:"0.00",paid:"20000.00"},
    {category:"extrascolaire",label:"Extrascolaire",currency:"EUR",billed:"40.00",paid:"30.00"},
  ],
  details:[
    {category:"scolarite",currency:"XAF",fee_code:"SCOL-2026",billed:"50000.00",paid:"20000.00"},
    {category:"extrascolaire",currency:"XAF",fee_code:"CANTINE",billed:"10000.00",paid:"5000.00"},
    {category:"extrascolaire",currency:"EUR",fee_code:"BUS-EUR",billed:"40.00",paid:"30.00"},
  ],
  receivables:{rows:[
    {category:"scolarite",currency:"XAF",outstanding:"30000.00",overdue:"20000.00",future:"10000.00"},
    {category:"extrascolaire",currency:"XAF",outstanding:"5000.00",overdue:"0.00",future:"5000.00"},
    {category:"extrascolaire",currency:"EUR",outstanding:"10.00",overdue:"10.00",future:"0.00"},
  ]},
};

test("les barres sont cliquables, les simulations exclues et aucune donnée nominative n'apparaît",async()=>{
  const user=userEvent.setup();
  render(<IncomeCategoryCharts report={base} schoolId="a" yearId="y"/>);
  expect(screen.queryByRole("button",{name:/Démonstration :/})).toBeNull();
  const school=screen.getByRole("button",{name:/Scolarité : 20.*XAF/});
  expect(school.getAttribute("aria-pressed")).toBe("false");
  await user.click(school);
  expect(school.getAttribute("aria-pressed")).toBe("true");
  const details=screen.getByLabelText("Détail de Scolarité");
  expect(within(details).getByText("SCOL-2026")).toBeTruthy();
  expect(within(details).getByText("50 000 XAF")).toBeTruthy();
  expect(screen.queryByText(/Secret Personne/)).toBeNull();
  await user.selectOptions(screen.getByLabelText("Indicateur des graphiques"),"overdue");
  expect(screen.getByRole("button",{name:/Scolarité : 20.*XAF/})).toBeTruthy();
  expect(screen.queryByLabelText("Détail de Scolarité")).toBeNull();
});

test("la devise se choisit sans additionner XAF et EUR",async()=>{
  const user=userEvent.setup();
  render(<IncomeCategoryCharts report={base} schoolId="a" yearId="y"/>);
  await user.selectOptions(screen.getByLabelText("Devise des graphiques"),"EUR");
  expect(screen.getByRole("button",{name:/Extrascolaire : 30.*EUR/})).toBeTruthy();
  expect(screen.queryByRole("button",{name:/Scolarité.*XAF/})).toBeNull();
  await user.selectOptions(screen.getByLabelText("Présentation du graphique"),"compact");
  await user.click(screen.getByRole("button",{name:"Masquer le graphique"}));
  expect(screen.queryByLabelText("Devise des graphiques")).toBeNull();
  await user.click(screen.getByRole("button",{name:"Afficher le graphique"}));
  expect(screen.getByLabelText("Devise des graphiques")).toBeTruthy();
});

test("les échéances absentes sont signalées au lieu d'être inventées",async()=>{
  const user=userEvent.setup();
  render(<IncomeCategoryCharts report={{rows:base.rows,details:base.details}} schoolId="a" yearId="y"/>);
  await user.selectOptions(screen.getByLabelText("Indicateur des graphiques"),"future");
  expect(screen.getByText(/Les échéances ne sont pas encore disponibles/)).toBeTruthy();
});
