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
    if(String(path).includes('finance/quality')) return {certified_revenue:false,currencies:{XAF:{legacy_cash_unverified:{count:2,amount:'5000.00'},explicit_demo_payments:{count:1,amount:'1000.00'},explicit_demo_charges:{count:1,net_amount:'1000.00'}}}};
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

test('finance quality warning exposes unverified historical cash without labeling it real',async()=>{
  mockFinance(['school.finance.read']);
  render(<FinancePanel schoolId='school'/>);
  const quality=await screen.findByLabelText('Contrôle de qualité des écritures financières');
  expect(quality.textContent).toContain('à vérifier');
  expect(quality.textContent).toContain('5000.00 XAF');
  expect(quality.textContent).toContain('explicitement fictif');
});
