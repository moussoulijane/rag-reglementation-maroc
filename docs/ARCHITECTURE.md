# Architecture du jalon bancaire FR/AR

État documentaire au **18 octobre 2026**. Corpus : loi 103-12, édition consolidée au **31 mars 2022**, français et arabe, publiée par Bank Al-Maghrib. Les fichiers sources, textes extraits et index restent locaux sous `data/`, ignoré par Git.

## Contrat d'une preuve

[models.py](../src/rag_reglementation_maroc/models.py) définit le contrat commun :

`Article → Chunk → SearchHit → réponse et citations`.

Un article porte un identifiant stable tel que `bam-10312-fr:article-34`, une langue, l'édition, l'URL officielle, les pages PDF numérotées depuis 1 et le SHA-256 du PDF. Les numéros d'article sont les chaînes 1 à 196, plus `19bis`. Un passage conserve des offsets dans le texte original. La normalisation destinée à la recherche ne remplace jamais ce texte cité.

## Modules et responsabilités

| Module | Rôle |
|---|---|
| `catalog.py`, `ingestion.py` | Sources officielles, téléchargement vérifié, extraction stricte, JSONL local et rapport de qualité. |
| `embeddings.py` | Encodeur multilingue optionnel à révision fixée, contrôle de longueur, normalisation et correspondance des offsets. |
| `text.py`, `chunking.py`, `retrieval.py` | Normalisation lexicale, passages, BM25, cosinus et fusion RRF ; déduplication par article. |
| `opensearch_backend.py` | Indexation explicite et recherche optionnelle dans OpenSearch, sous le même contrat de résultat. |
| `answering.py` | Sélection du contexte, abstention, extraits et adaptateur génératif expérimental ; contrôles des citations. |
| `runtime.py`, `api.py`, `cli.py` | Configuration, préparation du service, commandes et API HTTP. |
| `evaluation.py` | Recall/MRR par article, quatre directions linguistiques, décisions d'abstention, provenance et latence. |
| `evaluation_manifest.py` | Transfert explicite de la politique d'origine vers de nouveaux thèmes audités ; empreintes des données, critères, code et index. |

Aucun téléchargement de modèle n'a lieu au démarrage normal de l'API. `prepare-model` autorise explicitement la préparation ; les modes `semantic` et `hybrid` échouent si l'encodeur requis est absent.

## Recherche et préparation neuronale

`LocalRetriever(articles, encoder=None, cache_dir=None)` expose :

`search(question, language=None, mode="bm25", top_k=5) → list[SearchHit]`.

Le filtre `language` désigne la langue des **sources**, distincte de celle de la question. Le moteur local compare les passages, fusionne les rangs en mode hybride, puis déduplique par article. Un bon article peut cependant fournir un passage incomplet pour une question à plusieurs conditions.

Le modèle MiniLM ONNX produit 384 dimensions et accepte au maximum 128 tokens. La préparation normalisée emploie NFKC, retire les tatweels arabes et caractères de formatage, et maintient une correspondance vers les offsets originaux. Les passages visent 110 tokens avec recouvrement de 20. `--preprocessing raw|normalized` et `RAG_PREPROCESSING` distinguent les configurations ; `normalized` est le défaut actuel.

Le marqueur de préparation participe aux métadonnées et à l'empreinte de l'index. Le changement de normalisation affecte aussi le découpage ; son gain observé ne constitue pas un effet isolé des poids du modèle.

## Réponse et abstention

`AnswerService.ask(..., generator="extractive")` retourne les preuves acceptées ou un statut d'abstention. La politique combine des indices lexicaux ou sémantiques propres au mode et une garde de périmètre temporel. Le RRF n'est pas transformé en probabilité de vérité.

Le contexte génératif conserve les passages ancres et un nombre borné de voisins. L'adaptateur Ollama peut refuser, échouer ou dépasser le délai. Les [premiers essais](../reports/ollama_smoke.json) restent conservés. Le 18 octobre, un préchargement explicite a supprimé les timeouts sur un lot fixé ; des contrôles synthétiques ont motivé l'ordre `claims` avant `abstain` dans le schéma transmis. Le [lot V3](../reports/generation-v3/RESULTATS.md) produit deux affirmations soutenues sur six cas de développement connus, avec refus et omissions conservés. **La fidélité générale de Qwen reste non validée.** Aucun préchargement implicite n'a été ajouté à l'API.

La validité d'un identifiant ou d'une citation n'est pas une mesure de fidélité sémantique. Les métriques par article ne vérifient pas non plus que chaque proposition nécessaire figure dans le contexte.

## Entrées et cycle de vie

CLI : `download`, `ingest`, `prepare-model`, `ask`, `calibrate`, `evaluate`, `index-opensearch`, `serve`. `--data-dir` vaut `data` par défaut.

HTTP : `/health` pour la vivacité, `/ready` pour la préparation, `/search`, `/ask`, `/docs`. Les variables `RAG_DATA_DIR`, `RAG_ENCODER`, `RAG_PREPROCESSING`, `RAG_BACKEND` et `RAG_GENERATOR` configurent le service.

L'indexation OpenSearch est une action explicite. Le démarrage vérifie la disponibilité et la provenance en lecture seule ; il ne crée ni ne supprime un index. Les analyseurs lexicaux et le moteur vectoriel peuvent différer du backend local : la qualité doit être mesurée séparément.

## Expériences et validation

Le [premier test](../reports/reference/RESULTATS.md) est conservé. La normalisation arabe a été décidée **après lecture de ses erreurs**. Le [diagnostic suivant](../reports/diagnostic-normalization/RESULTATS.md), sur les mêmes questions, est explicitement exploratoire, même après recalibration sur développement. Voir le [protocole](PROTOCOL.md).

L'API HTTP locale et un conteneur Docker construit, exécuté sans root, ont réellement été testés en français et arabe sur l'article 34, ainsi que sur une demande d'information actuelle à refuser. Ces vérifications d'intégration ne sont pas un benchmark de pertinence. L'adaptateur OpenSearch a aussi été testé contre un cluster réel, en modes BM25, sémantique et hybride, sur fixtures puis corpus bancaire ; l'API avec backend OpenSearch et sa pertinence ne sont pas validées par ces essais. Le [bilan de validation](../reports/VALIDATION.md) et les [scripts smoke](../scripts/) précisent ces périmètres.



L'[évaluation sur de nouveaux thèmes](CHALLENGE_V2.md) du 18 octobre réutilise les seuils d'origine sans recalibration. Son manifeste fixe les questions, l'audit, le protocole et les sources Python avant exécution, puis la CLI vérifie le même index. Les [résultats et erreurs](../reports/extension-v2/BILAN.md) montrent un bon rappel sur ce lot, mais de nombreux négatifs proches indûment acceptés. Le gel reste une trace locale, sans expertise juridique indépendante ni préenregistrement externe.
