# Rapport d'audit : Securite

> **Re-audit de release/0.7.0 @ 94eec28 — score 97 → 97**

**Release** : 0.7.0
**Date** : 2026-08-24
**Auditeur** : claude-code
**Type** : re-audit apres remediation (audit initial = 97/100, 0 CRIT, 1 MAJ, 1 MIN, 3 INFO)

---

## Score de compliance

| Metrique | Valeur |
|----------|--------|
| Items conformes | 13 / 14 |
| Score | 97 / 100 |
| Ecarts CRITICAL | 0 |
| Ecarts MAJOR | 0 |
| Ecarts MINOR | 1 |
| Ecarts INFO | 4 |

Detail du calcul : poids total de la checklist = 36. Seul l'item 8.5.2
(poids 1) reste non conforme (voir [MIN] ci-dessous). Poids conformes = 35.
Score = 35 / 36 = 97,2 -> **97**.

Le score sur la checklist ponderee est **inchange (97 -> 97)** : l'ecart qui
maintenait la note sous 100 etait l'item 8.5.2, et cet item n'est que
*partiellement* remedie (python-multipart borne, mais torch/torchvision
toujours declares sans version). En revanche la **posture** progresse
nettement : l'ecart [MAJ] SSRF est **leve**, ramenant le compte MAJOR de 1 a 0.

---

## Etat de la remediation (par ecart de l'audit initial)

| Ecart initial | Item | Statut | Preuve (working tree @ 94eec28) |
|---------------|------|--------|---------------------------------|
| [MAJ] SSRF probe test-connection | 8.2.1 (concern additionnel) | **RESOLU** | `document-parser/infra/llm/ollama_probe.py:31-73` + `:82` ; `SECURITY.md:51-75` |
| [MIN] Deps sans borne superieure | 8.5.2 | **PARTIEL — reste ouvert** | `pyproject.toml:10` (corrige) ; `pyproject.toml:35-36` (toujours ouvert) |
| [INFO] trivyignore expiree | 8.5.1 | **INCHANGE — ouvert** | `.trivyignore.yaml:11` (`expired_at: 2026-06-30`) |
| [INFO] API sans authentification | (hors checklist) | **DOCUMENTE** | `SECURITY.md:51-75` (modele de confiance self-hosted) |
| [INFO] Pas de garde CORS `"*"`+creds | 8.4.1 (durcissement) | **INCHANGE** | `main.py:79` / `infra/settings.py` |

---

## Ecarts constates (restants)

### [MIN] Dependance backend sans borne de version (torch / torchvision)

- **Localisation** : `document-parser/pyproject.toml:35-36` (`torch`, `torchvision`
  declares sans aucune contrainte de version, dans le groupe `local`).
- **Constat** : la remediation `#audit-08` (commit `8e40bee`) a borne
  `python-multipart` — desormais `"python-multipart>=0.0.12,<1.0.0"`
  (`pyproject.toml:10`) — et **toutes** les dependances runtime de
  `[project].dependencies` (lignes 7-18) portent maintenant une borne superieure
  `<Y`. Il ne subsiste donc **plus aucun `>=` sans borne superieure**. En
  revanche `torch` et `torchvision` (groupe opt-in `local`, R&D conversion
  locale) restent declares **sans aucune version** (`"torch"`, `"torchvision"`),
  ce qui contrevient au libelle principal de l'item 8.5.2 (« Les versions des
  dependances sont epinglees »). L'audit initial classait deja ces deux
  declarations comme violation de 8.5.2 ; elles sont inchangees, donc l'item ne
  bascule pas conforme. Note : sous une lecture strictement litterale du seul
  parenthese (« pas de `>=` sans borne superieure »), l'item serait conforme —
  je conserve la lecture de l'audit initial (« versions epinglees ») pour
  coherence, d'ou le maintien de l'ecart.
- **Regle violee** : 8.5.2 — Les versions des dependances sont epinglees.
- **Facteurs attenuants** (inchanges) : `torch`/`torchvision` sont
  volontairement laisses libres pour etre rediriges vers l'index CPU via
  `[tool.uv.sources]` (`pyproject.toml:59-66`) ; `uv.lock` est resolu `--frozen`
  au build (Dockerfile), ce qui epingle la version exacte a l'installation. Le
  groupe `reasoning` epingle ses deux deps a l'exact (`docling-agent==0.6.0`,
  `mellea==0.4.2`). Risque reel faible (lockfile deterministe), portee reduite a
  un groupe optionnel.
- **Remediation** : ajouter un plafond majeur sur `torch`/`torchvision`
  (ex. `torch>=2.0,<3.0`) pour aligner la declaration sur le lockfile, ou
  documenter explicitement l'exemption dans la fiche de l'item.

### [INFO] Suppression trivyignore expiree (inchange)

- **Localisation** : `.trivyignore.yaml:11` (`CVE-2026-40393`,
  `expired_at: 2026-06-30`).
- **Constat** : **non modifie par la remediation** (conforme au perimetre
  annonce). La fenetre de suppression de `CVE-2026-40393` (Mesa OOB read, tire
  transitivement par `libgl1`) a expire le 2026-06-30 ; a la date du re-audit
  (2026-08-24) elle est inactive et re-apparaitra dans le scan Trivy. Les trois
  autres entrees restent valides (`2026-08-31`, `2026-09-30` x2) avec
  justification d'inatteignabilite.
- **Regle violee** : 8.5.1 (item nominalement conforme — CVE OS transitive,
  documentee, non atteignable) ; observation de maintenance.
- **Remediation** : re-trier `CVE-2026-40393` (drop de `libgl1` via
  `opencv-python-headless`, cf. #189) ou prolonger `expired_at` avec une
  justification a jour.

### [INFO] SSRF probe — residus de defense en profondeur (nouveau)

- **Localisation** : `document-parser/infra/llm/ollama_probe.py:59-73`,
  `:87-88`.
- **Constat** : la garde `_resolved_target_is_blocked` ferme le vecteur le plus
  grave (endpoint metadata cloud `169.254.169.254`, lien-local, reserve,
  multicast, unspecified) **avant toute requete sortante**, ce qui est correct
  et documente. Deux residus subsistent, tous deux assumes :
  1. **TOCTOU / DNS-rebinding** : la garde resout via `socket.getaddrinfo`
     (`:60`) puis `httpx.AsyncClient.get(url)` (`:88`) re-resout
     independamment ; l'adresse validee n'est pas epinglee pour la requete
     effective. Un resolveur hostile pourrait renvoyer une IP benigne au
     controle puis une IP bloquee a la connexion.
  2. **Loopback / LAN autorises par conception** : la garde laisse passer
     loopback et les plages RFC1918 (necessaire pour l'usage legitime Ollama
     sur `localhost:11434` / LAN). Sur un deploiement self-hosted expose, le
     probe peut donc encore servir a sonder des hotes/ports **du LAN interne**
     (timing / messages d'erreur). C'est explicitement documente comme une
     responsabilite reseau (`SECURITY.md:71-75`).
- **Regle violee** : aucune — l'item 8.2.1 reste conforme (validation Pydantic
  + garde presente). Note de durcissement.
- **Remediation** (optionnelle) : epingler l'IP resolue et validee pour la
  requete httpx (transport/`resolver` custom) afin de neutraliser le rebinding ;
  conserver la doc du modele de confiance LAN pour le self-hosted.

### [INFO] API sans authentification — config inscriptible en self-hosted (inchange, desormais documente)

- **Localisation** : `document-parser/main.py` (aucun middleware d'auth) ;
  modele de confiance decrit dans `SECURITY.md:51-75`.
- **Constat** : aucune couche d'authentification/autorisation. Sur `huggingface`
  les ecritures de config **et** le probe sont neutralises (403) ; en
  `self-hosted`, `PUT/DELETE /api/config/reasoning` et les routes CRUD restent
  ouverts a quiconque atteint le backend. Choix d'architecture assume (studio
  local / demo Space), **desormais explicite dans `SECURITY.md`** (« Self-hosted
  exposure is a deployment responsibility »).
- **Regle violee** : aucune (la checklist ne couvre pas l'authentification).
- **Remediation** : prevoir une protection reseau (reverse-proxy authentifie)
  pour tout deploiement self-hosted expose — deja recommande dans `SECURITY.md`.

### [INFO] Absence de garde-fou contre `CORS_ORIGINS="*"` avec credentials (inchange)

- **Localisation** : `document-parser/infra/settings.py` (parsing `CORS_ORIGINS`)
  + `document-parser/main.py:79` (`allow_origins=settings.cors_origins`,
  `allow_credentials=True`).
- **Constat** : le defaut est explicite (localhost), donc conforme, mais rien
  n'empeche un operateur de positionner `CORS_ORIGINS="*"` avec
  `allow_credentials=True`. **Non modifie** par la remediation.
- **Regle violee** : 8.4.1 (item conforme par defaut) — durcissement suggere.
- **Remediation** : rejeter au boot la combinaison `"*"` + credentials, ou
  logger un avertissement fort.

---

## Verification par item (re-verifie sur le working tree @ 94eec28)

| # | Item | Poids | Statut | Preuve |
|---|------|-------|--------|--------|
| 8.1.1 | Aucun secret en dur | 3 | Conforme | `git ls-files` : aucun `.env`/`.pem`/`.key` (seul `.env.example`) |
| 8.1.2 | `.env` dans `.gitignore` | 3 | Conforme | `.gitignore:26-28` (`.env`, `.env.local`, `.env.production`) |
| 8.1.3 | Secrets Docker par env, pas build args | 2 | Conforme | `docker-compose.yml` (`environment:`) |
| 8.2.1 | Entrees validees par Pydantic | 3 | Conforme | schemas Pydantic + garde SSRF `ollama_probe.py:82` |
| 8.2.2 | `MAX_FILE_SIZE` applique a l'upload | 3 | Conforme | `api/documents.py:76-88` (Content-Length + streaming, 413) |
| 8.2.3 | Types de fichiers valides | 2 | Conforme | `services/document_service.py:23-24` (magic bytes `%PDF`) |
| 8.3.1 | SQL en parametres lies | 3 | Conforme | f-strings n'interpolent que constantes / `?` (`document_repo.py:100-104`) |
| 8.3.2 | Pas de `eval/exec/os.system` | 3 | Conforme | grep : aucun resultat |
| 8.3.3 | DOMPurify sur rendu HTML/MD | 3 | Conforme | `frontend/src/shared/ui/MarkdownViewer.vue:3,24` (`DOMPurify.sanitize`) |
| 8.4.1 | CORS explicite, pas de `*` en prod | 3 | Conforme | `main.py:79` (`allow_origins=settings.cors_origins`, defaut localhost) |
| 8.4.2 | Rate limiter sauf `/api/health` | 2 | Conforme | `infra/rate_limiter.py:59,68` (`exclude_paths=("/api/health",)`) |
| 8.4.3 | Nginx sans directory listing | 2 | Conforme | `nginx.conf.template` + `frontend/nginx.conf.template` : `try_files`, pas d'`autoindex`, headers de securite |
| 8.5.1 | Pas de CVE critique connue | 3 | Conforme | CVE OS transitives documentees dans `.trivyignore.yaml` (voir INFO expiree) |
| 8.5.2 | Versions epinglees | 1 | **NON conforme** | `pyproject.toml:35-36` (`torch`/`torchvision` sans version) |

---

## Points positifs (confirmes / nouveaux)

- **[Nouveau] Garde SSRF sur le probe** : `_resolved_target_is_blocked`
  (`ollama_probe.py:31-73`) resout la cible et rejette **avant toute requete
  sortante** (`:82`) les adresses lien-local (dont metadata `169.254.169.254` et
  `fe80::/10`), multicast, reservees et unspecified — tout en autorisant
  explicitement loopback et le LAN (usage Ollama legitime). Aucun trafic reseau
  n'est emis vers une cible bloquee.
- **[Nouveau] Modele de confiance documente** : `SECURITY.md:51-75` decrit la
  surface SSRF, le refus 403 sur HuggingFace, l'autorisation deliberee du
  loopback/LAN et la responsabilite reseau du self-hosted.
- **[Nouveau] python-multipart borne** : `pyproject.toml:10`
  (`>=0.0.12,<1.0.0`) ; plus aucune dep runtime `>=` sans borne superieure.
- **Secrets** : aucun secret en dur ni dans le depot ; `.env*` dans
  `.gitignore` ; valeurs sensibles par `environment:` (jamais en build args).
- **Injection SQL** : requetes en parametres lies (`?`) ; les f-strings SQL
  (dont `document_repo.py:103` — `IN ({placeholders})` genere par le fix N+1
  `#audit-12`) n'interpolent que des `?` / constantes de module, jamais
  d'entree utilisateur. Aucun `eval`/`exec`/`os.system`.
- **XSS** : unique `v-html` (`frontend/src/shared/ui/MarkdownViewer.vue:3`)
  assaini par `DOMPurify.sanitize` (`:24`).
- **Upload** : double controle de taille (Content-Length puis lecture streaming
  bornee, `api/documents.py:76-88`, 413), validation par magic bytes `%PDF`.
- **CORS / rate limiting / Nginx** : origines explicites, rate limiter par IP
  avec `/api/health` exclu, headers de durcissement Nginx, pas d'`autoindex`.

---

## Verdict partiel : GO

Score 97/100 (>= 80), **0 ecart CRITICAL**, **0 ecart MAJOR** (l'ecart [MAJ]
SSRF de l'audit initial est leve). L'ecart [MIN] 8.5.2 est partiellement
remedie (python-multipart borne) mais reste ouvert sur `torch`/`torchvision` ;
l'[INFO] trivyignore `CVE-2026-40393` expiree reste ouvert (hors perimetre de
la remediation). Conditions de suivi (non bloquantes) :
1. Borner `torch`/`torchvision` (ou documenter l'exemption) pour clore 8.5.2.
2. Re-trier / prolonger `CVE-2026-40393` dans `.trivyignore.yaml`.
3. Optionnel : epingler l'IP resolue pour la requete du probe (anti-rebinding).
