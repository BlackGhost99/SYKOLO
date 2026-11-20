// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import FinancialMigration from "./FinancialMigration.jsx";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("la reprise réutilise le classeur en mémoire, avec la feuille et l'année des inscriptions", async () => {
  const file = new File(["csv"], "registre.xlsx");
  const years = [
    {id:"active",name:"Année courante",start:"2026-09-01",end:"2027-06-30",status:"current"},
    {id:"source",name:"Année des inscriptions",start:"2025-09-01",end:"2026-06-30",status:"open"},
  ];
  const data = {
    headers:["Matricule","Versement"], sheet:"Inscriptions", sheets:["Inscriptions","Historique"],
    header_row:3, row_count:1, years, today:"2026-11-20", tariffs:[],
    suggested_student_code:0, financial_columns:[1], financial_hints:{"1":"payment_candidate"},
  };
  const fetchMock = vi.fn(async url => ({
    ok:true, headers:{get:()=>"application/json"},
    json:async()=>url.endsWith("/inspect") ? data : {batches:[]},
  }));
  vi.stubGlobal("fetch",fetchMock);
  render(<FinancialMigration schoolId="school" workingYearId="active"
    source={{file,sheet:"Inscriptions",headerRow:3,year:"source"}}/>);

  expect(fetchMock.mock.calls.some(([url])=>url.endsWith("/inspect"))).toBe(false);
  fireEvent.click(screen.getByRole("button",{name:/Analyser le fichier des inscriptions/}));
  const year = await screen.findByLabelText("Année scolaire");
  expect(year.value).toBe("source");
  expect(screen.getByLabelText("Feuille").value).toBe("Inscriptions");
  expect(screen.getByText("Versement · Versement possible")).toBeTruthy();
  const [,options] = fetchMock.mock.calls.find(([url])=>url.endsWith("/inspect"));
  expect(options.method).toBe("POST");
  expect(options.body.get("file").name).toBe(file.name);
  expect(options.body.get("sheet")).toBe("Inscriptions");
  expect(options.body.get("header_row")).toBe("3");
});
