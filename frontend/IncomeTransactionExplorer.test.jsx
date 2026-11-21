// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import IncomeTransactionExplorer from "./IncomeTransactionExplorer.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

test("le clic révèle les règlements paginés et ouvre uniquement le justificatif autorisé",async()=>{
  const fetcher=vi.fn(async url=>{
    const params=new URLSearchParams(String(url).split("?")[1]);
    const page=Number(params.get("page"));
    return Response.json({
      total:30,page,pages:2,rows:[{id:"receipt-1",date:"2026-11-20",
        amount:"15000.00",currency:"XAF",method:"especes",evidence:"manual_record",
        future_dated:false,receipt_url:"/api/v1/schools/school/finance/payments/receipt-1/receipt"}],
    });
  });
  vi.stubGlobal("fetch",fetcher);
  const user=userEvent.setup();
  render(<IncomeTransactionExplorer schoolId="school" yearId="year"
    category="scolarite" currency="XAF" feeCode="SCOL-202611"/>);
  expect(fetcher).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button",{name:"Voir les transactions de SCOL-202611"}));
  const link=await screen.findByRole("link",{name:"Voir le reçu PDF"});
  expect(link.getAttribute("href")).toContain("/receipt-1/receipt");
  expect(link.getAttribute("rel")).toContain("noopener");
  const params=new URLSearchParams(String(fetcher.mock.calls[0][0]).split("?")[1]);
  expect(params.get("category")).toBe("scolarite");
  expect(params.get("currency")).toBe("XAF");
  expect(params.get("fee_code")).toBe("SCOL-202611");
  await user.click(screen.getByRole("button",{name:"Suivant"}));
  await waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(2));
  expect(new URLSearchParams(String(fetcher.mock.calls[1][0]).split("?")[1]).get("page")).toBe("2");
  await user.click(screen.getByRole("button",{name:"Fermer les transactions"}));
  expect(screen.queryByRole("link",{name:"Voir le reçu PDF"})).toBeNull();
});

test("un échec serveur ne révèle aucune transaction",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>Response.json({error:"Accès financier refusé"},{status:403})));
  const user=userEvent.setup();
  render(<IncomeTransactionExplorer schoolId="school" yearId="year"
    category="extrascolaire" currency="XAF" feeCode="transport"/>);
  await user.click(screen.getByRole("button",{name:"Voir les transactions de transport"}));
  expect((await screen.findByRole("alert")).textContent).toContain("Accès financier refusé");
  expect(screen.queryByRole("link",{name:"Voir le reçu PDF"})).toBeNull();
});

test("filtre les dates sans exposer de données puis prépare un export CSV protégé",async()=>{
  const fetcher=vi.fn(async()=>Response.json({total:1,page:1,pages:1,rows:[{
    id:"receipt-1",date:"2026-11-20",amount:"15000.00",currency:"XAF",
    method:"especes",evidence:"manual_record",
    receipt_url:"/api/v1/schools/school/finance/payments/receipt-1/receipt",
  }]}));
  vi.stubGlobal("fetch",fetcher);
  const user=userEvent.setup();
  render(<IncomeTransactionExplorer schoolId="school" yearId="year"
    category="scolarite" currency="XAF" feeCode="SCOL-202611"/>);
  await user.click(screen.getByRole("button",{name:"Voir les transactions de SCOL-202611"}));
  const exportLink=await screen.findByRole("link",{name:/Exporter les règlements filtrés en CSV/});
  expect(exportLink.getAttribute("href")).toContain("format=csv");
  fireEvent.change(screen.getByLabelText("Début de période"),{target:{value:"2026-11-20"}});
  fireEvent.change(screen.getByLabelText("Fin de période"),{target:{value:"2026-11-20"}});
  await waitFor(()=>expect(fetcher.mock.calls.some(([url])=>{
    const params=new URLSearchParams(String(url).split("?")[1]);
    return params.get("from")==="2026-11-20"&&params.get("to")==="2026-11-20";
  })).toBe(true));
  expect(screen.getByRole("link",{name:/Exporter les règlements filtrés en CSV/})
    .getAttribute("href")).toContain("from=2026-11-20");
  fireEvent.change(screen.getByLabelText("Début de période"),{target:{value:"2026-11-21"}});
  expect(screen.getByRole("alert").textContent).toContain("La date de début doit précéder");
  expect(screen.queryByRole("link",{name:/Exporter les règlements filtrés en CSV/})).toBeNull();
  await user.click(screen.getByRole("button",{name:"Effacer les dates"}));
  expect(screen.getByLabelText("Début de période").value).toBe("");
});
