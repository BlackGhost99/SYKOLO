// @vitest-environment jsdom
import React from "react";
import {cleanup,render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {afterEach,expect,test,vi} from "vitest";
import SchoolCommercialStatus from "./SchoolCommercialStatus.jsx";
afterEach(cleanup);

test("free school clearly has no payment deadline and administrative staff see only status",()=>{
  render(<SchoolCommercialStatus status={{mode:"free"}}/>);
  expect(screen.getByText("YEM · Mode gratuit")).toBeTruthy();
  expect(screen.getByText(/Facturation non activée · Aucune échéance/)).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
});

test("a management session displays next actual deadline and renewal, with direct access",async()=>{
  const open=vi.fn();
  const {rerender}=render(<SchoolCommercialStatus status={{mode:"active",next_payment_due:"2026-12-17",service_ends_before:"2027-11-17"}} canManage onManage={open}/>);
  expect(screen.getByText("YEM · Abonnement actif")).toBeTruthy();
  expect(screen.getByText(/Prochaine échéance : 17\/12\/2026 · Renouvellement le 17\/11\/2027/)).toBeTruthy();
  await userEvent.click(screen.getByRole("button",{name:/Mon abonnement/}));
  expect(open).toHaveBeenCalledTimes(1);
  rerender(<SchoolCommercialStatus status={{mode:"overdue",oldest_overdue_on:"2026-12-17",grace_days_remaining:29}} canManage onManage={open}/>);
  expect(screen.getByText("YEM · Abonnement en retard")).toBeTruthy();
  expect(screen.getByText(/29 jours de grâce restants/)).toBeTruthy();
});

test("read-only takes priority over a stale normal status, without showing private financial amounts",async()=>{
  const regularize=vi.fn();
  render(<SchoolCommercialStatus status={{mode:"active",paid_xaf:50000,overdue_xaf:25000}} restricted onRegularize={regularize}/>);
  expect(screen.getByText("YEM · Mode lecture seule")).toBeTruthy();
  expect(screen.getByText(/Modifications bloquées/)).toBeTruthy();
  expect(screen.queryByText(/50000|25000|FCFA/)).toBeNull();
  await userEvent.click(screen.getByRole("button",{name:"Contacter la direction"}));
  expect(regularize).toHaveBeenCalledTimes(1);
});

test("trial and expired service are distinct states; unknown status is not assumed free",()=>{
  const {rerender}=render(<SchoolCommercialStatus status={{mode:"trial",trial_ends_before:"2026-12-17"}}/>);
  expect(screen.getByText("YEM · Essai gratuit")).toBeTruthy();
  expect(screen.getByText(/Fin de l’essai le 17\/12\/2026/)).toBeTruthy();
  rerender(<SchoolCommercialStatus status={{mode:"expired",last_service_ended_on:"2026-11-17",grace_days_remaining:0}}/>);
  expect(screen.getByText("YEM · Abonnement expiré")).toBeTruthy();
  expect(screen.getByText(/Délai de grâce écoulé/)).toBeTruthy();
  rerender(<SchoolCommercialStatus status={null}/>);
  expect(screen.queryByRole("status")).toBeNull();
});

test("annual service coverage and monthly installments are distinct, free restrictions do not imply debt",()=>{
  const {rerender}=render(<SchoolCommercialStatus status={{mode:"active",billing_started:true,service_period_start:"2026-11-17",service_period_end:"2027-11-17",payment_period:"mensuel"}}/>);
  expect(screen.getByText(/Contrat annuel : du 17\/11\/2026 au 17\/11\/2027/)).toBeTruthy();
  expect(screen.getByText(/Règlement mensuel/)).toBeTruthy();
  rerender(<SchoolCommercialStatus status={{mode:"read_only",billing_started:false}} restricted canManage onRegularize={()=>{}}/>);
  expect(screen.getByText(/Facturation non activée/)).toBeTruthy();
  expect(screen.queryByText(/Abonnement à régulariser/)).toBeNull();
  expect(screen.getByRole("button",{name:"Contacter BWETEK"})).toBeTruthy();
});
