# YEM · Calendrier pédagogique multicycle

Un cycle est un `AcademicCycle` du même établissement. Les niveaux, séries, classes,
inscriptions, affectations et rattachements familiaux conservent leurs identifiants.

## Contrat pour les évaluations et les moyennes

- `AcademicPeriod.for_classroom(classroom)` désigne les publications de la classe.
  Les périodes historiques à cycle nul restent admissibles pour les références et
  les clients historiques. Elles restent identifiées comme communes dans le
  calendrier et ne sont attribuées à aucun cycle automatiquement.
- Le palier reste une entrée indépendante du calendrier. Une période de publication
  peut recouvrir un palier du même cycle. Aucune des deux entrées n'exige l'autre.
  Une classe sans publication peut toujours utiliser la référence annuelle nulle.
- Les semaines d'apprentissage et d'évaluation sont des nombres facultatifs sur
  chaque plage. Les congés et examens sont des événements distincts. La configuration
  du calendrier ne crée ni notes, ni bulletins, ni notifications.
- Les règles de barème, coefficients et arrondis continuent à venir de
  `resolve_settings` et des instantanés des évaluations. Les calculs normalisent
  en pourcentage puis restituent le barème configuré, y compris une échelle qualitative.
  Cette tranche utilise le périmètre existant année/cycle/niveau/classe. Un éventuel
  périmètre série pourra être ajouté avec les cas d'usage du moteur d'évaluation.
- Les nouveaux brouillons de bulletin enregistrent la révision de la période.
  Les bulletins déjà diffusés restent consultables avec leur instantané et leur ID
  de période. La publication d'un bulletin fige l'édition de sa période. Aucune
  migration ne réécrit les notes ni les bulletins existants.

## Configuration et mise en service

Le profil `calendar_profile` est un réglage facultatif année/cycle dans
`SchoolSetting`. Ses objectifs indicatifs `milestone_target` et
`publication_target` acceptent zéro. Les modèles proposés à l'écran ne génèrent
aucune donnée. Le portail de l'établissement fournit le choix d'école existant.

Avant application en production, joindre à la mise en service la CI PostgreSQL,
l'identifiant et l'horodatage d'une sauvegarde récente, et le résultat d'une
restauration sur une base isolée. La migration conserve les identifiants historiques.
Une fois des codes de périodes réutilisés entre cycles, revenir au schéma global
exige la restauration ou une nouvelle migration de compatibilité. Tester la recette
multi-cycle et mono-cycle sur un environnement isolé.
