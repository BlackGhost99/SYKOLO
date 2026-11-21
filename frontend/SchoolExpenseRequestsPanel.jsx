import React, {useCallback, useEffect, useState} from "react";
import {Button,Card,Status,Table} from "./yem-ui.jsx";

const API="/api/v1/";
const STATES={
  draft:"Brouillon", submitted:"Soumise", in_review:"En examen",
  approved:"Validée pour instruction budgétaire", rejected:"Refusée",
  cancelled:"Annulée",
};
const urgencyLabels={normal:"Normale",high:"Prioritaire",critical:"Urgente"};
const initial=()=>({
  service:"",reason:"",description:"",category:"",subcategory:"",
  cost_center:"",quantity:"1.00",estimated_unit_price:"",estimated_amount:"",
  currency:"XAF",beneficiary_name:"",urgency:"normal",desired_on:"",
  supporting_reference:"",
});
async function api(path,method="GET",payload){
  if(method!=="GET"){
    const csrf=await fetch(API+"auth/csrf",{credentials:"same-origin"});
    if(!csrf.ok)throw Error("Session expirée.");
  }
  const token=document.cookie.split("; ").find(v=>v.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch(API+path,{
    method,credentials:"same-origin",
    headers:payload===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},
    body:payload===undefined?undefined:JSON.stringify(payload),
  });
  const body=await response.json().catch(()=>({error:"Réponse indisponible."}));
  if(!response.ok)throw Error(body.error||"Opération impossible.");
  return body;
}
function computeAmount(quantity,price){
  if(!quantity||!price)return "";
  const value=Number(quantity)*Number(price);
  return Number.isFinite(value)&&value>0?value.toFixed(2):"";
}

export default function SchoolExpenseRequestsPanel({
  schoolId,workingYearId="",canCreate=false,canReview=false,
}){
  const root="schools/"+schoolId+"/operating/school-requests";
  const [options,setOptions]=useState({categories:[],centers:[]});
  const [requests,setRequests]=useState([]);
  const [total,setTotal]=useState(0);
  const [pageOffset,setPageOffset]=useState(0);
  const [hasMore,setHasMore]=useState(false);
  const [statusFilter,setStatusFilter]=useState("");
  const [mineOnly,setMineOnly]=useState(false);
  const [form,setForm]=useState(initial);
  const [editId,setEditId]=useState("");
  const [editRevision,setEditRevision]=useState(0);
  const [selected,setSelected]=useState(null);
  const [decisionReason,setDecisionReason]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [creationKey,setCreationKey]=useState("");
  const [loading,setLoading]=useState(true);

  const refresh=useCallback(async()=>{
    const params=new URLSearchParams();
    if(workingYearId)params.set("year",workingYearId);
    if(statusFilter)params.set("status",statusFilter);
    if(mineOnly)params.set("mine","1");
    params.set("limit","30");
    params.set("offset",String(pageOffset));
    const [optionsData,list]=await Promise.all([
      api(root+"/options"),api(root+"?"+params.toString()),
    ]);
    setOptions(optionsData);
    setRequests(list.requests||[]);
    setTotal(list.total??0);
    setHasMore(Boolean(list.has_more));
  },[root,workingYearId,statusFilter,mineOnly,pageOffset]);
  useEffect(()=>{
    let alive=true;
    setLoading(true);
    refresh().catch(e=>{if(alive)setError(e.message);}).finally(()=>{if(alive)setLoading(false);});
    return()=>{alive=false;};
  },[refresh]);

  async function perform(fn,success){
    if(busy)return null;
    setBusy(true);setError("");setMessage("");
    try{
      const response=await fn();
      await refresh();
      setMessage(success);
      return response;
    }catch(e){setError(e.message);return null;}
    finally{setBusy(false);}
  }
  const roots=options.categories.filter(c=>!c.parent);
  const subs=options.categories.filter(c=>c.parent===form.category);
  async function save(event){
    event.preventDefault();
    if(!workingYearId){setError("Sélectionnez une année scolaire.");return;}
    const payload={
      ...form,year:workingYearId,
      subcategory:form.subcategory||null,
      cost_center:form.cost_center||null,
      estimated_unit_price:form.estimated_unit_price||null,
    };
    let result;
    if(editId){
      result=await perform(()=>api(root+"/"+editId,"PATCH",{
        ...payload,revision:editRevision,
      }),"Demande corrigée : aucun engagement financier créé.");
    }else{
      const key=creationKey||crypto.randomUUID();
      setCreationKey(key);
      result=await perform(()=>api(root,"POST",{
        ...payload,idempotency_key:key,
      }),"Demande enregistrée en brouillon : aucun paiement déclenché.");
    }
    if(result){
      setEditId("");setEditRevision(0);setCreationKey("");setForm(initial());
      setSelected(null);
    }
  }
  async function detail(id){
    setError("");setDecisionReason("");
    try{setSelected(await api(root+"/"+id));}
    catch(e){setError(e.message);}
  }
  function editDraft(){
    const row=selected?.request;
    if(!row)return;
    setEditId(row.id);setEditRevision(row.revision);
    setForm({
      service:row.service,reason:row.reason,description:row.description,
      category:row.category,subcategory:row.subcategory||"",
      cost_center:row.cost_center||"",quantity:row.quantity,
      estimated_unit_price:row.estimated_unit_price||"",
      estimated_amount:row.estimated_amount,currency:row.currency,
      beneficiary_name:row.beneficiary_name,urgency:row.urgency,
      desired_on:row.desired_on,supporting_reference:row.supporting_reference,
    });
    setSelected(null);
  }
  async function action(row,operation,extra={}){
    const saved=await perform(
      ()=>api(root+"/"+row.id+"/"+operation,"POST",{revision:row.revision,...extra}),
      operation==="submit"?"Demande soumise à la direction sans engagement.":
      operation==="cancel"?"Demande annulée et historique conservé.":
      extra.decision==="rejected"?"Refus motivé enregistré.":
      extra.decision==="in_review"?"Demande mise en examen.":
      "Demande validée pour instruction budgétaire, sans décaissement."
    );
    if(saved)await detail(row.id);
  }
  return <section aria-label="Demandes de dépenses scolaires">
    <Card title="Demandes de matériel et charges scolaires" icon="receipt"
      subtitle="Enseignants, personnel administratif et fonctions habilitées.">
      <p className="hint">Une demande n'est ni une facture, ni un engagement de budget, ni un paiement. Le circuit financier reste indépendant.</p>
      {error&&<p role="alert">{error}</p>}
      {message&&<p role="status">{message}</p>}
      {!workingYearId&&<p role="alert">Sélectionnez l'année scolaire dans YEM.</p>}
    </Card>
    {canCreate&&<Card title={editId?"Corriger ma demande":"Nouvelle demande scolaire"} icon="file">
      <form onSubmit={save}>
        <div className="two">
          <label className="field">Service demandeur<input required maxLength={120}
            placeholder="Pédagogie, informatique, vie scolaire…"
            value={form.service} onChange={e=>setForm({...form,service:e.target.value})}/></label>
          <label className="field">Objet de la demande<input required maxLength={200}
            placeholder="Ex. manuels, routeur, fournitures…"
            value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label>
          <label className="field">Catégorie<select required value={form.category}
            onChange={e=>setForm({...form,category:e.target.value,subcategory:""})}>
            <option value="">Sélectionner une catégorie</option>
            {roots.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select></label>
          <label className="field">Sous-catégorie<select value={form.subcategory}
            onChange={e=>setForm({...form,subcategory:e.target.value})}>
            <option value="">Aucune</option>
            {subs.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select></label>
          <label className="field">Centre de coûts scolaire<select value={form.cost_center}
            onChange={e=>setForm({...form,cost_center:e.target.value})}>
            <option value="">Non renseigné</option>
            {options.centers.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select></label>
          <label className="field">Quantité<input required inputMode="decimal"
            value={form.quantity} onChange={e=>setForm({
              ...form,quantity:e.target.value,
              estimated_amount:form.estimated_unit_price?
                computeAmount(e.target.value,form.estimated_unit_price):form.estimated_amount,
            })}/></label>
          <label className="field">Prix unitaire estimé (facultatif)<input inputMode="decimal"
            value={form.estimated_unit_price} onChange={e=>setForm({
              ...form,estimated_unit_price:e.target.value,
              estimated_amount:e.target.value?
                computeAmount(form.quantity,e.target.value):form.estimated_amount,
            })}/></label>
          <label className="field">Montant total estimé<input required inputMode="decimal"
            value={form.estimated_amount}
            readOnly={Boolean(form.estimated_unit_price)}
            onChange={e=>setForm({...form,estimated_amount:e.target.value})}/></label>
          <label className="field">Devise<select value={form.currency} onChange={e=>setForm({...form,currency:e.target.value})}>
            <option value="XAF">FCFA — XAF</option>
            <option value="EUR">EUR</option>
            <option value="USD">USD</option>
          </select></label>
          <label className="field">Fournisseur ou bénéficiaire pressenti<input required maxLength={180}
            placeholder="Nom du prestataire ou « à identifier »"
            value={form.beneficiary_name} onChange={e=>setForm({...form,beneficiary_name:e.target.value})}/></label>
          <label className="field">Urgence<select value={form.urgency}
            onChange={e=>setForm({...form,urgency:e.target.value})}>
            {Object.entries(urgencyLabels).map(([key,label])=>
              <option value={key} key={key}>{label}</option>)}
          </select></label>
          <label className="field">Date souhaitée<input required type="date" value={form.desired_on}
            onChange={e=>setForm({...form,desired_on:e.target.value})}/></label>
          <label className="field">Référence du devis ou justificatif (facultatif)<input maxLength={240}
            value={form.supporting_reference}
            onChange={e=>setForm({...form,supporting_reference:e.target.value})}/></label>
        </div>
        <label className="field">Motif détaillé<textarea required rows={3} maxLength={600}
          value={form.reason} onChange={e=>setForm({...form,reason:e.target.value})}/></label>
        <div className="actions">
          <Button primary type="submit" disabled={busy||!workingYearId||!roots.length}>
            {editId?"Enregistrer la correction":"Créer le brouillon"}
          </Button>
          {editId&&<Button type="button" onClick={()=>{setEditId("");setForm(initial());setCreationKey("");}}>
            Annuler la correction</Button>}
        </div>
        {!roots.length&&<p className="hint">La comptabilité doit d'abord définir une catégorie de dépenses.</p>}
      </form>
    </Card>}
    <Card title={canReview?"File des demandes scolaires":"Mes demandes scolaires"} icon="idcard">
      <div className="actions">
        <label className="field">État<select value={statusFilter}
          onChange={e=>{setStatusFilter(e.target.value);setPageOffset(0);}}>
          <option value="">Tous les états</option>
          {Object.entries(STATES).map(([k,v])=><option value={k} key={k}>{v}</option>)}
        </select></label>
        {canReview&&<label className="field">Visibilité<select value={mineOnly?"mine":"all"}
          onChange={e=>{setMineOnly(e.target.value==="mine");setPageOffset(0);}}>
          <option value="all">Toutes les demandes de l'établissement</option>
          <option value="mine">Mes demandes uniquement</option>
        </select></label>}
      </div>
      {loading&&<p>Chargement des demandes…</p>}
      <p>{total} demande(s) enregistrée(s) dans cette sélection.</p>
      <Table headers={["Objet","Demandeur","Service","Montant estimé","Urgence","Statut","Actions"]}
        rows={requests.map(row=>[
          row.description,row.requester_name,row.service,
          row.estimated_amount+" "+row.currency,urgencyLabels[row.urgency]||row.urgency,
          <Status tone={row.status==="approved"?"green":row.status==="rejected"?"red":
            row.status==="submitted"||row.status==="in_review"?"blue":"gray"}>{STATES[row.status]||row.status}</Status>,
          <Button key={row.id} className="small" onClick={()=>detail(row.id)}>Détails</Button>,
        ])}/>
      <div className="actions">
        <Button disabled={pageOffset<=0} onClick={()=>setPageOffset(Math.max(0,pageOffset-30))}>
          Précédent</Button>
        <Button disabled={!hasMore} onClick={()=>setPageOffset(pageOffset+30)}>
          Suivant</Button>
      </div>
    </Card>
    {selected&&<Card title={"Demande — "+selected.request.description} icon="shield">
      <Button onClick={()=>setSelected(null)}>Fermer</Button>
      <p><strong>{selected.request.requester_name}</strong> · {selected.request.requester_function}
        {" · "+selected.request.service}</p>
      <p>Motif : {selected.request.reason}</p>
      <p>Catégorie : {selected.request.category_label}
        {selected.request.subcategory_label?" / "+selected.request.subcategory_label:""}</p>
      <p>Quantité : {selected.request.quantity} · Estimation : <strong>
        {selected.request.estimated_amount+" "+selected.request.currency}</strong></p>
      <p>Urgence : {urgencyLabels[selected.request.urgency]||selected.request.urgency}
        {" · Date souhaitée : "+selected.request.desired_on}</p>
      <p>Fournisseur ou bénéficiaire pressenti : {selected.request.beneficiary_name}</p>
      {selected.request.supporting_reference&&<p>Justificatif déclaré : {selected.request.supporting_reference}</p>}
      <p><strong>État : {STATES[selected.request.status]||selected.request.status}</strong></p>
      <p className="hint">Montant non engagé et non décaissé. Le contrôle financier interviendra séparément.</p>
      {selected.history.length>0&&<details><summary>Historique ({selected.history.length})</summary>
        <Table headers={["Date","Action","Motif"]}
          rows={selected.history.map(e=>[new Date(e.happened_at).toLocaleString("fr-FR"),
            STATES[e.action]||e.action,e.reason||"—"])}/>
      </details>}
      {canCreate&&selected.request.is_mine&&
        ["draft","rejected"].includes(selected.request.status)&&
        <div className="actions">
          <Button disabled={busy} onClick={editDraft}>Corriger le brouillon</Button>
          {selected.request.status==="draft"&&<Button primary disabled={busy}
            onClick={()=>action(selected.request,"submit")}>Soumettre à la direction</Button>}
        </div>}
      {canCreate&&selected.request.is_mine&&
        ["draft","rejected","submitted","in_review"].includes(selected.request.status)&&
        <Button disabled={busy} onClick={()=>action(selected.request,"cancel")}>Annuler ma demande</Button>}
      {canReview&&!selected.request.is_mine&&
        ["submitted","in_review"].includes(selected.request.status)&&<div>
          <label className="field">Motif du refus ou observations<textarea maxLength={500}
            value={decisionReason} onChange={e=>setDecisionReason(e.target.value)}/></label>
          <div className="actions">
            {selected.request.status==="submitted"&&<Button disabled={busy}
              onClick={()=>action(selected.request,"review",{decision:"in_review"})}>
              Mettre en examen</Button>}
            {selected.request.status==="in_review"&&<Button primary disabled={busy}
              onClick={()=>action(selected.request,"review",{decision:"approved"})}>
              Valider pour instruction budgétaire</Button>}
            <Button disabled={busy||decisionReason.trim().length<10}
              onClick={()=>action(selected.request,"review",{
                decision:"rejected",reason:decisionReason.trim(),
              })}>Refuser avec motif</Button>
          </div>
        </div>}
    </Card>}
  </section>;
