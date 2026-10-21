# Résultats pilotes : recherche bancaire FR/AR

Corpus BAM : loi 103-12, édition consolidée au 31 mars 2022. Les scores décrivent ce petit benchmark interne et ne valident pas le droit actuel.

Split : **test**. Les traductions d'un thème restent dans le même split. Les quatre directions linguistiques sont corrélées ; aucun intervalle d'indépendance artificiel n'est calculé.

**Nouveaux thèmes internes, politique figée transférée sans recalibration.** Questions et code gelés après audit interne et avant exécution. Ce jeu ne bénéficie pas d'une annotation juridique externe indépendante. Les traductions restent corrélées ; les scores sont descriptifs.

| Méthode | Direction | Recall@5 | MRR@5 | Positifs acceptés | Négatifs refusés |
| --- | --- | --- | --- | --- | --- |
| bm25 | fr->fr | 1.000 | 0.958 | 0.917 | 0.625 |
| bm25 | ar->ar | 0.750 | 0.556 | 0.583 | 0.625 |
| bm25 | fr->ar | 0.000 | 0.000 | 0.000 | 1.000 |
| bm25 | ar->fr | 0.000 | 0.000 | 0.000 | 1.000 |
| bm25 | overall | 0.438 | 0.378 | 0.375 | 0.812 |
| semantic | fr->fr | 0.917 | 0.875 | 0.833 | 0.500 |
| semantic | ar->ar | 1.000 | 0.760 | 0.917 | 0.500 |
| semantic | fr->ar | 0.833 | 0.632 | 0.750 | 0.750 |
| semantic | ar->fr | 0.833 | 0.662 | 1.000 | 0.750 |
| semantic | overall | 0.896 | 0.732 | 0.875 | 0.625 |
| hybrid | fr->fr | 1.000 | 0.958 | 0.917 | 0.500 |
| hybrid | ar->ar | 0.833 | 0.708 | 1.000 | 0.500 |
| hybrid | fr->ar | 0.833 | 0.632 | 1.000 | 0.625 |
| hybrid | ar->fr | 0.833 | 0.662 | 1.000 | 0.500 |
| hybrid | overall | 0.875 | 0.740 | 0.979 | 0.531 |

80 couples question/langue-source, 20 thèmes, par méthode. Le rappel et MRR portent uniquement sur les questions annotées comme répondables.

Les seuils d'abstention ont été choisis sur développement, puis conservés pour le test. L'abstention est une heuristique sur les passages retrouvés et la portée temporelle du corpus, pas un vérificateur de vérité.

**Fidélité générative non évaluée par ce benchmark.** La validité d'un identifiant ou la présence d'une citation ne prouve pas qu'une paraphrase générée est justifiée. Les résultats ci-dessus n'impliquent aucune mesure de qualité de Qwen/Ollama.

Les JSON conservent chaque question originale, son groupe, les articles attendus et retrouvés, les décisions d'abstention, la provenance et les latences. Ils ne contiennent aucun texte intégral ou extrait des PDF BAM.

Les temps de recherche excluent le chargement du modèle/index et la génération. Les poids ONNX sont préparés localement ; le corpus bancaire ne quitte pas la machine pour être encodé.

Les mesures ci-dessus concernent la recherche documentaire locale. Le statut des validations HTTP, Docker, OpenSearch et de génération est documenté séparément dans reports/VALIDATION.md.
