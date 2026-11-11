import React, {useEffect,useState} from "react";
import {PageHeader,Card,Metric,Table,Status,Button} from "./yem-ui.jsx";

const number = value => new Intl.NumberFormat("fr-FR").format(Number(value||0));
const amount = (value,currency) => `${number(value)} ${currency}`;
const SECTIONS = [
  ["synthese","Vue d’ensemble"],["scolarite","Scolarité"],
  ["finances","Finances"],["admissions","Admissions"],
  ["personnel","Personnel"],["activite","Activité"],
];

export default function OwnerDashboard({schoolId,schoolName="",onNavigate}) {
  const [year,setYear]=useState("");
  const [tab,setTab]=useState("synthese");
  const [data,setData]=useState(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  useEffect(()=>{setYear("");setTab("synthese");},[schoolId]);
  useEffect(()=>{
    if(!schoolId)return;
    let active=true;
    setLoading(true);setError("");setData(null);
    const params=year?`?year=${encodeURIComponent(year)}`:"";
    fetch(`/api/v1/schools/${schoolId}/owner/overview${params}`,{
      credentials:"same-origin",
    }).then(async response=>{
      const body=await response.json();
      if(!response.ok)throw Error(body.error||"Accès au pilotage indisponible.");
      if(active)setData(body);
    }).catch(err=>{if(active)setError(err.message);})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[schoolId,year]);

  const title="Pilotage du propriétaire";
  const metrics=data?.schooling||{};
  const staff=data?.staff||{};
  const admission=data?.admissions||{};
  const finance=data?.finance?.currencies||[];
  const activity=data?.activity||{};
  const financialTable=finance.length
    ? <Table headers={["Devise","Facturé","Encaissé","Restant dû","Échu","Encaissé ce mois"]}
      rows={finance.map(row=>[
        row.currency,amount(row.billed,row.currency),amount(row.paid,row.currency),
        amount(row.outstanding,row.currency),amount(row.overdue,row.currency),
        amount(row.paid_this_month,row.currency),
      ])}/>
    : <p className="hint">Aucun frais enregistré pour cette année scolaire.</p>;

  return <>
    <PageHeader title={title} subtitle={`Indicateurs de ${schoolName||data?.school?.name||"l’établissement"} — consultation sans pouvoir d’encaissement`}/>
    <div className="yd-real-body">
      {loading&&<p role="status">Chargement des indicateurs de l’établissement…</p>}
      {error&&<Card title="Pilotage indisponible" icon="alert">
        <p role="alert">{error}</p>
        <p className="hint">Cette vue est réservée au propriétaire autorisé de l’établissement.</p>
      </Card>}
      {data&&!loading&&<>
        <div className="actions" style={{alignItems:"center",justifyContent:"space-between",flexWrap:"wrap"}}>
          <label className="field" style={{maxWidth:310}}>Année scolaire
            <select aria-label="Année scolaire du pilotage" value={data.year?.id||""}
              onChange={event=>setYear(event.target.value)}>
              {!data.year&&<option value="">Aucune année scolaire</option>}
              {(data.years||[]).map(item=><option key={item.id} value={item.id}>{item.name}{item.status==="current"?" · en cours":item.status==="closed"?" · clôturée":""}</option>)}
            </select>
          </label>
          <Status tone="green">Lecture seule — chiffres consolidés</Status>
        </div>
        <div role="tablist" aria-label="Rubriques du pilotage" className="yd-real-tabs" style={{display:"flex",flexWrap:"wrap",gap:8}}>
          {SECTIONS.map(([key,label])=><button key={key} type="button" role="tab"
            aria-selected={tab===key} className={tab===key?"active":""}
            onClick={()=>setTab(key)}>{label}</button>)}
        </div>
        {(tab==="synthese"||tab==="scolarite")&&<>
          <div className="yd-metrics five">
            <Metric icon="users" label="Élèves inscrits" value={number(metrics.active_students)} trend="none" trendLabel={data.year?.name||"Aucune année active"}/>
            <Metric icon="school" label="Classes ouvertes" value={number(metrics.active_classes)} trend="none" trendLabel="Année sélectionnée"/>
            <Metric icon="idcard" label="Personnel actif" value={number(staff.active)} trend="none" trendLabel="Établissement"/>
            <Metric icon="adduser" label="Demandes à traiter" value={number(admission.pending)} trend="none" trendLabel="Admissions en attente"/>
            <Metric icon="file" label="Bulletins publiés" value={number(metrics.published_reports)} trend="none" trendLabel="Année sélectionnée"/>
          </div>
          <Card title="Effectifs par cycle" icon="school"
            subtitle="Répartition sans accès nominatif aux dossiers des élèves">
            {metrics.enrollment_by_cycle?.length
              ? <Table headers={["Cycle","Classes actives","Élèves inscrits"]}
                  rows={metrics.enrollment_by_cycle.map(item=>[item.cycle,number(item.classes),number(item.students)])}/>
              : <p className="hint">Aucun cycle avec classes ouvertes et inscriptions pour l'année choisie.</p>}
            <p className="hint">Capacité renseignée pour {number(metrics.capacities_defined)} classe(s) :
              {" "}{number(metrics.total_defined_places)} places. Les classes sans capacité définie ne sont pas incluses dans ce total.</p>
          </Card>
        </>}
        {(tab==="synthese"||tab==="finances")&&<Card title="Situation financière de l’établissement" icon="coins"
          subtitle="Total des frais et règlements enregistrés ; aucune caisse ni modification depuis cet espace">
          {financialTable}
          <p className="hint">{data.finance?.note}</p>
          {tab==="finances"&&data.finance?.monthly?.length>0&&<>
            <h3>Encaissements par mois</h3>
            <Table headers={["Mois","Devise","Montant"]}
              rows={data.finance.monthly.map(item=>[item.month,item.currency,amount(item.total,item.currency)])}/>
          </>}
        </Card>}
        {(tab==="synthese"||tab==="admissions")&&<Card title="Admissions et demandes" icon="adduser">
          <div className="yd-metrics">
            <Metric icon="file" label="Demandes reçues" value={number(admission.total)} trend="none"/>
            <Metric icon="hourglass" label="En attente" value={number(admission.pending)} trend="none"/>
            <Metric icon="check" label="Admises" value={number(admission.accepted)} trend="none"/>
            <Metric icon="users" label="Inscrites" value={number(admission.enrolled)} trend="none"/>
            <Metric icon="alert" label="Refusées" value={number(admission.rejected)} trend="none"/>
          </div>
          <p className="hint">La direction garde la responsabilité d'instruire et de décider les admissions.</p>
        </Card>}
        {(tab==="synthese"||tab==="personnel")&&<Card title="Équipe et organisation" icon="idcard">
          <div className="yd-metrics">
            <Metric icon="users" label="Collaborateurs actifs" value={number(staff.active)} trend="none"/>
            <Metric icon="check" label="Comptes YEM liés" value={number(staff.with_account)} trend="none"/>
            <Metric icon="school" label="Affectés aux classes" value={number(staff.assigned_to_classes)} trend="none"/>
            <Metric icon="layers" label="Nominations actives" value={number(staff.active_appointments)} trend="none"/>
          </div>
          <p className="hint">{number(staff.without_account)} personne(s) sans compte YEM. Un compte n'est pas obligatoire pour être enregistré comme personnel.</p>
        </Card>}
        {tab==="scolarite"&&<Card title="Activité pédagogique" icon="cap">
          <div className="yd-metrics">
            <Metric icon="file" label="Évaluations créées" value={number(metrics.assessments)} trend="none"/>
            <Metric icon="check" label="Évaluations publiées" value={number(metrics.published_assessments)} trend="none"/>
            <Metric icon="file" label="Bulletins publiés" value={number(metrics.published_reports)} trend="none"/>
            <Metric icon="calendar" label="Absences relevées" value={number(metrics.absence_marks)} trend="none"/>
            <Metric icon="alarm-clock" label="Retards relevés" value={number(metrics.late_marks)} trend="none"/>
          </div>
          <p className="hint">Ces chiffres mesurent l'activité enregistrée, pas les résultats individuels des élèves.</p>
        </Card>}
        {(tab==="synthese"||tab==="activite")&&<Card title="Activité récente de l’établissement" icon="calendar"
          subtitle="30 derniers jours — volumes d'opérations, sans noms, identifiants ni contenus des dossiers">
          <p><strong>{number(activity.total_30d)} opération(s) tracée(s)</strong></p>
          {activity.by_type?.length
            ? <Table headers={["Catégorie","Nombre"]}
                rows={activity.by_type.map(item=>[item.label,number(item.total)])}/>
            : <p className="hint">Aucune opération tracée au cours des trente derniers jours.</p>}
          {tab==="activite"&&activity.days?.length>0&&<>
            <h3>Évolution journalière</h3>
            <Table headers={["Date","Opérations"]}
              rows={activity.days.map(row=>[row.date,number(row.total)])}/>
          </>}
        </Card>}
        <Card title="Suivi et responsabilités" icon="shield">
          <p className="hint">Cet espace est réservé au pilotage et à la supervision. Le propriétaire peut observer les indicateurs sans disposer des droits d'encaisser, de modifier les notes, d'admettre des élèves ou de consulter les renseignements privés des familles.</p>
          {onNavigate&&<div className="actions">
            <Button onClick={()=>onNavigate("settings","roles")}>Gérer les comptes et les droits</Button>
          </div>}
          <p className="hint">Données arrêtées au {data.as_of}. Les chiffres affichés sont ceux de l'établissement et de l'année sélectionnés.</p>
        </Card>
      </>}
    </div>
  </>;
}
