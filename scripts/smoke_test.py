#!/usr/bin/env python3
"""Test manuel des requêtes Gallica (SRU + Document + IIIF), sans MCP.

À lancer depuis une machine ayant accès à gallica.bnf.fr :

    python scripts/smoke_test.py
    python scripts/smoke_test.py --query 'gallica all "Jean Jaurès"'

Affiche les résultats en clair pour vérifier que les endpoints répondent et
que le parsing fonctionne.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gallica_mcp.client import GallicaClient, GallicaError  # noqa: E402


def _show(title: str, data: object) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])


async def run(query: str) -> int:
    async with GallicaClient() as client:
        try:
            search = await client.search(query, maximum_records=3)
        except GallicaError as exc:
            print(f"[ERREUR] Recherche SRU : {exc}", file=sys.stderr)
            return 1

        _show(f"SRU — {search.total} résultats pour {query!r}", search.to_dict())
        if not search.records:
            print("Aucun résultat, arrêt.")
            return 0

        ark = next((r.ark for r in search.records if r.ark), None)
        if not ark:
            print("Pas d'ARK exploitable dans les résultats.")
            return 0
        print(f"\nARK retenu : {ark}")

        try:
            _show("Métadonnées (OAIRecord)", await client.metadata(ark))
        except GallicaError as exc:
            print(f"[avert] metadata : {exc}", file=sys.stderr)

        try:
            pagination = await client.pagination(ark)
            _show("Pagination", {"total_views": pagination.get("total_views")})
        except GallicaError as exc:
            print(f"[avert] pagination : {exc}", file=sys.stderr)

        print("\n=== IIIF ===")
        print("Manifeste :", f"https://gallica.bnf.fr/iiif/{ark}/manifest.json")
        print("Image f1  :", client.iiif_image_url(ark, 1, size=",1000"))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query",
        default='gallica all "Victor Hugo"',
        help="Requête CQL pour l'API SRU.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.query)))


if __name__ == "__main__":
    main()
