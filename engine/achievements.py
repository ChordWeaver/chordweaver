# -*- coding: utf-8 -*-
"""
Logros: el catálogo, el archivo donde se guardan y los detectores.

Este módulo no sabe nada de la interfaz. Se divide en tres partes:

* **El catálogo** -- qué logros existen, a qué estrella pertenecen y qué
  título dorado otorgan los legendarios.
* **:class:`Tracker`** -- qué tiene desbloqueado este usuario, persistido en
  ``achievements.json`` al lado del programa igual que el historial.
* **Los detectores** -- funciones puras que miran una corrida terminada, una
  melodía o una lista de acordes escritos y devuelven las claves que
  corresponden.

Sobre el costo
--------------
La detección corre una sola vez por corrida (o por clic), nunca dentro del
AG ni por cada tecla. Además todo detector recibe el conjunto de logros que
todavía faltan: lo que ya está desbloqueado no se vuelve a buscar, así que el
trabajo tiende a cero a medida que el usuario completa el juego. El único
recorrido cuadrático -- el barrido de quintas paralelas, pares de voces por
par de acordes -- está detrás de esa comprobación.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import history
from .fitness import GENRE_PROFILES, parallel_interval_violation
from .harmony import SET_PIECES, is_applied_dominant
from .theory import ROLE_FIFTH, ROLE_SEVENTH, ROLE_THIRD, Chord

_FILENAME = "achievements.json"

#: Título por completar las tres estrellas.
TRIUMPH_TITLE = "Triunfador"

#: Cuántas estrellas hay.
STAR_COUNT = 3


@dataclass(frozen=True)
class Achievement:
    """Un logro del catálogo.

    ``star`` es 1, 2 o 3; los legendarios llevan 0 porque no pertenecen a
    ninguna estrella y no cuentan para completarlas.
    """

    key: str
    name: str
    description: str
    star: int
    #: Sólo los legendarios otorgan título.
    title: str = ""
    legendary: bool = False

    @property
    def star_label(self) -> str:
        if self.legendary:
            return "Legendario"
        return f"{'★' * self.star}{'☆' * (STAR_COUNT - self.star)}"


# ---------------------------------------------------------------------------
# El catálogo
# ---------------------------------------------------------------------------

CATALOG: Tuple[Achievement, ...] = (
    # -- primera estrella ---------------------------------------------------
    Achievement("generator_first", "Escritor del caos",
                "Utilizá el generador por primera vez.", 1),
    Achievement("organiser_first", "Contrapunto del aprendiz",
                "Utilizá el organizador por primera vez.", 1),
    Achievement("harmoniser_first", "Armando y uniendo",
                "Utilizá el armonizador por primera vez.", 1),
    Achievement("genre_baroque", "Aprendiz de Bach",
                "Creá tu primera partitura barroca.", 1),
    Achievement("genre_gregorian", "Hombre de Fe",
                "Creá tu primera partitura gregoriana.", 1),
    Achievement("genre_jazz", "Nace un estándar",
                "Creá tu primer jazz.", 1),
    Achievement("seventh_chord", "Un mundo más allá",
                "Descubrí las séptimas.", 1),
    Achievement("first_rest", "Shhhh!",
                "Colocá tu primer silencio.", 1),
    Achievement("first_playback", "¿Quién necesita leer?",
                "Reproducí tu primera pieza.", 1),
    Achievement("first_export", "Músico digital",
                "Exportá tu primera partitura.", 1),
    Achievement("exotic_mode", "Mirando más allá",
                "Hacé una partitura en un modo que no sea el jónico ni el "
                "eólico.", 1),
    Achievement("passing_notes", "Caminamos juntos",
                "Creá tus primeras notas de paso.", 1),
    Achievement("cadential_six_four", "Dominación absoluta",
                "Escribí tu primer dominante 6/4.", 1),
    Achievement("diminished_chord", "El tenebroso",
                "Escribí tu primer acorde disminuido.", 1),
    Achievement("no_parallel_fifths", "Sin quintas, por favor",
                "Completá tu primera partitura sin quintas paralelas.", 1),
    Achievement("history_open", "Tomando nota",
                "Utilizá el historial por primera vez.", 1),
    Achievement("tutorial_done", "Aprendiz",
                "Completá el tutorial.", 1),
    Achievement("book_read", "Lector comprometido",
                "Leé el libro de teoría.", 1),

    # -- segunda estrella ---------------------------------------------------
    Achievement("set_piece_vivaldi", "El 1er Blues",
                "Descubrí la cadencia de Vivaldi.", 2),
    Achievement("set_piece_phrygian", "Take the road Jack!",
                "Descubrí la cadencia frigia.", 2),
    Achievement("set_piece_chromatic", "Nacido para sufrir",
                "Descubrí la cadencia descendente de bajo cromático.", 2),
    Achievement("time_five_four", "Take Five",
                "Componé tu primera partitura en 5/4.", 2),
    Achievement("custom_rules", "Rebelde sin causa",
                "Generá tu primera partitura sin usar las reglas por "
                "defecto.", 2),
    Achievement("tritone_leap", "El salto mortal",
                "Realizá un salto tritonal en el armonizador.", 2),
    Achievement("two_locks", "Las reglas están para romperse",
                "Bloqueá al menos dos acordes en el organizador.", 2),
    Achievement("ends_on_dominant", "El inconcluso",
                "Creá una partitura que termine en un dominante.", 2),
    Achievement("parallel_fifth", "Nunca más",
                "Creá tu primera quinta paralela.", 2),
    Achievement("three_dominants", "Efecto dominó",
                "Encadená 3 acordes dominantes seguidos.", 2),
    Achievement("two_five", "Feel the Swing",
                "Realizá tu primer ii-V.", 2),
    Achievement("plagal", "Y el Señor dijo",
                "Realizá tu primera cadencia plagal.", 2),
    Achievement("ga_tuned", "El mejor músico es el ingeniero",
                "Reconfigurá los parámetros del algoritmo genético.", 2),
    Achievement("six_voices", "Máximo poder!",
                "Escribí tu primera partitura a 6 voces.", 2),
    Achievement("sixth_omit_five", "Ole!",
                "Descubrí el acorde de sexta con la quinta omitida.", 2),
    Achievement("modulation", "Navegando nuevos mares",
                "Realizá tu primera modulación en el generador.", 2),
    Achievement("modal_interchange", "Después te lo devuelvo",
                "Realizá tu primer intercambio modal.", 2),

    # -- tercera estrella ---------------------------------------------------
    Achievement("extended_chord", "Unidos estamos, unidos triunfamos",
                "Hacé tu primer acorde de séptima, novena y oncena.", 3),
    Achievement("thief", "Ladrón musical",
                "Permití todos los intercambios modales y poné la modulación "
                "al máximo.", 3),
    Achievement("import_score", "Vine preparado",
                "Importá tu primera partitura.", 3),
    Achievement("principalis_changed", "Director divino",
                "En el modo gregoriano, cambiá la vox principalis.", 3),
    Achievement("supreme_melody", "La melodía suprema",
                "Utilizá todas las notas de la escala junto a todas las "
                "duraciones posibles.", 3),

    # -- legendarios --------------------------------------------------------
    # Las descripciones no dicen cómo se consiguen: se muestran en itálica y
    # son la única pista.
    Achievement("blues_pact", "Encrucijada del Destino",
                "Hay quienes dicen que ciertas progresiones no se aprenden. "
                "Se pactan.", 0, title="Maestro del Blues", legendary=True),
    Achievement("the_lick", "La Profecía",
                "Estaba destinado a suceder.", 0,
                title="The Swingster", legendary=True),
    Achievement("second_coming", "La Segunda Venida",
                "La música sonó y los cielos volvieron a abrirse.", 0,
                title="Hijo de Dios", legendary=True),
)

BY_KEY: Dict[str, Achievement] = {a.key: a for a in CATALOG}

#: Claves de cada estrella, en el orden en que se muestran.
STAR_KEYS: Dict[int, Tuple[str, ...]] = {
    star: tuple(a.key for a in CATALOG if a.star == star and not a.legendary)
    for star in range(1, STAR_COUNT + 1)
}

LEGENDARY_KEYS: Tuple[str, ...] = tuple(a.key for a in CATALOG if a.legendary)


# ---------------------------------------------------------------------------
# Lo que el usuario lleva conseguido
# ---------------------------------------------------------------------------

def achievements_path() -> str:
    return os.path.join(history.base_directory(), _FILENAME)


class Tracker:
    """
    Qué logros tiene este usuario, y el guardado al lado del programa.

    Guarda sólo cuando algo cambió: desbloquear es raro y leer es constante,
    así que el archivo no se toca en cada corrida.
    """

    def __init__(self, unlocked: Optional[Dict[str, str]] = None,
                 stars_seen: int = 0, path: Optional[str] = None):
        #: clave -> marca de tiempo ISO.
        self.unlocked: Dict[str, str] = dict(unlocked or {})
        #: Hasta qué estrella ya se mostró la animación, para no repetirla
        #: cada vez que se abre el programa.
        self.stars_seen = stars_seen
        self.path = path

    # -- persistencia -------------------------------------------------------

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Tracker":
        """Leer el archivo, tolerando que falte o esté roto."""
        target = path or achievements_path()
        if not os.path.exists(target):
            return cls(path=path)
        try:
            with open(target, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (json.JSONDecodeError, OSError):
            # Un archivo dañado no puede impedir que el programa arranque.
            return cls(path=path)
        if not isinstance(raw, dict):
            return cls(path=path)
        stored = raw.get("unlocked", {})
        if not isinstance(stored, dict):
            stored = {}
        # Una clave que ya no existe en el catálogo se descarta en silencio:
        # el archivo puede venir de una versión anterior.
        clean = {k: str(v) for k, v in stored.items() if k in BY_KEY}
        try:
            seen = int(raw.get("stars_seen", 0))
        except (TypeError, ValueError):
            seen = 0
        return cls(clean, max(0, min(STAR_COUNT, seen)), path=path)

    def save(self) -> None:
        target = self.path or achievements_path()
        try:
            with open(target, "w", encoding="utf-8") as handle:
                json.dump({"unlocked": self.unlocked,
                           "stars_seen": self.stars_seen},
                          handle, indent=2, ensure_ascii=False)
        except OSError:
            pass          # una carpeta de sólo lectura no puede romper la app

    # -- consultas ----------------------------------------------------------

    def has(self, key: str) -> bool:
        return key in self.unlocked

    def pending(self) -> Set[str]:
        """Las claves que todavía faltan. Es lo que se pasa a los detectores."""
        return {a.key for a in CATALOG if a.key not in self.unlocked}

    def wants(self, *keys: str) -> bool:
        """¿Vale la pena buscar alguno de estos? Falso si ya están todos."""
        return any(k not in self.unlocked for k in keys)

    def star_progress(self, star: int) -> Tuple[int, int]:
        keys = STAR_KEYS.get(star, ())
        return sum(1 for k in keys if k in self.unlocked), len(keys)

    def star_complete(self, star: int) -> bool:
        done, total = self.star_progress(star)
        return total > 0 and done == total

    def stars(self) -> int:
        """
        Cuántas estrellas están ganadas.

        Una estrella no se gana sin la anterior: se cuenta desde la primera y
        se corta en el primer hueco, así que completar la segunda antes que la
        primera no adelanta nada hasta que la primera cierre.
        """
        earned = 0
        for star in range(1, STAR_COUNT + 1):
            if not self.star_complete(star):
                break
            earned = star
        return earned

    def titles(self) -> List[str]:
        """Los títulos ganados. Se pueden tener varios a la vez."""
        found = [BY_KEY[k].title for k in LEGENDARY_KEYS
                 if k in self.unlocked and BY_KEY[k].title]
        if self.stars() >= STAR_COUNT:
            found.append(TRIUMPH_TITLE)
        return found

    def total_progress(self) -> Tuple[int, int]:
        """Logros conseguidos sobre el total, legendarios incluidos."""
        return len(self.unlocked), len(CATALOG)

    # -- desbloqueo ---------------------------------------------------------

    def unlock(self, keys: Iterable[str]) -> List[Achievement]:
        """
        Desbloquear lo que corresponda y devolver sólo lo nuevo.

        El orden de salida es el del catálogo, para que los avisos aparezcan
        siempre en el mismo orden y no en el arbitrario de un conjunto.
        """
        fresh = [k for k in keys if k in BY_KEY and k not in self.unlocked]
        if not fresh:
            return []
        stamp = datetime.now().isoformat(timespec="seconds")
        for key in fresh:
            self.unlocked[key] = stamp
        self.save()
        order = {a.key: i for i, a in enumerate(CATALOG)}
        return [BY_KEY[k] for k in sorted(set(fresh), key=lambda k: order[k])]

    def mark_stars_seen(self, star: int) -> None:
        """Recordar que la animación de esta estrella ya se mostró."""
        if star > self.stars_seen:
            self.stars_seen = star
            self.save()


# ---------------------------------------------------------------------------
# Herramientas de análisis
# ---------------------------------------------------------------------------

def chord_quality(chord: Chord) -> str:
    """
    La calidad de un acorde ya parseado.

    Misma lectura que :attr:`harmony.ChordOption.quality`, pero sobre un
    :class:`~engine.theory.Chord` suelto, que es lo que devuelve el parser
    cuando el usuario escribe el cifrado a mano.
    """
    third = next((t for t in chord.tones if t.role == ROLE_THIRD), None)
    seventh = next((t for t in chord.tones if t.role == ROLE_SEVENTH), None)
    fifth = next((t for t in chord.tones if t.role == ROLE_FIFTH), None)
    if third is None:
        return "other"
    if third.semitones == 3:
        if fifth is not None and fifth.semitones == 6:
            return "halfdim" if seventh is not None else "dim"
        return "minor"
    if fifth is not None and fifth.semitones == 8:
        return "aug"
    if seventh is not None and seventh.semitones == 10:
        return "dominant"
    return "major"


def _roman_degree(roman: str) -> str:
    """
    El grado en mayúsculas de un numeral, sin cifras ni alteraciones.

    ``V7`` -> ``V``; ``bVII`` -> ``VII``; ``vii°`` -> ``VII``. Así se puede
    distinguir el quinto grado del séptimo, que empiezan con la misma letra.
    """
    if not roman:
        return ""
    # Un acorde visitado en otra tonalidad viene como "mixolydian:vi".
    _area, _, local = roman.rpartition(":")
    text = local or roman
    letters = []
    for char in text:
        if char in "IViv":
            letters.append(char)
        elif letters:
            break                 # ya empezó el numeral y algo lo cortó
    return "".join(letters).upper()


def _is_dominant_function(chord: Chord, roman: str) -> bool:
    """Un dominante: el quinto grado, o cualquier acorde de esa calidad."""
    if _roman_degree(roman) == "V":
        return True
    return chord_quality(chord) == "dominant"


def _slot_view(outcome, solution) -> List[Tuple[Any, Any, Any]]:
    """
    Por cada acorde que suena: (acorde, plan de voicing, armonía).

    Los silencios se dejan afuera por dos razones: el cromosoma sólo tiene
    los slots que suenan -- así que los índices no coincidirían con
    ``spec.slots`` en cuanto haya un silencio -- y además un silencio lleva
    un acorde de relleno que contaría como un Do mayor que nadie escribió.

    En el modo manual el slot no tiene opciones y todo sale de su
    requirement; en el generador y el armonizador hay que ir a buscar la
    opción que esta solución eligió.
    """
    view = []
    sounding = [slot for slot in outcome.spec.slots if not slot.is_rest]
    for index, slot in enumerate(sounding):
        chord = slot.requirement.chord
        plan = slot.requirement.plan
        harmony_option = None
        if slot.options and index < len(solution.choices):
            option = slot.options[min(solution.choices[index],
                                      len(slot.options) - 1)]
            chord = option.requirement.chord
            plan = option.requirement.plan
            harmony_option = option.harmony
        view.append((chord, plan, harmony_option))
    return view


def _has_parallel_fifth(chords: Sequence[Sequence[int]]) -> bool:
    """¿Hay alguna quinta paralela entre dos acordes consecutivos?"""
    for index in range(1, len(chords)):
        previous, current = chords[index - 1], chords[index]
        if len(previous) != len(current):
            continue
        for a in range(len(current)):
            for b in range(a + 1, len(current)):
                fifth, _octave = parallel_interval_violation(
                    previous, current, a, b)
                if fifth:
                    return True
    return False


# ---------------------------------------------------------------------------
# Detectores: la corrida terminada
# ---------------------------------------------------------------------------

def inspect_outcome(outcome, wanted: Optional[Set[str]] = None) -> Set[str]:
    """
    Todo lo que una corrida terminada puede desbloquear por sí sola.

    ``wanted`` son las claves que todavía faltan: lo que ya está conseguido
    ni se busca. Es lo que mantiene el costo pegado a cero una vez que el
    usuario completó el juego.
    """
    found: Set[str] = set()
    if outcome is None or not getattr(outcome, "succeeded", False):
        return found
    if outcome.spec is None or not outcome.result.solutions:
        return found
    if wanted is None:
        wanted = set(BY_KEY)
    if not wanted:
        return found

    best = outcome.result.solutions[0]

    # -- la quotation que haya salido ---------------------------------------
    piece = getattr(outcome, "set_piece", None)
    if piece is not None:
        labels = {spec.label: key for key, spec in SET_PIECES.items()}
        mapping = {"vivaldi": "set_piece_vivaldi",
                   "phrygian": "set_piece_phrygian",
                   "chromatic_bass": "set_piece_chromatic"}
        key = mapping.get(labels.get(getattr(piece, "label", ""), ""), "")
        if key:
            found.add(key)

    # -- los gestos que el post-proceso reconoció ---------------------------
    flourishes = getattr(outcome, "flourishes", None)
    if flourishes is not None:
        marks = {m.key for group in flourishes.by_solution.values()
                 for m in group}
        marks |= {m.key for m in flourishes.marks}
        if "six_four" in marks:
            found.add("cadential_six_four")
        if marks & {"two_five", "secondary_two_five"}:
            found.add("two_five")
        if marks & {"plagal", "plagal_minor"}:
            found.add("plagal")
        if flourishes.sixth_symbol:
            found.add("sixth_omit_five")

    # -- lo que dicen los acordes -------------------------------------------
    # Se miran las tres soluciones, no sólo la ganadora. Las otras dos son
    # respuestas igual de reales -- el usuario las tiene en pantalla y puede
    # quedarse con cualquiera -- y mirar sólo la primera hacía que un acorde
    # prestado o una modulación que el generador sí había producido no
    # contaran porque habían caído en la opción 2.
    for solution in outcome.result.solutions:
        if any(note is not None for row in getattr(solution, "passing", [])
               for note in row):
            found.add("passing_notes")
        if getattr(solution, "mod_plan", None) is not None:
            found.add("modulation")

        dominant_run = 0
        last_dominant = False
        for chord, plan, option in _slot_view(outcome, solution):
            roman = getattr(option, "roman", "") if option is not None else ""
            if any(t.role == ROLE_SEVENTH for t in chord.tones):
                found.add("seventh_chord")
            if chord_quality(chord) in ("dim", "halfdim"):
                found.add("diminished_chord")
            if option is not None:
                # Una dominante aplicada también viaja como "prestada", pero
                # un V del V no es un intercambio modal: no viene del modo
                # paralelo, es una tónica pasajera.
                if (getattr(option, "is_borrowed", False)
                        and not is_applied_dominant(option)):
                    found.add("modal_interchange")
                if getattr(option, "key_area", ""):
                    found.add("modulation")

            # Séptima + novena + oncena sonando en el mismo acorde. Las notas
            # de color añadidas cuentan: son las que el voicing realmente
            # canta.
            degrees = {t.degree for t in list(plan.degrees) + list(plan.added)}
            if (any(d.endswith("7") for d in degrees)
                    and any(d.endswith("9") for d in degrees)
                    and any(d.endswith("11") for d in degrees)):
                found.add("extended_chord")

            # Tres dominantes encadenados: por calidad, no por grado. Tres
            # "V" seguidos serían el mismo acorde repetido; lo que la cadena
            # quiere decir es E7 A7 D7.
            if chord_quality(chord) == "dominant":
                dominant_run += 1
                if dominant_run >= 3:
                    found.add("three_dominants")
            else:
                dominant_run = 0
            last_dominant = _is_dominant_function(chord, roman)

        if last_dominant:
            found.add("ends_on_dominant")

    # -- quintas paralelas: el único barrido caro ---------------------------
    # Acá sí sólo la ganadora: es la partitura que el programa presenta
    # primero, y las dos frases -- "con" y "sin" quintas paralelas -- tienen
    # que hablar de la misma pieza o se ganarían las dos juntas siempre.
    if wanted & {"parallel_fifth", "no_parallel_fifths"}:
        if _has_parallel_fifth(best.slots):
            found.add("parallel_fifth")
        else:
            found.add("no_parallel_fifths")

    return found & wanted


# ---------------------------------------------------------------------------
# Detectores: la configuración
# ---------------------------------------------------------------------------

#: Modos que no cuentan como "más allá": el jónico y el eólico. El eólico
#: se llama "minor" en el catálogo -- son la misma escala y el programa
#: ofrece una sola.
PLAIN_MODES = frozenset({"major", "minor"})


def is_exotic_mode(mode_key: str) -> bool:
    return bool(mode_key) and mode_key not in PLAIN_MODES


#: Cómo queda la pantalla de reglas cuando nadie la tocó.
#:
#: El balance arranca en el medio de su recorrido, la cadencia en la opción
#: que el programa elige solo, y el dial de color en cero. Cualquier cosa
#: distinta de esto es alguien que entró a la pantalla y movió algo.
DEFAULT_BALANCE = 50.0
DEFAULT_CADENCE = "Premiar apenas"


def rules_customised(
    genre_key: str,
    switch_state: Dict[str, bool],
    balance: Optional[float] = None,
    cadence: Optional[str] = None,
    colour: float = 0.0,
    custom_ranges: bool = False,
) -> bool:
    """
    ¿Quedó algo distinto de como lo deja el estilo?

    Mira la pantalla de reglas entera y no sólo los interruptores. Antes
    contaba nada más las reglas duras, así que un usuario que hubiera
    corrido el balance hacia el estilo, exigido la cadencia como regla
    dura, subido el color y ampliado el registro de una voz --- cuatro
    decisiones, todas suyas, todas en contra de lo que el programa
    proponía --- seguía sin haberse "rebelado" según el programa. El logro
    dice "sin usar las reglas por defecto", y ésas también son reglas.
    """
    profile = GENRE_PROFILES.get(genre_key)
    if profile is None:
        return False
    if any(bool(value) != bool(getattr(profile, key, False))
           for key, value in switch_state.items()):
        return True
    if balance is not None and abs(float(balance) - DEFAULT_BALANCE) > 0.5:
        return True
    if cadence is not None and cadence != DEFAULT_CADENCE:
        return True
    if colour and abs(float(colour)) > 0.5:
        return True
    return bool(custom_ranges)


def ga_customised(config, defaults) -> bool:
    """¿El usuario tocó algún parámetro de la búsqueda?"""
    fields = ("population_size", "generations", "elitism", "tournament_size",
              "mutation_rate", "crossover_rate", "uniform_crossover_share")
    return any(getattr(config, f, None) != getattr(defaults, f, None)
               for f in fields)


# ---------------------------------------------------------------------------
# Detectores: la melodía del armonizador
# ---------------------------------------------------------------------------

#: El lick, en intervalos: re mi fa sol mi do re. Se guarda como la
#: diferencia entre notas sucesivas para que sirva en cualquier tonalidad.
THE_LICK = (2, 1, 2, -3, -4, 2)

TRITONE = 6


def has_tritone_leap(pitches: Sequence[int]) -> bool:
    return any(abs(pitches[i] - pitches[i - 1]) == TRITONE
               for i in range(1, len(pitches)))


def has_the_lick(pitches: Sequence[int]) -> bool:
    """El lick, en cualquier altura, en cualquier punto de la melodía."""
    if len(pitches) <= len(THE_LICK):
        return len(pitches) == len(THE_LICK) + 1 and tuple(
            pitches[i + 1] - pitches[i] for i in range(len(THE_LICK))
        ) == THE_LICK
    steps = tuple(pitches[i + 1] - pitches[i] for i in range(len(pitches) - 1))
    span = len(THE_LICK)
    return any(steps[i:i + span] == THE_LICK
               for i in range(len(steps) - span + 1))


#: Cuántas notas distintas tiene la escala: do re mi fa sol la si. La
#: alteración no cuenta -- un fa sostenido sigue siendo un fa -- porque el
#: pentagrama guarda la posición y no el semitono.
SCALE_STEPS = 7


def supreme_melody_progress(
    notes: Sequence[Tuple[int, float]],
    required_durations: Sequence[float],
) -> Tuple[int, int, int, int]:
    """
    Cuánto le falta a una melodía para ser la suprema.

    Devuelve ``(notas puestas, notas pedidas, figuras puestas, figuras
    pedidas)``. Existe aparte para que la pantalla pueda mostrar el avance:
    el logro pide dos cosas a la vez y, sin verlo, no hay forma de saber
    cuál de las dos es la que falta.
    """
    wanted = {round(d, 4) for d in required_durations}
    steps = {index % SCALE_STEPS for index, _duration in notes}
    used = {round(duration, 4) for _index, duration in notes} & wanted
    return len(steps), SCALE_STEPS, len(used), len(wanted)


def supreme_melody(notes: Sequence[Tuple[int, float]],
                   required_durations: Sequence[float]) -> bool:
    """
    Las siete notas de la escala y todas las figuras, en una sola melodía.

    ``notes`` son los pares ``(índice diatónico, duración)`` que guarda el
    pentagrama; el índice módulo siete es el grado, sin importar la octava.
    """
    if not notes or not required_durations:
        return False
    steps, needed_steps, used, needed_used = supreme_melody_progress(
        notes, required_durations)
    return steps == needed_steps and used == needed_used


# ---------------------------------------------------------------------------
# Detectores: los legendarios que se escriben a mano
# ---------------------------------------------------------------------------

#: I7 IV7 V7: tres dominantes con las fundamentales del blues. Guardado
#: como (semitonos sobre el primero, calidad).
BLUES_PACT = (
    (0, "dominant"),
    (5, "dominant"),
    (7, "dominant"),
)

#: La regla de la octava de Gospel, descendiendo. En Do:
#:
#:     C   G/B   C7/Bb   F/A   Fm/Ab   C/G   D7/F#   G   C
#:
#: y el bajo baja 0 11 10 9 8 7 6 7 0 sobre la tónica. Se guarda como
#: (fundamental sobre la tónica, calidad, bajo sobre la tónica) para que
#: valga en cualquier tonalidad jónica.
GOSPEL_OCTAVE_RULE = (
    (0, "major", 0),        # I
    (7, "major", 11),       # V/3
    (0, "dominant", 10),    # I7/b7
    (5, "major", 9),        # IV/3
    (5, "minor", 8),        # iv/b3
    (0, "major", 7),        # I/5
    (2, "dominant", 6),     # V7/V con la tercera en el bajo
    (7, "major", 7),        # V
    (0, "major", 0),        # I
)


def _chord_shape(chord: Chord) -> Tuple[int, str, int]:
    """(fundamental, calidad, bajo) de un acorde, en clases de altura."""
    bass = chord.bass_pc if chord.bass_pc is not None else chord.root_pc
    return chord.root_pc % 12, chord_quality(chord), bass % 12


def _matches_shape(chords: Sequence[Chord],
                   pattern: Sequence[Tuple[int, ...]],
                   start: int) -> bool:
    """¿Encaja el patrón, transportado, empezando en ``start``?"""
    tonic = chords[start].root_pc % 12
    for offset, expected in enumerate(pattern):
        root, quality, *rest = expected
        actual_root, actual_quality, actual_bass = _chord_shape(
            chords[start + offset])
        if (actual_root - tonic) % 12 != root % 12:
            return False
        if actual_quality != quality:
            return False
        if rest and (actual_bass - tonic) % 12 != rest[0] % 12:
            return False
    return True


def _contains_shape(chords: Sequence[Chord],
                    pattern: Sequence[Tuple[int, ...]]) -> bool:
    span = len(pattern)
    return any(_matches_shape(chords, pattern, start)
               for start in range(len(chords) - span + 1))


def first_match(chords: Sequence[Chord],
                pattern: Sequence[Tuple[int, ...]]) -> Optional[int]:
    """Dónde empieza la primera aparición del patrón, o ``None``."""
    span = len(pattern)
    for start in range(len(chords) - span + 1):
        if _matches_shape(chords, pattern, start):
            return start
    return None


def matched_tonics(chords: Sequence[Chord],
                   pattern: Sequence[Tuple[int, ...]]) -> Set[int]:
    """
    Sobre qué fundamentales encaja el patrón, en clases de altura.

    ``_contains_shape`` sólo dice si el patrón está; esto dice *dónde*, que
    es lo que necesita el modo historia para pedir la misma progresión en
    tres tonalidades distintas sin tener que guardar cada intento entero.
    """
    span = len(pattern)
    return {chords[start].root_pc % 12
            for start in range(len(chords) - span + 1)
            if _matches_shape(chords, pattern, start)}


def is_blues_pact(chords: Sequence[Chord]) -> bool:
    """I7 IV7 V7 seguidos, en cualquier tonalidad."""
    return _contains_shape(chords, BLUES_PACT)


def is_gospel_octave_rule(chords: Sequence[Chord]) -> bool:
    """
    La regla de la octava de Gospel descendente.

    Se acepta también sin la tónica final: los ocho acordes del descenso son
    la regla, y el noveno sólo la cierra.
    """
    if _contains_shape(chords, GOSPEL_OCTAVE_RULE):
        return True
    return _contains_shape(chords, GOSPEL_OCTAVE_RULE[:-1])


def inspect_written_chords(chords: Sequence[Chord],
                           wanted: Optional[Set[str]] = None) -> Set[str]:
    """Los legendarios que dependen de qué acordes escribió el usuario."""
    found: Set[str] = set()
    if wanted is None:
        wanted = set(BY_KEY)
    if "blues_pact" in wanted and is_blues_pact(chords):
        found.add("blues_pact")
    if "second_coming" in wanted and is_gospel_octave_rule(chords):
        found.add("second_coming")
    return found
