# YEM — Module 13 : emplois du temps et planification

Planification hebdomadaire avec trois ressources vérifiées : **classe, salle, enseignant**, sans imposer des créneaux ou des jours scolaires fixes.

- Salles par école : nom, code et capacité facultative.
- Créneaux par année scolaire : heures début/fin `HH:MM` et codes personnalisés.
- Séances : cours déjà créé, intervenant explicitement lié au cours via `CourseInstructor`, salle facultative, jour de semaine 0=lundi à 6=dimanche, intervalle de dates dans l'année et statut actif.
- Un intervalle horaire `[début, fin)` permet deux cours consécutifs. L'algorithme refuse les réservations se chevauchant sur une date où le jour de semaine existe effectivement dans les deux périodes.
- Conflits inter-classes par enseignant et salle, même si l'enseignant possède plusieurs affectations ; conflits par classe, même avec matières et intervenants distincts.
- Les opérations d'écriture verrouillent la ligne de l'établissement sous transaction PostgreSQL pour éviter la double réservation concurrente.
- Une séance peut être déplacée ou archivée avec révision optimiste ; les enregistrements historiques restent conservés, les routes DELETE sont interdites.
- Modifier la durée d'un créneau utilisé, ou désactiver une salle utilisée, est refusé tant que les séances liées sont actives.
- Permissions : direction/secrétariat gèrent ; enseignant consulte seulement les séances où il est le responsable du cours ; fondateur non gestionnaire n'accède pas aux emplois du temps.
- Audit des modifications et isolation de toutes les ressources par école.

API `/api/v1/schools/{school_id}/timetable/` : `rooms`, `rooms/{id}`, `slots`, `slots/{id}`, `entries`, `entries/{id}`. Les collections acceptent GET et POST, les détails GET et PATCH ; sessions et CSRF requis. Les entrées sont filtrables par année et classe.

Limites : cette V1 ne génère pas automatiquement un planning optimal et n'ajoute ni jours fériés, ni salles communes à plusieurs établissements, ni exception de séance unique. Les créneaux restent à configurer manuellement.
