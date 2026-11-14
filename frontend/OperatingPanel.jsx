import React, {useCallback, useEffect, useState} from "react";
import {Button, Card, Status, Table} from "./yem-ui.jsx";

const API="/api/v1/";
const today=()=>{const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");};
const fmt=(amount,currency)=>new Intl.NumberFormat("fr-FR",{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(amount||0))+" "+currency;
const METHODS=[["especes","Espèces (déclarées)"],["virement","Virement (déclaré)"],["mobile_money","Mobile Money (déclaré)"],["autre","Autre règlement"]];
const STATUS={draft:"À valider",approved:"Approuvée",partially_paid:"Partiellement réglée",paid:"Réglée"};
async function request(route,method="GET",data){
  if(method!=="GET"){
    const auth=await fetch(API+"auth/csrf",{credentials:"same-origin"});
    if(!auth.ok)throw Error("Session YEM expirée ou non sécurisée.");
  }
  const token=document.cookie.split("; ").find(s=>s.startsWith("csrftoken="))?.split("=")[1]||"";
  const res=await fetch(API+route,{
    method,credentials:"same-origin",
    headers:data===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},
    body:data===undefined?undefined:JSON.stringify(data),
  });
  const payload=await res.json().catch(()=>({error:"Réponse du serveur indisponible."}));
  if(!res.ok)throw Error(payload.error||"Opération refusée par l'établissement.");
  return payload;
}

export default function OperatingPanel({schoolId,workingYearId="",canManage=false,canApprove=false,canPay=false,canReverse=false}){
  const root="schools/"+schoolId+"/operating/";
  const [suppliers,setSuppliers]=useState([]);
  const [budgets,setBudgets]=useState([]);
  const [expenses,setExpenses]=useState([]);
  const [summary,setSummary]=useState(null);
  const [supplierForm,setSupplierForm]=useState({name:"",contact:"",phone:"",email:""});
  const [budgetForm,setBudgetForm]=useState({category:"",currency:"XAF",ceiling:""});
  const [expenseForm,setExpenseForm]=useState({budget:"",supplier:"",label:"",amount:"",invoice_reference:"",expense_on:today()});
  const [detail,setDetail]=useState(null);
  const [payment,setPayment]=useState({amount:"",method:"especes",reference:"",paid_on:today()});
  const [paymentKey,setPaymentKey]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const refresh=useCallback(async()=>{
    const qs=workingYearId?"?year="+encodeURIComponent(workingYearId):"";
    const [sup,bud,exp,sum]=await Promise.all([
      request(root+"suppliers"),request(root+"budgets"+qs),
      request(root+"expenses"+qs),request(root+"summary"+qs),
    ]);
    setSuppliers(sup.suppliers||[]);
    setBudgets(bud.budgets||[]);
    setExpenses(exp.expenses||[]);
    setSummary(sum);
  },[root,workingYearId]);
  useEffect(()=>{
    let active=true;
    setDetail(null);setError("");setMessage("");
    refresh().catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;};
  },[refresh]);
  async function op(action,ok){
    if(busy)return null;
    setBusy(true);setError("");setMessage("");
    try{
      const result=await action();
      await refresh();
      setMessage(ok);
      return result;
    }catch(e){setError(e.message);return null;}
    finally{setBusy(false);}
  }
  async function addSupplier(event){
    event.preventDefault();
    const result=await op(()=>request(root+"suppliers","POST",supplierForm),"Fournisseur ajouté.");
    if(result)setSupplierForm({name:"",contact:"",phone:"",email:""});
  }
  async function editSupplier(item){
    const name=window.prompt("Nom du fournisseur :",item.name);
    if(name===null||!name.trim())return;
    await op(()=>request(root+"suppliers/"+item.id,"PATCH",{revision:item.revision,name}),
      "Fournisseur mis à jour. Les anciennes dépenses conservent leur historique.");
  }
  async function addBudget(event){
    event.preventDefault();
    if(!workingYearId){setError("Sélectionnez une année scolaire dans YEM.");return;}
    const result=await op(()=>request(root+"budgets","POST",{...budgetForm,year:workingYearId}),
      "Budget proposé. La direction doit l'approuver avant utilisation.");
    if(result)setBudgetForm({...budgetForm,category:"",ceiling:""});
  }
  async function approveBudget(item){
    await op(()=>request(root+"budgets/"+item.id+"/approve","POST",{revision:item.revision}),
      "Enveloppe validée par le contrôleur.");
  }
  async function editBudget(item){
    const ceiling=window.prompt("Nouveau plafond (budget non encore validé) :",item.ceiling);
    if(ceiling===null)return;
    await op(()=>request(root+"budgets/"+item.id,"PATCH",{revision:item.revision,ceiling}),
      "Projet de budget mis à jour.");
  }
  async function addExpense(event){
    event.preventDefault();
    const saved=await op(()=>request(root+"expenses","POST",expenseForm),
      "Demande enregistrée. Un autre responsable doit l'approuver.");
    if(saved)setExpenseForm({...expenseForm,label:"",amount:"",invoice_reference:""});
  }
  async function openExpense(id){
    setError("");
    try{setDetail(await request(root+"expenses/"+id));}
    catch(e){setError(e.message);}
  }
  async function approveExpense(item){
    const saved=await op(()=>request(root+"expenses/"+item.id+"/approve","POST",{revision:item.revision}),
      "Dépense validée dans la limite du budget disponible.");
    if(saved)await openExpense(item.id);
  }
  async function editExpense(item){
    const amount=window.prompt("Nouveau montant (dépense en brouillon) :",item.amount);
    if(amount===null)return;
    const saved=await op(()=>request(root+"expenses/"+item.id,"PATCH",{revision:item.revision,amount}),
      "Demande corrigée.");
    if(saved)await openExpense(item.id);
  }
  async function markPaid(event){
    event.preventDefault();
    if(!detail)return;
    const key=paymentKey || crypto.randomUUID();
    setPaymentKey(key);
    const saved=await op(()=>request(root+"expenses/"+detail.expense.id+"/payments","POST",{
      ...payment,idempotency_key:key,
    }),"Versement manuel déclaré. Conservez la preuve de paiement.");
    if(saved){
      setPaymentKey("");
      setPayment({...payment,amount:"",reference:""});
      await openExpense(detail.expense.id);
    }
  }
  async function voidPayment(item){
    if(!detail)return;
    const reason=window.prompt("Motif contrôlé d'annulation (10 caractères minimum) :","");
    if(!reason)return;
    const saved=await op(()=>request(root+"payments/"+item.id+"/void","POST",{reason}),
      "Versement annulé, historique préservé.");
    if(saved)await openExpense(detail.expense.id);
  }
  const approvedBudgets=budgets.filter(b=>b.approved && Number(b.available)>0);
  const currentBudget=budgets.find(b=>b.id===expenseForm.budget);
  const statusTone=s=>s==="paid"?"green":s==="approved"?"blue":s==="partially_paid"?"orange":"gray";

  return <section aria-label="Dépenses, fournisseurs et budgets">
    <Card title="Dépenses et budgets de fonctionnement" icon="barchart"
      subtitle="Les achats de l'établissement, séparés des frais des élèves et des salaires.">
      <p className="hint">Toute dépense passe par un budget validé et un contrôle indépendant. Les règlements ne sont que des écritures déclaratives : YEM ne transmet aucun argent.</p>
      {error&&<p role="alert">{error}</p>}
      {message&&<p role="status">{message}</p>}
      {!workingYearId&&<p role="alert">Choisissez l'année scolaire dans la barre supérieure.</p>}
      {summary&&<div className="two">
        {Object.entries(summary.totals||{}).map(([unit,item])=>
          <p key={unit}><strong>Budget {unit} : {fmt(item.ceiling,unit)}</strong>
            <span style={{display:"block"}}>Engagé : {fmt(item.committed,unit)} · Déclaré payé : {fmt(item.paid,unit)}</span>
            <span style={{display:"block"}}>Disponible : {fmt(item.remaining,unit)}</span>
          </p>)}
        {!Object.keys(summary.totals||{}).length&&<p>Aucune enveloppe enregistrée pour cette année.</p>}
      </div>}
    </Card>
    <Card title="Fournisseurs et prestataires" icon="users"
      subtitle="Annuaire des fournisseurs de l’établissement, distinct du personnel.">
      {suppliers.length>0&&<Table headers={["Fournisseur","Contact","Téléphone","État","Action"]}
        rows={suppliers.map(s=>[s.name,s.contact||"—",s.phone||"—",
          <Status tone={s.active?"green":"gray"}>{s.active?"Actif":"Archivé"}</Status>,
          canManage?<Button className="small" disabled={busy} onClick={()=>editSupplier(s)}>Modifier</Button>:"—",
        ])}/>}
      {canManage&&<form onSubmit={addSupplier}>
        <div className="two">
          <label className="field">Nom fournisseur<input required maxLength={180} value={supplierForm.name} onChange={e=>setSupplierForm({...supplierForm,name:e.target.value})}/></label>
          <label className="field">Interlocuteur<input maxLength={160} value={supplierForm.contact} onChange={e=>setSupplierForm({...supplierForm,contact:e.target.value})}/></label>
          <label className="field">Téléphone<input maxLength={50} value={supplierForm.phone} onChange={e=>setSupplierForm({...supplierForm,phone:e.target.value})}/></label>
          <label className="field">Courriel<input type="email" value={supplierForm.email} onChange={e=>setSupplierForm({...supplierForm,email:e.target.value})}/></label>
        </div>
        <Button primary type="submit" disabled={busy}>Ajouter un fournisseur</Button>
      </form>}
    </Card>
    <Card title="Enveloppes budgétaires" icon="barchart"
      subtitle="Catégories libres par établissement, année et devise. Une enveloppe validée devient non modifiable.">
      {budgets.length>0&&<Table headers={["Catégorie","Plafond","Engagé","Disponible","Statut","Contrôle"]}
        rows={budgets.map(b=>[
          b.category,fmt(b.ceiling,b.currency),fmt(b.committed,b.currency),
          fmt(b.available,b.currency),<Status tone={b.approved?"green":"gray"}>{b.approved?"Approuvé":"Brouillon"}</Status>,
          !b.approved&&canApprove?<Button className="small" disabled={busy} onClick={()=>approveBudget(b)}>Approuver</Button>:
          !b.approved&&canManage?<Button className="small" disabled={busy} onClick={()=>editBudget(b)}>Modifier</Button>:"—",
        ])}/>}
      {canManage&&<form onSubmit={addBudget}>
        <div className="two">
          <label className="field">Catégorie de dépense<input required maxLength={100} placeholder="Ex. Entretien, électricité, fournitures" value={budgetForm.category} onChange={e=>setBudgetForm({...budgetForm,category:e.target.value})}/></label>
          <label className="field">Plafond<input required inputMode="decimal" value={budgetForm.ceiling} onChange={e=>setBudgetForm({...budgetForm,ceiling:e.target.value})}/></label>
          <label className="field">Devise<input required maxLength={3} value={budgetForm.currency} onChange={e=>setBudgetForm({...budgetForm,currency:e.target.value.toUpperCase()})}/></label>
        </div>
        <Button primary type="submit" disabled={busy||!workingYearId}>Proposer le budget</Button>
      </form>}
    </Card>
    <Card title="Demandes de dépenses" icon="idcard"
      subtitle="Achat, facture ou intervention justifiée : préparation, validation puis règlement.">
      {expenses.length>0&&<Table headers={["Objet","Fournisseur","Montant","Déclaré payé","Solde","État","Dossier"]}
        rows={expenses.map(e=>[
          e.label,e.supplier_name,fmt(e.amount,e.currency),fmt(e.paid,e.currency),
          fmt(e.balance,e.currency),
          <Status tone={statusTone(e.status)}>{STATUS[e.status]||e.status}</Status>,
          <Button className="small" onClick={()=>openExpense(e.id)}>Détail</Button>,
        ])}/>}
      {!expenses.length&&<p>Aucune dépense pour l'année sélectionnée.</p>}
      {canManage&&<form onSubmit={addExpense}>
        <div className="two">
          <label className="field">Enveloppe approuvée<select required value={expenseForm.budget} onChange={e=>setExpenseForm({...expenseForm,budget:e.target.value})}>
            <option value="">Sélectionner un budget</option>
            {approvedBudgets.map(b=><option key={b.id} value={b.id}>{b.category} · {fmt(b.available,b.currency)} disponibles</option>)}
          </select></label>
          <label className="field">Fournisseur<select required value={expenseForm.supplier} onChange={e=>setExpenseForm({...expenseForm,supplier:e.target.value})}>
            <option value="">Sélectionner un fournisseur</option>
            {suppliers.filter(s=>s.active).map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
          </select></label>
          <label className="field">Objet de l'achat<input required maxLength={200} value={expenseForm.label} onChange={e=>setExpenseForm({...expenseForm,label:e.target.value})}/></label>
          <label className="field">Montant demandé{currentBudget?" ("+currentBudget.currency+")":""}<input required inputMode="decimal" value={expenseForm.amount} onChange={e=>setExpenseForm({...expenseForm,amount:e.target.value})}/></label>
          <label className="field">Référence facture/devis<input required maxLength={120} value={expenseForm.invoice_reference} onChange={e=>setExpenseForm({...expenseForm,invoice_reference:e.target.value})}/></label>
          <label className="field">Date de dépense<input required type="date" value={expenseForm.expense_on} onChange={e=>setExpenseForm({...expenseForm,expense_on:e.target.value})}/></label>
        </div>
        <Button primary type="submit" disabled={busy||!approvedBudgets.length||!suppliers.some(s=>s.active)}>Préparer la demande</Button>
      </form>}
    </Card>
    {detail&&<Card title={"Dépense — "+detail.expense.label} icon="shield">
      <div className="actions"><Button onClick={()=>setDetail(null)}>Fermer</Button></div>
      <p>Fournisseur : <strong>{detail.expense.supplier_name}</strong> · Budget : {detail.expense.category}</p>
      <p>Référence : {detail.expense.invoice_reference} · Date : {detail.expense.expense_on}</p>
      <p>Montant : <strong>{fmt(detail.expense.amount,detail.expense.currency)}</strong> · Déclaré réglé : {fmt(detail.expense.paid,detail.expense.currency)} · Reste : <strong>{fmt(detail.expense.balance,detail.expense.currency)}</strong></p>
      <p>Statut : <Status tone={statusTone(detail.expense.status)}>{STATUS[detail.expense.status]||detail.expense.status}</Status></p>
      {canApprove&&detail.expense.status==="draft"&&<Button disabled={busy} onClick={()=>approveExpense(detail.expense)}>Approuver dans la limite du budget</Button>}
      {canManage&&detail.expense.status==="draft"&&<Button disabled={busy} onClick={()=>editExpense(detail.expense)}>Corriger le montant</Button>}
      {canPay&&["approved","partially_paid"].includes(detail.expense.status)&&<form onSubmit={markPaid}>
        <p className="hint">Déclarer uniquement un paiement déjà effectué : renseignez la preuve et sa référence. Aucune sortie de fonds n'est déclenchée par YEM.</p>
        <div className="two">
          <label className="field">Montant<input required inputMode="decimal" value={payment.amount} onChange={e=>{setPayment({...payment,amount:e.target.value});setPaymentKey("");}}/></label>
          <label className="field">Méthode<select value={payment.method} onChange={e=>{setPayment({...payment,method:e.target.value});setPaymentKey("");}}>
            {METHODS.map(([v,n])=><option key={v} value={v}>{n}</option>)}
          </select></label>
          <label className="field">Référence paiement<input required maxLength={120} value={payment.reference} onChange={e=>{setPayment({...payment,reference:e.target.value});setPaymentKey("");}}/></label>
          <label className="field">Date<input required type="date" max={today()} value={payment.paid_on} onChange={e=>{setPayment({...payment,paid_on:e.target.value});setPaymentKey("");}}/></label>
        </div>
        <Button primary type="submit" disabled={busy}>Enregistrer le règlement déclaré</Button>
      </form>}
      {detail.payments?.length>0&&<Table headers={["Date","Montant","Mode","Justificatif","État","Contrôle"]}
        rows={detail.payments.map(p=>[
          p.paid_on,fmt(p.amount,detail.expense.currency),METHODS.find(([v])=>v===p.method)?.[1]||p.method,
          p.reference,<Status tone={p.voided?"gray":"green"}>{p.voided?"Annulé":"Enregistré"}</Status>,
          canReverse&&!p.voided?<Button className="small" disabled={busy} onClick={()=>voidPayment(p)}>Annuler sous contrôle</Button>:"—",
        ])}/>}
    </Card>}
  </section>;
}
