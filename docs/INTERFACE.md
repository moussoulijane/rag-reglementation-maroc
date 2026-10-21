# Interface Daftar — produit, copie et contrôle d'accessibilité

**Évolution du 21 octobre :** l’interface utilise désormais le profil V3. Le [guide actif](GUIDE_ASSISTANT_V3.md) décrit les cinq décisions et l’export. Les essais du 19 octobre ci-dessous documentent la version précédente.

Document de conception, de copie bilingue et de QA. L'interface consulte le moteur existant ; elle ne modifie ni ses seuils, ni ses sources, ni les ressources gelées du challenge. Le bilan ci-dessous distingue les essais exécutés des vérifications restant à réaliser.

## État de validation — 19 octobre 2026

Le build de production a été vérifié dans un navigateur réel. Le [bilan UI](../reports/ui/VALIDATION.md) conserve les conditions et les preuves ; les contrôles source et les tests logiciels complètent cette observation.

Les parcours essayés comprennent :

- La consultation directe « article 34 » renvoie cinq passages français, les pages PDF 24–25 et un lien officiel vers cette plage. « المادة 34 » renvoie quatre passages arabes, avec `lang="ar"` et lecture de droite à gauche. Ces exemples vérifient le raccordement documentaire, sans mesurer la qualité des réponses à des questions de fond.
- Le changement de langue de l'interface conserve la langue des preuves. Modifier le formulaire après un résultat ne change pas la question affichée avec ce résultat.
- Une question sur la règle actuelle reçoit un refus lié à l'édition, sans citations. L'état de chargement a été observé.
- La vue Sources montre les deux PDF, leurs empreintes, 197 articles et 84 pages chacun dans la session chargée. La copie d'empreinte affiche « Copié » ; l'historique en mémoire restaure un résultat et peut être effacé.
- Un second serveur lancé avec un dossier de données vide affiche les ressources indisponibles, l'envoi désactivé même après sélection d'un exemple et des articles « Non chargé ». Il a été arrêté après l'essai.
- L'aide se ferme avec Échap. Les options décrivent les scores comme des valeurs de classement sans probabilité ; le détail charge un classement réel.
- Sur mobile 390 × 844, l'interface arabe ne déborde pas horizontalement. Le menu s'ouvre en dialogue et se ferme lors du retour au format large.

La relecture source a vérifié les textes échappés, les labels et aides reliés aux champs, l'annonce brève des résultats, la langue des preuves et de la reformulation, les capacités dynamiques et l'absence de blocage de `localhost` par `navigator.onLine`.

**Périmètre restant.** Les erreurs HTTP 422/503 en cours de recherche n'ont pas été provoquées dans le navigateur. Ollama dans l'interface, un lecteur d'écran, un parcours clavier exhaustif, le format 320 px et le zoom 200 % restent à vérifier. Le Docker historique du 17 octobre ne valide pas cette interface. Aucun audit de conformité d'accessibilité n'est revendiqué.

## Brief produit

**Daftar est un espace de lecture documentaire bilingue.** L'utilisateur formule une question, retrouve les passages du texte et peut ouvrir leur source officielle datée. Un refus est un résultat lisible, avec sa raison et une action possible.

Sur grand écran, une zone principale accueille la question puis les extraits ; un rail plus étroit situe l'édition et les deux PDF. Sur mobile, ces éléments suivent une seule colonne. La hiérarchie vient de la typographie et des espacements, avec une base neutre et un seul accent discret. Les citations restent longues et lisibles ; aucun faux dialogue, avatar, score de confiance ou tableau de benchmark n'occupe ce parcours.

Le français et l'arabe sont deux langues de l'interface. Ce choix ne traduit ni la question, ni les textes cités. La langue des sources est un réglage distinct. La génération n'est accessible que comme option avancée explicitement expérimentale ; le défaut reste l'extraction du texte.

La date du **31 mars 2022** reste visible avant et après la recherche. « Source officielle » qualifie les PDF de Bank Al-Maghrib, sans présenter Daftar comme une application officielle de cette institution.

## Développement et lancement local

La nouvelle application `rag_reglementation_ui` réutilise l'API et le moteur existants, puis ajoute `/ui-config` et les fichiers statiques. La commande `rag-maroc serve` reste une entrée API ; pour voir Daftar, utiliser l'entrée UI ci-dessous. Aucun fichier du moteur évalué n'est modifié par le build frontend.

Préparer le corpus avec les commandes habituelles `download` et `ingest`, et réinstaller le package éditable après ajout de l'UI pour enregistrer `rag-maroc-ui` (`.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`). Node.js et npm sont nécessaires pour compiler le frontend ; Python et les dépendances du projet sont nécessaires au service. Depuis la racine du projet :

```powershell
Set-Location frontend
npm ci
npm run build
Set-Location ..
```

`npm ci` utilise le lockfile du frontend ; `npm run build` vérifie TypeScript puis prépare les assets dans `src/rag_reglementation_ui/static`. Ce sont les fichiers servis par l'application Python. Le build et la vérification navigateur exécutés sont décrits dans le [bilan UI](../reports/ui/VALIDATION.md).

Lancer ensuite la baseline, sans encodeur neuronal :

```powershell
$env:RAG_ENCODER = 'none'
.\.venv\Scripts\rag-maroc-ui.exe --host 127.0.0.1 --port 8000
```

Équivalent sans console script :

```powershell
.\.venv\Scripts\python.exe -m uvicorn rag_reglementation_ui.app:app --host 127.0.0.1 --port 8000
```

Ouvrir `http://127.0.0.1:8000/`. Si un ancien serveur utilise ce port, l'arrêter ou choisir un autre port. La documentation HTTP reste sous `/docs`. En l'absence d'assets compilés, la racine affiche un état de préparation et l'API reste accessible.

Pour les trois méthodes de recherche, préparer explicitement le modèle avant le lancement :

```powershell
.\.venv\Scripts\rag-maroc.exe prepare-model
$env:RAG_ENCODER = 'multilingual'
.\.venv\Scripts\rag-maroc-ui.exe --host 127.0.0.1 --port 8000
```

L'option Python `neural` doit déjà être installée. Le démarrage ne télécharge pas de poids. Cette sélection ne précharge pas Ollama ; le workflow de génération reste celui des [notes de déploiement](DEPLOYMENT.md).

## Contrat de capacité `/ui-config`

Cette route complète `/health` et `/ready` sans sonder Ollama. Elle décrit les objets chargés et les limites de la session.

| Champ | Usage de l'interface |
|---|---|
| `ready` | Active l'envoi lorsque la session est préparée ; ne promet pas que la prochaine requête réussira. |
| `available_modes` | Liste de référence des méthodes activables. Aucune valeur absente n'est présentée comme disponible. |
| `encoder.loaded`, `encoder.configured` | Distinguent demande de configuration et objet effectivement chargé. |
| `article_count`, `article_count_by_language` | Comptes du corpus effectivement chargé ; jamais remplacés par 394 ou 197 par défaut. |
| `sources[].article_count` | Peut être `null` pour une entrée du catalogue non chargée ; afficher « non chargé » ou omettre le compte. |
| `sources` | Titres, langues, URL officielles, édition, pages et empreintes exposées par le service. |
| `policy_status` | État des réglages de recherche ; ne signifie pas que le droit ou la réponse est validé. |
| `generators.choices` | Options configurées, pas une preuve de disponibilité en exécution. |
| `generators.ollama.availability` | `not_checked` : aucune sonde de santé ou de chargement du modèle n'a été effectuée. |
| `request_limits` | Limites des formulaires et nombre de résultats par défaut, dérivés du contrat HTTP. |

Si la configuration est inaccessible, ne pas afficher des capacités ou compteurs mémorisés comme s'ils étaient actuels. L'utilisateur peut conserver sa question puis relancer la vérification. Une erreur d'un POST reste traitée même après une configuration indiquée prête.

La calibration, si elle est détaillée dans les options avancées, se décrit comme « réglages ajustés sur développement » ou « non ajustés pour cet index ». Éviter « réponse certifiée », « corpus validé » et tout pourcentage de confiance.

## Copie du parcours

| Élément | Français | العربية |
|---|---|---|
| Titre de travail | Consulter la loi bancaire | الاطلاع على القانون البنكي |
| Invitation | Retrouvez un article, vérifiez la source. | اعثر على المادة وتحقق من مصدرها. |
| Label du champ | Votre question | سؤالك |
| Aide du champ | Écrivez en français ou en arabe. | اكتب بالعربية أو بالفرنسية. |
| Action principale | Rechercher dans les textes | البحث في النصوص |
| Langue des sources | Langue des textes consultés | لغة النصوص التي سيشملها البحث |
| Option automatique | Même langue que la question | نفس لغة السؤال |
| Section de preuves | Extraits du texte | مقاطع من النص |
| Source | Ouvrir le PDF officiel | فتح ملف PDF الرسمي |
| Date | Édition consultée : 31 mars 2022 | النسخة المعتمدة للبحث: 31 مارس 2022 |
| Périmètre | Cette édition ne confirme pas le droit applicable aujourd'hui. | هذه النسخة لا تؤكد الأحكام السارية حاليا. |
| Nouvelle recherche | Poser une autre question | طرح سؤال آخر |

Les exemples de questions peuvent remplir le champ à la demande. Ils ne doivent pas déclencher une recherche au chargement, ni être accompagnés d'une réponse de démonstration présentée comme un résultat réel.

## Réglages nommés simplement

| Valeur API | Libellé FR | Libellé AR | Explication FR |
|---|---|---|---|
| `bm25` | Mots du texte | كلمات النص | Retrouve les passages avec les termes de la question. |
| `semantic` | Sens de la question | معنى السؤال | Recherche des passages de sens proche, y compris entre les deux langues. |
| `hybrid` | Recherche combinée | بحث يجمع الطريقتين | Combine la recherche par mots et par sens. |
| `extractive` | Extraits du texte | مقاطع من النص | Affiche les passages de la source. |
| `ollama` | Reformulation expérimentale | إعادة صياغة تجريبية | Peut prendre plus de temps ou refuser ; les extraits restent la référence. |

Aide AR de l'option expérimentale : « قد تستغرق وقتا أطول أو ترفض الإجابة؛ تبقى مقاطع المصدر هي المرجع. »

Activer uniquement les modes présents dans `/ui-config.available_modes`. Désactiver les modes par sens si l'encodeur n'est pas disponible, avec un texte « Indisponible dans cette session » / « غير متاح في هذه الجلسة ». Ne pas basculer silencieusement vers une autre méthode. La capacité générative est décrite par `/ui-config`, avec disponibilité non vérifiée : un moteur prêt ne prouve pas qu'Ollama est chargé.

## États de la page

| État | Copie FR | Copie AR | Comportement |
|---|---|---|---|
| Avant la première question | Posez une question. Les extraits s'afficheront ici après la recherche. | اطرح سؤالك. ستظهر المقاطع هنا بعد البحث. | Aucun passage ou article fictif. |
| Vérification du service | Connexion au service local… | جار الاتصال بالخدمة المحلية… | Le champ reste utilisable ; l'envoi attend la préparation. |
| Recherche en cours | Recherche dans les textes… | جار البحث في النصوص… | Résumé annoncé, pas de pourcentage ni de phase simulée. |
| Option générative en cours | Recherche et reformulation en cours… | جار البحث وإعادة الصياغة… | Prévenir que cette option peut prendre plus de temps. |
| Service injoignable | Le service local est injoignable. Votre question est conservée. | تعذر الاتصال بالخدمة المحلية. تم الاحتفاظ بسؤالك. | Action Réessayer / إعادة المحاولة. |
| Ressources non prêtes | Les documents ou le modèle nécessaires ne sont pas disponibles dans cette session. | الوثائق أو النموذج اللازم غير متاح في هذه الجلسة. | Lien vers les instructions locales ; aucun compteur inventé. |
| Champ trop court | Écrivez une question d'au moins trois caractères utiles. | اكتب سؤالا يتضمن ثلاثة أحرف مفيدة على الأقل. | Erreur sous le champ, focus conservé. |
| Demande refusée en 422 | Cette demande n'a pas pu être traitée. Essayez une question plus courte ou une autre méthode disponible. | تعذرت معالجة هذا الطلب. جرب سؤالا أقصر أو طريقة بحث أخرى متاحة. | Ne pas afficher une trace technique ou remplacer la méthode sans accord. |
| Erreur de recherche en 503 | La recherche n'est pas disponible pour le moment. Votre question est conservée. | البحث غير متاح حاليا. تم الاحتفاظ بسؤالك. | L'état d'erreur du POST prime sur un ancien état prêt. |
| Résultat absent de `/search` | Aucun passage retrouvé dans les textes sélectionnés. | لم يُعثر على أي مقطع ضمن النصوص المختارة. | C'est une absence de résultats, pas une preuve d'absence de règle. |

Un échec réseau ne prouve pas que le serveur est arrêté : la connexion ou le proxy peuvent aussi être en cause. Un `/health` valide indique la vivacité ; `/ready` donne l'état de préparation connu par le service, sans garantir qu'une requête suivante réussira.

## Traduction complète des motifs de refus

Le statut `abstained` ne doit pas devenir un simple écran vide. Afficher un titre « Réponse non établie » / « لم يثبت جواب مسند », puis le motif correspondant.

| `reason` | Français | العربية |
|---|---|---|
| `edition_does_not_establish_current_law` | Cette édition du 31 mars 2022 ne permet pas de confirmer une règle ou une donnée actuelle. | لا يمكن تأكيد القاعدة أو المعلومة الحالية انطلاقا من هذه النسخة المؤرخة في 31 مارس 2022. |
| `no_evidence` | Aucun passage n'a été retrouvé pour cette question dans les textes sélectionnés. | لم يُعثر على مقطع يتعلق بهذا السؤال ضمن النصوص المختارة. |
| `requested_article_missing` | Au moins un des articles demandés n'a pas été retrouvé dans cette édition. | تعذر العثور على مادة واحدة على الأقل من المواد المطلوبة في هذه النسخة. |
| `insufficient_lexical_support` | Les passages retrouvés ne reprennent pas assez d'éléments de la question pour proposer une réponse. | لا تتضمن المقاطع المسترجعة عناصر كافية من كلمات السؤال لتقديم جواب مسند. |
| `insufficient_semantic_support` | Les passages retrouvés ne sont pas assez proches du sens de la question pour proposer une réponse étayée. | المقاطع المسترجعة ليست قريبة بما يكفي من معنى السؤال لتقديم جواب مسند. |
| `generator_not_configured` | La reformulation n'est pas disponible dans cette session. | إعادة الصياغة غير متاحة في هذه الجلسة. |
| `model_found_no_supported_answer` | La reformulation n'a pas produit de réponse appuyée sur les passages fournis. | لم تنتج إعادة الصياغة جوابا مستندا إلى المقاطع المقدمة. |
| `generator_unavailable` | Le service de reformulation est indisponible pour cette demande. | خدمة إعادة الصياغة غير متاحة لهذا الطلب. |
| `invalid_generated_citation_or_schema` | Les références ou la présentation de la reformulation n'ont pas pu être vérifiées. Elle n'est pas affichée. | تعذر التحقق من مراجع الصياغة أو تنسيقها، لذلك لم يُعرض نصها. |
| Valeur inconnue | Aucune réponse étayée n'a pu être affichée pour cette demande. | تعذر عرض جواب مسند لهذا الطلب. |

Un refus ne signifie pas que la question est juridiquement fausse ou que la règle n'existe nulle part. Pour une erreur générative, proposer explicitement de revenir aux extraits ; cette action relance `/ask` avec `generator="extractive"`. Ne pas inventer des citations dans un résultat refusé.

## Contrat technique à respecter

- `POST /ask` reçoit `question`, `source_language`, `mode`, `top_k` et `generator`. Le champ accepte 3 à 1500 caractères, mais l'encodeur a aussi sa limite de tokens : une question sous cette longueur peut encore recevoir un 422.
- Envoyer explicitement `generator="extractive"` lorsque l'option expérimentale est désactivée. Une valeur absente ou `null` hérite du réglage du serveur.
- `source_language=null` dans `/ask` utilise la langue détectée de la question. Dans `/search`, l'absence de filtre recherche dans les deux langues : ces deux comportements ne sont pas identiques.
- Le mode extractif renvoie un `answer` qui duplique les citations. Rendre les extraits comme tels, sans fabriquer une synthèse. En génération, séparer la reformulation et ses références.
- Les citations apportent `quote`, `article_id`, `language`, `source_url`, `version_date`, `page_start`, `page_end`, identifiants et empreinte. Le contenu affiché provient de ces champs ; aucune réponse de fixture ne remplace le service réel.
- Les pages couvrent l'**article**, pas nécessairement la page exacte du passage. Libellé : « Article {article_id} · pages PDF {page_start}–{page_end} », avec les valeurs réellement retournées. Un lien `#page=page_start` ouvre le début de cette plage.
- Conserver le texte cité original, y compris l'arabe ; pas de normalisation de preuve à l'affichage ou à la copie. Les numéros et URL peuvent être isolés avec `bdi`.
- `score_is_probability=false`, scores, rangs, seuils et `latency_ms` ne deviennent pas un score de confiance ou une mesure de vérité. Les résultats du challenge restent dans la documentation de recherche.
- Une nouvelle question doit être associée à sa propre réponse. Ignorer les réponses réseau anciennes après une soumission plus récente. Annuler un fetch n'atteste pas que le calcul serveur est arrêté.
- Tous les contenus de question, citation et réponse restent du texte échappé. Ne pas injecter de HTML issu de ces champs.
- `navigator.onLine` fournit un indice de connexion, sans diagnostiquer l’accès à l’API locale. Ne pas bloquer une requête vers `localhost` sur ce seul indicateur ; voir [MDN, Navigator.onLine](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/onLine).

## Checklist fonctionnelle et accessible

### Parcours et données

- [ ] FR : saisir une question, soumettre, recevoir les passages réels et ouvrir le PDF officiel.
- [ ] AR : saisir en arabe, lire la réponse et copier une citation sans inversion des caractères.
- [ ] Croiser la langue de question et celle des sources ; vérifier le filtre et les citations effectivement reçues.
- [ ] Basculer l'interface FR/AR sans modifier ni traduire la question déjà saisie.
- [ ] Vérifier les neuf motifs de refus et un motif inconnu ; aucun ne montre de fausse citation.
- [ ] API absente, ressources non prêtes, résultats vides, 422 et 503 : question et réglages conservés.
- [ ] Mode par sens indisponible : contrôle désactivé, raison lisible, aucune substitution silencieuse.
- [ ] Option générative désactivée : payload explicitement extractif. Activée : traitement présenté comme expérimental.
- [ ] Deux requêtes rapprochées : une réponse ancienne ne remplace pas la dernière demande.
- [ ] Aucun benchmark, faux pourcentage de progression ou score de confiance dans le parcours.

### Clavier, lecture et direction

- [ ] Labels visibles au-dessus des champs ; aides et erreurs reliées par `aria-describedby`.
- [ ] Boutons, sélecteurs et accordéons utilisables au clavier ; focus toujours visible.
- [ ] DOM dans l'ordre question → réglages → action → état → résultat → preuves, même avec un rail visuel.
- [ ] Statuts brefs annoncés par `aria-live="polite"`, sans relire automatiquement tous les passages.
- [ ] Le document porte `lang` et `dir` adaptés ; question en `dir="auto"`, chaque preuve avec sa propre langue/direction.
- [ ] Les nombres, dates, numéros `19bis` et URL restent lisibles au sein d'une phrase arabe.
- [ ] À 320 px et au zoom 200 %, aucune perte de contenu ni débordement horizontal des textes et URL.
- [ ] Taille de lecture confortable, interligne suffisant pour les glyphes arabes ; pas de tracking serré.
- [ ] Contraste du texte courant au moins 4,5:1 ; ne pas rendre les métadonnées essentielles illisibles en gris pâle. Voir [W3C, contraste](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
- [ ] Cibles tactiles visées à 44 × 44 px ; le minimum WCAG 2.2 est de 24 px avec exceptions, sans confondre cette cible projet avec une certification. Voir [W3C, tailles de cible](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).
- [ ] Réduction des animations respectée via `prefers-reduced-motion` ; pas de texte qui défile ou se tape automatiquement.
- [ ] Un état de succès/refus ne dépend pas uniquement d'une couleur.

Le sens de lecture s'exprime dans le balisage HTML, pas seulement par l'alignement CSS ; voir [W3C, textes de droite à gauche](https://www.w3.org/International/questions/qa-html-dir). Cette liste reste une grille complète pour les prochaines vérifications ; le bilan en tête précise les seuls essais déjà exécutés. Elle ne revendique aucune conformité auditée.

