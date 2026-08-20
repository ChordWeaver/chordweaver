# -*- coding: utf-8 -*-
"""
Harmony: what chords exist in a key, and what makes a progression good.

Used by the random generator, where the search chooses the chords as well as
their voicing. The manual mode never touches this module: there the user has
already decided the harmony.

Two things live here:

* **Supply** -- the chords available in a key: the diatonic ones for the
  chosen mode, plus whichever borrowed chords the user switched on.
* **Judgement** -- how idiomatic a succession of those chords is for a given
  genre, scored from root motion, cadence shape and function.

Root motion is the backbone of the judgement. Common-practice harmony is
built on descending fifths; ascending a fifth (V to IV) is the textbook
retrogression; and modal writing prefers roots a step apart, which is why
the same progression scores differently depending on the style asked for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .theory import Chord, ChordTone, ROLE_FIFTH, ROLE_ROOT, ROLE_SEVENTH, ROLE_THIRD
from .theory import FLAT_NAMES, SHARP_NAMES, ChordParseError, parse_chord

# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Mode:
    """A scale pattern plus the label the interface shows."""

    key: str
    label: str
    intervals: Tuple[int, ...]      # semitones above the tonic, 7 degrees
    #: Degree (1-7) whose triad acts as the tonic chord.
    tonic_degree: int = 1

    def pitch_classes(self, tonic_pc: int) -> List[int]:
        return [(tonic_pc + i) % 12 for i in self.intervals]


MODES: Dict[str, Mode] = {
    "major":      Mode("major", "Mayor (jónico)", (0, 2, 4, 5, 7, 9, 11)),
    "minor":      Mode("minor", "Menor natural", (0, 2, 3, 5, 7, 8, 10)),
    "harmonic":   Mode("harmonic", "Menor armónica", (0, 2, 3, 5, 7, 8, 11)),
    "dorian":     Mode("dorian", "Dórico", (0, 2, 3, 5, 7, 9, 10)),
    "phrygian":   Mode("phrygian", "Frigio", (0, 1, 3, 5, 7, 8, 10)),
    "lydian":     Mode("lydian", "Lidio", (0, 2, 4, 6, 7, 9, 11)),
    "mixolydian": Mode("mixolydian", "Mixolidio", (0, 2, 4, 5, 7, 9, 10)),
    # El eolio no está listado aparte a propósito: es nota por nota la menor
    # natural, y ofrecer las dos era ofrecer la misma escala dos veces con
    # nombres distintos.
    "locrian":    Mode("locrian", "Locrio", (0, 1, 3, 5, 6, 8, 10)),
}

#: Modes whose seventh degree is a semitone below the tonic, i.e. a real
#: leading tone. Modal writing without one cannot form a dominant cadence,
#: which is precisely what distinguishes it.
MODES_WITH_LEADING_TONE = {"major", "harmonic", "lydian"}


# ---------------------------------------------------------------------------
# Chord options
# ---------------------------------------------------------------------------

@dataclass
class ChordOption:
    """One chord the generator may place, with everything needed to judge it."""

    chord: Chord
    label: str                  # what the user reads: "Am", "bVII", ...
    roman: str                  # function label: "vi", "bVII", "N6"
    scale_degree: int           # 1-7 for diatonic chords, 0 for borrowed
    root_pc: int
    is_borrowed: bool = False
    #: Which key area this chord belongs to. Empty means the home key.
    key_area: str = ""
    #: First inversion is forced for some chords -- the Neapolitan is almost
    #: always written with its third in the bass, which is what makes it a
    #: "sixth" chord.
    forced_bass_pc: Optional[int] = None

    @property
    def quality(self) -> str:
        third = next((t for t in self.chord.tones if t.role == ROLE_THIRD), None)
        seventh = next((t for t in self.chord.tones if t.role == ROLE_SEVENTH), None)
        fifth = next((t for t in self.chord.tones if t.role == ROLE_FIFTH), None)
        if third is None:
            return "other"
        if third.semitones == 3:
            if fifth is not None and fifth.semitones == 6:
                return "halfdim" if seventh else "dim"
            return "minor"
        if fifth is not None and fifth.semitones == 8:
            return "aug"
        if seventh is not None and seventh.semitones == 10:
            return "dominant"
        return "major"


#: Roman numerals per scale degree, lower case for minor-quality triads.
_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]


def _build_chord_from_scale(
    scale: Sequence[int],
    degree_index: int,
    with_seventh: bool,
) -> Chord:
    """Stack thirds on a scale degree, staying inside the scale."""
    root_pc = scale[degree_index % 7]
    third_pc = scale[(degree_index + 2) % 7]
    fifth_pc = scale[(degree_index + 4) % 7]

    tones = [
        ChordTone(0, ROLE_ROOT, "1"),
        ChordTone((third_pc - root_pc) % 12, ROLE_THIRD,
                  "b3" if (third_pc - root_pc) % 12 == 3 else "3"),
        ChordTone((fifth_pc - root_pc) % 12, ROLE_FIFTH,
                  {6: "b5", 8: "#5"}.get((fifth_pc - root_pc) % 12, "5")),
    ]
    if with_seventh:
        seventh_pc = scale[(degree_index + 6) % 7]
        interval = (seventh_pc - root_pc) % 12
        tones.append(ChordTone(interval, ROLE_SEVENTH,
                               "7" if interval == 11 else "b7"))

    return Chord(
        symbol=SHARP_NAMES[root_pc],
        root_pc=root_pc,
        root_letter=SHARP_NAMES[root_pc][0],
        tones=tones,
    )


def diatonic_options(
    tonic_pc: int,
    mode: Mode,
    with_sevenths: bool = False,
) -> List[ChordOption]:
    """Every triad (or seventh chord) native to the key."""
    scale = mode.pitch_classes(tonic_pc)
    options: List[ChordOption] = []
    for degree_index in range(7):
        chord = _build_chord_from_scale(scale, degree_index, with_sevenths)
        option = ChordOption(
            chord=chord,
            label=_symbol_for(chord),
            roman=_roman_for(degree_index, chord),
            scale_degree=degree_index + 1,
            root_pc=chord.root_pc,
        )
        chord.symbol = option.label
        options.append(option)
    return options


def _roman_for(degree_index: int, chord: Chord) -> str:
    numeral = _ROMAN[degree_index]
    third = next((t for t in chord.tones if t.role == ROLE_THIRD), None)
    fifth = next((t for t in chord.tones if t.role == ROLE_FIFTH), None)
    minor = third is not None and third.semitones == 3
    diminished = minor and fifth is not None and fifth.semitones == 6
    text = numeral.lower() if minor else numeral
    if diminished:
        text += "°"
    return text


def _symbol_for(chord: Chord, prefer_flats: bool = False) -> str:
    """
    American symbol for a chord built from scale degrees.

    Borrowed and lowered degrees are spelled with flats, because that is what
    their names say: the Neapolitan of A minor is bII, and writing it A#
    rather than Bb makes the label contradict the numeral beside it.
    """
    root = (FLAT_NAMES if prefer_flats else SHARP_NAMES)[chord.root_pc]
    third = next((t for t in chord.tones if t.role == ROLE_THIRD), None)
    fifth = next((t for t in chord.tones if t.role == ROLE_FIFTH), None)
    seventh = next((t for t in chord.tones if t.role == ROLE_SEVENTH), None)

    minor = third is not None and third.semitones == 3
    quality = ""
    if minor and fifth is not None and fifth.semitones == 6:
        quality = "m7b5" if seventh else "dim"
    elif minor:
        quality = "m7" if (seventh and seventh.semitones == 10) else ("mmaj7" if seventh else "m")
    elif fifth is not None and fifth.semitones == 8:
        quality = "aug"
    elif seventh is not None:
        quality = "7" if seventh.semitones == 10 else "maj7"
    return root + quality


# ---------------------------------------------------------------------------
# Modal interchange
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BorrowedChord:
    """A chord borrowed from the parallel mode."""

    key: str
    label: str
    roman: str
    root_offset: int            # semitones above the tonic
    quality: str                # "major", "minor", "dim", "dominant", "halfdim"
    description: str
    forced_first_inversion: bool = False


BORROWED_CHORDS: Dict[str, BorrowedChord] = {
    "iv": BorrowedChord(
        "iv", "4to menor (iv)", "iv", 5, "minor",
        "La subdominante menor prestada del modo menor. El préstamo más "
        "común de todos: suaviza la cadencia y es el sonido del 'plagal "
        "triste'.",
    ),
    "v": BorrowedChord(
        "v", "5to menor (v)", "v", 7, "minor",
        "Dominante menor. Al no tener sensible pierde la tensión de resolver, "
        "lo que le da un color modal en vez de funcional.",
    ),
    "bII": BorrowedChord(
        "bII", "2do bemol mayor (bII, napolitana)", "bII", 1, "major",
        "Napolitana en estado fundamental: un acorde mayor construido sobre "
        "el segundo grado rebajado.",
    ),
    "N6": BorrowedChord(
        "N6", "6ta napolitana (bII6)", "N6", 1, "major",
        "La napolitana con su tercera en el bajo, que es como se escribe "
        "casi siempre. De ahí el nombre 'de sexta': el bajo queda a una "
        "sexta de la fundamental.",
        forced_first_inversion=True,
    ),
    "bVII": BorrowedChord(
        "bVII", "7mo bemol mayor (bVII, eólico)", "bVII", 10, "major",
        "Subtónica mayor. Reemplaza a la dominante sin sensible, y es la "
        "marca del rock y del modo mixolidio.",
    ),
    "bVI": BorrowedChord(
        "bVI", "6to bemol mayor (bVI)", "bVI", 8, "major",
        "Submediante mayor prestada. Suele encadenarse con el bVII para "
        "volver a la tónica.",
    ),
    "bIII": BorrowedChord(
        "bIII", "3ro bemol mayor (bIII)", "bIII", 3, "major",
        "Mediante mayor prestada. Da un giro brillante e inesperado hacia "
        "el modo menor.",
    ),
    "subV": BorrowedChord(
        "subV", "Sustituto tritonal (bII7)", "subV", 1, "dominant",
        "El dominante que reemplaza al V, construido un semitono por encima "
        "de la tónica. Comparte con el V su tercera y su séptima -- las dos "
        "notas que definen la tensión -- y por eso puede ocupar su lugar y "
        "resolver bajando un semitono.",
    ),
    "iiø": BorrowedChord(
        "iiø", "2do semidisminuido (iiø)", "iiø", 2, "halfdim",
        "El ii del modo menor. Va de la mano del iv prestado y prepara la "
        "dominante con un color más oscuro.",
    ),
}

_QUALITY_TONES = {
    "major": [(0, ROLE_ROOT, "1"), (4, ROLE_THIRD, "3"), (7, ROLE_FIFTH, "5")],
    "minor": [(0, ROLE_ROOT, "1"), (3, ROLE_THIRD, "b3"), (7, ROLE_FIFTH, "5")],
    "dim": [(0, ROLE_ROOT, "1"), (3, ROLE_THIRD, "b3"), (6, ROLE_FIFTH, "b5")],
    "halfdim": [(0, ROLE_ROOT, "1"), (3, ROLE_THIRD, "b3"), (6, ROLE_FIFTH, "b5"),
                (10, ROLE_SEVENTH, "b7")],
    "dominant": [(0, ROLE_ROOT, "1"), (4, ROLE_THIRD, "3"), (7, ROLE_FIFTH, "5"),
                 (10, ROLE_SEVENTH, "b7")],
}


#: La séptima que cada préstamo trae del modo paralelo, en semitonos sobre
#: su fundamental, y cómo se escribe.
#:
#: Es la que le toca en el modo del que se lo pidió prestado: el bVII de
#: eólico es Bb-D-F-Ab, o sea dominante; el bVI y el bIII son maj7; el iv y
#: el v son menores con séptima menor. La napolitana viene de frigio y ahí
#: también es maj7.
_BORROWED_SEVENTH = {
    "iv": (10, "b7"),
    "v": (10, "b7"),
    "bII": (11, "7"),
    "bVII": (10, "b7"),
    "bVI": (11, "7"),
    "bIII": (11, "7"),
}


def borrowed_options(tonic_pc: int, enabled: Sequence[str],
                     with_sevenths: bool = False) -> List[ChordOption]:
    """
    Build the borrowed chords the user switched on.

    Con las séptimas prendidas los préstamos también las llevan. Salían como
    tríadas peladas en medio de una pieza donde todo lo demás era de
    séptima, y eso es exactamente lo que se oye como un acorde que no
    pertenece --- no por prestado, sino por delgado. La sexta napolitana es
    la excepción: se llama así por su cifrado de sexta, y una séptima
    encima la convierte en un acorde de quinta y sexta, que ya no es lo que
    el nombre promete.
    """
    options: List[ChordOption] = []
    for key in enabled:
        spec = BORROWED_CHORDS.get(key)
        if spec is None:
            continue
        root_pc = (tonic_pc + spec.root_offset) % 12
        tones = [ChordTone(s, role, degree)
                 for s, role, degree in _QUALITY_TONES[spec.quality]]
        if with_sevenths and key in _BORROWED_SEVENTH:
            semitones, degree = _BORROWED_SEVENTH[key]
            tones.append(ChordTone(semitones, ROLE_SEVENTH, degree))
        chord = Chord(
            symbol="",
            root_pc=root_pc,
            root_letter=SHARP_NAMES[root_pc][0],
            tones=tones,
        )
        # Every borrowed degree in the table is a lowered one, so they are
        # all written flat.
        chord.symbol = _symbol_for(chord, prefer_flats=spec.roman.startswith("b")
                                   or spec.roman in ("N6", "subV"))
        forced_bass = None
        if spec.forced_first_inversion:
            forced_bass = (root_pc + 4) % 12       # the major third
            chord.bass_pc = forced_bass
        options.append(ChordOption(
            chord=chord,
            label=chord.symbol,
            roman=spec.roman,
            scale_degree=0,
            root_pc=root_pc,
            is_borrowed=True,
            forced_bass_pc=forced_bass,
        ))
    return options


#: Índice del quinto grado dentro de la escala, para pedir sólo su
#: dominante: el V del V, que es el único aplicado que la escritura de
#: práctica común usa con soltura.
DEGREE_DOMINANT = 4


def secondary_dominants(
    tonic_pc: int,
    mode: Mode,
    with_sevenths: bool = True,
    degrees: Optional[Sequence[int]] = None,
) -> List[ChordOption]:
    """
    The dominant of each degree other than the tonic.

    A ii-V does not only aim at the tonic: applying the same two-chord
    approach to any degree is ordinary motion in jazz, not a change of key.
    Providing these means the search can write Em - A7 - Dm without
    modulation being switched on at all.

    ``degrees`` limits which targets are offered, as indices into the scale.
    The baroque styles ask for ``(DEGREE_DOMINANT,)`` alone: the V of the V
    belongs there, and the rest of the chain is a jazz habit.
    """
    scale = mode.pitch_classes(tonic_pc)
    wanted = tuple(degrees) if degrees is not None else tuple(range(1, 7))
    options: List[ChordOption] = []
    for degree_index in range(1, 7):          # every degree but the tonic
        if degree_index not in wanted:
            continue
        target_pc = scale[degree_index]
        root_pc = (target_pc + 7) % 12        # a fifth above the target
        tones = [
            ChordTone(0, ROLE_ROOT, "1"),
            ChordTone(4, ROLE_THIRD, "3"),
            ChordTone(7, ROLE_FIFTH, "5"),
        ]
        if with_sevenths:
            tones.append(ChordTone(10, ROLE_SEVENTH, "b7"))
        chord = Chord(symbol="", root_pc=root_pc,
                      root_letter=SHARP_NAMES[root_pc][0], tones=tones)
        chord.symbol = _symbol_for(chord)
        numeral = _ROMAN[degree_index]
        third = None
        # Name it after where it points: V/ii, V/iii and so on.
        options.append(ChordOption(
            chord=chord, label=chord.symbol,
            roman=f"V/{numeral.lower() if degree_index in (1, 2, 5) else numeral}",
            scale_degree=0, root_pc=root_pc, is_borrowed=True,
        ))
    return options


def build_chord_pool(
    tonic_pc: int,
    mode: Mode,
    borrowed: Sequence[str] = (),
    with_sevenths: bool = False,
    secondary: bool = False,
    secondary_degrees: Optional[Sequence[int]] = None,
) -> List[ChordOption]:
    """Everything the generator may choose from, diatonic first."""
    pool = diatonic_options(tonic_pc, mode, with_sevenths)
    if secondary:
        # Added even where a diatonic chord shares the root: A7 and Am7 sit
        # on the same note but are not the same chord, and it is precisely
        # the major third that lets one point at the second degree.
        existing = {(option.root_pc, option.quality) for option in pool}
        for option in secondary_dominants(tonic_pc, mode, with_sevenths,
                                          secondary_degrees):
            if (option.root_pc, option.quality) not in existing:
                pool.append(option)
    existing = {option.root_pc for option in pool}
    for option in borrowed_options(tonic_pc, borrowed, with_sevenths):
        # A borrowed chord whose root already exists diatonically is still
        # offered: bVII in mixolydian is diatonic, but iv in major is not the
        # same chord as IV even though both are rooted on the fourth degree.
        pool.append(option)
    return pool


# ---------------------------------------------------------------------------
# Progression judgement
# ---------------------------------------------------------------------------

#: Root motion, in semitones ascending, scored by how idiomatic it is in
#: common-practice harmony. Negative numbers are rewards.
#:
#: Descending a fifth (+7 ascending is the same as -5 descending) is the
#: strongest progression there is; ascending a fifth is the retrogression
#: every harmony course warns about; a step down is the common "IV-V" or
#: "bVI-bVII" motion; a third is smooth because two notes are shared.
FUNCTIONAL_ROOT_MOTION = {
    5: -14.0,    # up a fourth  == down a fifth: the strongest motion
    2: -8.0,     # up a step
    9: -6.0,     # down a third
    10: -4.0,    # down a step
    3: -3.0,     # up a third
    8: -2.0,     # down a third (minor)
    4: -2.0,     # up a third (major)
    7: 10.0,     # up a fifth: retrogression
    1: 4.0,
    11: 4.0,
    6: 12.0,     # tritone root motion
    0: 0.0,
}

#: Modal writing prefers roots a step apart and dislikes leaps, especially
#: the tritone. Fifth motion is fine but carries no special reward, because
#: there is no dominant function to reward.
MODAL_ROOT_MOTION = {
    2: -12.0, 10: -12.0,       # steps either way
    5: -4.0, 7: -4.0,          # fourths and fifths
    3: -2.0, 9: -2.0, 4: -2.0, 8: -2.0,
    1: 6.0, 11: 6.0,
    6: 20.0,                   # the tritone again
    0: 0.0,
}

#: Jazz lives on the cycle of fifths and on chromatic approach.
JAZZ_ROOT_MOTION = {
    5: -16.0,    # ii-V and V-I
    1: -6.0, 11: -6.0,         # chromatic approach, tritone substitution
    2: -6.0, 10: -6.0,
    9: -4.0, 3: -4.0, 8: -3.0, 4: -3.0,
    7: 4.0,
    6: -2.0,     # tritone motion is a substitution, not an error
    0: 0.0,
}

ROOT_MOTION_TABLES = {
    "classical": FUNCTIONAL_ROOT_MOTION,
    "chorale": FUNCTIONAL_ROOT_MOTION,
    "gregorian": MODAL_ROOT_MOTION,
    "jazz": JAZZ_ROOT_MOTION,
}


@dataclass
class HarmonyWeights:
    """How the progression itself is judged, independent of the voicing."""

    #: Overall multiplier applied to every term below.
    emphasis: float = 1.0
    #: Cost each time a chord follows itself. In the generator this is a
    #: hard bar, not a price: the program is choosing the chords, so there is
    #: never a reason to write the same one twice in a row, and letting it be
    #: merely expensive left runs where one chord repeated all the way
    #: through.
    repeat: float = 90.0
    forbid_repeat: bool = True
    #: Cost when the same chord appears more than twice in the piece.
    overuse: float = 25.0
    #: Reward for closing with a recognised cadence.
    cadence: float = -40.0
    #: Cost per borrowed chord. Negative values make the search seek them out.
    borrowed: float = 0.0
    #: Reward for a dominant that actually resolves down a fifth.
    dominant_resolution: float = -18.0
    #: Cost for a dominant that does not.
    dominant_escape: float = 14.0
    #: Which chord should open and close, by roman numeral ("I", "i", "vi").
    #: None leaves the search free. Enforced by weight here; the generator
    #: turns a *mandatory* endpoint into a single-option slot instead, which
    #: is both exact and far cheaper than penalising it after the fact.
    start_roman: Optional[str] = None
    end_roman: Optional[str] = None
    endpoint: float = 120.0
    #: Reward per chord carrying a seventh or an extension. Jazz lives on
    #: these; common practice does not.
    colour: float = 0.0
    #: Cost for a diminished triad used in root position, which common
    #: practice avoids -- vii° normally appears in first inversion.
    root_position_diminished: float = 0.0
    #: How much the functional grammar counts. This is the main judgement:
    #: it knows a dominant wants to resolve, which raw interval arithmetic
    #: cannot express.
    grammar: float = 1.0
    #: How much the raw root-motion table still counts. Kept as a light
    #: tiebreaker between moves the grammar rates alike, rather than as the
    #: primary judgement it used to be.
    root_motion: float = 0.35
    #: Where the piece may travel. None disables modulation entirely.
    modulation: Optional["ModulationSettings"] = None


def progression_cost(
    options: Sequence[ChordOption],
    genre_key: str,
    weights: HarmonyWeights,
    tonic_pc: int,
    bar_indices: Optional[Sequence[int]] = None,
) -> float:
    """
    Score a succession of chords. Lower is better, like every other cost here.

    Judged on root motion, on how the piece ends, on repetition, and on how
    much borrowed colour was used relative to the weight the user set.
    """
    if len(options) < 2:
        return 0.0

    table = ROOT_MOTION_TABLES.get(genre_key, FUNCTIONAL_ROOT_MOTION)
    total = 0.0

    if weights.start_roman and options[0].roman != weights.start_roman:
        total += weights.endpoint
    if weights.end_roman and options[-1].roman != weights.end_roman:
        total += weights.endpoint

    counts: Dict[str, int] = {}
    for option in options:
        quality = option.quality
        if weights.colour and quality in ("dominant", "halfdim"):
            total += weights.colour
        if weights.colour and any(t.role == ROLE_SEVENTH for t in option.chord.tones):
            total += weights.colour
        if weights.root_position_diminished and quality in ("dim", "halfdim"):
            if option.forced_bass_pc is None:
                total += weights.root_position_diminished
        counts[option.roman] = counts.get(option.roman, 0) + 1
        # El dial de "cuánto usar los intercambios modales" no manda sobre
        # las dominantes aplicadas: no son acordes prestados del modo
        # paralelo, y dejarlas bajo ese peso hacía que subir el dial
        # llenara la pieza de V/V sin haber pedido ninguno.
        if option.is_borrowed and not is_applied_dominant(option):
            total += weights.borrowed

    for roman, count in counts.items():
        if count > 2:
            total += weights.overuse * (count - 2)

    for index in range(1, len(options)):
        previous, current = options[index - 1], options[index]
        if previous.roman == current.roman:
            if weights.forbid_repeat:
                return float("inf")
            total += weights.repeat
            continue

        motion = (current.root_pc - previous.root_pc) % 12
        total += table.get(motion, 0.0) * weights.root_motion

        grammar = GRAMMARS.get(genre_key)
        if grammar is not None and weights.grammar:
            # Inside a key area the grammar is measured against that area's
            # own tonic; a V in the dominant key resolves to ITS tonic, not
            # to the home one.
            local_tonic = tonic_pc
            if current.key_area and current.key_area == previous.key_area:
                target = MODULATION_TARGETS.get(current.key_area)
                if target is not None:
                    local_tonic = (tonic_pc + target.offset) % 12
            total += weights.grammar * grammar_cost(
                previous, current, grammar, local_tonic,
                options[index - 2] if index >= 2 else None,
            )

        # A dominant-quality chord wants to fall a fifth. Letting it wander
        # off is the single most audible way a progression stops sounding
        # like functional harmony.
        #
        # Se mide por función y no sólo por la forma del acorde. Con las
        # séptimas prendidas el bVII prestado es literalmente un acorde de
        # dominante --- Bb-D-F-Ab en do ---, pero se para donde se para una
        # subdominante y su giro propio, bVII-I, sube un tono: cobrado como
        # dominante que se escapa, el préstamo más idiomático del catálogo
        # quedaba prohibido justo cuando se le daba su séptima.
        if (previous.quality == "dominant"
                and not _borrowed_subdominant(previous)
                and genre_key in ("classical", "chorale", "jazz")):
            total += (weights.dominant_resolution if motion == 5
                      else weights.dominant_escape)

    grammar = GRAMMARS.get(genre_key)
    # Una dominante aplicada en el último acorde no resuelve por definición:
    # no queda nada después. El bucle de arriba mira pares, así que este
    # caso hay que cobrarlo aparte o la pieza se cierra sobre una promesa.
    if (grammar is not None and grammar.applied_escape and options
            and is_applied_dominant(options[-1])):
        total += grammar.applied_escape * weights.grammar

    if grammar is not None and grammar.plagal_close and len(options) >= 2:
        closing, final = options[-2], options[-1]
        if (closing.roman in ("IV", "iv")
                and final.roman in ("I", "i")):
            total += grammar.plagal_close * weights.grammar

    total += _cadence_cost(options, genre_key, weights, tonic_pc)
    if weights.modulation is not None:
        total += modulation_cost(options, weights.modulation, genre_key,
                                 bar_indices, tonic_pc)
    return total * weights.emphasis


def _cadence_cost(
    options: Sequence[ChordOption],
    genre_key: str,
    weights: HarmonyWeights,
    tonic_pc: int,
) -> float:
    """Reward an ending that behaves like a cadence in the chosen style."""
    if len(options) < 2:
        return 0.0
    penultimate, last = options[-2], options[-1]
    if last.root_pc != tonic_pc:
        return 0.0

    motion = (last.root_pc - penultimate.root_pc) % 12
    if genre_key in ("classical", "chorale"):
        if motion == 5:                    # V-I, authentic
            return weights.cadence
        if motion == 7:                    # IV-I, plagal
            return weights.cadence * 0.6
    elif genre_key == "jazz":
        if motion == 5:
            return weights.cadence
        if motion == 1:                    # bII-I, tritone substitution
            return weights.cadence * 0.8
    else:                                   # modal
        if motion == 7:                    # IV-I, the plagal cadence
            # Checked before the stepwise options: this is the close the
            # idiom is built on, and letting a step-cadence match first made
            # the plagal an also-ran in its own style.
            return weights.cadence * 2.0
        if motion in (2, 10):              # bVII-I or II-I by step
            # Modal and organum practice lean on the plagal close far more
            # than on anything dominant-shaped, so it is rewarded here at
            # full strength rather than as a lesser alternative.
            return weights.cadence
        if motion == 5:
            return weights.cadence * 0.3
    return 0.0


#: Starting weights per genre. The user can override any of them.
def genre_harmony_weights(genre_key: str, emphasis: float = 8.0) -> HarmonyWeights:
    """
    Harmony weights that make each style behave like itself.

    The emphasis default is deliberately high: voice-leading cost accumulates
    over every voice of every transition, so with a neutral multiplier the
    progression term is drowned out and the generator produces smooth
    nonsense -- exactly the placebo the whole exercise is meant to avoid.
    """
    base = HarmonyWeights(emphasis=emphasis)
    if genre_key in ("classical", "chorale"):
        base.root_position_diminished = 30.0
        base.dominant_resolution = -26.0
        base.cadence = -60.0
    elif genre_key == "gregorian":
        base.dominant_resolution = 0.0
        base.dominant_escape = 0.0
        base.cadence = -70.0
        base.root_position_diminished = 20.0
    elif genre_key == "jazz":
        base.colour = -12.0
        base.cadence = -55.0
        base.dominant_resolution = -30.0
    return base


#: Borrowed chords each style reaches for by default, so the generator starts
#: somewhere idiomatic instead of empty. The user can tick or untick any.
#:
#: Classical writing borrows the minor subdominant and the Neapolitan sixth;
#: chorale writing adds the half-diminished ii; jazz lives on bVII, bVI and
#: the flat second used as a tritone substitute; modal writing borrows
#: nothing, because its colour already comes from the mode itself.
#: Deliberately sparse. Everything switched on at once made the generator
#: sound like it was showing off every trick it knew, which was most of what
#: made the results unpleasant. One borrowed colour per style is enough to
#: hear the flavour; the rest are a tick away.
GENRE_DEFAULT_BORROWED: Dict[str, List[str]] = {
    "classical": ["iv"],
    "chorale": ["iv"],
    # Jazz gets none by default: its colour already comes from the sevenths
    # and the tritone substitutions, and piling borrowed chords on top of
    # that is what turned it to mud.
    "jazz": [],
    "gregorian": ["bVII"],
}


# ---------------------------------------------------------------------------
# Functional grammar
# ---------------------------------------------------------------------------

#: The three jobs a chord can hold in a key.
TONIC = "tonic"
SUBDOMINANT = "subdominant"
DOMINANT = "dominant"

#: Which function each scale degree normally serves. The mediant is filed as
#: tonic and the submediant as tonic-ish because both share two notes with
#: the tonic triad and can stand in for it.
DEGREE_FUNCTION = {
    1: TONIC, 3: TONIC, 6: TONIC,
    2: SUBDOMINANT, 4: SUBDOMINANT,
    5: DOMINANT, 7: DOMINANT,
}

#: Function of each borrowed chord.
BORROWED_FUNCTION = {
    "iv": SUBDOMINANT, "iiø": SUBDOMINANT,
    "bVI": SUBDOMINANT, "bIII": TONIC,
    "v": DOMINANT,
    # bII in root position is the tritone substitute: a dominant standing in
    # for V, a semitone above the tonic it resolves to.
    "bII": DOMINANT,
    "subV": DOMINANT,
    # The Neapolitan *sixth* is the classical usage and behaves differently:
    # with its third in the bass it prepares the dominant rather than acting
    # as one, so it is filed as a subdominant even though it shares bII's root.
    "N6": SUBDOMINANT,
    # bVII is the fourth of the fourth. It stands where a subdominant stands,
    # which is why the bVII-IV-I turn sounds plagal rather than cadential.
    "bVII": SUBDOMINANT,
}


def _borrowed_subdominant(option: "ChordOption") -> bool:
    """
    ¿Un préstamo que se para donde se para una subdominante?

    Se pregunta por el nombre del préstamo y no por :func:`function_of`,
    que devuelve subdominante para todo lo que no reconoce --- y lo que no
    reconoce incluye a las dominantes aplicadas, que son justamente las que
    tienen que seguir obligadas a resolver.
    """
    return (option.is_borrowed
            and not is_applied_dominant(option)
            and BORROWED_FUNCTION.get(option.roman) == SUBDOMINANT)


def is_applied_dominant(option: "ChordOption") -> bool:
    """
    ¿Es una dominante aplicada -- un V/x -- y no un acorde prestado?

    Las dos viajan en el mismo campo (``is_borrowed``) porque ninguna es
    diatónica, pero no son lo mismo: la prestada trae el color del modo
    paralelo y la aplicada es una tónica pasajera. Distinguirlas importa
    para cobrarlas por separado y para no llamar "intercambio modal" a un
    V del V.
    """
    return option.roman.startswith("V/")


def seventh_is_structural(option: "ChordOption") -> bool:
    """
    ¿Este acorde necesita su séptima para seguir siendo lo que es?

    Sí en tres casos: una dominante --- la séptima es la mitad del trítono
    que la define y el motivo entero por el que resuelve ---, un
    semidisminuido --- sin séptima es una tríada disminuida, que es otro
    acorde --- y cualquier cosa que la gramática lea como dominante, o sea
    el V y las aplicadas. En el resto la séptima es color, y el color se
    puede cambiar por otro color.
    """
    if option.quality in ("dominant", "halfdim", "dim"):
        return True
    return option.roman == "V" or is_applied_dominant(option)


def function_of(option: "ChordOption") -> str:
    """What job this chord does in the key.

    Una dominante aplicada cae en el caso por defecto, subdominante, y está
    bien: dentro de la frase se para donde se para una subdominante, que es
    justo antes de la dominante a la que apunta.
    """
    if option.is_borrowed:
        return BORROWED_FUNCTION.get(option.roman, SUBDOMINANT)
    return DEGREE_FUNCTION.get(option.scale_degree, SUBDOMINANT)


@dataclass
class FunctionalGrammar:
    """
    What may follow what, per style.

    Root-motion tables alone judge a progression by interval arithmetic, and
    that is not how harmony works: a dominant does not merely prefer to fall
    a fifth, it wants to *resolve*, and where it may go instead is a short,
    well-known list. Writing the grammar out means the search stops guessing
    the syntax from distances and can spend its effort on the counterpoint,
    which is what it is actually for.

    ``transitions`` maps a function to the functions that may follow it, each
    with a cost (negative rewards the move). Anything missing gets
    ``unlisted``.
    """

    key: str
    transitions: Dict[str, Dict[str, float]]
    unlisted: float = 20.0
    #: Extra reward when a dominant resolves to the tonic by falling a fifth.
    authentic: float = -30.0
    #: Reward for the deceptive resolution, dominant to submediant.
    deceptive: float = -16.0
    #: Reward for a plagal move, subdominant straight to tonic.
    plagal: float = -12.0
    #: Extra reward when the piece ENDS plagally, on top of the move itself.
    #: Applied at the close because that is where a cadence lives: rewarding
    #: the motion alone let a stepwise ii-i win the ending while IV-I turned
    #: up harmlessly in the middle.
    plagal_close: float = 0.0
    #: Reward for a tritone substitute resolving down a semitone.
    tritone_substitute: float = 0.0
    #: Extra reward for a subdominant-dominant pair that then resolves --
    #: the ii-V-I that jazz is built on. Applied to the whole three-chord
    #: shape rather than to each step, because that is how it is heard.
    two_five_one: float = 0.0
    #: Cost for a dominant following another dominant. A chain of them
    #: postpones the resolution the ear is waiting for.
    chained_dominants: float = 0.0
    #: Extra reward for a plagal close, on top of the cadence term.
    plagal_bonus: float = 0.0
    #: Extra reward when the ii-V uses the plain diatonic chords rather than
    #: borrowed or substituted ones.
    plain_two_five: float = 0.0
    #: Reward for a ii-V aimed at a degree other than the tonic -- the same
    #: two-chord approach applied to ii, iii, IV, V or vi. This is ordinary
    #: jazz motion, not a modulation: the pair simply borrows the dominant of
    #: wherever it is heading and lands there.
    secondary_two_five: float = 0.0
    #: Precio de escribir una dominante aplicada -- un V/x -- en absoluto.
    #: Es un costo y no un premio a propósito: en la escritura de práctica
    #: común el V del V es un color ocasional, no material de todos los
    #: compases, así que tiene que perder contra el ii-V llano salvo que el
    #: entorno la justifique. Es la mitad "ligera posibilidad".
    applied_dominant: float = 0.0
    #: Premio cuando esa dominante aplicada efectivamente resuelve donde
    #: apunta, bajando una quinta. Junto con el costo de arriba deja el par
    #: V/V - V apenas por encima del ii-V, y cualquier otra continuación muy
    #: por debajo: es la mitad "y que resuelva".
    applied_resolution: float = 0.0
    #: Costo de una dominante aplicada que NO resuelve donde apunta. El
    #: premio de arriba solo no alcanzaba: pagado el costo de entrada, irse
    #: al ii o al vi salía apenas más caro que resolver, y una de cada tres
    #: se escapaba. Una aplicada que no resuelve no es un color, es un error
    #: de sintaxis, y se cobra como tal.
    applied_escape: float = 0.0

    def cost(self, previous: str, current: str) -> float:
        return self.transitions.get(previous, {}).get(current, self.unlisted)


#: Common practice: a direct, cadential syntax. Tonic goes anywhere,
#: subdominant leads to the dominant, and the dominant is expected to resolve.
#: Falling back from dominant to subdominant is the classic retrogression.
CLASSICAL_GRAMMAR = FunctionalGrammar(
    key="classical",
    transitions={
        TONIC: {TONIC: 6.0, SUBDOMINANT: -14.0, DOMINANT: -10.0},
        SUBDOMINANT: {TONIC: -4.0, SUBDOMINANT: -2.0, DOMINANT: -18.0},
        DOMINANT: {TONIC: -24.0, DOMINANT: 2.0, SUBDOMINANT: 22.0},
    },
    authentic=-34.0,
    deceptive=-18.0,
    plagal=-10.0,
    # Calibrado contra el ii-V llano, que en este estilo vale -18: el par
    # V/V - V queda en -14, o sea peor, así que aparece de vez en cuando y
    # no en cada frase. Un V/V que no resuelve se queda con el costo entero.
    applied_dominant=24.0,
    applied_resolution=-16.0,
    applied_escape=42.0,
)

#: Chorale writing is the same syntax, held tighter: the dominant is even
#: more strongly expected to resolve and wandering costs more.
CHORALE_GRAMMAR = FunctionalGrammar(
    key="chorale",
    transitions={
        TONIC: {TONIC: 10.0, SUBDOMINANT: -14.0, DOMINANT: -12.0},
        SUBDOMINANT: {TONIC: -2.0, SUBDOMINANT: -1.0, DOMINANT: -22.0},
        DOMINANT: {TONIC: -30.0, DOMINANT: 1.0, SUBDOMINANT: 28.0},
    },
    unlisted=26.0,
    authentic=-40.0,
    deceptive=-20.0,
    plagal=-8.0,
    # El coral aprieta todo, y el ii-V acá vale -22. Se mantiene la misma
    # distancia relativa: el V/V es un color, no un ladrillo.
    applied_dominant=25.0,
    applied_resolution=-16.0,
    applied_escape=46.0,
)

#: Modal writing has no dominant function to speak of: the cadence is plagal
#: or stepwise, and the leading-tone pull that drives the other styles simply
#: is not there. Everything is comparatively flat, which is the point.
MODAL_GRAMMAR = FunctionalGrammar(
    key="gregorian",
    transitions={
        TONIC: {TONIC: 4.0, SUBDOMINANT: -12.0, DOMINANT: -8.0},
        SUBDOMINANT: {TONIC: -20.0, SUBDOMINANT: -6.0, DOMINANT: -6.0},
        DOMINANT: {TONIC: -12.0, SUBDOMINANT: -8.0, DOMINANT: 2.0},
    },
    unlisted=8.0,
    authentic=-10.0,
    deceptive=-4.0,
    # The plagal close is what this idiom cadences with; it should be the
    # expected ending rather than one possibility among several.
    plagal=-90.0,
    plagal_bonus=-70.0,
    plagal_close=-260.0,
)

#: Jazz runs on ii-V-I and on substitution: the subdominant-to-dominant
#: motion is the strongest thing in the language, and a dominant may be
#: replaced by the one a tritone away.
JAZZ_GRAMMAR = FunctionalGrammar(
    key="jazz",
    transitions={
        TONIC: {TONIC: 4.0, SUBDOMINANT: -18.0, DOMINANT: -12.0},
        SUBDOMINANT: {TONIC: -6.0, SUBDOMINANT: -4.0, DOMINANT: -26.0},
        DOMINANT: {TONIC: -26.0, DOMINANT: -6.0, SUBDOMINANT: 8.0},
    },
    unlisted=10.0,
    authentic=-30.0,
    deceptive=-14.0,
    plagal=-6.0,
    tritone_substitute=-24.0,
    # The ii-V is not one option among many in this idiom, it is the
    # default motion, so it is rewarded far above anything else. Reaching it
    # unaltered is preferred too: a plain ii-V reads as the idiom, an
    # altered one as a variation on it.
    two_five_one=-140.0,
    chained_dominants=26.0,
    plain_two_five=-60.0,
    secondary_two_five=-95.0,
    # Estas tres estaban sin poner, o sea en cero, y eran las únicas que
    # vigilan la dominante aplicada suelta. Medido sobre quince progresiones
    # generadas: uno de cada cuatro acordes era un V/x y sólo el 37% caía
    # donde apuntaba --- una dominante aplicada que no resuelve no es un
    # color, es una promesa que el oído escucha y que después no pasa.
    #
    # `secondary_two_five` sigue premiando el par ii-V/x bien preparado con
    # -95, así que el caso idiomático gana cómodo; lo que se encarece es el
    # V/x suelto, y sobre todo el que se escapa.
    applied_dominant=18.0,
    applied_resolution=-14.0,
    applied_escape=45.0,
)

GRAMMARS: Dict[str, FunctionalGrammar] = {
    "classical": CLASSICAL_GRAMMAR,
    "chorale": CHORALE_GRAMMAR,
    "gregorian": MODAL_GRAMMAR,
    "jazz": JAZZ_GRAMMAR,
}


def grammar_cost(
    previous: "ChordOption",
    current: "ChordOption",
    grammar: FunctionalGrammar,
    tonic_pc: int,
    before: Optional["ChordOption"] = None,
) -> float:
    """
    Score one chord following another, by what each chord is doing.

    On top of the function-to-function cost, the named resolutions are
    recognised explicitly: a dominant falling a fifth to the tonic, the
    deceptive move to the submediant, the plagal approach, and -- in jazz --
    a dominant sliding down a semitone, which is the tritone substitute.
    """
    previous_function = function_of(previous)
    current_function = function_of(current)
    total = grammar.cost(previous_function, current_function)

    motion = (current.root_pc - previous.root_pc) % 12
    is_tonic_arrival = current.root_pc == tonic_pc

    if before is not None:
        before_function = function_of(before)
        if (grammar.two_five_one
                and before.roman == "ii"
                and previous.roman == "V"
                and (current_function == TONIC or motion == 5)):
            # The whole ii-V-I shape, rewarded once at its landing.
            total += grammar.two_five_one
            if grammar.plain_two_five and not (before.is_borrowed
                                               or previous.is_borrowed):
                total += grammar.plain_two_five
        elif grammar.secondary_two_five and _is_secondary_two_five(
                before, previous, current):
            total += grammar.secondary_two_five
        if grammar.chained_dominants and before_function == previous_function == DOMINANT:
            total += grammar.chained_dominants

    # Las dominantes aplicadas se cobran aparte de la gramática de
    # funciones, que no las distingue de una subdominante cualquiera.
    if grammar.applied_dominant and is_applied_dominant(current):
        total += grammar.applied_dominant
    if is_applied_dominant(previous):
        if motion == 5:
            # Bajó una quinta: aterrizó donde apuntaba.
            total += grammar.applied_resolution
        else:
            total += grammar.applied_escape
        # Y no cobra el premio plagal de más abajo: un V/V que cae en la
        # tónica no está haciendo una cadencia plagal, está abandonando una
        # resolución.
        return total

    if previous_function == DOMINANT:
        if motion == 5 and is_tonic_arrival:
            total += grammar.authentic
        elif motion == 5:
            total += grammar.authentic * 0.4      # secondary resolution
        elif current.scale_degree == 6:
            total += grammar.deceptive
        elif motion == 11 and grammar.tritone_substitute:
            # Down a semitone: the substitute resolving like the dominant it
            # stands in for.
            total += grammar.tritone_substitute
    elif previous_function == SUBDOMINANT and is_tonic_arrival:
        # The borrowed minor subdominant closes just as plagally as the
        # major one and gets the same reward, no more: rewarding it above
        # the diatomic IV made the search hunt for a borrowed chord even
        # when the user had asked for hardly any, because both land in the
        # same total and the bigger reward simply won.
        total += grammar.plagal + grammar.plagal_bonus

    return total


# ---------------------------------------------------------------------------
# Modulation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModulationTarget:
    """A key the piece may visit before coming home.

    ``offset`` is the new tonic in semitones above the home tonic, and
    ``mode_key`` the mode it takes there. An offset of zero with a different
    mode is a change of mode over the same tonic -- what the interface calls
    a modal modulation.
    """

    key: str
    label: str
    offset: int
    mode_key: str
    description: str

    @property
    def is_modal(self) -> bool:
        return self.offset == 0


#: Destinations, grounded in the standard account of closely related keys:
#: the five keys built on the diatonic triads (ii, iii, IV, V, vi) plus the
#: parallel mode. In major the commonest modulation is to the dominant; in
#: minor, to the relative major or the minor dominant.
MODULATION_TARGETS: Dict[str, ModulationTarget] = {
    "V": ModulationTarget(
        "V", "Dominante (V)", 7, "major",
        "La modulación más común en modo mayor. Sube una quinta y sólo "
        "cambia una nota de la escala, así que el oído la sigue sin esfuerzo.",
    ),
    "IV": ModulationTarget(
        "IV", "Subdominante (IV)", 5, "major",
        "Baja una quinta. Suena más relajada que ir al dominante, y es el "
        "camino habitual cuando la pieza quiere ensancharse en vez de tensar.",
    ),
    "vi": ModulationTarget(
        "vi", "Relativo menor (vi)", 9, "minor",
        "Mismo grupo de notas, otro centro. Al no cambiar ninguna alteración "
        "es la modulación más suave que existe.",
    ),
    "ii": ModulationTarget(
        "ii", "Supertónica menor (ii)", 2, "minor",
        "El relativo de la subdominante. Cercana, aunque menos frecuente que "
        "el dominante o el relativo.",
    ),
    "iii": ModulationTarget(
        "iii", "Mediante menor (iii)", 4, "minor",
        "El relativo del dominante. La más lejana de las cercanas.",
    ),
    "bIII": ModulationTarget(
        "bIII", "Relativo mayor (bIII)", 3, "major",
        "Desde un centro menor, el salto al relativo mayor. En modo menor es "
        "la modulación más habitual junto con el dominante menor.",
    ),
    "parallel_minor": ModulationTarget(
        "parallel_minor", "Modal: a menor", 0, "minor",
        "Misma tónica, modo menor. No es un viaje a otra tonalidad sino un "
        "cambio de color sobre el mismo centro.",
    ),
    "parallel_major": ModulationTarget(
        "parallel_major", "Modal: a mayor", 0, "major",
        "Misma tónica, modo mayor.",
    ),
    "parallel_dorian": ModulationTarget(
        "parallel_dorian", "Modal: a dórico", 0, "dorian",
        "Misma tónica, modo dórico: menor pero con la sexta mayor.",
    ),
    "parallel_mixolydian": ModulationTarget(
        "parallel_mixolydian", "Modal: a mixolidio", 0, "mixolydian",
        "Misma tónica, modo mixolidio: mayor con la séptima rebajada.",
    ),
}


@dataclass
class ModulationSettings:
    """What modulations are allowed and how much they are sought."""

    #: Travel to another tonic.
    key_enabled: bool = False
    #: Change mode over the same tonic. The two can be on at once.
    modal_enabled: bool = False
    #: Which targets are offered. Empty means the genre's defaults.
    targets: Tuple[str, ...] = ()
    #: How hard the search looks for a modulation. Negative seeks them out;
    #: at zero they are merely permitted.
    weight: float = -25.0
    #: Cost of each change of key area, which keeps a piece from wandering
    #: through a new key every other chord.
    switch_cost: float = 55.0
    #: Fewest whole bars a visit must last. Measured in bars rather than
    #: chords because that is how a listener hears it: three chords inside
    #: one bar is a passing colour, the same three spread over two bars is a
    #: new key.
    min_bars: int = 2
    #: Fewest bars the piece needs before modulating is offered at all.
    #: Below this there is no room to leave, settle and come back.
    min_bars_for_modulation: int = 8
    #: Bars that must stay in the home key at each end.
    home_margin_bars: int = 2
    #: Cost when a visit starts in the middle of a bar instead of on its
    #: downbeat, which is where a change of key is normally heard.
    offbeat_start: float = 90.0
    #: Cost when the excursion does not lead back with a dominant. Coming
    #: home should be prepared, not stumbled into.
    weak_return: float = 120.0
    #: How many separate excursions a piece may make. One is the normal
    #: shape: establish home, travel, come back. Several turns the piece
    #: into a tour, which is what "it modulates and does nothing" looked
    #: like from the outside.
    max_excursions: int = 1
    #: Cost per excursion beyond that limit.
    extra_excursion: float = 260.0

    @property
    def enabled(self) -> bool:
        return self.key_enabled or self.modal_enabled


#: Per genre: which targets, whether each kind starts on, and how strongly.
#:
#: Common practice modulates, but not restlessly, so it starts on with a mild
#: appetite and only to the closest keys. Jazz moves far more freely, and
#: leans on the subdominant, the dominant and the parallel mode. Modal
#: writing shifts to the fourth and the fifth, which is exactly what the
#: authentic and plagal forms of each mode are.
#: Destinations are fixed per style rather than offered freely: a piece does
#: not modulate wherever it likes, it goes where its idiom goes. Common
#: practice travels to the closest keys, jazz adds the parallel mode and the
#: flat mediant, and modal writing shifts by fourth and fifth, which is what
#: the authentic and plagal forms of each mode are.
GENRE_MODULATION: Dict[str, ModulationSettings] = {
    "classical": ModulationSettings(
        key_enabled=False, modal_enabled=False,
        targets=("V", "vi", "IV"), weight=-22.0, switch_cost=70.0,
        min_bars=2, home_margin_bars=2, weak_return=140.0,
    ),
    "chorale": ModulationSettings(
        key_enabled=False, modal_enabled=False,
        targets=("V", "vi"), weight=-16.0, switch_cost=62.0,
        min_bars=2, home_margin_bars=2, weak_return=160.0,
    ),
    "gregorian": ModulationSettings(
        key_enabled=False, modal_enabled=False,
        targets=("V", "IV", "parallel_dorian", "parallel_mixolydian"),
        weight=-20.0, switch_cost=130.0,
        # Modal writing has no dominant to lead back with, so the return is
        # not held to that standard.
        min_bars=2, home_margin_bars=1, weak_return=30.0,
    ),
    "jazz": ModulationSettings(
        key_enabled=False, modal_enabled=False,
        targets=("IV", "V", "parallel_minor", "parallel_major", "bIII"),
        weight=-34.0, switch_cost=40.0,
        min_bars=2, home_margin_bars=1, weak_return=90.0,
    ),
}


def modulation_pool(
    tonic_pc: int,
    settings: ModulationSettings,
    with_sevenths: bool = False,
) -> List[ChordOption]:
    """Chords from every key area the piece is allowed to visit."""
    if not settings.enabled:
        return []

    options: List[ChordOption] = []
    for key in settings.targets:
        target = MODULATION_TARGETS.get(key)
        if target is None:
            continue
        if target.is_modal and not settings.modal_enabled:
            continue
        if not target.is_modal and not settings.key_enabled:
            continue
        mode = MODES.get(target.mode_key)
        if mode is None:
            continue
        new_tonic = (tonic_pc + target.offset) % 12
        for option in diatonic_options(new_tonic, mode, with_sevenths):
            options.append(ChordOption(
                chord=option.chord,
                label=option.label,
                # Roman numerals are shown relative to the key being visited,
                # prefixed so the user can see where they are.
                roman=f"{key}:{option.roman}",
                scale_degree=option.scale_degree,
                root_pc=option.root_pc,
                is_borrowed=True,
                key_area=key,
            ))
    return options


def modulation_cost(
    options: Sequence[ChordOption],
    settings: ModulationSettings,
    genre_key: str,
    bar_indices: Optional[Sequence[int]] = None,
    tonic_pc: int = 0,
) -> float:
    """
    Score where the piece travels and how it gets back.

    Charges for every change of key area, so a modulation has to be worth
    making; rewards a visit that actually settles rather than touching a
    foreign chord in passing; and requires the ends to be at home, which is
    what makes it a round trip instead of a drift.
    """
    if not settings.enabled or not options:
        return 0.0

    areas = [option.key_area for option in options]
    bars = list(bar_indices) if bar_indices else [0] * len(options)
    last_bar = max(bars) if bars else 0
    total = 0.0

    switches = sum(1 for a, b in zip(areas, areas[1:]) if a != b)
    total += settings.switch_cost * switches

    excursions = 0
    index = 0
    while index < len(areas):
        area = areas[index]
        span = 1
        while index + span < len(areas) and areas[index + span] == area:
            span += 1
        if not area:
            index += span
            continue
        excursions += 1
        if excursions > settings.max_excursions:
            total += settings.extra_excursion

        first_bar = bars[index]
        final_bar = bars[index + span - 1]
        bar_span = final_bar - first_bar + 1

        if bar_span >= settings.min_bars:
            # Scaled by how long the visit lasts: a flat reward could never
            # outweigh the cost of leaving and returning, so the search
            # simply stayed home, and musically a longer stay *is* more of a
            # modulation than a two-chord detour.
            total += settings.weight * span
        else:
            # Too brief to be a key of its own -- that is a borrowed chord
            # wearing a modulation's clothes.
            total += abs(settings.weight) * 3.0 + settings.switch_cost

        # A change of key is heard on a downbeat. Starting mid-bar reads as
        # an accident rather than a decision.
        if index > 0 and bars[index - 1] == first_bar:
            total += settings.offbeat_start
        # Even-numbered bars are the usual place for a phrase to turn.
        elif first_bar % 2 == 1:
            total += settings.offbeat_start * 0.35

        # Room to breathe at both ends: the piece should establish home,
        # travel, and have space to land again.
        if first_bar < settings.home_margin_bars:
            total += 150.0
        if final_bar > last_bar - settings.home_margin_bars:
            total += 150.0

        # Coming home has to be prepared. The chord that leads back should
        # pull -- a fifth fall into the home key, or the semitone slide of a
        # substitute -- otherwise the return just happens.
        following = index + span
        if following < len(options):
            leaving = options[following - 1]
            arriving = options[following]
            motion = (arriving.root_pc - leaving.root_pc) % 12
            prepared = motion == 5 or (motion == 11 and genre_key == "jazz")
            if not prepared:
                total += settings.weak_return
        index += span

    # The piece has to start and finish at home.
    if areas[0]:
        total += 200.0
    if areas[-1]:
        total += 200.0
    return total


#: Whether each style builds its chords as sevenths by default. Jazz is
#: written in sevenths as a matter of course -- a bare triad is the exception
#: there -- while common practice and plainchant are triadic, with sevenths
#: appearing on particular degrees rather than everywhere.
GENRE_SEVENTHS: Dict[str, bool] = {
    "classical": False,
    "chorale": False,
    "gregorian": False,
    "jazz": True,
}


#: How each key area is written for the user. The internal keys are English
#: identifiers and were leaking into the score labels.
AREA_LABELS: Dict[str, str] = {
    "V": "dominante",
    "IV": "subdominante",
    "vi": "relativo menor",
    "ii": "segundo menor",
    "iii": "tercero menor",
    "bIII": "relativo mayor",
    "parallel_minor": "menor",
    "parallel_major": "mayor",
    "parallel_dorian": "dórico",
    "parallel_mixolydian": "mixolidio",
}


def display_roman(option: "ChordOption") -> str:
    """
    How a chord is labelled on screen.

    A chord visited in another key was printed as ``parallel_mixolydian:vi``,
    which is neither readable nor Spanish. Written as ``vi en mixolidio`` it
    says the same thing in a form a musician can scan.
    """
    roman = option.roman
    if ":" in roman:
        area, _, local = roman.partition(":")
        return f"{local} en {AREA_LABELS.get(area, area)}"
    return roman


# ---------------------------------------------------------------------------
# Set-piece cadences
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SetPiece:
    """A fixed progression that can appear instead of a generated one.

    These are quotations, not inventions: when one turns up the program is
    not composing a progression at all, it is laying out a shape that already
    exists and letting the search decide only how to sing it.
    """

    key: str
    label: str
    description: str
    #: (semitones above the tonic, quality) for each chord, in order.
    chords: Tuple[Tuple[int, str], ...]
    #: Bass note per chord, in semitones above the tonic. When set, the
    #: chords are inversions over a moving bass rather than root position,
    #: and the symbols are written with a slash.
    bass_line: Tuple[int, ...] = ()

    def __len__(self) -> int:
        return len(self.chords)


#: The Phrygian cadence: the minor subdominant with its third in the bass
#: falling a semitone to the dominant. The bass step bVI-V is what names it.
PHRYGIAN_CADENCE = SetPiece(
    key="phrygian",
    label="Cadencia frigia",
    description=(
        "i - bVII - bVI - V. El nombre viene del modo frigio: entre el bVI y "
        "el V hay sólo un semitono, y esa sensible descendente es la que le "
        "da el color."
    ),
    # i - bVII - bVI - V: the bass walks down the natural minor scale and
    # arrives at the dominant a semitone from above, which is what gives the
    # cadence its name.
    chords=((0, "minor"), (10, "major"), (8, "major"), (7, "major")),
)

#: Vivaldi's cycle: roots falling by fifths all the way around, the chords
#: majorised into a chain of secondary dominants, landing on the dominant and
#: then home. In A minor that is Am, D, G, C, F, B, E, Am.
VIVALDI_CADENCE = SetPiece(
    key="vivaldi",
    label="Ciclo de Vivaldi",
    description=(
        "Una cadena de quintas descendentes con los acordes mayorizados, "
        "como una hilera de dominantes que se resuelven una en otra hasta "
        "llegar a la dominante y volver a casa."
    ),
    chords=((0, "minor"), (5, "major"), (10, "major"), (3, "major"),
            (8, "major"), (2, "major"), (7, "major"), (0, "minor")),
)

#: Degrees written the way a musician reads them, rather than as a semitone
#: count. The quotations are minor-mode shapes, so the scale they are read
#: against is the natural minor.
_SET_PIECE_ROMANS = {
    0: "i", 1: "bII", 2: "ii°", 3: "bIII", 5: "iv", 7: "V",
    8: "bVI", 10: "bVII",
}

#: The descending chromatic bass: the tonic chord held while the bass walks
#: down under it. Every upper voice stays put -- oblique motion throughout --
#: which is what makes the line so audible. After the chromatic descent the
#: bass drops to the flat sixth and the dominant closes it.
CHROMATIC_BASS_CADENCE = SetPiece(
    key="chromatic_bass",
    label="Bajo cromático descendente",
    description=(
        "El acorde de tónica se sostiene mientras el bajo baja paso a paso "
        "por debajo. Las voces de arriba no se mueven: todo el interés está "
        "en esa línea que desciende hasta la dominante."
    ),
    chords=((0, "minor"), (0, "minor"), (0, "minor"), (0, "minor"),
            (7, "major"), (0, "minor")),
    bass_line=(0, 11, 10, 8, 7, 0),
)

#: Bass notes for the chromatic cadence, as semitones above the tonic. The
#: chord stays the same; only the bass moves.
#: 1 - 7 - b7, then the leap down to the flat sixth, then the dominant.
#: The step from b7 to b6 is a whole tone, not a semitone: the line is
#: chromatic where it descends and then drops to the sixth, which is what
#: sets up the cadence.
CHROMATIC_BASS_LINE = (0, 11, 10, 8, 7, 0)

SET_PIECES: Dict[str, SetPiece] = {
    piece.key: piece
    for piece in (PHRYGIAN_CADENCE, VIVALDI_CADENCE, CHROMATIC_BASS_CADENCE)
}

#: Styles where a quotation like this belongs at all.
SET_PIECE_GENRES = ("classical", "chorale", "jazz")

#: Not every quotation suits every style: the Phrygian and the Vivaldi cycle
#: are common-practice gestures, while the descending chromatic bass is at
#: home in jazz too.
SET_PIECE_BY_GENRE: Dict[str, Tuple[str, ...]] = {
    "classical": ("phrygian", "vivaldi", "chromatic_bass"),
    "chorale": ("phrygian", "vivaldi"),
    "jazz": ("chromatic_bass",),
}

#: Modes whose tonic triad is minor, so a minor-mode quotation fits.
MINOR_MODES = ("minor", "harmonic", "dorian", "phrygian")

#: How often one turns up when everything lines up. Deliberately low: the
#: point is that it is a surprise, not a feature you can count on.
SET_PIECE_CHANCE = 0.10

#: With the "raise the odds" setting on. Deliberately much higher than the
#: default: someone who ticks that box wants to hear these, not to keep
#: rolling for them.
SET_PIECE_CHANCE_HIGH = 0.45


def set_piece_for(
    genre_key: str,
    mode_key: str,
    chord_count: int,
    equal_durations: bool,
) -> List[SetPiece]:
    """
    Which quotations could stand in for a generated progression here.

    Every condition has to hold: the style has to be one that quotes, the
    key has to be minor -- both of these shapes are minor-mode gestures --
    the piece has to be exactly as long as the quotation, and the rhythm has
    to be even, because these are remembered as steady successions of equal
    chords rather than as anything syncopated.
    """
    if genre_key not in SET_PIECE_GENRES:
        return []
    # Any minor key: natural, harmonic, and the modes whose tonic triad is
    # minor. Melodic minor is not offered because the program does not have
    # it as a mode.
    if mode_key not in MINOR_MODES:
        return []
    if not equal_durations:
        return []
    allowed = SET_PIECE_BY_GENRE.get(genre_key, ())
    return [SET_PIECES[key] for key in allowed
            if len(SET_PIECES[key]) == chord_count]


def set_piece_options(piece: SetPiece, tonic_pc: int) -> List[ChordOption]:
    """Turn a quotation into the concrete chords of a key."""
    options: List[ChordOption] = []
    for position, (offset, quality) in enumerate(piece.chords):
        root_pc = (tonic_pc + offset) % 12
        tones = [ChordTone(s, role, degree)
                 for s, role, degree in _QUALITY_TONES[quality]]
        flat = offset in (1, 3, 6, 8, 10)
        chord = Chord(symbol="", root_pc=root_pc,
                      root_letter=(FLAT_NAMES if flat else SHARP_NAMES)[root_pc][0],
                      tones=tones)
        chord.symbol = _symbol_for(chord, prefer_flats=flat)

        # A moving bass turns these into inversions, and the symbol has to
        # say so: printing four bars of "Am" hides the very line the cadence
        # is about.
        if piece.bass_line and position < len(piece.bass_line):
            bass_pc = (tonic_pc + piece.bass_line[position]) % 12
            if bass_pc != root_pc:
                chord.bass_pc = bass_pc
                names = FLAT_NAMES if flat else SHARP_NAMES
                chord.symbol = f"{chord.symbol}/{names[bass_pc]}"

        options.append(ChordOption(
            chord=chord, label=chord.symbol,
            roman=_SET_PIECE_ROMANS.get(offset, f"+{offset}"),
            scale_degree=0, root_pc=root_pc,
        ))
    return options


#: What each style starts with. These are the textures the idioms actually
#: use: plainchant is thin and modal, chorale writing is the four-part SATB
#: it is named after, and jazz voicings need four parts to carry a seventh.
GENRE_DEFAULTS: Dict[str, dict] = {
    "classical": {"voices": ("B", "T", "S"), "sevenths": False, "colour": 0.0,
                  "mode": "major"},
    "chorale": {"voices": ("B", "T", "A", "S"), "sevenths": False,
                "colour": 0.0, "mode": "major"},
    "gregorian": {"voices": ("B", "T", "S"), "sevenths": False, "colour": 0.0,
                  "mode": "major"},
    "jazz": {"voices": ("B", "T", "A", "S"), "sevenths": True, "colour": 14.0,
             "mode": "major"},
}


def _is_secondary_two_five(before, previous, current) -> bool:
    """
    A ii-V aimed somewhere other than the tonic.

    The test is the motion, not the degree names: three roots each a fourth
    apart, with a minor chord approaching a major or dominant one that then
    resolves. In C that recognises Em - A - Dm as the ii-V of the second
    degree, which is everyday jazz rather than a change of key.
    """
    first_step = (previous.root_pc - before.root_pc) % 12
    second_step = (current.root_pc - previous.root_pc) % 12
    if first_step != 5 or second_step != 5:
        return False
    if before.quality not in ("minor", "halfdim"):
        return False
    return previous.quality in ("major", "dominant")
