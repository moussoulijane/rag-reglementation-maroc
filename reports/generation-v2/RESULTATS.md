# Génération locale V2 : lot fixé du 18 octobre 2026

Le transport local fonctionne après préchargement séparé ; la génération de réponses reste non validée. Aucun claim n’a été accepté dans ce lot. Les résultats du17octobre sont conservés intégralement.

Le [protocole](protocol.json) a été fixé le18octobre à22:14:20UTC avant tout appel de génération. Le lot comprend les deux questions génériques précédentes, les deux questions ciblées précédentes et deux consultations directes de l’article151. Ces six sondes hétérogènes ne constituent pas un benchmark de fidélité ; aucun taux de performance agrégé n’est calculé.

## Conditions et diagnostic du délai précédent

Modèle existant : Qwen2.5:7b, quantificationQ4_K_M, digest fixé. Aucun autre modèle téléchargé. Recherche, passages, encodeur, seuils et politique d’abstention inchangés. Contexte4096tokens, sortie maximale900tokens, température0, seed7. Aucun processus Docker/vmmem observé pendant ce lot.

Le journal Ollama du17octobre montre une fermeture de connexion client avant la fin du chargement, puis son annulation. Cela établit une interruption du chargement à froid, sans démontrer une insuffisance mémoire. Le nouveau runner sépare le chargement, avec un délai client de360secondes, des appels mesurés, qui gardent leur délai de180secondes. Le [préchargement par requête vide et keep_alive](https://docs.ollama.com/faq#how-can-i-preload-a-model-into-ollama-to-get-faster-response-times) est documenté par Ollama.

Le préchargement a terminé en9,236secondes. Les cinq générations tentées ont répondu en0,64à1,59seconde ; le sixième cas a été rejeté avant appel au modèle. Aucun nouveau timeout n’a été observé. Ces observations ne suffisent pas à attribuer le délai précédent à Docker ou à une autre contention.

## Résultats conservés

| Cas | Recherche | Résultat | Diagnostic |
| --- | --- | --- | --- |
| generic-fr | hybrid | model_found_no_supported_answer | Article34 absent des cinq ancres ; abstention du modèle cohérente avec cette absence de preuve de l’autorité compétente. |
| generic-ar | hybrid | model_found_no_supported_answer | Article34 et son introduction présents après expansion finale ; le modèle s’abstient malgré cette preuve pertinente. |
| targeted151-fr | bm25 | model_found_no_supported_answer | Passage151 français intégral fourni ; abstention structurée malgré la présence des deux éléments demandés. |
| targeted151-ar | bm25 | insufficient_lexical_support | Question rejetée avant Qwen par la politique lexicale inchangée ; aucune génération pour ce cas. |
| lookup151-fr | bm25 | model_found_no_supported_answer | Consultation directe151 avec passage français intégral ; le modèle renvoie une abstention. |
| lookup151-ar | bm25 | model_found_no_supported_answer | Consultation directe151 avec passage arabe intégral ; le modèle renvoie une abstention. |

Les réponses fournisseur étaient des abstentions JSON valides, avec arrêt normal. Les journaux locaux ne montrent ni dépassement du budget de sortie ni citation refusée : aucun claim n’a été produit. Le cas ciblé arabe n’a pas appelé Qwen, car son chevauchement lexical reste inférieur au seuil fixé.

## Inspection interne des preuves et de la configuration

La relecture interne des passages complets de l’article151, en français et en arabe, confirme la présence des éléments demandés. Les consultations directes reçoivent également ce passage. L’abstention systématique ne peut donc pas être expliquée par une absence de preuve dans tous les cas. Cette lecture documentaire interne n’est pas une annotation juridique indépendante. Aucun claim accepté n’était disponible pour une relecture de fidélité.

L’inspection en lecture seule de la configuration renvoie le système standard de Qwen, aucun paramètre supplémentaire et un templateChatML. Les requêtes exactes ont été reconstruites hors réseau, avec le code figé et les passages enregistrés. Les cas151 reçoivent un unique passage complet ; leur volume de contexte reste largement inférieur à4096tokens. Le format JSON, le prompt et le traitement du message système sont des pistes de diagnostic, sans cause démontrée à ce stade.

Les requêtes reconstruites, textes sources, sorties fournisseur et métriques détaillées restent sous `outputs/generation-v2/`, ignoré parGit. Le rapport public contient uniquement les questions originales, statuts, identifiants et diagnostics. Les fichiers [results.json](results.json) et [diagnosis.json](diagnosis.json) conservent ces observations sans extraits de la loi.

Aucun réessai ou changement de seuil n’a suivi ces résultats. Les éventuels contrôles synthétiques de développement doivent faire l’objet d’un protocole distinct fixé avant leurs appels.

## Validation logicielle

31tests ciblés de génération et de rapports passent ; Ruff est propre. Les tests vérifient notamment la conservation des ancres, les introductions, le retour à des substrings sources originaux après normalisation typographique, les refus de citations altérées et les diagnostics de timeout. Ils ne démontrent pas la fidélité d’un modèle génératif.
