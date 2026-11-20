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

test("la contrepassation attend un justificatif et une confirmation explicite", async () => {
  const batch = {
    id:"lot",source_reference:"registre.xlsx",year_name:"Année courante",
    cutoff:"2026-10-31",status:"approved",reversal_pending:true,
    reversal_reason:"Doublon du registre",can_confirm_reversal:true,entries:[],
  };
  const fetchMock = vi.fn(async url => ({
    ok:true,headers:{get:()=>"application/json"},
    json:async()=>{
      if(url.endsWith("/batches"))return {batches:[batch]};
      if(url.endsWith("/lot"))return batch;
      return {status:"reversed"};
    },
  }));
  vi.stubGlobal("fetch",fetchMock);
  render(<FinancialMigration schoolId="school"/>);

  fireEvent.click(await screen.findByRole("button",{name:"Examiner le lot"}));
  const approve = await screen.findByRole("button",{name:"Approuver le retrait des crédits historiques"});
  expect(approve.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Motif ou référence du justificatif"),{target:{value:"Pièce rectificative R-12"}});
  expect(approve.disabled).toBe(true);
  fireEvent.click(screen.getByRole("checkbox",{name:/Je confirme avoir contrôlé/}));
  fireEvent.click(approve);

  await screen.findByText("Contrepassation approuvée. Les soldes ont été recalculés.");
  const [,options] = fetchMock.mock.calls.find(([url])=>url.endsWith("/lot/reversal/confirm"));
  expect(options.method).toBe("POST");
  expect(options.body.get("reason")).toBe("Pièce rectificative R-12");
});
