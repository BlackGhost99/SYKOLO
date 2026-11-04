import React, {useEffect, useMemo, useRef, useState} from "react";
import "./parent-discovery.css";

async function api(path, body) {
  if (body !== undefined) await fetch("/api/v1/auth/csrf", {credentials:"same-origin"});
  const csrf=document.cookie.split("; ").find(x=>x.startsWith("csrftoken="))?.split("=")[1]||"";
  const response=await fetch("/api/v1/"+path, {
    method:body===undefined?"GET":"POST", credentials:"same-origin",
    headers:body===undefined?{}:{"Content-Type":"application/json","X-CSRFToken":csrf},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw Error("Le service YEM est momentanément indisponible.");
  const data=await response.json();
  if (!response.ok) throw Error(data.error||"Opération refusée.");
  return data;
}
const ROUTES={direct:"Inscription ou préinscription",concours:"Concours / test",orientation:"Affectation / orientation"};
const STATES={submitted:"Dossier déposé",review:"En cours d'étude",accepted:"Admission accordée",rejected:"Demande refusée",enrolled:"Inscription confirmée"};

export default function ParentDiscovery() {
  const [schools,setSchools]=useState([]);
  const [family,setFamily]=useState([]);
  const [applications,setApplications]=useState([]);
  const [notifications,setNotifications]=useState([]);
  const lastNotification=useRef(null);
  const [search,setSearch]=useState("");
  const [chosenSchool,setChosenSchool]=useState("");
  const [child,setChild]=useState("");
  const [classroom,setClassroom]=useState("");
  const [route,setRoute]=useState("direct");
  const [relation,setRelation]=useState("Parent");
  const [phone,setPhone]=useState("");
  const [origin,setOrigin]=useState("");
  const [reference,setReference]=useState("");
  const [paymentChoice,setPaymentChoice]=useState("cash");
  const [paymentOperator,setPaymentOperator]=useState("airtel");
  const [paymentPhone,setPaymentPhone]=useState("");
  const [activePay,setActivePay]=useState("");
  const [newChild,setNewChild]=useState({first_name:"",last_name:"",date_of_birth:""});
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [view,setView]=useState("schools");

  async function refresh() {
    const [list,children,requests,alerts]=await Promise.all([
      api("parents/catalog"),api("parents/family-children"),api("parents/applications"),api("parents/notifications"),
    ]);
    setSchools(list.schools||[]);
    setFamily(children.children||[]);
    setApplications(requests.applications||[]);
    setNotifications(alerts.notifications||[]);
  }
  useEffect(()=>{
    let live=true;
    Promise.all([api("parents/catalog"),api("parents/family-children"),api("parents/applications"),api("parents/notifications")])
      .then(([list,children,requests,alerts])=>{
        if(!live)return;
        setSchools(list.schools||[]);
        setFamily(children.children||[]);
        setApplications(requests.applications||[]);
        setNotifications(alerts.notifications||[]);
      }).catch(e=>{if(live)setError(e.message)});
    return()=>{live=false};
  },[]);
  useEffect(()=>{
    const latest=notifications[0];
    if(!latest)return;
    if(lastNotification.current&&latest.id!==lastNotification.current
      &&typeof window!=="undefined"&&"Notification" in window
      &&window.Notification.permission==="granted"){
      new window.Notification("YEM · "+latest.school,{body:latest.message});
    }
    lastNotification.current=latest.id;
  },[notifications]);
  const selectedSchool=schools.find(s=>s.id===chosenSchool);
  const selectedClass=selectedSchool?.classes.find(c=>c.id===classroom);
  const visible=useMemo(()=>schools.filter(s=>
    [s.name,s.city,s.district,s.school_type_label].join(" ").toLowerCase().includes(search.toLowerCase())
  ),[schools,search]);
  async function run(fn) {
    setBusy(true);setError("");setMessage("");
    try {await fn();await refresh();}
    catch(e){setError(e.message);}
    finally{setBusy(false);}
  }
  return <section className="yp-app" aria-label="Rechercher une école et inscrire un enfant">
    <header className="yp-head">
      <div><span className="yp-eyebrow">YEM · Familles</span><h2>Votre parcours scolaire, au même endroit.</h2>
        <p>Découvrez une école, déposez un dossier et suivez chaque étape sans déplacement inutile.</p></div>
      <div className="yp-stat">{family.length}<small>profils enfant</small></div>
    </header>
    <nav className="yp-tabs" aria-label="Espace familles">
      {[["schools","Établissements"],["children","Mes enfants"],["requests","Mes demandes"],["notifications","Actualités"]].map(([key,label])=>
        <button type="button" key={key} aria-current={view===key?"page":undefined}
          onClick={()=>{setView(key);setMessage("");setError("");}}>{label}</button>)}
    </nav>
    {error&&<p className="yp-error" role="alert">{error}</p>}
    {message&&<p className="yp-success" role="status">{message}</p>}
    {view==="schools"&&<>
      <label className="yp-field">Rechercher une école
        <input type="search" placeholder="Nom, ville ou quartier..." value={search} onChange={e=>setSearch(e.target.value)}/>
      </label>
      <div className="yp-schools">
        {visible.length===0&&<p>Aucun établissement n'a encore publié de places dans ce catalogue.</p>}
        {visible.map(s=><article key={s.id} className={"yp-school"+(s.id===chosenSchool?" active":"")}>
          <div className="yp-school-title"><div className="yp-emblem">Y</div><div>
            <h3>{s.name}</h3><small>{s.school_type_label} · {[s.city,s.district].filter(Boolean).join(" · ")||"Localisation à compléter"}</small>
          </div></div>
          {s.description&&<p>{s.description}</p>}
          <p className="yp-muted">{s.classes.length} classe(s) ouvertes à la consultation
            {s.phone?" · Contact : "+s.phone:""}</p>
          <button type="button" className="yp-button" onClick={()=>{
            setChosenSchool(s.id);setClassroom("");setRoute("direct");setPaymentChoice("cash");
          }}>{chosenSchool===s.id?"Établissement sélectionné":"Voir les classes et candidater"}</button>
          {chosenSchool===s.id&&<div className="yp-apply">
            <h4>Demander une inscription</h4>
            <p>Une candidature n'est ni une inscription définitive, ni une réservation de place.</p>
            <form onSubmit={e=>{e.preventDefault();run(async()=>{
              await api("parents/applications",{
                child,classroom,route,payment_choice:paymentChoice,
                guardian_relationship:relation,guardian_phone:phone,
                origin_school:origin,route_reference:reference,
              });
              setClassroom("");setView("requests");
              setMessage("Demande déposée. L'école examinera votre dossier.");
            });}}>
              <label className="yp-field">Enfant
                <select required value={child} onChange={e=>setChild(e.target.value)}>
                  <option value="">Choisir un enfant</option>
                  {family.map(c=><option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>)}
                </select>
              </label>
              {family.length===0&&<p>Commencez par créer le profil de votre enfant dans « Mes enfants ».</p>}
              <label className="yp-field">Classe souhaitée
                <select required value={classroom} onChange={e=>{const id=e.target.value;setClassroom(id);const c=s.classes.find(c=>c.id===id);setRoute(c?.routes[0]||"direct");setPaymentChoice(s.cash_at_school?"cash":c?.online_payment_available?"online":"cash");}}>
                  <option value="">Sélectionner une classe</option>
                  {s.classes.map(c=><option key={c.id} value={c.id} disabled={c.remaining===0}>
                    {c.name} · {c.year} · {c.remaining===null?"Places à confirmer":c.remaining+" place(s) restante(s)"}
                  </option>)}
                </select>
              </label>
              <label className="yp-field">Type de demande
                <select value={route} onChange={e=>setRoute(e.target.value)}>
                  {(selectedClass?.routes||["direct"]).map(value=><option key={value} value={value}>{ROUTES[value]||value}</option>)}
                </select>
              </label>
              <div className="yp-two">
                <label className="yp-field">Votre lien avec l'enfant
                  <input required maxLength={80} value={relation} onChange={e=>setRelation(e.target.value)}/>
                </label>
                <label className="yp-field">Votre téléphone
                  <input required type="tel" maxLength={45} value={phone} onChange={e=>setPhone(e.target.value)} placeholder="+241..."/>
                </label>
              </div>
              {route!=="direct"&&<>
                <label className="yp-field">Établissement précédent (facultatif)
                  <input maxLength={180} value={origin} onChange={e=>setOrigin(e.target.value)}/>
                </label>
                <label className="yp-field">Référence du concours ou de l'affectation (si connue)
                  <input maxLength={140} value={reference} onChange={e=>setReference(e.target.value)}/>
                </label>
              </>}
              <fieldset className="yp-payment">
                <legend>Comment souhaitez-vous payer les frais ?</legend>
                <label><input type="radio" name="yp-payment" checked={paymentChoice==="cash"}
                  onChange={()=>setPaymentChoice("cash")} disabled={!s.cash_at_school}/> Payer en espèces à l'école</label>
                <label className={!selectedClass?.online_payment_available?"yp-disabled":""}>
                  <input type="radio" name="yp-payment" checked={paymentChoice==="online"}
                    onChange={()=>setPaymentChoice("online")} disabled={!selectedClass?.online_payment_available}/>
                  Payer en ligne (Airtel Money / Moov Money)
                </label>
                <small>{selectedClass?.fee_amount_xaf?
                  "Frais de dossier : "+Number(selectedClass.fee_amount_xaf).toLocaleString("fr-FR")+" FCFA.":
                  "Montant des frais à confirmer auprès de l'établissement."}</small>
                <small>Aucun paiement n'est confirmé tant que le prestataire n'a pas vérifié la transaction.</small>
              </fieldset>
              <button className="yp-button yp-primary" type="submit"
                disabled={busy||!family.length||!classroom||(paymentChoice==="cash"&&!s.cash_at_school)||(paymentChoice==="online"&&!selectedClass?.online_payment_available)}>
                {busy?"Enregistrement...":"Déposer ma demande"}
              </button>
              {!s.cash_at_school&&<p>Le paiement en espèces n'est pas proposé par cette école.</p>}
            </form>
          </div>}
        </article>)}
      </div>
    </>}
    {view==="children"&&<div className="yp-pane">
      <h3>Profils de mes enfants</h3>
      <p>Les profils de préparation restent privés. Ils ne remplacent pas le dossier officiel créé par l'école.</p>
      {family.map(c=><div className="yp-child" key={c.id}><b>{c.first_name} {c.last_name}</b>
        <small>{c.date_of_birth?"Né(e) le "+c.date_of_birth:"Date de naissance non renseignée"}</small></div>)}
      <form onSubmit={e=>{e.preventDefault();run(async()=>{
        await api("parents/family-children",newChild);
        setNewChild({first_name:"",last_name:"",date_of_birth:""});
        setMessage("Profil de l'enfant ajouté.");
      });}}>
        <h4>Ajouter un enfant</h4>
        <div className="yp-two">
          <label className="yp-field">Prénom<input required maxLength={120} value={newChild.first_name}
            onChange={e=>setNewChild(v=>({...v,first_name:e.target.value}))}/></label>
          <label className="yp-field">Nom<input required maxLength={120} value={newChild.last_name}
            onChange={e=>setNewChild(v=>({...v,last_name:e.target.value}))}/></label>
        </div>
        <label className="yp-field">Date de naissance (facultatif)
          <input type="date" value={newChild.date_of_birth}
            onChange={e=>setNewChild(v=>({...v,date_of_birth:e.target.value}))}/></label>
        <button className="yp-button yp-primary" disabled={busy}>Enregistrer l'enfant</button>
      </form>
    </div>}
    {view==="requests"&&<div className="yp-pane">
      <h3>Mes candidatures</h3>
      <p>L'établissement reste responsable de la décision d'admission et de l'inscription officielle.</p>
      {applications.length===0&&<p>Aucune candidature enregistrée.</p>}
      {applications.map(a=><article key={a.id} className="yp-request">
        <b>{a.school_name}</b><p>{a.classroom_name} · {a.year} · {ROUTES[a.route]||a.route}</p>
        <strong>{STATES[a.status]||a.status}</strong>
        <small>Paiement choisi : espèces à la caisse · non confirmé en ligne</small>
      </article>)}
    </div>}
  </section>;
}

export function SchoolCatalogSettings({schoolId}) {
  const [settings,setSettings]=useState(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  useEffect(()=>{let alive=true;api("schools/"+schoolId+"/parent-listing").then(x=>{if(alive)setSettings(x)})
    .catch(e=>{if(alive)setMessage(e.message)});return()=>{alive=false};},[schoolId]);
  if(!settings)return <p role="status">{message||"Chargement du catalogue parent…"}</p>;
  const update=(key,value)=>setSettings(old=>({...old,[key]:value}));
  return <div className="yp-settings">
    <h3>Publication dans YEM Parents</h3>
    <p>L'établissement choisit librement d'apparaître dans le catalogue des familles.</p>
    <form onSubmit={async e=>{e.preventDefault();setBusy(true);setMessage("");
      try{const result=await api("schools/"+schoolId+"/parent-listing",settings);
        setSettings(x=>({...x,revision:result.revision}));setMessage("Fiche publique enregistrée.");
      }catch(err){setMessage(err.message)}finally{setBusy(false);}
    }}>
      <label className="yp-toggle"><input type="checkbox" checked={settings.published}
        onChange={e=>update("published",e.target.checked)}/> Publier cet établissement</label>
      <div className="yp-two">
        {[["city","Ville",100],["district","Quartier",100],["contact_phone","Téléphone public",45]].map(([key,label,max])=>
          <label key={key} className="yp-field">{label}<input maxLength={max} value={settings[key]}
            onChange={e=>update(key,e.target.value)}/></label>)}
      </div>
      <label className="yp-field">Présentation (600 caractères)
        <textarea maxLength={600} rows={3} value={settings.description}
          onChange={e=>update("description",e.target.value)}/></label>
      <label className="yp-toggle"><input type="checkbox" checked={settings.cash_at_school}
        onChange={e=>update("cash_at_school",e.target.checked)}/> Accepter les demandes avec paiement en espèces sur place</label>
      <button type="submit" className="yp-button yp-primary" disabled={busy}>Enregistrer la fiche publique</button>
      {message&&<p role="status">{message}</p>}
    </form>
  </div>;
}
