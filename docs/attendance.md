# YEM — Module 12 : présences, absences, retards et justificatifs

## Fonctionnement

Une séance d'appel appartient à une école, une classe, une **date** et un créneau nommé librement, par exemple le matin ou chaque cours. Le serveur ne présume aucun créneau ni aucune présence. Le système accepte plusieurs séances dans la même journée, et empêche les doublons pour le même créneau.

Les statuts sont **configurables par établissement**, et peuvent être surchargés par année, cycle, niveau et classe via `SchoolSetting`. Exemple :

```json
{
  "attendance": {
    "statuses": [
      {"code":"p","label":"Présent","group":"present"},
      {"code":"a","label":"Absent","group":"absent"},
      {"code":"r","label":"Retard","group":"late"},
      {"code":"sp","label":"Sortie autorisée","group":"other"}
    ]
  }
}
```

Les codes et libellés ne sont pas codés en dur. Les groupes techniques `present`, `absent`, `late`, `other` servent aux statistiques ; les écoles peuvent ajouter jusqu'à 30 codes. L'absence de politique ne crée **aucun statut implicite** : l'API demande une configuration explicite.

L'appel est effectué par lot d'au maximum 100 inscriptions, avec une révision pour chaque enregistrement. Une première saisie a une révision 0 ; une correction exige la révision courante et un motif. Le changement est conservé dans un historique append-only (avant / après / responsable / motif), sans suppression physique. Une justification peut être enregistrée par l'enseignant, mais seul un membre ayant le droit `school.attendance.write` peut la **valider** (champ `justified=true`). La clôture est réservée à `school.attendance.finalize` : elle vérifie que tous les inscrits éligibles sont renseignés, fige la séance, et empêche toute correction silencieuse. Une personne non renseignée reste « non renseignée » : ni présente ni absente par défaut.

## Accès et protection

La direction possède les droits lecture, écriture et clôture. Le secrétariat possède lecture et écriture. Un enseignant n'accède en lecture/écriture qu'aux classes où une affectation de personnel active le désigne ; un autre enseignant ne voit pas l'appel. Les permissions de rôle restent modifiables. Les événements importants sont audités ; sessions authentifiées et contrôle CSRF pour les écritures ; isolation multi-écoles 404.

Pas de notification automatique aux parents dans ce module, ni de document médical ou preuve clinique collectée ; les justificatifs sont de simples informations administratives textuelles.

## API

- `GET /api/v1/schools/{id}/attendance/options?classroom={id}` — statuts de cette classe
- `GET /api/v1/schools/{id}/attendance/sessions?classroom={id}` — liste ; `POST` — créer `{classroom,date,slot,label}`
- `GET /api/v1/schools/{id}/attendance/sessions/{id}` — liste des élèves inscrits et des marques existantes
- `POST /api/v1/schools/{id}/attendance/sessions/{id}/marks` — `{marks: [{enrollment,status,note,justification,justified,revision,reason}]}`
- `GET /api/v1/schools/{id}/attendance/sessions/{id}/marks/{enrollment}/history` — historique
- `POST /api/v1/schools/{id}/attendance/sessions/{id}/close` — `{revision}`
- `GET /api/v1/schools/{id}/attendance/summary?classroom={id}&from=YYYY-MM-DD&to=YYYY-MM-DD` — décompte de saisies par groupe, sans supposer que « non saisi » signifie « présent ».

Le scénario est couvert par `python backend/manage.py test institutions.test_attendance`, en plus de la CI complète. Les données de développement sont fictives. Une recette PC/Android et une validation de production restent nécessaires.
