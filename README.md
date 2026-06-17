# gallica-mcp-server

Serveur **MCP** (Model Context Protocol) pour interroger **Gallica**, la
bibliothèque numérique de la BnF — plus de 7 millions de documents, en accès
libre et **sans clé d'API**. Tout passe par de simples requêtes HTTP, et le
dénominateur commun de tous les services est l'identifiant **ARK**
(`ark:/12148/...`).

Pensé pour un usage **généalogique** : retrouver un registre ou un journal,
puis chercher un patronyme dans l'OCR de la presse ancienne et consulter les
images des actes via IIIF.

## Outils MCP exposés

| Outil | API Gallica | Rôle |
|-------|-------------|------|
| `gallica_search` | SRU 1.2 (CQL) | Rechercher des documents → ARK |
| `gallica_metadata` | Document / OAIRecord | Métadonnées Dublin Core d'un document |
| `gallica_pagination` | Document / Pagination | Nombre de vues et feuillets |
| `gallica_issues` | Document / Issues | Numéros d'un périodique par année (presse) |
| `gallica_ocr_search` | Document / ContentSearch | Recherche plein texte dans l'OCR |
| `gallica_iiif_manifest` | IIIF Presentation | Manifeste (structure + images) |
| `gallica_page_image_url` | IIIF Image | URL de l'image d'un feuillet |

## Workflow type (généalogie)

```
gallica_search           → trouver un registre / un périodique → ARK
   └─ gallica_issues     → (presse) lister les numéros d'une année
   └─ gallica_ocr_search → chercher un patronyme dans l'OCR
   └─ gallica_page_image_url / gallica_iiif_manifest → consulter les vues
```

## Installation

Nécessite Python ≥ 3.10.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .          # installe le serveur + dépendances (mcp, httpx)
```

## Lancement

Le serveur communique en **stdio** (transport MCP standard) :

```bash
gallica-mcp-server
# ou
python -m gallica_mcp
```

### Configuration dans un client MCP (ex. Claude Desktop)

```json
{
  "mcpServers": {
    "gallica": {
      "command": "gallica-mcp-server"
    }
  }
}
```

Si vous n'installez pas le paquet, pointez directement vers l'interpréteur du
venv :

```json
{
  "mcpServers": {
    "gallica": {
      "command": "/chemin/vers/.venv/bin/python",
      "args": ["-m", "gallica_mcp"]
    }
  }
}
```

## Tester les requêtes sans MCP

Un script de fumée appelle directement les API Gallica (SRU → métadonnées →
IIIF) et affiche les résultats :

```bash
python scripts/smoke_test.py
python scripts/smoke_test.py --query 'gallica all "Jean Jaurès"'
```

> ⚠️ Gallica doit être joignable depuis la machine. Certains environnements
> CI/cloud bloquent `gallica.bnf.fr` (réponse `403`) ; lancez alors le script
> depuis votre poste. Les **tests unitaires** (`pytest`), eux, n'ont besoin
> d'aucun réseau.

## Exemples de requêtes CQL (pour `gallica_search`)

```text
gallica all "Victor Hugo"
dc.title all "journal officiel" and dc.date >= "1914"
dc.creator all "Zola" and dc.type all "monographie"
arkPress all "cb32895690m_date"        # numéros d'un périodique de presse
```

Index utiles : `gallica` (tous champs), `dc.title`, `dc.creator`, `dc.date`,
`dc.type`, `dc.language`, `dc.subject`, `dc.publisher`. Opérateurs : `all`,
`any`, `adj`, `=`, `>=`, `<=`, combinables avec `and` / `or`.

## URL IIIF Image

`gallica_page_image_url` construit des URL de la forme :

```
https://gallica.bnf.fr/iiif/ark:/12148/{ark}/f{n}/{region}/{size}/{rotation}/native.jpg
```

- `region` : `full` ou `x,y,w,h` (zone à découper)
- `size`   : `full`, `max`, `,1000` (hauteur en px), `pct:50`, …
- `rotation` : `0`, `90`, `180`, `270`

## Développement

```bash
pip install -e ".[dev]"
pytest                    # tests hors-ligne (transport HTTP mocké)
```

Structure :

```
src/gallica_mcp/
  client.py    # GallicaClient : HTTP + parsing (SRU, Document, IIIF)
  server.py    # outils MCP (FastMCP)
scripts/
  smoke_test.py
tests/
  test_client.py
```

## Notes & limites

- API **non officielles dans le détail** : Gallica fait parfois évoluer ses
  services. Le parsing XML est volontairement défensif (recherche par nom
  local d'élément, tous namespaces confondus).
- Pas de cache ni de rate-limiting intégré pour l'instant — restez courtois
  avec les serveurs de la BnF.
- Pour du **moissonnage en masse**, préférez OAI-PMH ou data.bnf.fr (SPARQL),
  non couverts ici.

## Licence

MIT.
