// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import {ContextTarget,ContextTrigger,ContextReadOnly} from "./ContextMenu.jsx";
import {Table} from "./yem-ui.jsx";
afterEach(()=>cleanup());
const action=(run,extra={})=>({id:"open",label:"Ouvrir le dossier",run,...extra});
test("clic droit, action unique et sélection de la bonne ligne",()=>{
  const first=vi.fn(), second=vi.fn();
  render(<><ContextTarget actions={[action(first)]}>Élève A</ContextTarget><ContextTarget actions={[action(second)]}>Élève B</ContextTarget></>);
  fireEvent.contextMenu(screen.getByText("Élève B"),{clientX:20,clientY:30});
  fireEvent.click(screen.getByRole("menuitem",{name:"Ouvrir le dossier"}));
  expect(first).not.toHaveBeenCalled();expect(second).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("menu")).toBeNull();
});
test("clavier, bouton tactile, Échap et retour du focus",()=>{
  render(<ContextTarget actions={[action(vi.fn())]}>Dossier<ContextTrigger/></ContextTarget>);
  const trigger=screen.getByRole("button",{name:"Ouvrir les actions contextuelles"});
  fireEvent.click(trigger);expect(screen.getByRole("menu")).toBeTruthy();
  fireEvent.keyDown(screen.getByRole("menuitem"),{key:"Escape"});
  expect(screen.queryByRole("menu")).toBeNull();expect(document.activeElement).toBe(trigger);
  fireEvent.keyDown(trigger,{key:"F10",shiftKey:true});expect(screen.getByRole("menu")).toBeTruthy();
});
test("préserve la sélection native dans un champ et un lien",()=>{
  render(<ContextTarget actions={[action(vi.fn())]}><input aria-label="Texte"/><a href="#recu">Reçu</a></ContextTarget>);
  expect(fireEvent.contextMenu(screen.getByLabelText("Texte"))).toBe(true);
  expect(fireEvent.contextMenu(screen.getByText("Reçu"))).toBe(true);
  expect(screen.queryByRole("menu")).toBeNull();
});
test("lecture seule masque les écritures, actions désactivées non exécutables",()=>{
  const run=vi.fn();
  render(<ContextReadOnly.Provider value={true}><ContextTarget showTrigger actions={[
    action(run,{write:true}),{id:"read",label:"Consulter",run},
    {id:"busy",label:"Indisponible",run,disabled:true}
  ]}>Dossier</ContextTarget></ContextReadOnly.Provider>);
  fireEvent.contextMenu(screen.getByText("Dossier"));
  expect(screen.queryByRole("menuitem",{name:"Ouvrir le dossier"})).toBeNull();
  expect(screen.getByRole("menuitem",{name:"Indisponible"}).disabled).toBe(true);
  expect(run).not.toHaveBeenCalled();
});
test("fermeture extérieure et aucun menu vide",()=>{
  render(<><ContextTarget actions={[action(vi.fn())]}>A</ContextTarget><ContextTarget actions={[]}>B</ContextTarget></>);
  fireEvent.contextMenu(screen.getByText("A"));
  fireEvent.pointerDown(screen.getByText("B"));expect(screen.queryByRole("menu")).toBeNull();
  expect(fireEvent.contextMenu(screen.getByText("B"))).toBe(true);
});

test("Table : le raccourci suit l'identifiant lors d'un filtrage et d'un tri",()=>{
  const run=vi.fn();
  const table=values=><Table headers={["Élève","Classe"]} rows={values.map(id=>[id,"6e"])}
    rowKey={(_,i)=>values[i]}
    rowActions={(_,i)=>[{id:"file",label:"Ouvrir",run:()=>run(values[i])}]}/>;
  const {rerender}=render(table(["A","B"]));
  fireEvent.contextMenu(screen.getByText("A"));
  rerender(table(["B","A"]));
  fireEvent.click(screen.getByRole("menuitem",{name:"Ouvrir"}));
  expect(run).toHaveBeenCalledTimes(1);expect(run).toHaveBeenCalledWith("A");
});
test("un changement de restriction pendant l'ouverture interdit l'action d'écriture",()=>{
  const write=vi.fn(),read=vi.fn();
  const view=restricted=><ContextReadOnly.Provider value={restricted}>
    <ContextTarget actions={[action(write,{write:true}),{id:"read",label:"Consulter",run:read}]}>Écriture</ContextTarget>
  </ContextReadOnly.Provider>;
  const {rerender}=render(view(false));
  fireEvent.contextMenu(screen.getByText("Écriture"));
  rerender(view(true));
  expect(screen.queryByRole("menuitem",{name:"Ouvrir le dossier"})).toBeNull();
  expect(write).not.toHaveBeenCalled();
});
test("le menu n'intercepte pas le clic gauche, ni ne soumet le formulaire",()=>{
  const submit=vi.fn(e=>e.preventDefault()),run=vi.fn();
  render(<ContextTarget as="form" showTrigger actions={[action(run)]} onSubmit={submit}>
    <button type="submit">Enregistrer</button>
  </ContextTarget>);
  fireEvent.click(screen.getByRole("button",{name:"Ouvrir les actions contextuelles"}));
  fireEvent.click(screen.getByRole("menuitem"));
  expect(submit).not.toHaveBeenCalled();expect(run).toHaveBeenCalledTimes(1);
});
