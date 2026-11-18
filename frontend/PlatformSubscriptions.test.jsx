// @vitest-environment jsdom
import React from "react";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,expect,test,vi} from "vitest";
import PlatformSubscriptions from "./PlatformSubscriptions.jsx";
import OwnerSubscription from "./OwnerSubscription.jsx";
import CommercialReminders from "./CommercialReminders.jsx";

vi.mock("./CommercialSimulator.jsx",()=>({default:()=>null}));

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
test("monthly commercial quote is selected and issued with exact total",async()=>{
  const api=vi.fn(async(path,body)=>{
    if(!body)return {years:[{id:"y",name:"2026–2027"}],suggested_year:"y"};
    if(body.action==="quote")return {counts:{primaire:100},rates:{primaire:1500},labels:{primaire:"Primaire"},policy_revision:1,terms:{gross_xaf:150000,minimum_xaf:75000,student_count:100},first_due:"2026-11-17",setup_suggested_xaf:50000,can_issue:true};
    return {subscription:{lines:[],total_xaf:150000,paid_xaf:0,balance_xaf:150000,payments:[],terms:{period:"mensuel",annual_xaf:150000,minimum_xaf:75000,discount_xaf:0,setup_xaf:0},schedule:[]}};
  });
  const user=userEvent.setup();
  render(<PlatformSubscriptions schoolId="school-a" api={api}/>);
  await user.selectOptions(await screen.findByLabelText("Modalité de règlement"),"mensuel");
  await user.type(screen.getByLabelText(/Motif \/ référence du contrat/),"Contrat mensuel");
  const activate=screen.getByRole("button",{name:"Activer la facturation"});
  expect(activate.disabled).toBe(true);
  await user.click(screen.getByRole("switch",{name:/Autoriser le passage au service payant/}));
  await user.click(activate);
  await waitFor(()=>expect(api).toHaveBeenCalledWith("platform/schools/school-a/subscriptions",expect.objectContaining({action:"issue",period:"mensuel",expected_total_xaf:150000,expected_counts:{primaire:100}})));
  expect(await screen.findByText("Contrat annuel enregistré")).toBeTruthy();
});
test("management reads refreshed balances from the school endpoint",async()=>{
  const contract={id:1,year:"2026–2027",year_id:"y",lines:[],total_xaf:150000,paid_xaf:0,balance_xaf:150000,terms:{period:"mensuel",minimum_xaf:75000,discount_xaf:0,setup_xaf:0},schedule:[]};
  let contractReads=0;
  const fetcher=vi.fn(async url=>url.includes("commercial-access")?Response.json({revision:0,lifecycle:"active",overdue_xaf:0,late_30_xaf:0,restricted:false,can_restrict:false}):url.includes("subscription-reminders")?Response.json({reminders:[],count:0,overdue_count:0,due_count:0,upcoming_count:0,window_days:7,pages:1,page:1}):Response.json({subscriptions:[contractReads++===0?contract:{...contract,paid_xaf:12500,balance_xaf:137500}]}));
  vi.stubGlobal("fetch",fetcher);
  const hidden=vi.spyOn(document,"hidden","get").mockReturnValue(false);
  render(<OwnerSubscription schoolId="school-a" yearId="y"/>);
  await screen.findByText(/Total contractuel/);
  window.dispatchEvent(new Event("focus"));
  await waitFor(()=>expect(contractReads).toBe(2));
  expect(await screen.findByText(/137[\s\u202f]500 FCFA/)).toBeTruthy();
  expect(fetcher).toHaveBeenCalledWith("/api/v1/schools/school-a/owner/subscriptions",{credentials:"same-origin",cache:"no-store"});
  hidden.mockRestore();
});

test("commercial PDFs are available through private same-origin routes",async()=>{
  const schoolId="11111111-1111-1111-1111-111111111111";
  const root="/api/v1/schools/"+schoolId+"/owner/subscriptions/42";
  const contract={id:42,year:"2026–2027",year_id:"y",lines:[],total_xaf:150000,paid_xaf:10000,balance_xaf:140000,terms:{},schedule:[],
    documents:{invoice:{reference:"YEM-FAC-0000000042",url:root+"/invoice"},receipts:[
      {id:7,reference:"YEM-REC-0000000007",url:root+"/payments/7/receipt",amount_xaf:10000,voided:false},
      {id:8,reference:"YEM-REC-0000000008",url:root+"/payments/8/receipt",amount_xaf:2000,voided:true},
      {id:9,reference:"Lien invalide",url:"https://example.test/receipt",amount_xaf:2000,voided:false}
    ]}};
  vi.stubGlobal("fetch",vi.fn(async url=>url.includes("commercial-access")?Response.json({revision:0,lifecycle:"active",overdue_xaf:0,late_30_xaf:0,restricted:false,can_restrict:false}):url.includes("subscription-reminders")?Response.json({reminders:[],count:0,overdue_count:0,due_count:0,upcoming_count:0,window_days:7,pages:1,page:1}):Response.json({subscriptions:[contract]})));
  vi.spyOn(document,"hidden","get").mockReturnValue(false);
  render(<OwnerSubscription schoolId={schoolId} yearId="y"/>);
  await userEvent.click(screen.getByRole("button",{name:"Contrat et documents"}));
  expect((await screen.findByRole("link",{name:"Ouvrir la facture"})).getAttribute("href")).toBe(root+"/invoice?preview=1");
  expect(screen.getByRole("link",{name:"Télécharger la facture (PDF)"}).getAttribute("href")).toBe(root+"/invoice");
  expect(screen.getByRole("link",{name:"Télécharger le reçu (PDF)"}).getAttribute("href")).toBe(root+"/payments/7/receipt");
  expect(screen.getByRole("link",{name:"Télécharger le reçu annulé (PDF)"}).getAttribute("href")).toBe(root+"/payments/8/receipt");
  expect(screen.getByText(/ANNULÉ/)).toBeTruthy();
  expect(document.querySelector('a[href*="example.test"]')).toBeNull();
});

test("commercial reminders refresh without duplicate rows and disappear after payment",async()=>{
  const row={id:"3:abonnement:1:2026-11-17",school_id:"school-a",school:"École A",year:"2026–2027",kind:"abonnement",number:1,due_date:"2026-11-17",balance_xaf:8334,days_until_due:-2,stage:"late"};
  const empty={reminders:[],count:0,overdue_count:0,due_count:0,upcoming_count:0,window_days:7,page:1,pages:1};
  const fetcher=vi.fn().mockImplementationOnce(async()=>Response.json({...empty,reminders:[row],count:1,overdue_count:1,overdue_xaf:8334})).mockImplementation(async()=>Response.json(empty));
  vi.stubGlobal("fetch",fetcher);
  vi.spyOn(document,"hidden","get").mockReturnValue(false);
  const select=vi.fn();
  render(<CommercialReminders platform onSelectSchool={select}/>);
  expect(await screen.findByText("Retard de 2 jours")).toBeTruthy();
  await userEvent.click(screen.getByRole("button",{name:"Voir l’établissement"}));
  expect(select).toHaveBeenCalledWith("school-a");
  window.dispatchEvent(new Event("focus"));
  expect(await screen.findByText("Aucune échéance à relancer actuellement.")).toBeTruthy();
  expect(screen.queryByText("Retard de 2 jours")).toBeNull();
  expect(fetcher.mock.calls.every(([url])=>url==="/api/v1/platform/subscription-reminders?page=1")).toBe(true);
});

test("trial issuance requires an explicit duration and justification",async()=>{
  const {default:CommercialAdjustments}=await import("./CommercialAdjustments.jsx");
  const api=vi.fn(async()=>({trial:{status:"active"}})),saved=vi.fn();
  render(<CommercialAdjustments api={api} path="platform/schools/a/subscriptions" year="y" canTrial onSaved={saved}/>);
  const user=userEvent.setup();
  await user.type(screen.getByLabelText("Motif de l’essai"),"Découverte école");
  await user.click(screen.getByRole("button",{name:"Accorder l’essai"}));
  await waitFor(()=>expect(api).toHaveBeenCalledWith("platform/schools/a/subscriptions",{action:"trial_start",year_id:"y",days:30,reason:"Découverte école"}));
  expect(saved).toHaveBeenCalledTimes(1);
});
test("amendment quote must be explicitly confirmed before issuance",async()=>{
  const {default:CommercialAdjustments}=await import("./CommercialAdjustments.jsx");
  const quote={revision:1,additions:[{cycle:"primaire",label:"Primaire",students:1,rate_xaf:1500}],remaining_days:180,duration_days:365,gross_prorata_xaf:740,minimum_absorbed_xaf:0,amount_xaf:740};
  const api=vi.fn(async(path,body)=>body.action==="amendment_quote"?{amendment:quote}:{subscription:{}}),saved=vi.fn();
  render(<CommercialAdjustments api={api} path="p" year="y" sub={{total_xaf:75000,amendments:[]}} onSaved={saved}/>);
  const user=userEvent.setup();
  await user.click(screen.getByRole("button",{name:"Calculer un avenant"}));
  await screen.findByText(/Montant de l’avenant/);
  expect(api).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button",{name:"Émettre l’avenant"}).disabled).toBe(true);
  await user.type(screen.getByLabelText("Motif de l’avenant"),"Nouvel inscrit");
  await user.click(screen.getByRole("button",{name:"Émettre l’avenant"}));
  await waitFor(()=>expect(api).toHaveBeenCalledWith("p",{action:"amendment_issue",year_id:"y",expected:quote,reason:"Nouvel inscrit"}));
  expect(saved).toHaveBeenCalledTimes(1);
});

test("manual restriction and restoration use explicit revision and reason",async()=>{
  const {default:CommercialAccess}=await import("./CommercialAccess.jsx");
  const start={revision:0,lifecycle:"expired",overdue_xaf:1000,late_30_xaf:1000,restricted:false,can_restrict:true};
  const api=vi.fn(async(path,body)=>body?{...start,revision:body.revision+1,restricted:body.restricted}:start);
  vi.spyOn(document,"hidden","get").mockReturnValue(false);
  render(<CommercialAccess schoolId="school-a" api={api}/>);
  const user=userEvent.setup();
  expect((await screen.findByRole("button",{name:"Passer en lecture seule"})).disabled).toBe(true);
  await user.type(screen.getByLabelText("Motif de la décision commerciale"),"Retard confirmé");
  await user.click(screen.getByRole("button",{name:"Passer en lecture seule"}));
  await screen.findByText("Établissement en lecture seule");
  expect(api).toHaveBeenCalledWith("platform/schools/school-a/commercial-access",{restricted:true,revision:0,reason:"Retard confirmé"});
  await user.type(screen.getByLabelText("Motif de la décision commerciale"),"Accord de régularisation");
  await user.click(screen.getByRole("button",{name:"Réactiver l’établissement"}));
  await screen.findByText("Accès établissement normal");
  expect(api).toHaveBeenCalledWith("platform/schools/school-a/commercial-access",{restricted:false,revision:1,reason:"Accord de régularisation"});
});

test("read-only API rejection dispatches a tenant-bound regularization notice without consuming response",async()=>{
  const {installCommercialReadOnlyNotice}=await import("./commercial-read-only.js");
  const id="12345678-1234-1234-1234-123456789abc";
  const response=()=>Response.json({code:"commercial_workspace_read_only",school_id:id},{status:403});
  const emitter=new EventTarget(), listener=vi.fn();
  emitter.addEventListener("yem:commercial-read-only",listener);
  const target={fetch:vi.fn(async()=>response()),location:{href:"https://yem.test/",origin:"https://yem.test"},CustomEvent,dispatchEvent:emitter.dispatchEvent.bind(emitter)};
  installCommercialReadOnlyNotice(target);
  const result=await target.fetch("/api/v1/schools/"+id+"/students",{method:"POST"});
  expect((await result.json()).code).toBe("commercial_workspace_read_only");
  expect(listener).toHaveBeenCalledTimes(1);
  expect(listener.mock.calls[0][0].detail.schoolId).toBe(id);
  await target.fetch("https://other.test/api/v1/schools/"+id+"/students");
  await target.fetch("/api/v1/schools/99999999-9999-9999-9999-999999999999/students");
  expect(listener).toHaveBeenCalledTimes(1);
});

test("commercial dashboard filters the list, retains global totals and opens a school subscription",async()=>{
  const {default:CommercialDashboard}=await import("./CommercialDashboard.jsx");
  const totals={contracted_xaf:100000,amendments_xaf:0,paid_xaf:5000,balance_xaf:95000,overdue_xaf:5000,due_today_xaf:0,future_xaf:90000,unscheduled_xaf:0,overpaid_xaf:0,schools:2,contracted_schools:1,active_schools:1,active_trials:0,overdue_schools:1,read_only_schools:0,review_count:0};
  const school={school_id:"a",school:"École A",enabled:true,contracts:1,contracted_xaf:100000,paid_xaf:5000,balance_xaf:95000,overdue_xaf:5000,late_30_xaf:0};
  const api=vi.fn(async path=>({as_of:"2026-11-17",year:2026,totals,months:[{month:"2026-11",received_xaf:5000,voided_xaf:0}],year_received_xaf:5000,year_voided_xaf:0,methods:{especes:5000},count:1,page:1,pages:1,schools:[school]}));
  const select=vi.fn(),user=userEvent.setup();
  render(<CommercialDashboard api={api} onSelectSchool={select}/>);
  await screen.findByText("Montant contractuel cumulé");
  await user.selectOptions(screen.getByLabelText("État commercial"),"overdue");
  await waitFor(()=>expect(api.mock.calls.some(([p])=>p.includes("status=overdue"))).toBe(true));
  await user.click(await screen.findByRole("button",{name:"Gérer l’abonnement"}));
  expect(select).toHaveBeenCalledWith("a");
  expect(screen.getByText("Montant contractuel cumulé")).toBeTruthy();
});
