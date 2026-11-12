// @vitest-environment jsdom
import React from "react";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,expect,test,vi} from "vitest";
import AdmissionCashDesk from "./AdmissionCashDesk.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});

test("le caissier valide l'espèce réelle uniquement après confirmation de remise et voit le reçu",async()=>{
  const root="/api/v1/schools/lycee2/admission-cash";
  const onUpdated=vi.fn();
  let received=false;
  const fetchMock=vi.fn(async(url,options={})=>{
    if(url==="/api/v1/auth/csrf")return Response.json({csrf:"ready"});
    if(url===root&&options.method==="POST")throw Error("Not the payment endpoint");
    if(url===root+"/request1/confirm"){
      const body=JSON.parse(options.body);
      expect(body.received_cash).toBe(true);
      expect(body.acknowledge_demo).toBe(false);
      expect(body.reference).toBe("GUICHET-0001");
      expect(body.expected_amount_xaf).toBe(2500);
      received=true;return Response.json({status:"recu"},{status:201});
    }
    if(url===root+"?application=dossier1")return Response.json({payments:[{
      request:"request1",child:"TEST ALA",classroom:"Seconde S",
      year:"2026-2027",parent:"Mme TEST",amount_xaf:2500,
      is_demo:false,admission_status:"submitted",
      payment_status:received?"recu":"a_regler_sur_place",
      receipt_url:received?root+"/request1/receipt":null,
    }]});
    return Response.json({});
  });
  vi.stubGlobal("fetch",fetchMock);
  const user=userEvent.setup();
  render(<AdmissionCashDesk schoolId="lycee2" applicationId="dossier1" canReceive onUpdated={onUpdated}/>);
  expect(await screen.findByText("TEST ALA")).toBeTruthy();
  const confirm=screen.getByRole("button",{name:"Confirmer les espèces reçues"});
  expect(confirm.disabled).toBe(true);
  await user.type(screen.getByPlaceholderText("Référence du guichet"),"GUICHET-0001");
  await user.click(screen.getByRole("checkbox"));
  await user.click(confirm);
  expect(await screen.findByText("Espèces reçues")).toBeTruthy();
  expect(screen.getByText("Reste à payer : 0 FCFA")).toBeTruthy();
  expect(onUpdated).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("link",{name:"Reçu de caisse PDF"}).getAttribute("href"))
    .toBe(root+"/request1/receipt");
});

test("un tarif absent affiche un solde indéterminé puis l’action apparaît après actualisation",async()=>{
  let configured=false;
  vi.stubGlobal("fetch",vi.fn(async()=>Response.json({can_receive:true,payments:[{
    request:"dossier-direct",child:"TEST GUICHET",classroom:"Seconde S",year:"2026-2027",
    admission_status:"accepted",can_pay:configured,
    gross_amount_xaf:configured?2500:null,amount_xaf:configured?2500:null,
    payment_status:configured?"a_regler_sur_place":"tarif_non_configure",
  }]})));
  render(<AdmissionCashDesk schoolId="lycee2"/>);
  expect(await screen.findByText("Frais d'inscription : Tarif non configuré")).toBeTruthy();
  expect(screen.getByText("Reste à payer : Indéterminé")).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Confirmer les espèces reçues"})).toBeNull();
  configured=true;
  await userEvent.setup().click(screen.getByRole("button",{name:"Actualiser la caisse des admissions"}));
  expect(await screen.findByRole("button",{name:"Confirmer les espèces reçues"})).toBeTruthy();
});

test("le secrétariat ne peut pas encaisser ; la simulation n'est pas un reçu réel",async()=>{
  const root="/api/v1/schools/lycee2/admission-cash";
  vi.stubGlobal("fetch",vi.fn(async()=>Response.json({payments:[{
    request:"request2",child:"TEST TER",classroom:"Terminale C",
    year:"2026-2027",parent:"M TEST",amount_xaf:3500,is_demo:true,
    payment_status:"a_regler_sur_place",admission_status:"submitted",receipt_url:null,
  }]})));
  render(<AdmissionCashDesk schoolId="lycee2" canReceive={false}/>);
  expect(await screen.findByText("TEST TER")).toBeTruthy();
  expect(screen.getByText(/SIMULATION — 0 FCFA reçu/)).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Valider la simulation sans encaissement"})).toBeNull();
});


test("une bourse validée masque l'encaissement même pour un caissier habilité",async()=>{
  const root="/api/v1/schools/lycee2/admission-cash";
  const fetchMock=vi.fn(async()=>Response.json({payments:[{
    request:"request-bourse",child:"TEST BOURSIER",classroom:"Seconde C",
    year:"2026-2027",parent:"Mme TEST",amount_xaf:0,gross_amount_xaf:2500,
    scholarship_covered_xaf:2500,is_demo:false,
    payment_status:"dispense_bourse",admission_status:"accepted",
    scholarship_active:true,can_pay:false,receipt_url:null,
  }]}));
  vi.stubGlobal("fetch",fetchMock);
  render(<AdmissionCashDesk schoolId="lycee2" canReceive/>);
  expect(await screen.findByText("TEST BOURSIER")).toBeTruthy();
  expect(screen.getByText(/Bourse totale sur l'inscription : aucun règlement nécessaire/)).toBeTruthy();
  expect(screen.getByText("Frais pris en charge par bourse")).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Confirmer les espèces reçues"})).toBeNull();
  expect(screen.queryByPlaceholderText("Référence du guichet")).toBeNull();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test("une inscription déjà définitive ne propose pas de nouvel encaissement",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>Response.json({payments:[{
    request:"request-inscrit",child:"TEST INSCRIT",classroom:"Seconde C",
    year:"2026-2027",parent:"Mme TEST",amount_xaf:2500,is_demo:false,
    payment_status:"inscription_deja_finalisee",admission_status:"enrolled",
    scholarship_active:false,can_pay:false,receipt_url:null,
  }]})));
  render(<AdmissionCashDesk schoolId="lycee2" canReceive/>);
  expect(await screen.findByText("TEST INSCRIT")).toBeTruthy();
  expect(screen.getByText("Inscription déjà définitive — pas de nouveau règlement")).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Confirmer les espèces reçues"})).toBeNull();
});

test("une bourse partielle garde le guichet ouvert uniquement pour le reste à payer",async()=>{
  const root="/api/v1/schools/lycee2/admission-cash";
  vi.stubGlobal("fetch",vi.fn(async()=>Response.json({payments:[{
    request:"request-partial",child:"TEST PARTIEL",classroom:"Sixième A",
    year:"2026-2027",parent:"Responsable TEST",
    amount_xaf:1500,gross_amount_xaf:2500,scholarship_covered_xaf:1000,
    scholarship_active:true,is_demo:false,can_pay:true,
    payment_status:"a_regler_sur_place",admission_status:"accepted",receipt_url:null,
  }]})));
  render(<AdmissionCashDesk schoolId="lycee2" canReceive/>);
  expect(await screen.findByText("TEST PARTIEL")).toBeTruthy();
  expect(screen.getByText(/Bourse partielle : la caisse ne reçoit que le solde/)).toBeTruthy();
  expect(screen.getByText(/Reste à payer : 1[^0-9]*500 FCFA/)).toBeTruthy();
  expect(screen.getByRole("button",{name:"Confirmer les espèces reçues"})).toBeTruthy();
});
