# Plan d’amélioration — Daftar, assistant réglementaire bancaire FR/AR

**Implémentation du 21 octobre :** une V3 documentaire délimitée est réalisée avec corpus métier, propositions relues, cinq décisions, note exportable et outils de gel/revue. Le test réservé, l’arbitrage professionnel et le pilote métier restent à réaliser. Les critères ci-dessous sont des objectifs, pas des scores acquis. Voir le [bilan](../reports/assistant-v3/IMPLEMENTATION.md) et le [guide](GUIDE_ASSISTANT_V3.md).

Date : 19 octobre 2026. Statut : plan proposé, sans modification du moteur ni nouvelle mesure de performance.

## 1. Le produit visé

Premier utilisateur : un analyste conformité qui prépare une note et doit retrouver, comprendre et vérifier ses références.

Premier périmètre proposé : **traitement des réclamations et médiation bancaire**. Le livrable utile est un dossier de preuves : règle demandée, destinataire de l’obligation, conditions, délai lorsqu’il est établi, recours lorsqu’il est demandé, références et points restant à vérifier. Les conventions de compte pourront former un deuxième périmètre, évalué séparément.

Exemples de tâches à couvrir après validation du corpus :
- retrouver les textes nécessaires pour documenter une obligation ;
- répondre à une question précise en distinguant règle, condition et exception ;
- préparer une courte note dont chaque affirmation renvoie à une preuve ;
- produire une liste de vérifications, en séparant exigences textuelles et suggestions de travail.

La date de référence et le type d’établissement doivent être demandés lorsqu’ils changent la réponse. Une ambiguïté déclenche une clarification ciblée. Le résultat accompagne la lecture et l’analyse du professionnel ; sa disponibilité dans l’interface ne constitue pas une validation réglementaire.

## 2. Point de départ vérifié

Le corpus contient la loi 103-12 dans son édition du 31 mars 2022, en français et arabe. Le challenge interne V2 comporte 20 thèmes déclinés en 80 couples question/langue source, donc des variantes corrélées.

| Mesure V2 | Sémantique | Hybride |
| --- | ---: | ---: |
| Article attendu dans les cinq premiers résultats | 43/48 — 89,6 % | 42/48 — 87,5 % |
| Cas hors corpus acceptés par la garde | 12/32 | 15/32 |

Ces acceptations indiquent un défaut de reconnaissance de l’insuffisance des preuves ; elles ne mesurent pas directement un taux d’affirmations générées fausses. La génération n’a fourni que deux affirmations soutenues sur six sondes de développement déjà connues. L’UI et les 156 tests logiciels ne remplacent pas cette évaluation.

Références : [résultats V2](../reports/challenge-v2/RESULTATS.md), [erreurs V2](../reports/challenge-v2/ERREURS.md), [génération](../reports/generation-v3/RESULTATS.md), [validation UI](../reports/ui/VALIDATION.md).

## 3. Ordre des travaux et décisions de passage

| Lot | Travail | Livrable concret | Condition de passage |
| --- | --- | --- | --- |
| 0 — Référence et contrat métier | Conserver V2 ; définir tâches, périmètre et erreurs critiques. | Référence reproductible, fiche de périmètre et grille d’annotation. | Une tâche réussie et une erreur critique ont une définition observable. |
| 1 — Suffisance des preuves | Décomposer les demandes et vérifier ce que le contexte permet réellement d’affirmer. | Décision complète / partielle / absente / temporelle / ambiguë, avec justification par point. | Gain mesuré sur développement sans refus systématique des questions couvertes. |
| 2 — Corpus métier et versions | Ajouter un petit ensemble cohérent de textes nécessaires au premier usage. | Catalogue, textes vérifiés, liens de modification et rapport de qualité. | Aucune réponse métier ne dépend d’une transcription ou d’une version non vérifiée. |
| 3 — Contexte utile | Sélectionner les passages et renvois nécessaires, puis tester un reclassement si utile. | Contexte traçable sous budget de tokens, comparaison des variantes. | Amélioration de la suffisance du contexte, sans régression cachée en arabe ou sur les refus. |
| 4 — Réponse et UI | Rédiger une réponse courte par point, avec citations, limites et questions à clarifier. | Contrat de réponse versionné et interface adaptée. | Les affirmations, les manques et les preuves restent identifiables ; citations valides à chaque exécution. |
| 5 — Évaluation indépendante et pilote | Tester une version figée puis comparer son usage à une recherche manuelle. | Rapport complet, erreurs et décision de pilote. | Objectifs ci-dessous atteints et revue humaine des erreurs critiques. |

Les lots 1 et 3 se développent d’abord sur le corpus existant. Le lot 2 constitue une extension explicitement versionnée. Ajouter des textes n’est pas une preuve d’amélioration du mécanisme de refus.

## 4. Lot 0 : conserver une référence honnête

Avant la prochaine modification du moteur :
1. conserver le code, le corpus, la politique, les manifestes et les rapports V2 dans une référence immuable et reproductible ;
2. créer une version suivante avec ses propres ressources et empreintes ;
3. traiter désormais les erreurs déjà vues dans V2 et les sondes de génération V3 comme des cas de développement ou de régression ;
4. définir la taxonomie des erreurs et le protocole de la prochaine évaluation.

Le futur moteur ne doit pas être déclaré conforme au manifeste de l’ancien moteur. Pour reproduire V2, utiliser sa référence complète. Les rapports historiques ne sont pas réécrits après une correction.

Comparer une modification de recherche à corpus constant. Une comparaison impliquant de nouveaux textes doit distinguer les effets du corpus, de la recherche et de la politique de réponse.

## 5. Lot 1 : juger l’information disponible

La garde actuelle utilise surtout la meilleure similarité d’un passage ou un recouvrement lexical. Une forte proximité avec le sujet peut coexister avec l’absence du délai ou du montant demandé.

Pour chaque demande :
1. identifier les points nécessaires : par exemple acteur, obligation, délai, condition et recours, uniquement lorsque la question les exige ;
2. associer chaque point à un ou plusieurs passages sources ;
3. décider si les éléments répondent au point demandé, avec ses conditions et son périmètre ;
4. rendre la décision explicite.

| État | Comportement prévu |
| --- | --- |
| Complet | Tous les points nécessaires sont étayés ; réponse citée. |
| Partiel | Réponse aux seuls points établis ; liste explicite des points manquants. |
| Absent | Expliquer que l’information précise n’est pas établie dans les sources consultées. |
| Temporel | Préciser la date documentée et le défaut de couverture de la date demandée. |
| Ambigu | Poser une question de clarification avant une conclusion. |

Une réponse partielle ne peut contenir d’affirmations non soutenues. Un passage qui cite une autre réglementation sans donner son contenu ne fournit pas, à lui seul, le délai ou le montant recherché.

Contrôles déterministes : identifiants, citations présentes dans le texte original, offsets, dates connues, unités et nombres explicitement présents. Ces contrôles ne démontrent pas que la règle s’applique à la situation.

Jugement sémantique : preuve suffisante, exception, relation entre plusieurs textes et couverture de la demande. Un modèle peut assister ce jugement ; ses verdicts doivent être confrontés à des annotations humaines. Le modèle qui rédige et celui qui vérifie peuvent partager les mêmes erreurs.

## 6. Lot 2 : un corpus métier daté et vérifiable

Commencer par un inventaire des documents nécessaires aux réclamations et à la médiation, puis intégrer quelques textes complets avec leurs annexes. L’objectif est de couvrir le parcours choisi, plutôt qu’un nombre arbitraire de PDF.

Les circulaires BAM 9/W/2016 et 10/W/2016 constituent des candidats déjà repérés dans [SOURCES.md](SOURCES.md). Le projet avait constaté que leurs PDF individuels nécessitaient un OCR. Tout OCR devra être vérifié contre les pages rendues, avec une attention particulière aux nombres, négations, conditions, tableaux et notes.

Un [recueil officiel BAM](https://www.bkam.ma/content/download/814412/8935685/Recueil%20des%20textes%20l%C3%A9gislatifs%20et%20r%C3%A9glementaires%20de%20BAM%20_%20VF.pdf), indexé comme mis à jour à fin 2023, permet de repérer ces catégories de textes. C’est une piste d’inventaire datée, sans preuve d’exhaustivité ou d’applicabilité en 2026. L’ouverture directe de ce PDF a renvoyé 403 pendant la préparation de ce plan ; son extraction et sa vérification restent à faire.

Conserver, par document :
- autorité, type de texte, numéro, objet et champ d’application ;
- URL officielle, PDF immuable, empreinte et date de collecte ;
- dates de signature, publication, effet et consolidation, chacune séparée et inconnue si non établie ;
- langue disponible, qualité d’extraction et correspondance linguistique vérifiée ;
- références aux textes modifiés, remplacés ou complétés, avec leurs preuves ;
- provenance des paragraphes, pages exactes et annexes.

Une date de collecte récente ne rend pas un texte actuel. L’absence d’amendement dans notre catalogue ne prouve pas qu’il n’existe pas. Toute affirmation sur une règle à une date donnée exige une couverture documentaire vérifiée ; sinon, le système signale la limite.

Une langue manquante reste manquante. Une traduction de travail éventuelle ne devient pas un texte officiel ni une citation originale. Les règles de conservation locale des PDF et index décrites dans SOURCES.md restent applicables.

## 7. Lot 3 : retrouver le contexte qui permet de répondre

Le moteur déduplique actuellement les résultats par article ; une expansion ajoute ensuite des introductions et voisins. Le bon article peut donc être retrouvé sans toutes les propositions nécessaires.

Travaux proposés :
- garder plusieurs passages complémentaires d’un article lorsqu’ils apportent des éléments distincts ;
- préserver la structure paragraphes, conditions, exceptions, notes et annexes ;
- suivre les renvois utiles dans les textes disponibles, en signalant ceux qui manquent ;
- conserver des offsets vers le texte original et des pages exactes pour chaque preuve ;
- assembler le contexte sous le budget réel du modèle, après réservation de la place nécessaire à la réponse.

Comparer successivement la sélection actuelle, une sélection de passages améliorée, puis éventuellement un reclasseur multilingue. Le reclasseur est retenu seulement s’il apporte un gain mesuré sur développement et un coût acceptable. Un changement d’encodeur obéit à la même règle.

Mesurer les quatre directions FR→FR, AR→AR, FR→AR et AR→FR. Une hausse globale qui masque une régression en arabe ou une hausse des fausses acceptations n’est pas un gain suffisant.

Le diagnostic doit distinguer : preuve absente du corpus ; preuve non retrouvée ; preuve présente mais mal sélectionnée ; réponse refusée ou mal rédigée malgré un contexte suffisant.

## 8. Lot 4 : une réponse exploitable et une UI qui l’explique

Format de réponse proposé :
1. réponse courte à la question ;
2. points établis, avec citations liées à chaque affirmation ;
3. conditions et exceptions pertinentes ;
4. informations manquantes ou ambiguës ;
5. édition, date de référence et liens vers les textes.

Si des sources paraissent contradictoires, afficher les éléments en désaccord et demander un arbitrage ; ne pas choisir silencieusement une règle.

Une affirmation peut nécessiter plusieurs preuves. La réponse doit couvrir les alinéas nécessaires et distinguer une règle exprimée par le texte d’une suggestion pratique de l’assistant.

Dans l’UI : rendre visibles le statut complet/partiel, les points non établis, les preuves et la date. Ajouter une clarification ciblée lorsque nécessaire, puis l’export d’une note sourcée. Les statuts temporels ne sont pas résolus par la seule détection d’un mot comme « actuel ».

Le contrat API et l’UI doivent évoluer ensemble. Les erreurs de transport ou d’indisponibilité du modèle restent des erreurs de service, distinctes d’un refus documentaire. Tester également les instructions parasites dans les documents, les fausses références et les réponses arrivant après une nouvelle requête.

La génération reste conditionnée aux preuves. Si Ollama ne couvre pas les questions soutenues, diagnostiquer le contexte et le comportement du modèle sur développement, puis comparer une autre configuration ou un autre modèle. Changer de modèle n’est pas, à lui seul, un critère de réussite.

## 9. Lot 5 : comment décider que l’assistant fonctionne bien

### Données et indépendance

Préparer un ensemble de développement distinct. Après stabilisation du périmètre documentaire, confier la préparation du test à une personne ou une équipe qui ne règle pas le moteur et n’examine pas ses sorties avant le gel des annotations.

Viser progressivement **100 groupes de situations distinctes** : par exemple 40 entièrement répondables, 20 partiellement répondables, 20 sans réponse dans le corpus, 10 avec problème de date et 10 ambiguës. Chaque groupe peut être décliné dans les quatre directions linguistiques. Le volume est une cible de travail ; si le périmètre ne fournit pas assez de règles ou faits distincts, ne pas compter des paraphrases comme des situations indépendantes.

Annoter les propositions attendues, preuves nécessaires, points volontairement absents, état de réponse acceptable et gravité d’une erreur. Prévoir une double annotation sur les cas critiques et un arbitrage des désaccords. Des agents peuvent préparer et relire ; une validation juridique indépendante exige une revue humaine qualifiée.

Lorsqu’un document est ajouté, un ancien négatif peut devenir répondable. Son annotation doit être revue contre le nouveau corpus avant le test. Ce changement ne constitue pas automatiquement une amélioration du refus.

### Objectifs proposés avant le pilote

Ce sont des **cibles de projet à fixer avant le test**, pas des résultats acquis ni des normes réglementaires.

| Dimension | Cible initiale proposée |
| --- | --- |
| Recherche d’articles | Recall@5 ≥95 % sur les questions entièrement répondables. |
| Suffisance du contexte | ≥90 % de ces questions disposent de toutes les preuves nécessaires dans le contexte transmis. |
| Faux résultat complet | ≤5 % des situations non entièrement répondables produisent une réponse présentée à tort comme complète. |
| Réponse utile sur positifs | ≥80 % des questions entièrement répondables reçoivent effectivement une réponse complète, soutenue et correcte. |
| Fidélité des affirmations | ≥98 % des affirmations émises sont soutenues lors de la revue ; aucune erreur critique observée dans le lot de validation. |
| Couverture | ≥90 % des points attendus sont couverts dans les réponses annoncées complètes. |
| Provenance technique | 100 % des citations affichées passent les contrôles automatiques d’identifiant, texte et source. |

Présenter les effectifs, les résultats par langue et les incertitudes. Une variante linguistique qui échoue nécessite une décision explicite de correction ou de restriction du périmètre annoncé.

Ne pas récompenser un assistant qui refuse tout : évaluer ensemble fausses réponses complètes, réponses partielles correctes et questions couvertes inutilement refusées. Les erreurs critiques comprennent notamment un chiffre inventé, une condition inversée, une mauvaise autorité ou une actualité non établie.

Zéro erreur observée ne prouve pas zéro risque. À titre illustratif, avec zéro échec sur 60 situations réellement indépendantes, la borne supérieure binomiale unilatérale à 95 % reste proche de 4,9 % ; sur 20 situations elle est proche de 13,9 %. Les traductions ne multiplient pas l’effectif indépendant. Les hypothèses d’indépendance doivent elles-mêmes être examinées.

Une correction inspirée du test transforme les cas consultés en développement ; son évaluation finale nécessite d’autres cas encore inédits.

### Utilité sur le terrain

Faire réaliser les mêmes tâches avec recherche documentaire manuelle et avec Daftar, dans un ordre alterné pour limiter l’effet d’apprentissage. Mesurer :
- temps jusqu’à une réponse dont les références ont été vérifiées ;
- exactitude, couverture et erreurs critiques selon un évaluateur indépendant ;
- nombre de corrections nécessaires ;
- compréhension des limites et des dates par l’utilisateur ;
- latences médiane et au 95e percentile, coûts et incidents de service.

Une première cible métier proposée est une réduction d’au moins 30 % du temps de vérification, sans dégradation de qualité. Le petit pilote fournit un signal d’utilité ; il ne démontre pas à lui seul la fiabilité générale. Les budgets de latence seront fixés après mesure de la machine et des tâches.

## 10. Première tranche à réaliser après ce plan

Commencer par les lots 0 et 1 : figer la référence, rédiger la grille de suffisance, préparer des cas de développement distincts et rendre visibles les cinq décisions. Le premier résultat attendu est la baisse des acceptations sans preuve suffisante, accompagnée du taux de réponses utiles conservées.

Chaque lot se termine par une démonstration FR/AR, une comparaison mesurée et une mise à jour du guide avec : problème, modification, raison, test et limite restante. L’élargissement du corpus puis la rédaction générative suivent ces validations.

Le [guide pas à pas](GUIDE_PAS_A_PAS.md) et l’[atelier d’évaluation](ATELIER_EVALUATION_V2.md) constituent les supports de lecture pour suivre ces évolutions comme développeur.
