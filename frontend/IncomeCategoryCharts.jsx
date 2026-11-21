import React,{useEffect,useMemo,useState} from "react";

/** School-scoped charts from ONE existing read-only financial summary.
 *  They never mix currencies, treat simulations as revenue, or expose pupils.
 */
const VIEWS=[
  {code:"billed",label:"Frais nets facturés"},
  {code:"paid",label:"Règlements enregistrés"},
  {code:"overdue",label:"Créances échues"},
  {code:"future",label:"Échéances futures"},
];
const money=(value,currency)=>new Intl.NumberFormat("fr-FR",{maximumFractionDigits:2}).format(Number(value||0))+" "+currency;
const safeMoney=value=>{
  const amount=Number(value||0);
  return Number.isFinite(amount)&&amount>0?amount:0;
};

export default function IncomeCategoryCharts({report,schoolId,yearId}){
  const rows=useMemo(()=>(report?.rows||[]).filter(item=>item.category!=="demo"),[report]);
  const currencies=useMemo(()=>[...new Set(rows.map(r=>r.currency))].sort(),[rows]);
  const [currency,setCurrency]=useState("");
  const [metric,setMetric]=useState("paid");
  const [selected,setSelected]=useState("");
  const [show,setShow]=useState(true);
  const [layout,setLayout]=useState("bars");
  useEffect(()=>{setCurrency("");setSelected("");setMetric("paid");setShow(true);setLayout("bars");},[schoolId,yearId]);
  useEffect(()=>{
    if(!currencies.includes(currency))setCurrency(currencies.includes("XAF")?"XAF":currencies[0]||"");
    setSelected("");
  },[currency,currencies]);
  const records=useMemo(()=>{
    const owing=new Map((report?.receivables?.rows||[]).map(r=>[r.category+"/"+r.currency,r]));
    return rows.filter(row=>row.currency===currency).map(row=>({
      ...row,
      outstanding:owing.get(row.category+"/"+row.currency)?.outstanding ?? null,
      overdue:owing.get(row.category+"/"+row.currency)?.overdue ?? null,
      future:owing.get(row.category+"/"+row.currency)?.future ?? null,
    }));
  },[rows,report,currency]);
  const max=Math.max(1,...records.map(item=>safeMoney(item[metric])));
  const current=records.find(r=>r.category===selected)||null;
  const details=(report?.details||[]).filter(r=>current&&r.category===current.category&&r.currency===currency);
  const noDebtData=["overdue","future"].includes(metric)&&!report?.receivables?.rows;
  const demo=(report?.rows||[]).filter(r=>r.category==="demo").length;
  if(!rows.length)return <p className="hint">Aucune catégorie financière disponible pour ce graphique.</p>;
  return <section className="yd-income-charts" aria-label="Diagrammes interactifs des recettes scolaires"
    style={{border:"1px solid var(--yd-border,#d7dce0)",borderRadius:14,padding:16,marginBlock:14}}>
    <div className="actions" style={{display:"flex",flexWrap:"wrap",alignItems:"center",gap:10}}>
      <strong>Répartition des entrées par catégorie</strong>
      <button type="button" onClick={()=>setShow(x=>!x)} aria-expanded={show}>
        {show?"Masquer le graphique":"Afficher le graphique"}
      </button>
    </div>
    {show&&<>
      <div style={{display:"flex",flexWrap:"wrap",gap:12,marginTop:12}}>
        <label>Indicateur
          <select aria-label="Indicateur des graphiques" value={metric}
            onChange={e=>{setMetric(e.target.value);setSelected("");}}>
            {VIEWS.map(item=><option key={item.code} value={item.code}>{item.label}</option>)}
          </select>
        </label>
        <label>Devise
          <select aria-label="Devise des graphiques" value={currency}
            onChange={e=>setCurrency(e.target.value)}>
            {currencies.map(c=><option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label>Présentation
          <select aria-label="Présentation du graphique" value={layout}
            onChange={e=>setLayout(e.target.value)}>
            <option value="bars">Barres</option>
            <option value="compact">Liste compacte</option>
          </select>
        </label>
      </div>
      <p className="hint">Montants {metric==="paid"?"enregistrés, non certifiés":"issus du registre des créances"}.
        Les inscriptions encaissées à la caisse sont présentées séparément ; les devises ne sont jamais additionnées.</p>
      {noDebtData?<p>Les échéances ne sont pas encore disponibles pour cette année.</p>:
        <div style={{display:"grid",gap:12,marginTop:14}}>
          {records.map(row=>{
            const value=safeMoney(row[metric]);
            const active=selected===row.category;
            return <button type="button" key={row.category+"/"+row.currency}
              aria-pressed={active} onClick={()=>setSelected(active?"":row.category)}
              aria-label={row.label+" : "+money(value,currency)+". "+(active?"Masquer":"Voir")+" le détail"}
              style={{textAlign:"left",width:"100%",background:active?"var(--yd-surface,#edf4f0)":"transparent",
                border:"1px solid var(--yd-border,#d7dce0)",padding:layout==="compact"?8:12,borderRadius:10,
                cursor:"pointer"}}>
              <span style={{display:"flex",justifyContent:"space-between",gap:12,alignItems:"center"}}>
                <strong>{row.label}</strong><span>{money(value,currency)}</span>
              </span>
              {layout==="bars"&&<span aria-hidden="true" style={{
                display:"block",height:12,background:"var(--yd-soft,#e8edf0)",
                borderRadius:9,marginTop:8,overflow:"hidden"}}>
                <span style={{display:"block",height:"100%",width:(value/max*100)+"%",
                  background:row.category==="a_classer"?"#a47b23":"#248466",
                  borderRadius:9}}/>
              </span>}
            </button>;
          })}
        </div>}
      {current&&!noDebtData&&<div style={{marginTop:16}} aria-label={"Détail de "+current.label}>
        <h4>{current.label} — détail par code tarifaire ({currency})</h4>
        {details.length?<div style={{overflowX:"auto"}}><table className="dense">
          <thead><tr><th>Code tarif</th><th>Facturé</th><th>Règlements déclarés</th></tr></thead>
          <tbody>{details.map(d=><tr key={d.fee_code}>
            <td>{d.fee_code}</td><td>{money(d.billed,currency)}</td><td>{money(d.paid,currency)}</td>
          </tr>)}</tbody>
        </table></div>:<p>Aucune ligne de tarif pour cette catégorie.</p>}
        <p className="hint">Cette session donne une synthèse de gestion, sans accès nominatif aux élèves ni aux pièces comptables sensibles.</p>
      </div>}
      {demo>0&&<p className="hint">Les simulations sont visibles dans le tableau de ventilation, mais exclues de ce graphique de recettes enregistrées.</p>}
    </>}
  </section>;
}
