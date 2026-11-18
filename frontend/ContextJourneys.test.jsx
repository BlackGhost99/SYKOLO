// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {ContextReadOnly} from "./ContextMenu.jsx";
import {LiveStudents} from "./LiveScreens.jsx";
import {StaffDirectory, FamilyDirectory} from "./SchoolDirectories.jsx";
import TeachingDiary from "./TeachingDiary.jsx";
import FinancialDocuments from "./FinancialDocuments.jsx";
import TimetablePanel from "./TimetablePanel.jsx";

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
const student={id:'ada',first_name:'Ada',last_name:'TEST',active:true,student_code:'001',enrollment:{id:'enrollment',classroom:{id:'class',name:'6e A'}}};

test.each([
  ['secrétariat',false,false],['caisse',true,false],['direction sans délégation de caisse',false,false],['caisse en lecture seule abonnement',true,true],
])('élèves : %s accède seulement à ses raccourcis, sans écrire',async(role,canReceive,readOnly)=>{
  const fetchMock=vi.fn(async()=>Response.json({students:[student],classes:[],metrics:{},sensitive_visible:false,finance_visible:false}));
  vi.stubGlobal('fetch',fetchMock);const navigate=vi.fn();
  render(<ContextReadOnly.Provider value={readOnly}><LiveStudents schoolId="school" canReceive={canReceive} onNavigate={navigate}/></ContextReadOnly.Provider>);
  fireEvent.click(await screen.findByRole('button',{name:'Ouvrir les actions contextuelles'}));
  expect(!!screen.queryByRole('menuitem',{name:'Préparer un encaissement'})).toBe(canReceive&&!readOnly);
  fireEvent.click(screen.getByRole('menuitem',{name:'Ouvrir la fiche'}));
  expect(navigate).toHaveBeenCalledWith('students','fiche',{student:'ada'});
  expect(fetchMock.mock.calls.every(([,options])=>options.method==='GET')).toBe(true);
});

test('caisse : préparer un encaissement cible l’inscription sans effectuer de paiement',async()=>{
  const navigate=vi.fn(),fetchMock=vi.fn(async()=>Response.json({students:[student],classes:[],metrics:{}}));vi.stubGlobal('fetch',fetchMock);
  render(<LiveStudents schoolId="school" canReceive onNavigate={navigate}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Ouvrir les actions contextuelles'}));
  fireEvent.click(screen.getByRole('menuitem',{name:'Préparer un encaissement'}));
  expect(navigate).toHaveBeenCalledWith('payments','live',{enrollment:'enrollment'});
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

test.each([true,false])('personnel : droit dossier %s, aucun accès rémunérations ajouté',async canReadDossiers=>{
  vi.stubGlobal('fetch',vi.fn(async()=>Response.json({staff:[{id:'staff',active:true,first_name:'Ada',last_name:'TEST',position:'Professeur'}]})));
  render(<StaffDirectory schoolId="school" canReadDossiers={canReadDossiers}/>);
  await screen.findByText('Professeur');
  if(canReadDossiers){fireEvent.click(screen.getByRole('button',{name:'Ouvrir les actions contextuelles'}));expect(screen.getAllByRole('menuitem').map(x=>x.textContent)).toEqual(['Consulter la fiche professionnelle']);}
  else expect(screen.queryByRole('button',{name:'Ouvrir les actions contextuelles'})).toBeNull();
});

test('parents : raccourci vers le dossier du bon enfant et conservation des coordonnées',async()=>{
  const navigate=vi.fn();vi.stubGlobal('fetch',vi.fn(async url=>Response.json(
    url.includes('guardians-by-class')?{families:[{student_id:'ada',student_name:'Ada TEST',guardians:[{id:'g',name:'Parent',phone:'01020304'}]}]}:
    url.endsWith('academic/years')?{years:[{id:'year',name:'2026'}]}:{classes:[{id:'class',year:'year',name:'6e A',active:true}]}
  )));
  render(<FamilyDirectory schoolId="school" onNavigate={navigate}/>);
  const select=await screen.findByRole('combobox');
  await screen.findByRole('option',{name:/6e A/});fireEvent.change(select,{target:{value:'class'}});
  fireEvent.click(await screen.findByRole('button',{name:'Ouvrir les actions contextuelles'}));
  fireEvent.click(screen.getByRole('menuitem',{name:'Ouvrir le dossier élève'}));
  expect(navigate).toHaveBeenCalledWith('students','fiche',{student:'ada'});
  expect(screen.getByText('01020304')).toBeTruthy();
});

test.each([[true,false,true],[false,false,false],[true,true,false]])('cahier : cours modifiable=%s, abonnement restreint=%s',async(writable,readOnly,expected)=>{
  const api=vi.fn(async path=>path.endsWith('/courses?year=year')?{courses:[{id:'course',subject:'Maths',classroom:'6e A'}]}:
    {entries:[{id:'entry',revision:1,title:'Fractions',day:'2026-11-17',lesson:'Comparer',homework:'',published:false}],writable});
  render(<ContextReadOnly.Provider value={readOnly}><TeachingDiary schoolId="school" yearId="year" api={api}/></ContextReadOnly.Provider>);
  await screen.findByRole('heading',{name:'Fractions'});
  const trigger=screen.queryByRole('button',{name:'Ouvrir les actions contextuelles'});
  expect(!!trigger).toBe(expected);
  if(expected){fireEvent.click(trigger);fireEvent.click(screen.getByRole('menuitem',{name:'Modifier la séance'}));expect(screen.getByLabelText('Titre du cours').value).toBe('Fractions');}
  expect(api.mock.calls.every(([,body])=>body===undefined)).toBe(true);
});

test('documents : ouvrir et télécharger restent les mêmes liens authentifiés et natifs',async()=>{
  const url='/api/v1/schools/school/finance/invoices/invoice/pdf';
  render(<FinancialDocuments api={async()=>({invoices:[{id:'invoice-id',label:'Scolarité',url}]})} path="documents"/>);
  fireEvent.click(await screen.findByRole('button',{name:'Ouvrir les actions contextuelles'}));
  expect(screen.getAllByRole('menuitem').map(x=>x.textContent)).toEqual(['Ouvrir le PDF · Scolarité · INVOICE-','Télécharger le PDF · Scolarité · INVOICE-']);
  const download=screen.getByRole('link',{name:'Télécharger le PDF · Scolarité · INVOICE-'});
  expect(download.getAttribute('href')).toBe(url);
  fireEvent.keyDown(screen.getByRole('menu'),{key:'Escape'});
  expect(fireEvent.contextMenu(download)).toBe(true);expect(screen.queryByRole('menu')).toBeNull();
});

test.each([[false,true,false],[true,true,true],[true,false,false]])('emploi du temps : gestion=%s, année active=%s',async(canManage,active,enabled)=>{
  vi.stubGlobal('fetch',vi.fn(async url=>Response.json(
    url.endsWith('/academic/years')?{years:[{id:'year',name:'2026',active}]}:
    url.endsWith('/entries')?{entries:[{id:'entry',year:'year',active:true,course:'course',weekday:0,start_time:'08:00',end_time:'09:00'}]}:
    url.endsWith('/courses')?{courses:[{id:'course',subject:'subject'}]}:
    url.endsWith('/subjects')?{subjects:[{id:'subject',name:'Maths'}]}:{}
  )));
  render(<TimetablePanel schoolId="school" canManageTimetable={canManage}/>);
  await screen.findByText('08:00–09:00');
  const trigger=screen.queryByRole('button',{name:'Ouvrir les actions contextuelles'});
  expect(!!trigger).toBe(enabled);
  if(trigger){fireEvent.click(trigger);expect(screen.getByRole('menuitem',{name:'Modifier ou déplacer la séance'}).disabled).toBe(!enabled);}
  expect(screen.queryByRole('menuitem',{name:/Archiver/})).toBeNull();
});
