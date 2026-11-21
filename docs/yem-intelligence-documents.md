# YEM Intelligence — Documents P1a (préinspection locale)

Issue de suivi : [#274](https://github.com/BlackGhost99/SYKOLO/issues/274) ; feuille de route générale : [#225](https://github.com/BlackGhost99/SYKOLO/issues/225).

## Ce qui est livré

Le module `backend/institutions/intelligence_document_preflight.py` contrôle un flux **PDF, PNG ou JPEG** sans le parser, le décoder, le conserver ni appeler un service extérieur :

- extension contrôlée, signature magique correspondante, taille bornée à 5 Mio ;
- lecture bornée, restauration de la position du flux d'entrée si possible ;
- empreinte SHA-256 interne et métadonnées minimales sans nom de l'élève ;
- indicateurs explicites `not_performed`, `not_stored`, `external_provider_used=false`, `needs_human_validation=true` ;
- tests avec uniquement de faux octets, sans élèves réels ni appels payants.

Ceci est une **préinspection**, et non une validation de sécurité. Une signature PDF ou JPEG correcte ne prouve ni l'intégrité du document ni son innocuité. Aucune extraction de texte, aucun OCR, aucun antivirus, aucune vérification de champs et aucune écriture SQL ne sont livrés dans cette PR. Le module n'est pas encore exposé à un navigateur, ni raccordé aux flux de téléchargement d'YEM.

## Prochaines validations obligatoires

1. Exposer ce contrôle uniquement dans un flux autorisé d'établissement et d'année, avec permissions et isolation multi-écoles, sans fuite de données personnelles vers la console plateforme.
2. Quarantaine et analyse antivirus **avant tout parseur PDF/image ou OCR** ; limites de pages, taille décompressée, résolution, CPU/mémoire et durée de traitement.
3. Extraction de la couche texte si disponible, OCR local sinon, dépendance optionnelle et dégradation contrôlée ; aucun appel Gemini/Mistral par défaut.
4. Suggestions avec preuves traçables (source, page/zone, confiance), ambiguïtés et validation humaine explicite avant toute modification scolaire.
5. Tests en sandbox et avec fichiers anonymisés, double contrôle métier, conservation réglementée, nettoyage des fichiers temporaires.

## Exécution des tests

Depuis `backend/` :

```bash
python manage.py test institutions.test_intelligence_document_preflight
```

**Périmètre anti-conflit :** aucun changement aux finances, sorties/entrées, API, modèles, migrations, React, Render et SingPay. Pas de déploiement attendu pour cette seule brique.
