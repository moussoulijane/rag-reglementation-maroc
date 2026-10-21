# Exécution locale, modèle et OpenSearch

État au **18 octobre 2026**. Les [intégrations du 17 octobre](../reports/VALIDATION.md) restent historiques : API HTTP locale, conteneur Docker et adaptateur OpenSearch testés, sans nouveau test Docker le 18. Le [bilan de l'extension](../reports/extension-v2/BILAN.md) distingue la nouvelle évaluation et les essais de génération toujours expérimentaux.

Le chemin minimal utilise Python 3.11 ou 3.12, le corpus local, BM25 et les extraits
vérifiables. Il ne nécessite ni Docker, ni serveur de génération, ni téléchargement
de modèle au démarrage de l'API. La recherche neuronale et OpenSearch sont des
options explicites.

## Modèle multilingue

Installer l'option `neural`, puis utiliser la commande `prepare-model` décrite par
`rag-maroc --help`. Les poids restent dans `data/models/`, ignoré par Git. Cette
préparation autorise le téléchargement ; le chargement normal reste local :

```python
from pathlib import Path
from rag_reglementation_maroc.embeddings import MultilingualEncoder

# Une seule fois, sur demande explicite :
encoder = MultilingualEncoder(Path("data/models"), allow_download=True)

# API et expériences suivantes, sans connexion requise :
encoder = MultilingualEncoder(Path("data/models"), allow_download=False)
```

Le modèle est `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
384 dimensions, ONNX quantifié d'environ 220 Mo, licence Apache 2.0. Le dépôt
effectif `Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q` est fixé à la révision
`faf4aa4225822f3bc6376869cb1164e8e3feedd0`. Un manifeste local enregistre et vérifie
les SHA-256 du tokenizer et des poids. Le modèle utilise au maximum **128 tokens**.
Le découpage emploie son tokenizer exact avec 110 tokens et un chevauchement de
20 tokens ; les offsets renvoient toujours au texte original. Une entrée trop
longue est rejetée, sans troncature cachée. Les questions doivent donc rester
concises.

La préparation actuelle normalise les entrées par NFKC, retire les tatweels et les caractères de formatage, tout en conservant les offsets des preuves originales. `--preprocessing normalized` est le défaut ; `--preprocessing raw` reproduit la configuration initiale avec sa politique archivée. `RAG_PREPROCESSING` configure ce choix pour le service. Ce correctif a été diagnostiqué après lecture du premier test ; ses scores sur le même jeu sont donc [exploratoires](../reports/diagnostic-normalization/RESULTATS.md).

Les tests d'inférence réelle sont séparés des doubles utilisés dans les tests
unitaires. Après préparation, dans PowerShell :

```powershell
$env:RAG_RUN_MODEL_TESTS = '1'
python -m pytest -q tests/test_embeddings.py
Remove-Item Env:RAG_RUN_MODEL_TESTS
```

## API Python

Après téléchargement et ingestion du corpus, depuis la racine du dépôt :

```powershell
$env:RAG_DATA_DIR = 'data'
$env:RAG_ENCODER = 'none'
$env:RAG_BACKEND = 'local'
$env:RAG_GENERATOR = 'extractive'
python -m uvicorn rag_reglementation_maroc.api:app --host 127.0.0.1 --port 8000
```

`/health` indique la vivacité ; `/ready` vérifie la préparation du corpus.
L'interface des requêtes est documentée sur `http://127.0.0.1:8000/docs`.
Activer `RAG_ENCODER=multilingual` seulement après préparation locale du modèle.
Les modes `semantic` et `hybrid` échouent explicitement si cet encodeur est absent.

## Docker Compose facultatif

**Validation réelle du 17 octobre, non rejouée le 18 :** l'image API a été construite, puis un conteneur exécuté avec l'utilisateur non-root `rag` a répondu en HTTP local aux vérifications français/arabe sur l'article 34 et a refusé une demande d'information actuelle hors corpus. Le parcours utilise le backend local, sans encodeur neuronal et avec réponses extractives. Voir [docker_smoke.json](../reports/docker_smoke.json) et [smoke_docker.py](../scripts/smoke_docker.py).

Ce test valide cette intégration minimale. Il ne démontre ni la qualité générale des réponses, ni un déploiement public, ni une API configurée avec OpenSearch. Le conteneur temporaire a été retiré après le test ; l'image a été conservée.

Pour la baseline sans modèle, les données déjà préparées sont montées depuis
`./data` :

```powershell
docker compose build api
docker compose up api
```

Le port API est lié à `127.0.0.1:8000`. L'image n'embarque ni corpus ni poids ni
secrets. Pour inclure les dépendances neuronales, reconstruire explicitement :

```powershell
$env:RAG_INSTALL_EXTRAS = 'opensearch,neural'
docker compose build api
$env:RAG_ENCODER = 'multilingual'
docker compose up api
```

Le modèle doit déjà exister sous `data/models/`. L'API ne le télécharge pas.

## OpenSearch : service puis indexation explicite

**Validation réelle du 17 octobre :** l'adaptateur Python a été testé contre OpenSearch 3.9.0 avec le client 3.2.0, sur huit articles synthétiques puis le corpus de 394 articles / 728 passages. Les scénarios couvrent BM25, sémantique, hybride, français/arabe, références multiples, provenance et refus d'un index incompatible. Voir [opensearch_smoke.json](../reports/opensearch_smoke.json) et [smoke_opensearch.py](../scripts/smoke_opensearch.py).

Cela valide le contrat adaptateur/cluster ; **l'API configurée avec ce backend n'a pas été exécutée**, et aucun benchmark de pertinence OpenSearch n'est établi. Le service créé pour le test a ensuite été arrêté ; le volume et les index `p2-smoke` ont été conservés.

Le profil `search` fournit OpenSearch **3.9.0**, avec un seul nœud local et le
client Python **3.2.0**. La sécurité du service est désactivée pour ce laboratoire
local ; le port publié reste lié à `127.0.0.1:9200`. Cette configuration n'est pas
un déploiement Internet.

```powershell
docker compose --profile search up -d opensearch
Invoke-RestMethod 'http://127.0.0.1:9200/_cluster/health'
```

Le service peut nécessiter les réglages système OpenSearch/Docker habituels,
notamment `vm.max_map_count` sous Linux et suffisamment de mémoire pour la JVM.
Voir les [instructions Docker officielles](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/).

L'index doit être créé explicitement avec la commande suivante, exécutée sur
l'hôte après préparation du corpus et du modèle. Le client utilise
`http://127.0.0.1:9200` par défaut ; `OPENSEARCH_URL` permet de le modifier :

```powershell
python -m rag_reglementation_maroc index-opensearch --backend opensearch --encoder multilingual
```

Le constructeur et le démarrage de l'API ne créent ni ne suppriment d'index.
L'API vérifie la disponibilité et la provenance de l'index par une lecture seule.
**Après l'indexation, redémarrer l'API** : son chargement tente la préparation du
service une fois au démarrage. Une API initialement non prête ne recharge pas
automatiquement l'index.

L'interface Python correspondante, en reprenant les articles et passages
construits par le pipeline :

```python
from rag_reglementation_maroc.opensearch_backend import OpenSearchRetriever

retriever = OpenSearchRetriever(
    articles, chunks, encoder=encoder, url="http://127.0.0.1:9200"
)
retriever.index()  # Écriture explicite, aucune suppression d'index.
hits = retriever.search("Quelles opérations une banque peut-elle exercer ?", mode="hybrid")
```

Le nom d'index dérive de l'empreinte du corpus, des passages et du modèle. Une
empreinte différente sur un index nommé explicitement est refusée. Les passages
renvoyés par le service sont comparés au corpus local avant citation. La fusion
RRF s'effectue dans l'adaptateur après une recherche BM25 et une recherche k-NN,
avec une constante fixée à 60. Les scores RRF ne sont pas des probabilités de
justesse. Les analyses lexicales OpenSearch et Python diffèrent : mesurer leur
qualité séparément avant d'affirmer une parité des résultats.

Une fois le service prêt et l'indexation terminée :

```powershell
$env:RAG_BACKEND = 'opensearch'
$env:RAG_ENCODER = 'multilingual'
docker compose --profile search up api
```

## Génération Ollama facultative — expérimentale

Le [lot V3](../reports/generation-v3/RESULTATS.md) reprend **six cas de développement déjà vus**. Après préchargement explicite et correction de l'ordre des propriétés du schéma (`claims` avant `abstain`) motivée par des [contrôles synthétiques](../reports/generation-development-controls/RESULTATS.md), deux claims sont acceptés et quatre cas sont refusés, dont un par le filtre lexical avant tout appel à Qwen. Aucun seuil ni classement n'a été ajusté pour ces cas.

La [première revue interne](../reports/generation-v3/manual_review_primary.json) et la [seconde revue distincte](../reports/generation-v3/second_review.json) concordent : les deux affirmations sont soutenues. La consultation arabe ne couvre cependant qu'une partie de l'article complet ; le support du claim et la couverture de l'article sont des propriétés différentes. Ces réponses limitées ne mesurent ni une capacité générale de synthèse ni un taux global de fidélité. Les verdicts concernent uniquement les claims examinés. Le livrable génératif reste expérimental ; le mode extractif demeure le parcours par défaut.

Les [anciens essais du 17 octobre](../reports/ollama_smoke.json) et le [lot V2](../reports/generation-v2/RESULTATS.md) restent conservés. Le timeout historique a été relié à l'annulation d'un chargement à froid ; il ne prouve pas un manque de mémoire. Aucun nouveau timeout n'a été observé dans le lot V3 après préchargement, ce qui ne garantit pas l'absence de délai sur d'autres machines ou requêtes.

### Précharger avant une commande ou le démarrage de l'API

Ollama doit déjà être lancé et `qwen2.5:7b` déjà installé. La commande suivante charge explicitement le modèle ; elle ne télécharge pas de poids :

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:11434/api/generate' -ContentType 'application/json' -Body '{"model":"qwen2.5:7b","keep_alive":"15m","stream":false}' -TimeoutSec 360
```

Attendre la fin de ce chargement avant l'inférence. L'expérience sépare un délai maximal de chargement de 360 secondes du délai de requête de 180 secondes. La conservation en mémoire est demandée pour 15 minutes ; si le modèle a été déchargé, recommencer ce préchargement.

Pour explorer ensuite la CLI, avec corpus et encodeur déjà préparés :

```powershell
.\.venv\Scripts\rag-maroc.exe ask "Que prévoit la loi pour la convention de compte ?" --source-language fr --mode hybrid --encoder multilingual --generator ollama
```

Ou démarrer l'API locale après le même préchargement :

```powershell
.\.venv\Scripts\rag-maroc.exe serve --encoder multilingual --generator ollama
```

Ces commandes ne garantissent pas une réponse acceptée. Le préchargement n'améliore pas à lui seul la récupération, les filtres ou la fidélité du modèle.

`RAG_GENERATOR=ollama` configure aussi l'adaptateur du service. Compose transmet `RAG_OLLAMA_URL` (par défaut `http://host.docker.internal:11434`) et `RAG_OLLAMA_MODEL` (`qwen2.5:7b`). Le service hôte doit être joignable depuis le conteneur ; l'API Docker générative n'a pas été validée par les essais extractifs historiques. Aucun appel cloud n'est requis.

Une structure JSON valide ou une citation réellement présente dans la source ne démontre pas que chaque proposition de la paraphrase est justifiée. Les textes source et sorties brutes restent locaux ; les rapports publics conservent les conditions, verdicts et justifications sans extraits.

## Références de l'implémentation

- [Modèles FastEmbed](https://qdrant.github.io/fastembed/examples/Supported_Models/).
- [Définition du modèle quantifié et limite de tokens](https://github.com/qdrant/fastembed/blob/v0.9.0/fastembed/text/pooled_embedding.py).
- [Révision des poids utilisée](https://huggingface.co/Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q/tree/faf4aa4225822f3bc6376869cb1164e8e3feedd0).
- [Recherche k-NN OpenSearch](https://docs.opensearch.org/latest/vector-search/vector-search-techniques/approximate-knn/).
- [Principe RRF OpenSearch](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/rrf/).
- [Sorties structurées Ollama](https://docs.ollama.com/capabilities/structured-outputs).

## Vérifications locales reproductibles

Les scénarios ci-dessous utilisent uniquement les ressources déjà préparées. Les sorties brutes contenant des citations restent dans outputs/ ; les rapports versionnables ne conservent que les métadonnées.

```powershell
python scripts/smoke_api.py
python scripts/smoke_docker.py
python scripts/smoke_opensearch.py --include-corpus --report outputs/my-smokes/opensearch.json
python scripts/run_ollama_smoke.py
```

Le premier démarre temporairement un serveur HTTP local et le ferme après vérification FR/AR. Le script Docker teste un conteneur réel. Le script OpenSearch attend un service déjà disponible ; il crée ou réutilise ses index de test sans supprimer ni arrêter ce service. Le script Ollama historique conserve ses diagnostics ; ne pas écraser les anciens rapports pour documenter un nouvel essai. Les lots de génération récents ont leurs [conditions propres](../reports/generation-v3/protocol.json), avec préchargement séparé ; ils ne constituent pas un benchmark général de fidélité. Les prérequis modèle, image ou cluster doivent être disponibles avant chaque parcours.

Pour régénérer la figure depuis les JSON exportés, sans relancer la recherche :

```powershell
python -m pip install -e ".[plots]"
python scripts/plot_results.py
```

Les exports PNG et SVG vont dans reports/figures/.
