# Guide : retrouver un nom dans la presse ancienne

Ce scénario illustre l'enchaînement des outils MCP pour un usage généalogique :
on cherche les mentions d'un patronyme dans un journal régional d'une période
donnée. L'agent enchaîne les appels ; voici la logique.

## 1. Trouver le périodique → ARK

On cherche le titre de presse avec `gallica_search`. Pour cibler la presse,
on filtre sur le type et la date.

```json
// gallica_search
{ "query": "dc.title all \"Le Petit Journal\" and dc.type all \"fascicule\"", "maximum_records": 5 }
```

On récupère l'ARK du titre (ou de l'un de ses numéros). Pour un titre de presse,
l'identifiant ressemble souvent à `cb32895690m`.

## 2. (Presse) Lister les numéros d'une année

À partir de l'ARK du périodique, on liste les années disponibles puis les
numéros d'une année précise.

```json
// gallica_issues — années disponibles
{ "ark": "ark:/12148/cb32895690m" }

// gallica_issues — numéros de 1914
{ "ark": "ark:/12148/cb32895690m", "year": "1914" }
```

Chaque numéro renvoyé porte son propre ARK (`bpt6k...`) et sa date de parution.

## 3. Chercher le patronyme dans l'OCR

Sur l'ARK d'un numéro, on lance une recherche plein texte. C'est l'étape la plus
utile : elle indique **sur quels feuillets** le nom apparaît, avec un extrait.

```json
// gallica_ocr_search
{ "ark": "ark:/12148/bpt6k...", "query": "Dupont", "start_result": 1 }
```

Réponse type : `total_matches`, puis pour chaque occurrence un `page`
(ex. `PAG_5`) et un `snippet` de contexte.

## 4. Consulter / archiver l'image de la page

Une fois le bon feuillet repéré (ex. feuillet 5), on génère l'URL IIIF de
l'image. On peut demander une zone précise et une taille adaptée.

```json
// gallica_page_image_url — page entière, hauteur 2000 px
{ "ark": "ark:/12148/bpt6k...", "page": 5, "size": ",2000" }

// gallica_page_image_url — zone découpée (région x,y,w,h)
{ "ark": "ark:/12148/bpt6k...", "page": 5, "region": "1200,800,900,600" }
```

L'URL renvoyée est directement ouvrable dans un navigateur ou téléchargeable.

## Variante : registres / monographies

Pour un registre numérisé (pas de la presse), on saute l'étape `gallica_issues` :

```
gallica_search          → ARK du registre
gallica_pagination      → nombre de vues (f1..fN)
gallica_ocr_search      → repérer un nom (si l'OCR existe)
gallica_iiif_manifest   → structure complète / table des vues
gallica_page_image_url  → image d'un acte
```

## Astuce CQL

- `gallica all "..."` cherche dans tous les champs (le plus large).
- Combinez avec `and` / `or` : `dc.creator all "..." and dc.date >= "1850"`.
- Pour restreindre à la presse, `dc.type all "fascicule"` est souvent efficace.
