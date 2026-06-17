"""Serveur MCP Gallica.

Expose les API publiques de Gallica (BnF) en outils MCP, utilisables par un
agent. Transport stdio par défaut.

Workflow type (généalogie) :
    1. ``gallica_search``        — trouver un registre / un périodique → ARK
    2. ``gallica_issues``        — pour la presse, lister les numéros par date
    3. ``gallica_ocr_search``    — chercher un patronyme dans l'OCR
    4. ``gallica_page_image_url``/``gallica_iiif_manifest`` — consulter les vues
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import GallicaClient, GallicaError

mcp = FastMCP("gallica")

# Client partagé pour toute la durée de vie du serveur.
_client = GallicaClient()


def _ok(payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **payload}


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}


@mcp.tool()
async def gallica_search(
    query: str,
    maximum_records: int = 10,
    start_record: int = 1,
) -> dict[str, Any]:
    """Recherche des documents dans Gallica via l'API SRU (requête CQL).

    Exemples de `query` (CQL) :
      - `gallica all "Victor Hugo"`
      - `dc.title all "journal officiel" and dc.date >= "1914"`
      - `dc.creator all "Zola" and dc.type all "monographie"`
      - `arkPress all "cb32895690m_date"` (numéros d'un périodique)

    Renvoie le nombre total de résultats et une liste de notices avec leur ARK,
    titre, auteur, date et type.
    """
    try:
        resp = await _client.search(
            query,
            start_record=start_record,
            maximum_records=min(max(maximum_records, 1), 50),
        )
    except GallicaError as exc:
        return _err(str(exc))
    return _ok(resp.to_dict())


@mcp.tool()
async def gallica_metadata(ark: str) -> dict[str, Any]:
    """Métadonnées Dublin Core d'un document à partir de son ARK.

    Accepte `ark:/12148/bpt6k...`, `bpt6k...` ou une URL Gallica.
    """
    try:
        return _ok(await _client.metadata(ark))
    except GallicaError as exc:
        return _err(str(exc))


@mcp.tool()
async def gallica_pagination(ark: str) -> dict[str, Any]:
    """Structure de pagination d'un document : nombre de vues et feuillets.

    Utile pour savoir combien de pages (`f{n}`) sont disponibles avant de
    demander des images IIIF.
    """
    try:
        return _ok(await _client.pagination(ark))
    except GallicaError as exc:
        return _err(str(exc))


@mcp.tool()
async def gallica_issues(ark: str, year: str | None = None) -> dict[str, Any]:
    """Liste les numéros d'un périodique (presse).

    Sans `year` : renvoie les années de parution disponibles.
    Avec `year` (format `YYYY`) : renvoie les ARK des numéros de cette année.
    `ark` est celui du périodique (souvent un identifiant `cb...`).
    """
    try:
        return _ok(await _client.issues(ark, year))
    except GallicaError as exc:
        return _err(str(exc))


@mcp.tool()
async def gallica_ocr_search(
    ark: str,
    query: str,
    page: int | None = None,
    start_result: int = 1,
) -> dict[str, Any]:
    """Recherche plein texte dans l'OCR d'un document (ContentSearch).

    Idéal pour retrouver un nom/patronyme dans un document numérisé (ex. presse
    ancienne). Renvoie les occurrences avec le feuillet et un extrait de
    contexte. `page` limite la recherche à un feuillet précis.
    """
    try:
        return _ok(await _client.content_search(ark, query, page=page, start_result=start_result))
    except GallicaError as exc:
        return _err(str(exc))


@mcp.tool()
async def gallica_iiif_manifest(ark: str) -> dict[str, Any]:
    """Manifeste IIIF Presentation (JSON) d'un document : structure + images.

    Renvoie le manifeste tel quel ; il contient les canvases (vues) et les
    URL des services d'images IIIF.
    """
    try:
        return _ok({"manifest": await _client.iiif_manifest(ark)})
    except GallicaError as exc:
        return _err(str(exc))


@mcp.tool()
async def gallica_page_image_url(
    ark: str,
    page: int,
    region: str = "full",
    size: str = "full",
    rotation: int = 0,
) -> dict[str, Any]:
    """Construit l'URL IIIF de l'image d'un feuillet (page) d'un document.

    - `page` : numéro du feuillet (la vue `f{page}`).
    - `region` : `full` ou `x,y,w,h` pour découper une zone.
    - `size` : `full`, `max`, `,1000` (hauteur en px), `pct:50`, etc.
    - `rotation` : degrés (0, 90, 180, 270).

    Ne télécharge rien : renvoie une URL directement consultable.
    """
    try:
        url = _client.iiif_image_url(ark, page, region=region, size=size, rotation=rotation)
    except GallicaError as exc:
        return _err(str(exc))
    return _ok({"image_url": url})


def main() -> None:
    """Point d'entrée : lance le serveur MCP sur le transport stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
