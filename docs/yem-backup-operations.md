# YEM — sauvegardes opérationnelles (itération 3)

## Cible minimale proposée, à confirmer par une mesure réelle

- Sauvegarde logique PostgreSQL 17, chiffrée AES256, chaque jour à 02:00 UTC (03:00 Gabon), plus une sauvegarde avant une migration risquée.
- Deux copies contrôlées : disque du poste de sauvegarde et véritable volume externe sur un autre support/hôte. Le volume externe doit être monté ; un répertoire local de substitution est refusé. Le montage seul ne prouve pas l'indépendance physique : l'exploitant doit la vérifier.
- Objectifs indicatifs RPO 24 h, RTO 4 h ; mesurer et réviser après exercice. Vérifier la réussite chaque jour, alerter sur échec ou absence de sauvegarde récente. Rétention proposée : 30 quotidiennes et 3 mensuelles, à ajuster à la capacité et aux obligations applicables.
- Aucun effacement automatique dans cette version. Rotation après contrôle des deux copies, du dernier exercice réussi et des obligations de conservation. Surveiller l'espace libre des deux volumes. Une copie partielle ou un échec de transfert ne valide pas la sauvegarde.
- Les objets hors PostgreSQL (photos, pièces, documents stockés séparément), secrets de configuration et clés nécessaires au redémarrage doivent faire l'objet d'un plan de sauvegarde distinct.

## Installation sur un hôte Linux dédié (pas sur GitHub Actions)

1. Prévoir un compte système non privilégié `yem-backup`, une installation du code validé en lecture seule dans `/opt/yem`, Bash, PostgreSQL client 17, GnuPG, Python 3, coreutils et util-linux. Préparer deux destinations privées, hors du dépôt, accessibles à ce compte. Le volume externe doit être un vrai montage dédié, protégé contre les accès non autorisés. Ne pas utiliser un emplacement public.
2. Créer `/etc/yem/backup.env` avec droits root 0600. Configurer YEM_BACKUP_DATABASE_URL (connexion directe ou session PostgreSQL autorisée, TLS vérifié sur source distante), YEM_BACKUP_PASSPHRASE (secret aléatoire robuste, conservé dans un coffre indépendant), YEM_BACKUP_DIR et YEM_BACKUP_EXTERNAL_DIR (racine du montage externe). Ne jamais envoyer ces valeurs dans GitHub, les logs, ni le chat.
3. Installer les deux unités systemd depuis deploy/backup, recharger systemd, lancer manuellement `sudo systemctl start yem-backup.service` et vérifier son résultat. Activer `sudo systemctl enable --now yem-backup.timer` seulement après contrôle du premier succès. Contrôler `systemctl list-timers yem-backup.timer` et `journalctl -u yem-backup.service`. Surveiller les échecs via un service d'alerte de l'exploitant.
4. Le script conserve les copies locales si le transfert échoue. Réparer le montage et refaire un lancement. Les dossiers .partial-* ne sont pas des copies validées. Ne pas utiliser un GitHub Action public ni des artefacts CI pour les vraies données.

## Restauration réelle (condition d'ouverture client)

- Récupérer une copie externe et son empreinte. Utiliser un PostgreSQL 17 dédié, vide, local, avec base yem_drill_* ; isoler réseau et services sortants. Préparer les rôles/extensions PostgreSQL nécessaires à l'application. Ne jamais restaurer sur la production.
- L'ancien script de comparaison compare les volumes à la source **au moment du contrôle**, et non à l'instant du dump. Pour une recette probante, planifier un instant de référence sans écritures sur la source pendant dump et contrôle, ou établir un manifeste de volumes cohérent avec le snapshot. Une divergence n'autorise aucune correction automatique.
- Exécuter scripts/yem_restore_drill.sh avec les variables privées attendues. Vérifier le démarrage de l'application restaurée, les permissions, un rattachement parent, un bulletin et un reçu ; éviter les notifications et paiements réels. Ne publier ni données scolaires ni identifiants dans un rapport.
- Enregistrer date UTC, version du code, empreinte de l'archive, durée, contrôles réussis/échoués, responsable et décision. Programmer un exercice au moins mensuel et avant activation de la clôture réelle. Une réussite CI synthétique ne remplace jamais cet exercice.

## Limites de cette livraison

Le minuteur est un modèle à installer, pas un service déjà activé. L'absence d'un hôte de sauvegarde externe, d'un montage privé, d'un accès PostgreSQL approprié ou d'une preuve de restauration reste bloquante. Aucun achat, transfert de données réelles ou changement de configuration de production n'est inclus. Suivi : #49, #108.
