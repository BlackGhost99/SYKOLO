// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CourseProgress from "./CourseProgress.jsx";

afterEach(()=>cleanup());
test("progression réelle et chapitre dispensé déclaré avec séance justificative",async()=>{
 const api=vi.fn(async(_path,body)=>body?{revision:1}:{
   units:[{id:"unit",title:"Fractions",objectives:"Comparer",active:true,status:"not_started",revision:0,planned_start:null,planned_end:"2026-11-10",completed_on:null,evidence:null,overdue:true}],
   writable:true,summary:{total:1,completed:0,in_progress:0,overdue:1,unplanned:0,completed_late:0,percent:0},year_start:"2026-09-01",year_end:"2027-07-31",
 });
 const user=userEvent.setup();
 render(<CourseProgress schoolId="school" course="course" entries={[{id:"entry",day:"2026-11-15",title:"Fractions"}]} api={api}/>);
 await screen.findByText("0 / 1 chapitres dispensés · 0 %");
 await user.selectOptions(screen.getByLabelText("Avancement"),"completed");
 fireEvent.change(screen.getByLabelText("Date effective"),{target:{value:"2026-11-17"}});
 await user.selectOptions(screen.getByLabelText("Séance justificative (facultatif)"),"entry");
 await user.click(screen.getByRole("button",{name:"Enregistrer la progression"}));
 await screen.findByText("Progression enregistrée.");
 expect(api).toHaveBeenCalledWith("schools/school/diary/courses/course/progress",{unit:"unit",revision:0,planned_start:null,planned_end:"2026-11-10",status:"completed",completed_on:"2026-11-17",evidence:"entry"},"PATCH");
});
