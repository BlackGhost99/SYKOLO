// @vitest-environment jsdom
import React from "react";
import {cleanup, render, screen, within, waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach, expect, test, vi} from "vitest";
import SchoolDashboard from "./SchoolDashboard.jsx";

afterEach(()=>{
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("un professeur accède à ses évaluations sans permission scolaire globale", async()=>{
  vi.spyOn(window, "scrollTo").mockImplementation(()=>{});
  const school={id:"lycee-test",name:"Lycée Privé 2"};
  const root="/api/v1/schools/lycee-test/";
  const year={id:"2026-27",name:"2026-2027",active:true};
  const assignedCourse={id:"math-s",year:year.id,classroom:"seconde-s",
    subject:"math",active:true,coefficient:"2"};
  const fetchMock=vi.fn(async url=>Response.json({
    "/api/v1/schools":{schools:[school]},
    [root+"my-access"]:{school,role:"enseignant",
      permissions:["school.view","school.academic.read","school.curriculum.read",
        "school.timetable.read","school.settings.read"]},
    [root+"academic/annual-snapshot"]:{year,years:[year]},
    [root+"academic/annual-snapshot?year=2026-27"]:{year,years:[year]},
    [root+"organization/my-appointments"]:{appointments:[]},
    [root+"curriculum/my-courses"]:{courses:[assignedCourse]},
    [root+"courses"]:{courses:[assignedCourse,
      {id:"autre-cours-interdit",year:year.id,classroom:"terminal-c",
       subject:"phy",active:true,coefficient:"2"}]},
    [root+"academic/periods"]:{periods:[]},
    [root+"subjects"]:{subjects:[{id:"math",name:"Mathématiques"}]},
    [root+"academic/classes"]:{classes:[
      {id:"seconde-s",year:year.id,name:"Seconde S",active:true},
      {id:"terminal-c",year:year.id,name:"Terminale C",active:true},
    ]},
    [root+"academic/years"]:{years:[year]},
  }[url] || {}));
  vi.stubGlobal("fetch",fetchMock);
  const user=userEvent.setup();
  render(<SchoolDashboard user={{username:"enseignant"}}/>);
  const nav=await screen.findByRole("navigation",{name:"Navigation principale"});
  const access=await within(nav).findByRole("button",{name:"Évaluations et notes"});
  await user.click(access);
  expect(await screen.findByRole("heading",{name:"Évaluations et saisie des notes"})).toBeTruthy();
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledWith(root+"curriculum/my-courses",expect.anything()));
  expect(fetchMock.mock.calls.some(([url])=>url===root+"courses")).toBe(false);
  expect(screen.queryByText("Vous n'avez pas l'autorisation de consulter les évaluations")).toBeNull();
});
