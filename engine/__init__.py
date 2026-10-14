# -*- coding: utf-8 -*-
"""
ChordWeaver engine.

Pure-Python, dependency-free core: music theory, voicing rules, the fitness
function, the genetic algorithm and the exporters. Nothing in this package
imports a GUI toolkit, so it can be driven from the desktop app, from
``cli.py`` or from a test suite equally well.

The usual entry point is :func:`engine.session.generate`.
"""

#: La versión del programa entero, y la única. La interfaz la muestra al pie
#: de la configuración; cualquier otro lugar que la necesite la lee de acá.
__version__ = "1.3.1"

# El motor compilado, desde una ruta corta si la del programa es larga: con
# el ejecutable unas carpetas adentro, Windows no carga los `.pyd` y el
# programa se cerraba al arrancar. Antes de cualquier otro módulo del
# paquete, porque el primero que se importa ya es compilado. Ver `shortpath`.
from . import shortpath as _shortpath  # noqa: E402

_shortpath.relocate(__path__, "engine", __version__)
