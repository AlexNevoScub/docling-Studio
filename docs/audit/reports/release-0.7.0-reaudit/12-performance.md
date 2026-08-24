# Rapport d'audit : Performance

> **Re-audit de release/0.7.0 @ 94eec28 — score 76 → 86**

**Release** : 0.7.0
**Date** : 2026-08-24
**Auditeur** : claude-code
**Type** : re-audit apres remediation (audit initial = 76/100)

---

## Score de compliance

| Metrique | Valeur |
|----------|--------|
| Items conformes | 10 / 13 |
| Score | 86 / 100 |
| Ecarts CRITICAL | 0 |
| Ecarts MAJOR | 0 |
| Ecarts MINOR | 3 |
| Ecarts INFO | 4 |

Detail du calcul : poids total de la checklist = 21 (12.1 : 2+2+2+3+2 = 11 ;
12.2 : 2+2+1+1+1 = 7 ; 12.3 : 1+1+1 = 3). Items non conformes restants :
12.2.5 (poids 1), 12.3.1 (poids 1), 12.3.2 (poids 1) => 3 points non conformes.
Poids conformes = 18. Score = 18 / 21 = 85,7 => **86 / 100**.

Delta vs audit initial : l'unique ecart MAJOR (12.1.1, poids 2 — N+1 dans
`StoreService`) est **leve**. +2 points conformes => 76 -> 86.

---

## Verification de la remediation

### [RESOLU] 12.1.1 — N+1 dans `StoreService.list_stores` / `list_documents`

- **Etait** : `[MAJ]` (poids 2) — deux boucles emettaient une requete SQLite
  unitaire par element (une par store dans `list_stores`, une par lien dans
  `list_documents`), chacune rouvrant une connexion aiosqlite.
- **Verification sur le working tree @ 94eec28** :
  - `list_stores` (`document-parser/services/store_service.py:160-178`) appelle
    desormais `await self._links.count_by_store()` (l.163), une **requete unique**.
    L'implementation repository est un seul `GROUP BY` :
    `SELECT store_id, COUNT(*) AS n FROM document_store_links GROUP BY store_id`
    (`document-parser/persistence/document_store_link_repo.py:82-94`). Le compte est
    lu depuis le mapping `counts.get(store.id, 0)` (l.173) — plus aucun aller-retour
    dans la boucle, qui ne fait plus que construire les `StoreInfoView`.
  - `list_documents` (`document-parser/services/store_service.py:345-374`) resout
    tous les noms de fichiers via `await self._documents.find_by_ids([...])` (l.361),
    une **requete unique** `WHERE id IN (...)` a placeholders dynamiques
    (`document-parser/persistence/document_repo.py:91-107`), avec court-circuit
    `if not doc_ids: return {}` (l.98-99). La boucle `for link in links` (l.363) ne
    fait plus qu'un lookup memoire `docs.get(link.document_id)` (l.364).
- **Aucun N+1 residuel dans `store_service.py`** : les `find_for_store`
  restants (l.347 lecture des liens en une requete ; l.389 garde de suppression)
  et les `find_by_id` restants (l.235, l.308 re-lecture apres create/update) sont
  des appels **uniques hors boucle**, pas un pattern N+1.
- **Verdict item** : conforme. Ecart MAJOR leve.

---

## Ecarts constates (restants)

### [MIN] Logo PNG 1024x1024 (~858 KiB) non optimise, servi en topbar et en favicon

- **Localisation** : `frontend/public/logo.png` (1024x1024, 8-bit RGB, 878 643 octets),
  reference dans `frontend/index.html:7` (`<link rel="icon" type="image/png" href="/logo.png">`),
  ainsi que `frontend/src/app/App.vue`, `frontend/src/pages/StudioPage.vue`,
  `frontend/src/pages/HomePage.vue`.
- **Constat** : etat **inchange** depuis l'audit initial. Le meme PNG ~858 KiB /
  1024 px sert d'icone de titre, de visuel d'import, de hero et de favicon. Un
  `favicon.svg` (270 octets) existe dans `frontend/public/` mais n'est toujours pas
  branche comme icone. Couple a l'absence de cache statique (12.3.1), l'asset est
  re-telecharge a chaque visite.
- **Regle violee** : 12.2.5 — "Les assets lourds (images, fonts) sont optimises"
  (poids 1).
- **Remediation** : pointer `rel="icon"` sur `favicon.svg`, servir une version
  compressee/redimensionnee pour topbar/hero, compresser le PNG source
  (pngquant/oxipng, cible < ~100 KiB).

### [MIN] Nginx ne configure aucun cache pour les fichiers statiques

- **Localisation** : `frontend/nginx.conf.template:13-15` et `nginx.conf.template:13-15`
  (racine).
- **Constat** : etat **inchange**. Les deux templates servent le SPA via
  `location / { try_files $uri $uri/ /index.html; }` sans directive `expires` /
  `Cache-Control` ni bloc `location ~* \.(js|css|png|woff2|...)$`. Vite emet
  pourtant des noms content-hashes immutables — cas ideal pour
  `Cache-Control: public, max-age=31536000, immutable`.
- **Regle violee** : 12.3.1 — "Nginx a une configuration de cache pour les fichiers
  statiques" (poids 1).
- **Remediation** : ajouter un bloc `location ~* \.(js|css|woff2?|png|svg|jpg)$`
  avec `expires 1y; add_header Cache-Control "public, immutable";` et un
  `Cache-Control: no-cache` cible sur `index.html`, dans les deux templates.

### [MIN] La liste des analyses renvoie les colonnes lourdes (markdown, HTML, pages, chunks) pour chaque job

- **Localisation** : `document-parser/api/analyses.py:71-81` (`list_analyses`),
  `document-parser/api/analyses.py:23-40` (`_to_response`),
  `document-parser/persistence/analysis_repo.py:39-43` (`_SELECT_WITH_DOC`, `SELECT aj.*`)
  et `:59-67` (`find_all`).
- **Constat** : etat **inchange**. `GET /api/analyses` mappe chaque job via
  `_to_response`, qui serialise `content_markdown`, `content_html`, `pages_json` et
  `chunks_json` (l.29-32) pour **chaque** job (jusqu'a `limit=200`). Cote DB,
  `find_all` fait `SELECT aj.*` (`_SELECT_WITH_DOC`), chargeant aussi la colonne
  `document_json` (la plus volumineuse) en memoire avant de la jeter. Bon point
  conserve : `document_json` n'est pas renvoye au client (`has_document_json: bool`,
  l.33) — optimisation amorcee mais partielle.
- **Regle violee** : 12.3.2 — "Les reponses API sont de taille raisonnable (pas
  d'envoi de donnees inutiles)" (poids 1).
- **Remediation** : projection "resume" pour la liste (id, statut, filename,
  timestamps, progression, drapeaux `has_*`) ; contenu complet uniquement sur
  `GET /api/analyses/{id}`. Cote repo, `SELECT` de colonnes explicites (sans
  `document_json` ni contenus) pour le chemin liste.

---

## Observations (informatif — inchangees)

### [INFO] Upload et preview chargent le fichier entier en memoire

- **Localisation** : `document-parser/api/documents.py:82-90` (upload,
  `content = b"".join(chunks)`), `document-parser/services/document_service.py:64-106`
  + `:154-165`, `document-parser/api/documents.py:181` (preview).
- **Constat** : le fichier complet reside en RAM (comptage de pages via
  `pdfinfo_from_bytes`, preview via `convert_from_bytes`, `ServeConverter` via
  `path.read_bytes`). Ces bibliotheques exigent les octets complets, et le
  chargement est borne par `MAX_FILE_SIZE_MB` (rejet 413 en amont). Item 12.1.5
  considere **conforme** ; note pour tracabilite.
- **Regle concernee** : 12.1.5 (poids 2, conforme).

### [INFO] Aucun mode WAL sur SQLite ; une connexion neuve par appel repository

- **Localisation** : `document-parser/persistence/database.py` (`get_db` /
  `get_connection`).
- **Constat** : chaque methode repository ouvre puis referme une connexion aiosqlite
  (pas de pool), sans `PRAGMA journal_mode=WAL`. Les index restent bien couverts.
  Note : la remediation N+1 **reduit** deja le nombre d'ouvertures/fermetures dans
  les deux cas d'usage `StoreService` (une requete ensembliste au lieu de N), donc
  la pointe d'overhead que cette observation soulignait dans ces boucles a disparu ;
  l'observation WAL/connexion-par-appel reste valide de facon generale.
- **Regle concernee** : 12.1.1 / concurrence (informatif). Suggestion : activer WAL
  au boot et evaluer une connexion long-vivante partagee.

### [INFO] Pas d'annulation (AbortController) des requetes API superseder

- **Localisation** : `frontend/src/` (aucune occurrence d'`AbortController`),
  debounce present dans `frontend/src/pages/DocsLibraryPage.vue:158-163` et
  `frontend/src/features/chunks/ui/ChunksEditor.vue:239-249`.
- **Constat** : item 12.2.3 exige "annulation OU debounce quand pertinent" ; le
  debounce couvre les cas pertinents. Item **conforme** ; note pour amelioration.
- **Regle concernee** : 12.2.3 (poids 1, conforme).

### [INFO] Debounce de sauvegarde de chunk sans nettoyage a l'unmount

- **Localisation** : `frontend/src/features/chunks/ui/ChunksEditor.vue:239-249`.
- **Constat** : `saveTimer` est `clearTimeout`e avant chaque re-armement mais aucun
  `onUnmounted`/`onBeforeUnmount` ne l'annule ; un demontage dans la fenetre de
  600 ms declenche encore un `updateText`. Pas une fuite memoire (timer a un coup),
  d'ou INFO.
- **Regle concernee** : 12.2.1 / 12.2.2 (conformes par ailleurs).

---

## Points positifs (re-verifies sur le working tree @ 94eec28)

- **N+1 elimine (12.1.1, poids 2 — desormais conforme)** : `count_by_store` (GROUP BY
  unique, `document_store_link_repo.py:82-94`) et `find_by_ids` (`WHERE id IN (...)`
  unique, `document_repo.py:91-107`) remplacent les deux boucles a requete unitaire.
- **Operations longues non bloquantes (12.1.4, poids 3 — conforme)** : toute la
  charge lourde traverse `asyncio.to_thread` — conversion Docling
  (`infra/local_converter.py:295`), chunking (`infra/local_chunker.py:106`), lecture
  PDF distante (`infra/serve_converter.py:113`), run reasoning
  (`infra/docling_agent_reasoning.py:194`), ecriture upload + comptage pages
  (`services/document_service.py:84`).
- **Semaphore de concurrence (12.1.3, conforme)** : `MAX_CONCURRENT_ANALYSES`
  (`infra/settings.py:159`, defaut 3) injecte dans un `asyncio.Semaphore`
  (`services/analysis_service.py:98`).
- **Nettoyage des temporaires (12.1.2, conforme)** : uploads hors-limite `os.unlink`es
  via `asyncio.to_thread` (`services/document_service.py:93`), suppression de document
  avec garde anti-traversee (`services/document_service.py:130`).
- **Nettoyage frontend systematique (12.2.1 / 12.2.2, conformes)** : `removeEventListener`
  symetriques en `onUnmounted`, observers `disconnect()`, timers de polling stoppes
  au demontage — inchange depuis l'audit initial.
- **Health check leger (12.3.3, conforme)** : `SELECT 1` + lecture de settings.

---

## Verdict partiel : GO

Score **86/100** (bande >= 80), **0 ecart CRITICAL**, **0 ecart MAJOR**. L'unique
MAJOR de l'audit initial (N+1 `StoreService`) est leve et verifie dans le code.
Restent 3 ecarts MINOR non bloquants (logo/favicon, cache nginx, projection liste
analyses), a traiter au prochain cycle.
