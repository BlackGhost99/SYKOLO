# Module 07 — Matières et programmes YEM

Une école crée son propre catalogue de matières (code, intitulé et description). Chaque cours rattache une matière à une classe et une année précises. Son coefficient décimal positif est choisi par l'établissement, et non imposé par la plateforme. L'équipe peut structurer le programme pédagogique en unités ordonnées et ajouter plusieurs intervenants, préalablement affectés à cette classe dans le module 06.

API : GET/POST /schools/{id}/subjects, /courses, /courses/{course_id}/units, /courses/{course_id}/instructors ; GET/PATCH sur les UUID de matières, cours et unités ; PATCH des intervenants pour archiver. Préfixe complet /api/v1. Aucun DELETE : historisation par révision et active=false.

Droits : school.curriculum.read en lecture ; school.curriculum.manage pour créer/mettre à jour catalogue, cours et affectations de matières. Un enseignant affecté à un cours peut modifier uniquement les unités de son cours, pas le coefficient ni les affectations. Toutes les données sont rattachées à l'établissement ; les relations d'année, classe, matière et enseignant doivent appartenir à cette école.

Les évaluations, notes et bulletins réels ne sont pas inclus ; ils exploiteront ce référentiel dans les modules 08 et 09.
