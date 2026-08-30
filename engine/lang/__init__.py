# -*- coding: utf-8 -*-
"""
Los catálogos de traducción, uno por idioma.

Cada catálogo es un diccionario `castellano -> otro idioma`, partido en
varios módulos por área nada más que para que ningún archivo sea imposible
de abrir. :func:`catalog` los junta en uno solo la primera vez que se pide
un idioma y guarda el resultado.

**La clave es la cadena castellana tal cual está escrita en el código.** No
se normaliza nada: un espacio de más es otra entrada. Por eso las claves no
se escriben a mano sino que las saca `python -m engine.lang.audit` leyendo
las llamadas a `tr()` del programa, y esa misma herramienta avisa cuál
falta y cuál sobra.
"""

from __future__ import annotations

from typing import Dict

_CACHE: Dict[str, Dict[str, str]] = {}

#: Qué módulos forma cada idioma. El castellano no tiene: es el original.
PARTS = {
    "en": ("en_app", "en_screens", "en_tools", "en_engine", "en_story",
           "en_book"),
}


def catalog(code: str) -> Dict[str, str]:
    """El catálogo entero de un idioma. Vacío si no hay ninguno."""
    cached = _CACHE.get(code)
    if cached is not None:
        return cached
    merged: Dict[str, str] = {}
    for part in PARTS.get(code, ()):
        try:
            module = __import__("engine.lang." + part, fromlist=["CATALOG"])
        except Exception:                                   # noqa: BLE001
            # Un pedazo que falta deja esa área en castellano y el resto
            # traducido, que es mucho mejor que no traducir nada.
            continue
        merged.update(getattr(module, "CATALOG", {}) or {})
    _CACHE[code] = merged
    return merged
