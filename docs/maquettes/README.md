# Maquettes de référence YEM

Ces images sont la référence visuelle de l'interface. Le code doit les reproduire à l'identique (disposition, textes, couleurs, présentation des fonctionnalités).

| Fichier | Écran | Composant |
| --- | --- | --- |
| 01-tableau-de-bord.jpg | Tableau de bord fondateur | `frontend/YemDesktop.jsx` → `Dashboard` |
| 02-eleves.jpg | Gestion des élèves | `Students` |
| 03-admissions.jpg | Admissions & préinscriptions | `Admissions` |
| 04-paiements.jpg | Encaissements et caisse journalière | `Payments` |
| 05-impayes-relances.jpg | Impayés & relances | `Arrears` |
| 06-bulletins.jpg | Bulletins et résultats scolaires | `Bulletins` / `ReportCard` |
| 07-parametrage-bulletins.jpg | Paramétrage pédagogique et bulletins | `BulletinConfig` |
| 08-mobile-parent-appel-recu.jpg | Expérience mobile (parent, appel, reçu) | `frontend/YemMobile.jsx` |

Les composants communs (logo, barre supérieure, menu, cartes, tableaux, graphiques) sont dans `frontend/yem-ui.jsx` et `frontend/yem-desktop.css`.
L'espace réel connecté (`frontend/SchoolDashboard.jsx`) utilise le même cadre et le même menu ; ses pages affichent les modules existants autorisés pour le rôle du compte.
