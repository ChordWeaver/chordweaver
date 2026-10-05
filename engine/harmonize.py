# -*- coding: utf-8 -*-
"""
Harmonising a melody someone else wrote.

The other two modes start from chords. This one starts from a line and works
out what could sit underneath it, which is a different problem: the melody is
fixed, and every chord has to accommodate a note that is already decided.

How it works
------------
Chords are placed on strong beats only -- that is where harmony is heard to
change -- and the note that falls there decides what fits. A chord is judged
by the role the melody note plays in it: the third is the most characteristic
place for a melody to sit, the fifth next, the root best at points of repose.
Sixths, sevenths and ninths are available when the user has asked for colour,
at lower priority.

The pass runs **backwards**, from the last chord to the first. Harmony is
heard as approach rather than departure: knowing that the next chord is a
point of rest is what tells you the current one wants to be a dominant, and
that information only exists if the end is decided first.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .harmony import (
    DOMINANT,
    GRAMMARS,
    MINOR_MODES,
    MODES,
    grammar_cost,
    Mode,
    ChordOption,
    borrowed_options,
    build_chord_pool,
    diatonic_options,
    function_of,
)
from .theory import FLAT_NAMES, LETTER_SEMITONES, SHARP_NAMES, parse_chord
from engine.i18n import tr, trf, trs

#: Melody notes shorter than this are never harmonised on their own.
MIN_DURATION = 0.5


# ---------------------------------------------------------------------------
# The melody
# ---------------------------------------------------------------------------

@dataclass
class MelodyNote:
    """One note of the given line."""

    pitch: int                       # MIDI; None would be a rest
    duration_quarters: float
    bar_index: int
    offset_quarters: float           # from the start of its bar
    is_rest: bool = False
    #: El usuario marcó esta nota: quiere un acorde debajo de ella, caiga
    #: donde caiga. Sin esto, el armonizador escribe sobre los tiempos
    #: fuertes y una nota en el medio del compás se escucha contra el acorde
    #: del tiempo anterior --- que casi siempre está bien, y a veces es
    #: justamente la nota que la persona quería sostener.
    must_harmonise: bool = False
    #: El pedido contrario: el usuario apagó el dorado que el programa había
    #: puesto acá. El lugar de acorde que caía sobre esta nota se saca y su
    #: duración se la queda un lugar vecino del **mismo compás**, así que el
    #: compás sigue sumando lo que dice su cifra.
    skip_harmonise: bool = False


@dataclass
class MelodyBar:
    """A bar of the melody, with its own metre and key."""

    beats: int = 4
    beat_type: int = 4
    tonic: int = 0                   # pitch class
    mode_key: str = "major"

    @property
    def quarters(self) -> float:
        return self.beats * 4.0 / self.beat_type

    @property
    def mode(self) -> Mode:
        return MODES.get(self.mode_key, MODES["major"])


@dataclass
class Melody:
    """A line to harmonise, plus the bars it runs through."""

    notes: List[MelodyNote] = field(default_factory=list)
    bars: List[MelodyBar] = field(default_factory=list)
    #: Which voice the user wrote, as an index into the voice list.
    melody_voice: int = 0

    def bar(self, index: int) -> MelodyBar:
        if 0 <= index < len(self.bars):
            return self.bars[index]
        return MelodyBar()

    def sounding_at(self, bar_index: int, offset: float) -> Optional[MelodyNote]:
        """The note sounding at a moment, if any."""
        for note in self.notes:
            if note.bar_index != bar_index or note.is_rest:
                continue
            if note.offset_quarters <= offset + 1e-6 < (
                    note.offset_quarters + note.duration_quarters):
                return note
        return None

    def next_after(self, bar_index: int, offset: float) -> Optional[MelodyNote]:
        """The next note to begin after a moment."""
        best = None
        for note in self.notes:
            if note.is_rest:
                continue
            position = (note.bar_index, note.offset_quarters)
            if position <= (bar_index, offset):
                continue
            if best is None or position < (best.bar_index, best.offset_quarters):
                best = note
        return best


def strong_beat_offsets(beats: int, beat_type: int) -> List[float]:
    """
    Where harmony is heard to change in a regular metre.

    Simple metres put a secondary accent halfway through when they have an
    even number of beats -- the third beat of a bar of four. Compound metres
    accent the start of each group of three, which is what makes 6/8 two
    beats rather than six.
    """
    quarters_per_beat = 4.0 / beat_type
    if beat_type == 8 and beats % 3 == 0 and beats >= 6:
        group = 3 * quarters_per_beat
        return [index * group for index in range(beats // 3)]
    total = beats * quarters_per_beat
    if beats % 2 == 0 and beats > 2:
        return [0.0, total / 2.0]
    return [0.0]


@dataclass
class HarmonySpot:
    """A strong beat waiting for a chord."""

    bar_index: int
    offset_quarters: float
    duration_quarters: float
    #: The melody note this chord has to accommodate, if there is one.
    note: Optional[MelodyNote] = None
    #: A chord the user pinned here, by roman numeral.
    forced_roman: str = ""
    #: La nota que este lugar tiene que sostener, cuando no se elige sino
    #: que viene dada: la marcó el usuario. `choose_note_for_spot` puede
    #: preferir la nota siguiente cuando entra mucho mejor en los acordes
    #: disponibles, y eso es exactamente lo que no se quiere acá --- se
    #: pidió un acorde para **esta** nota.
    required_note: Optional["MelodyNote"] = None
    #: Grados de la escala a los que queda limitado este lugar, cuando algo
    #: lo exige. Por grado y no por cifra romana porque la cifra cambia con
    #: el modo --- el quinto es "V" en mayor y "v" en menor --- y lo que se
    #: quiere fijar es la función, que no cambia.
    allowed_degrees: Tuple[int, ...] = ()
    #: La nota fuera de la escala que este lugar sostiene cuando sube (o, en
    #: jazz, baja) un semitono a la siguiente: el acorde de este lugar no se
    #: elige de la tonalidad sino de los que **apuntan a esa nota** --- su
    #: dominante, y en barroco y jazz también su séptimo grado. Ver
    #: :func:`pin_chromatic_approaches`.
    approach: Optional["ChromaticApproach"] = None
    #: La clase de altura adonde resuelve el acorde del lugar anterior,
    #: cuando ese acorde es una dominante aplicada forzada por una nota
    #: cromática. El acorde que tiene esa nota de fundamental se premia: un
    #: mi mayor debajo de un sol sostenido promete un la menor, y cumplir la
    #: promesa es lo que hace que el sol sostenido se escuche como sensible.
    resolution_pc: Optional[int] = None


def bar_events(melody: Melody,
               bar_index: int) -> List[Tuple[Optional[int], float]]:
    """
    One bar of the given line as ``(pitch, quarters)``, gaps filled.

    A ``None`` pitch is a rest. The events are padded to the bar length and
    trimmed if a note runs past it, because a measure whose durations do not
    add up is rejected by every notation program -- and the line the user
    drew is under no obligation to fill its bars exactly.

    This is what the exporter writes for the melody voice. The search never
    sees it: there the line is sampled one note per chord, which is the
    rhythm the counterpoint is judged on.
    """
    bar = melody.bar(bar_index)
    total = bar.quarters
    written = sorted(
        (note for note in melody.notes if note.bar_index == bar_index),
        key=lambda note: note.offset_quarters,
    )

    events: List[Tuple[Optional[int], float]] = []
    cursor = 0.0
    for note in written:
        if note.offset_quarters > cursor + 1e-6:
            events.append((None, note.offset_quarters - cursor))
            cursor = note.offset_quarters
        length = min(note.duration_quarters, total - cursor)
        if length <= 1e-6:
            continue
        events.append((None if note.is_rest else note.pitch, length))
        cursor += length
    if cursor < total - 1e-6:
        events.append((None, total - cursor))
    return events


def harmony_spots(melody: Melody) -> List[HarmonySpot]:
    """Every strong beat in the melody, in order."""
    spots: List[HarmonySpot] = []
    for bar_index, bar in enumerate(melody.bars):
        offsets = strong_beat_offsets(bar.beats, bar.beat_type)
        for position, offset in enumerate(offsets):
            end = (offsets[position + 1] if position + 1 < len(offsets)
                   else bar.quarters)
            spots.append(HarmonySpot(
                bar_index=bar_index,
                offset_quarters=offset,
                duration_quarters=end - offset,
            ))

    # A tune that ends on a weak beat still ends: leaving the final note
    # unharmonised means the cadence lands on whatever happened to fall on
    # the last strong beat, which is usually the note before the arrival.
    last = max((n for n in melody.notes if not n.is_rest),
               key=lambda n: (n.bar_index, n.offset_quarters), default=None)
    if last is not None and spots:
        final = spots[-1]
        already = (final.bar_index == last.bar_index
                   and abs(final.offset_quarters - last.offset_quarters) < 1e-6)
        # Y sólo si la nota cae DESPUÉS del último tiempo fuerte. Cuando el
        # último compás lleva una nota sola al principio --- una melodía que
        # cierra con una redonda, por ejemplo --- la nota cae antes, y este
        # bloque le restaba: el lugar de la mitad del compás quedaba de media
        # negra y se agregaba otro encima del que ya estaba en el uno. El
        # compás sumaba tres negras y media en un cuatro por cuatro, que es
        # una partitura que ningún editor acepta, y encima quedaban dos
        # acordes distintos escritos en el mismo lugar.
        after = (last.bar_index > final.bar_index
                 or (last.bar_index == final.bar_index
                     and last.offset_quarters > final.offset_quarters + 1e-6))
        gap = last.offset_quarters - final.offset_quarters
        if (not already and after and last.bar_index == final.bar_index
                and gap < MIN_DURATION - 1e-6):
            # La nota cae a menos de una corchea del último tiempo fuerte
            # ---una semicorchea en 2,25 de un cuatro por cuatro, que sólo
            # llega importada---. Estirar ese lugar a la duración mínima y
            # abrir otro desde la nota hasta la barra los superponía: el
            # compás sumaba cuatro negras y cuarto. `spot_for_note` ya sabe
            # qué hacer con un pedazo tan corto: corre el lugar entero hasta
            # la nota y le da lo de antes al lugar anterior del compás.
            spot_for_note(spots, last)
        elif not already and after:
            final.duration_quarters = max(MIN_DURATION, gap)
            # Hasta la barra y no hasta el final de la nota: lo que sobra del
            # último compás es del último acorde. Con la duración de la nota,
            # un último compás incompleto ---«re do» en un tres por cuatro---
            # sumaba de menos, y como la melodía se escribe completa hasta la
            # barra, en el MusicXML las otras voces entraban corridas.
            spots.append(HarmonySpot(
                bar_index=last.bar_index,
                offset_quarters=last.offset_quarters,
                duration_quarters=(melody.bar(last.bar_index).quarters
                                   - last.offset_quarters),
            ))

        # Y nada de acordes después de que la melodía terminó. Una línea que
        # no llena su último compás --- nueve negras en cuatro por cuatro,
        # por ejemplo --- dejaba tres tiempos vacíos que igual recibían su
        # acorde, así que la cadencia caía sobre el silencio: la última nota
        # se armonizaba con el anteúltimo acorde y la tónica final sonaba
        # sola, sin nadie escuchándola. Se corta ahí y el último acorde
        # vuelve a ser el de la última nota.
        end_bar, end_offset = last.bar_index, (last.offset_quarters
                                               + last.duration_quarters)
        trimmed = [spot for spot in spots
                   if (spot.bar_index, spot.offset_quarters)
                   < (end_bar, end_offset - 1e-6)]
        if trimmed and len(trimmed) < len(spots):
            # Lo que ocupaban los que se van se lo queda el que queda: el
            # acorde final se estira hasta la barra, así que el compás sigue
            # sumando lo que dice su cifra y la nota final se sostiene con
            # un acorde solo en vez de con tres.
            #
            # Pero sólo lo de **su** compás. Los compases enteros que
            # quedaron vacíos después de la melodía ---tres compases
            # escritos de cuatro--- no tienen acorde ni nota que escribir y
            # se caen de la partitura; sumándoselos al último, ése pasaba a
            # medir ocho negras en un cuatro por cuatro y el MusicXML salía
            # inválido.
            closing = trimmed[-1]
            closing.duration_quarters += sum(
                spot.duration_quarters for spot in spots[len(trimmed):]
                if spot.bar_index == closing.bar_index)
            spots = trimmed

        # La nota final lleva un acorde solo, aunque dure varios tiempos
        # fuertes. Partida en dos, la redonda del final recibía un IV y
        # después el I, la cadencia de verdad quedaba un lugar antes y la
        # pieza cerraba V, IV, I: un paso para atrás justo antes de llegar.
        anchor = next((spot for spot in spots
                       if spot.bar_index == last.bar_index
                       and abs(spot.offset_quarters
                               - last.offset_quarters) < 1e-6), None)
        held = {id(spot) for spot in spots
                if spot.bar_index == last.bar_index
                and spot.offset_quarters > last.offset_quarters + 1e-6}
        if anchor is not None and held:
            anchor.duration_quarters += sum(
                spot.duration_quarters for spot in spots if id(spot) in held)
            spots = [spot for spot in spots if id(spot) not in held]

    # Y las notas que el usuario marcó, al final: se les abre un lugar
    # propio si no cayó ninguno encima. Va después del recorte porque el
    # recorte reparte duraciones, y un lugar abierto antes se le habría
    # escapado a esa cuenta.
    for note in _sounding_notes(melody):
        if not note.must_harmonise:
            continue
        spot = spot_for_note(spots, note)
        if spot is not None:
            spot.required_note = note
    return spots


def drop_skipped_spots(
    melody: Melody,
    spots: List[HarmonySpot],
    settings: "HarmonisationSettings",
) -> List[HarmonySpot]:
    """
    Sacar los lugares cuyo acorde caía sobre una nota que el usuario apagó.

    El dorado del pentagrama es una respuesta del programa, y hasta acá era
    una respuesta que no se podía discutir: se podía pedir un acorde de más
    y nunca uno de menos. Apagar una nota saca su lugar, y lo que ese lugar
    ocupaba se lo queda un vecino **del mismo compás** --- el anterior si lo
    hay, si no el siguiente, que se estira hacia atrás. Repartirlo fuera del
    compás lo dejaría sumando de más, que es una partitura que ningún editor
    acepta.

    Un lugar que no tiene con quién repartir ---el único de su compás--- se
    queda: su nota sigue dorada, que es la manera honesta de decir que ahí
    el acorde no se puede sacar.
    """
    if not any(note.skip_harmonise for note in melody.notes):
        return spots
    kept: List[HarmonySpot] = []
    for index, spot in enumerate(spots):
        pool, extra = _spot_pool(melody, spot, settings)
        note = spot.required_note or choose_note_for_spot(
            melody, spot, pool + extra, settings.allow_colour)
        if (note is None or not note.skip_harmonise
                or spot.required_note is not None):
            kept.append(spot)
            continue
        earlier = kept[-1] if kept else None
        if earlier is not None and earlier.bar_index == spot.bar_index:
            earlier.duration_quarters += spot.duration_quarters
            continue
        later = next((s for s in spots[index + 1:]
                      if s.bar_index == spot.bar_index), None)
        if later is not None:
            later.duration_quarters += (later.offset_quarters
                                        - spot.offset_quarters)
            later.offset_quarters = spot.offset_quarters
            continue
        kept.append(spot)
    return kept or spots


def spot_for_note(spots: List[HarmonySpot],
                  note: MelodyNote) -> Optional[HarmonySpot]:
    """
    El lugar de acorde que cae sobre una nota, abriéndolo si no lo hay.

    Es la maniobra que hacía `pin_leading_tone` para su sensible y que ahora
    hacen las dos cosas que necesitan un acorde en un punto que el compás no
    eligió. El lugar que se parte se queda con lo que hay hasta la nota y el
    nuevo con **todo el resto**, no con la duración de la nota: los lugares
    reparten el compás entre ellos, así que dejar el sobrante sin dueño es
    escribir un compás que no suma --- y un compás que no suma lo rechaza
    cualquier editor de partituras.

    Devuelve None cuando la nota cae fuera de todo lugar, que es lo que pasa
    con lo que quedó después de que la melodía terminó.
    """
    here = next((spot for spot in spots
                 if spot.bar_index == note.bar_index
                 and abs(spot.offset_quarters
                         - note.offset_quarters) < 1e-6), None)
    if here is not None:
        return here

    covering = next(
        (spot for spot in spots
         if spot.bar_index == note.bar_index
         and spot.offset_quarters <= note.offset_quarters
         < spot.offset_quarters + spot.duration_quarters), None)
    if covering is None:
        return None
    end = covering.offset_quarters + covering.duration_quarters
    head = note.offset_quarters - covering.offset_quarters
    if head < MIN_DURATION:
        # El lugar de al lado quedaría más corto que cualquier acorde que
        # este programa escribe. Se lo corre entero en vez de partirlo, y lo
        # que quedaba antes de la nota se lo lleva el lugar anterior: correr
        # el lugar y no dárselo a nadie deja ese tiempo sin acorde, y un
        # compás al que le falta un pedazo lo rechaza cualquier editor de
        # partituras.
        position = spots.index(covering)
        earlier = spots[position - 1] if position else None
        if earlier is None or earlier.bar_index != covering.bar_index:
            # No hay a quién dárselo. El acorde entonces arranca un poco
            # antes que la nota, que es lo de menos: igual la sostiene.
            return covering
        earlier.duration_quarters += head
        covering.offset_quarters = note.offset_quarters
        covering.duration_quarters = end - note.offset_quarters
        return covering
    covering.duration_quarters = head
    fresh = HarmonySpot(
        bar_index=note.bar_index,
        offset_quarters=note.offset_quarters,
        duration_quarters=end - note.offset_quarters,
    )
    spots.insert(spots.index(covering) + 1, fresh)
    return fresh


# ---------------------------------------------------------------------------
# How well a melody note sits in a chord
# ---------------------------------------------------------------------------

#: Cost of each role the melody note can play. Lower is better.
#:
#: The third is where a melody most characteristically sits -- it is the note
#: that tells you whether the chord is major or minor, so hearing it on top
#: identifies the harmony. The fifth is neutral and safe. The root is plain
#: and works best where the music comes to rest.
ROLE_COST = {
    3: 0.0,      # minor third
    4: 0.0,      # major third
    7: 14.0,     # fifth
    0: 26.0,     # root
}

#: Colour tones, offered only when the user asked for colour.
COLOUR_COST = {
    9: 44.0,     # sixth
    10: 52.0,    # minor seventh
    11: 52.0,    # major seventh
    2: 58.0,     # ninth
}

#: The root is the natural place to land, so it is cheap at the ends.
ROOT_AT_REST = -22.0

#: A melody note that is in the chord at all beats one that is not, by a wide
#: margin: harmonising a passing note as though it were structural is the
#: main way this kind of thing goes wrong.
NOT_A_CHORD_TONE = 400.0


def note_fit(
    option: ChordOption,
    pitch: int,
    allow_colour: bool,
    at_rest: bool = False,
) -> float:
    """
    What it costs to harmonise this note with this chord.

    Returns a large number when the note is not in the chord at all, so such
    a pairing only survives when nothing else is available.
    """
    interval = (pitch - option.root_pc) % 12
    chord_intervals = {tone.semitones % 12 for tone in option.chord.tones}

    if interval in ROLE_COST and interval in chord_intervals:
        cost = ROLE_COST[interval]
        if interval == 0 and at_rest:
            cost += ROOT_AT_REST
        return cost

    if interval in chord_intervals:
        # A seventh that genuinely belongs to the chord is a normal place for
        # a melody, whether or not extra colour was asked for.
        return COLOUR_COST.get(interval, 60.0)

    if allow_colour and interval in COLOUR_COST:
        return COLOUR_COST[interval]

    return NOT_A_CHORD_TONE


def melodic_weight(cost: float) -> float:
    """
    Scale the melodic fit so it outweighs everything else.

    The whole question this mode answers is what chord holds the note the
    user wrote. Left on the same scale as the progression terms, a chord
    that reads well as harmony could win while leaving the melody note
    outside it -- which is how a Bdim turned up under an A.
    """
    return cost * 3.0


def choose_note_for_spot(
    melody: Melody,
    spot: HarmonySpot,
    options: Sequence[ChordOption],
    allow_colour: bool,
) -> Optional[MelodyNote]:
    """
    Decide which note this chord is really harmonising.

    The note on the beat is the obvious candidate, but it may be a suspension
    or an anacrusis -- a note that resolves into the harmony rather than
    stating it. When the following note fits the available chords markedly
    better, that one is taken as the real target.
    """
    on_beat = melody.sounding_at(spot.bar_index, spot.offset_quarters)
    following = melody.next_after(spot.bar_index, spot.offset_quarters)
    if on_beat is None:
        return following
    if following is None or not options:
        return on_beat

    def best_cost(note: MelodyNote) -> float:
        return min(note_fit(option, note.pitch, allow_colour)
                   for option in options)

    on_beat_cost = best_cost(on_beat)
    following_cost = best_cost(following)
    # Only defer to the next note when it is clearly better, and only when
    # it arrives soon enough to still belong to this chord.
    close_enough = (following.bar_index == spot.bar_index
                    and following.offset_quarters
                    < spot.offset_quarters + spot.duration_quarters)
    if close_enough and following_cost + 40.0 < on_beat_cost:
        return following
    return on_beat


# ---------------------------------------------------------------------------
# Choosing the chords
# ---------------------------------------------------------------------------

@dataclass
class HarmonisationSettings:
    """What the harmoniser is allowed to do."""

    genre_key: str = "chorale"
    allow_colour: bool = False
    #: Whether iv and bVII may be used.
    allow_borrowed: bool = True
    with_sevenths: bool = False
    #: Reward for a dominant standing before a point of repose. Applied when
    #: working backwards, which is the whole reason for going that way.
    dominant_before_rest: float = -70.0
    #: Cost of repeating the same chord on consecutive strong beats.
    #: Kept well below the cost of misplacing the melody: what note the
    #: melody has in the chord matters more than avoiding a repetition.
    repeat: float = 22.0
    #: How often iv is taken in place of IV, and of V.
    borrowed_iv_for_four: float = 0.30
    borrowed_iv_for_five: float = 0.10
    borrowed_flat_seven: float = 0.35


def _pool_for_bar(
    bar: MelodyBar,
    settings: HarmonisationSettings,
) -> List[ChordOption]:
    """The chords available in one bar's key."""
    # Los préstamos son del menor paralelo. En una tonalidad menor ya son
    # suyos: el iv y el VII estaban dos veces, y el VII con nombre de
    # préstamo.
    borrowed = (["iv", "bVII"] if settings.allow_borrowed
                and bar.mode.key not in MINOR_MODES else [])
    return build_chord_pool(bar.tonic, bar.mode, borrowed,
                            settings.with_sevenths)


#: Los grados que pueden sostener la sensible antes de la tonica.
#:
#: El quinto siempre: la sensible ES su tercera, y ese semitono subiendo a
#: la tonica es la cadencia entera. En jazz se agrega el septimo, que es el
#: mismo tritono sin la fundamental --- un Bm7b5 sobre un si es lo que ese
#: idioma escribe donde el coral escribe un sol.
LEADING_TONE_DEGREES = (5,)
LEADING_TONE_DEGREES_JAZZ = (5, 7)


def _sounding_notes(melody: Melody) -> List[MelodyNote]:
    """Las notas de verdad, en orden y sin los silencios."""
    return sorted((n for n in melody.notes if not n.is_rest),
                  key=lambda n: (n.bar_index, n.offset_quarters))


def pin_leading_tone(
    melody: Melody,
    spots: List[HarmonySpot],
    settings: HarmonisationSettings,
) -> None:
    """
    Si la anteultima nota es la sensible, ponerle su dominante debajo.

    Una melodia que sube por la sensible a la tonica esta pidiendo una
    cadencia y no otra cosa; armonizarla con cualquier acorde que contenga
    esa nota --- el septimo en primera inversion, un iii --- deja la pieza
    cerrando sin haber cerrado. Y si en ese punto no caia ningun acorde,
    directamente no habia cadencia: la dominante se escuchaba un tiempo
    antes, sobre otra nota, y la sensible pasaba como si fuera de adorno.
    Aca se le abre un lugar propio, con la duracion de la nota.

    No hace nada cuando el modo no tiene sensible --- el menor natural la
    tiene rebajada, y su quinto grado es menor --- porque ahi el acorde que
    se forzaria no contiene la nota que vino a sostener.
    """
    notes = _sounding_notes(melody)
    if len(notes) < 2 or not spots:
        return
    penultimate = notes[-2]
    if penultimate.skip_harmonise:
        return          # el usuario apagó justamente esa nota
    bar = melody.bar(penultimate.bar_index)
    if penultimate.pitch % 12 != (bar.tonic - 1) % 12:
        return

    degrees = (LEADING_TONE_DEGREES_JAZZ if settings.genre_key == "jazz"
               else LEADING_TONE_DEGREES)
    # Sólo sirve si el acorde que se va a exigir contiene la nota. En el
    # menor natural no la contiene ninguno, y forzarlo igual pondria la
    # sensible como nota extraña encima de su propio acorde.
    pool = _pool_for_bar(bar, settings)
    usable = tuple(
        degree for degree in degrees
        if any(option.scale_degree == degree
               and penultimate.pitch % 12 in {
                   option.chord.pitch_class_of(t) for t in option.chord.tones}
               for option in pool)
    )
    if not usable:
        return

    # Si no caia ningun acorde sobre la sensible, se le abre uno partiendo
    # el que la cubria: la misma maniobra que necesita una nota marcada por
    # el usuario, y por eso vive en `spot_for_note`.
    here = spot_for_note(spots, penultimate)
    if here is not None:
        here.allowed_degrees = usable


# ---------------------------------------------------------------------------
# Las notas fuera de la escala
# ---------------------------------------------------------------------------

def key_of_ending(last_pitch: Optional[int], tonic: int) -> Tuple[int, str]:
    """
    La tonalidad de una melodía dentro de su armadura, por la nota final.

    Una armadura sirve para dos tonalidades y el Armonizador elegía siempre
    la mayor. Una melodía en La menor se armonizaba en Do, y su sol
    sostenido salía como un la bemol con un Reb o un Fa menor debajo. Casi
    toda melodía que termina lo hace en su tónica, así que si termina en la
    relativa menor, es menor.

    El menor es el natural, que tiene la escala de la armadura. Así lo que
    el pentagrama pinta de naranja es lo mismo que el armonizador trata como
    cromático, y el sol sostenido que sube a la recibe su dominante por la
    regla de la nota cromática.
    """
    relative = (tonic + 9) % 12
    if last_pitch is not None and last_pitch % 12 == relative:
        return relative, "minor"
    return tonic, "major"


def out_of_scale(pitch: int, bar: MelodyBar) -> bool:
    """¿Esta altura cae fuera de la escala del compás?"""
    return pitch % 12 not in bar.mode.pitch_classes(bar.tonic)


#: Los estilos donde la nota cromática que sube un semitono puede llevar,
#: además de su dominante, el séptimo grado de la nota a la que va: el
#: G#dim debajo de un sol sostenido que sube a la. Es el mismo trítono que el
#: Mi mayor sin la fundamental, y es vocabulario barroco y de jazz; en el
#: coral y en el gregoriano se queda la dominante sola.
LEADING_APPROACH_GENRES = ("classical", "jazz")

#: Con qué probabilidad sale el séptimo grado en vez de la dominante, donde
#: se lo permite. Menos de la mitad a propósito: la dominante es la
#: respuesta de manual y el séptimo grado un color que aparece de a ratos.
LEADING_APPROACH_CHANCE = 0.3

#: Los estilos donde la nota cromática que **baja** un semitono también
#: pide un acorde propio. Sólo el jazz tiene uno que la contenga y apunte a
#: la nota siguiente: la sustitución tritonal (subV7), cuya fundamental es
#: justamente la nota que baja. En los demás estilos ninguna dominante de la
#: nota de llegada contiene un semitono por encima de ella, así que la nota
#: se armoniza con las reglas de siempre.
TRITONE_APPROACH_GENRES = ("jazz",)

#: Premio para el acorde que tiene de fundamental la nota a la que resuelve
#: una dominante aplicada forzada. Tiene que ganarle a la diferencia de
#: lugar en el acorde --- la nota de llegada es su fundamental, que cuesta
#: más que la tercera de cualquier otro --- y además a la ventana de azar de
#: `harmonise`. Con -140 la diferencia quedaba adentro de esa ventana y un
#: Mi mayor debajo de un sol sostenido resolvía en Fa una de cada tres.
RESOLUTION_REWARD = -190.0

#: Costo de una dominante aplicada elegida para sostener una nota cromática
#: ---no la de la regla, que es forzada--- cuando el acorde siguiente no es
#: aquél al que apunta. La gramática del estilo ya lo cobra, pero se lleva
#: un sexto de lo que pesa la melodía, y un Si mayor que salta a un Fa
#: ganaba de taquito sobre un La bemol mayor: la tercera le gana a la
#: quinta. Una dominante que no resuelve no es un color sino una promesa
#: rota, y para una nota cromática casi siempre hay un préstamo que la
#: sostiene sin prometer nada.
UNRESOLVED_APPLIED = 90.0

#: Castigo para un acorde que deja afuera a una nota cromática que le toca
#: sostener. Con el color prendido, un acorde de la tonalidad podía tomar la
#: nota cromática como sexta o novena y ganarle a uno que la tiene adentro:
#: la nota fuera de la escala sonaba como adorno de un acorde que la ignora,
#: que es exactamente lo contrario de lo que se pidió.
CHROMATIC_OUTSIDE = 150.0

#: Lo que se le cobra a una dominante aplicada en el gregoriano: el modal no
#: tiene función de dominante, y la mezcla de modos es su manera de alterar
#: una nota. Sólo pesa cuando hay un préstamo que también la sostiene.
APPLIED_IN_MODAL = 60.0


@dataclass(frozen=True)
class ChromaticApproach:
    """Una nota fuera de la escala que va por semitono a la siguiente."""

    note: MelodyNote
    target: MelodyNote
    #: True si sube a la nota siguiente (es su sensible); False si baja.
    rising: bool

    @property
    def target_pc(self) -> int:
        return self.target.pitch % 12


def chromatic_approach(melody: Melody, note: MelodyNote,
                       genre_key: str) -> Optional[ChromaticApproach]:
    """
    Si esta nota cumple la regla de la nota cromática, cómo la cumple.

    La regla: una nota fuera de la escala que **sube un semitono** a la
    siguiente es la sensible de esa nota, y lleva debajo su dominante. Y en
    jazz, la que **baja un semitono** lleva la sustitución tritonal de la
    dominante de la nota de llegada. Se mide en alturas reales y no en
    clases de altura: un sol sostenido que salta una séptima abajo a un la
    no es una sensible resolviendo, es un salto.
    """
    if note.is_rest or note.skip_harmonise:
        return None
    if note.duration_quarters < MIN_DURATION - 1e-6:
        # Una semicorchea cromática es una nota de paso y no pide acorde.
        # En el pentagrama del Armonizador no se puede escribir ninguna;
        # llega importada, y abrirle un acorde propio partía el compás en
        # pedazos más cortos que cualquier acorde que este programa escribe.
        return None
    if not out_of_scale(note.pitch, melody.bar(note.bar_index)):
        return None
    following = melody.next_after(note.bar_index, note.offset_quarters)
    if following is None:
        return None
    step = following.pitch - note.pitch
    if step == 1:
        return ChromaticApproach(note, following, True)
    if step == -1 and genre_key in TRITONE_APPROACH_GENRES:
        return ChromaticApproach(note, following, False)
    return None


def chromatic_approaches(melody: Melody,
                         genre_key: str) -> List[ChromaticApproach]:
    """Todas las notas de la melodía que cumplen la regla, en orden."""
    found: List[ChromaticApproach] = []
    for note in _sounding_notes(melody):
        approach = chromatic_approach(melody, note, genre_key)
        if approach is not None:
            found.append(approach)
    return found


#: Intervalos de cada calidad que se arma acá, para elegir cómo se escribe
#: la fundamental.
_QUALITY_INTERVALS = {
    "": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10),
    "dim": (0, 3, 6), "dim7": (0, 3, 6, 9),
}
#: Cuántas letras arriba de la fundamental se escribe cada intervalo.
_INTERVAL_LETTERS = {0: 0, 3: 2, 4: 2, 6: 4, 7: 4, 9: 6, 10: 6}
_LETTER_ORDER = "CDEFGAB"


def _spelling_cost(name: str, root_pc: int, intervals: Sequence[int]) -> int:
    """Cuántas alteraciones lleva un acorde escrito desde esa fundamental."""
    start = _LETTER_ORDER.index(name[0])
    cost = 0
    for interval in intervals:
        letter = _LETTER_ORDER[(start + _INTERVAL_LETTERS[interval]) % 7]
        alteration = ((root_pc + interval - LETTER_SEMITONES[letter] + 6)
                      % 12) - 6
        # Un doble sostenido o un doble bemol cuenta mucho más: un la
        # sostenido mayor con do doble sostenido es el mismo sonido que un
        # si bemol mayor y nadie lo escribe así.
        cost += abs(alteration) + (3 if abs(alteration) > 1 else 0)
    return cost


def _root_name(root_pc: int, quality: str, prefer_flats: bool) -> str:
    """
    El nombre de la fundamental que escribe el acorde con menos alteraciones.

    Con `SHARP_NAMES` solo, la dominante de un mi bemol salía la sostenido
    mayor, con do doble sostenido de tercera. Se prueban los dos nombres y
    gana el que altera menos notas; el empate lo decide el acorde: las
    dominantes suben a su nota y se escriben con sostenidos, la sustitución
    tritonal baja y se escribe con bemoles.
    """
    intervals = _QUALITY_INTERVALS[quality]
    sharp, flat = SHARP_NAMES[root_pc], FLAT_NAMES[root_pc]
    sharp_cost = _spelling_cost(sharp, root_pc, intervals)
    flat_cost = _spelling_cost(flat, root_pc, intervals)
    # Una alteración de ventaja para el lado preferido, y el empate también
    # es suyo: el Gb7 que baja a fa lleva cuatro bemoles y el F#7 tres
    # sostenidos, y el que se escribe es el Gb7.
    if prefer_flats:
        return flat if flat_cost - 1 <= sharp_cost else sharp
    return sharp if sharp_cost - 1 <= flat_cost else flat


_PLAIN_ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII")


def degree_roman(pc: int, bar: MelodyBar) -> str:
    """
    El nombre romano de la nota a la que apunta un acorde aplicado.

    Para una nota de la escala es la cifra de su tríada ---"vi", "ii"---,
    que es como se escribe un V/vi. Para una nota fuera de la escala, el
    grado de abajo con sostenido y, si no lo hay, el de arriba con bemol.
    """
    scale = bar.mode.pitch_classes(bar.tonic)
    pc %= 12
    if pc in scale:
        degree = scale.index(pc)
        return diatonic_options(bar.tonic, bar.mode)[degree].roman
    for degree, member in enumerate(scale):
        if (member + 1) % 12 == pc:
            return "#" + _PLAIN_ROMAN[degree]
    # La segunda aumentada de la menor armónica deja dos notas entre el
    # sexto y la sensible, y la de arriba ---el sol natural en La menor--- no
    # es un semitono arriba de ningún grado: salía «V/?». Es la séptima
    # natural, un semitono abajo de la sensible, y así la escribe el resto
    # del programa: bVII, el mismo nombre que tiene como préstamo.
    for degree, member in enumerate(scale):
        if (member - 1) % 12 == pc:
            return "b" + _PLAIN_ROMAN[degree]
    return "?"


def _made_option(root_pc: int, quality: str, roman: str,
                 prefer_flats: bool = False,
                 scale_degree: int = 0) -> ChordOption:
    """Un acorde fuera de la tonalidad, escrito con su nombre de verdad."""
    chord = parse_chord(_root_name(root_pc, quality, prefer_flats) + quality)
    return ChordOption(
        chord=chord, label=chord.symbol, roman=roman,
        scale_degree=scale_degree, root_pc=root_pc,
        # Viajan como los préstamos porque no son de la tonalidad, igual que
        # las dominantes aplicadas del Generador.
        is_borrowed=scale_degree == 0,
    )


def applied_dominant(target_pc: int, bar: MelodyBar,
                     with_seventh: bool) -> ChordOption:
    """
    La dominante de una nota: el acorde mayor una quinta arriba de ella.

    Cuando la nota es la tónica no es una dominante aplicada sino **el**
    quinto grado ---el V del menor armónico, por ejemplo--- y se nombra y se
    archiva así, para que la cadencia lo reconozca.
    """
    root = (target_pc + 7) % 12
    quality = "7" if with_seventh else ""
    if target_pc % 12 == bar.tonic % 12:
        return _made_option(root, quality, "V", scale_degree=5)
    return _made_option(root, quality,
                        "V/" + degree_roman(target_pc, bar))


def applied_leading(target_pc: int, bar: MelodyBar,
                    with_seventh: bool) -> ChordOption:
    """El séptimo grado de una nota: el disminuido sobre su sensible."""
    root = (target_pc - 1) % 12
    quality = "dim7" if with_seventh else "dim"
    numeral = "vii°7" if with_seventh else "vii°"
    if target_pc % 12 == bar.tonic % 12:
        return _made_option(root, quality, numeral)
    return _made_option(root, quality,
                        numeral + "/" + degree_roman(target_pc, bar))


def tritone_substitute(target_pc: int, bar: MelodyBar) -> ChordOption:
    """La sustitución tritonal de la dominante de una nota: un semitono arriba."""
    root = (target_pc + 1) % 12
    roman = ("subV" if target_pc % 12 == bar.tonic % 12
             else "subV/" + degree_roman(target_pc, bar))
    return _made_option(root, "7", roman, prefer_flats=True)


def approach_options(
    approach: ChromaticApproach,
    bar: MelodyBar,
    settings: "HarmonisationSettings",
    picker: Optional[random.Random] = None,
) -> List[ChordOption]:
    """
    Los acordes que pueden ir debajo de una nota que cumple la regla.

    Subiendo, la dominante de la nota siguiente ---con séptima donde el
    estilo las usa--- y, en barroco y jazz, su séptimo grado, que sale con
    menos probabilidad. Sin `picker` se devuelven todos: es la pregunta de
    la vista previa, que no elige acorde. Bajando (sólo en jazz), la
    sustitución tritonal.
    """
    target = approach.target_pc
    if not approach.rising:
        return [tritone_substitute(target, bar)]
    dominant = [applied_dominant(target, bar, settings.with_sevenths)]
    leading: List[ChordOption] = []
    if settings.genre_key in LEADING_APPROACH_GENRES:
        leading.append(applied_leading(
            target, bar,
            settings.with_sevenths and settings.genre_key == "jazz"))
    if picker is None:
        return dominant + leading
    if leading and picker.random() < LEADING_APPROACH_CHANCE:
        return leading
    return dominant


#: Los préstamos que se ofrecen para sostener una nota cromática. Son todos
#: los del catálogo menos los que tienen dueño: la sexta napolitana es un
#: giro del barroco y la sustitución tritonal del jazz.
_CHROMATIC_BORROWED = ("iv", "v", "bII", "bIII", "bVI", "bVII", "iiø")


def chromatic_options(pc: int, bar: MelodyBar,
                      settings: "HarmonisationSettings") -> List[ChordOption]:
    """
    Los acordes fuera de la tonalidad que tienen adentro esta nota.

    Es lo que el motor ya sabe escribir: las dominantes aplicadas de cada
    grado, los préstamos del modo paralelo ---que de paso dan las mediantes
    cromáticas, el bIII y el bVI--- y, en jazz, la sustitución tritonal de
    cada dominante. Ninguno es de la tonalidad: una nota cromática en un
    tiempo fuerte se escucha mejor sostenida por un acorde que la tiene que
    metida a la fuerza en uno que no.
    """
    pc %= 12
    scale = bar.mode.pitch_classes(bar.tonic)
    sevenths = settings.with_sevenths
    applied: List[ChordOption] = []
    # Desde la tónica: en menor su dominante es el acorde que sostiene la
    # sensible subida, y no está en la escala. En mayor no agrega nada,
    # porque el V ya es de la tonalidad y no tiene ninguna nota cromática.
    for degree in range(7):
        applied.append(applied_dominant(scale[degree], bar, False))
        if sevenths or settings.genre_key == "jazz":
            applied.append(applied_dominant(scale[degree], bar, True))
        if settings.genre_key == "jazz":
            applied.append(tritone_substitute(scale[degree], bar))

    borrowed: List[ChordOption] = []
    if settings.allow_borrowed:
        keys = list(_CHROMATIC_BORROWED)
        if settings.genre_key in ("classical", "chorale"):
            keys.append("N6")
        if settings.genre_key == "jazz":
            keys.append("subV")
        borrowed = borrowed_options(bar.tonic, keys, sevenths)

    def holds(option: ChordOption) -> bool:
        return pc in {option.chord.pitch_class_of(t) for t in option.chord.tones}

    out: List[ChordOption] = []
    seen = set()
    for option in borrowed + applied:
        if not holds(option):
            continue
        key = (option.root_pc, frozenset(option.chord.pitch_classes),
               option.chord.bass_pc)
        if key in seen:
            continue
        seen.add(key)
        out.append(option)
    return out


def _applied_target(option: ChordOption) -> Optional[int]:
    """Adónde apunta una dominante aplicada, o None si no es una."""
    if option.roman.startswith("V/"):
        return (option.root_pc + 5) % 12
    if option.roman.startswith("subV"):
        return (option.root_pc - 1) % 12
    return None


def pin_chromatic_approaches(
    melody: Melody,
    spots: List[HarmonySpot],
    settings: "HarmonisationSettings",
) -> None:
    """
    Darle su acorde a cada nota cromática que va por semitono a la siguiente.

    La nota recibe un lugar propio ---como si el usuario la hubiera
    marcado--- limitado a los acordes de :func:`approach_options`. Y la nota
    de llegada también recibe el suyo, con premio para el acorde que la
    tiene de fundamental: una dominante que suena un tiempo y resuelve
    debajo de otra nota es una promesa que el oído escucha y que después no
    pasa.

    La nota de llegada se abre **antes** que la cromática. Al revés, si la
    cromática es corta, partir su lugar para la llegada podía correrlo
    entero sobre la nota siguiente, y la dominante terminaba debajo de la
    resolución.
    """
    for approach in chromatic_approaches(melody, settings.genre_key):
        if not approach.target.skip_harmonise:
            landing = spot_for_note(spots, approach.target)
            if landing is not None:
                if landing.required_note is None:
                    landing.required_note = approach.target
                landing.resolution_pc = approach.target_pc
        here = spot_for_note(spots, approach.note)
        if here is not None:
            here.required_note = approach.note
            here.approach = approach
            here.allowed_degrees = ()


def _spot_pool(
    melody: Melody,
    spot: HarmonySpot,
    settings: "HarmonisationSettings",
) -> Tuple[List[ChordOption], List[ChordOption]]:
    """
    Los acordes de un lugar: los de la tonalidad y, aparte, los cromáticos.

    Los cromáticos son los que sostienen alguna nota fuera de la escala que
    este lugar podría estar armonizando ---la del tiempo, la que viene
    enseguida o la que el usuario marcó---. Viajan aparte porque no pasan
    por el sorteo de los préstamos: están porque hacen falta.
    """
    bar = melody.bar(spot.bar_index)
    pool = _pool_for_bar(bar, settings)
    candidates = [spot.required_note,
                  melody.sounding_at(spot.bar_index, spot.offset_quarters),
                  melody.next_after(spot.bar_index, spot.offset_quarters)]
    extra: List[ChordOption] = []
    seen = set()
    for note in candidates:
        if note is None or note.is_rest:
            continue
        if not out_of_scale(note.pitch, melody.bar(note.bar_index)):
            continue
        if note.pitch % 12 in seen:
            continue
        seen.add(note.pitch % 12)
        extra.extend(chromatic_options(note.pitch, bar, settings))
    return pool, extra


def harmonise(
    melody: Melody,
    settings: HarmonisationSettings,
    rng: Optional[random.Random] = None,
) -> List[Tuple[HarmonySpot, ChordOption]]:
    """
    Pick a chord for every strong beat.

    Runs from the last spot to the first: the chord after this one is what
    says whether a dominant is wanted here, and that is only known once the
    later chord exists.
    """
    picker = rng or random.Random()
    spots = drop_skipped_spots(melody, harmony_spots(melody), settings)
    if not spots:
        return []
    pin_leading_tone(melody, spots, settings)
    pin_chromatic_approaches(melody, spots, settings)

    chosen: List[Optional[ChordOption]] = [None] * len(spots)

    for index in range(len(spots) - 1, -1, -1):
        spot = spots[index]
        bar = melody.bar(spot.bar_index)
        pool, extra = _spot_pool(melody, spot, settings)
        at_rest = index in (0, len(spots) - 1)

        # Una nota marcada no se discute: el lugar existe porque alguien
        # pidió un acorde para ella.
        spot.note = spot.required_note or choose_note_for_spot(
            melody, spot, pool + extra, settings.allow_colour)

        if spot.forced_roman:
            pinned = next((o for o in pool if o.roman == spot.forced_roman), None)
            if pinned is not None:
                chosen[index] = pinned
                continue

        following = chosen[index + 1] if index + 1 < len(chosen) else None
        scored: List[Tuple[float, ChordOption]] = []
        allowed = spot.allowed_degrees
        chromatic = (spot.note is not None and not spot.note.is_rest
                     and out_of_scale(spot.note.pitch,
                                      melody.bar(spot.note.bar_index)))
        if spot.approach is not None:
            # La regla de la nota cromática: el acorde no se elige de la
            # tonalidad, se elige entre los que apuntan a la nota siguiente.
            candidates = approach_options(spot.approach, bar, settings, picker)
            free = {id(option) for option in candidates}
        else:
            # Los cromáticos entran sólo si la nota que se armoniza es
            # cromática. Con una nota de la escala no hacen falta, y sin el
            # sorteo de los préstamos aparecerían en cualquier lado.
            candidates = pool + (extra if chromatic else [])
            free = {id(option) for option in extra}
        for option in candidates:
            if allowed and option.scale_degree not in allowed:
                continue
            if (id(option) not in free
                    and not _borrowed_allowed(option, index, len(spots),
                                              settings, picker)):
                continue
            cost = 0.0
            if spot.note is not None:
                cost += melodic_weight(note_fit(
                    option, spot.note.pitch, settings.allow_colour, at_rest))
                if chromatic and spot.note.pitch % 12 not in set(
                        option.chord.pitch_classes):
                    cost += CHROMATIC_OUTSIDE
            if (settings.genre_key == "gregorian" and id(option) in free
                    and spot.approach is None
                    and option.roman.startswith(("V/", "subV"))):
                cost += APPLIED_IN_MODAL
            if (spot.resolution_pc is not None
                    and option.root_pc == spot.resolution_pc):
                cost += RESOLUTION_REWARD
            if (id(option) in free and spot.approach is None
                    and _applied_target(option) is not None
                    and (following is None or following.root_pc
                         != _applied_target(option))):
                cost += UNRESOLVED_APPLIED
            cost += _progression_cost(option, following, bar, settings, index,
                                      len(spots))
            scored.append((cost, option))

        if not scored:
            continue
        scored.sort(key=lambda pair: pair[0])
        # A little randomness among near-equal choices, so two runs on the
        # same melody are not identical.
        # Anything within a real margin of the best is fair game, so the same
        # melody comes back harmonised differently on a second run. The
        # margin is generous on purpose: the top few candidates usually hold
        # the melody note equally well and differ only in how they connect.
        best = scored[0][0]
        close = [option for cost, option in scored if cost <= best + 55.0]
        chosen[index] = picker.choice(close) if close else scored[0][1]

    return [(spot, option) for spot, option in zip(spots, chosen)
            if option is not None]


def planned_notes(
    melody: Melody,
    settings: HarmonisationSettings,
) -> List[MelodyNote]:
    """
    Qué notas van a recibir un acorde, sin armonizar nada todavía.

    Es la misma cuenta que hace `harmonise` --- los mismos lugares, la misma
    elección de nota por lugar --- pero sin elegir acordes, así que no
    depende del azar y se puede correr en cada tecla mientras el usuario
    dibuja. Existe para que el pentagrama pueda pintarlas de dorado: la
    pregunta "¿a cuál de estas notas le va a poner un acorde?" no tenía
    respuesta hasta después de esperar la búsqueda entera, y era la única
    manera de entender por qué una nota sonaba contra la armonía anterior.
    """
    spots = drop_skipped_spots(melody, harmony_spots(melody), settings)
    if not spots:
        return []
    pin_leading_tone(melody, spots, settings)
    pin_chromatic_approaches(melody, spots, settings)
    seen = set()
    out: List[MelodyNote] = []
    for spot in spots:
        pool, extra = _spot_pool(melody, spot, settings)
        note = spot.required_note or choose_note_for_spot(
            melody, spot, pool + extra, settings.allow_colour)
        if note is None:
            continue
        where = (note.bar_index, note.offset_quarters)
        if where in seen:
            continue
        seen.add(where)
        out.append(note)
    return out


def _borrowed_allowed(
    option: ChordOption,
    index: int,
    total: int,
    settings: HarmonisationSettings,
    picker: random.Random,
) -> bool:
    """
    Whether a borrowed chord may be considered here.

    Both have narrow uses: the minor subdominant stands in for IV, and less
    often for V; the flat seventh belongs immediately before the close, where
    it approaches the tonic from below.
    """
    if not option.is_borrowed:
        return True
    if not settings.allow_borrowed:
        return False
    if option.roman == "iv":
        return picker.random() < max(settings.borrowed_iv_for_four,
                                     settings.borrowed_iv_for_five)
    if option.roman == "bVII":
        if index != total - 2:
            return False
        return picker.random() < settings.borrowed_flat_seven
    return False


def _progression_cost(
    option: ChordOption,
    following: Optional[ChordOption],
    bar: MelodyBar,
    settings: HarmonisationSettings,
    index: int,
    total: int,
) -> float:
    """How well this chord leads into the one already chosen after it."""
    cost = 0.0
    # Both ends want the tonic: a harmonisation that opens somewhere else
    # leaves the key unstated, and one that closes elsewhere leaves it open.
    if index in (0, total - 1) and option.root_pc != bar.tonic:
        # Decisive: a harmonisation that opens or closes away from the tonic
        # leaves the key unstated, whatever the style's grammar prefers.
        cost += 260.0
    if following is None:
        return cost

    if option.roman == following.roman:
        cost += settings.repeat

    # A dominant leading into a point of repose is the shape the backward
    # pass exists to find.
    if following.root_pc == bar.tonic and function_of(option) == DOMINANT:
        cost += settings.dominant_before_rest

    # The style's own grammar decides the rest, so a harmonisation sounds
    # like the idiom it was asked for: the same melody gets ii-V motion in
    # jazz and plagal closes in the modal setting.
    grammar = GRAMMARS.get(settings.genre_key)
    if grammar is not None:
        cost += grammar_cost(option, following, grammar, bar.tonic) * 0.6

    # The closing gesture is what makes a harmonisation sound like its style,
    # so the last approach is weighted well above the rest. Kept to the
    # cadence alone: pushing the whole progression this hard would flatten
    # the melodic fit that the mode exists to serve.
    if index == total - 2 and following.root_pc == bar.tonic:
        if settings.genre_key == "gregorian":
            if option.roman in ("IV", "iv"):
                cost += -150.0          # the plagal close
        elif settings.genre_key == "jazz":
            if option.roman == "V":
                cost += -120.0          # and the ii before it, below
        elif option.roman == "V":
            cost += -130.0              # the authentic cadence
    # In jazz the chord before the dominant wants to be the second degree.
    if (settings.genre_key == "jazz" and index == total - 3
            and following.roman == "V" and option.roman == "ii"):
        cost += -110.0
    return cost


# ---------------------------------------------------------------------------
# The weak-beat notes
# ---------------------------------------------------------------------------

#: Intervals above the bass that are harsh enough to matter even in passing.
#: A minor ninth is the sharpest dissonance there is, and a tritone against
#: the bass unsettles the harmony rather than decorating it.
HARSH_ABOVE_BASS = (1, 6)


def weak_beat_clashes(
    melody: Melody,
    spot: HarmonySpot,
    bass_pitch: int,
) -> int:
    """
    Count the ugly collisions a chord makes with the notes passing over it.

    The melody's weak-beat notes are free to be passing tones -- that is what
    they are for -- but a minor ninth or a tritone against the bass is heard
    as a mistake rather than as movement, so those are worth avoiding when
    there is a choice.
    """
    clashes = 0
    end = spot.offset_quarters + spot.duration_quarters
    for note in melody.notes:
        if note.is_rest or note.bar_index != spot.bar_index:
            continue
        if not (spot.offset_quarters <= note.offset_quarters < end):
            continue
        if abs(note.offset_quarters - spot.offset_quarters) < 1e-6:
            continue          # the strong-beat note is judged separately
        if (note.pitch - bass_pitch) % 12 in HARSH_ABOVE_BASS:
            clashes += 1
    return clashes


def clash_penalty(
    melody: Melody,
    spots: Sequence[HarmonySpot],
    chords: Sequence[Sequence[int]],
    weight: float = 55.0,
) -> float:
    """Total cost of the harsh collisions in a finished harmonisation."""
    total = 0.0
    for index, spot in enumerate(spots):
        if index >= len(chords) or not chords[index]:
            continue
        total += weight * weak_beat_clashes(melody, spot, chords[index][0])
    return total
