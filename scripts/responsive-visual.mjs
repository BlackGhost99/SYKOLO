import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
const output="responsive-results";
await mkdir(output,{recursive:true});
const browsers=await chromium.launch({headless:true});
const report=[];
const viewports=[[360,640],[390,844],[768,1024],[1366,768],[1920,1080]];
const roles=[
  ["direction","Tableau de bord"],
  ["proprietaire","Pilotage du propriétaire"],
  ["platform","Console d'administration YEM"],
  ["parent","Espace parents"],
  ["econome","Tableau de bord"],
];
try{
 for(const [width,height] of viewports){
  const page=await browsers.newPage({viewport:{width,height},serviceWorkers:"block"});
  const errors=[];
  page.on("pageerror",e=>errors.push(e.message));
  // Demo only. Block API traffic that could escape the in-memory backend.
  await page.route("**/api/**",route=>route.abort());
  try{
    await page.goto("http://127.0.0.1:4173/#/demo");
    const selector=page.getByRole("combobox",{name:"Profil de démonstration"});
    await selector.waitFor();
    for(const [role,heading] of roles){
      try{
        errors.length=0;
        await selector.selectOption(role);
        const root=page.locator(".yem-demo-real-app");
        await root.getByRole("heading",{name:heading,exact:true}).first().waitFor({state:role==="parent"?"attached":"visible",timeout:20000});
        await page.evaluate(()=>document.fonts.ready);
        await page.waitForTimeout(400);
        const metrics=await root.evaluate(el=>{
          const doc=document.documentElement;
          const nav=el.querySelector(".yd-school-bottom-nav,.yfx-bottom-nav");
          return {
            width:doc.clientWidth,scrollWidth:doc.scrollWidth,scrollHeight:doc.scrollHeight,
            rootWidth:el.getBoundingClientRect().width,
            navVisible:!!nav&&nav.getClientRects().length>0,
            brandingImages:[...el.querySelectorAll(".yd-fixed-banner-art,.yd-fixed-banner-mark img,.yfx-school-banner,.yfx-school-logo")].map(img=>({loaded:img.complete&&img.naturalWidth>0,fit:getComputedStyle(img).objectFit})),
            demoError:!!document.querySelector(".yem-demo-error")
          };
        });
        const name=role+"-"+width+"x"+height;
        await page.screenshot({path:output+"/"+name+".png",animations:"disabled",style:".yem-demo-pilot{visibility:hidden!important}"});
        const failures=[];
        if(metrics.scrollWidth>metrics.width+2)failures.push("Débordement horizontal de page");
        if(metrics.demoError)failures.push("Erreur du composant de démonstration");
        if(errors.length)failures.push(...errors);
        if(width<=760&&["direction","proprietaire","econome","parent"].includes(role)&&!metrics.navVisible)failures.push("Navigation mobile absente");
        report.push({role,width,height,...metrics,failures});
      }catch(e){report.push({role,width,height,failures:[String(e)]});}
    }
  }finally{await page.close();}
 }
}finally{
 await browsers.close();
 await writeFile(output+"/report.json",JSON.stringify(report,null,2));
 const errors=report.filter(r=>r.failures.length);
 console.log(JSON.stringify({screens:report.length,passed:report.length-errors.length,failed:errors.length,errors},null,2));
 if(errors.length)process.exitCode=1;
}
