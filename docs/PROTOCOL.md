# Protocole d'évaluation — pilote bancaire bilingue

Version : `bam-10312-pilot-v1`. Protocole écrit le 16 octobre 2026 avant le premier rapport du jeu test. Il s'agit d'un protocole local, sans préenregistrement externe ni évaluation indépendante. L'amendement du 17 octobre ci-dessous décrit une analyse décidée après lecture du premier test ; il ne réécrit pas son statut.

## Question et périmètre

Le système retrouve-t-il le bon article de la loi 103-12, en français et en arabe, et sait-il refuser une question que le corpus ne permet pas de résoudre ?

Le corpus est l'édition consolidée au **31 mars 2022** de cette loi, publiée par Bank Al-Maghrib, dans ses deux langues. Une réponse sur cette édition n'atteste pas le droit applicable aujourd'hui. Le système ne couvre ni toutes les circulaires, ni les tarifs des banques, ni les décisions monétaires courantes.

Nous distinguons trois propriétés :

1. **Retrouver** : le bon article figure dans les résultats.
2. **Décider de répondre** : une règle accepte ou refuse les preuves disponibles.
3. **Répondre fidèlement** : toutes les propositions de la réponse sont effectivement soutenues par ces preuves.

Ce pilote mesure les deux premières. Une URL, un numéro d'article ou une citation textuelle valide ne suffit pas à mesurer la troisième. La fidélité sémantique d'une réponse générée doit être évaluée séparément, avec une grille et une relecture humaine.

## Questions et séparation

Le fichier versionné [questions.json](../evaluation/questions.json) contient des questions originales, sans passages copiés de Bank Al-Maghrib.

| Unité | Développement | Test | Total |
|---|---:|---:|---:|
| Thèmes positifs | 5 | 5 | 10 |
| Thèmes hors corpus | 3 | 3 | 6 |
| Couples question / langue de source | 32 | 32 | 64 |

Chaque thème a une formulation française et une formulation arabe. Chacune est recherchée dans les sources françaises puis arabes : FR→FR, AR→AR, FR→AR et AR→FR. Les quatre variantes restent dans le même split. Les 64 lignes représentent **16 thèmes**, et non 64 observations indépendantes.

Les cinq thèmes positifs de développement concernent les articles 1, 10, 16, 34 et 54. Les cinq thèmes de test concernent les articles 58, 150, 151, 155 et 157. Les questions ne donnent pas le numéro d'article au moteur. Une question positive a ici un article attendu ; le calcul accepte plusieurs articles attendus pour une future extension.

Les négatifs comprennent des sujets éloignés, des informations commerciales, des faits actuels, ainsi que deux pièges proches du corpus : le délai de traitement d'une réclamation et le minimum CET1 en octobre 2026. **Hors corpus** ne veut pas dire qu'aucun texte juridique n'existe sur le sujet. Cela signifie que les deux documents indexés ne suffisent pas à répondre à la question posée.

Les annotations ont été vérifiées sur les textes locaux de cette édition. Elles n'ont pas fait l'objet d'une adjudication par un juriste externe. La petite taille du pilote, le nombre limité de thèmes et les questions rédigées avec connaissance du corpus limitent sa représentativité.

## Comparaison des moteurs

Comparer BM25, semantic et hybrid sur le même corpus, le même filtre de langue et le même découpage. Le mode hybride fusionne les rangs par RRF ; son score n'est pas une probabilité de vérité.

Pour une comparaison des trois modes, charger l'encodeur puis construire **une seule instance** du moteur. BM25 utilise alors les mêmes passages que les deux autres modes. Un BM25 exécuté sans encodeur reste une baseline autonome utile, mais son découpage en caractères diffère : ne pas attribuer entièrement au modèle une différence observée entre ces deux configurations.

Fixer avant test :

- édition du corpus et SHA-256 des PDF ;
- version et révision du modèle, paramètres de découpage et empreinte de l'index ;
- constante RRF, nombre de candidats et `top_k=5` ;
- questions, groupes et split ;
- politique d'abstention [abstention_policy.json](../evaluation/abstention_policy.json).

Le chargement de modèle et la construction d'index ne font pas partie de la latence de recherche. Le premier appel peut néanmoins chauffer le runtime ; conserver le contexte matériel avant de comparer des temps.

## Choix des seuils

Choisir les seuils **uniquement sur développement**, puis enregistrer les valeurs dans `evaluation/abstention_policy.json` avant toute mesure de test. Ce fichier doit conserver les groupes de développement, l'empreinte des questions et la règle de choix.

Le score lexical, le cosinus et le RRF ont des échelles différentes. La règle utilise des indices adaptés au mode, ainsi qu'une garde sur les demandes d'information actuelle hors de cette édition. Elle ne transforme pas un score RRF en confiance.

Une calibration peut sélectionner la meilleure balanced accuracy sur développement ; les égalités doivent suivre une convention déterministe annoncée dans le fichier de politique. La balanced accuracy moyenne le taux de réponse sur les positifs et le taux d'abstention sur les négatifs. Les quatre directions d'un thème restent liées : il ne faut pas gonfler artificiellement la taille de l'échantillon.

Après test, toute modification de seuil, de formulation, de modèle ou de découpage devient une nouvelle expérience. Les résultats du même jeu test deviennent exploratoires. Une amélioration confirmatoire nécessite alors de nouveaux thèmes tenus à l'écart.

## Amendement du 17 octobre 2026 — diagnostic après consultation du test

La première exécution est conservée dans [reports/reference](../reports/reference/RESULTATS.md), avec ses JSON et sa [politique utilisée](../reports/reference/policy_used.json). Ces fichiers décrivent le système avant le correctif ; ils ne doivent pas être remplacés par les nouveaux scores.

La lecture des erreurs test a révélé un défaut de préparation des entrées arabes : les allongements typographiques du PDF, ou **tatweel/kashidas** (`ـ`), fragmentaient les mots et consommaient des tokens. La normalisation lexicale les retirait déjà, mais pas le chemin neuronal initial. Le diagnostic est donc issu du test, même si le défaut technique est explicable indépendamment.

Le correctif normalise les entrées du tokenizer et de l'encodeur par NFKC, retire les tatweels et les caractères de formatage, et conserve une correspondance vers les offsets du texte original. Le corpus cité n'est pas réécrit. Le marqueur de préparation `nfkc-no-tatweel-bidi-v1` entre dans les métadonnées et l'empreinte de l'index. Les poids du modèle restent les mêmes ; le prétraitement et le découpage peuvent changer.

La commande `--preprocessing raw` et la politique `evaluation/abstention_policy_v1.json` permettent de reproduire la configuration initiale sans remplacer ses rapports. La nouvelle configuration utilise `--preprocessing normalized` ; elle est recalibrée uniquement sur les groupes de développement. Ses résultats sur les **mêmes questions test déjà consultées** sont enregistrés séparément dans `reports/diagnostic-normalization` et qualifiés **EXPLORATOIRES APRÈS CONSULTATION DU TEST**, avec le marqueur `--analysis-status exploratory_after_initial_test`. Une calibration sur développement ne rend pas de nouveau inédit un test qui a servi au diagnostic.

Cette comparaison étudie l'effet de la chaîne de normalisation sur ce pilote. Elle ne fournit pas une nouvelle validation tenue à l'écart. Les changements de découpage, les nouvelles empreintes et les politiques doivent rester visibles ; le gain ne peut pas être attribué à un nouvel entraînement du modèle. Une confirmation de généralisation exige de nouveaux thèmes, rédigés et annotés indépendamment avant toute consultation.

## Métriques

Dédupliquer les résultats par article avant de compter les rangs. La langue source fait partie du contexte : l'article 34 français est attendu lorsque la source demandée est française, son équivalent arabe lorsque la source demandée est arabe. Un passage retourné dans la mauvaise langue est une erreur d'interface, pas un succès.

Pour chaque question positive :

- **Recall@5** = nombre d'articles attendus retrouvés parmi les cinq premiers articles distincts / nombre d'articles attendus ;
- **MRR@5** = inverse du rang du premier article pertinent, ou zéro s'il n'est pas retrouvé.

Retrouver l'article ne prouve pas que le passage retenu contient toutes les conditions, exceptions ou propositions nécessaires à la question. Une métrique de couverture des preuves ou une relecture adaptée est nécessaire pour mesurer cette propriété.

Avec un seul article attendu, Recall@5 est une réussite binaire. Les négatifs n'ont pas de pertinence article attendue ; ils sont exclus du calcul de rappel et de MRR.

Pour la décision d'abstention :

- **positive_answer_rate** : part des questions positives acceptées ;
- **negative_abstention_rate** : part des questions hors corpus refusées ;
- **coverage** : part de toutes les questions acceptées ;
- **answerability_precision** : part de questions positives parmi les questions acceptées ;
- **answerability_balanced_accuracy** : moyenne des deux premiers taux.

Une règle qui refuse tout obtient 100 % d'abstention sur les négatifs mais 0 % de réponse sur les positifs. Une règle qui répond toujours présente le défaut inverse. Aucun de ces taux ne prouve que le texte d'une réponse acceptée est correct.

Rapporter chaque direction séparément et leur moyenne macro, puis les erreurs par thème. Le rapport global pondère les lignes, la macro pondère les directions également. Ne pas présenter d'intervalles binomiaux calculés en supposant indépendantes les traductions. Ce pilote ne fournit pas d'intervalle de généralisation.

## Lecture des résultats et critères

Le jalon est réussi si les résultats sont reproductibles, les erreurs visibles, la provenance vérifiable et les limites respectées. **Aucun seuil universel du type « 90 % suffit » n'autorise un usage juridique.**

Pour décider d'une amélioration technique :

1. Vérifier que le corpus couvre effectivement la question et que l'article attendu est bien annoté.
2. Comparer rappel et MRR dans les quatre directions. Un gain monolingue qui détruit l'arabe ou le croisement de langues mérite d'être signalé.
3. Examiner les faux positifs sur les négatifs proches du corpus ; un refus sur un sujet éloigné est insuffisant.
4. Lire les questions positives refusées pour mesurer le prix de la prudence.
5. Inspecter les articles manqués et le passage sélectionné avant de changer un paramètre.

Une amélioration de moyenne sur cinq thèmes test reste une observation descriptive. Ajouter ensuite des questions rédigées à l'aveugle par d'autres personnes, des variantes dialectales, des questions multi-articles et de vrais cas ambigus.

## Génération optionnelle et déploiement

Le mode extractif retourne des preuves du corpus. Le mode Ollama ajoute une reformulation locale. La vérification automatique des citations empêche certains identifiants ou extraits inventés ; elle ne détecte pas toutes les omissions, inférences ou paraphrases fausses.

Une validation humaine distincte doit noter au minimum : proposition soutenue, proposition non soutenue, contradiction, citation adéquate et abstention nécessaire. Ne pas publier un « taux de fidélité » sans cette annotation.

Les tests unitaires utilisent des textes synthétiques. Leurs scores ne mesurent pas les performances sur la loi bancaire. Les PDF, textes extraits, embeddings et index demeurent locaux dans `data/` ; aucun droit de redistribution du corpus n'est déduit du seul accès public.


## Extension du 18 octobre 2026 — nouveaux thèmes internes

Le [protocole V2](CHALLENGE_V2.md), figé avant sa première exécution, décrit vingt nouveaux thèmes avec quatre directions linguistiques chacun. Il transfère les seuils du développement d'origine sans les recalibrer sur ces questions. Un audit interne des annotations et un manifeste d'empreintes précèdent l'exécution. Cette extension ne réécrit pas le statut exploratoire du diagnostic précédent et ne constitue pas une adjudication juridique externe.

Les [résultats complets](../reports/challenge-v2/RESULTATS.md), les [erreurs](../reports/challenge-v2/ERREURS.md) et le [bilan de cette étape](../reports/extension-v2/BILAN.md) sont séparés. Une modification motivée par ces nouvelles erreurs rendrait une nouvelle exécution du V2 exploratoire.
