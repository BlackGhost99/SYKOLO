// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CycleScopeManager from "./CycleScopeManager.jsx";

afterEach(cleanup);

const cycles = [
  {id:"cycle-maternelle",name:"Maternelle"},
  {id:"cycle-primaire",name:"Primaire"},
];
const accounts = [
  {member_id:"g",username:"agent-global",name:"Agent global",access_cycle_ids:null},
  {member_id:"r",username:"agent-primaire",name:"Agent primaire",access_cycle_ids:["cycle-primaire"]},
];

test("le propriétaire voit et peut examiner les accès globaux sans modification automatique",async()=>{
  const user=userEvent.setup();
  render(<CycleScopeManager schoolId="school-test" cycles={cycles} accounts={accounts}/>);
  const notice=screen.getByRole("status");
  expect(notice.textContent).toContain("1 compte(s) non propriétaires sur 2");
  const picker=screen.getByRole("combobox");
  expect(picker.textContent).toContain("Accès global à vérifier");
  await user.selectOptions(picker,"g");
  expect(screen.getByText(/Ce compte possède actuellement un accès global/)).toBeTruthy();
  const globalRadio=screen.getByRole("radio",{name:/Accès global à l'établissement/});
  expect(globalRadio.checked).toBe(true);
  expect(screen.getByRole("button",{name:"Enregistrer les cycles autorisés"}).disabled).toBe(true);
});

test("une école avec un seul cycle n'affiche pas de fausse alerte",()=>{
  render(<CycleScopeManager schoolId="school-simple" cycles={cycles.slice(0,1)} accounts={accounts}/>);
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.getByRole("combobox").textContent).not.toContain("Accès global à vérifier");
});
