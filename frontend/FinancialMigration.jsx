import React, {useState} from "react";
import {Button, Card, PageHeader} from "./yem-ui.jsx";
import {useLoad} from "./EnrollmentScreens.jsx";

const statusLabels = {
  proposed:"Montant déclaré à vérifier", zero:"Zéro déclaré", unknown:"Montant inconnu",
  overpayment:"Dépassement du montant dû", existing_review:"Paiement YEM à rapprocher",
  invalid:"Incompatible / invalide", identity_review:"Matricule inconnu, ambigu ou répété",
};
const columnHints = {
  balance:"Solde possible", scholarship:"Bourse ou remise possible", billing:"Frais ou échéance possible",
  payment_candidate:"Versement possible", ambiguous:"Montant à identifier",
};
const batchStatus = batch => batch.reversal_pending ? "Contrepassation à approuver" : ({prepared:"À approuver",approved:"Approuvé",cancelled:"Annulé",reversed:"Contrepassé"})[batch.status];
const money = value => value == null ? "—" : new Intl.NumberFormat("fr-FR", {maximumFractionDigits:2}).format(Number(value))+" FCFA";

export default function FinancialMigration({schoolId,tabs,workingYearId,source}) {
  const [file,setFile] = useState(source?.file || null);
  const [meta,setMeta] = useState(null);
  const [sheet,setSheet] = useState(source?.sheet || "");
  const [header,setHeader] = useState(source?.headerRow || 1);
  const [year,setYear] = useState("");
  const [cutoff,setCutoff] = useState("");
  const [code,setCode] = useState("");
  const [mapping,setMapping] = useState({});
  const [result,setResult] = useState(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [onlyReview,setOnlyReview] = useState(false);
  const [selectedBatch,setSelectedBatch] = useState("");
  const [reason,setReason] = useState("");
  const [confirmed,setConfirmed] = useState(false);
  const [message,setMessage] = useState("");
  const root = `schools/${schoolId}/imports/finance/`;
  const lots = useLoad(root+"batches");
  const lot = useLoad(selectedBatch?root+selectedBatch:null);
  const activeLot = lot.data?.id===selectedBatch?lot.data:null;

  async function send(action, selectedFile, selectedSheet, selectedHeader, extra={}) {
    const body = new FormData();
    if(selectedFile){body.append("file", selectedFile);body.append("sheet", selectedSheet);body.append("header_row", String(selectedHeader));}
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
  async function inspect(f, s="", h=1, preferredYear=workingYearId) {
    if (!f) return;
    setBusy(true);setError("");setMeta(null);setResult(null);setMapping({});setCode("");
    try {
      const data = await send("inspect", f, s, h);
      setMeta(data);setSheet(data.sheet);setHeader(data.header_row);
      setCode(data.suggested_student_code == null ? "" : String(data.suggested_student_code));
      selectYear(data.years.find(x=>x.id===preferredYear)?.id||data.years.find(x=>x.status==="current")?.id||data.years[0]?.id||"",data);
    } catch(e){setError(e.message);}
    finally {setBusy(false);}
  }
  async function preview() {
    setBusy(true);setError("");setResult(null);
    try {
      const amounts = mappedAmounts();
      const data = await send("preview",file,sheet,header,{year,cutoff,mapping:JSON.stringify({student_code:Number(code),amounts})});
      setResult(data);
    } catch(e){setError(e.message);}
    finally {setBusy(false);}
  }
  function chooseBatch(id){setSelectedBatch(id);setReason("");setConfirmed(false);setError("");}
  async function prepareBatch(){
    if(busy||!canPrepare||!valid||!rows.length||rows.some(r=>!["proposed","zero"].includes(r.status)))return;
    setBusy(true);setError("");setMessage("");
    try{
      const amounts=mappedAmounts();
      const data=await send("prepare",file,sheet,header,{year,cutoff,mapping:JSON.stringify({student_code:Number(code),amounts})});
      chooseBatch(data.batch);setMessage("Lot préparé. Aucun paiement ni solde modifié avant approbation indépendante.");lots.reload();lot.reload();setResult(null);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function decide(action){
    if(busy||!activeLot||!confirmed||reason.trim().length<5)return;
    setBusy(true);setError("");setMessage("");
    try{
      await send(activeLot.id+"/"+action,null,"",1,{reason:reason.trim()});
      setMessage({
        approve:"Lot approuvé. Les crédits historiques sont intégrés aux soldes.",
        cancel:"Lot préparé annulé.",
        "reversal/request":"Contrepassation demandée. Les soldes sont inchangés en attendant l’approbation.",
        "reversal/withdraw":"Demande de contrepassation retirée.",
        "reversal/confirm":"Contrepassation approuvée. Les soldes ont été recalculés.",
      }[action]);
      setReason("");setConfirmed(false);lots.reload();lot.reload();
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  function mappedAmounts(){return Object.entries(mapping).filter(([,ids])=>ids.length).map(([column,schedules])=>({column:Number(column),schedules}));}
  function assignTariffs(column,ids){setMapping(old=>({...old,[column]:ids}));setResult(null);}
  function changeCode(v) {
    setCode(v);setMapping(old=>{const next={...old};delete next[v];return next;});setResult(null);
  }
  const tariffs = (meta?.tariffs||[]).filter(t=>t.year===year);
  const selected = Object.values(mapping).flat();
  const selectedColumns = Object.values(mapping).filter(ids=>ids.length).length;
  const selectedYear = meta?.years.find(y=>y.id===year);
  const valid = !!file&&!!meta&&!!year&&!!cutoff&&code!==""&&selectedColumns>0&&selectedColumns<=12&&selectedColumns*meta.row_count<=2000&&selected.length<=240&&Object.values(mapping).every(ids=>ids.length<=100)&&new Set(selected).size===selected.length;
  const rows = (result?.rows||[]).flatMap(row=>row.status==="identity_review"?[{line:row.line,status:row.status}]:row.cells.map(cell=>({...cell,line:row.line})));
  const visibleRows = onlyReview?rows.filter(row=>!["proposed","zero"].includes(row.status)):rows;
  const canPrepare=!!lots.data?.can_prepare;
  return <>
    <PageHeader title="Reprise financière" subtitle="YEM Intelligence — migration des historiques avec validation indépendante" banner={false}/>
    {tabs}
    <div className="yd-real-body">
      {message&&<p role="status" className="yd-form-msg">{message}</p>}
      <Card title="Lots de reprise" icon="file">
        {lots.error&&<p role="alert">{lots.error}</p>}
        <Button type="button" disabled={busy||lots.loading} onClick={()=>lots.reload()}>Actualiser les lots</Button>
        {(lots.data?.batches||[]).map(b=><div key={b.id} style={{padding:"10px 0"}}>
          <p><strong>{b.source_reference}</strong> · {b.year_name} · {b.row_count} lignes · {batchStatus(b)}</p>
          <Button type="button" disabled={busy} onClick={()=>chooseBatch(b.id)}>Examiner le lot</Button>
        </div>)}
        {lots.data&&!lots.data.batches.length&&<p className="hint">Aucun lot disponible.</p>}
        {lot.error&&<p role="alert">{lot.error}</p>}
        {activeLot&&<section aria-label="Détail du lot">
          <h4>{activeLot.source_reference}</h4><p>Reprise au {activeLot.cutoff} · {activeLot.year_name} · {batchStatus(activeLot)}</p>
          <div style={{maxWidth:"100%",overflowX:"auto",maxHeight:"420px",overflowY:"auto"}}><table style={{width:"100%"}}><thead><tr>{["Ligne","Matricule","Tarif","Dû net","Déclaré","Bourse"].map(h=><th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{activeLot.entries.map((e,i)=><tr key={i}><td>{e.line}</td><td>{e.student_code}</td><td>{e.schedule}</td><td>{money(e.net_due)}</td><td>{money(e.declared)}</td><td>{money(e.scholarship)}</td></tr>)}</tbody></table></div>
          {activeLot.reversal_reason&&<p>Motif de contrepassation demandé · {activeLot.reversal_reason}</p>}
          {activeLot.reversal_evidence&&<p>Référence d’approbation · {activeLot.reversal_evidence}</p>}
          {(activeLot.can_approve||activeLot.can_cancel||activeLot.can_request_reversal||activeLot.can_confirm_reversal||activeLot.can_withdraw_reversal)&&<>
            <label className="field">Motif ou référence du justificatif<textarea rows={3} maxLength={255} disabled={busy} value={reason} onChange={e=>setReason(e.target.value)}/></label>
            <label><input type="checkbox" disabled={busy} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> Je confirme avoir contrôlé ce lot et ses justificatifs.</label>
            <div className="actions">
              {activeLot.can_approve&&<Button type="button" disabled={busy||!confirmed||reason.trim().length<5} onClick={()=>decide("approve")}>Approuver la reprise historique</Button>}
              {activeLot.can_cancel&&<Button type="button" disabled={busy||!confirmed||reason.trim().length<5} onClick={()=>decide("cancel")}>Annuler le lot préparé</Button>}
              {activeLot.can_request_reversal&&<Button type="button" disabled={busy||!confirmed||reason.trim().length<5} onClick={()=>decide("reversal/request")}>Demander la contrepassation</Button>}
              {activeLot.can_confirm_reversal&&<Button type="button" disabled={busy||!confirmed||reason.trim().length<5} onClick={()=>decide("reversal/confirm")}>Approuver le retrait des crédits historiques</Button>}
              {activeLot.can_withdraw_reversal&&<Button type="button" disabled={busy||!confirmed||reason.trim().length<5} onClick={()=>decide("reversal/withdraw")}>Retirer la demande</Button>}
            </div>
          </>}
          {!activeLot.can_approve&&activeLot.status==="prepared"&&<p className="hint">Approbation réservée à un comptable distinct du préparateur.</p>}
        </section>}
      </Card>
      <Card title="1. Analyser le registre financier" icon="excel">
        <p className="hint">Importez d’abord les élèves et leurs inscriptions. Ce parcours compare des montants cumulés déclarés par tarif ; il ne crée aucun paiement ni reçu. Aucun fournisseur IA externe sollicité.</p>
        <label className="field">Fichier Excel ou CSV
          <input type="file" accept=".xlsx,.csv" disabled={busy} onChange={e=>{const f=e.target.files?.[0]||null;setFile(f);setSheet("");setHeader(1);setMeta(null);setResult(null);setError("");if(f)inspect(f);}}/>
        </label>
        {file&&<p className="hint">{file.name}</p>}
        {source?.file===file&&!meta&&<Button type="button" disabled={busy} onClick={()=>inspect(file,sheet,header,source.year)}>
          Analyser le fichier des inscriptions
        </Button>}
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
          <p className="hint">Associez à chaque colonne un tarif ou plusieurs variantes du même code de frais selon les classes. YEM utilisera la classe réelle de l’élève, puis le tarif général uniquement si vous l’avez sélectionné. Ne mappez pas les soldes, les totaux généraux ni les libellés « payé ».</p>
          {meta.headers.map((h,i)=>{
            if(String(i)===code)return null;
            const ids=mapping[i]||[];
            const chosen=tariffs.find(t=>t.id===ids[0]);
            const alternatives=chosen?tariffs.filter(t=>t.code===chosen.code&&!selected.includes(t.id)&&!ids.some(id=>tariffs.find(a=>a.id===id)?.classroom_id===t.classroom_id)):[];
            return <div key={i} style={{marginBottom:14}}>
              <label className="field">{h||"Colonne "+(i+1)} {meta.financial_hints?.[i]?" · "+columnHints[meta.financial_hints[i]]:""}
                <select disabled={busy||!year} value={ids[0]||""} onChange={e=>assignTariffs(i,e.target.value?[e.target.value]:[])}>
                  <option value="">Ne pas reprendre</option>
                  {tariffs.map(t=><option key={t.id} value={t.id} disabled={selected.includes(t.id)&&!ids.includes(t.id)}>{t.label} · {t.classroom||"Toutes classes"} · {t.due_date||"Sans échéance"} · {money(t.amount)}</option>)}
                </select>
              </label>
              {ids.slice(1).map(id=>{const t=tariffs.find(item=>item.id===id);return <div key={id}><span>{t?.classroom||"Toutes classes"} · {money(t?.amount)}</span> <Button type="button" disabled={busy} onClick={()=>assignTariffs(i,ids.filter(x=>x!==id))}>Retirer</Button></div>;})}
              {alternatives.length>0&&<label className="field">Ajouter une variante de classe
                <select value="" disabled={busy||ids.length>=100} onChange={e=>{if(e.target.value)assignTariffs(i,[...ids,e.target.value]);}}>
                  <option value="">Sélectionner…</option>
                  {alternatives.map(t=><option key={t.id} value={t.id}>{t.classroom||"Toutes classes"} · {t.due_date||"Sans échéance"} · {money(t.amount)}</option>)}
                </select>
              </label>}
            </div>;
          })}
          {selectedColumns>12||selectedColumns*meta.row_count>2000||selected.length>240?<p role="alert">Limite : 12 colonnes, 240 tarifs et 2 000 cellules par aperçu. Fractionnez le fichier.</p>:null}
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
        <p className="hint">La préparation ne modifie aucun solde. Les cellules inconnues doivent être régularisées avant de préparer un lot. Un comptable distinct devra contrôler les justificatifs et approuver.</p>
        {canPrepare&&<Button type="button" disabled={busy||!valid||!rows.length||rows.some(r=>!["proposed","zero"].includes(r.status))} onClick={prepareBatch}>Préparer le lot pour validation comptable</Button>}
      </Card>}
    </div>
  </>;
}
