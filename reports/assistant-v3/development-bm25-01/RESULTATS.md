# Diagnostic de développement — assistant V3

35 groupes, 70 variantes FR/AR, mode bm25.

- Statut conforme aux annotations internes : 64/70.
- Réponses annoncées complètes à tort : 1/26 cas attendus non complets.
- Cas complets avec les faits attendus : 39/44.
- Validité mécanique des citations : True.

## Erreurs observées

- complaint-unit / ar : attendu complete, obtenu ambiguous.
- complaint-system / fr : attendu complete, obtenu partial.
- complaint-training / fr : attendu complete, obtenu partial.
- complaint-information / fr : attendu complete, obtenu partial.
- complaint-duty / ar : attendu complete, obtenu ambiguous.
- partial-mandate / fr : attendu partial, obtenu complete.

## Limites

- Questions et catalogue préparés en développement ; pas de test tenu à l’écart.
- La présence des faits attendus vérifie le contrat du catalogue, pas la fidélité sémantique générale.
- Les variantes FR/AR sont corrélées ; aucun gain universel sur V2 ne peut en être déduit.
- Le profil a été rétréci et le corpus élargi : comparaison causale à corpus constant requise.
