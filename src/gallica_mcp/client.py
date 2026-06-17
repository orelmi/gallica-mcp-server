"""Client HTTP pour les API publiques de Gallica (BnF).

Toutes les API Gallica sont en accès libre et sans clé. Le dénominateur commun
est l'identifiant ARK (``ark:/12148/{id}``). Ce module encapsule :

* l'API de recherche SRU 1.2 (requêtes CQL) ;
* l'API Document (OAIRecord, Pagination, Toc, Issues, ContentSearch) ;
* l'API IIIF (manifeste de présentation + construction d'URL d'images).

Le parsing XML reste volontairement défensif : Gallica renvoie du XML aux
namespaces variables (SRU/Dublin Core/OAI), on cherche donc les éléments par
nom local plutôt que par QName complet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable
from xml.etree import ElementTree as ET

import httpx

BASE_URL = "https://gallica.bnf.fr"
SRU_ENDPOINT = f"{BASE_URL}/SRU"
SERVICES_ENDPOINT = f"{BASE_URL}/services"
IIIF_ENDPOINT = f"{BASE_URL}/iiif"

DEFAULT_USER_AGENT = "gallica-mcp-server/0.1 (+https://github.com/orelmi/gallica-mcp-server)"
DEFAULT_TIMEOUT = 30.0

_ARK_PREFIX = "ark:/12148/"
_ARK_RE = re.compile(r"(ark:/12148/)?(?P<id>[0-9a-zA-Z]+)")


class GallicaError(RuntimeError):
    """Erreur réseau ou réponse invalide d'un service Gallica."""


def normalize_ark(ark: str) -> tuple[str, str]:
    """Normalise un ARK en deux formes utiles.

    Accepte ``ark:/12148/bpt6k...``, ``bpt6k...`` ou une URL Gallica complète,
    et renvoie ``(ark_complet, identifiant_court)``.

    * ``ark_complet`` (``ark:/12148/bpt6k...``) sert pour les chemins IIIF.
    * ``identifiant_court`` (``bpt6k...``) sert pour le paramètre ``ark=`` des
      services Document.
    """
    if not ark or not ark.strip():
        raise GallicaError("ARK vide")
    cleaned = ark.strip()
    # Extrait l'ARK depuis une éventuelle URL (gallica.bnf.fr/ark:/12148/...).
    if "ark:/12148/" in cleaned:
        cleaned = cleaned[cleaned.index("ark:/12148/") :]
    cleaned = cleaned.split("/")[-1] if cleaned.startswith(BASE_URL) else cleaned
    short = cleaned[len(_ARK_PREFIX) :] if cleaned.startswith(_ARK_PREFIX) else cleaned
    # Retire un éventuel suffixe de page/feuillet (ex. /f12) ou query.
    short = short.split("/")[0].split("?")[0].split(".")[0]
    if not short:
        raise GallicaError(f"ARK non reconnu : {ark!r}")
    return f"{_ARK_PREFIX}{short}", short


def _localname(tag: str) -> str:
    """Retire le namespace ``{...}`` d'un tag XML."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _iter_local(elem: ET.Element, name: str) -> Iterable[ET.Element]:
    """Itère récursivement sur les descendants dont le nom local == ``name``."""
    for child in elem.iter():
        if _localname(child.tag) == name:
            yield child


def _first_text(elem: ET.Element, name: str) -> str | None:
    for found in _iter_local(elem, name):
        if found.text and found.text.strip():
            return found.text.strip()
    return None


@dataclass
class SearchResult:
    """Une notice renvoyée par la recherche SRU."""

    ark: str | None
    title: str | None
    creator: str | None
    date: str | None
    type: str | None
    language: str | None
    publisher: str | None
    raw: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ark": self.ark,
            "title": self.title,
            "creator": self.creator,
            "date": self.date,
            "type": self.type,
            "language": self.language,
            "publisher": self.publisher,
        }


@dataclass
class SearchResponse:
    total: int
    records: list[SearchResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_results": self.total,
            "returned": len(self.records),
            "records": [r.to_dict() for r in self.records],
        }


class GallicaClient:
    """Client asynchrone pour les services Gallica.

    À utiliser comme context manager async, ou en réutilisant une instance
    partagée (le serveur MCP en crée une seule pour tout le cycle de vie).
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    async def __aenter__(self) -> "GallicaClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ---- transport -------------------------------------------------------

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        try:
            resp = await self._client.get(url, params=params)
        except httpx.HTTPError as exc:  # réseau, timeout, DNS...
            raise GallicaError(f"Échec de la requête vers {url} : {exc}") from exc
        if resp.status_code >= 400:
            raise GallicaError(
                f"Gallica a répondu {resp.status_code} pour {resp.url}"
            )
        return resp

    async def _get_xml(self, url: str, params: dict[str, Any] | None = None) -> ET.Element:
        resp = await self._get(url, params)
        try:
            return ET.fromstring(resp.content)
        except ET.ParseError as exc:
            raise GallicaError(f"Réponse XML invalide depuis {resp.url} : {exc}") from exc

    # ---- 1. Recherche SRU ------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        start_record: int = 1,
        maximum_records: int = 10,
        collapsing: bool = True,
    ) -> SearchResponse:
        """Recherche SRU 1.2 en CQL.

        ``query`` est une requête CQL, par ex. ::

            gallica all "Victor Hugo"
            dc.title all "journal officiel" and dc.date >= "1914"
            arkPress all "cb32895690m_date"   # numéros d'un périodique

        ``collapsing`` regroupe les résultats d'un même document.
        """
        params = {
            "version": "1.2",
            "operation": "searchRetrieve",
            "query": query,
            "startRecord": start_record,
            "maximumRecords": maximum_records,
            "collapsing": "true" if collapsing else "false",
        }
        root = await self._get_xml(SRU_ENDPOINT, params)

        diagnostic = _first_text(root, "message")
        total_text = _first_text(root, "numberOfRecords")
        total = int(total_text) if total_text and total_text.isdigit() else 0

        records: list[SearchResult] = []
        for record in _iter_local(root, "record"):
            fields: dict[str, list[str]] = {}
            for el in record.iter():
                name = _localname(el.tag)
                if name in _DC_FIELDS and el.text and el.text.strip():
                    fields.setdefault(name, []).append(el.text.strip())
            if not fields:
                continue
            records.append(
                SearchResult(
                    ark=_extract_ark(fields),
                    title=_first(fields, "title"),
                    creator=_first(fields, "creator"),
                    date=_first(fields, "date"),
                    type=_first(fields, "type"),
                    language=_first(fields, "language"),
                    publisher=_first(fields, "publisher"),
                    raw=fields,
                )
            )

        if not records and diagnostic:
            raise GallicaError(f"SRU diagnostic : {diagnostic}")
        return SearchResponse(total=total, records=records)

    # ---- 2. API Document -------------------------------------------------

    async def metadata(self, ark: str) -> dict[str, Any]:
        """Métadonnées Dublin Core d'un document (service OAIRecord)."""
        _, short = normalize_ark(ark)
        root = await self._get_xml(f"{SERVICES_ENDPOINT}/OAIRecord", {"ark": short})
        dc: dict[str, list[str]] = {}
        for el in root.iter():
            name = _localname(el.tag)
            if name in _DC_FIELDS and el.text and el.text.strip():
                dc.setdefault(name, []).append(el.text.strip())
        return {
            "ark": f"{_ARK_PREFIX}{short}",
            "title": _first(dc, "title"),
            "creator": _first(dc, "creator"),
            "date": _first(dc, "date"),
            "publisher": _first(dc, "publisher"),
            "type": _first(dc, "type"),
            "language": _first(dc, "language"),
            "source": _first(dc, "source"),
            "dublin_core": dc,
        }

    async def pagination(self, ark: str) -> dict[str, Any]:
        """Structure de pagination : nb de vues, feuillets, etc."""
        _, short = normalize_ark(ark)
        root = await self._get_xml(f"{SERVICES_ENDPOINT}/Pagination", {"ark": short})
        nb_pages = _first_text(root, "nbVueImages")
        pages = []
        for page in _iter_local(root, "page"):
            pages.append(
                {
                    "order": _first_text(page, "ordre"),
                    "number": _first_text(page, "numero"),
                    "physical": _first_text(page, "pagination"),
                }
            )
        return {
            "ark": f"{_ARK_PREFIX}{short}",
            "total_views": int(nb_pages) if nb_pages and nb_pages.isdigit() else None,
            "pages": pages,
        }

    async def table_of_contents(self, ark: str) -> dict[str, Any]:
        """Table des matières (service Toc), renvoyée en XML brut + texte."""
        _, short = normalize_ark(ark)
        resp = await self._get(f"{SERVICES_ENDPOINT}/Toc", {"ark": short})
        return {"ark": f"{_ARK_PREFIX}{short}", "toc_xml": resp.text}

    async def issues(self, ark: str, year: str | None = None) -> dict[str, Any]:
        """Numéros d'un périodique (service Issues).

        Sans ``year`` : renvoie les années de parution disponibles.
        Avec ``year`` (``YYYY``) : renvoie les ARK des numéros de cette année.
        L'``ark`` attendu est celui du périodique (souvent ``cb...``).
        """
        _, short = normalize_ark(ark)
        params: dict[str, Any] = {"ark": short}
        if year:
            params["date"] = year
        root = await self._get_xml(f"{SERVICES_ENDPOINT}/Issues", params)

        years = [y.text.strip() for y in _iter_local(root, "year") if y.text]
        items = []
        for issue in _iter_local(root, "issue"):
            items.append(
                {
                    "ark": issue.get("ark"),
                    "date": issue.get("dateMiseEnLigne") or issue.get("date"),
                    "label": (issue.text or "").strip() or None,
                }
            )
        return {
            "periodical_ark": f"{_ARK_PREFIX}{short}",
            "years": years,
            "issues": items,
        }

    async def content_search(
        self,
        ark: str,
        query: str,
        *,
        page: int | None = None,
        start_result: int = 1,
    ) -> dict[str, Any]:
        """Recherche plein texte dans l'OCR d'un document (ContentSearch).

        Idéal pour retrouver un patronyme dans la presse ancienne. Renvoie les
        occurrences avec leur feuillet (``f{n}``) et un extrait de contexte.
        """
        _, short = normalize_ark(ark)
        params: dict[str, Any] = {"ark": short, "query": query, "startResult": start_result}
        if page is not None:
            params["page"] = page
        root = await self._get_xml(f"{SERVICES_ENDPOINT}/ContentSearch", params)

        items = []
        for item in _iter_local(root, "item"):
            content = _first_text(item, "content")
            page_no = _first_text(item, "p_id") or _first_text(item, "page")
            items.append({"page": page_no, "snippet": content})
        total = _first_text(root, "items") or _first_text(root, "numberOfResults")
        return {
            "ark": f"{_ARK_PREFIX}{short}",
            "query": query,
            "total_matches": int(total) if total and total.isdigit() else len(items),
            "matches": items,
        }

    # ---- 3. API IIIF -----------------------------------------------------

    async def iiif_manifest(self, ark: str) -> dict[str, Any]:
        """Manifeste IIIF Presentation (JSON) d'un document."""
        full, _ = normalize_ark(ark)
        resp = await self._get(f"{IIIF_ENDPOINT}/{full}/manifest.json")
        try:
            return resp.json()
        except ValueError as exc:
            raise GallicaError(f"Manifeste IIIF invalide pour {full} : {exc}") from exc

    @staticmethod
    def iiif_image_url(
        ark: str,
        page: int,
        *,
        region: str = "full",
        size: str = "full",
        rotation: int = 0,
        quality: str = "native",
        fmt: str = "jpg",
    ) -> str:
        """Construit une URL IIIF Image pour un feuillet donné.

        Schéma : ``/iiif/{ark}/f{page}/{region}/{size}/{rotation}/{quality}.{fmt}``.
        ``region`` peut être ``full`` ou ``x,y,w,h`` ; ``size`` ``full``,
        ``max``, ``,1000`` (hauteur), ``pct:50``, etc.
        """
        full, _ = normalize_ark(ark)
        return (
            f"{IIIF_ENDPOINT}/{full}/f{page}/{region}/{size}/{rotation}/{quality}.{fmt}"
        )


# --- helpers Dublin Core ---------------------------------------------------

_DC_FIELDS = {
    "title",
    "creator",
    "contributor",
    "date",
    "type",
    "language",
    "publisher",
    "subject",
    "description",
    "identifier",
    "source",
    "rights",
    "format",
    "relation",
    "coverage",
}


def _first(fields: dict[str, list[str]], key: str) -> str | None:
    values = fields.get(key)
    return values[0] if values else None


def _extract_ark(fields: dict[str, list[str]]) -> str | None:
    """Trouve l'ARK parmi les identifiants Dublin Core."""
    for ident in fields.get("identifier", []):
        if "ark:/12148/" in ident:
            try:
                full, _ = normalize_ark(ident)
                return full
            except GallicaError:
                continue
    return None
