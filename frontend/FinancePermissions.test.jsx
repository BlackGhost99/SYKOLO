// @vitest-environment jsdom
import React from 'react';
import {afterEach,expect,test,vi} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
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

test('the audited tariff intervention edits an existing schedule with revision but cannot bill',async()=>{
  let schedule={id:'schedule',year:'year',classroom:null,label:'Mensualité',amount:'25000.00',currency:'XAF',revision:4};
  const fetchMock=vi.fn(async (path, options)=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>{
    if(String(path).endsWith('my-access'))return {permissions:['school.finance.read'],platform_tariff_intervention:true};
    if(options?.method==='PATCH'){
      expect(String(path)).toContain('/finance/schedules/schedule');
      expect(JSON.parse(options.body)).toEqual({revision:4,amount:'30000'});
      schedule={...schedule,amount:'30000.00',revision:5};
      return schedule;
    }
    return {years:[{id:'year',name:'Année',active:true}],classes:[],schedules:[schedule]};
  }}));
  vi.stubGlobal('fetch',fetchMock);
  render(<FinancePanel schoolId='school' mode='settings' workingYearId='year'/>);
  const user=userEvent.setup();
  await user.click(await screen.findByRole('button',{name:'Modifier le montant'}));
  const input=screen.getByLabelText('Nouveau montant (XAF)');
  await user.clear(input);
  await user.type(input,'30000');
  await user.click(screen.getByRole('button',{name:'Enregistrer le montant'}));
  expect(await screen.findByText(/30000.00 XAF/)).toBeTruthy();
  expect(screen.queryByRole('button',{name:'Affecter ce frais'})).toBeNull();
});

test('tariff intervention does not expose billing controls in the full finance view',async()=>{
  vi.stubGlobal('fetch',vi.fn(async path=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>{
    if(String(path).endsWith('my-access'))return {permissions:['school.finance.read'],platform_tariff_intervention:true};
    return {years:[],classes:[],enrollments:[],students:[],schedules:[],charges:[]};
  }})));
  render(<FinancePanel schoolId='school'/>);
  await screen.findByRole('heading',{name:'Frais scolaires et caisse'});
  expect(screen.queryByRole('button',{name:'Créer le tarif'})).toBeNull();
  expect(screen.queryByRole('button',{name:'Affecter ce frais'})).toBeNull();
});

test('tariff settings edit the deadline without rescheduling existing student charges',async()=>{
  let schedule={id:'schedule',year:'year',classroom:null,label:'Mensualité',amount:'25000.00',currency:'XAF',revision:4,due_date:'2026-10-05'};
  const fetchMock=vi.fn(async (path,options)=>({ok:true,headers:{get:()=> 'application/json'},json:async()=>{
    if(String(path).endsWith('my-access'))return {permissions:['school.finance.read'],platform_tariff_intervention:true};
    if(options?.method==='PATCH'){
      const data=JSON.parse(options.body);
      expect(data).toEqual({revision:4,due_date:'2026-10-10'});
      schedule={...schedule,...data,revision:5};
      return schedule;
    }
    return {years:[{id:'year',name:'Année',active:true}],classes:[],schedules:[schedule]};
  }}));
  vi.stubGlobal('fetch',fetchMock);
  render(<FinancePanel schoolId='school' mode='settings' workingYearId='year'/>);
  const user=userEvent.setup();
  await user.click(await screen.findByRole('button',{name:'Modifier l’échéance'}));
  const field=screen.getByLabelText('Nouvelle date d’échéance');
  await user.clear(field);
  await user.type(field,'2026-10-10');
  await user.click(screen.getByRole('button',{name:'Enregistrer l’échéance'}));
  expect(await screen.findByText(/Échéance : 2026-10-10/)).toBeTruthy();
});
