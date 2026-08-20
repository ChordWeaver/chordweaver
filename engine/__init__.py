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
__version__ = "1.0.1"
