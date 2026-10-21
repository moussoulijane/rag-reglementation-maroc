# Assistant documentaire V3 — implémentation et validation

Date : 21 octobre 2026. Périmètre : notes sur les réclamations et la médiation bancaire, à partir d’éditions documentaires identifiées.

La V3 est fonctionnelle en local. Elle identifie les points demandés, les relie à un catalogue de propositions relues en interne, assemble une note et expose ses manques. **Cette implémentation ne démontre pas une fiabilité juridique générale.** Le test réservé, la revue professionnelle indépendante des réponses et le pilote métier restent non réalisés.

![Accueil de la V3, sans extrait de PDF](home.jpg)

## Livré

- Référence V2 inchangée : 16 fichiers Python et cinq ressources gelées conformes au manifeste ; les rapports historiques sont conservés.
- Package V3 séparé, routes `/assistant/config`, `/assistant/ask`, `/assistant/search`, schéma de requête `/assistant/schema` et commande `rag-maroc-assistant`.
- Cinq décisions : points identifiés étayés, réponse partielle, information non établie, date non couverte et précision nécessaire.
- Catalogue explicite de 25 propositions et de leurs références. Les notes FR/AR sont des formulations du projet ; elles ne prétendent pas être une traduction officielle des circulaires.
- Preuves non tronquées silencieusement, avec document, édition, article, pages, texte et empreinte. Les scores de classement ne certifient pas leur suffisance.
- Expansion des références guidée par le catalogue, tracée séparément des candidats de la recherche. Plusieurs preuves peuvent contribuer à la note.
- Réutilisation des vecteurs des passages de la référence ; seuls les passages ajoutés sont encodés et mis en cache. Un test protège ce comportement.
- Interface bilingue avec contexte d’établissement et de date, liste des points identifiés, manques explicites et export Markdown sourcé.
- Outils de gel du futur test réservé, contrôle des modifications après gel et import d’une revue de toutes les sorties et affirmations.

La compréhension des questions repose sur un vocabulaire contrôlé, pas sur un vérificateur sémantique universel. Le statut « points identifiés étayés » suppose de vérifier que les points affichés correspondent réellement à la demande. La reformulation libre est désactivée dans ce profil ; les expérimentations historiques d’Ollama restent séparées.

## Corpus et versions

Le corpus actif comprend **418 articles** : les 394 de la loi 103-12 déjà préparés et 24 articles du recueil BAM de fin 2023, soit 221 en français et 197 en arabe.

| Source logique | Langue | Articles | Pages PDF |
| --- | --- | ---: | --- |
| Loi 103-12, édition du 31 mars 2022 | FR | 197 | PDF de 84 pages |
| Loi 103-12, édition du 31 mars 2022 | AR | 197 | PDF de 84 pages |
| Circulaire 9/W/2016, version du recueil fin 2023 | FR | 9 | 1144–1145 du recueil |
| Circulaire 10/W/2016, version du recueil fin 2023 | FR | 15 | 1146–1148 du recueil |

Les deux dernières sources logiques proviennent du même PDF de 1268 pages. Son empreinte est `4855c4b2315510ff07463fad4a1a9206219760d7fde4b1564b2e52dc7d170a69`.

Les six pages des scans individuels et les cinq pages utiles du recueil ont été rendues et inspectées. Les versions diffèrent : la circulaire de médiation compte notamment 16 articles dans le scan individuel et neuf dans le recueil ; la rédaction de certains articles de réclamation diffère aussi. La V3 utilise les articles du recueil, sans fusionner ces versions ni déduire leur statut juridique respectif.

La précision de l’édition est conservée sous `2023-12`, affichée « fin 2023 ». Les dates de signature et publication sont distinctes. Aucune couverture exhaustive des modifications postérieures, ni aucune applicabilité actuelle, n’est affirmée. La version arabe des deux circulaires n’est pas chargée : le filtre arabe strict ne fabrique pas de preuve de substitution.

Les PDF, extractions, index et images de revue restent dans les dossiers ignorés. La capture publique ci-dessus présente seulement l’accueil.

## Diagnostic de développement

Les questions ont été préparées et utilisées pendant le développement. Elles ne constituent pas un test indépendant.

Le [premier diagnostic BM25](development-bm25-01/RESULTATS.md) exposait six statuts incorrects sur 70 variantes, dont une réponse présentée complète malgré une durée chiffrée absente. Les erreurs ont été conservées et analysées : collisions entre « format », « formation » et « information », vocabulaire arabe, et confusion entre recevabilité et demande déjà recevable.

Le [diagnostic final](development-final-verified/RESULTATS.md), avec l’encodeur multilingue, comporte 35 situations déclinées en français/arabe :

- Statut conforme aux annotations internes : **70/70**.
- Cas attendus non complets présentés à tort comme complets : **0/26**.
- Cas attendus complets, effectivement complets avec les propositions attendues : **44/44**.
- Contrôles mécaniques des citations : réussis pour toutes les citations émises.

Ces chiffres vérifient le contrat du catalogue sur des exemples connus. Ils ne mesurent pas la fidélité sémantique générale, ne démontrent pas une baisse de risque à moins de 5 % et ne permettent pas une comparaison causale avec V2. Les 70 variantes ne sont pas 70 situations indépendantes. Le périmètre a été réduit et le corpus augmenté ; les résultats de classement doivent également distinguer la recherche initiale de l’expansion par références relues.

Un nouveau reclasseur neuronal n’a pas été évalué dans cette livraison. La sélection documentaire a été améliorée par les propositions et leurs références ; la comparaison d’autres modèles ou reclasseurs reste conditionnée à un gain mesuré.

## Contrôles exécutés

| Contrôle | Résultat |
| --- | --- |
| Suite Python, tests du modèle réel activés | **188 tests réussis** ; un avertissement de dépréciation Starlette/httpx |
| Ruff et formatage | Réussis |
| TypeScript et build Vite | Réussis |
| Export de note | Test unitaire réussi : statut, manques, références et limites conservés ; extraits bruts absents de la note |
| API HTTP réelle | Neuf parcours V3 réussis et API historique préservée |
| Corpus | PDF approuvé, 24 articles, séquences et métadonnées de provenance vérifiés |
| Distribution | Roue installée dans un répertoire séparé ; commande console exécutée ; modules et ressource de revue exacts |
| Fichiers statiques installés | **19 fichiers exacts**, aucun ancien bundle ; page et capacités accessibles sans corpus |
| Référence gelée | 16 sources et cinq ressources inchangées dans le dépôt ; les 16 sources sont aussi vérifiées dans la roue |
| Publication | Données, réponses brutes, modèles, environnements et node_modules exclus de Git |
| Compose | Configuration validée ; image Docker V3 non exécutée ici |

La vérification de distribution réutilise les dépendances du venv existant. Ce n’est pas une installation complète des dépendances dans un environnement neuf.

Preuves publiques : [contrôles logiciels](software_and_integrity_checks.json), [HTTP](http-smoke.json), [distribution](distribution_checks.json). Les réponses privées ne sont pas copiées dans ces rapports.

## Parcours navigateur vérifiés

- Note française reliée à la circulaire de réclamation, article 4, page PDF 1146.
- Note arabe sur une demande de médiation déjà recevable, reliée à l’article 5 du recueil, avec preuve originale française.
- Délai et montant d’indemnisation demandés ensemble : réponse partielle, montant non établi visible.
- Date juridique saisie : prise en compte et limite temporelle sans fausse citation.
- Filtre arabe strict : information non établie et explication de l’absence des circulaires arabes.
- Demande de délai sans étape précise : clarification affichée.
- Catalogue des quatre sources logiques, comptes et éditions visibles.
- Bouton d’export activé dans le navigateur ; le contenu de la note est contrôlé par le test unitaire. Le fichier physiquement enregistré par le navigateur n’a pas été audité.
- Version mobile arabe à 390 × 844 : texte et note lisibles, largeur du document 375 px, aucun débordement horizontal ; format ordinateur inspecté à 1280 × 900.
- Aucun message d’erreur console recueilli sur les parcours de la V3.

## Ce qui reste à valider

1. Construire et annoter de nouvelles situations avec un professionnel distinct du développement, puis geler le test réservé. Le modèle fourni reste vide, sans identité d’expert inventée.
2. Vérifier la suffisance des passages, la fidélité de chaque affirmation, la couverture et les erreurs critiques sur toutes les sorties du test. La validité d’une citation ne suffit pas.
3. Auditer les relations entre versions et la couverture nécessaire pour une demande à une date donnée.
4. Réaliser un pilote métier comparant recherche manuelle et Daftar, avec temps jusqu’à une référence vérifiée, qualité et corrections.
5. N’activer une reformulation libre qu’après sa propre validation. Mesurer les coûts et latences sur les tâches représentatives.

L’outillage est livré ; ces étapes humaines et leurs résultats ne sont pas simulés. Les objectifs du [plan](../../docs/PLAN_ASSISTANT_REGLEMENTAIRE.md) restent des critères futurs.

## Reprendre comme développeur

Le [guide V3](../../docs/GUIDE_ASSISTANT_V3.md) explique le trajet question → points identifiés → références → note et décisions, ainsi que les commandes de préparation, diagnostic, gel et revue.

Pour refaire la vérification HTTP avec un nouveau rapport :

```powershell
.\.venv\Scripts\python.exe scripts/smoke_assistant.py --output outputs/ma-verification-http.json
```
