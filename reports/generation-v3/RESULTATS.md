# Génération V3 : cas de développement déjà vus

Le chemin de génération produit ici deux réponses citées, mais ses limites restent importantes. Ce lot est une reprise de six cas de développement déjà vus après une correction choisie sur des contrôles synthétiques. Il ne constitue pas une évaluation tenue à l’écart, ni une mesure générale de fidélité. Les échecs V2 restent intacts.

## Correction et gel

Le seul changement de génération est l’ordre des propriétés et des champs requis du schéma envoyé au modèle : `claims` avant `abstain`. Les clés du contrat JSON et le validateur de cohérence sont identiques. Consignes, modèle, options, recherche, découpage, encodeur, filtres et seuils restent inchangés. Le [protocole](protocol.json) a été fixé le 18 octobre 2026 à 22:22:56 UTC, avant les appels. Les [contrôles synthétiques séparés](../generation-development-controls/RESULTATS.md) motivent la correction ; leurs données ne proviennent pas de la loi.

Le modèle a été préchargé séparément. Aucun nouveau timeout ni rejet de citation n’a été observé dans ce lot ; les statuts d’abstention ci-dessous ne sont donc pas des erreurs de transport.

## Chaque cas reste visible

| Cas | Statut | Diagnostic |
| --- | --- | --- |
| generic-fr | model_found_no_supported_answer | L’autorité attendue n’est pas dans les cinq articles retrouvés ; le modèle s’abstient et ne lui substitue aucune réponse inventée. |
| generic-ar | model_found_no_supported_answer | L’article34 et le passage introductif pertinent sont fournis, mais le modèle s’abstient encore. |
| targeted151-fr | evidence_found | Une affirmation acceptée, citation originale exacte ; première relecture documentaire : soutenu. |
| targeted151-ar | insufficient_lexical_support | Le seuil lexical inchangé bloque la demande avant l’appel au générateur. |
| lookup151-fr | model_found_no_supported_answer | Le passage151 est fourni ; le modèle s’abstient encore sur cette demande très brève. |
| lookup151-ar | evidence_found | Une affirmation acceptée, citation arabe originale restituée avec sa typographie ; première relecture : soutenu. |

Aucun taux agrégé de performance ou de fidélité n’est calculé sur ces sondes hétérogènes. Le générique français conserve une absence de preuve attendue dans ses résultats. Le refus du générique arabe, malgré son passage pertinent, et celui de la consultation française restent des limites de réponse visibles. Le ciblé arabe expose séparément une limite de la politique lexicale existante ; aucun seuil n’a été abaissé pour le faire passer.

## Relecture des affirmations acceptées

La [première revue interne par claim](manual_review_primary.json) classe les affirmations acceptées des cas targeted151-fr et lookup151-ar comme **soutenues**. Chaque citation retournée est un substring exact du texte source local de l’édition du 31 mars 2022, avec conservation de la typographie originale dans la citation arabe. Cette vérification de présence ne remplace pas la lecture sémantique de l’affirmation contre la preuve.

La consultation arabe fournit un élément exact mais ne reproduit pas tout l’article. La couverture incomplète de cette réponse est distinguée du support complet de son unique affirmation. Les deux sorties reprennent essentiellement le passage disponible : elles ne démontrent pas une capacité générale de synthèse juridique.

Cette revue est une lecture documentaire interne, pas une annotation juridique indépendante. Les textes des affirmations, citations et articles examinés restent uniquement sous `outputs/generation-v3/`. Les fichiers publics donnent des verdicts et des raisons originales sans extraits. Une seconde relecture interne distincte est traitée séparément par un autre agent, sans connaître les premiers verdicts avant de rédiger les siens.

## Traçabilité et contrôles

Les [résultats par cas](results.json), le protocole, la revue et le [contrôle d’intégrité](integrity.json) sont conservés ensemble. Les empreintes historiques du 17 octobre, de V2 et des contrôles synthétiques sont inchangées. Aucun retry ou variante n’a suivi ce lot.

32 tests ciblés de génération et de rapports passent, dont une régression sur l’ordre réellement transmis au fournisseur ; Ruff est propre. Ces contrôles logiciels ne sont pas une mesure de qualité du modèle. Le préchargement séparé est celui du runner expérimental ; les contrats API et CLI existants n’ont pas été étendus.
