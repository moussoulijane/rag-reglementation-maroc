# Atelier — comprendre l'évaluation sur de nouveaux thèmes

Cet atelier complète le [guide en dix séances](GUIDE_PAS_A_PAS.md). Son objectif est de te faire expliquer pourquoi un bon score sur un jeu déjà consulté ne suffit pas à établir que la correction se généralise.

## 1. Distinguer diagnostic et nouvelle mesure

Le premier test avait révélé des problèmes de préparation du texte arabe. Corriger ces problèmes puis relancer les mêmes questions fournit un diagnostic utile. Ces questions ont cependant participé au développement du système.

Le challenge V2 ajoute de nouveaux thèmes, rédigés sans consulter les classements du moteur. Un second agent relit les annotations contre les articles du corpus. Cette relecture est interne ; elle ne remplace pas l'arbitrage d'un juriste indépendant.

Les quatre directions FR→FR, AR→AR, FR→AR et AR→FR d'un thème sont liées. Quatre variantes d'une même question ne deviennent pas quatre expériences indépendantes.

## 2. Comprendre le transfert des seuils

Les seuils de refus ont été choisis sur le développement du premier benchmark. Nous les gardons pour le challenge V2, avec exactement le même moteur et le même index. Nous ne cherchons pas les meilleurs seuils sur ces nouvelles questions.

Le parcours habituel de la CLI reste strict : une politique d'un autre benchmark ne peut pas être utilisée silencieusement. Le nouveau parcours nécessite un manifeste explicite qui rattache le nouveau jeu à sa calibration d'origine et à l'audit des annotations.

Lis [evaluation_manifest.py](../src/rag_reglementation_maroc/evaluation_manifest.py) puis repère les contrôles suivants :

- questions, politique, origine et audit inchangés depuis leur gel ;
- mêmes fichiers Python et même empreinte du moteur ;
- groupes, identifiants et formulations absents du benchmark d'origine ;
- quatre directions cohérentes par groupe ;
- articles annotés présents dans la langue et l'édition demandées ;
- modes réellement calibrés, cinq articles recherchés ;
- nouveau dossier de résultats, sans écraser une ancienne exécution.

La disjonction des identifiants ne prouve pas, à elle seule, que les thèmes diffèrent. C'est la raison de la relecture des questions avant exécution.

## 3. Lire le manifeste

Un manifeste contient des empreintes SHA-256. Une empreinte change dès que les octets du fichier changent : elle permet de détecter une modification après le gel. Elle n'atteste pas que les annotations sont justes et ne constitue pas un préenregistrement externe.

Les règles de [.gitattributes](../.gitattributes) préservent les octets des fichiers gelés : une conversion automatique CRLF/LF changerait sinon leurs empreintes. Une édition qui ne change que les fins de ligne peut donc suffire à invalider un gel.

La CLI vérifie ces empreintes avant d'appeler le moteur sur le challenge. Le rapport conserve séparément l'empreinte des questions testées et celle du benchmark sur lequel les seuils ont été calibrés.

Le [protocole V2](CHALLENGE_V2.md) décrit les commandes et les ressources de cette expérience. Les scripts ne rendent pas acceptable une modification des questions motivée par un mauvais classement.

## 4. Examiner les erreurs avant de modifier

Après la première exécution, conserve les résultats et réponds à ces questions :

1. Quels articles attendus manquent dans les cinq premiers résultats ?
2. Le passage choisi contient-il réellement la proposition nécessaire ?
3. Quelles questions positives sont refusées malgré un bon article retrouvé ?
4. Quelles questions hors corpus sont acceptées ?
5. Les écarts concernent-ils surtout l'arabe, la traduction ou les thèmes eux-mêmes ?

Une correction issue de cette analyse doit être développée sur des exemples de développement, puis mesurée sur un autre jeu encore inédit. Une nouvelle exécution du challenge V2 après cette correction redevient exploratoire.

## 5. Séparer le générateur et le moteur

Retrouver un article, accepter ses preuves et rédiger une réponse sont trois étapes différentes. Un test HTTP réussi prouve que les composants communiquent. Une citation présente dans la source prouve l'existence de l'extrait. Pour juger une paraphrase, il faut encore examiner ce qu'elle affirme et ce qu'elle omet.

Un échec de chargement de modèle, une abstention du filtre lexical et une abstention décidée par Qwen doivent être enregistrés séparément. Augmenter le délai de chargement n'améliore pas automatiquement la fidélité d'une réponse.

**Exercice.** Le rappel augmente sur un nouveau jeu, mais le moteur accepte davantage de négatifs proches du corpus. Peux-tu conclure à une amélioration globale ?

**Correction.** Il faut présenter les deux effets, leurs effectifs, les directions linguistiques et les erreurs. Un rappel supérieur ne compense pas automatiquement une hausse des réponses non étayées. Des jeux de questions différents ne permettent pas non plus d'attribuer causalement un écart de score à une modification du moteur.

Le manifeste de cette livraison existe déjà. Pour reproduire ses résultats, conserve-le et exécute la commande d'évaluation dans un nouveau dossier de sortie ; il n'est pas nécessaire de le régénérer. Le script de gel refuse d'écraser un manifeste existant. Une nouvelle expérience modifiée doit recevoir sa propre trace, avec un statut approprié à l'utilisation des questions.
