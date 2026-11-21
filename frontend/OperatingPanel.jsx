import React, {useCallback, useEffect, useState} from "react";
import {Button, Card, Status, Table} from "./yem-ui.jsx";

const API="/api/v1/";
const today=()=>{const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");};
const fmt=(amount,currency)=>new Intl.NumberFormat("fr-FR",{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(amount||0))+" "+currency;
const METHODS=[["especes","Espèces (déclarées)"],["virement","Virement (déclaré)"],["mobile_money","Mobile Money (déclaré)"],["autre","Autre règlement"]];
const STATUS={draft:"Brouillon",submitted:"En attente de validation",rejected:"Refusée",approved:"Autorisée",partially_paid:"Partiellement réglée",paid:"Réglée"};
const POLES=[
  ["school","Scolarité"],["extraschool","Extrascolarité"],
  ["common","Administration et charges communes"],["investment","Investissements"],
  ["cash_other","Autres sorties de trésorerie"],
];
const POLE_LABELS={unclassified:"À classer (historique)",...Object.fromEntries(POLES)};
const BENEFICIARY_TYPES=[
  ["supplier","Fournisseur ou prestataire"],
  ["staff","Personnel — hors rémunération"],
  ["government","Administration ou organisme public"],
  ["parent","Parent ou responsable légal"],
  ["individual","Personne physique"],
  ["organization","Organisation ou association"],
  ["other","Autre bénéficiaire"],
];
const BENEFICIARY_LABELS=Object.fromEntries(BENEFICIARY_TYPES);
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
  const [categories,setCategories]=useState([]);
  const [showCatalog,setShowCatalog]=useState(false);
  const [categoryForm,setCategoryForm]=useState({code:"",name:"",parent:"",suggested_pole:""});
  const [editingCategory,setEditingCategory]=useState(null);
  const [archiveTarget,setArchiveTarget]=useState("");
  const [budgets,setBudgets]=useState([]);
  const [expenses,setExpenses]=useState([]);
  const [summary,setSummary]=useState(null);
  const [supplierForm,setSupplierForm]=useState({name:"",contact:"",phone:"",email:""});
  const [budgetForm,setBudgetForm]=useState({category:"",currency:"XAF",ceiling:""});
  const [expenseForm,setExpenseForm]=useState({
    budget:"",supplier:"",label:"",amount:"",invoice_reference:"",
    expense_on:today(),activity_pole:"",cost_center:"",accounting_nature:"",
    category_ref:"",subcategory_ref:"",
    beneficiary_type:"supplier",beneficiary_name:"",beneficiary_reference:"",
  });
  const [poleFilter,setPoleFilter]=useState("");
  const [draftClassification,setDraftClassification]=useState({activity_pole:"",cost_center:"",accounting_nature:"",category_ref:"",subcategory_ref:""});
  const [draftBeneficiary,setDraftBeneficiary]=useState({
    beneficiary_type:"supplier",supplier:"",beneficiary_name:"",beneficiary_reference:"",
  });
  const [detail,setDetail]=useState(null);
  const [rejectionReason,setRejectionReason]=useState("");
  const [payment,setPayment]=useState({amount:"",method:"especes",reference:"",paid_on:today()});
  const [paymentKey,setPaymentKey]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const refresh=useCallback(async()=>{
    const qs=workingYearId?"?year="+encodeURIComponent(workingYearId):"";
    const expenseQs=qs+(poleFilter?(qs?"&":"?")+"activity_pole="+encodeURIComponent(poleFilter):"");
    const [sup,cat,bud,exp,sum]=await Promise.all([
      request(root+"suppliers"),request(root+"categories"),request(root+"budgets"+qs),
      request(root+"expenses"+expenseQs),request(root+"summary"+qs),
    ]);
    setSuppliers(sup.suppliers||[]);
    setCategories(cat.categories||[]);
    setBudgets(bud.budgets||[]);
    setExpenses(exp.expenses||[]);
    setSummary(sum);
  },[root,workingYearId,poleFilter]);
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
    const payload={
      ...expenseForm,
      supplier:expenseForm.beneficiary_type==="supplier"?expenseForm.supplier:null,
      beneficiary_name:expenseForm.beneficiary_type==="supplier"?"":expenseForm.beneficiary_name,
    };
    const saved=await op(()=>request(root+"expenses","POST",payload),
      "Demande enregistrée. Un autre responsable doit l'approuver.");
    if(saved)setExpenseForm({...expenseForm,label:"",amount:"",invoice_reference:"",subcategory_ref:""});
  }
  async function openExpense(id){
    setError("");
    try{
      const data=await request(root+"expenses/"+id);
      setDetail(data);
      setRejectionReason("");
      setDraftClassification({
        activity_pole:data.expense.activity_pole==="unclassified"?"":data.expense.activity_pole,
        cost_center:data.expense.cost_center||"",
        accounting_nature:data.expense.accounting_nature||"",
        category_ref:data.expense.category_ref||"",
        subcategory_ref:data.expense.subcategory_ref||"",
      });
      setDraftBeneficiary({
        beneficiary_type:data.expense.beneficiary_type||"supplier",
        supplier:data.expense.supplier||"",
        beneficiary_name:data.expense.beneficiary_type==="supplier"?"":data.expense.beneficiary_name||"",
        beneficiary_reference:data.expense.beneficiary_reference||"",
      });
    }catch(e){setError(e.message);}
  }
  async function updateDraftClassification(event){
    event.preventDefault();
    if(!detail)return;
    const saved=await op(()=>request(root+"expenses/"+detail.expense.id,"PATCH",{
      revision:detail.expense.revision,...draftClassification,
    }),"Classification du projet enregistrée.");
    if(saved)await openExpense(detail.expense.id);
  }
  async function updateDraftBeneficiary(event){
    event.preventDefault();
    if(!detail)return;
    const saved=await op(()=>request(root+"expenses/"+detail.expense.id,"PATCH",{
      revision:detail.expense.revision,
      beneficiary_type:draftBeneficiary.beneficiary_type,
      supplier:draftBeneficiary.beneficiary_type==="supplier"?draftBeneficiary.supplier:null,
      beneficiary_name:draftBeneficiary.beneficiary_type==="supplier"?"":draftBeneficiary.beneficiary_name,
      beneficiary_reference:draftBeneficiary.beneficiary_reference,
    }),"Bénéficiaire du projet mis à jour.");
    if(saved)await openExpense(detail.expense.id);
  }
  async function submitExpense(item){
    const saved=await op(()=>request(root+"expenses/"+item.id+"/submit","POST",{
      revision:item.revision,
    }),"Demande soumise au contrôleur. Aucun fonds n'est engagé avant autorisation.");
    if(saved)await openExpense(item.id);
  }
  async function rejectExpense(event){
    event.preventDefault();
    if(!detail||rejectionReason.trim().length<10)return;
    const item=detail.expense;
    const saved=await op(()=>request(root+"expenses/"+item.id+"/reject","POST",{
      revision:item.revision,reason:rejectionReason.trim(),
    }),"Demande refusée. Motif enregistré ; une correction est requise pour la soumettre à nouveau.");
    if(saved)await openExpense(item.id);
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
  async function addCategory(event){
    event.preventDefault();
    const saved=await op(()=>request(root+"categories","POST",{
      ...categoryForm,parent:categoryForm.parent||null,
    }),"Catégorie de dépenses ajoutée.");
    if(saved)setCategoryForm({code:"",name:"",parent:"",suggested_pole:""});
  }
  async function updateCategory(event){
    event.preventDefault();
    if(!editingCategory)return;
    const saved=await op(()=>request(root+"categories/"+editingCategory.id,"PATCH",{
      revision:editingCategory.revision,name:editingCategory.name,
      suggested_pole:editingCategory.suggested_pole,
    }),"Catégorie actualisée ; les anciens libellés des dépenses sont conservés.");
    if(saved)setEditingCategory(null);
  }
  async function toggleCategory(item){
    const saved=await op(()=>request(root+"categories/"+item.id,"PATCH",{
      revision:item.revision,active:!item.active,
    }),item.active?"Catégorie archivée sans supprimer les opérations.":"Catégorie réactivée.");
    if(saved)setArchiveTarget("");
  }
  const categoryRoots=categories.filter(c=>!c.parent);
  const activeRoots=categoryRoots.filter(c=>c.active);
  const selectableSubs=(parentId)=>categories.filter(c=>c.parent===parentId&&c.active);
  const approvedBudgets=budgets.filter(b=>b.approved && Number(b.available)>0);
  const currentBudget=budgets.find(b=>b.id===expenseForm.budget);
  const statusTone=s=>s==="paid"?"green":s==="approved"?"blue":s==="partially_paid"?"orange":s==="rejected"?"red":s==="submitted"?"blue":"gray";

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
    <Card title="Ventilation des sorties par activité" icon="barchart"
      subtitle="Engagements approuvés et règlements déclarés, sans mélange avec les recettes.">
      {Object.entries(summary?.by_activity_pole||{}).flatMap(([currency,groups])=>
        Object.entries(groups).map(([pole,values])=>
          <p key={currency+"-"+pole}>
            <strong>{POLE_LABELS[pole]||pole} · {currency}</strong>
            <span style={{display:"block"}}>Engagé : {fmt(values.committed,currency)} · Déclaré payé : {fmt(values.paid,currency)} · Reste : {fmt(values.unpaid,currency)}</span>
          </p>))}
      {!Object.keys(summary?.by_activity_pole||{}).length&&<p>Aucune sortie approuvée sur cette période.</p>}
      <p className="hint">Les anciennes dépenses non classées restent visibles sans réaffectation automatique.</p>
    </Card>
    <div className="actions">
      <Button onClick={()=>setShowCatalog(!showCatalog)}>{showCatalog?"Masquer le catalogue":"Configurer les catégories de dépenses"}</Button>
    </div>
    {showCatalog&&<Card title="Catalogue de dépenses" icon="idcard"
      subtitle="Catégories et sous-catégories personnalisables par établissement. Archivage sans suppression.">
      {categories.length>0&&<Table headers={["Code","Catégorie / sous-catégorie","Pôle suggéré","État","Actions"]}
        rows={categories.map(item=>[
          item.code,(item.parent?"↳ ":"")+item.name,
          POLE_LABELS[item.suggested_pole]||"Non défini",
          <Status tone={item.active?"green":"gray"}>{item.active?"Active":"Archivée"}</Status>,
          canManage?<div className="actions">
            <Button className="small" disabled={busy} onClick={()=>{setEditingCategory({...item});setArchiveTarget("");}}>Modifier</Button>
            {archiveTarget===item.id?
              <>
                <Button className="small" disabled={busy} onClick={()=>toggleCategory(item)}>Confirmer {item.active?"archivage":"réactivation"}</Button>
                <Button className="small" onClick={()=>setArchiveTarget("")}>Annuler</Button>
              </>:
              <Button className="small" disabled={busy} onClick={()=>setArchiveTarget(item.id)}>{item.active?"Archiver":"Réactiver"}</Button>}
          </div>:"—",
        ])}/>}
      {!categories.length&&<p>Ce catalogue est vide. Les catégories proposées dans les exemples ne sont pas créées automatiquement.</p>}
      {canManage&&<form onSubmit={addCategory}>
        <div className="two">
          <label className="field">Code catégorie / sous-catégorie<input required maxLength={40} pattern="[a-z][a-z0-9_-]*"
            placeholder="ex. fournitures" value={categoryForm.code} onChange={e=>setCategoryForm({...categoryForm,code:e.target.value.toLowerCase()})}/></label>
          <label className="field">Nom catégorie / sous-catégorie<input required maxLength={100} value={categoryForm.name} onChange={e=>setCategoryForm({...categoryForm,name:e.target.value})}/></label>
          <label className="field">Catégorie parente<select value={categoryForm.parent} onChange={e=>setCategoryForm({...categoryForm,parent:e.target.value})}>
            <option value="">Aucune — catégorie principale</option>
            {activeRoots.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select></label>
          <label className="field">Pôle suggéré<select value={categoryForm.suggested_pole} onChange={e=>setCategoryForm({...categoryForm,suggested_pole:e.target.value})}>
            <option value="">Aucun — classification indépendante</option>
            {POLES.map(([key,label])=><option key={key} value={key}>{label}</option>)}
          </select></label>
        </div>
        <Button primary type="submit" disabled={busy}>Ajouter cette catégorie</Button>
      </form>}
      {canManage&&editingCategory&&<form onSubmit={updateCategory}>
        <p><strong>Modifier {editingCategory.code}</strong> — le code et le parent restent fixes.</p>
        <div className="two">
          <label className="field">Nouveau libellé<input required maxLength={100}
            value={editingCategory.name} onChange={e=>setEditingCategory({...editingCategory,name:e.target.value})}/></label>
          <label className="field">Pôle conseillé<select value={editingCategory.suggested_pole} onChange={e=>setEditingCategory({...editingCategory,suggested_pole:e.target.value})}>
            <option value="">Aucun</option>
            {POLES.map(([key,label])=><option key={key} value={key}>{label}</option>)}
          </select></label>
        </div>
        <div className="actions">
          <Button primary type="submit" disabled={busy}>Enregistrer la catégorie</Button>
          <Button type="button" onClick={()=>setEditingCategory(null)}>Annuler</Button>
        </div>
      </form>}
      <p className="hint">Modifier une catégorie ne modifie pas les libellés des dépenses déjà enregistrées.</p>
    </Card>}
    <Card title="Fournisseurs et prestataires" icon="users"
      subtitle="Annuaire des fournisseurs de l’établissement, distinct du personnel.">
      {suppliers.length>0&&<Table rowKey={(_,i)=>suppliers[i].id} rowActions={(_,i)=>canManage?[{id:"edit",label:"Modifier le fournisseur",write:true,disabled:busy,run:()=>editSupplier(suppliers[i])}]:[]} headers={["Fournisseur","Contact","Téléphone","État","Action"]}
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
      <label className="field">Filtrer les dépenses par activité<select value={poleFilter} onChange={e=>setPoleFilter(e.target.value)}>
        <option value="">Toutes les activités</option>
        {POLES.map(([key,label])=><option key={key} value={key}>{label}</option>)}
        <option value="unclassified">À classer (historique)</option>
      </select></label>
      {expenses.length>0&&<Table rowKey={(_,i)=>expenses[i].id} rowActions={(_,i)=>[{id:"detail",label:"Consulter la dépense",run:()=>openExpense(expenses[i].id)}]} headers={["Objet","Pôle financier","Bénéficiaire","Montant","Déclaré payé","Solde","État","Dossier"]}
        rows={expenses.map(e=>[
          e.label,POLE_LABELS[e.activity_pole]||"À classer",e.beneficiary_name||e.supplier_name||"—",fmt(e.amount,e.currency),fmt(e.paid,e.currency),
          fmt(e.balance,e.currency),
          <Status tone={statusTone(e.status)}>{STATUS[e.status]||e.status}</Status>,
          <Button className="small" onClick={()=>openExpense(e.id)}>Détail</Button>,
        ])}/>}
      {!expenses.length&&<p>Aucune dépense pour l'année sélectionnée.</p>}
      {canManage&&<form onSubmit={addExpense}>
        <p className="hint">Les salaires passent exclusivement par le module Paie ; une indemnité hors paie peut être affectée au personnel. Les remboursements de frais scolaires restent à rapprocher dans le circuit dédié.</p>
        <div className="two">
          <label className="field">Enveloppe approuvée<select required value={expenseForm.budget} onChange={e=>setExpenseForm({...expenseForm,budget:e.target.value})}>
            <option value="">Sélectionner un budget</option>
            {approvedBudgets.map(b=><option key={b.id} value={b.id}>{b.category} · {fmt(b.available,b.currency)} disponibles</option>)}
          </select></label>
          <label className="field">Catégorie de la dépense<select required value={expenseForm.category_ref}
            onChange={e=>{const item=categories.find(c=>c.id===e.target.value);setExpenseForm({
              ...expenseForm,category_ref:e.target.value,subcategory_ref:"",
              activity_pole:expenseForm.activity_pole||item?.suggested_pole||"",
            });}}>
            <option value="">Choisir une catégorie active</option>
            {activeRoots.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select></label>
          <label className="field">Sous-catégorie de la dépense<select value={expenseForm.subcategory_ref}
            onChange={e=>setExpenseForm({...expenseForm,subcategory_ref:e.target.value})}>
            <option value="">Aucune</option>
            {selectableSubs(expenseForm.category_ref).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select></label>
          <label className="field">Pôle financier<select required value={expenseForm.activity_pole} onChange={e=>setExpenseForm({...expenseForm,activity_pole:e.target.value})}>
            <option value="">Choisir l'activité concernée</option>
            {POLES.map(([key,label])=><option key={key} value={key}>{label}</option>)}
          </select></label>
          <label className="field">Centre de coûts<input maxLength={100} placeholder="Ex. Administration, collège, cantine" value={expenseForm.cost_center} onChange={e=>setExpenseForm({...expenseForm,cost_center:e.target.value})}/></label>
          <label className="field">Nature comptable<input maxLength={100} placeholder="Ex. Entretien, achats, immobilisation" value={expenseForm.accounting_nature} onChange={e=>setExpenseForm({...expenseForm,accounting_nature:e.target.value})}/></label>
          <label className="field">Type de bénéficiaire<select required value={expenseForm.beneficiary_type}
            onChange={e=>setExpenseForm({...expenseForm,beneficiary_type:e.target.value,supplier:"",beneficiary_name:"",beneficiary_reference:""})}>
            {BENEFICIARY_TYPES.map(([key,name])=><option key={key} value={key}>{name}</option>)}
          </select></label>
          {expenseForm.beneficiary_type==="supplier"?
            <label className="field">Fournisseur<select required value={expenseForm.supplier} onChange={e=>setExpenseForm({...expenseForm,supplier:e.target.value})}>
              <option value="">Sélectionner un fournisseur</option>
              {suppliers.filter(s=>s.active).map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
            </select></label>:
            <label className="field">Nom du bénéficiaire<input required maxLength={180}
              placeholder="Identité ou dénomination du bénéficiaire" value={expenseForm.beneficiary_name}
              onChange={e=>setExpenseForm({...expenseForm,beneficiary_name:e.target.value})}/></label>}
          <label className="field">Référence interne du bénéficiaire<input maxLength={120}
            placeholder="Référence de dossier non sensible (facultatif)" value={expenseForm.beneficiary_reference}
            onChange={e=>setExpenseForm({...expenseForm,beneficiary_reference:e.target.value})}/></label>
          <label className="field">Objet de l'achat<input required maxLength={200} value={expenseForm.label} onChange={e=>setExpenseForm({...expenseForm,label:e.target.value})}/></label>
          <label className="field">Montant demandé{currentBudget?" ("+currentBudget.currency+")":""}<input required inputMode="decimal" value={expenseForm.amount} onChange={e=>setExpenseForm({...expenseForm,amount:e.target.value})}/></label>
          <label className="field">Référence facture/devis<input required maxLength={120} value={expenseForm.invoice_reference} onChange={e=>setExpenseForm({...expenseForm,invoice_reference:e.target.value})}/></label>
          <label className="field">Date de dépense<input required type="date" value={expenseForm.expense_on} onChange={e=>setExpenseForm({...expenseForm,expense_on:e.target.value})}/></label>
        </div>
        <Button primary type="submit" disabled={busy||!approvedBudgets.length||!activeRoots.length||
          (expenseForm.beneficiary_type==="supplier"&&!suppliers.some(s=>s.active))}>Préparer la demande</Button>
      </form>}
    </Card>
    {detail&&<Card title={"Dépense — "+detail.expense.label} icon="shield">
      <div className="actions"><Button onClick={()=>setDetail(null)}>Fermer</Button></div>
      <p>Bénéficiaire : <strong>{detail.expense.beneficiary_name||detail.expense.supplier_name||"—"}</strong>
        {" · "+(BENEFICIARY_LABELS[detail.expense.beneficiary_type]||"Fournisseur")}
        {" · Budget : "+detail.expense.category}
        {detail.expense.beneficiary_reference?" · Référence interne : "+detail.expense.beneficiary_reference:""}
      </p>
      <p>Catégorie : <strong>{detail.expense.expense_category||"À classer (historique)"}</strong>
        {detail.expense.expense_subcategory?" / "+detail.expense.expense_subcategory:""}
      </p>
      <p>Activité : <strong>{POLE_LABELS[detail.expense.activity_pole]||"À classer"}</strong>
        {detail.expense.cost_center?" · Centre de coûts : "+detail.expense.cost_center:""}
        {detail.expense.accounting_nature?" · Nature comptable : "+detail.expense.accounting_nature:""}
      </p>
      {canManage&&detail.expense.status==="draft"&&<form onSubmit={updateDraftClassification}>
        <div className="two">
          <label className="field">Catégorie du projet<select required value={draftClassification.category_ref}
            onChange={e=>setDraftClassification({...draftClassification,category_ref:e.target.value,subcategory_ref:""})}>
            <option value="">Choisir une catégorie active</option>
            {activeRoots.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select></label>
          <label className="field">Sous-catégorie du projet<select value={draftClassification.subcategory_ref}
            onChange={e=>setDraftClassification({...draftClassification,subcategory_ref:e.target.value})}>
            <option value="">Aucune</option>
            {selectableSubs(draftClassification.category_ref).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select></label>
          <label className="field">Pôle de cette dépense<select required value={draftClassification.activity_pole} onChange={e=>setDraftClassification({...draftClassification,activity_pole:e.target.value})}>
            <option value="">Choisir le pôle</option>
            {POLES.map(([key,label])=><option key={key} value={key}>{label}</option>)}
          </select></label>
          <label className="field">Centre de coûts du projet<input maxLength={100} value={draftClassification.cost_center} onChange={e=>setDraftClassification({...draftClassification,cost_center:e.target.value})}/></label>
          <label className="field">Nature comptable du projet<input maxLength={100} value={draftClassification.accounting_nature} onChange={e=>setDraftClassification({...draftClassification,accounting_nature:e.target.value})}/></label>
        </div>
        <Button type="submit" disabled={busy}>Enregistrer la classification</Button>
      </form>}
      {canManage&&detail.expense.status==="draft"&&<form onSubmit={updateDraftBeneficiary}>
        <p className="hint">Modifier uniquement les brouillons. L'identité du bénéficiaire est figée après approbation.</p>
        <div className="two">
          <label className="field">Type de bénéficiaire du projet<select required value={draftBeneficiary.beneficiary_type}
            onChange={e=>setDraftBeneficiary({...draftBeneficiary,beneficiary_type:e.target.value,supplier:"",beneficiary_name:"",beneficiary_reference:""})}>
            {BENEFICIARY_TYPES.map(([key,name])=><option key={key} value={key}>{name}</option>)}
          </select></label>
          {draftBeneficiary.beneficiary_type==="supplier"?
            <label className="field">Fournisseur du projet<select required value={draftBeneficiary.supplier}
              onChange={e=>setDraftBeneficiary({...draftBeneficiary,supplier:e.target.value})}>
              <option value="">Sélectionner un fournisseur actif</option>
              {suppliers.filter(s=>s.active||s.id===detail.expense.supplier).map(s=>
                <option key={s.id} value={s.id}>{s.name}</option>)}
            </select></label>:
            <label className="field">Nom du bénéficiaire du projet<input required maxLength={180}
              value={draftBeneficiary.beneficiary_name}
              onChange={e=>setDraftBeneficiary({...draftBeneficiary,beneficiary_name:e.target.value})}/></label>}
          <label className="field">Référence interne du bénéficiaire du projet<input maxLength={120}
            value={draftBeneficiary.beneficiary_reference}
            onChange={e=>setDraftBeneficiary({...draftBeneficiary,beneficiary_reference:e.target.value})}/></label>
        </div>
        <Button type="submit" disabled={busy}>Mettre à jour le bénéficiaire</Button>
      </form>}
      <p>Référence : {detail.expense.invoice_reference} · Date : {detail.expense.expense_on}</p>
      <p>Montant : <strong>{fmt(detail.expense.amount,detail.expense.currency)}</strong> · Déclaré réglé : {fmt(detail.expense.paid,detail.expense.currency)} · Reste : <strong>{fmt(detail.expense.balance,detail.expense.currency)}</strong></p>
      <p>Statut : <Status tone={statusTone(detail.expense.status)}>{STATUS[detail.expense.status]||detail.expense.status}</Status></p>
      {detail.decisions?.length>0&&<details>
        <summary>Historique des autorisations ({detail.decisions.length})</summary>
        <Table headers={["Date","Décision","Compte","Justification"]}
          rows={detail.decisions.map(item=>[
            new Date(item.occurred_at).toLocaleString("fr-FR"),
            ({submitted:"Soumission",approved:"Autorisation",rejected:"Refus",revised:"Correction"})[item.action]||item.action,
            item.actor,item.reason||"—",
          ])}/>
      </details>}
      {canManage&&["draft","rejected"].includes(detail.expense.status)&&<Button disabled={busy||detail.expense.status==="rejected"} onClick={()=>submitExpense(detail.expense)}>
        Soumettre pour autorisation
      </Button>}
      {canApprove&&detail.expense.status==="submitted"&&<>
        <Button disabled={busy} onClick={()=>approveExpense(detail.expense)}>Autoriser la dépense</Button>
        <form onSubmit={rejectExpense}>
          <label className="field">Motif du refus (10 caractères minimum)
            <textarea required minLength={10} maxLength={240} rows={2}
              value={rejectionReason} onChange={e=>setRejectionReason(e.target.value)}
              placeholder="Expliquez précisément la correction nécessaire"/>
          </label>
          <Button type="submit" disabled={busy||rejectionReason.trim().length<10}>Refuser la demande</Button>
        </form>
      </>}
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
