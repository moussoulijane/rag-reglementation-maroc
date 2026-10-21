# Ton guide de développement — assistant bancaire français / arabe

Ce guide te permet de reprendre le projet comme son développeur. Tu dois pouvoir suivre une question depuis le PDF jusqu'à la preuve affichée, expliquer une erreur et refaire l'expérience.

Le projet porte sur **la loi 103-12, édition consolidée au 31 mars 2022**, en français et en arabe, publiée par Bank Al-Maghrib. Ce périmètre est volontairement limité. Il ne constitue pas une base complète de la réglementation bancaire marocaine actuelle.

Consacre dix séances au guide. Pour chacune, lis le code indiqué, exécute l'expérience, puis réponds aux questions avant de lire la correction. Garde un petit journal de ce que tu as compris et de ce qui te surprend.

## Séance 1 — Comprendre ce que nous construisons

**Objectif :** expliquer le produit sans réciter « RAG ».

Une personne pose une question. Le programme cherche des passages dans une collection connue, conserve leur provenance puis affiche les preuves. Un générateur local peut ensuite les reformuler. Le modèle n'est pas chargé de deviner la réglementation.

Le chemin est :

```text
PDF officiels datés
    ↓ téléchargement + empreinte SHA-256
articles avec langue, pages et provenance
    ↓ découpage en passages
BM25 / embeddings / fusion des rangs
    ↓ sélection de preuves + décision d'abstention
extraits vérifiables ou reformulation locale
    ↓
question, preuves, édition, limites
```

Le mode par défaut est une **baseline de recherche et d'extraction**, utilisable sans LLM. Le mode génératif est optionnel. Cette séparation permet de comprendre si une erreur vient de la recherche ou de la rédaction.

Ouvre [ARCHITECTURE.md](ARCHITECTURE.md), puis [models.py](../src/rag_reglementation_maroc/models.py). Repère :

- `Article` : un article original, sa langue et sa provenance ;
- `Chunk` : un passage, avec ses positions dans le texte de l'article ;
- `SearchHit` : un passage retrouvé, son article et ses scores.

**Exercice.** Pourquoi le champ `article_id="34"` ne suffit-il pas à identifier une preuve ?

**Correction.** Le numéro se répète entre langues, documents et éditions. Un identifiant source le rattache à une version ; l'URL, la date, les pages et l'empreinte permettent de contrôler ce rattachement. La page PDF est numérotée à partir de 1, même si la page imprimée porte un autre numéro.

**À savoir expliquer en entretien.** « Je commence par retrouver une source datée et vérifiable. La génération est une étape supplémentaire, avec ses propres erreurs. »

## Séance 2 — Installer et reproduire la base

**Objectif :** comprendre le rôle de Python, du package et de l'environnement.

Après avoir cloné le dépôt, ouvre PowerShell dans son dossier. Depuis le dossier parent :

```powershell
Set-Location .\rag-reglementation-maroc
```

Pour une installation neuve :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\rag-maroc.exe --help
```

Si `.venv` existe déjà et fonctionne, garde-le. L'appel explicite à `.venv\Scripts\python.exe` évite de dépendre de l'activation PowerShell. `-e` rend le package éditable : une modification de `src/` est utilisée sans réinstallation complète.

Lis [pyproject.toml](../pyproject.toml). Le fichier [requirements.lock](../requirements.lock) fige aussi les dépendances transitives de l'environnement préparé. Ce verrou est fourni pour reproduction ; une réinstallation complète à partir de lui n'a pas été exécutée séparément. Les dépendances principales couvrent la lecture PDF, BM25 et l'API. Les groupes optionnels ajoutent l'encodeur neuronal ou le client OpenSearch. Installer un client OpenSearch ne démarre pas un serveur.

Vérifie :

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Les tests emploient des petits documents synthétiques. Ils valident des comportements précis ; leurs résultats ne mesurent pas la qualité sur la loi bancaire.

**Exercice.** Une personne lance `python` et n'obtient pas les mêmes bibliothèques que toi. Que regardes-tu d'abord ?

**Correction.** Le chemin de l'interpréteur, sa version et l'environnement installé. Une dépendance absente n'est pas nécessairement un défaut du code de recherche.

## Séance 3 — Passer d'un PDF à des articles fiables

**Objectif :** traiter le corpus comme une donnée contrôlée.

Lis [catalog.py](../src/rag_reglementation_maroc/catalog.py) puis [ingestion.py](../src/rag_reglementation_maroc/ingestion.py).

```powershell
.\.venv\Scripts\rag-maroc.exe download
.\.venv\Scripts\rag-maroc.exe ingest
```

Le téléchargement reste une action explicite. L'API ne doit pas ouvrir un site ni télécharger un modèle parce qu'une question arrive.

Observe le dossier local `data/`. Les PDF, textes, articles et index y restent ignorés par Git. La possibilité de télécharger un document public n'accorde pas automatiquement un droit de redistribution.

Une empreinte SHA-256 décrit exactement les octets d'un fichier. Si le PDF change, son empreinte change. Elle ne prouve pas à elle seule que le contenu juridique est juste : le catalogue et l'origine du téléchargement restent nécessaires.

L'ingestion ne doit pas seulement « trouver du texte ». Elle vérifie l'ordre et le nombre d'articles, les pages et la provenance. L'édition attendue contient 197 articles par langue : 1 à 196, plus 19bis.

Les difficultés sont concrètes :

- les notes de bas de page peuvent se coller aux numéros ;
- les en-têtes et pieds de page se répètent ;
- l'arabe comporte des caractères et espacements spécifiques ;
- l'ordre visuel d'un PDF n'est pas toujours son ordre de lecture extrait.

**Exercice.** Si une expression régulière confond « article 34 » suivi d'un appel de note avec « article 348 », pourquoi ne faut-il pas simplement accepter le résultat ?

**Correction.** Tu construirais un index dont les identifiants sont faux. Un contrôle de séquence et de cardinalité détecte cette anomalie avant qu'elle devienne une fausse citation.

**Expérience.** Lis le rapport de qualité produit par l'ingestion. Choisis un article dans chaque langue et vérifie ses pages dans le PDF. Ne remplace pas une inspection de texte par un simple nombre de lignes.

## Séance 4 — Comprendre BM25 et les langues

**Objectif :** disposer d'une baseline compréhensible.

Lis [text.py](../src/rag_reglementation_maroc/text.py) et [retrieval.py](../src/rag_reglementation_maroc/retrieval.py).

BM25 classe les passages à partir des mots de la question. Un terme rare apporte généralement plus d'information qu'un terme présent partout. La fréquence dans un passage aide, mais avec saturation ; la longueur du passage est aussi prise en compte.

Ce moteur n'apprend pas automatiquement que deux mots de langues différentes ont le même sens. Une question française recherchée uniquement dans les sources arabes constitue donc un test difficile pour une baseline lexicale.

La normalisation sert à la recherche : casse, accents et variantes de caractères. Le texte cité reste le texte original extrait. Ne normalise pas une preuve au point de ne plus pouvoir la retrouver dans la source.

Lance une première question :

```powershell
.\.venv\Scripts\rag-maroc.exe ask "Qui autorise une nouvelle banque à exercer au Maroc ?"
```

Compare ensuite les sources françaises et arabes :

```powershell
.\.venv\Scripts\rag-maroc.exe ask "Qui autorise une nouvelle banque à exercer au Maroc ?" --source-language fr --mode bm25
.\.venv\Scripts\rag-maroc.exe ask "Qui autorise une nouvelle banque à exercer au Maroc ?" --source-language ar --mode bm25
```

Lis les options exactes disponibles :

```powershell
.\.venv\Scripts\rag-maroc.exe ask --help
```

Utilise le filtre de **langue source** pour distinguer la langue de ta question de celle du document recherché. Le filtre n'est pas une traduction.

**Exercice.** Si tu demandes directement « article 34 », le succès du moteur démontre-t-il qu'il comprend la question réglementaire ?

**Correction.** Non. La recherche explicite par numéro est utile, mais elle résout un problème beaucoup plus simple. Le benchmark évite de donner ce numéro dans ses questions positives.

**Expérience.** Compare une question contenant « agrément » avec une paraphrase utilisant « autorisation de commencer l'activité ». Observe la différence de rang et le passage affiché.

## Séance 5 — Embeddings et découpage

**Objectif :** comprendre ce qu'ajoute la recherche sémantique.

Lis [embeddings.py](../src/rag_reglementation_maroc/embeddings.py) et [chunking.py](../src/rag_reglementation_maroc/chunking.py).

Un embedding représente un texte par un vecteur numérique. Ici, un modèle multilingue MiniLM produit 384 coordonnées. Le cosinus compare la direction des vecteurs. Une proximité peut aider à retrouver une paraphrase ou un passage d'une autre langue ; elle ne prouve pas que le passage répond à tous les détails de la question.

Prépare le modèle de façon explicite :

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,neural]"
.\.venv\Scripts\rag-maroc.exe prepare-model
```

Une fois le modèle préparé :

```powershell
.\.venv\Scripts\rag-maroc.exe ask "من يمنح الاعتماد لبنك جديد؟" --source-language fr --mode semantic --encoder multilingual
```

Le nom et la révision du modèle sont fixés dans le code. Conserver la révision et les empreintes évite qu'un téléchargement ultérieur change silencieusement l'expérience.

Le modèle est limité à 128 tokens. Un token est une unité du tokenizer ; ce n'est ni un mot ni un caractère. Le découpage neuronal vise 110 tokens avec un recouvrement de 20, en gardant les offsets dans le texte original. La marge laisse de la place aux tokens spéciaux.

Sans encodeur, le projet utilise un découpage en caractères pour la baseline. Pour comparer BM25, semantic et hybrid équitablement, charge le même encodeur et utilise une seule instance d'index pour les trois modes.

**Un vrai diagnostic du projet.** La première mesure a montré une très mauvaise récupération vers les sources arabes. En lisant le texte extrait, nous avons trouvé des allongements typographiques `ـ` répétés au milieu des mots. BM25 les supprimait pour chercher ; le chemin neuronal initial les envoyait au tokenizer. Ils fragmentaient donc l'entrée et utilisaient sa petite capacité de tokens.

Le correctif applique NFKC puis retire les tatweels et les caractères de formatage avant la tokenisation et l'encodage. Une table relie les caractères normalisés aux positions du texte original : les preuves affichées restent des extraits de la source, avec leurs vrais offsets. Le marqueur `nfkc-no-tatweel-bidi-v1` modifie les métadonnées et l'empreinte du cache.

Ce défaut a été identifié **après lecture du test initial**. La première mesure reste dans `reports/reference/`. La nouvelle mesure, dans `reports/diagnostic-normalization/`, est exploratoire : une amélioration sur ces questions déjà vues ne devient pas une validation indépendante. C'est aussi une leçon de développement : changer la préparation des données peut compter davantage que changer de modèle.

**Exercice.** Pourquoi ne pas encoder directement les articles longs puis faire confiance au résultat ?

**Correction.** Un modèle peut tronquer silencieusement une partie du texte. La preuve utile pourrait disparaître. Le projet contrôle les limites et les offsets ; une question trop longue doit être traitée explicitement.

**Expérience.** Pose une question arabe sur un article français. Compare lexical et sémantique avec la même langue source. Note un succès et un échec au lieu de supposer que « sémantique » signifie toujours meilleur.

## Séance 6 — Fusion RRF et choix des preuves

**Objectif :** expliquer l'hybride sans additionner des scores incompatibles.

Le score BM25 et le cosinus n'ont pas la même unité. La fusion RRF utilise les positions dans chaque classement :

```text
score RRF(passage) = somme de 1 / (60 + rang_du_passage)
```

Un passage bien classé par les deux méthodes reçoit deux contributions. Un passage présent dans une seule liste conserve une contribution. Cette valeur sert à ordonner, pas à donner un pourcentage de confiance.

Lis `reciprocal_rank_fusion` dans [retrieval.py](../src/rag_reglementation_maroc/retrieval.py). Les paramètres comme le nombre de candidats et la constante 60 influencent le résultat. Ils doivent être conservés avec le rapport d'évaluation.

Les articles sont découpés en plusieurs passages. Le moteur puis l'évaluation dédupliquent par article : trois passages du même article ne doivent pas occuper trois succès dans un rappel par article.

Cette déduplication a aussi une limite : le passage retenu peut donner une règle tandis qu'une exception utile se trouve ailleurs dans le même article. Un Recall@5 parfait ne prouve donc pas que les preuves sélectionnées suffisent pour répondre à toutes les parties de la question.

**Exercice.** Deux listes classent A puis B, et B puis A. Qui gagne avec la formule ci-dessus ?

**Correction.** Ils sont ex æquo : chacun reçoit une contribution au rang 1 et une au rang 2. Le système doit départager les égalités de manière déterministe pour être reproductible.

**Expérience.** Cherche une question où les deux moteurs ne sont pas d'accord. Lis les preuves des deux côtés avant de conclure que l'hybride est meilleur. Une fusion peut aussi remonter une erreur partagée.

## Séance 7 — Répondre, citer et s'abstenir

**Objectif :** distinguer preuve disponible et réponse fiable.

Lis [answering.py](../src/rag_reglementation_maroc/answering.py). Commence en mode extractif. Une réponse doit permettre de retrouver la langue source, le numéro d'article, l'édition, les pages et le document.

La décision d'abstention est une règle explicite. Ses seuils sont choisis sur développement puis figés dans [abstention_policy.json](../evaluation/abstention_policy.json). Le score RRF n'est pas utilisé comme une probabilité juridique.

Teste trois familles de questions :

1. Une question couverte, par exemple sur l'autorisation d'exercer.
2. Une question proche mais dépendant d'une circulaire absente, par exemple un délai chiffré de traitement des réclamations.
3. Une information actuelle, par exemple le taux directeur du jour.

Le troisième cas ne peut pas être résolu honnêtement avec une édition de loi de 2022. Le deuxième est plus subtil : un article peut parler de réclamations sans donner le délai demandé.

Le mode Ollama reste optionnel, local et **expérimental**. Les [anciens échecs](../reports/ollama_smoke.json) restent conservés. Le [lot V3](../reports/generation-v3/RESULTATS.md) reprend six cas de développement déjà vus après des contrôles synthétiques de l'ordre du schéma : deux claims sont acceptés et quatre cas refusés, dont un avant le modèle. Deux [relectures internes concordantes](../reports/generation-v3/second_review.json) soutiennent les deux claims. La consultation arabe couvre seulement une partie de l'article : cela distingue le support de l'affirmation de la complétude de la réponse. Cela ne donne aucun taux global de fidélité, ni une validation générale du générateur.

Le timeout de chargement à froid a été traité en séparant explicitement le chargement de l'inférence. Avec Ollama déjà lancé et le modèle déjà installé, précharge-le avant la commande ou le démarrage de l'API :

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:11434/api/generate' -ContentType 'application/json' -Body '{"model":"qwen2.5:7b","keep_alive":"15m","stream":false}' -TimeoutSec 360
```

Attends sa fin. Aucun poids n'est téléchargé par cette commande. Aucun nouveau timeout n'a été observé dans le lot V3 ; cela ne garantit pas les performances d'autres requêtes. Les [notes de déploiement](DEPLOYMENT.md) expliquent les délais et le maintien en mémoire.

La commande suivante permet ensuite d'explorer l'adaptateur, sans garantie de réponse acceptée :

```powershell
.\.venv\Scripts\rag-maroc.exe ask "Que prévoit la loi pour la convention de compte ?" --source-language fr --mode hybrid --encoder multilingual --generator ollama
```

Consulte `ask --help` pour ses options. Un modèle comme Qwen 2.5 7B requiert Ollama et un modèle déjà disponible sur ta machine ; sa présence ne doit pas être supposée chez un autre utilisateur.

La génération doit rester rattachée aux preuves proposées. Le programme contrôle les citations et les extraits qu'il peut vérifier. **Une citation valide ne garantit pas que toute la reformulation est fidèle.** Le champ `semantic_faithfulness` de l'API reste `not_evaluated`. Les verdicts documentaires par claim des essais particuliers sont conservés dans des rapports séparés ; ils ne s'étendent pas aux autres réponses.

**Exercice.** Le modèle cite le bon article, mais ajoute une exception absente de cet article. Le contrôle de numéro de citation suffit-il ?

**Correction.** Non. Il faut vérifier les propositions de la réponse, pas seulement l'existence de la référence. La génération, l'abstention et la recherche demandent des évaluations distinctes.

**Expérience.** Compare la preuve brute à une reformulation générée. Souligne chaque proposition de cette reformulation et indique quelle phrase de la preuve la soutient. Une proposition sans support est une erreur, même si le reste est convaincant.

## Séance 8 — Mesurer sans se raconter une histoire

**Objectif :** reproduire un résultat et comprendre ses limites.

Lis [PROTOCOL.md](PROTOCOL.md), [questions.json](../evaluation/questions.json) et [evaluation.py](../src/rag_reglementation_maroc/evaluation.py).

Le pilote contient 16 thèmes, chacun décliné en quatre couples de langues : 64 lignes. Développement et test contiennent chacun 5 thèmes positifs et 3 thèmes hors corpus. Les traductions d'un même thème restent groupées.

Lance d'abord l'aide :

```powershell
.\.venv\Scripts\rag-maroc.exe evaluate --help
```

Pour les trois moteurs sur le même index :

```powershell
.\.venv\Scripts\rag-maroc.exe evaluate --split dev --modes bm25 semantic hybrid --encoder multilingual --preprocessing normalized --output-dir outputs/my-evaluation/development
.\.venv\Scripts\rag-maroc.exe calibrate --encoder multilingual --preprocessing normalized --output outputs/my-evaluation/policy.json
.\.venv\Scripts\rag-maroc.exe evaluate --split test --modes bm25 semantic hybrid --encoder multilingual --preprocessing normalized --policy outputs/my-evaluation/policy.json --analysis-status exploratory_after_initial_test --output-dir outputs/my-evaluation/test
```

Pour reproduire la configuration du premier test, avant normalisation, sans écraser ses rapports :

```powershell
.\.venv\Scripts\rag-maroc.exe evaluate --encoder multilingual --preprocessing raw --split test --modes bm25 semantic hybrid --policy evaluation/abstention_policy_v1.json --output-dir outputs/reproduce-v1
```

La politique V1 conservée correspond à cette configuration. Le mode `normalized`, devenu le défaut, utilise une autre empreinte d'index et sa propre calibration. La variable `RAG_PREPROCESSING` configure le même choix pour le service.

Ces commandes écrivent tes propres sorties dans `outputs/` et préservent les rapports de référence. Comme le jeu test a déjà été consulté pour diagnostiquer le défaut arabe, ta reproduction sur ce jeu reste une réplication ou une analyse exploratoire, même si tu recalibres seulement sur développement. Ne relance pas la calibration après avoir lu le test pour faire monter ses scores. Pour une baseline sans téléchargement neuronal :

```powershell
.\.venv\Scripts\rag-maroc.exe evaluate --split dev --modes bm25 --encoder none --output-dir outputs/my-evaluation/baseline
```

Exécute le développement pour choisir la politique, puis le test avec cette politique figée. Le rapport doit permettre de retrouver la version des questions, le modèle et le découpage. Les commandes exactes et les résultats de la livraison figurent dans le README.

Pour une question dont le bon article est en position 3 :

- Recall@5 vaut 1 ;
- MRR@5 vaut 1/3 ;
- si le bon article est absent des cinq premiers, les deux valent 0.

Ces scores ne portent que sur les questions positives. Les négatifs évaluent la décision d'abstention.

Lis ensemble le taux de réponse sur les positifs et le taux de refus sur les négatifs. Refuser toutes les questions est une mauvaise solution, même avec un taux de refus de 100 % sur les négatifs.

**Exercice.** Une amélioration de 4 points sur 64 lignes représente-t-elle forcément plusieurs nouveaux cas indépendants résolus ?

**Correction.** Non. Les quatre lignes d'un thème partagent son contenu. Une seule idée mieux traitée peut faire monter plusieurs lignes. Le pilote rapporte des observations descriptives, sans prétendre mesurer une précision juridique générale.

**Ton travail de développeur.** Choisis une erreur test. Classe-la : corpus incomplet, annotation, extraction, découpage, récupération, abstention ou génération. Écris l'hypothèse avant de modifier le code. Après consultation du test, conserve l'expérience suivante comme exploratoire ou prépare de nouveaux thèmes test.

### Prolonger avec les nouveaux thèmes V2

L'[atelier pratique V2](ATELIER_EVALUATION_V2.md) suit la première exécution sur 20 nouveaux thèmes, après audit et gel du code, de l'index, des questions et de la politique existante. Lis le [protocole figé](CHALLENGE_V2.md), le [manifeste](../evaluation/challenge_v2_manifest.json), les [résultats](../reports/challenge-v2/RESULTATS.md) et les [erreurs](../reports/challenge-v2/ERREURS.md).

La méthode sémantique retrouve l'article attendu dans 43/48 couples positifs, mais accepte 12/32 couples hors corpus. L'hybride en retrouve 42/48 et accepte 15/32 hors corpus. Le problème devient clair : un passage proche peut ne pas donner le chiffre, le délai ou le détail technique demandé. L'hybride ne gagne pas sur tous les critères.

Ces couples représentent 12 thèmes positifs et 8 négatifs déclinés en quatre directions liées. Les thèmes diffèrent du premier pilote ; comparer directement leurs pourcentages ne mesure pas un gain causal. Le [bilan de l'extension](../reports/extension-v2/BILAN.md) distingue cette évaluation des essais génératifs sur des cas de développement connus.

## Séance 9 — API, OpenSearch et Docker

**Objectif :** comprendre ce qui change quand le code devient un service.

Lis [api.py](../src/rag_reglementation_maroc/api.py) et [opensearch_backend.py](../src/rag_reglementation_maroc/opensearch_backend.py).

```powershell
.\.venv\Scripts\rag-maroc.exe serve
```

Ouvre la documentation interactive à l'adresse affichée dans le terminal, généralement `http://127.0.0.1:8000/docs`.

- `/health` indique que le processus répond ;
- `/ready` indique si les ressources requises sont prêtes ;
- `/search` retourne des preuves classées ;
- `/ask` applique la politique de réponse.

Un serveur vivant peut ne pas être prêt : corpus absent, index incompatible ou modèle non préparé. Le service doit signaler cette situation, sans inventer de résultats.

OpenSearch est un backend optionnel. Il ne devient pas nécessaire parce que le projet parle de RAG. Le moteur local suffit pour comprendre le fonctionnement et étudier ce petit corpus. Le backend distant permet ensuite de travailler les mappings, l'indexation, les requêtes et les différences de classement.

Au 17 octobre, l'API HTTP locale et un conteneur Docker construit, exécuté avec l'utilisateur non-root `rag`, ont réellement passé les vérifications français/arabe sur l'article 34 et le refus d'une demande d'information actuelle. L'adaptateur OpenSearch a également été testé contre un vrai cluster sur fixtures et corpus, dans les trois modes de recherche. Ce test n'a pas exécuté l'API avec OpenSearch et ne mesure pas sa pertinence.

Ces vérifications d'intégration datent du 17 octobre ; Docker n'a pas été rejoué le 18. Lis le [bilan de validation historique](../reports/VALIDATION.md), [smoke_api.py](../scripts/smoke_api.py), [smoke_docker.py](../scripts/smoke_docker.py) et [smoke_opensearch.py](../scripts/smoke_opensearch.py). Un test d'intégration vérifie que les composants communiquent dans des scénarios précis ; il ne suffit pas pour conclure que toutes les réponses sont bonnes.

**Exercice.** Si les tests locaux passent et Docker ne démarre pas, le moteur est-il forcément faux ?

**Correction.** Non. Le daemon, les images, les volumes, les ports et les paramètres du backend constituent une autre couche. Il faut diagnostiquer cette couche et indiquer honnêtement ce qui a été validé.

**Expérience.** Prépare le corpus avant le démarrage, consulte `/ready`, pose une question, puis suis l'identifiant d'article de la réponse jusqu'au fichier source. Arrête le service avec Ctrl+C.

## Séance 10 — Présenter le projet et savoir le défendre

**Objectif :** devenir capable d'expliquer tes décisions et leurs conséquences.

Avant une publication GitHub, inspecte le statut :

```powershell
git status --short
git check-ignore data
git diff --check
```

Vérifie que `.venv/`, les PDF, les textes extraits, les caches et les secrets ne sont pas suivis. Le code, les questions originales, le protocole, les tests et les résultats agrégés peuvent être présentés en distinguant leurs droits.

La licence du code ne couvre pas automatiquement les documents de Bank Al-Maghrib ni les modèles externes. Le projet conserve l'attribution et les liens de provenance. N'ajoute pas un PDF au dépôt pour rendre la démonstration « plus pratique » sans vérifier ses conditions.

Explique la valeur concrète :

> Un assistant bilingue sur un corpus bancaire daté, avec provenance par article, comparaison lexicale / sémantique / hybride et étude des abstentions.

Prépare cinq explications :

1. Pourquoi commencer avec une seule loi datée plutôt qu'un corpus immense ?
2. Comment sais-tu qu'une citation appartient réellement au document utilisé ?
3. Pourquoi une recherche française dans des documents arabes mérite-t-elle une mesure séparée ?
4. Comment empêches-tu le choix d'un seuil sur les résultats test ?
5. Quelle erreur un bon rappel peut-il laisser passer dans une réponse générée ?

**Corrections attendues.** Le périmètre facilite la vérification ; les identifiants, offsets et empreintes rattachent les preuves ; le croisement de langues teste une difficulté distincte ; les groupes et la politique figée séparent développement et test ; une récupération correcte ne garantit pas une paraphrase fidèle.

**Pour la suite.** La priorité est d'obtenir davantage de questions indépendantes, une annotation humaine des réponses générées et une procédure d'actualisation du corpus. Ajouter un nouveau modèle sans comprendre les erreurs actuelles apporte moins d'information.

## Repères pour reprendre le code

| Si tu veux comprendre… | Lis d'abord… |
|---|---|
| Les sources, versions et téléchargements | `catalog.py`, `ingestion.py` |
| Ce qu'est une preuve | `models.py` |
| Les mots et la normalisation | `text.py` |
| Le découpage et les limites du modèle | `chunking.py`, `embeddings.py` |
| BM25, cosinus et fusion | `retrieval.py` |
| Le backend distant | `opensearch_backend.py` |
| Les refus, citations et reformulations | `answering.py` |
| Les mesures et les splits | `evaluation.py`, `PROTOCOL.md` |
| L'entrée terminal et l'entrée HTTP | `cli.py`, `api.py` |

À la fin, tu dois pouvoir modifier une hypothèse, annoncer ce qu'elle devrait changer, exécuter une vérification et expliquer le résultat, y compris lorsqu'il ne va pas dans le sens attendu.

## Après les dix séances — utiliser et comprendre Daftar

Daftar ajoute une interface française/arabe au moteur documentaire. Le navigateur envoie la question au même service ; il ne contient pas de réponses bancaires de démonstration. Le [brief de l'interface](INTERFACE.md) décrit ses états. Les [essais réels du 19 octobre](../reports/ui/VALIDATION.md) couvrent la consultation directe d'un article en FR/AR, le refus lié à l'édition 2022, l'état sans corpus, la copie d'empreinte, l'historique et l'affichage mobile. Ils ne constituent pas un audit complet d'accessibilité ; Ollama dans l'interface et les erreurs HTTP simulées n'ont pas été testés.

### Préparer le frontend et lancer le service

Depuis la racine du projet, avec Python, Node.js et npm disponibles :

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Set-Location frontend
npm ci
npm run build
Set-Location ..
```

La réinstallation éditable enregistre aussi la commande `rag-maroc-ui`. Le build TypeScript/Vite produit les fichiers de l'interface sous `src/rag_reglementation_ui/static`. Il ne reconstruit pas l'index bancaire et ne modifie pas le moteur gelé.

Après `download` et `ingest`, démarre la version de base :

```powershell
$env:RAG_ENCODER = 'none'
.\.venv\Scripts\rag-maroc-ui.exe --host 127.0.0.1 --port 8000
```

Ouvre `http://127.0.0.1:8000/`. Si le script n'est pas enregistré, l'équivalent est :

```powershell
.\.venv\Scripts\python.exe -m uvicorn rag_reglementation_ui.app:app --host 127.0.0.1 --port 8000
```

L'ancien `rag-maroc serve` lance l'API seule ; l'entrée UI ajoute la page et ses assets. Le même port ne peut pas être utilisé par deux serveurs en même temps. Arrête le serveur avec Ctrl+C lorsque tu as terminé.

Pour disposer des trois méthodes, prépare le modèle avec `prepare-model`, puis relance avec `RAG_ENCODER='multilingual'`. L'option Python `neural` doit déjà être installée. La reformulation conserve son préchargement Ollama séparé ; afficher une option configurée ne prouve pas que le modèle est disponible.

### Suivre une question dans le code

Lis [api.ts](../frontend/src/api.ts), [i18n.ts](../frontend/src/i18n.ts) puis [l'application UI Python](../src/rag_reglementation_ui/app.py).

1. `/ui-config` décrit les ressources chargées, les méthodes disponibles et les limites de formulaire.
2. Le formulaire conserve ta question et distingue langue de l'interface, langue de la question et langue des sources.
3. `POST /ask` reçoit le texte et les réglages explicites. L'option expérimentale désactivée envoie `generator="extractive"`.
4. Un succès affiche des citations réellement retournées, avec article, langue, édition et lien officiel.
5. Un refus affiche son motif compréhensible. Il ne fabrique pas une preuve pour remplir l'écran.

Les compteurs viennent de la configuration réelle. S'il n'y a pas de corpus chargé, l'interface ne doit pas afficher 394 articles comme donnée de secours. Le catalogue des PDF officiels peut rester consultable sans prétendre que ces documents sont déjà indexés.

### Expériences à réaliser

- Pose une question précise en français, puis en arabe ; compare la langue de la question et celle des preuves.
- Passe l'interface en arabe sans traduire le texte déjà saisi. Les citations conservent leur propre sens de lecture.
- Demande une information actuelle : lis le motif lié à l'édition 2022 au lieu d'interpréter ce refus comme une réponse juridique.
- Désactive l'encodeur au prochain lancement : les méthodes par sens doivent devenir indisponibles.
- Interromps la connexion au service, garde une question saisie puis rétablis-la. Une erreur ne doit pas effacer ton travail. L'indicateur réseau du navigateur n'interdit pas à lui seul l'accès à un serveur local.
- Ouvre une citation dans le PDF : les pages indiquées couvrent l'article, sans garantir la page exacte du passage.

**Exercice.** Pourquoi la présence du bouton « Reformulation expérimentale » ne garantit-elle pas qu'une réponse générée arrivera ?

**Correction.** `/ui-config` décrit une configuration. Il ne lance aucune sonde Ollama et n'atteste pas que le modèle est chargé. La requête peut encore être refusée, échouer ou manquer de preuve. Une citation affichée n'établit toujours pas la fidélité de chaque proposition.

**Exercice.** Pourquoi ne pas afficher les scores du moteur comme un pourcentage de fiabilité dans l'interface ?

**Correction.** Ils servent à ordonner des passages. Les échelles diffèrent selon la méthode et ne mesurent ni la vérité juridique, ni la disponibilité de la réponse, ni la fidélité de la reformulation.


## Évolution du 21 octobre : assistant V3

Le [guide V3](GUIDE_ASSISTANT_V3.md) explique le nouveau profil réclamations/médiation, les décisions complètes ou partielles, les notes sourcées et le futur test réservé. Les expériences précédentes restent des références historiques.
