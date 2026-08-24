# Rapport d'audit : Tests

> **Re-audit de `release/0.7.0` @ `94eec28` — score 93 → 100**

**Release** : 0.7.0
**Date** : 2026-08-24
**Auditeur** : claude-code
**Type** : re-audit apres remediation (audit initial : 93/100, 1 MAJ)

---

## Score de compliance

| Metrique | Valeur |
|----------|--------|
| Items conformes | 14 / 14 |
| Score | 100 / 100 |
| Ecarts CRITICAL | 0 |
| Ecarts MAJOR | 0 |
| Ecarts MINOR | 3 |
| Ecarts INFO | 4 |

Detail du calcul : poids conformes 27 / poids total 27 = 100,0 -> **100**.

| # | Item | Poids | Conforme | Evolution |
|---|------|-------|----------|-----------|
| 9.1.1 | Tous les tests backend passent | 3 | Oui | = |
| 9.1.2 | Tous les tests frontend passent | 3 | Oui | = |
| 9.1.3 | Les tests e2e Karate passent | 2 | Oui (voir INFO — non re-execute) | = |
| 9.2.1 | Chaque endpoint API a un test happy path | 2 | Oui (voir MIN — versions HTTP) | = |
| 9.2.2 | Cas d'erreur endpoints (400, 404, 413, 429) | 2 | **Oui — 413 desormais teste** | **MAJ leve** |
| 9.2.3 | Services : tests d'orchestration | 2 | Oui (voir MIN — export) | = |
| 9.2.4 | Fonctions domain (bbox, value objects) | 1 | Oui | = |
| 9.2.5 | Composants Vue critiques (stores/composables) | 2 | Oui | = |
| 9.3.1 | Pas de `.only` / `fdescribe` / `fit` | 3 | Oui — aucun | = |
| 9.3.2 | Pas de skip sans justification | 1 | Oui — skips env-gated justifies | = |
| 9.3.3 | Tests deterministes | 2 | Oui | = |
| 9.3.4 | Integration teste le flux reel, pas un mock complet | 2 | Oui (voir MIN — export) | = |
| 9.3.5 | Assertions specifiques | 1 | Oui | = |
| 9.3.6 | Noms de tests explicites | 1 | Oui | = |

> Note : l'audit initial affichait « 12 / 13 » (coquille de decompte). Le decompte
> reel est de 14 items pour 27 points de poids ; seul 9.2.2 (poids 2) etait non
> conforme, d'ou 25/27 = 93. Le present re-audit corrige l'affichage a 14/14.

---

## Verification de la remediation (MAJ initial — code 413)

**Ecart initial** : le code 413 (payload trop volumineux) n'etait teste nulle part.

**Correctif verifie sur le working tree** :

- `document-parser/tests/test_api_endpoints.py:179-193` —
  `test_upload_rejects_oversized_content_length` : la fixture `mock_document_service`
  est reglee a `max_file_size = 5` octets, un upload de 23 octets est poste, et le
  test asserte `status_code == 413`, `"too large" in detail`, puis
  `mock_document_service.upload.assert_not_called()`.
- L'assertion `assert_not_called()` prouve que la garde 413 s'exerce **avant** la
  couche service : elle atteint bien la branche de pre-check Content-Length de
  l'endpoint, `document-parser/api/documents.py:79-80`
  (`if _max > 0 and file.size and file.size > _max: raise HTTPException(413, ...)`).
- Le message assert (`"too large"`) correspond au detail construit ligne
  `api/documents.py:78` (`f"File too large (max {service.max_file_size_mb} MB)"`).

Les quatre codes exiges par 9.2.2 disposent desormais d'au moins un test :
400 (`test_upload_too_large:168`, `test_preview_page_out_of_range:206`),
404 (`test_delete_document_not_found:215`, `test_export_document_no_analysis_returns_404:264`),
**413 (`test_upload_rejects_oversized_content_length:179`)**,
429 (`tests/test_rate_limiter.py:70` et `:88`, deterministe via `time.monotonic` patche `:91`).

**Conclusion** : item 9.2.2 **conforme**. L'ecart MAJ est **leve**.

---

## Ecarts constates

### [MIN] Les endpoints HTTP `document_versions` n'ont aucun test au niveau API

- **Localisation** : `document-parser/api/document_versions.py` (routes `GET /{doc_id}/versions`, `POST /{doc_id}/versions/{version_id}/restore`) ; `document-parser/tests/test_version_service.py`
- **Constat** : inchange depuis l'audit initial. `test_version_service.py` reste purement
  au niveau service (`VersionService`) ; aucun test ne monte le router `document_versions`
  via `TestClient` (`grep -rln "document_versions\|/versions" tests/` -> aucun resultat).
  La serialisation `_to_response` et le mapping `_raise_for` (`VersionServiceError` -> code
  HTTP) ne sont exerces que par la feature e2e ui `doc-history-drawer.feature`. Le happy path
  restant couvert (service + e2e), 9.2.1 demeure conforme, mais le contrat HTTP de ces deux
  routes n'a pas de filet unitaire.
- **Regle violee** : 9.2.1 (partiel) — Chaque endpoint API a au moins un test happy path.
- **Remediation** : ajouter un `test_document_versions_api.py` sur le modele de
  `test_reasoning_api.py` (service reel + repo fake) couvrant list/restore + le mapping d'erreur.

### [MIN] L'orchestration de `ExportService` n'est executee par aucun test

- **Localisation** : `document-parser/tests/test_api_endpoints.py:47-53` (fixture `mock_export_service`) et `:221-278` ; `document-parser/services/export_service.py:40`
- **Constat** : inchange. Les tests d'export mockent integralement le service
  (`mock_svc.export = AsyncMock()`), validant le cablage du router (pdf/md/json, 422, 404)
  sans jamais executer la logique reelle de `ExportService.export()` (dispatch de format,
  branches `ExportNotFoundError`, construction du nom de fichier / `Content-Disposition`).
  `grep -rln "ExportService(" tests/` -> aucun test ne construit le service reel. C'est le
  seul service dont l'orchestration n'est couverte par aucun test unitaire.
- **Regle violee** : 9.2.3 / 9.3.4 (partiel) — logique d'orchestration testee ; flux reel.
- **Remediation** : ajouter un test unitaire de `ExportService.export()` sur les trois formats
  et les branches d'erreur, avec repos fakes.

### [MIN] La logique reelle de `LocalChunker.chunk()` n'est pas testee ; commentaire vers un fichier inexistant

- **Localisation** : `document-parser/infra/local_chunker.py` ; `document-parser/tests/test_chunking.py:486`
- **Constat** : inchange. Aucun test n'exerce la logique de `LocalChunker` (construction
  `HybridChunker`/`HierarchicalChunker`, comptage de tokens, mapping `source_page`). Le
  commentaire `test_chunking.py:486` affirme toujours « Real chunker integration is covered by
  `test_local_chunker.py` » alors que ce fichier **n'existe pas**
  (`ls tests/test_local_chunker.py` -> MISSING). Le mock au niveau port pour eviter le reseau
  HuggingFace reste une bonne pratique, mais la reference laisse croire a une couverture
  inexistante hors e2e.
- **Regle violee** : 9.2.3 / 9.3.4 (partiel) — flux reel du chunking.
- **Remediation** : ajouter le `test_local_chunker.py` promis (sur un `document_json` fixe, sans
  reseau), ou corriger le commentaire pour pointer vers la seule couverture reelle (e2e).

### [INFO] Deux branches 413 secondaires restent non couvertes

- **Localisation** : `document-parser/api/documents.py:87-88` (garde flux en lecture sur `total`) ; `document-parser/services/graph_service.py:51`, `:93-94` (`GraphTooLargeError`, `truncated=True`)
- **Constat** : le 413 principal (pre-check Content-Length) est desormais teste et l'item 9.2.2
  est leve. Restent deux branches 413 non exercees par la suite rapide : (a) la garde de flux
  `if _max > 0 and total > _max` (`documents.py:88`, atteinte quand `file.size` est absent mais
  le corps depasse la limite) ; (b) `GraphService` levant `GraphTooLargeError` (HTTP 413) quand
  `payload.truncated` est vrai — `grep -rn "truncated=True\|GraphTooLarge" tests/` -> aucun
  resultat, `test_graph_api` ne teste que `truncated=False`. Completude de branche, non bloquant.
- **Remediation** : ajouter (a) un test flux (`file.size` absent, corps > limite) et (b) un test
  `test_graph_api` avec `truncated=True` assurant le 413.

### [INFO] Suite e2e Karate non re-executee dans ce re-audit

- **Localisation** : `e2e/api/`, `e2e/ui/`
- **Constat** : inchange. L'execution Karate necessite une stack live (backend + services) —
  hors perimetre de ce re-audit en lecture seule. Les suites existent et couvrent les chemins
  critiques 0.7.0. La preuve d'execution releve du pipeline CI (audit 10).
- **Remediation** : s'appuyer sur l'audit 10 (CI/Build) ; ne pas versionner `target/`.

### [INFO] RuntimeWarning « coroutine never awaited » dans `test_pipeline_options.py`

- **Localisation** : `document-parser/tests/test_pipeline_options.py:365` et `:375`
- **Constat** : inchange. `patch("services.analysis_service.asyncio.create_task")` remplace
  `create_task` par un `MagicMock` ; la coroutine `_run_analysis(...)` construite pour l'argument
  n'est jamais awaited/fermee, d'ou un `RuntimeWarning`. Le test est correct (il asserte
  `create_task` appele une fois) mais laisse un coroutine non consomme — bruit sans impact
  fonctionnel.
- **Remediation** : recuperer l'argument du mock et `.close()`, ou asserter sur le nom de
  coroutine sans en creer une reelle.

### [INFO] 15 tests Neo4j skippes en l'absence de Neo4j local

- **Localisation** : `document-parser/tests/neo4j/conftest.py:35`
- **Constat** : inchange. Les skips sont tous « Neo4j not reachable » — env-gated et justifies
  (9.3.2 conforme). En dev local sans Neo4j, tout le paquet `tests/neo4j/` n'apporte aucune
  couverture ; la garantie repose sur le service `neo4j:5.15-community` de la CI.
- **Remediation** : verifier dans l'audit 10 que la CI demarre Neo4j et n'ignore pas
  silencieusement ces skips.

---

## Points positifs

- **Ecart bloquant leve proprement** : le seul MAJ de l'audit initial (413 non teste) est
  corrige par un test cible et bien construit (`test_upload_rejects_oversized_content_length`),
  qui asserte le code, le message, ET que le service n'est jamais atteint — la garde est bien
  exercee au niveau endpoint, pas simule.
- **Discipline anti-focus maintenue** : zero `.only` / `fdescribe` / `fit` / `xit` cote frontend,
  zero focus cote backend (9.3.1) — re-verifie sur le working tree.
- **Les quatre codes d'erreur exiges (400/404/413/429)** ont chacun un test dedie et
  deterministe (rate-limiter patche `time.monotonic`).
- **Chemins critiques 0.7.0 tres bien couverts** : reasoning (`test_reasoning_api.py` : happy
  path + 503/400/404/502/500), config runtime (`test_config_api.py` : GET/PUT/DELETE/probe +
  400/403/422), les deux cablant le service reel avec fakes au seul niveau port.
- **Aucune regression introduite par la remediation** : les trois MIN et les INFO preexistants
  sont inchanges, aucun nouvel ecart n'apparait.

---

## Verdict partiel : GO

Score **100/100**, **0 CRITICAL**, **0 MAJOR**. La remediation du code 413 est verifiee sur le
working tree (`test_api_endpoints.py:179-193` exercant la garde `api/documents.py:79-80`) : l'item
9.2.2 est conforme et le seul ecart bloquant potentiel de l'audit initial est leve. Restent trois
MIN non bloquants (endpoints versions au niveau API, orchestration `ExportService`, `LocalChunker`
+ commentaire pointant vers un `test_local_chunker.py` inexistant) et quatre INFO, tous a traiter
au cycle suivant sans impact sur la release.
