// @vitest-environment jsdom
import React from "react";
import {cleanup,render,screen,within} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,expect,test,vi} from "vitest";
import {BrandContext,PageHeader,Shell} from "./yem-ui.jsx";
import {SchoolHeaderBanner,SchoolHeaderSearch,DashboardShortcuts} from "./SchoolDashboardHeader.jsx";
afterEach(cleanup);

test("branding is in the shared header only, with the configured school logo",()=>{
  const brand={name:"Lycée test",city:"Libreville",logo:"/logo.png",banner:"/banner.jpg",fixedHeader:true};
  render(<BrandContext.Provider value={brand}><Shell headerBanner={<SchoolHeaderBanner brand={brand}/>}><PageHeader title="Tableau de bord"/></Shell></BrandContext.Provider>);
  const header=screen.getByRole("banner");
  expect(within(header).getByAltText("Logo de l’établissement").getAttribute("src")).toBe("/logo.png");
  expect(within(header).getByText("Lycée test")).toBeTruthy();
  expect(screen.getAllByAltText("Logo de l’établissement")).toHaveLength(1);
  expect(screen.getByRole("heading",{name:"Tableau de bord"})).toBeTruthy();
});

test("search icon opens accessible school navigation and forwards student query",async()=>{
  const navigate=vi.fn(),user=userEvent.setup();
  render(<SchoolHeaderSearch nav={[["students","users","Élèves"],["payments","wallet","Paiements"]]} canSearchStudents onNavigate={navigate}/>);
  const toggle=screen.getByRole("button",{name:"Rechercher dans l’établissement"});
  await user.click(toggle);
  const input=screen.getByLabelText("Rechercher",{exact:true});
  expect(document.activeElement).toBe(input);
  await user.type(input,"Ndong");
  await user.click(screen.getByRole("button",{name:"Rechercher « Ndong » dans les élèves"}));
  expect(navigate).toHaveBeenCalledWith("students","live",{query:"Ndong"});
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  await user.click(toggle);
  await user.keyboard("{Escape}");
  expect(document.activeElement).toBe(toggle);
});

test("search without pupil permissions lists only supplied modules",async()=>{
  const navigate=vi.fn(),user=userEvent.setup();
  render(<SchoolHeaderSearch nav={[["bulletins","file","Évaluations et notes"]]} canSearchStudents={false} onNavigate={navigate}/>);
  await user.click(screen.getByRole("button",{name:"Rechercher dans l’établissement"}));
  expect(screen.queryByRole("button",{name:/dans les élèves/})).toBeNull();
  await user.click(screen.getByRole("button",{name:"Évaluations et notes"}));
  expect(navigate).toHaveBeenCalledWith("bulletins","",null);
});

test("shortcut cards navigate to exact tabs and do not add forbidden modules",async()=>{
  const navigate=vi.fn(),user=userEvent.setup();
  render(<DashboardShortcuts items={[{id:"bulletins",tab:"reports",icon:"file",title:"Bulletins",subtitle:"Consultation"}]} onNavigate={navigate}/>);
  const nav=screen.getByRole("navigation",{name:"Raccourcis du tableau de bord"});
  expect(within(nav).queryByText("Paiements")).toBeNull();
  await user.click(within(nav).getByRole("button",{name:/Bulletins/}));
  expect(navigate).toHaveBeenCalledWith("bulletins","reports");
});
