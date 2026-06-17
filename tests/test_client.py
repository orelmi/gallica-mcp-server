"""Tests hors-ligne du parsing et de la normalisation (pas d'accès réseau)."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gallica_mcp.client import GallicaClient, GallicaError, normalize_ark  # noqa: E402


@pytest.mark.parametrize(
    "raw,expected_short",
    [
        ("ark:/12148/bpt6k5619759j", "bpt6k5619759j"),
        ("bpt6k5619759j", "bpt6k5619759j"),
        ("https://gallica.bnf.fr/ark:/12148/bpt6k5619759j/f12.item", "bpt6k5619759j"),
        ("ark:/12148/bpt6k5619759j/f3", "bpt6k5619759j"),
    ],
)
def test_normalize_ark(raw: str, expected_short: str) -> None:
    full, short = normalize_ark(raw)
    assert short == expected_short
    assert full == f"ark:/12148/{expected_short}"


def test_normalize_ark_rejects_empty() -> None:
    with pytest.raises(GallicaError):
        normalize_ark("   ")


def test_iiif_image_url() -> None:
    url = GallicaClient.iiif_image_url("bpt6k5619759j", 12, size=",1000")
    assert url == (
        "https://gallica.bnf.fr/iiif/ark:/12148/bpt6k5619759j/f12/full/,1000/0/native.jpg"
    )


def test_iiif_image_url_region_rotation() -> None:
    url = GallicaClient.iiif_image_url(
        "ark:/12148/bpt6k5619759j", 1, region="0,0,500,500", rotation=90
    )
    assert "/f1/0,0,500,500/full/90/native.jpg" in url


SRU_SAMPLE = """<?xml version="1.0"?>
<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/">
  <srw:numberOfRecords>42</srw:numberOfRecords>
  <srw:records>
    <srw:record>
      <srw:recordData>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>Les Misérables</dc:title>
          <dc:creator>Hugo, Victor</dc:creator>
          <dc:date>1862</dc:date>
          <dc:type>monographie</dc:type>
          <dc:language>fre</dc:language>
          <dc:identifier>https://gallica.bnf.fr/ark:/12148/bpt6k5619759j</dc:identifier>
        </oai_dc:dc>
      </srw:recordData>
    </srw:record>
  </srw:records>
</srw:searchRetrieveResponse>"""


def _client_with_response(content: str, content_type: str = "text/xml") -> GallicaClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content.encode(), headers={"content-type": content_type})

    transport = httpx.MockTransport(handler)
    return GallicaClient(client=httpx.AsyncClient(transport=transport))


async def test_search_parses_records() -> None:
    client = _client_with_response(SRU_SAMPLE)
    try:
        resp = await client.search('gallica all "Hugo"')
    finally:
        await client._client.aclose()
    assert resp.total == 42
    assert len(resp.records) == 1
    rec = resp.records[0]
    assert rec.title == "Les Misérables"
    assert rec.creator == "Hugo, Victor"
    assert rec.date == "1862"
    assert rec.ark == "ark:/12148/bpt6k5619759j"


CONTENT_SEARCH_SAMPLE = """<?xml version="1.0"?>
<results>
  <query>Dupont</query>
  <items>2</items>
  <item><p_id>PAG_5</p_id><content>...mariage de M. Dupont...</content></item>
  <item><p_id>PAG_9</p_id><content>...succession Dupont...</content></item>
</results>"""


async def test_content_search_parses_matches() -> None:
    client = _client_with_response(CONTENT_SEARCH_SAMPLE)
    try:
        out = await client.content_search("bpt6k5619759j", "Dupont")
    finally:
        await client._client.aclose()
    assert out["total_matches"] == 2
    assert out["matches"][0]["page"] == "PAG_5"
    assert "Dupont" in out["matches"][0]["snippet"]


async def test_http_error_raises_gallica_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, content=b"forbidden")

    client = GallicaClient(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    try:
        with pytest.raises(GallicaError):
            await client.search("x")
    finally:
        await client._client.aclose()
