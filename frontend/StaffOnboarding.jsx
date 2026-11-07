import React, {useEffect, useMemo, useState} from "react";
import CycleScopeManager from "./CycleScopeManager.jsx";

const EMPTY_STAFF = {staff_code:"", first_name:"", last_name:"", position:""};
const EMPTY_APPOINTMENT = {function_code:"", cycle_code:"", starts_on:"", ends_on:""};
const EMPTY_CLASS = {year:"", classroom:"", duty:"enseignant"};
const EMPTY_ACCOUNT = {username:"", email:"", password:"", role:"", additional_roles:[]};

async function request(path, data) {
  if (data !== undefined) {
    const csrf = await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
    if (!csrf.ok) throw Error("Session expirée ou non sécurisée.");
  }
  const token = document.cookie.split("; ").find(c=>c.startsWith("csrftoken="))?.split("=")[1] || "";
  const response = await fetch("/api/v1/"+path, {
    method:data===undefined?"GET":"POST", credentials:"same-origin",
    headers:data===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":token},
    body:data===undefined?undefined:JSON.stringify(data),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw Error("Réponse inattendue du serveur YEM.");
  }
  const result = await response.json();
  if (!response.ok) throw Error(result.error || "Opération refusée.");
  return result;
}

const domains = {
  members:"Comptes", roles:"Permissions", academic:"Structure scolaire",
  admissions:"Admissions", students:"Élèves", staff:"Personnel",
  organization:"Organigramme", curriculum:"Programmes", timetable:"Emplois du temps",
  assessments:"Notes", reports:"Bulletins", attendance:"Absences",
  deliberations:"Conseils", finance:"Finances", settings:"Paramètres",
};

export default function StaffOnboarding({schoolId}) {
  const [context,setContext] = useState(null);
  const [loading,setLoading] = useState(true);
  const [step,setStep] = useState(0);
  const [staff,setStaff] = useState(EMPTY_STAFF);
  const [appointments,setAppointments] = useState([]);
  const [classes,setClasses] = useState([]);
  const [createAccess,setCreateAccess] = useState(false);
  const [account,setAccount] = useState(EMPTY_ACCOUNT);
  const [ack,setAck] = useState(false);
  const [limitAccess,setLimitAccess] = useState(true);
  const [chosenCycles,setChosenCycles] = useState([]);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [success,setSuccess] = useState(null);
  const base = "schools/"+schoolId+"/staff/onboard";

  useEffect(()=>{
    let active=true;
    setLoading(true);setError("");setContext(null);setSuccess(null);
    setStep(0);setStaff(EMPTY_STAFF);setAppointments([]);setClasses([]);
    setCreateAccess(false);setAccount(EMPTY_ACCOUNT);setAck(false);
    setLimitAccess(true);setChosenCycles([]);
    request(base).then(data=>{
      if (active) {
        setContext(data);
        setAccount(old=>({...old,role:""}));
      }
    }).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[schoolId]);

  const roles = context?.roles||[];
  const positions = context?.positions||[];
  const selectedRoles = useMemo(
    ()=>roles.filter(r=>r.code===account.role||account.additional_roles.includes(r.code)),
    [roles,account.role,account.additional_roles]
  );
  const granted = [...new Set(selectedRoles.flatMap(r=>r.permissions))].sort();
  const manyCycles = (context?.education_cycles?.length||0)>1;
  const academicCycles = context?.academic_cycles||[];
  const actorRestricted = context?.actor_access_cycle_ids!==null;
  const changeStaff = (field,value)=>setStaff(old=>({...old,[field]:value}));
  const changeAccount = (field,value)=>setAccount(old=>({...old,[field]:value}));
  const editAppointment = (index,field,value)=>setAppointments(old=>old.map((item,i)=>i===index?{
    ...item,[field]:value,...(field==="function_code"?{cycle_code:""}:{})
  }:item));
  const editClass = (index,field,value)=>setClasses(old=>old.map((item,i)=>i===index?{
    ...item,[field]:value,...(field==="year"?{classroom:""}:{})
  }:item));
  const chosenPosition = (item)=>positions.find(p=>p.code===item.function_code);
  const labelCycle = (code)=>({
    prescolaire:"Maternelle",primaire:"Primaire",college:"Collège",
    lycee_general:"Lycée général",lycee_technique:"Lycée technique"
  })[code]||code||"Ensemble de l'établissement";
  const readyStaff = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,49}$/.test(staff.staff_code)
    && Boolean(staff.first_name.trim()&&staff.last_name.trim()&&staff.position.trim());
  const readyAppointments = appointments.every(a=>{
    const p=chosenPosition(a);
    return p&& (p.scope==="school"||p.allowed_cycles?.includes(a.cycle_code))
      && (!a.starts_on||!a.ends_on||a.starts_on<=a.ends_on);
  });
  const readyClasses = classes.every(a=>a.year&&a.classroom&&/^[a-z][a-z0-9_-]{0,49}$/.test(a.duty)
    && context?.classes.some(c=>c.id===a.classroom&&c.year===a.year));
  const readyAccount = !createAccess||Boolean(context?.can_create_account
    && roles.some(r=>r.code===account.role)
    && account.username.trim()&&account.email.includes("@")
    && account.password.length>=12
    && ((!limitAccess&&!actorRestricted) || (limitAccess&&chosenCycles.length>0)));
  const ready = readyStaff&&readyAppointments&&readyClasses&&readyAccount
    && (!manyCycles||!createAccess||ack);

  async function submit(e){
    e.preventDefault();setError("");
    if(!ready||busy) return;
    setBusy(true);
    try {
      const payload = {
        staff:{...staff,staff_code:staff.staff_code.trim(),
          first_name:staff.first_name.trim(),last_name:staff.last_name.trim(),
          position:staff.position.trim()},
        account:createAccess?{
          username:account.username.trim(),email:account.email.trim(),
          password:account.password,role:account.role,additional_roles:account.additional_roles,
          access_cycle_ids:limitAccess?chosenCycles:null,
        }:null,
        appointments:appointments.map(a=>({
          function_code:a.function_code,
          cycle_code:chosenPosition(a)?.scope==="school"?"":a.cycle_code,
          starts_on:a.starts_on||null,ends_on:a.ends_on||null,
        })),
        class_assignments:classes,
        ack_school_wide_permissions:Boolean(ack),
      };
      const result = await request(base,payload);
      setSuccess(result);
      setAccount(old=>({...old,password:""}));
      setStep(4);
    } catch(e) {setError(e.message);}
    finally {setBusy(false);}
  }

  const reset = ()=>{
    setStaff(EMPTY_STAFF);setAppointments([]);setClasses([]);
    setCreateAccess(false);setAccount(EMPTY_ACCOUNT);
    setAck(false);setLimitAccess(true);setChosenCycles([]);setSuccess(null);setError("");setStep(0);
  };

  if(loading) return <section className="card" aria-label="Ajouter un collaborateur"><h2>Ajouter un collaborateur</h2><p>Chargement des autorisations…</p></section>;
  if(!context) return <section className="card"><h2>Ajouter un collaborateur</h2><p role="alert">{error||"Accès indisponible."}</p></section>;
  return <section className="card" aria-label="Ajouter un collaborateur">
    <h2>Ajouter un collaborateur</h2>
    <p className="hint">Un seul parcours pour enregistrer une personne, ses fonctions, ses classes et, si nécessaire, son compte YEM dans <strong>{context.school_name}</strong>.</p>
    <p className="hint">Les opérations sont enregistrées ensemble : si une validation échoue, aucun compte, poste ou fiche n'est créé.</p>
    <div className="yd-onboarding-steps" aria-label="Étapes de création" style={{display:"flex",flexWrap:"wrap",gap:8,margin:"1rem 0"}}>
      {["Identité","Fonctions","Accès YEM","Vérification"].map((label,i)=><span key={label} style={{
        padding:"0.4rem 0.7rem",borderRadius:18,fontSize:"0.85rem",
        border:"1px solid #cadad3",background:step===i?"#d9f0e4":"transparent",
        fontWeight:step===i?700:400
      }}>{i+1}. {label}</span>)}
    </div>
    {step===4&&success?<div role="status" style={{padding:"1rem",border:"1px solid #b7ddc4",borderRadius:12}}>
      <h3>Collaborateur créé</h3>
      <p><strong>{staff.first_name} {staff.last_name}</strong> · Matricule {success.staff.staff_code}</p>
      <p>{success.appointments_count} fonction(s) officielle(s) et {success.assignments_count} affectation(s) de classe enregistrée(s).</p>
      <p>{success.account_created?<>Compte YEM activé : <strong>{success.username}</strong>. Invitez cette personne à changer son mot de passe initial et à sécuriser son compte.</>:"Aucun accès YEM créé : la fiche du personnel existe sans compte."}</p>
      <button type="button" onClick={reset}>Ajouter un autre collaborateur</button>
    </div>:<form onSubmit={submit}>
      {step===0&&<div>
        <h3>1. Qui est cette personne ?</h3>
        <div className="two">
          <label className="field">Matricule (unique dans l'école)
            <input required maxLength={50} pattern="[a-zA-Z0-9][a-zA-Z0-9_-]{0,49}" value={staff.staff_code} onChange={e=>changeStaff("staff_code",e.target.value)} placeholder="EX-2026-001"/>
          </label>
          <label className="field">Prénom(s)
            <input required maxLength={120} value={staff.first_name} onChange={e=>changeStaff("first_name",e.target.value)}/>
          </label>
          <label className="field">Nom
            <input required maxLength={120} value={staff.last_name} onChange={e=>changeStaff("last_name",e.target.value)}/>
          </label>
          <label className="field">Poste / métier sur la fiche
            <input required maxLength={100} value={staff.position} onChange={e=>changeStaff("position",e.target.value)} placeholder="Ex. Directrice, instituteur, secrétaire"/>
          </label>
        </div>
        <p className="hint">La fiche professionnelle existe même si la personne ne se connecte pas à YEM.</p>
      </div>}
      {step===1&&<div>
        <h3>2. Quelles fonctions exerce-t-elle ?</h3>
        <p className="hint">Les fonctions sont facultatives : une personne peut exercer plusieurs responsabilités dans différents cycles. Une nomination ne donne pas automatiquement accès aux données.</p>
        {!context.can_appoint&&<p>Vous pouvez enregistrer la fiche mais les nominations officielles requièrent une autorisation supplémentaire.</p>}
        {appointments.map((item,index)=><fieldset key={index} style={{marginBottom:"0.9rem"}}>
          <legend>Fonction {index+1}</legend>
          <div className="two">
            <label className="field">Fonction
              <select value={item.function_code} required onChange={e=>editAppointment(index,"function_code",e.target.value)}>
                <option value="">Choisir…</option>
                {positions.map(p=><option key={p.code} value={p.code}>{p.label}</option>)}
              </select>
            </label>
            {chosenPosition(item)?.scope==="cycle"&&<label className="field">Cycle concerné
              <select value={item.cycle_code} required onChange={e=>editAppointment(index,"cycle_code",e.target.value)}>
                <option value="">Choisir un cycle…</option>
                {chosenPosition(item).allowed_cycles.map(c=><option key={c} value={c}>{labelCycle(c)}</option>)}
              </select>
            </label>}
            <label className="field">Début (facultatif)
              <input type="date" value={item.starts_on} onChange={e=>editAppointment(index,"starts_on",e.target.value)}/>
            </label>
            <label className="field">Fin (facultatif)
              <input type="date" min={item.starts_on||undefined} value={item.ends_on} onChange={e=>editAppointment(index,"ends_on",e.target.value)}/>
            </label>
          </div>
          <button type="button" onClick={()=>setAppointments(old=>old.filter((_,i)=>i!==index))}>Retirer cette fonction</button>
        </fieldset>)}
        {context.can_appoint&&<button type="button" onClick={()=>setAppointments(old=>[...old,{...EMPTY_APPOINTMENT}])} disabled={appointments.length>=20}>Ajouter une fonction</button>}
        <h3 style={{marginTop:"1.5rem"}}>Affectations à des classes (facultatif)</h3>
        <p className="hint">L'affectation relie une personne, une année scolaire et une classe. Répétez pour les autres classes.</p>
        {classes.map((item,index)=><fieldset key={index}>
          <legend>Affectation {index+1}</legend>
          <div className="two">
            <label className="field">Année scolaire
              <select value={item.year} required onChange={e=>editClass(index,"year",e.target.value)}>
                <option value="">Choisir…</option>
                {context.years.map(y=><option key={y.id} value={y.id}>{y.name}</option>)}
              </select>
            </label>
            <label className="field">Classe
              <select value={item.classroom} required onChange={e=>editClass(index,"classroom",e.target.value)}>
                <option value="">Choisir…</option>
                {context.classes.filter(c=>c.year===item.year).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="field">Responsabilité (code)
              <input value={item.duty} pattern="[a-z][a-z0-9_-]*" maxLength={50} required onChange={e=>editClass(index,"duty",e.target.value)}/>
            </label>
          </div>
          <button type="button" onClick={()=>setClasses(old=>old.filter((_,i)=>i!==index))}>Retirer l'affectation</button>
        </fieldset>)}
        <button type="button" disabled={!context.years.length||!context.classes.length||classes.length>=30} onClick={()=>setClasses(old=>[...old,{...EMPTY_CLASS}])}>Ajouter une classe</button>
      </div>}
      {step===2&&<div>
        <h3>3. Cette personne doit-elle utiliser YEM ?</h3>
        <label style={{display:"flex",gap:8,alignItems:"center",marginBottom:12}}>
          <input type="checkbox" checked={createAccess} disabled={!context.can_create_account} onChange={e=>{setCreateAccess(e.target.checked);setAck(false);}}/>
          <span>Créer un compte de connexion pour cette école</span>
        </label>
        {!context.can_create_account&&<p className="hint">Vous pouvez créer le personnel sans compte. Pour créer un accès, demandez la permission de gestion des comptes au propriétaire.</p>}
        {createAccess&&<div>
          <div className="two">
            <label className="field">Identifiant de connexion
              <input required maxLength={150} value={account.username} onChange={e=>changeAccount("username",e.target.value)} autoComplete="off"/>
            </label>
            <label className="field">Email professionnel ou personnel
              <input required type="email" maxLength={254} value={account.email} onChange={e=>changeAccount("email",e.target.value)}/>
            </label>
            <label className="field">Mot de passe initial
              <input required type="password" minLength={12} value={account.password} onChange={e=>changeAccount("password",e.target.value)} autoComplete="new-password"/>
            </label>
            <label className="field">Rôle applicatif principal
              <select required value={account.role} onChange={e=>setAccount(old=>({...old,role:e.target.value,additional_roles:old.additional_roles.filter(r=>r!==e.target.value)}))}>
                <option value="">Choisir un rôle…</option>
                {roles.map(r=><option key={r.code} value={r.code}>{r.label}</option>)}
              </select>
            </label>
          </div>
          <fieldset><legend>Périmètre des autorisations</legend>
            <p className="hint">Sélectionnez les cycles académiques réels que ce compte pourra consulter et administrer. Les anciennes API non compatibles avec cette restriction seront bloquées.</p>
            {!actorRestricted&&<label style={{display:"flex",gap:8}}><input type="radio" name="staff-cycle-scope" checked={!limitAccess} onChange={()=>{setLimitAccess(false);setChosenCycles([]);}}/><span>Accès à tout l’établissement (réservé aux comptes de confiance)</span></label>}
            <label style={{display:"flex",gap:8}}><input type="radio" name="staff-cycle-scope" checked={limitAccess} onChange={()=>setLimitAccess(true)}/><span>Limiter aux cycles sélectionnés</span></label>
            {limitAccess&&academicCycles.map(c=><label key={c.id} style={{display:"flex",gap:8,alignItems:"center",marginLeft:16}}>
              <input type="checkbox" checked={chosenCycles.includes(c.id)} onChange={e=>setChosenCycles(old=>e.target.checked?[...old,c.id]:old.filter(x=>x!==c.id))}/><span>{c.name}</span>
            </label>)}
            {limitAccess&&!academicCycles.length&&<p className="hint">Aucun cycle académique disponible. Un responsable doit d’abord configurer les cycles scolaires.</p>}
          </fieldset>
          <fieldset><legend>Rôles applicatifs supplémentaires (facultatif)</legend>
            {roles.filter(r=>r.code!==account.role).map(r=><label key={r.code} style={{display:"flex",gap:8,alignItems:"center"}}>
              <input type="checkbox" checked={account.additional_roles.includes(r.code)} onChange={e=>setAccount(old=>({...old,additional_roles:e.target.checked?[...old.additional_roles,r.code]:old.additional_roles.filter(c=>c!==r.code)}))}/>
              <span>{r.label}</span>
            </label>)}
          </fieldset>
          <details>
            <summary>Voir les autorisations accordées ({granted.length})</summary>
            <ul>{granted.map(p=><li key={p}>{domains[p.split(".")[1]]||p.split(".")[1]} — {p.split(".").slice(2).join(".")||"Accès"}</li>)}</ul>
          </details>
        </div>}
      </div>}
      {step===3&&<div>
        <h3>4. Vérifier avant d'enregistrer</h3>
        <p><strong>{staff.first_name} {staff.last_name}</strong> — matricule {staff.staff_code} — {staff.position}</p>
        <p><strong>Nominations :</strong> {appointments.length?appointments.map((a,i)=><span key={i}>{i?", ":""}{chosenPosition(a)?.label} ({labelCycle(a.cycle_code)})</span>):"Aucune"}</p>
        <p><strong>Classes :</strong> {classes.length||"Aucune"}</p>
        <p><strong>Compte YEM :</strong> {createAccess?account.username+" · "+selectedRoles.map(r=>r.label).join(", "):"Aucun"}</p>
        {createAccess&&<p><strong>Cycles autorisés :</strong> {limitAccess?academicCycles.filter(c=>chosenCycles.includes(c.id)).map(c=>c.name).join(", "):"Ensemble de l’établissement"}</p>}
        {createAccess&&<p className="hint" role="note">Les comptes limités sont contrôlés par le serveur : les modules qui ne filtrent pas encore leurs données par cycle sont refusés. Un accès global ne doit être attribué qu'aux comptes de confiance.</p>}
        {createAccess&&manyCycles&&<label style={{display:"flex",alignItems:"flex-start",gap:8}}>
          <input type="checkbox" required checked={ack} onChange={e=>setAck(e.target.checked)}/>
          <span>Je confirme avoir vérifié les cycles sélectionnés et les permissions du compte. Certains modules restent indisponibles aux comptes limités en attendant leur adaptation.</span>
        </label>}
        <p className="hint">Aucun poste fictif ni compte supplémentaire ne sera créé. Les changements sont audités.</p>
      </div>}
      {error&&<p role="alert" style={{color:"#a12e2e",marginTop:12}}>{error}</p>}
      <div style={{display:"flex",justifyContent:"space-between",gap:8,flexWrap:"wrap",marginTop:"1.5rem"}}>
        <button type="button" disabled={busy||step===0} onClick={()=>{setError("");setStep(s=>Math.max(0,s-1));}}>Précédent</button>
        {step<3?<button type="button" className="pc-primary" disabled={busy||(step===0&&!readyStaff)||(step===1&&(!readyAppointments||!readyClasses))||(step===2&&!readyAccount)} onClick={()=>{setError("");setStep(s=>s+1);}}>Continuer</button>:
          <button type="submit" className="pc-primary" disabled={busy||!ready}>{busy?"Enregistrement…":"Créer le collaborateur"}</button>}
      </div>
    </form>}
    {context.can_manage_cycle_access&&<CycleScopeManager schoolId={schoolId}
      cycles={academicCycles} accounts={context.existing_accounts||[]}
      onSaved={async()=>setContext(await request(base))}/>} 
  </section>;
}
