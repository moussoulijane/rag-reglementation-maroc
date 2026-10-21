# Contrôles synthétiques de développement du générateur

Cette phase est distincte du lot bancaire V2 échoué. Son [protocole](protocol.json) a été fixé avant les appels le18octobre2026 à22:20:23UTC. Il utilise uniquement un fait inventé : le code de l’agence fictive Lumen est ORION-42. Aucun texte de la loi ni nouveau thème du challenge n’est utilisé. Chaque contrôle a été exécuté une fois, sans retry, avec le même modèle et les mêmes options déterministes.

| Contrôle | Sortie observée |
| --- | --- |
| Schéma de production, français | Abstention |
| Schéma de production, arabe | Abstention |
| Mêmes messages français, champ format supprimé | Abstention |
| Mêmes instructions/preuve/schéma, endpoint generate avec system+prompt | Abstention |
| Mêmes messages français, schéma réordonné : claims avant abstain | Réponse ORION-42, abstain=false |
| Contrat minimal sans branche d’abstention, instructions adaptées | Réponse ORION-42 |

Le contraste le plus informant conserve la question, la preuve, les consignes, le modèle et les options ; seul l’ordre des propriétés et des champs requis du schéma change. Il soutient l’hypothèse d’une décision d’abstention prématurée liée à l’ordre de génération. Il ne démontre pas un défaut du parseur Ollama : le contrôle sans format s’abstient également. Le contrôle par l’endpoint generate ne soutient pas une explication limitée au template chat.

Les deux réponses synthétiques contenant le fait attendu ont des identifiants de preuve connus et des citations retrouvées exactement dans le passage inventé. La relecture interne confirme le fait ORION-42 ; elle ne mesure aucune capacité juridique ou fidélité générale. Le contrôle minimal modifie à la fois le contrat et les instructions, donc ne permet pas d’attribuer son résultat au seul schéma.

Recommandation : pour une correction de génération versionnée séparément, transmettre les champs claims avant abstain, sans modifier les décisions d’abstention amont ni les seuils. Toute nouvelle confrontation bancaire doit être fixée dans un protocole distinct avant ses appels. Les résultats V2 échoués restent inchangés. Une réussite sur ce fait synthétique ne remplace aucune évaluation bancaire.

Les sorties fournisseur détaillées restent sous outputs/generation-development-controls/. Les [résultats](results.json) et le [diagnostic](diagnosis.json) ne contiennent aucun corpus bancaire. answering.py et les artefacts V2 ont les mêmes empreintes qu’avant les contrôles.
