# -*- coding: utf-8 -*-
"""
Los huevos de pascua: qué los dispara, cuántos van y el título secreto.

Este módulo es **datos, detectores y estado**, igual que ``story.py``. No
dibuja nada y no suena nada: la viñeta, el zorro, la explosión y los
carteles viven en ``app.py``, y los ruidos en ``engine/ambience.py``. Acá
está sólo la respuesta a dos preguntas: *¿esto que acaba de hacer el usuario
es un huevo?* y *¿cuántos lleva encontrados?*

Por qué no son logros
---------------------
Un logro se anuncia, se lista y dice cómo se consigue. Un huevo de pascua es
lo contrario: no se anuncia, no se lista y la única señal de que existe es
un contador que dice cuántos hay y ninguno cuál. Meterlos en el catálogo de
``achievements.py`` los habría convertido en cuarenta y seis renglones con
su descripción al lado, que es exactamente lo que un huevo no puede tener.
Por eso tienen su propio archivo --- ``eggs.json``, al lado de
``history.json``, ``achievements.json`` y ``story.json`` --- y su propia
clase de estado.

Los detectores son funciones puras
----------------------------------
Cada uno recibe lo que el usuario escribió o eligió y devuelve un booleano.
No tocan el estado, no guardan nada y no saben que existe una ventana: eso
los vuelve verificables desde ``tests.py`` sin abrir la aplicación, que es
la única forma sensata de probar un huevo cuya condición es "exactamente
esta combinación y ninguna otra".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import history

_FILENAME = "eggs.json"

#: Lo que se gana encontrándolos todos. No es un logro del catálogo: es un
#: título aparte, y se entrega recién cuando el usuario toca el huevo dorado.
SECRET_TITLE = "Adepto del azar"

SECRET_NOTE = (
    "No sé si hiciste trampa o genuinamente lograste todo, pero tu lealtad "
    "no ha pasado desapercibida. Gracias por usar mi aplicación."
)

SECRET_SIGNATURE = "firma: El creador"


@dataclass(frozen=True)
class Egg:
    """Un huevo del catálogo.

    ``name`` no se muestra en ninguna parte mientras el huevo esté sin
    encontrar --- ni siquiera tachado. Existe para el historial interno y
    para que los tests hablen de algo.
    """

    key: str
    name: str
    #: Los pasos exactos para volver a provocarlo.
    #:
    #: **No se muestra en ninguna parte mientras el juego siga abierto.** Es
    #: la recompensa de haber terminado el cien por ciento de los logros: ahí
    #: ya no queda nada que arruinar, y lo único que sigue teniendo valor es
    #: poder mostrárselos a otro. Antes de eso el contador dice cuántos hay y
    #: jamás cuáles.
    recipe: str = ""


CATALOG: Tuple[Egg, ...] = (
    Egg("zombie", "El rugido",
        "Armonizador. Dibujá exactamente tres notas en el pentagrama: la "
        "tónica, la tónica otra vez y la quinta, las tres redondas y sin "
        "ninguna más. Tocá «Escuchar»."),
    Egg("fox", "El zorro",
        "Engranaje de configuración. Escribí 1, 9, 8 y 7 en los cuatro "
        "primeros campos del algoritmo genético, de arriba hacia abajo, y "
        "dale a «Aceptar»."),
    Egg("glasses", "Los anteojos",
        "Engranaje de configuración. Llevá el dial del tamaño de letra hasta "
        "el tope y soltalo."),
    Egg("blast", "El hongo",
        "Generador. En la pantalla de armonía, las cinco barras al máximo y "
        "absolutamente todos los tildes puestos --- los intercambios modales "
        "uno por uno, las séptimas, las dos modulaciones, las cromáticas y "
        "las notas de paso de cada voz --- y generá."),
    Egg("locksmith", "El cerrajero",
        "Organizador. Escribí al menos dos acordes y ponéles el candado a "
        "todos, sin dejar ninguno libre. Seguí a la pantalla siguiente."),
    Egg("bach", "Agradecé que Bach está muerto",
        "Barroco, con «Modo coral» encendido y las quintas paralelas "
        "permitidas al mismo tiempo. Generá."),
)

BY_KEY: Dict[str, Egg] = {egg.key: egg for egg in CATALOG}

#: Cuántos hay. El contador de la pantalla de logros lo muestra; cuáles son,
#: no.
TOTAL = len(CATALOG)


# ---------------------------------------------------------------------------
# Los detectores
# ---------------------------------------------------------------------------

#: Una redonda, en negras. Es la duración que pide el rugido.
WHOLE = 4.0

#: Semitonos de la quinta justa sobre la tónica.
FIFTH = 7


def zombie_call(written: Sequence[Tuple[int, float]], tonic: int) -> bool:
    """
    ¿La melodía es tónica, tónica y quinta, las tres redondas?

    ``written`` es lo que devuelve el pentagrama: pares de altura MIDI y
    duración en negras. La condición es **estricta** --- exactamente tres
    notas, las tres redondas, en ese orden y en ninguna otra combinación ---
    porque el huevo tiene que poder escribirse a propósito y no caer solo en
    la mitad de una melodía cualquiera. La octava no importa: lo que se
    escucha es el grado.
    """
    if len(written) != 3:
        return False
    if any(abs(duration - WHOLE) > 1e-6 for _pitch, duration in written):
        return False
    classes = [pitch % 12 for pitch, _duration in written]
    home = tonic % 12
    return classes == [home, home, (home + FIFTH) % 12]


#: Los cuatro primeros campos del algoritmo genético, de arriba hacia abajo,
#: y lo que hay que escribir en ellos. Son los que se ven sin desplazar el
#: panel.
FOX_FIELDS: Tuple[str, ...] = ("population_size", "generations", "elitism",
                               "tournament_size")
FOX_SEQUENCE: Tuple[str, ...] = ("1", "9", "8", "7")


def fox_numbers(values: Dict[str, str]) -> bool:
    """
    ¿Están los cuatro primeros parámetros en 1, 9, 8, 7, de arriba a abajo?

    Se compara el texto tal cual quedó escrito y no el número: la
    configuración nunca llega a aplicarse --- una población de 1 la rechaza
    la validación --- así que lo único que existe en ese momento es lo que
    dice cada casilla.
    """
    return tuple(str(values.get(key, "")).strip()
                 for key in FOX_FIELDS) == FOX_SEQUENCE


def glasses(scale: float, maximum: float) -> bool:
    """¿El tamaño de letra está en el tope del dial?"""
    return scale >= maximum - 1e-6


def all_locked(entries: Sequence) -> bool:
    """
    ¿Están todos los acordes escritos con el candado puesto?

    Los silencios no cuentan --- no hay nada que fijar en un silencio ---, y
    hacen falta al menos dos acordes: con uno solo, "todos" es una palabra
    demasiado grande para lo que pasó.
    """
    chords = [entry for entry in entries if not getattr(entry, "is_rest", False)]
    if len(chords) < 2:
        return False
    return all(getattr(entry, "locked_pitches", None) for entry in chords)


def bach_spinning(chorale: bool, forbid_parallel_fifths: bool) -> bool:
    """¿Modo coral con las quintas paralelas permitidas?"""
    return bool(chorale) and not forbid_parallel_fifths


#: Cada dial del generador con su tope. El huevo pide el tope de todos, y no
#: el valor exacto: los deslizadores no se clavan en un pixel, así que se
#: acepta el último tramo de cada uno.
BLAST_DIALS: Tuple[Tuple[str, float], ...] = (
    ("borrowed", 40.0),
    ("harmony", 14.0),
    ("modulation", 60.0),
    ("colour", 30.0),
    ("passing", 1.0),
)

#: Qué tan cerca del tope hay que estar, en partes del recorrido total.
BLAST_MARGIN = 0.02


def blast(dials: Dict[str, float], switches: Iterable[bool]) -> bool:
    """
    ¿Está el generador con todo al máximo y todo prendido?

    ``dials`` son las cinco barras de la pantalla de armonía y ``switches``
    todo lo que se puede tildar ahí: los intercambios modales uno por uno,
    las séptimas, las dos modulaciones, las cromáticas y las notas de paso
    de cada voz. Falta uno solo y no hay explosión.
    """
    for name, top in BLAST_DIALS:
        value = dials.get(name)
        if value is None or value < top * (1.0 - BLAST_MARGIN):
            return False
    values = list(switches)
    return bool(values) and all(values)


# ---------------------------------------------------------------------------
# Lo que el usuario lleva encontrado
# ---------------------------------------------------------------------------

def eggs_path() -> str:
    return os.path.join(history.base_directory(), _FILENAME)


class Basket:
    """
    Los huevos encontrados, persistidos en ``eggs.json``.

    Misma regla que el registro de logros y que el estado del sendero: se
    guarda sólo cuando algo cambió, y un archivo roto o de otra versión no
    puede impedir que el programa arranque.
    """

    def __init__(self, found: Optional[Dict[str, str]] = None,
                 claimed: bool = False, path: Optional[str] = None):
        #: clave -> marca de tiempo ISO.
        self.found: Dict[str, str] = dict(found or {})
        #: Si el usuario ya tocó el huevo dorado y se quedó con el título.
        self.claimed = claimed
        self.path = path

    # -- persistencia -------------------------------------------------------

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Basket":
        target = path or eggs_path()
        if not os.path.exists(target):
            return cls(path=path)
        try:
            with open(target, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return cls(path=path)
        if not isinstance(raw, dict):
            return cls(path=path)
        stored = raw.get("found", {})
        if not isinstance(stored, dict):
            stored = {}
        clean = {k: str(v) for k, v in stored.items() if k in BY_KEY}
        return cls(clean, bool(raw.get("claimed", False)), path=path)

    def save(self) -> None:
        target = self.path or eggs_path()
        try:
            with open(target, "w", encoding="utf-8") as handle:
                json.dump({"found": self.found, "claimed": self.claimed},
                          handle, indent=2, ensure_ascii=False)
        except OSError:
            pass          # una carpeta de sólo lectura no puede romper nada

    # -- consultas ----------------------------------------------------------

    def has(self, key: str) -> bool:
        return key in self.found

    def count(self) -> int:
        return len(self.found)

    def complete(self) -> bool:
        return self.count() >= TOTAL

    def missing(self) -> List[str]:
        """Las claves que faltan. No se muestra en ninguna pantalla."""
        return [egg.key for egg in CATALOG if egg.key not in self.found]

    # -- hallazgo -----------------------------------------------------------

    def find(self, key: str) -> bool:
        """
        Anotar un huevo. Devuelve ``True`` sólo la primera vez.

        Es lo que decide si la animación corre: repetir la combinación no
        vuelve a dispararla, igual que un logro no se gana dos veces.
        """
        if key not in BY_KEY or key in self.found:
            return False
        self.found[key] = datetime.now().isoformat(timespec="seconds")
        self.save()
        return True

    def claim(self) -> bool:
        """Quedarse con el título. ``True`` si acaba de entregarse."""
        if self.claimed or not self.complete():
            return False
        self.claimed = True
        self.save()
        return True

    def titles(self) -> List[str]:
        """El título secreto, si ya se reclamó. Vacío mientras tanto."""
        return [SECRET_TITLE] if self.claimed else []
