# Bilan de validation — 17 octobre 2026

Le projet est un prototype local de recherche documentaire français/arabe sur **la loi 103-12, édition BAM consolidée au 31 mars 2022**. Il permet de retrouver des preuves datées, puis éventuellement de les reformuler. La recherche extractive fonctionne ; la génération Qwen reste expérimentale et non validée.

## Ce qui a réellement été exécuté

| Parcours | Résultat observé | Preuve et portée |
| --- | --- | --- |
| Qualité du corpus | 197 articles par langue, soit 394 ; empreintes des deux PDF et du JSONL contrôlées | [Sources et extraction](../docs/SOURCES.md). Les textes et PDF restent locaux sous `data/`. |
| Suite logicielle finale | **125 tests réussis**, aucun ignoré, Python 3.11.9, 22,66 s | [Compte rendu logiciel](software_checks.json) et commandes ci-dessous, dont inférence réelle avec les encodeurs normalisé et historique. Un avertissement de dépréciation Starlette/httpx ; aucun échec. |
| Style, format, environnement | Ruff check et format réussis ; `pip check` sans dépendance cassée ; Compose config valide | Contrôles logiciels, pas mesures de pertinence juridique. |
| Package | Wheel final construit avec les dépendances de build déclarées ; installation isolée sans dépendances et import vérifiés | [Contrôle du wheel](packaging_smoke.json). Le lancement des commandes reste documenté depuis la racine du projet pour accéder aux fichiers `evaluation/`. Une réinstallation complète depuis le verrou seul n'a pas été testée. |
| API locale | HTTP réel : lecture article 34 FR/AR et refus d'une question sur le taux directeur actuel | [Rapport API](api_smoke.json), [script](../scripts/smoke_api.py). Serveur temporaire fermé. |
| API en conteneur | Image construite puis mêmes contrôles HTTP réussis sur le corpus réel ; utilisateur `rag` | [Rapport Docker](docker_smoke.json), [script](../scripts/smoke_docker.py). Moteur local BM25, réponse extractive ; conteneur temporaire supprimé. |
| Adaptateur OpenSearch | Cluster 3.9.0, client 3.2.0 ; **43 contrôles de recherche et 3 refus d'index incompatible réussis** | [Rapport OpenSearch](opensearch_smoke.json), [script](../scripts/smoke_opensearch.py). Contrats sur données synthétiques puis 394 articles / 728 passages réels ; BM25, k-NN, fusion, FR/AR, références multiples et provenance. |
| Génération Qwen | Quatre essais hétérogènes conservés, aucune réponse générée acceptée | [Rapport détaillé](ollama_smoke.json), [premier essai archivé](ollama_smoke_v1.json). Aucune mesure de fidélité générative établie. |

Le test OpenSearch valide l'adaptateur contre un serveur réel. Il ne valide pas une API configurée avec ce backend, ni une équivalence de classement avec le moteur local, ni un benchmark de pertinence OpenSearch. L'indexation du corpus a pris 69,05 s ; le service approchait 948 Mio sur sa limite de 1 Gio. Les index `p2-smoke-*` et le volume sont conservés ; le service lancé pour ce test a été arrêté. Aucun autre service n'a été arrêté.

Le Docker Desktop local a pu être démarré pendant cette livraison. Les premières expériences conservées mentionnent son indisponibilité **au moment de leur exécution** ; elles n'ont pas été réécrites pour masquer cet historique.

## Ce que disent les résultats de recherche

| Exécution | BM25 Recall@5 | Sémantique Recall@5 | Hybride Recall@5 |
| --- | ---: | ---: | ---: |
| [Premier test conservé](reference/RESULTATS.md) | 45 % | 50 % | 55 % |
| [Diagnostic après normalisation arabe](diagnostic-normalization/RESULTATS.md) | 45 % | 80 % | 85 % |

Le diagnostic retire le tatweel et certains caractères de présentation de l'entrée neuronale, avec normalisation NFKC. Les preuves originales restent inchangées et leurs positions sont conservées. La modification change aussi le découpage : l'écart observé n'isole pas un effet causal des seuls embeddings.

**Le second résultat est exploratoire.** Nous avons examiné le premier test avant de corriger le prétraitement, puis réutilisé les mêmes thèmes. Les seuils restent choisis sur développement, mais ces thèmes de test ne sont plus inconnus. Le test contient seulement huit thèmes, dont cinq répondables, déclinés dans quatre directions linguistiques corrélées. Les annotations ne sont pas arbitrées par un expert juridique indépendant.

85 % signifie que l'article annoté attendu apparaît parmi les cinq premiers articles pour 17 des 20 couples positifs question/langue-source. Ce n'est pas un taux de réponses correctes. L'hybride refuse 10 des 12 cas négatifs ; les deux autres illustrent la limite du filtre d'abstention.

## Pourquoi la génération reste expérimentale

Les deux questions génériques FR/AR du premier essai ont reçu une abstention structurée : les passages transmis ne contenaient pas la preuve nécessaire. Ces observations précèdent la dernière amélioration de la sélection du contexte et sont conservées telles quelles.

Dans les deux essais ciblant ensuite l'article 151, la question française a expiré après environ 180 secondes sans sortie fournisseur ; la question arabe a été refusée avant Qwen, car son chevauchement lexical était de 0,214 contre un seuil fixé à 0,25. Les validations Docker/OpenSearch avaient lieu en parallèle ; un effet des ressources est possible, sans causalité démontrée.

Ces essais n'ont pas de taux agrégé. Aucun énoncé généré accepté n'a pu faire l'objet d'une relecture de fidélité. Les tests logiciels vérifient les règles de citation et d'abstention ; ils ne remplacent pas cette évaluation humaine.

## Reproduire les vérifications

Depuis la racine du projet, sous PowerShell :

```powershell
$env:PYTHONUTF8 = '1'
$env:RAG_RUN_MODEL_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
docker compose config --quiet
.\.venv\Scripts\python.exe scripts/smoke_api.py
docker compose build api
.\.venv\Scripts\python.exe scripts/smoke_docker.py
```

Les tests d'inférence nécessitent le modèle déjà préparé localement. Sans cette variable, ces tests peuvent être ignorés et le nombre de tests exécutés diffère. Le test Docker nécessite le corpus préparé et le daemon actif.

Pour OpenSearch, avec le modèle déjà préparé :

```powershell
docker compose --profile search up -d opensearch
.\.venv\Scripts\python.exe scripts/smoke_opensearch.py --include-corpus --report outputs/my-smokes/opensearch.json
docker compose --profile search stop opensearch
```

Le script attend un serveur prêt ; suivre les [notes de déploiement](../docs/DEPLOYMENT.md). N'arrêter le service que si tu l'as démarré pour ce test et qu'aucun autre travail ne l'utilise. Le script ne supprime ni index ni service. Les scripts API/Docker mettent à jour leurs rapports ; sauvegarder les rapports de livraison avant une reproduction si l'on veut conserver ces observations.

La configuration CI Python 3.11/3.12 est fournie ; aucune exécution GitHub Actions de ce deuxième projet n'est revendiquée. Le dépôt est local, sans publication GitHub.

## Décider de la suite

Pour soutenir une affirmation de qualité, il faut constituer de nouveaux thèmes sans les utiliser pour corriger le système, faire vérifier les articles attendus, fixer les critères et seuils sur développement, puis mesurer les quatre directions linguistiques et analyser les erreurs. Pour la génération, il faut aussi relire des énoncés effectivement produits et leurs preuves, y compris les omissions et les inférences injustifiées.

Commence par le [guide en dix séances](../docs/GUIDE_PAS_A_PAS.md), puis confronte tes réponses au [protocole](../docs/PROTOCOL.md). Le résultat actuel se présente comme un prototype de recherche bilingue évalué avec transparence, sur une édition juridique précise.
