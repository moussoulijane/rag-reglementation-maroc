# Sources, édition et qualité du corpus

Le premier jalon utilise deux documents officiels publiés par **Bank Al-Maghrib** : la loi n° 103-12 relative aux établissements de crédit et organismes assimilés, en français et en arabe. Les deux couvertures annoncent une édition consolidée au **31 mars 2022**. Le projet interroge cette édition documentaire ; il ne détermine pas le droit applicable aujourd’hui et ne fournit pas une consultation juridique.

## Sources exactes

[Page officielle de la loi bancaire](https://www.bkam.ma/fr/Trouvez-l-information-concernant/Reglementation/Loi-bancaire).

| Identifiant | Document officiel | Édition | Pages PDF | SHA-256 |
|---|---|---|---:|---|
| `bam-10312-fr` | [PDF français](https://www.bkam.ma/fr/content/download/757666/8545663/loi%20bancaire%20fr.pdf) | 2022-03-31 | 84 | `663038cf056a377d9f7ab1d31ad1136077440c8bcada92ee9c116ef41791a56a` |
| `bam-10312-ar` | [PDF arabe](https://www.bkam.ma/ar/content/download/757666/8545665/loi%20bancaire%20ar%2022%20V2%20web.pdf) | 2022-03-31 | 84 | `ac1453c87ee9ecd17a29c0e47320686d75ecd4d5b4d34099b903ccddcc2cd790` |

Les fichiers ont été consultés le **16 octobre 2026**. Les dates de création informatiques des PDF se situent en juin 2022 ; elles ne remplacent pas la date d’édition indiquée dans le document. Le catalogue lie les URL aux empreintes exactes. Une modification distante fait échouer la vérification au lieu de changer silencieusement le corpus.

Chaque langue comporte **197 articles** : les articles 1 à 196 et l’article **19 bis**. L’identifiant commun est `law-103-12` ; l’identifiant stable d’un article est, par exemple, `bam-10312-fr:article-34`. Les versions linguistiques sont reliées par ce numéro d’article, jamais par leur position sur une page.

## Préparation locale et intégrité

`download_sources(data_dir)` enregistre les PDF dans `data/raw/`. Un fichier déjà présent est réutilisé seulement après une nouvelle vérification SHA-256. Les téléchargements utilisent HTTPS avec la vérification TLS normale, un délai maximal et une limite de taille. Une réponse HTML ou un PDF différent est rejeté.

`ingest_sources(data_dir)` vérifie à nouveau les octets avant l’extraction avec **pypdf 6.21.0**, puis écrit `data/processed/articles.jsonl` et `quality.json`. Le rapport contient les sources et leurs empreintes, le nombre de pages, les comptes d’articles, les limites connues et l’empreinte du JSONL. Aucun modèle linguistique ne reconstruit les passages manquants.

`load_articles(path)` exige le rapport de qualité associé. Il contrôle l’intégrité du cache, le schéma Pydantic, les identifiants uniques, les deux séquences complètes et les empreintes de provenance. Ces contrôles détectent les modifications accidentelles du cache ; ils ne sont pas une signature cryptographique contre un attaquant capable de réécrire à la fois données et rapport.

## Pourquoi l’extraction n’est pas une simple expression régulière

Les exposants des notes de bas de page se collent parfois aux numéros. Dans le PDF français, `Article 111` page 10 représente l’article **11**, suivi de l’appel de note **1**. Le véritable article **111** apparaît page 53. Le même problème distingue l’article 19 suivi de la note 2 du véritable article 192. L’article 19 bis possède lui aussi un appel de note.

Le parseur applique une table auditée par **langue, page PDF et titre extrait** pour les onze titres annotés de chaque langue. Il lit les autres numéros présents dans le texte. Il ne distribue jamais les numéros en fonction d’un compteur. La liste finale doit respecter exactement l’ordre `1…19, 19bis, 20…196` ; un titre inconnu, une omission, une répétition ou une permutation fait échouer l’ingestion.

Les numéros arabes peuvent précéder le mot « المادة » dans l’ordre extrait ; les appels de notes peuvent aussi le précéder. La tolérance aux espaces concerne ces titres audités. La normalisation destinée à la recherche reste séparée du texte conservé pour les citations.

Les quatre premières pages contiennent les couvertures et la présentation éditoriale. Elles ne sont pas traitées comme des articles. Les folios et titres courants identifiés sont retirés. Les références de page sont toujours celles du **PDF, à partir de 1** : l’article 150 se trouve page 66 en français et page 67 en arabe ; l’article 157 couvre les pages 68–69 en français et la page 69 en arabe.

## Limites à garder visibles

- Les notes de bas de page sont conservées dans les corps extraits. Selon leur position, une note peut être rattachée au dernier article de la page plutôt qu’à l’article dont elle décrit la modification. Il faut consulter le PDF pour une lecture juridique de ces notes.
- Le texte arabe provient de la couche textuelle du PDF. Il garde ses particularités typographiques et l’ordre d’extraction de pypdf. Une bonne récupération d’article ne garantit pas une transcription parfaite de chaque glyphe.
- Les deux langues constituent des versions documentaires du même texte : leurs scores d’évaluation ne représentent pas deux lois indépendantes.
- Les taux, ratios, décisions et évolutions postérieurs ou absents de cette édition sont hors corpus. Par exemple, l’article 157 établit le dispositif de réclamation, mais le délai de 40 jours ne figure pas dans cet article : le système ne doit pas l’inventer.

## Réutilisation et publication du dépôt

Les [mentions légales de Bank Al-Maghrib](https://www.bkam.ma/Mentions-legales) revendiquent des droits sur le site et les documents qu’il contient et indiquent une interdiction de reproduction du site. Aucune licence ouverte applicable à ces PDF n’a été constatée. Le code du projet et les questions d’évaluation originales ont leur propre licence ; cette licence ne s’étend pas aux documents de Bank Al-Maghrib.

Le dépôt conserve donc les URL, empreintes, paramètres, code et questions originales. **Les PDF, textes intégraux extraits et index restent locaux sous `data/`, ignoré par Git.** Leur disponibilité publique ne constitue pas une attribution de licence libre. Cette séparation est un choix de publication du projet, sans prétendre trancher le régime juridique des textes officiels.

## Extensions identifiées, hors corpus initial

Deux circulaires associées sont proposées sur la [page réglementaire des relations avec la clientèle](https://www.bkam.ma/fr/Trouvez-l-information-concernant/Reglementation/Activite-des-etablissements-de-credit-et-assimiles/Reglementation-des-relations-etablissements-de-credit-clientele) :

- [Circulaire 9/W/2016 du 10 juin 2016, médiation bancaire](https://www.bkam.ma/fr/content/download/746662/8469174/Circulaire%20n%C2%B0%209%20W%2016%20modalit%C3%A9s%20de%20fonctionnement%20du%20dispositif%20de%20m%C3%A9diation%20bancaire.pdf).
- [Circulaire 10/W/2016 du 10 juin 2016, traitement des réclamations](https://www.bkam.ma/fr/content/download/746673/8469196/Circulaire%20n%C2%B010%20W%202016%20relative%20aux%20modalit%C3%A9s%20de%20traitement%20des%20r%C3%A9clamations.pdf).

Les deux fichiers testés comportent trois pages scannées chacun et aucune couche textuelle utilisable par pypdf. Leur ajout exige une étape OCR suivie d’une vérification humaine, ainsi qu’un nouveau catalogue et une nouvelle évaluation. Le premier jalon ne prétend pas les couvrir.

## Extension documentaire V3 — 21 octobre 2026

La V3 extrait 24 articles des pages 1144–1148 du recueil BAM de fin 2023. Ces pages ont été rendues et comparées à leur couche textuelle. Les PDF individuels et le recueil diffèrent en rédaction et numérotation ; ils ne sont pas fusionnés. Seule la version du recueil est active pour les nouvelles circulaires. La précision mensuelle de l’édition est conservée, avec les dates de signature et publication séparées. L’actualité et l’arbitrage juridique entre versions restent non établis. Voir le [bilan V3](../reports/assistant-v3/IMPLEMENTATION.md).
