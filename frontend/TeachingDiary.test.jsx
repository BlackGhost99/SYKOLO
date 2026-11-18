// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TeachingDiary, {FamilyTeachingDiary} from "./TeachingDiary.jsx";
import {ContextReadOnly} from "./ContextMenu.jsx";

afterEach(()=>cleanup());

test("saisie d'une séance et publication explicite",async()=>{
  const api=vi.fn(async(path, body)=>{
    if(path.includes("?year="))return {courses:[{id:"course",subject:"Maths",classroom:"6e A",year_name:"2026"}]};
    if(body)return {id:body.id,revision:1};
    return {entries:[],writable:true};
  });
  render(<TeachingDiary schoolId="school" yearId="year" api={api}/>);
  const user=userEvent.setup();
  await screen.findByRole("heading",{name:"Nouvelle séance"});
  fireEvent.change(screen.getByLabelText("Date du cours"),{target:{value:"2026-11-17"}});
  await user.type(screen.getByLabelText("Titre du cours"),"Fractions");
  await user.type(screen.getByLabelText("Contenu de la séance"),"Comparer les fractions");
  await user.type(screen.getByLabelText("Travail à faire (facultatif)"),"Exercice 1");
  fireEvent.change(screen.getByLabelText("Échéance du devoir"),{target:{value:"2026-11-20"}});
  await user.click(screen.getByRole("checkbox",{name:"Publier pour les familles de cette classe"}));
  await user.click(screen.getByRole("button",{name:"Enregistrer et publier"}));
  await screen.findByText("Séance publiée aux familles.");
  const call=api.mock.calls.find(([,body])=>body);
  expect(call[0]).toBe("schools/school/diary/courses/course");
  expect(call[1]).toEqual({id:expect.any(String),day:"2026-11-17",title:"Fractions",lesson:"Comparer les fractions",homework:"Exercice 1",due_on:"2026-11-20",published:true});
  expect(call[2]).toBe("POST");
});

test("famille: le cahier est en consultation et rattaché à l'enfant et à l'année",async()=>{
  const api=vi.fn(async()=>({entries:[{id:"entry",day:"2026-11-17",title:"Fractions",subject:"Maths",classroom:"6e A",lesson:"Comparer les fractions",homework:"Exercice 1",due_on:"2026-11-20",resources:[{id:"file",filename:"exercices.txt",size:100}]}]}));
  render(<FamilyTeachingDiary api={api} childBase="parents/children/child" year="year"/>);
  await screen.findByText("Fractions");
  expect(screen.getByText("Exercice 1")).toBeTruthy();
  expect(screen.getByRole("link",{name:"exercices.txt"}).getAttribute("href")).toBe("/api/v1/parents/children/child/diary/resources/file?year=year");
  expect(screen.queryByRole("button",{name:"Modifier la séance"})).toBeNull();
  expect(api).toHaveBeenCalledWith("parents/children/child/diary?year=year");
});

test("les filtres classe et matière ne sélectionnent que des cours autorisés, dans les deux espaces",async()=>{
  const api=vi.fn(async(path)=>path.includes("?year=")?{courses:[
    {id:"a-maths",classroom_id:"a",classroom:"6e A",subject:"Maths",year:"year",year_name:"2026"},
    {id:"a-fr",classroom_id:"a",classroom:"6e A",subject:"Français",year:"year",year_name:"2026"},
    {id:"b-maths",classroom_id:"b",classroom:"6e B",subject:"Maths",year:"year",year_name:"2026"}
  ]}:{entries:[],writable:true});
  render(<TeachingDiary schoolId="school" yearId="year" api={api} audience="teacher"/>);
  await screen.findByRole("heading",{name:"Nouvelle séance"});
  const user=userEvent.setup();
  expect(screen.getByLabelText("Matière").options.length).toBe(3);
  await user.selectOptions(screen.getByLabelText("Classe"),screen.getByRole("option",{name:"6e B"}).value);
  await screen.findByRole("heading",{name:"6e B · Maths"});
  expect(screen.getByLabelText("Matière").options.length).toBe(2);
  expect(api).toHaveBeenCalledWith("schools/school/diary/courses/b-maths");
  expect(screen.getByRole("heading",{name:"Mes séances"})).toBeTruthy();
});

test("historique filtrable par texte, statut et date; édition existante",async()=>{
  const api=vi.fn(async(path)=>path.includes("?year=")?{courses:[{id:"course",subject:"Maths",classroom:"6e A",year_name:"2026"}]}:{writable:true,entries:[
    {id:"one",revision:2,published:true,title:"Géométrie",day:"2026-11-17",lesson:"Triangles",subject:"Maths",classroom:"6e A",homework:"",resources:[]},
    {id:"two",revision:1,published:false,title:"Fractions",day:"2026-11-16",lesson:"Exercices",subject:"Maths",classroom:"6e A",homework:"",resources:[]}
  ]});
  render(<TeachingDiary schoolId="school" yearId="year" api={api}/>);
  await screen.findByRole("heading",{name:"Géométrie"});
  const user=userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Statut"),"draft");
  expect(screen.queryByRole("heading",{name:"Géométrie"})).toBeNull();
  await user.click(screen.getByRole("button",{name:"Modifier la séance"}));
  expect(screen.getByLabelText("Titre du cours").value).toBe("Fractions");
  await user.selectOptions(screen.getByLabelText("Statut"),"all");
  await user.type(screen.getByLabelText("Rechercher une séance"),"geometrie");
  expect(screen.queryByRole("heading",{name:"Fractions"})).toBeNull();
  expect(screen.getByRole("heading",{name:"Géométrie"})).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Date de séance"),{target:{value:"2026-11-16"}});
  expect(screen.getByText(/Aucune séance ne correspond/)).toBeTruthy();
});

test("clic droit et trois points ouvrent le menu de la séance filtrée; duplication sans publication ni envoi",async()=>{
  const api=vi.fn(async(path)=>path.includes("?year=")?{courses:[{id:"course",subject:"Maths",classroom:"6e A",year_name:"2026"}]}:{writable:true,entries:[
    {id:"one",revision:2,published:true,title:"Géométrie",day:"2026-11-17",lesson:"Triangles",subject:"Maths",classroom:"6e A",homework:"Exercice",due_on:"2026-11-20",resources:[]},
    {id:"two",revision:1,published:false,title:"Fractions",day:"2026-11-16",lesson:"Exercices",subject:"Maths",classroom:"6e A",homework:"",resources:[]}
  ]});
  render(<TeachingDiary schoolId="school" yearId="year" api={api}/>);
  await screen.findByRole("heading",{name:"Géométrie"});
  const user=userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Statut"),"published");
  fireEvent.contextMenu(screen.getByRole("heading",{name:"Géométrie"}));
  fireEvent.click(screen.getByRole("menuitem",{name:"Dupliquer en nouveau brouillon"}));
  expect(screen.getByLabelText("Titre du cours").value).toBe("Géométrie");
  expect(screen.getByLabelText("Échéance du devoir").value).toBe("");
  expect(screen.getByRole("checkbox",{name:"Publier pour les familles de cette classe"}).checked).toBe(false);
  expect(api.mock.calls.every(([,body])=>!body)).toBe(true);
  fireEvent.click(screen.getByRole("button",{name:"Ouvrir les actions contextuelles"}));
  expect(screen.getByRole("menuitem",{name:"Modifier la séance"})).toBeTruthy();
});
test("lecture seule commerciale: séances et statuts visibles, aucune action d'écriture",async()=>{
  const api=vi.fn(async(path)=>path.includes("?year=")?{courses:[{id:"course",subject:"Maths",classroom:"6e A",year_name:"2026"}]}:{writable:true,entries:[
    {id:"one",revision:2,published:true,title:"Géométrie",day:"2026-11-17",lesson:"Triangles",subject:"Maths",classroom:"6e A",homework:"",resources:[]}
  ]});
  render(<ContextReadOnly.Provider value={true}><TeachingDiary schoolId="school" yearId="year" api={api}/></ContextReadOnly.Provider>);
  await screen.findByRole("heading",{name:"Géométrie"});
  expect(screen.queryByRole("button",{name:"Modifier la séance"})).toBeNull();
  expect(screen.queryByRole("button",{name:"Ouvrir les actions contextuelles"})).toBeNull();
  expect(screen.queryByRole("button",{name:"Enregistrer le brouillon"})).toBeNull();
  expect(fireEvent.contextMenu(screen.getByRole("heading",{name:"Géométrie"}))).toBe(true);
});
