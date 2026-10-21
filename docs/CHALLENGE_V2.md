# Challenge V2 — nouveaux thèmes, confirmation prospective interne

Création : **18 octobre 2026, 22:15:47 UTC**. Édition du corpus : **31 mars 2022**. Critères finalisés le **18 octobre 2026 à 22:22:20 UTC**. Statut de ce document : **prêt au gel, audit interne clos avant toute exécution**. Le manifeste doit encore être créé avant le premier passage dans le moteur.

## Pourquoi un nouveau jeu

Les erreurs du premier test ont servi à diagnostiquer le défaut de normalisation arabe. Le diagnostic réalisé ensuite sur ce même test était donc exploratoire. Ce challenge introduit de nouveaux thèmes pour observer le système corrigé avec sa politique déjà calibrée, sans utiliser ces questions pour la choisir.

Les résultats historiques sont déjà connus de l'équipe. La rédaction de ces nouveaux thèmes repose sur la lecture directe des articles français et arabes du corpus local ; **aucune recherche classée ni sortie du moteur sur ces nouvelles questions n'a été consultée pour les rédiger ou les adapter**. Les vérifications de périmètre portent sur le texte source, pas sur ses classements.

Il s'agit d'une **confirmation prospective interne sur de nouveaux thèmes après gel**, non d'une validation externe ou d'un préenregistrement indépendant. La création et l'audit assistés par des agents internes ne constituent pas une expertise juridique indépendante.

## Composition et absence de réutilisation

Le fichier [challenge_v2.json](../evaluation/challenge_v2.json) est compatible avec le schéma du pilote. Tous les cas ont `split="test"`.

| Unité | Positifs | Hors corpus | Total |
|---|---:|---:|---:|
| Thèmes | 12 | 8 | 20 |
| Couples question / langue source | 48 | 32 | 80 |
| Couples par direction | 12 | 8 | 20 |

Chaque thème comporte une formulation française et une formulation arabe, chacune dirigée vers les sources françaises puis arabes : FR→FR, AR→AR, FR→AR, AR→FR. Cela donne 40 formulations et 80 couples ; les traductions et répétitions de langue source **ne sont pas indépendantes**.

Les articles et questions anciens 1, 10, 16, 34, 54, 58, 150, 151, 155 et 157 sont exclus des annotations positives. Les nouveaux identifiants sont disjoints. Le domaine juridique, les auteurs internes et certaines familles de négatifs restent communs : de nouveaux thèmes ne constituent pas une nouvelle population indépendante. La nouveauté sémantique reste un objet d'audit : changer seulement le numéro, une langue ou quelques mots ne suffirait pas.

Les douze règles positives sont ciblées et vérifiables dans un seul article chacune. Aucune question positive ne donne ce numéro. Les références de page ci-dessous utilisent la numérotation du PDF, à partir de 1.

| Nouveau thème positif | Article attendu | Pages FR | Pages AR |
|---|---|---|---|
| Fonds des comptes de paiement en liquidation | 17 | 11–12 | 12 |
| Formes juridiques des établissements | 35 | 25–26 | 26 |
| Libération du capital ou versement de la dotation | 36 | 26 | 26 |
| Mentions d'identité dans les publications | 46 | 30 | 30 |
| Examen concurrentiel d'une concentration bancaire | 50 | 31 | 32 |
| Périodicité et bases des états de synthèse | 73 | 40–41 | 41 |
| Comités de gouvernance pour contrôle et risques | 78 | 42 | 43 |
| Vigilance interne contre le blanchiment et le financement du terrorisme | 97 | 48 | 49 |
| Commissaires aux comptes : nombre et exception | 99 | 49 | 49–50 |
| Fonds des comptes sans opération ni réclamation | 152 | 67 | 67–68 |
| Délai minimal de notification d'une sanction pécuniaire | 174 | 75 | 76 |
| Agences de notation et confidentialité | 180 | 77–78 | 77–78 |

Les négatifs demandent une information que ces deux documents ne suffisent pas à fournir. Ils ne sont ni une affirmation que la règle n'existe nulle part, ni une assertion que la proposition est fausse. Les trois cas proches d'une règle présente distinguent obligation générale et modalités absentes.

| Nouveau thème hors corpus | Justification de périmètre, sans extrait |
|---|---|
| Délai chiffré de notification d'un incident cyber | 77 : La loi pose un contrôle général des risques mais ne donne pas le délai horaire demandé pour un incident cyber. |
| Modèle détaillé d'un plan de redressement de crise | 79 : L'article permet d'exiger un plan et renvoie ses modalités ; le corpus ne fournit ni gabarit de fichier ni liste de champs. |
| Mensualité exacte d'une offre individuelle de prêt immobilier | Une offre individuelle suppose taux, frais, assurance et décision commerciale absents de cette loi. Les seuls nombres fournis ne déterminent pas le montant. |
| TVA actuelle sur les commissions bancaires | Il faut des dispositions fiscales actuelles, hors de la loi bancaire consolidée en 2022 ; aucun taux courant ne doit en être inventé. |
| Code BIC/SWIFT d'un établissement nommé | Le code d'une banque nommée relève d'un annuaire bancaire ou d'informations commerciales, pas des deux textes de la loi. |
| Récupération d'accès à une application bancaire | La récupération d'accès dépend du service et de la banque ; ce parcours utilisateur n'est pas fourni par le corpus légal. |
| Montant exact du plafond de garantie des dépôts | 138 : La loi indique que Bank Al-Maghrib fixe le plafond, sans en donner la valeur ; retrouver cette délégation ne répond pas au chiffre demandé. |
| Contrat technique d'une API d'open banking | Les deux textes ne fournissent aucune spécification des routes, paramètres ou contrats techniques d'une API d'open banking. |

`topic_annotations` conserve les justifications originales et, lorsque pertinent, les identifiants, pages, URL, édition et empreinte des sources FR/AR. Pour un négatif, `scope_article_ids` donne une référence de contexte, **jamais une réponse pertinente attendue** : `expected_article_ids` reste vide. Aucun passage BAM n'est reproduit dans ce jeu.

## Réglages et critères annoncés avant exécution

La politique de développement déjà choisie est transférée **sans recalibration sur ce challenge**. Le backend local, le modèle à révision fixée, la normalisation, le découpage, le corpus, les modes et `top_k=5` doivent correspondre au manifeste gelé. BM25, semantic et hybrid utilisent le même index pour une comparaison interne à ce jeu.

Rapporter, sans sélectionner uniquement les cellules favorables :

1. Recall@5 et MRR@5 par article sur les 48 couples positifs, dans les quatre directions, puis moyenne macro et score global.
2. Taux de questions positives acceptées et taux de négatifs refusés, couverture et précision d'answerability. Un négatif refusé ne compte pas comme un article correctement retrouvé.
3. Comptes bruts, groupes concernés et erreurs par thème. Les 80 lignes représentent 20 thèmes, dont seulement 12 positifs.
4. Latence de recherche avec son périmètre, en séparant le chargement du modèle et de l'index. Ne pas en déduire une latence générative.

Aucun seuil arbitraire du type « 90 % signifie prêt » n'est annoncé. Les critères sont descriptifs : couverture des règles nouvelles, différences entre directions et méthodes, et compromis entre réponse et abstention. Toute amélioration doit être discutée avec les exemples manqués ou indûment acceptés.

Les comparaisons avec les scores historiques portent sur des thèmes différents : elles ne sont pas une estimation causale d'un gain de modèle. Les traductions liées ne justifient pas des intervalles supposant 80 essais indépendants. Une éventuelle étude d'incertitude devrait respecter les groupes et le très faible nombre de thèmes.

**Les métriques par article ne prouvent ni que tous les éléments de réponse figurent dans les passages sélectionnés, ni la fidélité d'une génération.** Le challenge porte sur la récupération et la décision d'abstention ; il ne mesure pas la qualité de Qwen/Ollama.

## Audit, gel et journal d'intégrité

L'audit interne doit vérifier : suffisance de chaque article attendu dans les deux langues, fidélité des formulations FR/AR, caractère réellement hors corpus des négatifs, absence de paraphrase des thèmes anciens et absence de classement consulté pour ajuster ces questions. Il doit être clos avant tout passage dans le moteur.

Après correction éventuelle **avant exécution**, figer :

- les octets du fichier de questions et leur SHA-256, ainsi que la date UTC ;
- le rapport d'audit et son SHA-256 ;
- les anciens groupes de calibration et la politique transférée ;
- les fichiers source du programme, le corpus, la signature de l'index et les paramètres ;
- les critères de ce document et le statut `prospective_internal_challenge`.

Le manifeste local produit par `evaluation_manifest.create_manifest` relie ces ressources. L'exécution doit passer ce manifeste à `evaluate --evaluation-manifest` et écrire dans un dossier neuf, sans écraser les rapports précédents. Le manifeste est une trace locale vérifiable, pas une attestation infalsifiable ou un dépôt externe.

### Commandes après clôture de l'audit

Le rapport d'audit retenu est `evaluation/challenge_v2_audit.json`. Le script de gel écrit `evaluation/challenge_v2_manifest.json` et lie aussi les octets du présent protocole :

```powershell
.\.venv\Scripts\python.exe scripts/freeze_challenge.py
```

Ensuite seulement, exécuter le challenge avec les seuils existants, sans recalibration :

```powershell
.\.venv\Scripts\rag-maroc.exe evaluate --encoder multilingual --preprocessing normalized --split test --questions evaluation/challenge_v2.json --policy evaluation/abstention_policy.json --modes bm25 semantic hybrid --analysis-status prospective_internal_challenge --evaluation-manifest evaluation/challenge_v2_manifest.json --output-dir reports/challenge-v2
```

Le dossier de sortie doit être neuf. Le présent document ne contiendra ni résultats, ni SHA du manifeste : cela évite une dépendance circulaire avec le gel. La date UTC effective de gel est portée par le manifeste créé avant la première recherche. Après sa création, ce document et le fichier de questions restent inchangés ; résultats et ateliers sont documentés séparément.

### État final prêt au gel

- Fichier : `evaluation/challenge_v2.json`.
- SHA-256 final des questions : `727e29c69c48b581edb490ccec5ab735c3919ff69bf8fb52e1629ebd2862c802`.
- Date du premier candidat : 18 octobre 2026, 22:15:47 UTC.
- Audit : **passé**, voir [challenge_v2_audit.json](../evaluation/challenge_v2_audit.json). Les formulations FR de p06 et p09 ont été alignées sur les établissements de crédit ; le libellé AR du plan de crise a été clarifié. Les positifs, négatifs et références FR/AR ont été revus avant toute exécution. Aucun score n'a motivé ces corrections.
- Date effective de gel : portée par le manifeste créé **avant la première exécution**, avec les SHA des questions, du présent protocole, de l'audit, de la politique et du code. Ce document est désormais figé et ne sera pas complété après ce gel.

Après le gel, ne changer ni questions, ni annotations, ni seuils à partir de leurs scores. Si une erreur d'annotation est découverte après exécution, conserver l'original, documenter l'erratum et marquer toute réanalyse comme telle. Une nouvelle décision de réglage demande de nouveaux thèmes ultérieurs.
