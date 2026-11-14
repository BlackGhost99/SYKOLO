// @vitest-environment jsdom
import {afterEach,expect,test} from "vitest";
import {readFileSync} from "node:fs";

const css=readFileSync("frontend/teacher-mobile.css","utf8");
afterEach(()=>{
  document.getElementById("yem-mobile-fit-test-style")?.remove();
  document.body.innerHTML="";
});

test("l'en-tête professeur annule display:flex et height:55px du header global",()=>{
  const style=document.createElement("style");
  style.id="yem-mobile-fit-test-style";
  style.textContent="header { display:flex; height:76px } @media (max-width:700px) { header { height:55px } }\n"+css;
  document.head.appendChild(style);
  document.body.innerHTML='<div class="ym-prof-app"><header class="ym-prof-header"><div class="ym-prof-header-top">YEM</div><h2 class="ym-prof-hero-title">Bonjour, Clarisse</h2><div class="ym-prof-school">Lycée AWASSI</div><div class="ym-prof-year">2026-2027</div></header><main class="ym-prof-body"><div class="ym-page"></div></main></div>';
  const header=document.querySelector(".ym-prof-app > header.ym-prof-header");
  expect(getComputedStyle(header).display).toBe("block");
  expect(getComputedStyle(header).height).toBe("auto");
  expect(getComputedStyle(document.querySelector(".ym-prof-app")).overflowX).toBe("clip");
});

test("les grilles restent bornées, le tableau de notes seul défile horizontalement",()=>{
  expect(css).toMatch(/\.ym-grade-table-wrap\s*\{[^}]*overflow-x:\s*auto\s*;/);
  expect(css).toMatch(/\.ym-prof-app\s*>\s*main\.ym-prof-body\s*\{[^}]*max-width:\s*820px\s*;/);
  expect(css).toMatch(/\.ym-prof-app\s+\.ym-status\s*\{[^}]*min-width:\s*0\s*;/);
  expect(css).toMatch(/\.ym-prof-app\s*>\s*nav\.ym-prof-nav\s*\{[^}]*max-width:\s*100vw\s*;/);
});

test("les colonnes globales de styles.css ne masquent plus les notes sur téléphone",()=>{
  const compact=css.slice(css.indexOf("Correctif cahier professeur"));
  expect(compact).toMatch(/@media \(max-width: 600px\)/);
  expect(compact).toMatch(/thead tr > th:nth-child\(n\+4\)/);
  expect(compact).toMatch(/tbody tr > td:nth-child\(n\+4\)/);
  expect(compact).toMatch(/\.ym-grade-table \.ym-grade-student\s*\{[^}]*position: static;/);
  expect(compact).toMatch(/\.ym-grade-table tbody td :is\(input,select\)\s*\{[^}]*width: 100%;[^}]*min-width: 0;/);
  expect(compact).toMatch(/\.ym-grade-table tbody tr > td:nth-child\(3\)\s*\{[^}]*width: 99px;/);
  expect(compact).toMatch(/\.ym-grade-table tr > :first-child\s*\{[^}]*width: 38px;/);
});
test("les tableaux, moyennes et appels restent bornés sur mobile",()=>{
  const compact=css.slice(css.indexOf("Correctif cahier professeur"));
  expect(compact).toMatch(/\.ym-grade-table-wrap\s*\{[^}]*overflow-x: auto;/);
  expect(compact).toMatch(/\.ym-stats-four > div strong\s*\{[^}]*font-size: clamp\(/);
  expect(compact).toMatch(/\.ym-call-heading :is\(h2,p\)\s*\{[^}]*overflow-wrap: anywhere;/);
});
