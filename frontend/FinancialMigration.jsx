import React, {useState} from "react";
import {Button, Card, PageHeader} from "./yem-ui.jsx";

const statusLabels = {
  proposed:"Montant déclaré à vérifier", zero:"Zéro déclaré", unknown:"Montant inconnu",
  overpayment:"Dépassement du montant dû", existing_review:"Paiement YEM à rapprocher",
  invalid:"Incompatible / invalide", identity_review:"Matricule inconnu, ambigu ou répété",
};
const money = value => value == null ? "—" : new Intl.NumberFormat("fr-FR", {maximumFractionDigits:2}).format(Number(value))+" FCFA";

export default function FinancialMigration({schoolId,tabs,workingYearId}) {
  const [file,setFile] = useState(null);
  const [meta,setMeta] = useState(null);
  const [sheet,setSheet] = useState("");
  const [header,setHeader] = useState(1);
  const [year,setYear] = useState("");
  const [cutoff,setCutoff] = useState("");
  const [code,setCode] = useState("");
  const [mapping,setMapping] = useState({});
  const [result,setResult] = useState(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [onlyReview,setOnlyReview] = useState(false);

  async function send(action, selectedFile, selectedSheet, selectedHeader, extra={}) {
    const body = new FormData();
    body.append("file", selectedFile);
    body.append("sheet", selectedSheet);
    body.append("header_row", String(selectedHeader));
    Object.entries(extra).forEach(([k,v])=>body.append(k,v));
    await fetch("/api/v1/auth/csrf",{credentials:"same-origin"});
    const csrf = document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
    const response = await fetch("/api/v1/schools/"+schoolId+"/imports/finance/"+action,{
      method:"POST",credentials:"same-origin",headers:{"X-CSRFToken":csrf},body,
      cache:"no-store",
    });
    if (!response.headers.get("content-type")?.includes("application/json")) throw Error("Serveur indisponible.");
    const data = await response.json();
    if (!response.ok) throw Error(data.error||"Analyse refusée.");
    return data;
  }
  function selectYear(id,data=meta) {
    setYear(id);
    const y = data?.years.find(x=>x.id===id);
    setCutoff(y ? (y.end < data.today ? y.end : data.today) : "");
    setMapping({});setResult(null);setError("");
  }
  async function inspect(f, s="", h=1) {
    if (!f) return;
    setBusy(true);setError("");setMeta(null);setResult(null);setMapping({});setCode("");
    try {
      const data = await send("inspect", f, s, h);
      setMeta(data);setSheet(data.sheet);setHeader(data.header_row);
      setCode(data.suggested_student_code == null ? "" : String(data.suggested_student_code));
      selectYear(data.years.find(x=>x.id===workingYearId)?.id||data.years.find(x=>x.status==="current")?.id||data.years[0]?.id||"",data);
    } catch(e){setError(e.message);}
    finally {setBusy(false);}
  }
  async function preview() {
    setBusy(true);setError("");setResult(null);
    try {
      const amounts = Object.entries(mapping).filter(([,v])=>v).map(([column,schedule])=>({column:Number(column),schedule}));
      const data = await send("preview",file,sheet,header,{year,cutoff,mapping:JSON.stringify({student_code:Number(code),amounts})});
      setResult(data);
    } catch(e){setError(e.message);}
    finally {setBusy(false);}
  }
  function changeCode(v) {
    setCode(v);setMapping(old=>{const next={...old};delete next[v];return next;});setResult(null);
  }
  const tariffs = (meta?.tariffs||[]).filter(t=>t.year===year);
  const selected = Object.values(mapping).filter(Boolean);
  const selectedYear = meta?.years.find(y=>y.id===year);
  const valid = !!file&&!!meta&&!!year&&!!cutoff&&code!==""&&selected.length>0&&selected.length<=12&&selected.length*meta.row_count<=2000&&new Set(selected).size===selected.length;
  const rows = (result?.rows||[]).flatMap(row=>row.status==="identity_review"?[{line:row.line,status:row.status}]:row.cells.map(cell=>({...cell,line:row.line})));
  const visibleRows = onlyReview?rows.filter(row=>!["proposed","zero"].includes(row.status)):rows;
  return <>
    <PageHeader title="Reprise financière" subtitle="YEM Intelligence — migration des historiques, aperçu sans écriture" banner={false}/>
    {tabs}
    <div className="yd-real-body">
      <Card title="1. Analyser le registre financier" icon="excel">
        <p className="hint">Importez d’abord les élèves et leurs inscriptions. Ce parcours compare des montants cumulés déclarés par tarif ; il ne crée aucun paiement ni reçu. Aucun fournisseur IA externe sollicité.</p>
        <label className="field">Fichier Excel ou CSV
          <input type="file" accept=".xlsx,.csv" disabled={busy} onChange={e=>{const f=e.target.files?.[0]||null;setFile(f);setMeta(null);setResult(null);setError("");if(f)inspect(f);}}/>
        </label>
        {file&&<p className="hint">{file.name}</p>}
        {file&&<label className="field">Ligne des en-têtes
          <select value={header} disabled={busy} onChange={e=>{const h=Number(e.target.value);setHeader(h);inspect(file,sheet,h);}}>
            {Array.from({length:10},(_,i)=><option key={i+1} value={i+1}>{i+1}</option>)}
          </select>
        </label>}
        {meta&&<>
          <p>{meta.row_count} lignes · {meta.headers.length} colonnes</p>
          {meta.sheets.length>1&&<label className="field">Feuille
            <select value={sheet} disabled={busy} onChange={e=>{setSheet(e.target.value);inspect(file,e.target.value,header);}}>{meta.sheets.map(s=><option key={s}>{s}</option>)}</select>
          </label>}
          <p className="hint">Colonnes financières possibles : {meta.financial_columns.map(i=>meta.headers[i]).join(", ")||"aucune reconnue"}. Vérifiez leur signification avant toute association.</p>
        </>}
      </Card>
      {error&&<p role="alert" className="pc-alert">{error}</p>}
      {meta&&<Card title="2. Associer les colonnes" icon="settings">
        <form onSubmit={e=>{e.preventDefault();if(valid&&!busy)preview();}}>
          <label className="field">Année scolaire
            <select required disabled={busy} value={year} onChange={e=>selectYear(e.target.value)}>
              <option value="">Choisir…</option>{meta.years.map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
            </select>
          </label>
          <label className="field">Date de reprise
            <input type="date" required disabled={busy||!year} min={selectedYear?.start} max={selectedYear?(selectedYear.end<meta.today?selectedYear.end:meta.today):undefined} value={cutoff} onChange={e=>{setCutoff(e.target.value);setResult(null);}}/>
          </label>
          <label className="field">Colonne du matricule local
            <select required disabled={busy} value={code} onChange={e=>changeCode(e.target.value)}>
              <option value="">Choisir…</option>{meta.headers.map((h,i)=><option key={i} value={i}>{h||"Colonne "+(i+1)}</option>)}
            </select>
          </label>
          <p className="hint">Choisissez un tarif par colonne de montant. Ne mappez pas les soldes, totaux généraux ou libellés « payé » comme des montants versés. Les tarifs de classes différentes doivent être traités dans des fichiers/feuilles distincts.</p>
          {meta.headers.map((h,i)=>String(i)!==code&&<label key={i} className="field">
            {h||"Colonne "+(i+1)} {meta.financial_columns.includes(i)?" · montant possible":""}
            <select disabled={busy||!year} value={mapping[i]||""} onChange={e=>{setMapping(old=>({...old,[i]:e.target.value}));setResult(null);}}>
              <option value="">Ne pas reprendre</option>
              {tariffs.map(t=><option key={t.id} value={t.id} disabled={selected.includes(t.id)&&mapping[i]!==t.id}>{t.label} · {t.classroom||"Toutes classes"} · {t.due_date||"Sans échéance"} · {money(t.amount)}</option>)}
            </select>
          </label>)}
          {selected.length>12||selected.length*meta.row_count>2000?<p role="alert">Limite : 12 tarifs et 2 000 cellules par aperçu. Fractionnez le fichier.</p>:null}
          <Button type="submit" disabled={busy||!valid}>{busy?"Analyse…":"Prévisualiser la reprise"}</Button>
        </form>
      </Card>}
      {result&&<Card title="3. Contrôler les résultats" icon="file">
        <p role="status">{result.notice}</p>
        {Object.entries(result.counts).map(([k,v])=><p key={k}>{statusLabels[k]||k} : <strong>{v}</strong></p>)}
        <label><input type="checkbox" checked={onlyReview} onChange={e=>setOnlyReview(e.target.checked)}/> Afficher uniquement les anomalies et rapprochements</label>
        <div style={{maxWidth:"100%",overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse"}}>
            <thead><tr>{["Ligne","Colonne","Dû net","Déclaré","Déjà comptabilisé","Reste déclaré","Diagnostic"].map(x=><th key={x} scope="col" style={{textAlign:"left",padding:8}}>{x}</th>)}</tr></thead>
            <tbody>{visibleRows.map((r,i)=><tr key={i}>
              <td style={{padding:8}}>{r.line}</td><td style={{padding:8}}>{r.column==null?"—":meta.headers[r.column]}</td>
              {[r.net_due,r.declared,r.already_booked,r.declared_balance].map((v,j)=><td key={j} style={{padding:8,whiteSpace:"nowrap"}}>{money(v)}</td>)}
              <td style={{padding:8}}>{statusLabels[r.status]||r.status}{r.error?" : "+r.error:""}</td>
            </tr>)}</tbody>
          </table>
          {!visibleRows.length&&<p>Aucune ligne dans cette sélection.</p>}
        </div>
        <p className="hint">Aucun bouton de validation comptable à ce stade. La reprise définitive nécessite une preuve et un circuit de validation distinct.</p>
      </Card>}
    </div>
  </>;
}
