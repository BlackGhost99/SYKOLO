// @vitest-environment jsdom
import React from "react";
import {afterEach, expect, test, vi} from "vitest";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TeachingDiary, {FamilyTeachingDiary} from "./TeachingDiary.jsx";

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
  const api=vi.fn(async()=>({entries:[{id:"entry",day:"2026-11-17",title:"Fractions",subject:"Maths",classroom:"6e A",lesson:"Comparer les fractions",homework:"Exercice 1",due_on:"2026-11-20"}]}));
  render(<FamilyTeachingDiary api={api} childBase="parents/children/child" year="year"/>);
  await screen.findByText("Fractions");
  expect(screen.getByText("Exercice 1")).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Modifier la séance"})).toBeNull();
  expect(api).toHaveBeenCalledWith("parents/children/child/diary?year=year");
});
