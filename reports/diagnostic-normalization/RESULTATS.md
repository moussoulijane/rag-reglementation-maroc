# Résultats pilotes : recherche bancaire FR/AR

Corpus BAM : loi 103-12, édition consolidée au 31 mars 2022. Les scores décrivent ce petit benchmark interne et ne valident pas le droit actuel.

Split : **test**. Les traductions d'un thème restent dans le même split. Les quatre directions linguistiques sont corrélées ; aucun intervalle d'indépendance artificiel n'est calculé.

**Analyse exploratoire après consultation du premier test.** Le correctif de normalisation arabe a été motivé par les erreurs de la première exécution. Les mêmes thèmes sont réutilisés : ce diagnostic ne constitue pas une nouvelle validation sur des questions inconnues. Les seuils sont choisis sur développement.

| Méthode | Direction | Recall@5 | MRR@5 | Positifs acceptés | Négatifs refusés |
| --- | --- | --- | --- | --- | --- |
| bm25 | fr->fr | 1.000 | 0.867 | 1.000 | 0.667 |
| bm25 | ar->ar | 0.800 | 0.650 | 1.000 | 1.000 |
| bm25 | fr->ar | 0.000 | 0.000 | 0.000 | 1.000 |
| bm25 | ar->fr | 0.000 | 0.000 | 0.000 | 1.000 |
| bm25 | overall | 0.450 | 0.379 | 0.500 | 0.917 |
| semantic | fr->fr | 1.000 | 1.000 | 0.800 | 1.000 |
| semantic | ar->ar | 0.800 | 0.500 | 1.000 | 1.000 |
| semantic | fr->ar | 0.600 | 0.440 | 0.600 | 1.000 |
| semantic | ar->fr | 0.800 | 0.550 | 0.800 | 1.000 |
| semantic | overall | 0.800 | 0.623 | 0.800 | 1.000 |
| hybrid | fr->fr | 1.000 | 1.000 | 0.800 | 0.667 |
| hybrid | ar->ar | 1.000 | 0.750 | 1.000 | 1.000 |
| hybrid | fr->ar | 0.600 | 0.440 | 0.800 | 0.667 |
| hybrid | ar->fr | 0.800 | 0.550 | 1.000 | 1.000 |
| hybrid | overall | 0.850 | 0.685 | 0.900 | 0.833 |

32 couples question/langue-source, 8 thèmes, par méthode. Le rappel et MRR portent uniquement sur les questions annotées comme répondables.

Les seuils d'abstention ont été choisis sur développement, puis conservés pour le test. L'abstention est une heuristique sur les passages retrouvés et la portée temporelle du corpus, pas un vérificateur de vérité.

**Fidélité générative non évaluée par ce benchmark.** La validité d'un identifiant ou la présence d'une citation ne prouve pas qu'une paraphrase générée est justifiée. Les résultats ci-dessus n'impliquent aucune mesure de qualité de Qwen/Ollama.

Les JSON conservent chaque question originale, son groupe, les articles attendus et retrouvés, les décisions d'abstention, la provenance et les latences. Ils ne contiennent aucun texte intégral ou extrait des PDF BAM.

Les temps de recherche excluent le chargement du modèle/index et la génération. Les poids ONNX sont préparés localement ; le corpus bancaire ne quitte pas la machine pour être encodé.

Docker Compose est fourni et sa configuration est validée. Le daemon Docker de cette machine est indisponible : le build et l'intégration avec un cluster OpenSearch n'ont pas été exécutés.
