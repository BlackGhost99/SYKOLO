// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,test,vi} from "vitest";
import {act,cleanup,render,screen} from "@testing-library/react";
import YemFamilles from "./YemFamilles.jsx";
vi.mock("./YemFamillesFidele.jsx",()=>({default:({m})=><div aria-label="Identité école">{m.schoolBrand?.logo||"Sans logo"} | {m.schoolBrand?.banner||"Sans bannière"}</div>}));
afterEach(cleanup);
const children=[{student:"child-a",school:"a",first_name:"A",last_name:"Test"},{student:"child-b",school:"b",first_name:"B",last_name:"Test"}];
const brand=(id,logo="/api/v1/schools/"+id+"/branding/logo?v=2")=>({school_id:id,logo_url:logo,banner_url:"/api/v1/schools/"+id+"/branding/banner?v=2"});
test("only the currently selected linked school branding is shown; late replies are ignored",async()=>{
  let resolveA;
  const api=vi.fn(path=>path==="schools/a/branding"?new Promise(resolve=>{resolveA=resolve;}):Promise.resolve(path==="schools/b/branding"?brand("b"):{enrollments:[],notifications:[]}));
  const props={api,children,setSelected:vi.fn()};
  const {rerender}=render(<YemFamilles {...props} selected="child-a"/>);
  rerender(<YemFamilles {...props} selected="child-b"/>);
  expect(await screen.findByText(/schools\/b\/branding\/logo/)).toBeTruthy();
  await act(async()=>resolveA(brand("a")));
  expect(screen.getByLabelText("Identité école").textContent).toContain("/schools/b/");
  expect(screen.getByLabelText("Identité école").textContent).not.toContain("/schools/a/");
  rerender(<YemFamilles {...props} selected=""/>);
  expect(screen.getByLabelText("Identité école").textContent).toContain("Sans logo");
});
test("rejects external branding URLs and mismatched school metadata",async()=>{
  const api=vi.fn(path=>Promise.resolve(path==="schools/a/branding"?brand("a","https://example.test/logo"):path==="schools/b/branding"?brand("a"):{enrollments:[],notifications:[]}));
  const props={api,children,setSelected:vi.fn()};
  const {rerender}=render(<YemFamilles {...props} selected="child-a"/>);
  await screen.findByText(/schools\/a\/branding\/banner/);
  expect(screen.getByLabelText("Identité école").textContent).toContain("Sans logo");
  rerender(<YemFamilles {...props} selected="child-b"/>);
  await act(async()=>{});
  expect(screen.getByLabelText("Identité école").textContent).toBe("Sans logo | Sans bannière");
});
