# YEM — Module 15 : espace parents et contrôle des accès

L'espace parents est une **interface de lecture seule** sur les informations du ou des enfants explicitement reliés au compte par un établissement. Il ne crée ni note, ni bulletin, ni paiement ni demande de modification.

## Vérification des liens

Un nom, téléphone ou e-mail identique à une fiche responsable légal **ne vaut pas autorisation**. L'établissement vérifie le lien familial hors système, nomme un compte utilisateur existant avec rôle « parent » actif dans son école, puis confirme l'association via \`school.parents.manage\` (direction par défaut). L'API ne constitue pas une preuve d'identité automatique et ne stocke aucun justificatif sensible. La liaison possède l'acteur de vérification, sa date, une révision et un historique d'audit ; révocation explicite possible à tout moment. L'accès est immédiatement interrompu en cas de révocation, rôle parent retiré, membre désactivé, compte désactivé, établissement fermé ou fiche responsable/élève archivée.

Une personne peut accéder à plusieurs enfants si **chacun** possède une liaison vérifiée. Un même enfant peut avoir plusieurs responsables si les liens sont vérifiés individuellement. Aucun accès transversal entre établissements ou familles, même si l'identifiant UUID est connu.

## Informations visibles

- Dossier scolaire : élèves liés et inscriptions par année, classe et statut.
- Bulletins : **publiés uniquement**, dernier rectificatif officiel le cas échéant ; téléchargement du PDF autorisé via une route filtrée pour cet enfant. Aucun brouillon ni évaluation non publiée.
- Assiduité : uniquement séances clôturées ; statut et indication de justification, sans exposer les observations internes.
- Finances : frais facturés, montants enregistrés, soldes et dates d'échéance, regroupés par devise. Les références de caisse et moyens de paiement ne sont pas divulgués. Aucune confirmation bancaire ni paiement automatique n'est prétendu.
- Emploi du temps : séances actives des classes d'inscriptions actives de l'enfant, sans liste des autres élèves.

Tous les résultats utilisent des réponses privées non mises en cache, des contrôles sur **chaque objet demandé**, et des sessions Django authentifiées. Les rôles utilisateurs sont respectés ; une session de l'école ne suffit pas à voir un enfant.

## API

Préfixe \`/api/v1\` :
- \`GET /parents/children\` : enfants vérifiés, toutes écoles autorisées
- \`GET /parents/children/{student_id}/enrollments\`
- \`GET /parents/children/{student_id}/reports\`
- \`GET /parents/children/{student_id}/reports/{report_id}\`
- \`GET /parents/children/{student_id}/reports/{report_id}/pdf\`
- \`GET /parents/children/{student_id}/attendance\`
- \`GET /parents/children/{student_id}/finance\`
- \`GET /parents/children/{student_id}/timetable\`
- \`GET/POST /schools/{school_id}/parent-links\` — gestion réservée à la direction
- \`PATCH /schools/{school_id}/parent-links/{link_id}\` — révocation avec révision

Le compte parent doit avoir été créé et affecté par les procédures sécurisées d'administration des comptes existants. Aucun lien magique public, autorisation par adresse e-mail ou collecte libre de documents de mineurs n'est introduit.

Ce module ne livre pas encore la messagerie, les notifications automatiques ou des paiements en ligne. Une recette mobile/PC avec plusieurs vrais rôles et établissements reste requise avant un déploiement.
