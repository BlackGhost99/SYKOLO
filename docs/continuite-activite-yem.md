# YEM — Continuité d'activité, sauvegarde et restauration (P0, issue #49)

État au 05/11/2026 : scripts créés et exercice automatique uniquement **sur données fictives**. Cela **ne valide pas** les sauvegardes de production.

## Infrastructure vérifiée
- API : Render yem-api, déploiement manuel de main.
- Base réellement utilisée : projet **YEM Supabase** (kxkifsrlkwhedqraojvj), région **eu-west-1**, PostgreSQL 17. Ne pas confondre avec la base Gaboshop du compte Render.
- Formule d'abonnement, sauvegardes, horaire, rétention et droit de restauration **non vérifiés** avec les accès disponibles. Tableau de bord : https://supabase.com/dashboard/project/kxkifsrlkwhedqraojvj/database/backups
- Référence Supabase : https://supabase.com/docs/guides/platform/backups. Sur Free, il ne faut pas se reposer sur une garantie de sauvegarde quotidienne. Aucune souscription payante n'a été engagée.

## Procédure indépendante, chiffrée, sur un poste d'administration fiable
Prérequis : client PostgreSQL 17 (ou plus récent), Bash, GnuPG, sha256sum. La sauvegarde ne doit jamais être conservée dans le dépôt Git, ni les logs Render/GitHub, ni envoyée dans un chat.

1. Récupérer dans un coffre à secrets l'URL PostgreSQL de **YEM** (pas la clé API Supabase) et une phrase secrète aléatoire d'au moins 24 caractères. Ne pas les mettre dans le code ni dans GitHub Actions.
2. Dans un terminal administrateur, définir les variables d'environnement YEM_BACKUP_DATABASE_URL, YEM_BACKUP_PASSPHRASE, YEM_BACKUP_DIR. Le répertoire doit être privé, hors du dépôt.
3. Exécuter : bash scripts/yem_backup.sh
4. Le script génère une archive pg_dump personnalisée chiffrée symétriquement par GnuPG AES-256, vérifie qu'elle est lisible par pg_restore, et crée un fichier de contrôle SHA-256. Il ne modifie pas la base.
5. Copier les deux fichiers vers un **stockage sécurisé indépendant** (et idéalement géographiquement séparé). Vérifier la rétention, les accès, le chiffrement, les alarmes en cas d'échec et le renouvellement périodique.
6. Effacer les variables sensibles de session après opération et gérer leur rotation.

Une sauvegarde manuelle prouve seulement l'existence de l'archive le jour considéré. Il faudra organiser une exécution récurrente surveillée sur un système de confiance, et documenter la fréquence, les échecs et les accès.

## Restauration — jamais sur la base de production
Sur un PostgreSQL local de même version majeure, créer une base **neuve et vide** dont le nom commence par yem_drill_. Définir YEM_DRILL_DATABASE_URL, YEM_RESTORE_ARCHIVE et reprendre la phrase secrète + la connexion source YEM (lecture de décomptes seulement), puis :

  bash scripts/yem_restore_drill.sh

Le script refuse les destinations distantes, les bases pré-remplies, les mauvais noms de base et les archives altérées. Après restauration, il vérifie le nombre de comptes, écoles, membres, élèves, inscriptions, bulletins, paiements et clôtures de caisse. Les décomptes ne révèlent aucun dossier personnel.

**La restauration n'est réellement acceptée** qu'après une vérification manuelle sur l'instance isolée : connexion, MFA, accès inter-écoles, bulletins PDF, caisse, absence d'erreurs de migration et traçabilité. Détruire la base de test ensuite.

Le workflow GitHub Actions backup-drill.yml vérifie ces scripts sur **une base PostgreSQL éphémère contenant une école fictive et un élève fictif** ; il n'accède ni à Supabase production ni aux sauvegardes réelles.

## Autorisation de commercialisation — preuves requises
- [ ] Supabase : plan, stratégie de sauvegarde, localisation et conservation confirmés et consignés.
- [ ] Premier dump **réel** chiffré et stocké en lieu indépendant.
- [ ] Copie restaurée sur environnement isolé avec procès-verbal et résultats fonctionnels.
- [ ] RPO (perte maximale), RTO (reprise maximale) et rétention validés par le responsable.
- [ ] Automatisation supervisée, alerte sur échec, rotation et accès restreints.
- [ ] Sauvegarde séparée des éventuels documents ou objets hors base.
- [ ] Validation de la résidence et des transferts de données personnelles sensibles par un interlocuteur compétent.

Ne jamais conclure que les sauvegardes production sont opérationnelles sur la seule foi des tests CI.
