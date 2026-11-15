// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,render,screen,fireEvent} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MonthlyTariffSetup from "./MonthlyTariffSetup.jsx";
afterEach(cleanup);
test("a cycle can generate a single batch with selected classes and months",async()=>{
  const onGenerate=vi.fn();
  const user=userEvent.setup();
  render(<MonthlyTariffSetup year="2026" classes={[
    {id:"a",name:"Première année A",cycle_name:"Primaire"},
    {id:"b",name:"Deuxième année A",cycle_name:"Primaire"},
    {id:"c",name:"Sixième",cycle_name:"Collège"},
  ]} onGenerate={onGenerate}/>);
  const submit=screen.getByRole("button",{name:"Générer les mensualités"});
  expect(submit.disabled).toBe(true);
  await user.click(screen.getByLabelText("Cycle : Primaire"));
  fireEvent.change(screen.getByLabelText("Montant mensuel (FCFA)"),{target:{value:"20000"}});
  fireEvent.change(screen.getByLabelText("Premier mois"),{target:{value:"2026-10"}});
  fireEvent.change(screen.getByLabelText("Dernier mois"),{target:{value:"2027-06"}});
  expect(submit.disabled).toBe(false);
  await user.click(submit);
  expect(onGenerate).toHaveBeenCalledWith({year:"2026",classrooms:["a","b"],amount:"20000",
    first_month:"2026-10",last_month:"2027-06",due_day:5});
});
