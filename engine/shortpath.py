"""
Los módulos compilados, cargados desde una ruta corta cuando la del programa
es larga.

Windows no carga una DLL ---y un ``.pyd`` es una DLL--- desde una ruta de más
de unos 250 caracteres: ``LoadLibrary`` contesta que el nombre es demasiado
largo y el ``import`` falla. Con el programa descomprimido unas carpetas
adentro alcanza: el motor compilado con Cython (``engine/*.pyd``) no cargaba
y el ejecutable se cerraba al arrancar, sin decir nada porque no tiene
consola. Lo mismo le pasa a Pillow, que customtkinter usa para las imágenes.

La salida es la misma que con las fuentes (ver ``app._rescue_widget_fonts`` y
``staff.load_music_font``): una copia en ``%TEMP%``, que es una ruta corta, y
el paquete busca ahí primero. Sólo en el ejecutable y sólo si hace falta;
desde el fuente no se toca nada.

Este módulo no importa nada del proyecto: lo usa ``engine/__init__`` antes
de que exista cualquier otro.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from typing import List

#: Desde qué largo de ruta se copia. Por debajo del límite real, que varía
#: unos caracteres según cómo se cargue la DLL: con la ruta justo debajo, un
#: ``.pyd`` cargaba y el de al lado no.
LIMIT = 200

#: La carpeta de las copias, dentro de la temporal del sistema.
FOLDER = "ChordWeaver-modules"


def _extended(path: str) -> str:
    """La misma ruta con el prefijo que deja pasar de 260 en Windows."""
    if os.name != "nt" or path.startswith("\\\\?\\"):
        return path
    return "\\\\?\\" + os.path.abspath(path)


def relocate(search_path: List[str], package: str, tag: str) -> bool:
    """
    Copiar los ``.pyd`` de un paquete a una ruta corta y buscar ahí primero.

    `search_path` es el ``__path__`` del paquete, `package` su nombre y `tag`
    lo que separa una versión del programa de otra en la carpeta de copias.
    Devuelve True si el paquete quedó buscando en la copia. Nada de esto
    levanta excepciones: si no se puede copiar, el import se intenta desde
    donde estaba, que es lo que pasaba siempre.
    """
    if not getattr(sys, "frozen", False):
        return False
    try:
        here = search_path[0]
        names = [name for name in os.listdir(_extended(here))
                 if name.lower().endswith(".pyd")]
    except (OSError, IndexError, TypeError):
        return False
    if not names:
        return False
    if max(len(os.path.join(here, name)) for name in names) < LIMIT:
        return False
    safe_tag = "".join(c if c.isalnum() or c in "._-" else "-" for c in tag)
    target = os.path.join(tempfile.gettempdir(), FOLDER, safe_tag, package)
    try:
        os.makedirs(target, exist_ok=True)
        for name in names:
            source = _extended(os.path.join(here, name))
            copy = os.path.join(target, name)
            # Otra copia del programa abierta tiene la DLL cargada y no se
            # puede pisar; si es del mismo tamaño es la misma y alcanza.
            if (not os.path.exists(copy)
                    or os.path.getsize(copy) != os.path.getsize(source)):
                shutil.copyfile(source, copy)
        search_path.insert(0, target)
    except (OSError, AttributeError):
        return False
    return True
