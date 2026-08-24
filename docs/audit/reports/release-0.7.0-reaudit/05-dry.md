# Rapport d'audit : DRY (Don't Repeat Yourself)

> **Re-audit de release/0.7.0 @ 94eec28 — score 67 → 67** (aucun mouvement de note :
> l'item 5.1 reste non conforme malgre la resolution de la palette couleur, car la
> seconde duplication qui le declenchait — le helper datetime copie 7x — subsiste.)

**Release** : 0.7.0
**Date** : 2026-08-24
**Auditeur** : claude-code

---

## Score de compliance

| Metrique | Valeur |
|----------|--------|
| Items conformes | 5 / 7 |
| Score | 67 / 100 |
| Ecarts CRITICAL | 0 |
| Ecarts MAJOR | 2 |
| Ecarts MINOR | 2 |
| Ecarts INFO | 2 |

Poids total de la checklist : 12. Poids conformes : 8 (les items 5.1 et 5.3,
poids 2 chacun, restent non conformes). `score = 8 / 12 * 100 = 67`.

| # | Item | Poids | Conforme | Evolution |
|---|------|-------|----------|-----------|
| 5.1 | Aucun bloc identique/quasi-identique 3+ fois sans factorisation | 2 | **Non** | Palette couleur levee (05a) ; helper datetime 7x subsiste (05b) → item toujours NON |
| 5.2 | Types partages centralises (`shared/types.ts` / `domain/models.py`) | 2 | Oui | Inchange |
| 5.3 | Pas de magic numbers/strings eparpilles — constantes nommees et centralisees | 2 | **Non** | Couleurs UI en dur non levees (05c) |
| 5.4 | Logique reactive partagee dans `shared/composables/` | 1 | Oui | Inchange |
| 5.5 | Appels API sans duplication de config HTTP — centralises dans `shared/api/http.ts` | 2 | Oui | Inchange |
| 5.6 | Schemas Pydantic transforment le domain, ne le redefinissent pas | 2 | Oui | Inchange |
| 5.7 | Regles de validation definies a un seul endroit (pas de desaccord front/back) | 1 | Oui | Inchange |

---

## Etat de la remediation (rappel du 1er audit : 3 MAJ, 2 MIN, 2 INFO — score 67)

| Ecart initial | Item | Statut au re-audit | Verification |
|---------------|------|--------------------|--------------|
| Palette `ELEMENT_COLORS` redeclaree 4x (05a) | 5.1 / 5.3 | **RESOLU** | Source unique `frontend/src/shared/elementColors.ts:14` ; les 3 composants `analysis` importent la constante, aucune redeclaration locale |
| Helper `_parse_iso`/`_parse_dt` copie 7x + divergence UTC `analysis_repo` (05b) | 5.1 | **NON RESOLU** | 7 definitions toujours presentes ; `analysis_repo.py:11` diverge encore (pas de coercition UTC) |
| Couleurs UI en dur + tokens `--color-*` inexistants (05c) | 5.3 | **NON RESOLU** | Namespace `--color-border`/`--color-text-muted` toujours reference et jamais defini ; `#d1d5db` x7, `#6b7280` x12, `#dc2626` x11 subsistent |

---

## Ecarts constates

### [MAJ] Helper de parsing ISO-datetime copie-colle dans 7 repositories (non resolu)

- **Localisation** : `document-parser/persistence/document_repo.py:12`, `document-parser/persistence/chunk_repo.py:14`, `document-parser/persistence/chunk_edit_repo.py:13`, `document-parser/persistence/document_store_link_repo.py:12`, `document-parser/persistence/document_version_repo.py:13`, `document-parser/persistence/store_repo.py:29`, `document-parser/persistence/analysis_repo.py:11`
- **Constat** : la meme fonction utilitaire de conversion ISO→`datetime` est toujours reimplementee a l'identique dans quatre repos optionnels (`document_repo`, `chunk_repo`, `chunk_edit_repo`, `document_store_link_repo` — corps strictement identique : garde `None`/`""`, `datetime.fromisoformat`, coercition `tzinfo`→UTC si naive), plus une variante non-optionnelle dans `document_version_repo:13` et une variante acceptant `str | datetime` dans `store_repo:29`. Sept copies au total. `analysis_repo._parse_dt` (`analysis_repo.py:11-15`) **diverge toujours** : il n'applique PAS la coercition `tzinfo`→UTC des six autres (`return datetime.fromisoformat(value)` seul), donc `AnalysisJob.started_at`/`completed_at` peut ressortir naive la ou tous les autres agregats ressortent aware. Aucun module `persistence/_datetime.py` ni helper partage dans `persistence/database.py` n'a ete introduit ; aucun repo n'importe de fonction commune.
- **Regle violee** : item 5.1 — « Aucun bloc de code identique ou quasi-identique n'apparait 3+ fois sans etre factorise » (poids 2).
- **Remediation** : extraire un unique `parse_iso(value: str | datetime | None, *, default_utc: bool) -> datetime | None` dans `persistence/database.py` (ou `persistence/_datetime.py` dedie) consomme par tous les `_row_to_*`, et aligner `analysis_repo` sur la coercition UTC pour supprimer la divergence de comportement.

### [MAJ] Couleurs UI en dur et tokens `--color-*` non definis, eparpilles (non resolu)

- **Localisation** : `frontend/src/features/store/ui/StoreForm.vue:389` `:394` `:401` `:405` `:414` `:454` `:475` `:487` `:503`, `frontend/src/features/store/ui/Neo4jConfigForm.vue:94` `:99` `:103` `:107`, `frontend/src/features/store/ui/OpenSearchConfigForm.vue:77` `:82` `:86` `:90`, `frontend/src/features/analysis/ui/GraphView.vue:576`, `frontend/src/pages/IngestLaunchDialog.vue:327` `:345` `:357`
- **Constat** : les formulaires de store referencent toujours un namespace **inexistant** (`var(--color-border, #d1d5db)`, `var(--color-text-muted, #6b7280)`) : `grep` sur `--color-border:`/`--color-text-muted:` ne renvoie aucune definition `:root`, alors que le systeme de design definit bien `--border` (`App.vue:86`/`:117`) et `--text-muted` (`App.vue:84`/`:115`). Le repli sur hex en dur subsiste : `#d1d5db` (7 occurrences), `#6b7280` (12 occurrences), `#dc2626` (11 occurrences sur 6 fichiers). Plus revelateur encore : un token d'erreur existe deja — `App.vue:121` definit `--error: #dc2626` — mais il n'est consomme nulle part ; les 10 autres sites recopient le litteral `#dc2626` au lieu de `var(--error)`.
- **Regle violee** : item 5.3 — « Pas de magic numbers ou magic strings eparpilles — les constantes sont nommees et centralisees » (poids 2).
- **Remediation** : remplacer `var(--color-border, #d1d5db)` / `var(--color-text-muted, #6b7280)` par les tokens reels du systeme (`var(--border)` / `var(--text-muted)`), et consommer `var(--error)` (deja defini) partout au lieu du hex `#dc2626`. Aucun fallback en dur ne doit subsister une fois le token cable.

### [MIN] Bloc de style `.field-*` et pont reactif v-model dupliques dans les formulaires de store (non resolu)

- **Localisation** : `frontend/src/features/store/ui/Neo4jConfigForm.vue:78-108` et `:53`, `frontend/src/features/store/ui/OpenSearchConfigForm.vue:61-91` et `:40`, `frontend/src/features/store/ui/StoreForm.vue`
- **Constat** : le bloc scoped `.config-form` / `.field-label` / `.field-input` / `.field-input[aria-invalid='true']` / `.field-help` / `.field-error` est toujours recopie a l'identique entre `Neo4jConfigForm` et `OpenSearchConfigForm`, et repris quasi tel quel dans `StoreForm`. En parallele, le pont reactif `const indexName = ref(String(props.modelValue.indexName ?? props.modelValue.index_name ?? ''))` est duplique verbatim entre `Neo4jConfigForm.vue:53` et `OpenSearchConfigForm.vue:40`.
- **Regle violee** : item 5.1 (duplication d'ampleur limitee — CSS scoped + petit pattern reactif), non bloquant.
- **Remediation** : extraire les regles `.field-*` communes dans une feuille partagee (ou un composant `FormField`), et factoriser le pont v-model en composable `useStringConfigField(modelValue, key, emit)`.

### [MIN] Bornes de chunking et defauts d'options dupliques entre DTO Pydantic et value objects du domain (non resolu)

- **Localisation** : `document-parser/api/schemas.py:133-138` `:161-162` `:188` `:206-207` ; `document-parser/domain/value_objects.py:102-104` `:111` `:131-132` ; `frontend/src/features/chunks/ui/StrategyPopover.vue:52-53`
- **Constat** : les DTO de requete redeclarent champ par champ, avec les memes valeurs par defaut, les value objects du domain (`do_ocr=True`, `do_table_structure=True`, `table_mode="accurate"`, `images_scale=1.0`, `max_tokens=512`, `merge_peers=True`). Les bornes `max_tokens` `64`/`8192` sont ecrites en litteral a la fois dans le validateur Pydantic (`schemas.py:206-207`) et dans le template (`StrategyPopover.vue` `min="64"` / `max="8192"`), sans constante partagee : aucune `CHUNK_MAX_TOKENS_MIN/MAX` n'a ete introduite (contrairement a `maxIterations`, deja centralise des deux cotes).
- **Regle violee** : item 5.3 (defauts/bornes non nommes et dupliques) ; recoupe l'esprit de 5.6. Non bloquant.
- **Remediation** : deriver les defauts des DTO depuis les value objects du domain, et extraire `CHUNK_MAX_TOKENS_MIN/MAX` en constante backend exposee au front, sur le modele deja applique a `maxIterations`.

### [INFO] `fetch()` brut dans DownloadDropdown hors du client HTTP centralise (inchange)

- **Localisation** : `frontend/src/features/document/ui/DownloadDropdown.vue:131`
- **Constat** : seul `fetch()` du front hors de `shared/api/http.ts`. Justifie fonctionnellement (besoin du `Response` brut pour lire un `blob()` + parser le `content-disposition`, la ou `apiFetch` fait toujours `response.json()`) : ce n'est pas une duplication de config HTTP (ni base URL ni headers recopies). L'item 5.5 reste conforme.
- **Regle violee** : item 5.5 — observation, non bloquante.
- **Remediation** : optionnel — exposer un helper `downloadBlob(url)` dans `shared/api/` si un second appelant apparait.

### [INFO] Petites constantes de troncature repetees dans l'infra (inchange)

- **Localisation** : `document-parser/infra/neo4j/queries.py:104` et `:128` (`[:200]`), `document-parser/infra/docling_agent_reasoning.py:188` `:204` `:218` (`query[:120]`)
- **Constat** : la limite de troncature `200` est ecrite deux fois dans `queries.py` (aperçu de noeud) et `query[:120]` trois fois dans `docling_agent_reasoning.py`. Ampleur negligeable, chaque repetition locale a son fichier.
- **Regle violee** : item 5.3 — observation d'appoint, non bloquante.
- **Remediation** : promouvoir en constante module-level (`_PREVIEW_CHARS = 200`, `_LOG_QUERY_CHARS = 120`).

---

## Points positifs

- **Palette d'element type desormais reellement unifiee (05a resolu, item 5.1/5.3)** : `frontend/src/shared/elementColors.ts:14` (`ELEMENT_COLORS`, gele via `Object.freeze`) est l'unique source de verite. `BboxOverlay.vue:41`, `StructureViewer.vue:67`, `ResultTabs.vue:198` l'importent depuis `@/shared/elementColors` ; `LayersBar`, `ElementProperties`, `DocTreeNode`, `BboxCanvas`, `ChunksPanel` consomment `colorFor`, et `reasoning/kindColors.ts:10` derive ses teintes de `ELEMENT_COLORS`. Aucune redeclaration locale (`grep ELEMENT_COLORS` ne montre que la definition partagee + des imports/usages), et la divergence `title`/`code` manquants dans `StructureViewer` a disparu. La promotion vers `shared/` supprime aussi le couplage inter-feature `analysis → document`.
- **Client HTTP integralement centralise (item 5.5)** : les modules `features/*/api.ts` passent par `apiFetch` (`shared/api/http.ts`) ; en-tetes, gestion `response.ok`, extraction du `detail` FastAPI et court-circuit `204` ecrits une seule fois. Seul `DownloadDropdown` fait un `fetch` brut, fonctionnellement justifie.
- **Types partages reellement centralises (item 5.2)** : `shared/types.ts` porte les contrats transverses ; les types restants sont authentiquement feature-scoped. Cote back, `domain/models.py` et `domain/value_objects.py` restent l'unique source des entites et VO.
- **Schemas Pydantic transformateurs, pas redefinisseurs (item 5.6)** : les DTO de reponse projettent le domain via constructeurs explicites (`from_trace`/`from_step`/…) et `asdict`, la serialisation camelCase mutualisee par `_CamelModel`.
- **Regles de validation sans desaccord front/back (item 5.7)** : la borne `maxIterations` est definie une fois par cote et alignee ; contre-exemple positif du chunking non centralise.

---

## Verdict partiel : GO CONDITIONNEL

Aucun ecart CRITICAL (la checklist DRY ne comporte aucun item poids 3, la severite
maximale atteignable est MAJ). La remediation a leve un des trois MAJ (palette couleur
`ELEMENT_COLORS` centralisee dans `shared/`, 05a), mais laisse ouverts les deux autres :
helper datetime copie 7x avec divergence UTC persistante dans `analysis_repo` (05b, item
5.1) et couleurs UI en dur non tokenisees (05c, item 5.3). Ces deux MAJ portent chacun
sur un item de poids 2 deja non conforme au 1er passage — d'ou une note **inchangee a
67 / 100** (tranche 60-79) : la resolution 05a a reduit le perimetre du constat 5.1 sans
faire basculer l'item, encore tenu en echec par 05b. Deux MAJ restants, sous le seuil
bloquant (> 3 MAJ) ; a executer avant le prochain release.
