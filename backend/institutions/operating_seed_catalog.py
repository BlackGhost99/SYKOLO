"""Catalogue initial des dépenses YEM — cahier des charges Chantier B, familles B01 à B20.

Ces entrées sont un modèle de départ ADMINISTRABLE, jamais une nomenclature
comptable rigide. Les pôles ne sont que des suggestions ; le choix effectif
de l'activité reste distinct de la famille comptable. Installation explicite,
idempotente et par établissement (aucun auto-seeding en GET/migration).
"""

# (code, intitulé, pôle SUGGÉRÉ ou vide, [(code de sous-catégorie, intitulé)])
DEFAULT_EXPENSE_FAMILIES = [
  [
    "b01",
    "Rémunérations du personnel",
    "",
    [
      [
        "b01_salaires_des_proviseurs_et_directeur",
        "Salaires des proviseurs et directeurs"
      ],
      [
        "b01_salaires_des_enseignants",
        "Salaires des enseignants"
      ],
      [
        "b01_salaires_des_educateurs",
        "Salaires des éducateurs"
      ],
      [
        "b01_salaires_des_censeurs",
        "Salaires des censeurs"
      ],
      [
        "b01_salaires_des_surveillants",
        "Salaires des surveillants"
      ],
      [
        "b01_salaires_des_secretaires",
        "Salaires des secrétaires"
      ],
      [
        "b01_salaires_des_comptables",
        "Salaires des comptables"
      ],
      [
        "b01_salaires_des_economes",
        "Salaires des économes"
      ],
      [
        "b01_salaires_des_informaticiens",
        "Salaires des informaticiens"
      ],
      [
        "b01_salaires_des_agents_de_securite",
        "Salaires des agents de sécurité"
      ],
      [
        "b01_salaires_du_personnel_d_entretien",
        "Salaires du personnel d'entretien"
      ],
      [
        "b01_salaires_des_chauffeurs",
        "Salaires des chauffeurs"
      ],
      [
        "b01_salaires_du_personnel_de_restauratio",
        "Salaires du personnel de restauration"
      ],
      [
        "b01_remunerations_des_vacataires",
        "Rémunérations des vacataires"
      ],
      [
        "b01_remunerations_des_stagiaires",
        "Rémunérations des stagiaires"
      ],
      [
        "b01_remunerations_des_remplacants",
        "Rémunérations des remplaçants"
      ],
      [
        "b01_remunerations_des_responsables_pedag",
        "Rémunérations des responsables pédagogiques"
      ],
      [
        "b01_remunerations_du_proprietaire_exerca",
        "Rémunérations du propriétaire exerçant une fonction salariée"
      ],
      [
        "b01_remunerations_de_toute_autre_fonctio",
        "Rémunérations de toute autre fonction personnalisée"
      ]
    ]
  ],
  [
    "b02",
    "Primes et indemnités",
    "",
    [
      [
        "b02_primes_de_rendement",
        "Primes de rendement"
      ],
      [
        "b02_primes_d_anciennete",
        "Primes d'ancienneté"
      ],
      [
        "b02_primes_de_responsabilite",
        "Primes de responsabilité"
      ],
      [
        "b02_primes_exceptionnelles",
        "Primes exceptionnelles"
      ],
      [
        "b02_heures_supplementaires",
        "Heures supplémentaires"
      ],
      [
        "b02_indemnites_de_transport",
        "Indemnités de transport"
      ],
      [
        "b02_indemnites_de_logement",
        "Indemnités de logement"
      ],
      [
        "b02_indemnites_de_repas",
        "Indemnités de repas"
      ],
      [
        "b02_indemnites_de_mission",
        "Indemnités de mission"
      ],
      [
        "b02_indemnites_de_conges",
        "Indemnités de congés"
      ],
      [
        "b02_indemnites_de_depart",
        "Indemnités de départ"
      ],
      [
        "b02_gratifications_et_recompenses",
        "Gratifications et récompenses"
      ],
      [
        "b02_autres_avantages_personnalises",
        "Autres avantages personnalisés"
      ]
    ]
  ],
  [
    "b03",
    "Charges sociales, fiscales et réglementaires",
    "common",
    [
      [
        "b03_cotisations_patronales",
        "Cotisations patronales"
      ],
      [
        "b03_cotisations_salariales_a_reverser",
        "Cotisations salariales à reverser"
      ],
      [
        "b03_cotisations_cnss",
        "Cotisations CNSS"
      ],
      [
        "b03_cotisations_cnamgs",
        "Cotisations CNAMGS"
      ],
      [
        "b03_retenues_fiscales_a_reverser",
        "Retenues fiscales à reverser"
      ],
      [
        "b03_impots_applicables",
        "Impôts applicables"
      ],
      [
        "b03_taxes_professionnelles",
        "Taxes professionnelles"
      ],
      [
        "b03_taxes_municipales",
        "Taxes municipales"
      ],
      [
        "b03_frais_d_agrement",
        "Frais d'agrément"
      ],
      [
        "b03_autorisations_administratives",
        "Autorisations administratives"
      ],
      [
        "b03_penalites_et_regularisations",
        "Pénalités et régularisations"
      ]
    ]
  ],
  [
    "b04",
    "Locaux et bâtiments",
    "common",
    [
      [
        "b04_loyers",
        "Loyers"
      ],
      [
        "b04_location_de_bureaux",
        "Location de bureaux"
      ],
      [
        "b04_location_de_terrains",
        "Location de terrains"
      ],
      [
        "b04_construction",
        "Construction"
      ],
      [
        "b04_extension",
        "Extension"
      ],
      [
        "b04_renovation",
        "Rénovation"
      ],
      [
        "b04_peinture",
        "Peinture"
      ],
      [
        "b04_reparation_de_toiture",
        "Réparation de toiture"
      ],
      [
        "b04_plomberie",
        "Plomberie"
      ],
      [
        "b04_travaux_electriques",
        "Travaux électriques"
      ],
      [
        "b04_amenagement_exterieur",
        "Aménagement extérieur"
      ],
      [
        "b04_entretien_immobilier",
        "Entretien immobilier"
      ]
    ]
  ],
  [
    "b05",
    "Eau, énergie et télécommunications",
    "common",
    [
      [
        "b05_electricite",
        "Électricité"
      ],
      [
        "b05_eau",
        "Eau"
      ],
      [
        "b05_gaz",
        "Gaz"
      ],
      [
        "b05_carburant_des_groupes_electrogenes",
        "Carburant des groupes électrogènes"
      ],
      [
        "b05_internet",
        "Internet"
      ],
      [
        "b05_telephonie_fixe",
        "Téléphonie fixe"
      ],
      [
        "b05_telephonie_mobile",
        "Téléphonie mobile"
      ],
      [
        "b05_forfaits_de_donnees",
        "Forfaits de données"
      ]
    ]
  ],
  [
    "b06",
    "Fournitures administratives",
    "common",
    [
      [
        "b06_papier",
        "Papier"
      ],
      [
        "b06_stylos",
        "Stylos"
      ],
      [
        "b06_fournitures_de_bureau",
        "Fournitures de bureau"
      ],
      [
        "b06_classeurs",
        "Classeurs"
      ],
      [
        "b06_dossiers",
        "Dossiers"
      ],
      [
        "b06_enveloppes",
        "Enveloppes"
      ],
      [
        "b06_cartouches_et_toners",
        "Cartouches et toners"
      ],
      [
        "b06_registres",
        "Registres"
      ],
      [
        "b06_impressions",
        "Impressions"
      ],
      [
        "b06_cachets_et_consommables",
        "Cachets et consommables"
      ]
    ]
  ],
  [
    "b07",
    "Matériel pédagogique",
    "school",
    [
      [
        "b07_manuels_scolaires",
        "Manuels scolaires"
      ],
      [
        "b07_cahiers_pedagogiques",
        "Cahiers pédagogiques"
      ],
      [
        "b07_tableaux",
        "Tableaux"
      ],
      [
        "b07_craies_et_marqueurs",
        "Craies et marqueurs"
      ],
      [
        "b07_materiel_scientifique",
        "Matériel scientifique"
      ],
      [
        "b07_materiel_de_laboratoire",
        "Matériel de laboratoire"
      ],
      [
        "b07_bibliotheque",
        "Bibliothèque"
      ],
      [
        "b07_jeux_educatifs",
        "Jeux éducatifs"
      ],
      [
        "b07_materiel_de_motricite",
        "Matériel de motricité"
      ],
      [
        "b07_ressources_numeriques",
        "Ressources numériques"
      ]
    ]
  ],
  [
    "b08",
    "Tenues, marchandises et stocks",
    "extraschool",
    [
      [
        "b08_achat_de_tenues_scolaires",
        "Achat de tenues scolaires"
      ],
      [
        "b08_achat_de_tenues_de_sport",
        "Achat de tenues de sport"
      ],
      [
        "b08_achat_de_blouses",
        "Achat de blouses"
      ],
      [
        "b08_achat_de_badges_et_ecussons",
        "Achat de badges et écussons"
      ],
      [
        "b08_fournitures_destinees_a_la_revente",
        "Fournitures destinées à la revente"
      ],
      [
        "b08_frais_de_confection",
        "Frais de confection"
      ],
      [
        "b08_frais_de_livraison",
        "Frais de livraison"
      ],
      [
        "b08_frais_de_stockage",
        "Frais de stockage"
      ]
    ]
  ],
  [
    "b09",
    "Informatique et logiciels",
    "",
    [
      [
        "b09_ordinateurs",
        "Ordinateurs"
      ],
      [
        "b09_tablettes",
        "Tablettes"
      ],
      [
        "b09_imprimantes",
        "Imprimantes"
      ],
      [
        "b09_serveurs",
        "Serveurs"
      ],
      [
        "b09_equipements_reseau",
        "Équipements réseau"
      ],
      [
        "b09_onduleurs",
        "Onduleurs"
      ],
      [
        "b09_licences_logicielles",
        "Licences logicielles"
      ],
      [
        "b09_abonnement_yem",
        "Abonnement YEM"
      ],
      [
        "b09_hebergement",
        "Hébergement"
      ],
      [
        "b09_maintenance_informatique",
        "Maintenance informatique"
      ],
      [
        "b09_antivirus_et_securite_informatique",
        "Antivirus et sécurité informatique"
      ],
      [
        "b09_support_technique",
        "Support technique"
      ]
    ]
  ],
  [
    "b10",
    "Hygiène, entretien et sécurité",
    "common",
    [
      [
        "b10_produits_de_nettoyage",
        "Produits de nettoyage"
      ],
      [
        "b10_materiel_de_nettoyage",
        "Matériel de nettoyage"
      ],
      [
        "b10_desinfectants",
        "Désinfectants"
      ],
      [
        "b10_collecte_des_dechets",
        "Collecte des déchets"
      ],
      [
        "b10_desinsectisation",
        "Désinsectisation"
      ],
      [
        "b10_deratisation",
        "Dératisation"
      ],
      [
        "b10_gardiennage",
        "Gardiennage"
      ],
      [
        "b10_videosurveillance",
        "Vidéosurveillance"
      ],
      [
        "b10_controle_d_acces",
        "Contrôle d'accès"
      ],
      [
        "b10_securite_incendie",
        "Sécurité incendie"
      ],
      [
        "b10_equipements_de_protection",
        "Équipements de protection"
      ]
    ]
  ],
  [
    "b11",
    "Restauration et cantine",
    "extraschool",
    [
      [
        "b11_denrees_alimentaires",
        "Denrées alimentaires"
      ],
      [
        "b11_boissons",
        "Boissons"
      ],
      [
        "b11_gouters",
        "Goûters"
      ],
      [
        "b11_ustensiles",
        "Ustensiles"
      ],
      [
        "b11_equipements_de_cuisine",
        "Équipements de cuisine"
      ],
      [
        "b11_entretien_des_equipements",
        "Entretien des équipements"
      ],
      [
        "b11_prestations_de_restauration",
        "Prestations de restauration"
      ],
      [
        "b11_livraison_alimentaire",
        "Livraison alimentaire"
      ],
      [
        "b11_repas_pris_en_charge",
        "Repas pris en charge"
      ],
      [
        "b11_consommables",
        "Consommables"
      ]
    ]
  ],
  [
    "b12",
    "Transport et véhicules",
    "",
    [
      [
        "b12_achat_de_vehicules",
        "Achat de véhicules"
      ],
      [
        "b12_location_de_vehicules",
        "Location de véhicules"
      ],
      [
        "b12_carburant",
        "Carburant"
      ],
      [
        "b12_vidanges",
        "Vidanges"
      ],
      [
        "b12_reparations",
        "Réparations"
      ],
      [
        "b12_pieces_detachees",
        "Pièces détachées"
      ],
      [
        "b12_pneumatiques",
        "Pneumatiques"
      ],
      [
        "b12_assurance_automobile",
        "Assurance automobile"
      ],
      [
        "b12_controle_technique",
        "Contrôle technique"
      ],
      [
        "b12_prestations_de_transport",
        "Prestations de transport"
      ],
      [
        "b12_stationnement",
        "Stationnement"
      ],
      [
        "b12_deplacements_professionnels",
        "Déplacements professionnels"
      ]
    ]
  ],
  [
    "b13",
    "Examens et activités scolaires",
    "school",
    [
      [
        "b13_organisation_des_examens",
        "Organisation des examens"
      ],
      [
        "b13_impression_des_sujets",
        "Impression des sujets"
      ],
      [
        "b13_remuneration_des_correcteurs",
        "Rémunération des correcteurs"
      ],
      [
        "b13_organisation_des_concours",
        "Organisation des concours"
      ],
      [
        "b13_examens_blancs",
        "Examens blancs"
      ],
      [
        "b13_activites_sportives",
        "Activités sportives"
      ],
      [
        "b13_activites_culturelles",
        "Activités culturelles"
      ],
      [
        "b13_sorties_pedagogiques",
        "Sorties pédagogiques"
      ],
      [
        "b13_voyages_scolaires",
        "Voyages scolaires"
      ],
      [
        "b13_ceremonies",
        "Cérémonies"
      ]
    ]
  ],
  [
    "b14",
    "Santé, assurances et assistance",
    "common",
    [
      [
        "b14_assurance_scolaire",
        "Assurance scolaire"
      ],
      [
        "b14_responsabilite_civile",
        "Responsabilité civile"
      ],
      [
        "b14_assurance_des_batiments",
        "Assurance des bâtiments"
      ],
      [
        "b14_assurance_des_equipements",
        "Assurance des équipements"
      ],
      [
        "b14_assurance_du_personnel",
        "Assurance du personnel"
      ],
      [
        "b14_achats_pour_l_infirmerie",
        "Achats pour l'infirmerie"
      ],
      [
        "b14_prestations_medicales",
        "Prestations médicales"
      ],
      [
        "b14_assistance_sociale",
        "Assistance sociale"
      ]
    ]
  ],
  [
    "b15",
    "Communication et marketing",
    "common",
    [
      [
        "b15_publicite",
        "Publicité"
      ],
      [
        "b15_affiches",
        "Affiches"
      ],
      [
        "b15_prospectus",
        "Prospectus"
      ],
      [
        "b15_supports_graphiques",
        "Supports graphiques"
      ],
      [
        "b15_reseaux_sociaux",
        "Réseaux sociaux"
      ],
      [
        "b15_site_internet",
        "Site Internet"
      ],
      [
        "b15_campagnes_de_recrutement_d_eleves",
        "Campagnes de recrutement d'élèves"
      ],
      [
        "b15_journees_portes_ouvertes",
        "Journées portes ouvertes"
      ]
    ]
  ],
  [
    "b16",
    "Formation et prestations externes",
    "",
    [
      [
        "b16_formation_des_enseignants",
        "Formation des enseignants"
      ],
      [
        "b16_formation_administrative",
        "Formation administrative"
      ],
      [
        "b16_formation_informatique",
        "Formation informatique"
      ],
      [
        "b16_honoraires_juridiques",
        "Honoraires juridiques"
      ],
      [
        "b16_honoraires_comptables",
        "Honoraires comptables"
      ],
      [
        "b16_audit",
        "Audit"
      ],
      [
        "b16_consultants",
        "Consultants"
      ],
      [
        "b16_recrutement",
        "Recrutement"
      ]
    ]
  ],
  [
    "b17",
    "Mobilier et investissements",
    "investment",
    [
      [
        "b17_tables_bancs",
        "Tables-bancs"
      ],
      [
        "b17_chaises",
        "Chaises"
      ],
      [
        "b17_bureaux",
        "Bureaux"
      ],
      [
        "b17_armoires",
        "Armoires"
      ],
      [
        "b17_climatiseurs",
        "Climatiseurs"
      ],
      [
        "b17_ventilateurs",
        "Ventilateurs"
      ],
      [
        "b17_equipements_sportifs",
        "Équipements sportifs"
      ],
      [
        "b17_aires_de_jeux",
        "Aires de jeux"
      ],
      [
        "b17_groupes_electrogenes",
        "Groupes électrogènes"
      ],
      [
        "b17_acquisition_de_terrains",
        "Acquisition de terrains"
      ],
      [
        "b17_acquisition_de_batiments",
        "Acquisition de bâtiments"
      ]
    ]
  ],
  [
    "b18",
    "Frais bancaires et financiers",
    "",
    [
      [
        "b18_frais_de_tenue_de_compte",
        "Frais de tenue de compte"
      ],
      [
        "b18_frais_de_virement",
        "Frais de virement"
      ],
      [
        "b18_frais_mobile_money",
        "Frais Mobile Money"
      ],
      [
        "b18_commissions_singpay",
        "Commissions SingPay"
      ],
      [
        "b18_interets_d_emprunts",
        "Intérêts d'emprunts"
      ],
      [
        "b18_frais_de_dossier_bancaire",
        "Frais de dossier bancaire"
      ],
      [
        "b18_pertes_de_change",
        "Pertes de change"
      ],
      [
        "b18_autres_commissions",
        "Autres commissions"
      ]
    ]
  ],
  [
    "b19",
    "Remboursements et dépenses exceptionnelles",
    "",
    [
      [
        "b19_remboursement_d_inscription",
        "Remboursement d'inscription"
      ],
      [
        "b19_remboursement_de_scolarite",
        "Remboursement de scolarité"
      ],
      [
        "b19_remboursement_de_trop_percu",
        "Remboursement de trop-perçu"
      ],
      [
        "b19_remboursement_de_prestation_annulee",
        "Remboursement de prestation annulée"
      ],
      [
        "b19_remboursement_de_frais_professionnel",
        "Remboursement de frais professionnels"
      ],
      [
        "b19_bourses_effectivement_versees_en_arg",
        "Bourses effectivement versées en argent"
      ],
      [
        "b19_dons_effectues",
        "Dons effectués"
      ],
      [
        "b19_indemnisations",
        "Indemnisations"
      ],
      [
        "b19_contentieux",
        "Contentieux"
      ],
      [
        "b19_depenses_d_urgence",
        "Dépenses d'urgence"
      ]
    ]
  ],
  [
    "b20",
    "Autres sorties de trésorerie",
    "cash_other",
    [
      [
        "b20_avances_sur_salaire",
        "Avances sur salaire"
      ],
      [
        "b20_avances_de_mission",
        "Avances de mission"
      ],
      [
        "b20_avances_aux_fournisseurs",
        "Avances aux fournisseurs"
      ],
      [
        "b20_depots_de_garantie",
        "Dépôts de garantie"
      ],
      [
        "b20_cautions_versees",
        "Cautions versées"
      ],
      [
        "b20_remboursement_du_capital_des_emprunt",
        "Remboursement du capital des emprunts"
      ],
      [
        "b20_remboursement_d_avances_du_proprieta",
        "Remboursement d'avances du propriétaire"
      ],
      [
        "b20_distribution_de_benefices",
        "Distribution de bénéfices"
      ],
      [
        "b20_retraits_du_proprietaire_selon_le_st",
        "Retraits du propriétaire selon le statut juridique"
      ],
      [
        "b20_remises_en_banque",
        "Remises en banque"
      ],
      [
        "b20_transferts_entre_comptes",
        "Transferts entre comptes"
      ],
      [
        "b20_reversement_des_fonds_collectes_pour",
        "Reversement des fonds collectés pour des tiers"
      ]
    ]
  ]
]

DEFAULT_FAMILY_CODES = frozenset(row[0] for row in DEFAULT_EXPENSE_FAMILIES)
