import React from "react";
import {Button,Card,PageHeader} from "./yem-ui.jsx";
import PWAInstall from "./PWAInstall.jsx";

export default function TeacherHome({schoolName, onNavigate, canNotes, canAttendance, canClasses}) {
  return <><PageHeader title="Tableau de bord" subtitle="Espace professeur" />
    <div className="yd-real-body">
    <Card title="Mon espace professeur" icon="cap" subtitle={"Vos cours et votre suivi pédagogique · "+schoolName}>
      <div className="actions"><PWAInstall buttonClassName="yd-btn primary" label="Installer YEM sur mon téléphone"/></div>
      <p className="hint">La même application YEM fonctionne sur ordinateur et sur téléphone. Les données de l'école restent synchronisées lorsque vous êtes connecté.</p>
    </Card>
    <Card title="Mes actions pédagogiques" icon="calendar"
      subtitle="Accédez aux fonctionnalités auxquelles votre établissement vous a donné droit.">
      <div className="actions" style={{flexWrap:"wrap"}}>
        {canNotes&&<Button icon="file" primary onClick={()=>onNavigate("bulletins","assessments")}>Saisir les notes et consulter les moyennes</Button>}
        {canAttendance&&<Button icon="users" onClick={()=>onNavigate("absences","attendance")}>Faire l'appel</Button>}
        {canClasses&&<Button icon="layers" onClick={()=>onNavigate("classes","live")}>Mes classes</Button>}
        <Button icon="user" onClick={()=>onNavigate("profile")}>Mon profil et ma photo</Button>
      </div>
      {!canNotes&&!canAttendance&&!canClasses&&<p className="hint">Vos accès pédagogiques seront disponibles après affectation par la direction.</p>}
    </Card>
  </div></>;
}
