import React from "react";
import "./school-commercial-status.css";

const labels={free:"Mode gratuit",trial:"Essai gratuit",active:"Abonnement actif",scheduled:"Abonnement programmé",due_today:"Échéance aujourd’hui",overdue:"Abonnement en retard",expired:"Abonnement expiré",read_only:"Mode lecture seule",review:"Abonnement à vérifier"};
const formatDate=value=>typeof value==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(value)?value.split("-").reverse().join("/"):null;

export default function SchoolCommercialStatus({status,restricted=false,canManage=false,onManage,onRegularize}){
  if(!status&&!restricted)return null;
  const mode=restricted?"read_only":status?.mode;
  if(!labels[mode])return null;
  const due=formatDate(status?.next_payment_due),end=formatDate(status?.service_ends_before),overdue=formatDate(status?.oldest_overdue_on),expired=formatDate(status?.last_service_ended_on),trialEnd=formatDate(status?.trial_ends_before);
  const days=status?.grace_days_remaining;
  const grace=typeof days==="number"&&days>=0?(days===0?"Délai de grâce écoulé":days+" jour"+(days===1?"":"s")+" de grâce restant"+(days===1?"":"s")):null;
  let details=[];
  if(mode==="free")details=["Facturation non activée","Aucune échéance"];
  else if(mode==="trial")details=["Aucun règlement exigible",trialEnd&&"Fin de l’essai le "+trialEnd];
  else if(mode==="read_only")details=["Modifications bloquées","Abonnement à régulariser",overdue&&"Impayé depuis le "+overdue];
  else if(mode==="overdue")details=[overdue&&"Impayé depuis le "+overdue,grace,end&&"Renouvellement le "+end];
  else if(mode==="expired")details=[expired&&"Fin du service le "+expired,grace,"Renouvellement nécessaire"];
  else if(mode==="review")details=["Échéancier à vérifier auprès de BWETEK"];
  else details=[due?(mode==="due_today"?"À régler le ":"Prochaine échéance : ")+due:"Aucune échéance impayée",end&&"Renouvellement le "+end];
  const attention=["read_only","overdue","due_today","expired","review"].includes(mode);
  return <aside className={"yd-commercial-status yd-commercial-status--"+mode} aria-label="Statut de l’abonnement YEM">
    <div className="yd-commercial-status-main" role="status">
      <span className="yd-commercial-status-marker" aria-hidden="true"/>
      <div className="yd-commercial-status-text"><strong>YEM · {labels[mode]}</strong><span>{details.filter(Boolean).join(" · ")}</span></div>
    </div>
    {mode==="read_only"&&onRegularize?<button type="button" onClick={onRegularize}>{canManage?"Régulariser":"Contacter la direction"}</button>:canManage&&onManage?<button type="button" onClick={onManage}>{attention?"Voir l’abonnement":"Mon abonnement"} <span aria-hidden="true">›</span></button>:attention&&<small className="yd-commercial-status-contact">Contacter la direction</small>}
  </aside>;
}
