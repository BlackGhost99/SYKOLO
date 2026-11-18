// @vitest-environment jsdom
import React from 'react';
import {afterEach,expect,test,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {ContextTarget,ContextTrigger,ContextReadOnly} from './ContextMenu.jsx';
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
const action=(id,run=vi.fn(),extra={})=>({id,label:id,run,...extra});

test('ouvrir au clavier un autre menu ferme le précédent',()=>{
  render(<><ContextTarget actions={[action('A')]}>A</ContextTarget><ContextTarget actions={[action('B')]}>B</ContextTarget></>);
  fireEvent.contextMenu(screen.getByText('A'));
  fireEvent.keyDown(screen.getByText('B'),{key:'ContextMenu'});
  expect(screen.getAllByRole('menu')).toHaveLength(1);expect(screen.getByRole('menuitem').textContent).toBe('B');
});

test('menu et focus restent dans le dialogue modal',()=>{
  render(<dialog open><ContextTarget showTrigger actions={[action('Dossier')]}>Élève</ContextTarget></dialog>);
  const trigger=screen.getByRole('button',{name:'Ouvrir les actions contextuelles'});fireEvent.click(trigger);
  expect(screen.getByRole('menu').closest('dialog')).toBeTruthy();
  expect(trigger.getAttribute('aria-controls')).toBe(screen.getByRole('menu').id);
  fireEvent.keyDown(screen.getByRole('menuitem'),{key:'Escape'});
  expect(document.activeElement).toBe(trigger);
});

test('un double clic ne peut pas invoquer deux fois une action',()=>{
  const run=vi.fn();render(<ContextTarget actions={[action('Ouvrir',run)]}>Dossier</ContextTarget>);
  fireEvent.contextMenu(screen.getByText('Dossier'));const item=screen.getByRole('menuitem');
  fireEvent.click(item);fireEvent.click(item);expect(run).toHaveBeenCalledTimes(1);
});

test('la révision courante des actions est utilisée et les actions retirées restent inaccessibles',()=>{
  const old=vi.fn(),fresh=vi.fn();const {rerender}=render(<ContextTarget actions={[action('Ouvrir',old)]}>Dossier</ContextTarget>);
  fireEvent.contextMenu(screen.getByText('Dossier'));
  rerender(<ContextTarget actions={[action('Ouvrir',fresh)]}>Dossier</ContextTarget>);
  fireEvent.click(screen.getByRole('menuitem'));expect(old).not.toHaveBeenCalled();expect(fresh).toHaveBeenCalledTimes(1);
  fireEvent.contextMenu(screen.getByText('Dossier'));const stale=screen.getByRole('menuitem');
  rerender(<ContextTarget actions={[]}>Dossier</ContextTarget>);fireEvent.click(stale);expect(fresh).toHaveBeenCalledTimes(1);
});

test('le défilement interne reste possible, le défilement viewport ferme sans exception',()=>{
  render(<ContextTarget actions={[action('Ouvrir')]}>Dossier</ContextTarget>);
  fireEvent.contextMenu(screen.getByText('Dossier'));fireEvent.scroll(screen.getByRole('menu'));
  expect(screen.getByRole('menu')).toBeTruthy();fireEvent.scroll(window);expect(screen.queryByRole('menu')).toBeNull();
});

test('placement dans le visualViewport et fermeture lors du zoom mobile',()=>{
  const viewport=new EventTarget();Object.assign(viewport,{width:320,height:480,offsetLeft:30,offsetTop:40});
  vi.stubGlobal('visualViewport',viewport);
  const original=HTMLElement.prototype.getBoundingClientRect;
  vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockImplementation(function(){return this.getAttribute('role')==='menu'?{width:200,height:160}:original.call(this);});
  render(<ContextTarget actions={[action('Ouvrir')]}>Dossier</ContextTarget>);
  fireEvent.contextMenu(screen.getByText('Dossier'),{clientX:999,clientY:999});
  expect(screen.getByRole('menu').style.left).toBe('142px');expect(screen.getByRole('menu').style.top).toBe('352px');
  fireEvent(viewport,new Event('resize'));expect(screen.queryByRole('menu')).toBeNull();
});

test('zones natives : tous champs, lien, texte sélectionné et opt-out explicite',()=>{
  render(<ContextTarget actions={[action('Ouvrir')]}><input aria-label="Nom"/><textarea aria-label="Note"/><select aria-label="Classe"><option>6e</option></select><div contentEditable suppressContentEditableWarning>Éditable</div><span data-native-context>Natif</span><a href="/pdf">PDF</a><strong>Élève</strong></ContextTarget>);
  for(const node of [screen.getByLabelText('Nom'),screen.getByLabelText('Note'),screen.getByLabelText('Classe'),screen.getByText('Éditable'),screen.getByText('Natif'),screen.getByText('PDF')])expect(fireEvent.contextMenu(node)).toBe(true);
  vi.spyOn(window,'getSelection').mockReturnValue({toString:()=> 'Élève'});
  expect(fireEvent.contextMenu(screen.getByText('Élève'))).toBe(true);expect(screen.queryByRole('menu')).toBeNull();
});

test('navigation clavier complète et retour à un élément extérieur avec Tab',async()=>{
  render(<ContextTarget actions={[action('A'),action('Occupé',vi.fn(),{disabled:true}),action('B')]} showTrigger>Dossier</ContextTarget>);
  const user=userEvent.setup();fireEvent.click(screen.getByRole('button',{name:'Ouvrir les actions contextuelles'}));
  expect(document.activeElement.textContent).toBe('A');await user.keyboard('{ArrowDown}');expect(document.activeElement.textContent).toBe('B');
  await user.keyboard('{Home}');expect(document.activeElement.textContent).toBe('A');await user.keyboard('{End}');expect(document.activeElement.textContent).toBe('B');
  await user.tab();expect(screen.queryByRole('menu')).toBeNull();
});

test('changer la restriction retire toute écriture même avec une ancienne référence',()=>{
  const run=vi.fn();const view=readOnly=><ContextReadOnly.Provider value={readOnly}><ContextTarget actions={[action('Écrire',run,{write:true}),action('Lire')]}>Dossier</ContextTarget></ContextReadOnly.Provider>;
  const {rerender}=render(view(false));fireEvent.contextMenu(screen.getByText('Dossier'));const old=screen.getByRole('menuitem',{name:'Écrire'});
  rerender(view(true));fireEvent.click(old);expect(run).not.toHaveBeenCalled();
});
