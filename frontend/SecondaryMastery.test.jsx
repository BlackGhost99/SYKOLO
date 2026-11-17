// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SecondaryMastery from "./SecondaryMastery.jsx";

afterEach(()=>cleanup());
test("enregistre une remédiation sans marquer la compétence acquise",async()=>{
 const api=vi.fn(async(path,body)=>body?{...body,revision:1}:path.includes("?enrollment=")?{
   units:[{id:"unit",active:true,title:"Géométrie",objectives:"Construire",mark:null}],writable:true,year_start:"2026-09-01",year_end:"2027-07-31"
 }:{students:[{id:"enrollment",name:"Élève test"}]});
 const user=userEvent.setup();
 render(<SecondaryMastery schoolId="school" course="course" api={api}/>);
 await user.selectOptions(await screen.findByLabelText("Élève"),"enrollment");
 await screen.findByText("Géométrie");
 await user.selectOptions(screen.getByLabelText("Maîtrise"),"not_yet");
 await user.type(screen.getByLabelText("Action de remédiation"),"Exercices ciblés");
 await user.selectOptions(screen.getByLabelText("État de la remédiation"),"planned");
 fireEvent.change(screen.getByLabelText("Échéance"),{target:{value:"2026-11-20"}});
 await user.click(screen.getByRole("button",{name:"Enregistrer le suivi"}));
 await screen.findByText("Suivi enregistré.");
 expect(api).toHaveBeenCalledWith("schools/school/diary/courses/course/remediation",{unit:"unit",enrollment:"enrollment",revision:0,stage:"not_yet",action:"Exercices ciblés",action_status:"planned",due_on:"2026-11-20"},"PATCH");
});
