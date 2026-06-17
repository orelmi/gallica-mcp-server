#!/usr/bin/env python3
"""Recherche Gallica en ligne de commande (toutes les notices d'une requête).

Pagine l'API SRU et liste l'ensemble des résultats (ARK, titre, auteur, date,
type). Pratique pour explorer un patronyme avant de passer aux outils MCP.

Exemples :
    python scripts/recherche.py 'gallica all "Bouvy"'
    python scripts/recherche.py 'dc.creator all "Bouvy"' --max 200
    python scripts/recherche.py 'gallica all "famille Bouvy"' --json > bouvy.json

À lancer depuis une machine ayant accès à gallica.bnf.fr.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gallica_mcp.client import GallicaClient, GallicaError  # noqa: E402

PAGE_SIZE = 50


async def collect(query: str, cap: int) -> tuple[int, list[dict]]:
    """Récupère jusqu'à `cap` notices en paginant l'API SRU."""
    out: list[dict] = []
    total = 0
    async with GallicaClient() as client:
        start = 1
        while len(out) < cap:
            batch = min(PAGE_SIZE, cap - len(out))
            resp = await client.search(query, start_record=start, maximum_records=batch)
            total = resp.total
            if not resp.records:
                break
            out.extend(r.to_dict() for r in resp.records)
            start += len(resp.records)
            if start > total:
                break
    return total, out


def _print_table(total: int, records: list[dict]) -> None:
    print(f"\n{total} résultat(s) au total — {len(records)} affiché(s)\n")
    for i, r in enumerate(records, 1):
        print(f"[{i}] {r.get('title') or '(sans titre)'}")
        meta = " · ".join(
            v for v in (r.get("creator"), r.get("date"), r.get("type")) if v
        )
        if meta:
            print(f"     {meta}")
        if r.get("ark"):
            print(f"     {r['ark']}")
            print(f"     https://gallica.bnf.fr/{r['ark']}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Requête CQL (ex. 'gallica all \"Bouvy\"').")
    parser.add_argument("--max", type=int, default=100, help="Nombre max de notices (défaut 100).")
    parser.add_argument("--json", action="store_true", help="Sortie JSON brute.")
    args = parser.parse_args()

    try:
        total, records = asyncio.run(collect(args.query, args.max))
    except GallicaError as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        raise SystemExit(1)

    if args.json:
        json.dump(
            {"query": args.query, "total_results": total, "records": records},
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        print()
    else:
        _print_table(total, records)


if __name__ == "__main__":
    main()
