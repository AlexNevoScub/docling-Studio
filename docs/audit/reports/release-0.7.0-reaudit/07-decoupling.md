# Rapport de re-audit : Decouplage

> **Re-audit de `release/0.7.0` @ `94eec28` — score 80 → 94**

**Release** : 0.7.0
**Date** : 2026-08-24
**Auditeur** : claude-code
**Reference** : re-audit du rapport `release-0.7.0/07-decoupling.md` (score initial 80/100, NO-GO)

---

## Score de compliance

| Metrique | Valeur |
|----------|--------|
| Items conformes | 15 / 16 |
| Score | 94 / 100 |
| Ecarts CRITICAL | 0 |
| Ecarts MAJOR | 1 |
| Ecarts MINOR | 0 |
| Ecarts INFO | 3 |

Detail du calcul : somme des poids = 35 ; seul l'item **7.4.2** (poids 2) reste
non conforme. Poids conformes = 33. `33 / 35 * 100 = 94,29` -> **94**.

| Item | Poids | Statut re-audit | Evolution |
|------|-------|-----------------|-----------|
| 7.1.1 REST-only front/back | 3 | Conforme | = |
| 7.1.2 Types TS = schemas Pydantic | 3 | Conforme | = |
| 7.1.3 Front mockable (api.ts par feature) | 2 | Conforme | = |
| 7.1.4 Back testable sans front (TestClient) | 2 | Conforme | = |
| 7.1.5 Pas de logique metier dupliquee | 2 | Conforme | = |
| 7.2.1 Feature = store + api + ui | 2 | Conforme | = |
| 7.2.2 Frontiere barrel public + ESLint no-restricted-imports | 3 | **Conforme** | **[CRIT] -> leve** |
| 7.2.3 Types partages dans `shared/types.ts` | 2 | **Conforme** | **[MAJ] -> leve** |
| 7.2.4 Store n'accede pas au state d'un autre store | 2 | Conforme | = |
| 7.3.1 Repos retournent des objets du domaine | 2 | Conforme | = |
| 7.3.2 Pas de types `docling.*` dans les services | 3 | Conforme | = |
| 7.3.3 Changement de DB confine a `persistence/` | 2 | Conforme | = |
| 7.3.4 Changement HTTP confine a `api/` + `main.py` | 2 | Conforme | = |
| 7.4.1 Ports = signatures claires + types domaine | 2 | Conforme | = |
| 7.4.2 Pas de `dict`/`Any` dans les responses | 2 | **Non conforme [MAJ]** | inchange |
| 7.4.3 Format de reponse coherent | 1 | Conforme | = |

---

## Verification de la remediation

### [CRIT] 7.2.2 — Frontiere barrel public entre features : **RESOLU**

L'item a ete reformule (« frontiere barrel ») et le re-audit est mene contre
cette regle : les features ne s'importent qu'a travers leur barrel public
`index.ts` (ou `shared/`), jamais dans les internes `store`/`api`/`ui` d'une
autre feature, invariant impose par une regle ESLint `no-restricted-imports`.
Verifie sur le working tree :

1. **Regle ESLint presente et ciblee** — `frontend/eslint.config.js:28-55` :
   `no-restricted-imports` (severite `error`) bloque les patterns
   `../*/store`, `../*/api`, `../*/ui/*`, leurs variantes `../../*` et
   `@/features/*/store|api|ui/*`. Exemption explicite des fichiers de test
   (`eslint.config.js:68-74`) pour les mocks/fixtures.
2. **Briques partagees extraites vers `shared/`** — les quatre elements cites
   dans le CRIT initial ont ete deplaces et leurs anciens emplacements
   n'existent plus (`ls` en erreur `No such file or directory`) :
   - `shared/bboxScaling.ts` (ex `document/bboxScaling`)
   - `shared/elementColors.ts` (ex `document/elementColors`)
   - `shared/ui/MarkdownViewer.vue` (ex `analysis/ui/MarkdownViewer.vue`)
   - `shared/ui/StatusBadge.vue` (ex `document/ui/StatusBadge.vue`)
   Tous les consommateurs les importent desormais via `@/shared/...`
   (ex. `reasoning/kindColors.ts:10`, `chunks/ui/StaleStoresStrip.vue:35`,
   `document/ui/TableModal.vue:36`, `analysis/ui/BboxOverlay.vue:39-41`).
3. **Tout acces inter-features passe par le barrel `@/features/<name>`** —
   les 10 imports croises du working tree (hors tests) pointent tous sur un
   `index.ts` public, aucun ne plonge dans un interne :
   - `document/store.ts:5-6` -> `@/features/analysis`, `@/features/chunks`
   - `reasoning/store.ts:3` -> `@/features/document`
   - `chunks/store.ts:5` -> `@/features/document`
   - `admin-config/store.ts:10` -> `@/features/feature-flags`
   - `analysis/ui/AnalysisPanel.vue:61`, `analysis/ui/StructureViewer.vue:64`
     -> `@/features/document`
   - `chunking/ui/ChunkPanel.vue:228` -> `@/features/analysis`
   - `settings/ui/SettingsPanel.vue:73-74` -> `@/features/feature-flags`,
     `@/features/admin-config`
   Les barrels exportent bien les symboles consommes
   (`document/index.ts`, `analysis/index.ts`, `chunks/index.ts`,
   `feature-flags/index.ts`, `admin-config/index.ts`).
4. **Aucun import relatif `../` ne franchit une frontiere de feature** — le scan
   exhaustif des imports `../` (hors tests) ne renvoie que des cibles
   intra-feature (`../store`, `../api`, `../graphApi`, `../timeline.logic`, …)
   ou `shared/` (`../../shared/...`). Les 19 imports croises deep du 1er audit
   ont tous disparu.

**Conclusion : item 7.2.2 conforme** — le CRIT est leve.

### [MAJ] 7.2.3 — `RechunkOptions` dans `shared/types.ts` : **RESOLU**

`interface RechunkOptions` est desormais definie dans
`frontend/src/shared/types.ts:90`. Les quatre consommateurs l'importent depuis
`@/shared/types` : `document/api.ts:2`, `chunks/store.ts:4`,
`chunks/ui/ChunksPanel.vue:96`, `chunks/ui/StrategyPopover.vue:128`. Plus aucune
definition dans une feature. Le MAJ est leve.

---

## Ecarts constates

### [MAJ] `dict` non type dans un schema de reponse (item 7.4.2) — **inchange**

- **Localisation** : `document-parser/api/schemas.py:310`
  (`StoreResponse.config: dict`) ; corrobore par
  `document-parser/api/graph.py:32` (`GraphNode` -> `model_config = {"extra": "allow"}`).
- **Constat** : L'item 7.4.2 exige qu'aucune reponse n'utilise `dict` ou `Any`.
  Le read model `StoreResponse` expose toujours `config: dict` (ligne 310) : le
  contrat du config store (polymorphe selon `kind` : neo4j vs opensearch) reste
  non type cote wire, alors que le frontend en modelise les formes
  (`Neo4jConfigForm.vue`, `OpenSearchConfigForm.vue`). En complement, le modele
  de reponse `GraphNode` autorise des champs arbitraires via `extra="allow"`
  (`graph.py:32`), ouvrant le contrat cote noeud. Ces cas sont au niveau *champ*
  (et non annotation de retour), donc invisibles pour la commande de la fiche
  (`grep "-> dict|-> Any|Dict[str, Any]"`, qui ne renvoie rien). Ecart reel mais
  a risque contenu (champs polymorphes assumes par conception). Aucune
  modification depuis le 1er audit — conformement au perimetre de remediation.
  (N.B. `config: dict` apparait aussi en `schemas.py:329` et `:349`, mais ce
  sont des schemas de *requete* — `StoreCreateRequest` / `StoreUpdateRequest` —
  hors perimetre de 7.4.2 qui vise les *responses*.)
- **Regle violee** : 7.4.2 (poids 2) — « pas de `dict` ou `Any` dans les responses ».
- **Remediation** : Typer `StoreResponse.config` via une union discriminee
  (`Neo4jConfig | OpenSearchConfig`) ou un modele `StoreConfig` dedie par `kind` ;
  pour `GraphNode`, remplacer `extra="allow"` par les attributs cytoscape
  effectivement emis (ou un sous-modele `data` type). Ecart isole, non bloquant
  (1 seul MAJ, seuil master = > 3) — a planifier au prochain cycle.

### [INFO] Champ de contrat orphelin `stores?` cote frontend — inchange

- **Localisation** : `frontend/src/shared/types.ts:39`
- **Constat** : L'interface `Document` declare toujours `stores?: string[]`
  (« added in E1 #203 ») alors que le schema backend `DocumentResponse` n'emet
  plus ce champ (seul `store_links` / `storeLinks` est peuple, cf. #283). Champ
  optionnel donc inoffensif a l'execution ; residu de contrat mort qui brouille
  la correspondance TS <-> Pydantic (7.1.2, considere conforme par ailleurs).
- **Remediation** : Supprimer `stores?: string[]` de l'interface `Document`.

### [INFO] Pre-validation de taille de fichier cote front — inchange

- **Localisation** : `frontend/src/features/document/store.ts:75-77`
- **Constat** : Le front rejette un fichier trop volumineux avant l'upload. Ce
  n'est pas une reinvention de logique metier (7.1.5) : la limite provient de la
  config serveur (`appMaxFileSizeMb`, alimentee par `/health`) et sert de garde
  UX ; le backend reste l'autorite. Signale pour tracabilite.
- **Remediation** : Aucune action requise.

### [INFO] Perimetre de la regle ESLint plus etroit que « barrel uniquement »

- **Localisation** : `frontend/eslint.config.js:31-49`
- **Constat** : La regle `no-restricted-imports` couvre exactement les internes
  `store`/`api`/`ui` cites par l'item 7.2.2 reformule, ce qui est conforme. Mais
  elle ne bloquerait pas un futur import croise vers un module *racine* d'une
  autre feature hors de ces trois dossiers (ex. `@/features/document/linkedView`,
  `@/features/reasoning/kindColors`, `../analysis/legendFilters`). A ce commit,
  **zero violation de ce type n'existe** — tout acces inter-features transite par
  le barrel — l'observation ne degrade donc pas le score. Simple durcissement
  possible du garde-fou.
- **Remediation** (optionnelle) : Ajouter des patterns englobant tout deep import
  inter-feature (ex. autoriser uniquement `@/features/<name>` et `@/features/<name>/index`,
  interdire `@/features/*/*` et `../*/*` sauf `index`), ou s'appuyer sur une regle
  de type `import/no-internal-modules` avec allowlist des barrels.

---

## Points positifs

- **CRIT 7.2.2 verrouille par outillage.** Au-dela de la refactorisation, la
  frontiere est desormais **executee par ESLint** (`no-restricted-imports`,
  severite `error`), donc regressable en CI plutot que par revue manuelle.
- **`shared/` devient le vrai socle transverse.** Helpers de rendu
  (`bboxScaling`, `elementColors`), composants (`MarkdownViewer`, `StatusBadge`)
  et types (`RechunkOptions` et les contrats deja centralises : `DocChunk`,
  `ChunkDiff`, `PushSummary`, `DocTreeNode`, `DocumentVersion`) vivent tous dans
  `shared/`, sans dependance vers une feature.
- **Barrels publics coherents.** Chaque feature productrice
  (`document`, `analysis`, `chunks`, `feature-flags`, `admin-config`) expose un
  `index.ts` qui reexporte exactement les symboles consommes ailleurs.
- **Isolation infra/domaine intacte (7.3.2 / 7.4.1).** Aucun `import docling`
  dans `services/` ; ports orientes domaine ; couches HTTP/DB confinees — non
  regresse par la remediation.

---

## Verdict partiel : GO

Score de compliance **94/100**, en hausse de **80 -> 94**. Les deux ecarts
bloquants du 1er audit sont leves et verifies sur le code du working tree
(`94eec28`) : le **[CRIT] 7.2.2** via la frontiere barrel public imposee par
ESLint, et le **[MAJ] 7.2.3** via `RechunkOptions` deplace dans `shared/types.ts`.
Il ne subsiste **aucun CRIT** et **1 seul MAJ** (7.4.2, sous le seuil master de
> 3), assorti de 3 INFO non bloquantes.

Condition de suivi (non bloquante) :
1. Planifier au prochain cycle le [MAJ] 7.4.2 — typer `StoreResponse.config`
   (`schemas.py:310`) et resserrer `GraphNode` (`graph.py:32`).
