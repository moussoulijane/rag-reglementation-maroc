# Comprendre et relancer l’assistant documentaire V3

État : 21 octobre 2026. La V3 prépare des notes sur les réclamations et la médiation. Sa compréhension des demandes repose sur un vocabulaire explicite et un catalogue de propositions relues en interne. Elle ne constitue pas un vérificateur juridique général.

## Ce qui a changé

Le moteur et les résultats V2 sont conservés. Le nouveau package `rag_reglementation_assistant` ajoute un corpus métier, une interprétation des points demandés et des notes sourcées. L’API historique `/ask` reste disponible ; l’interface utilise `/assistant/ask`.

Le corpus V3 comprend les 394 articles de la loi déjà préparés et 24 articles du recueil BAM de fin 2023 : 15 pour la circulaire 10/W/2016 et 9 pour la circulaire 9/W/2016. Les versions de ces circulaires dans le recueil diffèrent des PDF individuels scannés. Les versions ne sont pas fusionnées. Les deux nouvelles circulaires sont chargées uniquement en français ; l’arabe reste disponible pour la question, la note et la loi.

Les cinq pages utiles du recueil ont été rendues et comparées au texte extrait. Le contrôle est interne. Les PDF, textes extraits et index restent sous `data/`, les images de revue sous `outputs/`, tous exclus de Git.

## 1. Préparer les documents et les commandes

Depuis la racine du projet, avec Python 3.11/3.12 et Node 24 :

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,neural]"
.\.venv\Scripts\rag-maroc.exe download
.\.venv\Scripts\rag-maroc.exe ingest
.\.venv\Scripts\rag-maroc-assistant.exe prepare-domain
```

Les deux premières commandes de corpus préparent la référence légale. `prepare-domain` télécharge le recueil dont l’empreinte est fixée, contrôle ses 1268 pages puis extrait les deux sections sélectionnées. Un fichier distant différent nécessite une nouvelle revue. Le démarrage du service ne télécharge rien.

Le catalogue conserve une précision mensuelle `2023-12`, affichée « fin 2023 ». Il ne transforme pas cette indication en une date exacte de consolidation. Dates de signature et de publication restent distinctes ; l’applicabilité actuelle n’est pas établie.

## 2. Faire une première recherche sans modèle neuronal

```powershell
.\.venv\Scripts\rag-maroc-assistant.exe ask "Quel délai de réponse pour une réclamation ?" --mode bm25
.\.venv\Scripts\rag-maroc-assistant.exe ask "ما أجل معالجة طلب وساطة مقبول؟" --mode bm25
```

Lire le JSON dans cet ordre : `assessment.status`, `assessment.findings`, `answer`, puis `citations`. Chaque affirmation de la note possède des numéros de preuve. Une recherche de candidats peut échouer en BM25 entre langues ; le catalogue de propositions fournit une expansion explicite des références. Cette contribution est enregistrée dans `trace.reference_expansion_article_ids` : elle n’est pas présentée comme une réussite du seul encodeur.

## 3. Comprendre les cinq décisions

| État | Sens |
| --- | --- |
| `complete` | Les points identifiés sont étayés dans le périmètre documentaire. Vérifier que l’interprétation affichée correspond à la question. |
| `partial` | Des points sont établis et d’autres restent explicitement non établis. |
| `absent` | L’information précise n’est pas établie par les preuves de ce profil. |
| `temporal` | Les sources ne suffisent pas à confirmer la règle à la date demandée. |
| `ambiguous` | La source, l’étape ou la demande doit être précisée. |

Exercice : demander « Quel délai de réponse à une réclamation et quel montant d’indemnisation ? ». Observer la réponse partielle. Le montant ne doit pas être complété à partir d’un passage seulement apparenté.

Autres essais : « Quel délai pour une réclamation ? » appelle une précision ; une question « actuellement applicable » produit une limite temporelle. Une date juridique explicite ne garantit pas que l’édition disponible documente cette date.

## 4. Suivre une question dans le code

1. [intent.py](../src/rag_reglementation_assistant/intent.py) identifie le thème, les points et les limites explicites. Ce dictionnaire peut manquer une nuance ; ce n’est pas une analyse sémantique universelle.
2. [retrieval.py](../src/rag_reglementation_assistant/retrieval.py) étend l’index avec les nouveaux passages en réutilisant les vecteurs de la référence. Le classement n’est pas un score de vérité.
3. [knowledge.py](../src/rag_reglementation_assistant/knowledge.py) relie les propositions relues aux articles nécessaires. Les résumés français/arabe sont des formulations du projet, pas des versions arabes officielles des circulaires.
4. [service.py](../src/rag_reglementation_assistant/service.py) vérifie la présence des références et les filtres, conserve les conditions dans les preuves, déclare les points manquants et assemble la note. Un budget de taille limite le contexte sans tronquer silencieusement une preuve. Il n’est pas annoncé comme le budget d’un générateur actif.
5. [api.py](../src/rag_reglementation_assistant/api.py) expose le contrat V3. Les citations conservent texte, document, édition, pages et empreinte.
6. [AssistantSummary.tsx](../frontend/src/components/AssistantSummary.tsx) rend le statut et les points identifiés ; [note.ts](../frontend/src/note.ts) prépare l’export Markdown.

La reformulation libre reste désactivée dans ce profil. La note est assemblée à partir des propositions relues. Les expérimentations Ollama historiques ne sont pas une validation de génération de la V3.

## 5. Lancer l’interface

```powershell
Set-Location frontend
npm ci
npm run build
Set-Location ..
$env:RAG_ENCODER = 'none'
.\.venv\Scripts\rag-maroc-ui.exe --host 127.0.0.1 --port 8000
```

Pour le classement multilingue, préparer d’abord le modèle, puis choisir explicitement l’encodeur :

```powershell
.\.venv\Scripts\rag-maroc.exe prepare-model
$env:RAG_ENCODER = 'multilingual'
.\.venv\Scripts\rag-maroc-ui.exe --host 127.0.0.1 --port 8000
```

Ouvrir [Daftar](http://127.0.0.1:8000/). Les options avancées permettent de préciser le type d’établissement et une date juridique. Le mode automatique consulte les langues disponibles ; le filtre arabe strict ne fournit pas de fausse traduction des circulaires françaises. La note s’exporte avec son statut, ses manques et ses références, sans les extraits bruts du PDF.

L’entrée API historique garde son schéma. Les requêtes V3 sont décrites par `/assistant/schema`, les capacités par `/assistant/config`, le classement par `/assistant/search`.

## 6. Reproduire le diagnostic de développement

```powershell
.\.venv\Scripts\rag-maroc-assistant.exe evaluate-development --output reports/assistant-v3/mon-diagnostic-bm25 --mode bm25
.\.venv\Scripts\rag-maroc-assistant.exe evaluate-development --output reports/assistant-v3/mon-diagnostic-semantic --encoder multilingual --mode semantic
```

Choisir un dossier nouveau à chaque fois. Les questions, le code, les références et la configuration sont empreints avant exécution. La commande calcule les statuts, la présence des propositions attendues et la validité mécanique des citations. Ces mesures ne constituent pas une évaluation humaine de la fidélité ou de la suffisance sémantique.

Les 35 situations de [développement](../evaluation/assistant_v3_development.json), déclinées en FR/AR, ont participé aux corrections. Les 70 variantes ne sont pas 70 observations indépendantes. Le premier lot et ses erreurs restent conservés à côté des lots suivants.

## 7. Préparer un véritable test réservé et sa revue

Le [modèle réservé](../evaluation/assistant_v3_reserved_template.json) est volontairement vide et marqué en attente. Un professionnel distinct du développement doit construire de nouvelles situations, vérifier les sources, annoter les points attendus et auditer les recouvrements avec les cas connus.

Une situation utilise cette structure :

```json
{"group_id":"nouvelle-situation","variants":[
  {"query_language":"fr","source_language":"fr","question":"Question nouvelle",
   "expected_status":"partial","required_propositions":[],"expected_missing":[]}
]}
```

Déclarer les différences d’annotation lorsque la langue source demandée ne dispose pas du texte nécessaire. Les quatre directions d’un groupe restent liées. Remplir la déclaration de revue, puis utiliser :

```powershell
.\.venv\Scripts\rag-maroc-assistant.exe freeze-test --cases CHEMIN_DU_TEST --manifest CHEMIN_DU_MANIFESTE
.\.venv\Scripts\rag-maroc-assistant.exe evaluate-test --cases CHEMIN_DU_TEST --manifest CHEMIN_DU_MANIFESTE --output reports/assistant-v3/test-reserve --private-output outputs/assistant-v3/test-reserve
.\.venv\Scripts\rag-maroc-assistant.exe import-review --results reports/assistant-v3/test-reserve/results.json --review outputs/assistant-v3/test-reserve/review-remplie.json --output reports/assistant-v3/test-reserve/revue.json
```

Le gel contrôle questions, moteur, corpus, modèle et méthode. Les réponses et citations destinées à la revue restent sous `outputs/`. La revue doit couvrir toutes les sorties et toutes les affirmations, avec verdict, couverture et erreur critique ; les lignes non relues ne peuvent être assimilées à des succès. Une déclaration de compétence n’est pas une authentification effectuée par le logiciel.

Le test réservé, la validation professionnelle des réponses et le pilote utilisateur ne sont pas réalisés. Le [modèle de pilote](../evaluation/assistant_v3_pilot_template.json) permet de consigner les tâches manuelles et assistées, le temps jusqu’à une référence vérifiée, les erreurs et les corrections. Les objectifs restent ceux du [plan](PLAN_ASSISTANT_REGLEMENTAIRE.md).

## 8. Vérifier les changements

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
npm --prefix frontend run test:note
npm --prefix frontend run build
```

La suite protège notamment la distinction entre recevabilité et traitement d’une demande déjà recevable, les filtres de langue, l’absence d’un montant, les collisions de vocabulaire et la conservation des vecteurs existants.

Le [bilan d’implémentation](../reports/assistant-v3/IMPLEMENTATION.md) sépare les contrôles exécutés des validations restantes. Pour comprendre la référence initiale, revenir au [guide en dix séances](GUIDE_PAS_A_PAS.md).
