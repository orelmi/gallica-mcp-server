# Référence des outils MCP

Chaque outil renvoie un objet JSON. En cas de succès : `{"ok": true, ...}`.
En cas d'erreur (réseau, ARK invalide, diagnostic SRU…) :
`{"ok": false, "error": "message"}`.

Les outils acceptent un ARK sous n'importe quelle forme :
`ark:/12148/bpt6k5619759j`, `bpt6k5619759j` ou une URL Gallica complète.

---

## `gallica_search`

Recherche de documents via l'API SRU 1.2 (langage CQL).

**Paramètres**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `query` | str | — | Requête CQL (voir exemples) |
| `maximum_records` | int | 10 | Nombre de notices (borné à 50) |
| `start_record` | int | 1 | Pagination (1-based) |

**Exemple d'appel**

```json
{ "query": "dc.creator all \"Zola\" and dc.type all \"monographie\"", "maximum_records": 5 }
```

**Réponse (extrait)**

```json
{
  "ok": true,
  "total_results": 312,
  "returned": 5,
  "records": [
    {
      "ark": "ark:/12148/bpt6k5619759j",
      "title": "Germinal",
      "creator": "Zola, Émile",
      "date": "1885",
      "type": "monographie",
      "language": "fre",
      "publisher": "G. Charpentier"
    }
  ]
}
```

---

## `gallica_metadata`

Métadonnées Dublin Core d'un document (service OAIRecord).

**Paramètres** : `ark` (str).

**Réponse (extrait)**

```json
{
  "ok": true,
  "ark": "ark:/12148/bpt6k5619759j",
  "title": "Germinal",
  "creator": "Zola, Émile",
  "date": "1885",
  "dublin_core": { "subject": ["Roman"], "rights": ["domaine public"] }
}
```

`dublin_core` contient l'ensemble des champs DC bruts (listes de valeurs).

---

## `gallica_pagination`

Structure de pagination : nombre de vues et correspondance feuillet ↔ page.

**Paramètres** : `ark` (str).

**Réponse (extrait)**

```json
{
  "ok": true,
  "ark": "ark:/12148/bpt6k5619759j",
  "total_views": 592,
  "pages": [{ "order": "1", "number": "NP", "physical": "" }]
}
```

Le `total_views` donne le `f{n}` maximal exploitable côté IIIF.

---

## `gallica_issues`

Numéros d'un périodique (presse). L'ARK est celui du **titre** (souvent `cb...`).

**Paramètres**

| Nom | Type | Description |
|-----|------|-------------|
| `ark` | str | ARK du périodique |
| `year` | str \| null | Année `YYYY` ; si absent → liste des années |

**Sans `year`** → `{"years": ["1914", "1915", ...]}`
**Avec `year`** → liste des numéros et leur ARK :

```json
{
  "ok": true,
  "periodical_ark": "ark:/12148/cb32895690m",
  "years": [],
  "issues": [{ "ark": "bpt6k...", "date": "1914-08-02", "label": "..." }]
}
```

---

## `gallica_ocr_search`

Recherche plein texte dans l'OCR d'un document (ContentSearch). **L'outil clé
pour la généalogie** : retrouver un patronyme dans la presse ancienne.

**Paramètres**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `ark` | str | — | ARK du document |
| `query` | str | — | Terme recherché (ex. un patronyme) |
| `page` | int \| null | null | Limiter à un feuillet `f{n}` |
| `start_result` | int | 1 | Pagination des occurrences |

**Réponse (extrait)**

```json
{
  "ok": true,
  "ark": "ark:/12148/bpt6k...",
  "query": "Dupont",
  "total_matches": 3,
  "matches": [{ "page": "PAG_5", "snippet": "...mariage de M. Dupont..." }]
}
```

---

## `gallica_iiif_manifest`

Manifeste IIIF Presentation (JSON brut) : canvases (vues) et services d'images.

**Paramètres** : `ark` (str).
**Réponse** : `{"ok": true, "manifest": { ... }}` (manifeste IIIF tel quel).

---

## `gallica_page_image_url`

Construit l'URL IIIF d'une image **sans rien télécharger**.

**Paramètres**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `ark` | str | — | ARK du document |
| `page` | int | — | Numéro de feuillet (vue `f{n}`) |
| `region` | str | `full` | `full` ou `x,y,w,h` |
| `size` | str | `full` | `full`, `max`, `,1000`, `pct:50`… |
| `rotation` | int | 0 | 0, 90, 180, 270 |

**Réponse**

```json
{
  "ok": true,
  "image_url": "https://gallica.bnf.fr/iiif/ark:/12148/bpt6k.../f12/full/,1000/0/native.jpg"
}
```
