"""Serveur MCP pour Gallica (Bibliothèque nationale de France).

Expose les API publiques de Gallica (SRU, Document/ContentSearch, IIIF) sous
forme d'outils MCP, sans clé d'API. Le point commun de tous les services est
l'identifiant ARK du document (``ark:/12148/...``).
"""

from .client import GallicaClient, GallicaError, normalize_ark

__all__ = ["GallicaClient", "GallicaError", "normalize_ark"]
__version__ = "0.1.0"
