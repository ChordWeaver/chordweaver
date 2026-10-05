# -*- coding: utf-8 -*-
"""
Reading a score back in.

Lets the user start from music that already exists: the file is parsed into
the same chord entries the manual mode works with, so an imported piece can
be re-voiced, ornamented and exported exactly like one typed by hand.

What is read
------------
* **The chords** -- what sounds at each rhythmic position, matched against
  the chord vocabulary and named in American notation.
* **The order of the voices** -- which part sings which note. This is kept
  as the starting arrangement and as what the padlock offers, but the search
  is free to change it. That is the point of importing: you bring the
  harmony, the program finds a better way to sing it. Only a padlock makes
  an arrangement binding.
* **The rhythm** -- durations and bar positions, so the imported piece keeps
  its shape.

Parsed with the standard library alone; MusicXML is plain XML and pulling in
a notation library for this would be a heavy dependency for a small job.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .theory import (
    LETTER_SEMITONES,
    QUALITY_TEMPLATES,
    SHARP_NAMES,
    Chord,
    ChordTone,
    ROLE_ROOT,
    parse_chord,
)
from engine.i18n import tr, trf, trs


class ImportError_(Exception):
    """Raised when a file cannot be read as a score."""


@dataclass
class ImportedChord:
    """One sounding moment recovered from a file."""

    pitches: List[int]              # lowest voice first
    duration_quarters: float
    bar_index: int
    symbol: str = ""
    matched: bool = True            # False when no chord name fitted


@dataclass
class ImportedScore:
    chords: List[ImportedChord] = field(default_factory=list)
    voice_count: int = 0
    beats: int = 4
    beat_type: int = 4
    warnings: List[str] = field(default_factory=list)

    @property
    def bar_count(self) -> int:
        return len({chord.bar_index for chord in self.chords})


def _text(node: Optional[ET.Element], default: str = "") -> str:
    return node.text.strip() if node is not None and node.text else default


def _pitch_to_midi(pitch: ET.Element) -> Optional[int]:
    step = _text(pitch.find("step"))
    if step not in LETTER_SEMITONES:
        return None
    alter = int(float(_text(pitch.find("alter"), "0") or 0))
    octave = int(_text(pitch.find("octave"), "4") or 4)
    return LETTER_SEMITONES[step] + alter + (octave + 1) * 12


def _load_root(path: str) -> ET.Element:
    """Open a .musicxml or a compressed .mxl."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            # A compressed score points at its real content from META-INF.
            names = [n for n in archive.namelist()
                     if n.endswith((".xml", ".musicxml"))
                     and not n.startswith("META-INF")]
            if not names:
                raise ImportError_("El archivo comprimido no contiene una partitura.")
            with archive.open(names[0]) as handle:
                return ET.parse(handle).getroot()
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ImportError_(trf("No se pudo leer el archivo: {exc}", exc=exc)) from exc


def read_musicxml(path: str) -> ImportedScore:
    """
    Read a score into chord entries.

    Notes are collected by their onset, because that is what makes a chord:
    everything sounding at the same moment belongs together, whatever part
    or staff it was written on. Walking the parts and trusting them to line
    up breaks on the first piece whose voices have different rhythms.
    """
    root = _load_root(path)
    score = ImportedScore()

    divisions = 1.0
    beats, beat_type = 4, 4
    #: onset in quarter notes -> list of (pitch, bar index)
    events: Dict[float, List[int]] = {}
    onset_bar: Dict[float, int] = {}
    onset_duration: Dict[float, float] = {}

    bar_start = 0.0
    for bar_index, measure in enumerate(root.iter("measure")):
        attributes = measure.find("attributes")
        if attributes is not None:
            divisions_node = attributes.find("divisions")
            if divisions_node is not None:
                divisions = float(_text(divisions_node, "1") or 1)
            time_node = attributes.find("time")
            if time_node is not None:
                beats = int(_text(time_node.find("beats"), "4") or 4)
                beat_type = int(_text(time_node.find("beat-type"), "4") or 4)

        cursor = bar_start
        longest = cursor
        previous_duration = 0.0
        # Walked in document order, because <backup> and <forward> move the
        # cursor and only make sense in sequence. Reading just the <note>
        # elements ignores those rewinds, and every voice then lands at a
        # different moment -- which turned a four-part chorale into thirty-two
        # one-note "chords".
        for element in measure:
            if element.tag == "backup":
                cursor -= float(_text(element.find("duration"), "0") or 0) / divisions
                previous_duration = 0.0
                continue
            if element.tag == "forward":
                cursor += float(_text(element.find("duration"), "0") or 0) / divisions
                previous_duration = 0.0
                continue
            if element.tag != "note":
                continue

            duration = float(_text(element.find("duration"), "0") or 0) / divisions
            is_chord = element.find("chord") is not None
            is_rest = element.find("rest") is not None
            pitch_node = element.find("pitch")

            if is_chord:
                # Sounds with the previous note rather than after it.
                cursor -= previous_duration

            if not is_rest and pitch_node is not None:
                midi = _pitch_to_midi(pitch_node)
                if midi is not None:
                    events.setdefault(cursor, []).append(midi)
                    onset_bar.setdefault(cursor, bar_index)
                    onset_duration[cursor] = max(
                        onset_duration.get(cursor, 0.0), duration
                    )

            cursor += duration
            previous_duration = duration
            longest = max(longest, cursor)

        # <backup> rewinds within a bar; taking the furthest point reached
        # keeps the next bar starting where it should.
        bar_start = max(longest, bar_start + beats * 4.0 / beat_type)

    score.beats, score.beat_type = beats, beat_type
    if not events:
        raise ImportError_("La partitura no tiene notas que leer.")

    # A chord is three or more notes sounding together. Anything thinner is
    # ornament -- a passing note moves while the rest of the texture holds,
    # so it shows up as a one- or two-note event between the real chords.
    # Reading those as chords of their own distorted the whole progression.
    MIN_NOTES_FOR_CHORD = 3
    skipped = 0
    for onset in sorted(events):
        pitches = sorted(events[onset])
        if len(pitches) < MIN_NOTES_FOR_CHORD:
            skipped += 1
            continue
        chord = ImportedChord(
            pitches=pitches,
            duration_quarters=onset_duration.get(onset, 1.0) or 1.0,
            bar_index=onset_bar.get(onset, 0),
        )
        symbol = identify_chord(pitches)
        chord.symbol = symbol or "-".join(SHARP_NAMES[p % 12] for p in pitches)
        chord.matched = symbol is not None
        score.chords.append(chord)

    if not score.chords:
        raise ImportError_(
            "No se encontró ningún acorde: la partitura tiene menos de tres "
            "voces sonando a la vez."
        )
    if skipped:
        score.warnings.append(
            trf("Se ignoraron {skipped} momento(s) con menos de tres "
                "notas: son notas de adorno, no acordes, y se descartan "
                "para no deformar la progresión.",
                skipped=skipped)
        )
    score.voice_count = max(len(c.pitches) for c in score.chords)
    uneven = {len(c.pitches) for c in score.chords}
    if len(uneven) > 1:
        score.warnings.append(
            trf("La partitura no tiene la misma cantidad de voces en todos "
                "los acordes (van de {value} a {value2}). Se completará o "
                "recortará según las voces que elijas.",
                value=min(uneven), value2=max(uneven))
        )
    unmatched = sum(1 for c in score.chords if not c.matched)
    if unmatched:
        score.warnings.append(
            trf("{unmatched} acorde(s) no coinciden con ningún cifrado "
                "conocido; quedan cargados como notas sueltas.",
                unmatched=unmatched)
        )
    return score


#: Qualities tried when naming a chord, ordered so the plainest reading wins
#: a tie -- a C major triad should come back as "C", not as some exotic
#: spelling that happens to contain the same three notes.
_NAMING_ORDER = [
    "", "m", "7", "maj7", "m7", "dim", "aug", "m7b5", "dim7", "sus4", "sus2",
    "6", "m6", "9", "maj9", "m9", "add9", "7sus4", "mmaj7", "6/9", "11", "13",
    "7#9", "7b9", "maj7#11", "7#11", "m11", "m13", "maj13", "aug7",
]


def identify_chord(pitches: Sequence[int]) -> Optional[str]:
    """
    Name a set of sounding pitches in American notation.

    Every root and quality is tried and the exact match is taken. The bass
    note is preferred as the root, and a slash is added when the chord turns
    out to be inverted, so the name describes what is actually heard rather
    than an abstract root position.
    """
    if not pitches:
        return None
    sounding = {p % 12 for p in pitches}
    bass_pc = min(pitches) % 12

    best: Optional[Tuple[Tuple[int, int], str]] = None
    for index, quality in enumerate(_NAMING_ORDER):
        template = QUALITY_TEMPLATES.get(quality)
        if template is None:
            continue
        for root_pc in range(12):
            expected = {(root_pc + tone.semitones) % 12 for tone in template}
            if expected != sounding:
                continue
            # The commoner reading wins first, and only then the one with its
            # root in the bass. F-A-C-D is both an F6 and a Dm7 in first
            # inversion; naming it by the bass gives F6, but a minor seventh
            # is the reading a musician expects, so quality is ranked first.
            score = (index, 0 if root_pc == bass_pc else 1)
            if best is None or score < best[0]:
                symbol = SHARP_NAMES[root_pc] + quality
                if root_pc != bass_pc:
                    symbol += "/" + SHARP_NAMES[bass_pc]
                best = (score, symbol)
    return best[1] if best else None


def scale_from_chords(chords: Sequence[Sequence[int]]) -> List[int]:
    """
    The pitch classes a piece actually uses.

    Passing tones need to know what counts as diatonic, and an imported or
    hand-typed progression has no declared key. Collecting what the music
    already sounds is a better answer than guessing a key and being wrong:
    ornaments then move through notes the piece has established.
    """
    used: Dict[int, int] = {}
    for chord in chords:
        for pitch in chord:
            pc = pitch % 12
            used[pc] = used.get(pc, 0) + 1
    return sorted(used)


# ---------------------------------------------------------------------------
# Reading a single line
# ---------------------------------------------------------------------------

def read_melody(path: str):
    """
    Read a score as one melodic line, for the harmoniser.

    Where :func:`read_musicxml` looks for chords, this keeps the top note of
    every moment and the rhythm it is written in. A melody to harmonise is
    usually written as a single line anyway; taking the top note means a
    score that happens to carry more than one still yields the tune.
    """
    from .harmonize import Melody, MelodyBar, MelodyNote

    root = _load_root(path)
    divisions = 1.0
    beats, beat_type = 4, 4
    fifths = 0

    bars: List = []
    notes: List = []

    for bar_index, measure in enumerate(root.iter("measure")):
        attributes = measure.find("attributes")
        if attributes is not None:
            node = attributes.find("divisions")
            if node is not None:
                divisions = float(_text(node, "1") or 1)
            time_node = attributes.find("time")
            if time_node is not None:
                beats = int(_text(time_node.find("beats"), "4") or 4)
                beat_type = int(_text(time_node.find("beat-type"), "4") or 4)
            key_node = attributes.find("key")
            if key_node is not None:
                fifths = int(_text(key_node.find("fifths"), "0") or 0)

        tonic, mode_key = key_from_fifths(fifths)
        bars.append(MelodyBar(beats=beats, beat_type=beat_type,
                              tonic=tonic, mode_key=mode_key))

        cursor = 0.0
        previous = 0.0
        highest: Dict[float, int] = {}
        lengths: Dict[float, float] = {}
        for element in measure:
            if element.tag == "backup":
                cursor -= float(_text(element.find("duration"), "0") or 0) / divisions
                previous = 0.0
                continue
            if element.tag == "forward":
                cursor += float(_text(element.find("duration"), "0") or 0) / divisions
                previous = 0.0
                continue
            if element.tag != "note":
                continue

            duration = float(_text(element.find("duration"), "0") or 0) / divisions
            if element.find("chord") is not None:
                cursor -= previous
            pitch_node = element.find("pitch")
            if element.find("rest") is None and pitch_node is not None:
                midi = _pitch_to_midi(pitch_node)
                if midi is not None:
                    # The top note of the moment is the melody.
                    if cursor not in highest or midi > highest[cursor]:
                        highest[cursor] = midi
                        lengths[cursor] = duration
            cursor += duration
            previous = duration

        for offset in sorted(highest):
            notes.append(MelodyNote(
                pitch=highest[offset],
                duration_quarters=lengths.get(offset, 1.0) or 1.0,
                bar_index=bar_index,
                offset_quarters=offset,
            ))

    if not notes:
        raise ImportError_("La partitura no tiene notas que leer.")
    return Melody(notes=notes, bars=bars or [MelodyBar()])


#: Major keys by their signature, as a count of sharps (positive) or flats.
_KEY_TONICS = {0: 0, 1: 7, 2: 2, 3: 9, 4: 4, 5: 11, 6: 6, 7: 1,
               -1: 5, -2: 10, -3: 3, -4: 8, -5: 1, -6: 6, -7: 11}


def key_from_fifths(fifths: int, minor: bool = False):
    """Turn a key signature into a tonic and a mode."""
    tonic = _KEY_TONICS.get(max(-7, min(7, fifths)), 0)
    if minor:
        return (tonic + 9) % 12, "minor"
    return tonic, "major"


# ---------------------------------------------------------------------------
# Reading every voice, for the analyser
# ---------------------------------------------------------------------------

#: Cómo se llaman las voces según cuántas haya, de grave a aguda. El
#: analizador habla de ellas todo el tiempo --- "el tenor y el alto hacen
#: quintas" --- y "voz 2 y voz 3" no dice nada. Más de seis y se numeran: a
#: esa altura ya no es un coro y ponerle nombres de coro sería inventar.
VOICE_LADDERS = {
    2: ("Bajo", "Soprano"),
    3: ("Bajo", "Alto", "Soprano"),
    4: ("Bajo", "Tenor", "Alto", "Soprano"),
    5: ("Bajo", "Tenor", "Alto", "Mezzo", "Soprano"),
    6: ("Bajo", "Barítono", "Tenor", "Alto", "Mezzo", "Soprano"),
}


def voice_names(count: int) -> List[str]:
    ladder = VOICE_LADDERS.get(count)
    if ladder:
        return list(ladder)
    return [f"Voz {n + 1}" for n in range(count)]


def read_voices(path: str):
    """
    Leer una partitura conservando cada voz por separado.

    Donde :func:`read_musicxml` junta todo lo que suena a la vez en un
    acorde, acá hace falta lo contrario: el análisis contrapuntístico
    pregunta qué hace **cada voz** entre un acorde y el siguiente, y eso se
    pierde en cuanto las notas se apilan.

    Una voz es un par (parte, número de voz): un coral escrito en dos
    pentagramas con dos voces cada uno tiene cuatro, igual que uno escrito
    en cuatro partes. Cuando dentro de una voz aparece un acorde escrito
    --- varias notas marcadas como simultáneas --- se lo reparte en tantas
    líneas como notas tenga, porque para el contrapunto eso es lo que es:
    varias voces anotadas juntas.

    Las ligaduras de prolongación se unen en una sola nota: una blanca
    ligada a otra es una nota de dos blancas, y contarla dos veces
    inventaría un ataque donde no lo hay.
    """
    from . import analysis

    root = _load_root(path)
    title = _text(root.find(".//work/work-title")) or _text(
        root.find(".//movement-title"))

    beats, beat_type, fifths = 4, 4, 0
    read_signature = False
    #: (parte, voz, altura dentro del acorde) -> lista de notas
    lines: Dict[Tuple[int, str, int], List] = {}
    #: Dónde arranca cada compás en la línea de tiempo de la pieza. Lo
    #: calcula la primera parte y las demás lo reusan: si cada parte llevara
    #: su propio reloj, un compás mal cerrado correría a esa parte respecto
    #: de las otras desde ahí hasta el final.
    bar_starts: List[float] = []
    #: Cuánto dura de verdad cada compás leído y a qué compás de la pieza
    #: pertenece. Ver :func:`_plan_bars`.
    lengths, metre_from, odd_metres = _plan_bars(root)
    pickup = 0.0
    #: Los cambios de compás, por número de compás en la pieza (el que le
    #: pone `_plan_bars`, no el orden en el archivo). Una pieza puede
    #: cambiar de compás en el medio, y forzarla al primero corre todas las
    #: barras que vienen después --- y con ellas los tiempos fuertes, que es
    #: de donde sale la lectura de acordes.
    metre_changes: Dict[int, Tuple[int, int]] = {}

    for part_index, part in enumerate(root.iter("part")):
        cursor = 0.0
        divisions = 1.0
        local_beats, local_beat_type = beats, beat_type
        for bar_index, measure in enumerate(part.iter("measure")):
            attributes = measure.find("attributes")
            if attributes is not None:
                node = attributes.find("divisions")
                if node is not None:
                    divisions = float(_text(node, "1") or 1)
                time_node = attributes.find("time")
                if time_node is not None:
                    local_beats = int(_text(time_node.find("beats"), "4") or 4)
                    local_beat_type = int(
                        _text(time_node.find("beat-type"), "4") or 4)
                    if part_index == 0 and bar_index < len(metre_from):
                        metre_changes[metre_from[bar_index]] = (
                            local_beats, local_beat_type)
                    if not read_signature:
                        beats, beat_type = local_beats, local_beat_type
                key_node = attributes.find("key")
                if key_node is not None and not read_signature:
                    fifths = int(_text(key_node.find("fifths"), "0") or 0)
                    read_signature = True

            per_bar = local_beats * 4.0 / local_beat_type
            if part_index == 0 and bar_index >= len(bar_starts):
                bar_starts.append(cursor)
            if bar_index < len(bar_starts):
                cursor = bar_starts[bar_index]

            start_of_bar = cursor
            previous = 0.0
            #: Cuántas notas lleva el acorde que se está escribiendo, para
            #: saber a qué línea va la siguiente.
            chord_depth = 0

            for element in measure:
                if element.tag == "backup":
                    cursor -= float(
                        _text(element.find("duration"), "0") or 0) / divisions
                    previous = 0.0
                    chord_depth = 0
                    continue
                if element.tag == "forward":
                    cursor += float(
                        _text(element.find("duration"), "0") or 0) / divisions
                    previous = 0.0
                    chord_depth = 0
                    continue
                if element.tag != "note":
                    continue

                duration = float(
                    _text(element.find("duration"), "0") or 0) / divisions
                voice = _text(element.find("voice"), "1") or "1"
                if element.find("chord") is not None:
                    cursor -= previous
                    chord_depth += 1
                else:
                    chord_depth = 0

                pitch_node = element.find("pitch")
                if element.find("rest") is None and pitch_node is not None:
                    midi = _pitch_to_midi(pitch_node)
                    if midi is not None:
                        key = (part_index, voice, chord_depth)
                        notes = lines.setdefault(key, [])
                        if _continues_a_tie(element) and notes:
                            # Ligada a la anterior: se estira aquélla en vez
                            # de empezar una nota nueva.
                            notes[-1].duration = (cursor + duration
                                                  - notes[-1].onset)
                        else:
                            notes.append(analysis.Note(
                                pitch=midi, onset=cursor, duration=duration))
                cursor += duration
                previous = duration

            if part_index == 0:
                length = (lengths[bar_index] if bar_index < len(lengths)
                          else None)
                if (bar_index == 0 and length is not None
                        and 0 < length < per_bar - 1e-6):
                    # Primer compás incompleto: es una anacrusa, y de ahí
                    # sale la grilla de tiempos fuertes de toda la pieza.
                    pickup = length
                    cursor = start_of_bar + length
                elif length is not None:
                    cursor = start_of_bar + length
                else:
                    cursor = start_of_bar + per_bar
                if bar_index + 1 >= len(bar_starts):
                    bar_starts.append(cursor)

    if not lines:
        raise ImportError_("La partitura no tiene notas que leer.")

    parts = []
    for key in sorted(lines):
        notes = sorted(lines[key], key=lambda n: n.onset)
        if notes:
            parts.append(analysis.Part(name="", notes=notes))
    parts.sort(key=lambda p: p.mean_pitch())
    for name, part in zip(voice_names(len(parts)), parts):
        part.name = name

    # Los compases ya vienen numerados como en la partitura (`_plan_bars`):
    # el de la anacrusa es el 0 y el primer compás completo es el 1. Un
    # compás suelto más corto que el resto entra como un compás propio con
    # su medida, y el que le sigue vuelve a la de antes salvo que el archivo
    # diga otra cosa.
    forced, restored = odd_metres
    for number, metre in restored.items():
        metre_changes.setdefault(number, metre)
    metre_changes.update(forced)
    metres = tuple(sorted((number, count, figure)
                          for number, (count, figure) in metre_changes.items()
                          if number >= 1))
    return analysis.Score(parts=parts, fifths=fifths, beats=beats,
                          beat_type=beat_type, title=title,
                          pickup_quarters=pickup, metres=metres)


def _measure_reach(measure: ET.Element, divisions: float) -> float:
    """Hasta dónde llega lo escrito en un compás, en negras desde su comienzo.

    Se recorre igual que al leer las notas ---los <backup> y <forward>
    mueven el cursor---, y se queda con el punto más lejano: un compás
    escrito a dos voces vuelve atrás para escribir la segunda, y lo que
    mide es la más larga.
    """
    cursor = reach = previous = 0.0
    for element in measure:
        if element.tag in ("backup", "forward"):
            step = float(_text(element.find("duration"), "0") or 0) / divisions
            cursor += -step if element.tag == "backup" else step
            previous = 0.0
        elif element.tag == "note":
            duration = float(_text(element.find("duration"), "0") or 0) / divisions
            if element.find("chord") is not None:
                cursor -= previous
            cursor += duration
            previous = duration
        else:
            continue
        reach = max(reach, cursor)
    return reach


def _metre_for(quarters: float, beat_type: int) -> Optional[Tuple[int, int]]:
    """La medida que escribe un compás de esa duración: (tiempos, figura)."""
    for figure in (beat_type, 8, 16, 32):
        count = quarters * figure / 4.0
        if count >= 1 - 1e-6 and abs(count - round(count)) <= 1e-6:
            return int(round(count)), figure
    return None


def _plan_bars(root: ET.Element):
    """
    Cuánto dura cada compás del archivo y con qué número se lo cita.

    Un compás se mide por lo que **todas** las partes escriben en él, no por
    el compás que rige. Casi siempre es lo mismo, pero no siempre: un coral
    con la repetición en medio de un compás lo escribe partido en dos ---el
    7 de dos tiempos y el 7a del tercero---, y estirando cada mitad hasta un
    compás entero aparecían tres tiempos de silencio que la pieza no tiene.
    Todo lo que venía después quedaba corrido: los acordes caían a
    contratiempo, las cadencias en el compás equivocado, y la mitad del
    análisis de un coral salía mal.

    Tres casos, y en ninguno se toca la grilla de tiempos fuertes:

    * el primer compás incompleto es la **anacrusa**, como siempre;
    * dos compases cortos seguidos que juntos hacen uno entero son **las
      dos mitades** de ese compás: suenan pegadas y llevan el mismo número;
    * un compás corto suelto en el medio ---la anacrusa de una sección que
      cambia de compás--- es **un compás con su propia medida**, y el
      siguiente vuelve a la de antes.

    El último compás, si está incompleto, se deja como estaba: completa la
    anacrusa y después no viene nada que pueda correrse.

    Devuelve tres cosas: la duración de cada compás leído, el número de
    compás de la pieza desde el que rige un cambio de compás escrito en él,
    y los cambios de medida que agregan los compases sueltos ---(los que se
    imponen, los que se ponen si el archivo no dice otro)---.
    """
    nominal: List[float] = []
    metres_at: List[Tuple[int, int]] = []
    reach: List[float] = []
    for part_index, part in enumerate(root.iter("part")):
        divisions = 1.0
        beats, beat_type = 4, 4
        for index, measure in enumerate(part.iter("measure")):
            attributes = measure.find("attributes")
            if attributes is not None:
                node = attributes.find("divisions")
                if node is not None:
                    divisions = float(_text(node, "1") or 1)
                time_node = attributes.find("time")
                if time_node is not None:
                    beats = int(_text(time_node.find("beats"), "4") or 4)
                    beat_type = int(_text(time_node.find("beat-type"), "4") or 4)
            if part_index == 0:
                nominal.append(beats * 4.0 / beat_type)
                metres_at.append((beats, beat_type))
            while len(reach) <= index:
                reach.append(0.0)
            reach[index] = max(reach[index], _measure_reach(measure, divisions))

    count = len(nominal)
    lengths = list(nominal)
    short = [0.0 < reach[i] < nominal[i] - 1e-6 for i in range(count)]
    joined = [False] * count
    odd: Dict[int, Tuple[int, int]] = {}
    index = 0
    while index < count:
        if not short[index]:
            index += 1
            continue
        lengths[index] = reach[index]
        following = index + 1
        if index == 0:
            index += 1                          # la anacrusa
            continue
        # Las dos mitades suman el compás de la primera. La segunda puede
        # traer ya el compás que sigue: en BWV 41.6 el 14 tiene tres tiempos
        # de cuatro por cuatro y el 14a es la anacrusa de la sección en tres.
        if (following < count and short[following]
                and abs(reach[index] + reach[following]
                        - nominal[index]) <= 1e-6):
            lengths[following] = reach[following]
            joined[following] = True
            index += 2
            continue
        metre = _metre_for(reach[index], metres_at[index][1])
        if following >= count or metre is None:
            lengths[index] = nominal[index]     # el último, o una medida rara
        else:
            odd[index] = metre
        index += 1

    numbers: List[int] = []
    number = 0 if (count and short[0]) else 1
    for index in range(count):
        if index > 0 and not joined[index]:
            number += 1
        numbers.append(number)
    forced = {numbers[index]: metre for index, metre in odd.items()}
    restored = {numbers[index + 1]: metres_at[index + 1] for index in odd}
    # Un cambio de compás escrito en la segunda mitad de un compás partido
    # rige desde el compás siguiente: esa mitad todavía completa el de antes.
    starts = [numbers[index] + (1 if joined[index] else 0)
              for index in range(count)]
    return lengths, starts, (forced, restored)


def kept_voices(parts: Sequence, count: int) -> List:
    """
    Las voces que entran cuando la partitura tiene más de las que caben.

    Se eligen **momento a momento** y no línea por línea: en cada tramo entre
    dos ataques va al primer carril la nota más grave que suena, al último
    la más aguda, y a los del medio las que más clases de altura nuevas
    agregan. Antes quedaban las cuatro líneas más graves, y en una partitura
    de piano eso tiraba la melodía. Eligiendo líneas enteras tampoco
    alcanzaba: un acorde de piano se lee como una línea por nota y ninguna
    es el bajo todo el tiempo. Medido contra un análisis de referencia, el
    preludio de Chopin en do menor pasó de 37 % de acordes bien leídos a lo
    mismo que leyendo todas sus voces.

    Una nota que sigue sonando en el mismo carril sigue siendo la misma nota:
    partirla en cada tramo inventaba ataques que no están escritos, y de los
    ataques salen los adornos y el contrapunto.

    `parts` viene de grave a aguda; las voces que vuelven también.
    """
    from . import analysis
    parts = list(parts)
    if len(parts) <= count or count < 2:
        return parts[:max(1, count)] if count < 2 else parts
    notes = sorted((note for part in parts for note in part.notes),
                   key=lambda note: (note.onset, note.pitch))
    bounds = sorted({note.onset for note in notes}
                    | {note.onset + note.duration for note in notes})
    lanes: List[list] = [[] for _ in range(count)]
    held: List[Optional[Tuple[object, object]]] = [None] * count
    active: List = []
    position = 0
    for start, end in zip(bounds, bounds[1:]):
        if end - start < 1e-6:
            continue
        while position < len(notes) and notes[position].onset <= start + 1e-6:
            active.append(notes[position])
            position += 1
        active = [note for note in active
                  if note.onset + note.duration > start + 1e-6]
        sounding = sorted(active, key=lambda note: (note.pitch, note.onset))
        picks = _pick_lanes(sounding, count, held)
        for lane, note in enumerate(picks):
            current = held[lane]
            if note is None:
                held[lane] = None
                continue
            if current is not None and current[0] is note:
                written = current[1]
                written.duration = end - written.onset
                continue
            written = analysis.Note(pitch=note.pitch, onset=start,
                                    duration=end - start)
            lanes[lane].append(written)
            held[lane] = (note, written)
    kept = [analysis.Part(name=name, notes=lane)
            for name, lane in zip(voice_names(count), lanes)]
    return [part for part in kept if part.notes] or kept


def _pick_lanes(sounding: List, count: int,
                held: List[Optional[Tuple[object, object]]]) -> List:
    """Qué nota va a cada carril en un tramo. None es un silencio."""
    picks: List = [None] * count
    if not sounding:
        return picks
    previous = {id(entry[0]): lane for lane, entry in enumerate(held)
                if entry is not None}
    if len(sounding) == 1:
        note = sounding[0]
        lane = previous.get(id(note))
        if lane is None:
            lane = 0 if note.pitch < 60 else count - 1
        picks[lane] = note
        return picks
    bass, top = sounding[0], sounding[-1]
    picks[0], picks[-1] = bass, top
    inner = sounding[1:-1]
    room = count - 2
    if len(inner) > room:
        taken = {bass.pitch % 12, top.pitch % 12}
        chosen: List = []
        for _ in range(room):
            best = max(inner, key=lambda note: (
                note.pitch % 12 not in taken,
                id(note) in previous,
                -abs(note.pitch - (bass.pitch + top.pitch) / 2.0)))
            chosen.append(best)
            taken.add(best.pitch % 12)
            inner = [note for note in inner if note is not best]
        inner = sorted(chosen, key=lambda note: note.pitch)
    # Los del medio, en los carriles del medio de abajo hacia arriba; si
    # sobran carriles, el que queda vacío es el más cercano al bajo.
    for offset, note in enumerate(inner):
        picks[count - 1 - len(inner) + offset] = note
    return picks


def written_line(part) -> List[Tuple[Optional[int], float]]:
    """
    Una voz leída, escrita como se escribe: con sus silencios.

    :func:`read_voices` devuelve sólo las notas, cada una con el momento en
    que empieza. Un pentagrama, en cambio, escribe una cosa detrás de otra,
    así que los huecos entre notas tienen que existir como silencios o la
    voz se corre hacia adelante. Y una voz corrida contra las otras no es un
    detalle de dibujo: la armonía que se lee en cada tiempo pasa a ser otra.

    Devuelve pares (altura o None, duración), donde None es un silencio.
    """
    written: List[Tuple[Optional[int], float]] = []
    cursor = 0.0
    for note in part.notes:
        if note.onset > cursor + 1e-6:
            written.append((None, note.onset - cursor))
        written.append((note.pitch, note.duration))
        cursor = max(cursor, note.onset + note.duration)
    return written


def _continues_a_tie(note: ET.Element) -> bool:
    """Es esta nota la cola de una ligadura de prolongación."""
    for tie in note.findall("tie"):
        if tie.get("type") == "stop":
            return True
    for tied in note.findall("notations/tied"):
        if tied.get("type") == "stop":
            return True
    return False
