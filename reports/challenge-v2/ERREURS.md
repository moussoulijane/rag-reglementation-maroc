# Analyse des erreurs — nouveaux thèmes

Les scores complets et les quatre directions sont dans [RESULTATS.md](RESULTATS.md). Les effectifs ci-dessous portent sur des couples question/langue-source corrélés.

| Mode | Rappel incomplet sur positifs | Positifs acceptés avec rappel incomplet | Positifs refusés malgré rappel complet | Négatifs acceptés |
| --- | ---: | ---: | ---: | ---: |
| bm25 | 27 | 0 | 3 | 6 |
| semantic | 5 | 4 | 5 | 12 |
| hybrid | 6 | 6 | 1 | 15 |

Un article retrouvé peut ne pas contenir le passage utile dans le contexte sélectionné. Une question positive acceptée sans tous les articles annotés doit être relue ; cela ne suffit pas à conclure que la réponse aurait été fausse, car le gold peut être incomplet. Un négatif accepté signale que la garde d'abstention n'a pas reconnu l'insuffisance du corpus.

## Négatifs acceptés

### bm25

- v2_n01_cyber_incident_deadline — fr->fr (related_missing_operational_rule)
- v2_n01_cyber_incident_deadline — ar->ar (related_missing_operational_rule)
- v2_n02_recovery_plan_template — fr->fr (related_missing_template)
- v2_n02_recovery_plan_template — ar->ar (related_missing_template)
- v2_n05_bank_swift_directory — ar->ar (commercial_directory_fact)
- v2_n07_deposit_guarantee_numeric_cap — fr->fr (related_missing_numeric_parameter)

### semantic

- v2_n01_cyber_incident_deadline — fr->fr (related_missing_operational_rule)
- v2_n01_cyber_incident_deadline — ar->ar (related_missing_operational_rule)
- v2_n02_recovery_plan_template — fr->fr (related_missing_template)
- v2_n02_recovery_plan_template — ar->ar (related_missing_template)
- v2_n07_deposit_guarantee_numeric_cap — fr->fr (related_missing_numeric_parameter)
- v2_n07_deposit_guarantee_numeric_cap — ar->ar (related_missing_numeric_parameter)
- v2_n07_deposit_guarantee_numeric_cap — fr->ar (related_missing_numeric_parameter)
- v2_n07_deposit_guarantee_numeric_cap — ar->fr (related_missing_numeric_parameter)
- v2_n08_open_banking_api_contract — fr->fr (missing_technical_interface_contract)
- v2_n08_open_banking_api_contract — ar->ar (missing_technical_interface_contract)
- v2_n08_open_banking_api_contract — fr->ar (missing_technical_interface_contract)
- v2_n08_open_banking_api_contract — ar->fr (missing_technical_interface_contract)

### hybrid

- v2_n01_cyber_incident_deadline — fr->fr (related_missing_operational_rule)
- v2_n01_cyber_incident_deadline — ar->ar (related_missing_operational_rule)
- v2_n01_cyber_incident_deadline — ar->fr (related_missing_operational_rule)
- v2_n02_recovery_plan_template — fr->fr (related_missing_template)
- v2_n02_recovery_plan_template — ar->ar (related_missing_template)
- v2_n02_recovery_plan_template — fr->ar (related_missing_template)
- v2_n02_recovery_plan_template — ar->fr (related_missing_template)
- v2_n07_deposit_guarantee_numeric_cap — fr->fr (related_missing_numeric_parameter)
- v2_n07_deposit_guarantee_numeric_cap — ar->ar (related_missing_numeric_parameter)
- v2_n07_deposit_guarantee_numeric_cap — fr->ar (related_missing_numeric_parameter)
- v2_n07_deposit_guarantee_numeric_cap — ar->fr (related_missing_numeric_parameter)
- v2_n08_open_banking_api_contract — fr->fr (missing_technical_interface_contract)
- v2_n08_open_banking_api_contract — ar->ar (missing_technical_interface_contract)
- v2_n08_open_banking_api_contract — fr->ar (missing_technical_interface_contract)
- v2_n08_open_banking_api_contract — ar->fr (missing_technical_interface_contract)

Conserver ces résultats avant tout changement de seuil ou de classement. Une correction motivée par ce lot rend sa prochaine exécution exploratoire. La fidélité d'une réponse générée reste une mesure distincte. Les identifiants de tous les cas concernés sont dans [error_analysis.json](error_analysis.json).
