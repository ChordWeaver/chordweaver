# -*- coding: utf-8 -*-
"""
Qué falta traducir y qué sobra en el catálogo.

Las claves del catálogo son las cadenas castellanas **tal cual están
escritas en el código**, y varias se arman pegando renglones. Copiarlas a
mano es exactamente la clase de trabajo donde un espacio de más no se ve y
deja la entrada muerta, así que no se copian: esta herramienta lee el árbol
de sintaxis y las saca de ahí.

Junta dos cosas:

* lo que pasa por `tr()`, `trf()`, `trs()` o `N()`, que es lo que el
  programa va a buscar de verdad;
* y además **toda la prosa castellana suelta** de los módulos que guardan
  texto en tablas ---el libro, el guion, los logros---, porque ahí el
  castellano vive en una constante y quien lo traduce es el `tr()` de la
  pantalla que la dibuja, lejos de donde está escrito.

Cosechar de más no rompe nada: **el catálogo es pasivo**. Nadie busca una
cadena por su traducción --- `tr()` se llama sólo donde el texto entra a un
widget ---, así que una entrada que no se dibuja nunca es trabajo perdido y
no un error. Lo caro es lo contrario: una que se dibuja y no está.

    python -m engine.lang.audit            # el resumen
    python -m engine.lang.audit --missing  # las que faltan, listas para pegar
    python -m engine.lang.audit --orphans  # las que ya no usa nadie
    python -m engine.lang.audit --file app.py   # sólo las de un archivo

Devuelve 1 cuando falta alguna, así que sirve de prueba.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from typing import Dict, List, Optional, Set, Tuple

#: Dónde se busca. Es el programa entero menos las pruebas y las
#: herramientas de compilación, que no le hablan a ningún usuario.
ROOTS = ("app.py", "analyzer.py", "spectrum.py", "staff.py", "updater.py",
         "chooser.py", "cinematic.py", "cli.py", "engine")

SKIP = {"tests.py", "audit.py", "build_engine.py", "verify_ui.py",
        "uitest.py", "i18n.py"}

#: Los nombres con los que se llama a la traducción. `N` no traduce nada
#: --- marca ---, pero para juntar claves es lo mismo.
CALLS = {"tr", "trf", "trs", "N"}

#: Qué se considera prosa castellana. Pide una marca del idioma ---un
#: acento, una eñe, un signo de apertura o una palabra corta de las que sólo
#: aparecen en castellano--- para no arrastrar los nombres de acordes, las
#: claves internas ni los formatos.
SPANISH = re.compile(
    r"[áéíóúüñÁÉÍÓÚÜÑ¿¡]"
    r"|\b(el|la|los|las|de|del|que|un|una|unos|unas|con|para|por|se|no|es|"
    r"y|en|al|lo|su|sus|como|cuando|si|pero|cada|todo|toda|todos|todas|hay|"
    r"ser|sin|sobre|desde|entre|hasta|este|esta|esto|esos|esas|ya|solo|"
    r"vos|acá|allá|nada|nunca|siempre|donde|porque|aunque|mismo|misma)\b",
    re.I)

#: Y además tiene que parecer una frase: dos palabras, o una sola palabra
#: acentuada. Una cadena de una palabra sin acento es casi siempre una clave.
LETTERS = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")

#: Lo que la cosecha encuentra y **no** hay que traducir, con el motivo.
#: Es una lista corta y a mano: son los casos en que la cadena parece prosa
#: pero nadie la busca nunca en el catálogo.
IGNORED = {
    # El encabezado de un MusicXML: es formato de archivo, no interfaz. Cae
    # acá porque el DOCTYPE trae palabras sueltas que parecen castellano.
    # `theory.py` está en la base del programa y no importa nada del
    # proyecto ---ni siquiera `i18n`---, así que sus mensajes de error no
    # pasan por `tr()`. Los otros seis ya estaban en inglés desde antes.
    'no se entiende la fundamental de',
}


def _ignored(text: str) -> bool:
    """Si esta cadena está en la lista de las que no se traducen."""
    if text in IGNORED:
        return True
    # Cualquier cosa con forma de marcado es formato, no interfaz.
    return "<" in text and ">" in text


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))


def _sources() -> List[str]:
    root = _project_root()
    found: List[str] = []
    for entry in ROOTS:
        path = os.path.join(root, entry)
        if os.path.isfile(path):
            found.append(path)
        elif os.path.isdir(path):
            for base, _dirs, files in os.walk(path):
                parts = base.split(os.sep)
                if "lang" in parts or "__pycache__" in parts:
                    continue
                for name in sorted(files):
                    if name.endswith(".py") and name not in SKIP:
                        found.append(os.path.join(base, name))
    return found


def _called_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _strings_in(node: ast.AST) -> List[str]:
    """Las cadenas literales de un argumento, lista incluida."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        out: List[str] = []
        for item in node.elts:
            out.extend(_strings_in(item))
        return out
    # `tr(a if x else b)` traduce el resultado, así que las claves son las
    # dos ramas. Lo mismo con `a or b` y con `"pre " + algo`.
    if isinstance(node, ast.IfExp):
        return _strings_in(node.body) + _strings_in(node.orelse)
    if isinstance(node, ast.BoolOp):
        out = []
        for item in node.values:
            out.extend(_strings_in(item))
        return out
    if isinstance(node, ast.BinOp):
        return _strings_in(node.left) + _strings_in(node.right)
    return []


def _docstrings(tree: ast.AST) -> Set[int]:
    """
    Las cadenas que son comentario y no interfaz.

    El docstring de un módulo, de una clase o de una función, y además
    **cualquier cadena suelta puesta como sentencia**: eso es un comentario
    escrito con comillas --- a veces un docstring que quedó debajo de un
    `return` --- y nadie lo lee nunca desde la ventana.
    """
    found: Set[int] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            found.add(id(node.value))
    return found


def is_prose(text: str) -> bool:
    """Si una cadena suelta parece algo que alguien va a leer."""
    stripped = text.strip()
    if len(stripped) < 4 or not SPANISH.search(stripped):
        return False
    if _ignored(stripped):
        return False
    words = [w for w in re.split(r"\s+", stripped) if LETTERS.search(w)]
    if len(words) >= 2:
        return True
    # Una sola palabra sólo cuenta si lleva acento: «Género» sí, «voices» no.
    return bool(re.search(r"[áéíóúüñÁÉÍÓÚÜÑ]", stripped))


def keys_in_source() -> Dict[str, Set[str]]:
    """Cada cadena traducible y en qué archivos aparece."""
    found: Dict[str, Set[str]] = {}
    root = _project_root()
    for path in _sources():
        try:
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
        except (OSError, SyntaxError):
            continue
        short = os.path.relpath(path, root).replace(os.sep, "/")
        docs = _docstrings(tree)
        marked: Set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _called_name(node) not in CALLS or not node.args:
                continue
            for item in _strings_in(node.args[0]):
                if item:
                    found.setdefault(item, set()).add(short)
            for sub in ast.walk(node.args[0]):
                marked.add(id(sub))
        # Y la prosa suelta: la que vive en una tabla y se traduce lejos.
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and id(node) not in docs and id(node) not in marked
                    and is_prose(node.value)):
                found.setdefault(node.value, set()).add(short)
    return found


def compare(code: str = "en", only: Optional[str] = None
            ) -> Tuple[List[str], List[str], Dict[str, Set[str]]]:
    from engine import lang
    stored = lang.catalog(code)
    # Una sola pasada por el código: leer el árbol de sintaxis del programa
    # entero cuesta un segundo, y preguntarlo por cada clave del catálogo lo
    # multiplicaba por mil.
    everything = keys_in_source()
    source = everything
    if only:
        source = {key: where for key, where in everything.items()
                  if any(only in place for place in where)}
    missing = [key for key in source if key not in stored]
    orphans = [key for key in stored if key not in everything]
    return missing, orphans, source


def _as_entries(keys: List[str], source: Dict[str, Set[str]]) -> str:
    lines: List[str] = []
    for key in sorted(keys, key=lambda k: (sorted(source.get(k, ["?"]))[0], k)):
        lines.append("    %r: %r," % (key, key))
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    only = None
    if "--file" in argv:
        only = argv[argv.index("--file") + 1]
    missing, orphans, source = compare("en", only)
    if "--missing" in argv:
        print(_as_entries(missing, source))
    elif "--orphans" in argv:
        for key in sorted(orphans):
            print(repr(key))
    else:
        print("cadenas traducibles en el código: %d" % len(source))
        print("traducidas:                      %d" % (len(source) - len(missing)))
        print("faltan:                          %d" % len(missing))
        print("sobran en el catálogo:           %d" % len(orphans))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.path.insert(0, _project_root())
    raise SystemExit(main(sys.argv[1:]))
