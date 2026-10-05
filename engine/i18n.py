# -*- coding: utf-8 -*-
"""
Los dos idiomas del programa.

El original está escrito en castellano y **el castellano es la clave**: cada
cadena que se ve en pantalla se busca tal cual está escrita en el código y,
si no hay traducción, se devuelve la misma cadena. Eso tiene dos
consecuencias que importan:

* agregar una pantalla nueva no rompe nada --- sale en castellano hasta que
  alguien le escriba la entrada inglesa;
* envolver de más tampoco rompe nada --- una cadena que no es prosa
  simplemente no está en el catálogo y pasa de largo.

**La traducción ocurre al dibujar, no al importar.** Las tablas de prosa del
programa ---las tarjetas, el libro, los diálogos--- siguen guardando el
castellano; quien lo convierte es el `tr()` del lugar donde el texto entra a
un widget. Es lo que permite cambiar de idioma desde la configuración sin
reabrir el programa: alcanza con volver a dibujar.

Este módulo no importa nada del proyecto y nada de la interfaz.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

#: Los idiomas, en el orden en que se ofrecen. La clave es la que se guarda
#: en las preferencias; el rótulo está escrito en su propio idioma, que es
#: como se elige un idioma que todavía no está puesto.
LANGUAGES: Tuple[Tuple[str, str], ...] = (
    ("es", "Español (Argentina)"),
    ("en", "English (United States)"),
)

#: Con cuál se escribió el programa. Es también el que vale cuando la
#: preferencia guardada dice cualquier otra cosa.
DEFAULT = "es"

_current = DEFAULT
_catalog: Dict[str, str] = {}
#: El catálogo al revés, para los menús. Ver :func:`untr`.
_reverse: Dict[str, str] = {}


def languages() -> Tuple[Tuple[str, str], ...]:
    return LANGUAGES


def codes() -> List[str]:
    return [code for code, _label in LANGUAGES]


def label_of(code: str) -> str:
    for key, label in LANGUAGES:
        if key == code:
            return label
    return code


def language() -> str:
    """El idioma en curso."""
    return _current


def is_default() -> bool:
    """Si se está hablando en el idioma en el que está escrito el programa."""
    return _current == DEFAULT


def set_language(code: str) -> str:
    """
    Cambiar de idioma y cargar su catálogo. Devuelve el que quedó puesto.

    Un código desconocido ---o un catálogo que no se puede importar--- deja
    el castellano: un idioma que falta no puede ser el motivo por el que el
    programa no abre.
    """
    global _current, _catalog, _reverse
    code = (code or "").strip().lower()
    if code not in codes():
        code = DEFAULT
    _current = code
    _catalog = _load_catalog(code)
    # El revés se arma una vez por idioma. Si dos entradas castellanas
    # cayeran en la misma traducción, gana la primera --- y es un error del
    # catálogo, no de acá: dos opciones de un menú que se leen igual no se
    # pueden distinguir en ningún idioma.
    _reverse = {}
    for spanish, other in _catalog.items():
        _reverse.setdefault(other, spanish)
    return _current


def _load_catalog(code: str) -> Dict[str, str]:
    if code == DEFAULT:
        return {}
    try:
        from engine import lang as _lang
        return _lang.catalog(code)
    except Exception:                                       # noqa: BLE001
        return {}


def tr(text: str) -> str:
    """
    El texto en el idioma en curso.

    Sin traducción devuelve lo que le dieron, que es el castellano original.
    No levanta excepciones ni con `None`: es la función más llamada de la
    interfaz y un error acá dejaría una pantalla a medio dibujar.
    """
    if not _catalog or not isinstance(text, str) or not text:
        return text
    return _catalog.get(text, text)


#: Los nombres de voz que guardaba el historial antes de que el catálogo de
#: voces pasara a castellano. Una corrida vieja dice «Bass»; sin esto, con la
#: interfaz en castellano seguía diciendo «Bass».
_OLD_VOICE_NAMES = {"Bass": "Bajo", "Baritone": "Barítono",
                    "Mezzo-soprano": "Mezzosoprano"}


def tr_name(name: str) -> str:
    """
    El nombre de una voz en el idioma en curso, con su número si lo tiene.

    Dos voces del mismo tipo se llaman «Bajo 1» y «Bajo 2», y `tr()` busca
    la frase entera: ninguna de las dos está en el catálogo y salían en
    castellano con la interfaz en inglés. Se traduce el nombre y se le
    vuelve a pegar el número.
    """
    if not isinstance(name, str) or not name:
        return name
    base, _, number = name.rpartition(" ")
    if not (base and number.isdigit()):
        base, number = name, ""
    base = _OLD_VOICE_NAMES.get(base, base)
    return tr(base) + (" " + number if number else "")


def trf(text: str, *args, **kwargs) -> str:
    """
    Traducir y después rellenar los huecos: ``trf("Paso {n}", n=3)``.

    Los huecos van **con nombre** para que la traducción pueda ordenarlos de
    otra manera. Si el formato falla ---una traducción con un hueco que no
    existe--- se devuelve el original formateado, que es peor que la
    traducción y mucho mejor que una pantalla rota.
    """
    translated = tr(text)
    try:
        return translated.format(*args, **kwargs)
    except (IndexError, KeyError, ValueError):
        try:
            return text.format(*args, **kwargs)
        except (IndexError, KeyError, ValueError):
            return text


def untr(text: str) -> str:
    """
    De vuelta al castellano: lo que un menú **muestra** a lo que el programa
    **compara**.

    Un desplegable de Tk devuelve el renglón que se ve, así que traducir sus
    opciones rompería todas las comparaciones del programa contra el
    castellano --- que están escritas en decenas de lugares y son la
    definición de lo que cada opción significa. Con esto se traduce sólo lo
    que se dibuja: se muestra con `trs()` y se lee con `untr()`, y en el
    medio no cambia una sola comparación.

    Lo que no salió de una traducción vuelve tal cual, así que en castellano
    no hace nada.
    """
    if not _reverse or not isinstance(text, str) or not text:
        return text
    return _reverse.get(text, text)


def N(text: str) -> str:
    """
    Marcar una cadena para traducir **sin** traducirla ahora.

    Es para la prosa que vive en una constante de módulo ---las tarjetas,
    los pasos del tutorial, el guion--- que se arma al importar, cuando
    todavía no hay ningún idioma elegido. La traducción de verdad la hace el
    `tr()` del lugar donde ese texto entra a un widget; esto no hace nada en
    tiempo de ejecución y existe para dos lectores: el que lee el código y
    ve que ese renglón se traduce, y `engine.lang.audit`, que junta las
    claves leyendo el árbol de sintaxis.
    """
    return text


def trs(items: Iterable[str]) -> List[str]:
    """Traducir una lista de cadenas, para las que van a un menú."""
    return [tr(item) for item in items]


# ---------------------------------------------------------------------------
# Los nombres de las notas
#
# El castellano las dice con solfeo ---Do, Re, Mi--- y el inglés con las
# letras que el motor ya usa por dentro. Es la única parte de la traducción
# que no es una cadena buscada en una tabla, porque las notas se arman a
# partir de un número.
# ---------------------------------------------------------------------------

#: Cómo se dice cada letra. Vacío en inglés: la letra ya es el nombre.
_SOLFEGE = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa", "G": "Sol",
            "A": "La", "B": "Si"}

_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

_SOLFEGE_SHARP = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#",
                  "La", "La#", "Si"]
_SOLFEGE_FLAT = ["Do", "Reb", "Re", "Mib", "Mi", "Fa", "Solb", "Sol", "Lab",
                 "La", "Sib", "Si"]


def note_name(pc: int, prefer_flats: bool = False) -> str:
    """Cómo se llama esa altura en el idioma en curso."""
    index = int(pc) % 12
    if _current == "en":
        return (_FLAT if prefer_flats else _SHARP)[index]
    return (_SOLFEGE_FLAT if prefer_flats else _SOLFEGE_SHARP)[index]


def say_letter(letter: str) -> str:
    """
    Una letra suelta ---la de una nota escrita «F#4»--- como se dice.

    En inglés se dice la letra, así que se devuelve tal cual.
    """
    if _current == "en":
        return letter
    return _SOLFEGE.get(letter, letter)


def spell(name: str) -> str:
    """
    Un nombre de nota entero ---«F#», «Bb»--- como se dice.

    Se traduce la letra y se le devuelve la alteración pegada, que es la
    misma en los dos idiomas.
    """
    if _current == "en" or not name:
        return name
    return say_letter(name[0]) + name[1:]
