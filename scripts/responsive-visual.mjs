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
        if(width<=760&&role==="direction"){
          const toolbar=await root.locator(".yd-topbar").evaluate(el=>{
            const boxes=[".yd-logo",".yd-header-search",".yd-bell",".yd-user-wrap"].map(s=>el.querySelector(s)?.getBoundingClientRect());
            return {aligned:boxes.every(b=>b&&Math.abs(b.top+ b.height/2-(boxes[0].top+boxes[0].height/2))<5),height:el.getBoundingClientRect().height};
          });
          if(!toolbar.aligned)failures.push("Les quatre commandes de l’en-tête ne sont pas alignées");
          if(toolbar.height>195)failures.push("En-tête mobile trop haut : "+toolbar.height);
          const art=root.locator(".yd-fixed-banner-art");
          const crest=root.locator(".yd-school-picker .yd-school-logo");
          if(!await art.isVisible()||!await crest.isVisible())failures.push("Visuels d’établissement absents");
          else{
            const artInfo=await art.evaluate(img=>({loaded:img.complete&&img.naturalWidth>0,fit:getComputedStyle(img).objectFit,width:img.getBoundingClientRect().width}));
            if(!artInfo.loaded||artInfo.fit!=="contain"||artInfo.width<width*.8)failures.push("Bannière rognée ou trop étroite");
          }
          const account=root.getByRole("button",{name:/^Compte de/});
          await account.click();
          const menu=root.getByRole("menu",{name:"Menu du compte"});
          await menu.waitFor();
          const bounds=await menu.boundingBox();
          if(!bounds||bounds.x<0||bounds.x+bounds.width>width+1||bounds.y<0||bounds.y+bounds.height>height+1)failures.push("Menu du compte hors écran");
          await page.screenshot({path:output+"/"+name+"-compte.png",animations:"disabled",style:".yem-demo-pilot{visibility:hidden!important}"});
          await page.keyboard.press("Escape");
          if(await menu.isVisible())failures.push("Échap ne ferme pas le compte");
          if(await root.locator(".yd-year-picker").count()&&await root.getByRole("combobox",{name:"Année scolaire",exact:true}).count())failures.push("Sélecteur d’année dupliqué");
        }
        if(width<=1150&&role==="platform"){
          const directory=root.locator(".ya-directory");
          const detail=root.locator(".ya-school-detail-panel");
          if(await detail.isVisible())failures.push("Fiche école affichée d’office sous le répertoire");
          if(width<=760){
            const row=directory.locator("tbody tr").first();
            if(await row.count()){
              const box=await row.boundingBox();
              if(!box||box.height>100)failures.push("Ligne établissement trop haute sur mobile");
            }
          }
          const manage=directory.getByRole("button",{name:/^Gérer/}).first();
          if(await manage.count()){
            await manage.click();
            await detail.waitFor({state:"visible"});
            if(await directory.isVisible())failures.push("Répertoire et fiche empilés");
            await page.screenshot({path:output+"/"+name+"-fiche.png",animations:"disabled",style:".yem-demo-pilot{visibility:hidden!important}"});
            await detail.getByRole("button",{name:"Retour aux établissements"}).click();
            await directory.waitFor({state:"visible"});
          }
        }
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
