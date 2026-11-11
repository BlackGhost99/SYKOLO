// @vitest-environment jsdom
import React from 'react';
import {afterEach,expect,test,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FinancePanel from './FinancePanel.jsx';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

function mockFinance(permissions) {
  vi.stubGlobal('fetch',vi.fn(async path=>({ok:true,headers:{get:()=> 'application/json'},json:async()=> {
    if(String(path).endsWith('my-access')) return {permissions};
    if(String(path).includes('payments?')) return {payments:[{id:'receipt',amount:'10',currency:'XAF',method:'especes',paid_on:'2026-11-04',voided:false}]};
    if(String(path).endsWith('charges')) return {charges:[{id:'charge',label:'Scolarité',enrollment:'enroll',balance:'10',currency:'XAF'}]};
    return {years:[{id:'year',name:'Année',active:true}],classes:[],enrollments:[],students:[],schedules:[]};
  }})));
}

test('direction can consult receipts without tariff, collection or reversal controls',async()=>{
  mockFinance(['school.finance.read','school.finance.approve']);
  render(<FinancePanel schoolId='school'/>);
  await screen.findByRole('option',{name:/Scolarité/});
  expect(screen.queryByRole('button',{name:'Créer le tarif'})).toBeNull();
  expect(screen.queryByRole('button',{name:'Affecter ce frais'})).toBeNull();
  await userEvent.setup().selectOptions(screen.getByLabelText('Frais dû'),'charge');
  await screen.findByRole('link',{name:'Reçu PDF'});
  expect(screen.queryByRole('button',{name:'Demander une annulation'})).toBeNull();
  expect(screen.queryByLabelText('Montant encaissé')).toBeNull();
});

test('cashier sees collection but cannot configure tariffs or reverse',async()=>{
  mockFinance(['school.finance.read','school.finance.receive']);
  render(<FinancePanel schoolId='school'/>);
  await screen.findByRole('option',{name:/Scolarité/});
  await userEvent.setup().selectOptions(screen.getByLabelText('Frais dû'),'charge');
  await screen.findByLabelText('Montant encaissé');
  expect(screen.queryByRole('button',{name:'Créer le tarif'})).toBeNull();
  expect(screen.queryByRole('button',{name:'Demander une annulation'})).toBeNull();
});

test('pricing delegate sees tariff actions',async()=>{
  mockFinance(['school.finance.read','school.finance.manage']);
  render(<FinancePanel schoolId='school'/>);
  await screen.findByRole('button',{name:'Créer le tarif'});
  expect(screen.getByRole('button',{name:'Affecter ce frais'})).toBeTruthy();
});

test("le responsable des tarifs peut modifier l’échéance des tranches déjà affectées", async () => {
  const schedule = {id:"fee",year:"year",label:"Scolarité – tranche 2",
    amount:"50000",currency:"XAF",due_date:"2026-12-05",revision:3};
  const fetchMock = vi.fn(async (path, options) => {
    if (path.endsWith("my-access")) return Response.json({permissions:["school.finance.manage"]});
    if (options?.method === "PATCH") return Response.json({...schedule,rescheduled_charges:2});
    return Response.json({years:[{id:"year",name:"2026-2027",active:true}],classes:[],schedules:[schedule]});
  });
  vi.stubGlobal("fetch",fetchMock);
  render(<FinancePanel schoolId="school" mode="settings"/>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button",{name:"Modifier l’échéance"}));
  fireEvent.change(screen.getByLabelText("Nouvelle date d’échéance"),{target:{value:"2026-12-15"}});
  await user.click(screen.getByRole("button",{name:"Enregistrer l’échéance"}));
  expect(await screen.findByText("Échéance enregistrée pour 2 frais en attente.")).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledWith("/api/v1/schools/school/finance/schedules/fee",
    expect.objectContaining({method:"PATCH",body:JSON.stringify({
      due_date:"2026-12-15",revision:3,reschedule_open_charges:true,
    })}));
});
