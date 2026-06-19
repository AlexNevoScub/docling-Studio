# Plan — Support des fichiers DOCX

## Contexte

Docling supporte nativement le format Word (`.docx`) via `InputFormat.DOCX`. L'application
est aujourd'hui câblée pour les PDF uniquement : validation magic-bytes, prévisualisation
pdf2image, frontend `accept=".pdf"`. Ce document décrit les étapes pour lever ces contraintes.

---

## Vue d'ensemble des fichiers impactés

| Fichier | Nature du changement |
|---------|----------------------|
| `services/document_service.py` | Supprimer la validation PDF-only, généraliser la preview |
| `infra/local_converter.py` | Enregistrer `InputFormat.DOCX` dans le convertisseur |
| `infra/serve_converter.py` | Aucun changement requis (mimetypes.guess_type couvre DOCX) |
| `api/documents.py` | Fallback content-type, messages d'erreur preview |
| `services/export_service.py` | Export "source" : retourner .docx si le fichier est DOCX |
| `domain/value_objects.py` | Ajouter `InputFileType` pour distinguer PDF/DOCX |
| `frontend/.../DocumentUpload.vue` | `accept`, validation `isPdf` → `isAcceptedFormat` |
| `frontend/.../DocsNewPage.vue` | Idem |
| `frontend/.../ReasoningDocPicker.vue` | Idem |
| `frontend/.../DownloadDropdown.vue` | Adapter l'option export source selon le type du document |
| `frontend/.../api.ts` | Type union `getExportUrl` |
| `frontend/src/shared/i18n.ts` | ~15 strings FR + EN |
| `tests/test_document_service.py` | Fixtures DOCX, adapter `test_rejects_non_pdf` |
| `tests/test_api_endpoints.py` | Ligne 261 : DOCX ne sera plus un format "unsupported" |
| `tests/test_analysis_service.py` | Compléter le test `test_non_pdf_file` existant |

---

## Étapes

### Étape 1 — Domaine : modéliser le type de fichier

**Fichier** : `document-parser/domain/value_objects.py`

Ajouter un enum `InputFileType` qui encode les formats acceptés :

```python
class InputFileType(str, Enum):
    PDF  = "pdf"
    DOCX = "docx"
```

Ajouter un helper `InputFileType.from_filename(filename: str) -> InputFileType | None`
et `InputFileType.from_content_type(ct: str) -> InputFileType | None`.

Ce type sera utilisé dans `document_service.py` et `local_converter.py` pour remplacer
tous les comparaisons ad-hoc sur les extensions ou magic bytes.

---

### Étape 2 — Backend : lever la validation PDF-only à l'upload

**Fichier** : `document-parser/services/document_service.py`

Points à modifier :

1. **Supprimer `_PDF_MAGIC`** (ligne 24) et le bloc `if not file_content[:4].startswith(...)`.
   Le remplacer par une détection basée sur l'extension du `filename` passé à `upload()`,
   en utilisant `InputFileType.from_filename`. Rejeter les formats non reconnus avec
   `ValueError("Unsupported file format. Accepted: PDF, DOCX")`.

2. **Supprimer le hard-code `ext = ".pdf"`** (ligne 78).
   Dériver l'extension depuis l'`InputFileType` détecté.

3. **Adapter `_count_pages`** (ligne 168) :
   - Si PDF → `pdfinfo_from_bytes` comme aujourd'hui
   - Si DOCX → retourner `None` (le nombre de pages sera rempli après conversion Docling)

4. **Adapter `generate_preview`** (ligne 143) — voir Étape 3.

---

### Étape 3 — Backend : prévisualisation des DOCX

**Fichier** : `document-parser/services/document_service.py`

La prévisualisation est la partie la plus structurante. Deux approches possibles :

#### Option A — Prévisualisation via LibreOffice (recommandée si LibreOffice disponible)
Convertir le DOCX en PDF en mémoire via `libreoffice --headless --convert-to pdf`,
puis passer le résultat à `convert_from_bytes` (pdf2image). Avantages : rendu fidèle,
navigation page par page conservée. Inconvénient : dépendance LibreOffice dans le
conteneur.

#### Option B — Pas de prévisualisation pour les DOCX (approche conservative)
`generate_preview` retourne `None` pour les DOCX. L'endpoint `GET /api/documents/{id}/preview`
retourne `HTTP 204 No Content`. Le frontend affiche un placeholder (icône Word)
à la place du viewer PDF.

**Décision à prendre avant d'implémenter.** L'option B est moins coûteuse et évite
d'alourdir l'image Docker ; l'option A offre une meilleure expérience.

Quelle que soit l'option choisie, `generate_preview` doit détecter le format du fichier
(via `InputFileType`) avant d'appeler pdf2image — ne jamais passer un DOCX à poppler.

---

### Étape 4 — Backend : enregistrer DOCX dans le convertisseur local

**Fichier** : `document-parser/infra/local_converter.py`

Dans `_build_docling_converter`, ajouter `InputFormat.DOCX` dans `format_options` :

```python
from docling.document_converter import WordFormatOption   # à vérifier selon version Docling

return DoclingConverter(
    format_options={
        InputFormat.PDF:  PdfFormatOption(pipeline_options=pipeline_options),
        InputFormat.DOCX: WordFormatOption(),
    }
)
```

Vérifier dans la documentation Docling si `WordFormatOption` accepte un sous-ensemble
des `PdfPipelineOptions` (notamment `do_table_structure`, `do_ocr` peut être ignoré
pour un DOCX natif). Passer les options compatibles, ignorer silencieusement les autres.

---

### Étape 5 — Backend : corriger l'API documents

**Fichier** : `document-parser/api/documents.py`

1. **Ligne 95** — supprimer le fallback `or "application/pdf"` ; laisser `content_type`
   à `None` si le browser ne l'envoie pas.

2. **Lignes 188-192** — remplacer les messages "PDF file not found" / "Failed to read PDF file"
   par des messages génériques ("Source file not found", "Failed to read source file").

---

### Étape 6 — Backend : export du fichier source DOCX

**Fichier** : `document-parser/services/export_service.py`

L'export `ExportFormat.PDF` retourne actuellement `doc.storage_path` quel que soit le
format d'origine. Pour un document DOCX, il faut :

1. Ajouter `ExportFormat.DOCX` dans l'enum (ou renommer `ExportFormat.PDF` en
   `ExportFormat.SOURCE`).
2. Dans le handler d'export, déduire le `media_type` correct depuis `doc.content_type`
   ou l'extension du `storage_path`.
3. Retourner le fichier avec le bon `Content-Type` et le bon nom de fichier.

---

### Étape 7 — Frontend : généraliser la validation d'upload

**Fichiers** :
- `frontend/src/features/document/ui/DocumentUpload.vue`
- `frontend/src/pages/DocsNewPage.vue`
- `frontend/src/features/reasoning/ui/ReasoningDocPicker.vue`

Dans chaque fichier :

1. Remplacer `accept=".pdf"` par `accept=".pdf,.docx"`.

2. Extraire la fonction `isPdf` dans un helper partagé
   `frontend/src/shared/utils/fileFormat.ts` :

```typescript
const ACCEPTED_MIME = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])
const ACCEPTED_EXT = new Set(['.pdf', '.docx'])

export function isAcceptedFormat(file: File): boolean {
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  return ACCEPTED_MIME.has(file.type) || ACCEPTED_EXT.has(ext)
}
```

3. Remplacer tous les appels à `isPdf(file)` par `isAcceptedFormat(file)`.

4. Dans `DocsNewPage.vue`, renommer la variable `pdfs` en `validFiles`.

---

### Étape 8 — Frontend : adapter le PDF viewer pour les DOCX

**Dépend du choix fait à l'Étape 3.**

- **Option A** (preview LibreOffice) : aucun changement côté viewer, il reçoit toujours
  des images raster depuis le même endpoint.

- **Option B** (pas de preview DOCX) : le composant PDF viewer doit gérer le cas
  où l'endpoint `/preview` retourne 204. Afficher un placeholder (icône document Word +
  message "Prévisualisation non disponible pour les fichiers Word") à la place du canvas.

---

### Étape 9 — Frontend : adapter le téléchargement source

**Fichier** : `frontend/src/features/document/ui/DownloadDropdown.vue`

L'option "Télécharger le fichier source" propose actuellement `format='pdf'`.
Rendre cette option dynamique : si le document a `contentType` DOCX, utiliser
`format='docx'` (ou le format déduit depuis `document.filename`).

**Fichier** : `frontend/src/features/document/api.ts`

Étendre le type de `getExportUrl` pour accepter `'docx'` en plus de `'pdf'`.

---

### Étape 10 — Frontend : mettre à jour les traductions

**Fichier** : `frontend/src/shared/i18n.ts`

Remplacer toutes les mentions "PDF" qui doivent devenir génériques. Liste exhaustive :

| Clé | Ligne FR | Ligne EN | Remplacement suggéré |
|-----|----------|----------|----------------------|
| `upload.drop` | 208 | 852 | "Déposez un document ici…" / "Drop a document here…" |
| `upload.invalidFormat` | 211 | 855 | "Formats acceptés : PDF, DOCX" / "Accepted formats: PDF, DOCX" |
| `docsNew.drop` | 92 | 742 | "Déposez des documents ici…" |
| `docsNew.dropHint` | 93 | 743 | "PDF, DOCX" |
| `studio.subtitle` | 133 | 781 | "Importez un document (PDF ou DOCX)…" |
| `reasoning.dropPdf` | 283 | 924 | "Dépose un document" / "Drop a document" |
| `reasoning.dropPdfHint` | 284 | 925 | "PDF, DOCX" |
| `reasoning.noDocsAnalyzed` | 288 | 929 | "dépose un nouveau document" |
| `reasoning.doclingParsing` | 297 | 938 | "Docling analyse le document" |

Les mentions "PDF" dans les descriptions des options OCR (indispensable pour les PDF
non-natifs) peuvent être conservées — elles sont contextuellement correctes.

---

### Étape 11 — Tests backend

**Fichiers** : `tests/test_document_service.py`, `tests/test_api_endpoints.py`,
`tests/test_analysis_service.py`

1. **`test_document_service.py`** :
   - Ajouter une fixture `DOCX_MAGIC = b"PK\x03\x04" + b"\x00" * 26` (ZIP minimal valide).
   - Ajouter `test_upload_docx_accepted` : vérifie que l'upload avec un fichier `.docx`
     ne lève pas d'erreur de validation.
   - Renommer `test_rejects_non_pdf` en `test_rejects_unsupported_format` et adapter
     le message attendu.
   - Ajouter `test_generate_preview_docx_returns_none` si Option B est choisie,
     ou `test_generate_preview_docx_returns_image` si Option A.

2. **`test_api_endpoints.py`** :
   - Ligne 261 : si `docx` devient un format d'export valide, remplacer l'exemple
     de format non supporté par `format=xyz`.
   - Ajouter un test d'upload DOCX end-to-end.

3. **`test_analysis_service.py`** :
   - Le test `test_non_pdf_file` existant confirme que le batching est désactivé pour
     les DOCX — le conserver et l'étoffer avec un cas qui va jusqu'à la conversion.

---

### Étape 12 — Tests frontend

Mettre à jour les tests unitaires des composants modifiés :

- `DocumentUpload.spec.ts` : tester que `isAcceptedFormat` accepte `.docx` et rejette `.xlsx`.
- `DocsNewPage.spec.ts` : tester le filtrage multi-format.

---

## Ordre d'implémentation recommandé

```
Étape 1  → Domaine (InputFileType)
Étape 2  → Validation upload backend
Étape 4  → Converter local (DOCX → Docling)
Étape 5  → API documents (messages)
Étape 3  → Preview (décision + implémentation)
Étape 6  → Export DOCX
Étape 7  → Frontend : validation upload
Étape 8  → Frontend : viewer (selon décision étape 3)
Étape 9  → Frontend : téléchargement source
Étape 10 → Frontend : i18n
Étape 11 → Tests backend
Étape 12 → Tests frontend
```

Les étapes 1–4 forment le MVP fonctionnel (upload + conversion sans preview).
Les étapes 5–10 complètent l'expérience utilisateur.
Les étapes 11–12 sécurisent la non-régression.

---

## Points de décision ouverts

| # | Question | Impact |
|---|----------|--------|
| D1 | Preview DOCX : LibreOffice (Option A) ou placeholder (Option B) ? | Étapes 3 et 8 |
| D2 | Les options OCR/table côté UI doivent-elles être masquées/grisées pour les DOCX ? | UX, aucun fichier listé ci-dessus |
| D3 | Le reasoning (docling-agent) supporte-t-il les DOCX ? Faut-il le désactiver pour ce format ? | `ReasoningDocPicker.vue` |
