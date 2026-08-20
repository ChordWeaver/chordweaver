# -*- coding: utf-8 -*-
"""
Voicing planning: deciding *which* chord tones the available voices sing.

This module answers the "shape" question (which degrees are present, what is
doubled, what is omitted). It deliberately does NOT choose octaves or
registers -- that is the genetic algorithm's job, and it is what the fitness
function optimises.

Two situations have to be handled:

* More voices than chord tones (e.g. a triad sung by five voices) -> some
  tones must be **doubled**.
* More chord tones than voices (e.g. a 13th chord sung by four voices) ->
  some tones must be **omitted**, and the user has to be warned about it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .theory import (
    Chord,
    ChordTone,
    ROLE_EXTENSION,
    ROLE_FIFTH,
    ROLE_ROOT,
    ROLE_SEVENTH,
    ROLE_THIRD,
)

#: Los roles que definen de qué acorde se trata, y por lo tanto los únicos
#: que pueden ir en el bajo. Todo lo demás es color y va por encima.
BASS_ROLES = frozenset({ROLE_ROOT, ROLE_THIRD, ROLE_FIFTH, ROLE_SEVENTH})

#: Order in which tones are dropped when the chord has more notes than voices.
#: The fifth goes first (it is harmonically inert, especially when perfect),
#: then the root (the bass usually implies it), then the least colourful
#: extensions. The third and the seventh are never dropped: they carry the
#: chord quality. An altered fifth (b5/#5) is *not* inert, so it is treated as
#: a colour tone rather than a free drop.
OMISSION_PRIORITY = [
    "5",        # perfect fifth: safest omission
    "1",        # root: implied by the bass line
    "9",        # plain ninth before the spicier alterations
    "11",
    "13",
    "6",
]

#: Order in which tones are duplicated when there are more voices than tones.
#: Doubling the root is the standard choice, then the fifth. Thirds are
#: doubled reluctantly (doubled thirds sound thick, and doubling a *major*
#: third in a cadence is a classic no-no), and sevenths/extensions are never
#: doubled because that just muddies the colour.
DOUBLING_PRIORITY = ["1", "5", "3", "b3"]


@dataclass
class VoicingPlan:
    """The set of chord degrees assigned to the voices of one chord slot.

    ``degrees[i]`` is the chord tone sung by voice ``i`` (voice 0 = lowest).
    The plan fixes *what* each voice sings, not in which octave.

    This is the *default* shape shown in the UI. It is deliberately NOT what
    the genetic algorithm searches over -- see :class:`ChordRequirement`.
    """

    chord: Chord
    degrees: List[ChordTone]
    omitted: List[ChordTone]
    doubled: List[ChordTone]
    #: Colour tones added to fill the texture instead of doubling, when
    #: special voicings are switched on.
    added: List[ChordTone] = field(default_factory=list)
    #: La séptima que se cambió por un color, cuando la hubo. Va aparte de
    #: `omitted` --- donde también figura --- porque el nombre del acorde
    #: depende de ella: un Dm7 al que se le sacó la séptima ya no se llama
    #: Dm7, y sin este dato el cartel decía "Dm76".
    swapped_seventh: Optional[ChordTone] = None

    @property
    def pitch_classes(self) -> List[int]:
        return [self.chord.pitch_class_of(t) for t in self.degrees]

    @property
    def has_warnings(self) -> bool:
        return bool(self.omitted)


@dataclass
class ChordRequirement:
    """What the GA must satisfy for one chord slot.

    Rather than pinning voice *i* to chord tone *i*, the GA is free to give
    any voice any tone of the chord, as long as the chord still comes out
    complete. That freedom is the whole point: fixing the assignment forces
    doubled tones to stay locked in octaves with each other, which makes
    parallel octaves unavoidable between consecutive chords and leaves the
    classical and chorale profiles with no legal solution at all.

    Attributes
    ----------
    allowed_pitch_classes:
        Every pitch class a voice may sing in this slot.
    required_pitch_classes:
        Pitch classes that must appear somewhere in the chord, so the
        harmony is not silently gutted by the search.
    bass_pitch_class:
        When set, the lowest voice is pinned to this pitch class (slash
        chords); the GA still chooses the octave.
    """

    chord: Chord
    plan: VoicingPlan
    allowed_pitch_classes: List[int]
    required_pitch_classes: List[int]
    bass_pitch_class: Optional[int] = None

    @property
    def omitted(self) -> List[ChordTone]:
        return self.plan.omitted

    @property
    def bass_pitch_classes(self) -> List[int]:
        """
        Qué puede cantar la voz más grave.

        El bajo no es una voz más: es lo que dice **qué acorde es**. Sobre la
        fundamental, la tercera, la quinta o la séptima se oye el acorde
        escrito, en estado fundamental o en una de sus tres inversiones.
        Sobre cualquier otra nota se oye otro acorde, y el cifrado que el
        usuario escribió deja de ser cierto.

        Por eso las notas de color ---novena, oncena, trecena, sexta,
        cuarta--- quedan afuera de acá aunque estén permitidas en el resto de
        las voces: el color va arriba. Sin esta lista, el relleno de color
        podía mandar su nota al bajo y el resultado era otro acorde: un
        ``Dm7`` al que se le agregó la oncena salía si-fa-la-re, que es un
        ``Bm7b5``; un ``F`` con la cuarta agregada salía con el si bemol
        abajo. Medido, le pasaba al 6% de los acordes con el dial de color
        puesto.

        Un acorde con barra no llega hasta acá: cuando el usuario escribe
        ``C/E`` o ``C/F#`` el bajo lo eligió él y se respeta como esté, que
        es lo que hace ``bass_pitch_class``.
        """
        kept = _kept_tones(self.chord, self.plan)
        pcs = sorted({
            self.chord.pitch_class_of(tone) for tone in kept
            if tone.role in BASS_ROLES
        })
        # El bajo no se queda nunca sin candidatos. De un acorde escrito
        # siempre sobrevive alguna nota estructural ---la tercera y la
        # séptima no se omiten--- pero uno armado a mano en el piano puede
        # ser cualquier cosa, y quedarse sin solución es peor que un bajo
        # discutible.
        return pcs or list(self.allowed_pitch_classes)


#: Degrees that make a voicing "special" rather than a strict triad/seventh:
#: sixths, ninths, elevenths and their alterations. These are exactly the
#: colours the user can switch off per genre.
SPECIAL_VOICING_DEGREES = {"6", "9", "b9", "#9", "11", "#11", "13", "b13"}


def strip_special_voicings(chord: Chord) -> Chord:
    """
    Reduce a chord to its plain triad or seventh.

    Used when the genre has special voicings switched off: a Cmaj9 is written
    as Cmaj7 and a C6/9 as a plain C major, so a Gregorian setting never
    sprouts a ninth. The chord keeps its original symbol so the user can see
    what they asked for, but only the structural tones are voiced.
    """
    kept = [t for t in chord.tones if t.degree not in SPECIAL_VOICING_DEGREES]
    if not kept:
        return chord
    if all(t.role != ROLE_THIRD for t in kept):
        # sus chords hide their third in a "special" degree; keep the chord
        # intact rather than reducing it to a bare fifth.
        return chord
    return Chord(
        symbol=chord.symbol,
        root_pc=chord.root_pc,
        root_letter=chord.root_letter,
        tones=kept,
        bass_pc=chord.bass_pc,
        bass_letter=chord.bass_letter,
    )


def build_requirement(
    chord: Chord,
    voice_count: int,
    forced_omissions: Optional[Sequence[str]] = None,
    allow_special_voicings: bool = True,
    special_fills: bool = False,
    allow_major_sixth_on_minor: bool = False,
    colour_appetite: float = 1.0,
    rng: Optional[random.Random] = None,
    may_swap_seventh: bool = False,
) -> ChordRequirement:
    """
    Build the search space for one chord slot.

    The omission logic still runs first (a six-note chord sung by four voices
    genuinely has to lose two tones), but what comes out is a *pool* of legal
    pitch classes plus the ones that may not go missing, instead of a rigid
    voice-by-voice assignment.

    When ``allow_special_voicings`` is off, colour tones are stripped before
    anything else, so the switch genuinely changes the harmony rather than
    just the preference weights.
    """
    if not allow_special_voicings:
        chord = strip_special_voicings(chord)
        # Filling with colour is itself a special voicing. Leaving it on
        # while the colours were being stripped meant a style that has them
        # switched off (the modal profile) still sprouted ninths through the
        # other door.
        special_fills = False
    plan = build_voicing_plan(chord, voice_count, forced_omissions,
                              special_fills=special_fills,
                              allow_major_sixth_on_minor=allow_major_sixth_on_minor,
                              colour_appetite=colour_appetite, rng=rng,
                              may_swap_seventh=may_swap_seventh)

    kept_tones = _kept_tones(chord, plan)
    added_pcs = {chord.pitch_class_of(t) for t in plan.added}
    allowed = sorted({chord.pitch_class_of(t) for t in kept_tones} | added_pcs)

    # Essential tones (third, seventh) must always sound. The root is
    # required too whenever it survived the omission pass, otherwise the
    # chord loses its identity. Colour tones that were kept are required as
    # well -- if the user asked for a #9 they should hear the #9.
    #
    # A colour tone the plan *added* is required for the same reason. Merely
    # allowing it left the choice to the search, and the search always
    # declined: a doubling is reachable with less motion than a ninth, so the
    # spare voice went back to doubling and switching colour on changed
    # nothing anyone could hear. Requiring it is what makes the setting bite.
    # It is dropped again below when there is genuinely no room for it.
    required = sorted({chord.pitch_class_of(t) for t in kept_tones} | added_pcs)

    bass_pc = chord.bass_pc
    if bass_pc is not None and bass_pc not in allowed:
        # A slash bass that is not a chord tone (C/F#) still has to sound.
        allowed = sorted(set(allowed) | {bass_pc})

    # More required tones than voices cannot be satisfied; trim the least
    # essential ones so the GA is not handed an impossible job.
    if len(required) > voice_count:
        # Added colour goes first: it is decoration this module chose, not
        # part of the chord the user asked for.
        for pc in sorted(added_pcs):
            if len(required) <= voice_count:
                break
            if pc in required:
                required.remove(pc)
        ranked = sorted(
            kept_tones,
            key=lambda t: (t.is_essential, -_colour_rank(t)),
        )
        while len(required) > voice_count and ranked:
            victim = ranked.pop(0)
            pc = chord.pitch_class_of(victim)
            if pc in required and not victim.is_essential:
                required.remove(pc)

    return ChordRequirement(
        chord=chord,
        plan=plan,
        allowed_pitch_classes=allowed,
        required_pitch_classes=required,
        bass_pitch_class=bass_pc,
    )


def _kept_tones(chord: Chord, plan: VoicingPlan) -> List[ChordTone]:
    """Chord tones that survived the omission pass, without duplicates."""
    omitted = {id(t) for t in plan.omitted}
    seen: List[ChordTone] = []
    for tone in chord.tones:
        if id(tone) in omitted:
            continue
        if all(tone.degree != other.degree for other in seen):
            seen.append(tone)
    return seen


@dataclass
class VoicingAdvice:
    """Result of checking a chord against the available number of voices."""

    fits: bool
    message: str = ""
    suggested_omissions: List[str] = None  # printed degrees, e.g. ["5", "1"]

    def __post_init__(self) -> None:
        if self.suggested_omissions is None:
            self.suggested_omissions = []


def check_chord_fits(chord: Chord, voice_count: int) -> VoicingAdvice:
    """
    Check whether ``chord`` can be sung by ``voice_count`` voices.

    Returns advice the UI can show verbatim. When the chord has more tones
    than voices we do not refuse it -- we report which degrees we would drop
    so the user can accept the implied voicing or pick a simpler chord.
    """
    tone_count = len(chord.tones)
    if tone_count <= voice_count:
        return VoicingAdvice(fits=True)

    surplus = tone_count - voice_count
    droppable = _omission_order(chord)
    if len(droppable) < surplus:
        return VoicingAdvice(
            fits=False,
            message=(
                f"{chord.symbol} tiene {tone_count} notas y hay sólo {voice_count} "
                f"voces. Ni sacando todo lo prescindible entra: usá más voces "
                f"o un acorde más simple."
            ),
        )

    to_drop = [t.degree for t in droppable[:surplus]]
    return VoicingAdvice(
        fits=False,
        message=(
            f"{chord.symbol} tiene {tone_count} notas y hay {voice_count} voces. "
            f"Igual se puede escribir dando por sobreentendido: {', '.join(to_drop)}."
        ),
        suggested_omissions=to_drop,
    )


def _omission_order(chord: Chord) -> List[ChordTone]:
    """Return the chord's droppable tones, in the order they should be dropped."""
    by_degree = {t.degree: t for t in chord.tones}
    ordered: List[ChordTone] = []
    for degree in OMISSION_PRIORITY:
        tone = by_degree.get(degree)
        if tone is not None and not tone.is_essential:
            ordered.append(tone)
    # Any remaining non-essential tone (altered fifths, b9, #9, #11, b13...)
    # can still be dropped as a last resort, least essential first.
    remaining = [
        t for t in chord.tones
        if t not in ordered and not t.is_essential and t.role != ROLE_ROOT
    ]
    remaining.sort(key=lambda t: _colour_rank(t))
    ordered.extend(remaining)
    return ordered


def _colour_rank(tone: ChordTone) -> int:
    """Lower rank = dropped earlier. Altered tones are the most characterful."""
    if tone.degree in ("b5", "#5"):
        return 2
    if tone.degree in ("b9", "#9", "#11", "b13"):
        return 3
    if tone.role == ROLE_EXTENSION:
        return 1
    return 0


def _doubling_order(chord: Chord) -> List[ChordTone]:
    """Return the chord's tones in the order they should be doubled."""
    by_degree = {t.degree: t for t in chord.tones}
    ordered: List[ChordTone] = []
    for degree in DOUBLING_PRIORITY:
        tone = by_degree.get(degree)
        if tone is not None:
            ordered.append(tone)
    if not ordered:
        # Exotic chord with none of the usual doubling candidates: fall back to
        # the root, then whatever is left, keeping extensions last.
        ordered = sorted(chord.tones, key=lambda t: _ROLE_DOUBLING_RANK.get(t.role, 9))
    return ordered


_ROLE_DOUBLING_RANK = {
    ROLE_ROOT: 0,
    ROLE_FIFTH: 1,
    ROLE_THIRD: 2,
    ROLE_SEVENTH: 8,
    ROLE_EXTENSION: 9,
}


#: Colour tones that may fill an incomplete chord instead of a doubling,
#: when special voicings are switched on. Keyed by chord quality.
#:
#: The sixth added to a minor chord is split out because a *major* sixth over
#: a minor triad is a jazz sound (it is the m6 chord) and out of place in a
#: classical or modal setting, where a minor chord takes a minor sixth.
SPECIAL_FILL_MAJOR = [
    ("9", 2), ("11", 5), ("6", 9), ("4", 5),
]
SPECIAL_FILL_MINOR = [
    ("9", 2), ("11", 5), ("6", 8), ("4", 5),
]
SPECIAL_FILL_MINOR_JAZZ = [
    ("9", 2), ("11", 5), ("6", 9), ("6", 8), ("4", 5),
]


#: Con qué frecuencia, como fracción del dial de color, una séptima que no
#: cumple función de dominante se cambia por un color.
#:
#: A cuatro voces y con las séptimas prendidas el dial de color no hacía
#: absolutamente nada: cada acorde trae exactamente cuatro notas, no sobra
#: ninguna voz, y el color sólo entra por las voces que sobran. Todo sonaba
#: a séptima de punta a punta. Cambiar la séptima por un color es la única
#: puerta que queda, y va deliberadamente baja: es una variante, no el
#: sonido por defecto.
SEVENTH_SWAP_SHARE = 0.30

#: Los únicos colores que pueden ocupar el lugar de una séptima. Una novena
#: o una sexta reemplazan a la séptima sin discutirle el lugar a nadie; una
#: oncena choca de segunda contra la tercera y una trecena ES la sexta una
#: octava más arriba.
SEVENTH_SWAP_DEGREES = ("6", "9")


def _seventh_swap(chord: Chord, allow_major_sixth_on_minor: bool,
                  picker) -> Optional[ChordTone]:
    """El color que puede ocupar el lugar de la séptima, o ``None``."""
    third = next((t for t in chord.tones if t.role == ROLE_THIRD), None)
    if third is None:
        return None
    is_minor = third.semitones == 3
    present = {t.semitones % 12 for t in chord.tones}
    options: List[ChordTone] = []
    for degree in SEVENTH_SWAP_DEGREES:
        if degree == "9":
            semitones = 2
        else:
            semitones = 9 if (not is_minor or allow_major_sixth_on_minor) else 8
        if semitones % 12 in present:
            continue
        options.append(ChordTone(semitones % 12, ROLE_EXTENSION, degree))
    if not options:
        return None
    return picker.choice(options)


def _is_diminished(chord: Chord) -> bool:
    """True for a chord built on a diminished fifth."""
    fifth = next((t for t in chord.tones if t.role == ROLE_FIFTH), None)
    return fifth is not None and fifth.semitones == 6


def _special_fill_tones(chord: Chord, allow_major_sixth_on_minor: bool,
                        colour_appetite: Optional[float] = None) -> List[ChordTone]:
    """
    Colour tones available to fill out an incomplete chord.

    Only tones the chord does not already contain are offered, so a Cmaj9
    does not get a second ninth, and anything that would collide with an
    existing degree is skipped.
    """
    # A diminished chord is already at the limit of what it can carry: it is
    # built entirely of tension, and stacking ninths and elevenths on top
    # turns it to mud. It gets a doubling instead of a colour tone.
    if _is_diminished(chord):
        return []

    third = next((t for t in chord.tones if t.role == ROLE_THIRD), None)
    is_minor = third is not None and third.semitones == 3

    # Below a third of the way the dial offers the sixth alone: it is the
    # mildest colour there is, the one that thickens a chord without
    # announcing itself, so it is what "just a touch" should mean.
    if colour_appetite is not None and 0.0 < colour_appetite <= 0.33:
        sixth = 9 if (not is_minor or allow_major_sixth_on_minor) else 8
        present = {t.semitones % 12 for t in chord.tones}
        if sixth % 12 in present:
            return []
        return [ChordTone(sixth % 12, ROLE_EXTENSION, "6")]

    if not is_minor:
        table = SPECIAL_FILL_MAJOR
    elif allow_major_sixth_on_minor:
        table = SPECIAL_FILL_MINOR_JAZZ
    else:
        table = SPECIAL_FILL_MINOR

    present = {t.semitones % 12 for t in chord.tones}
    fills: List[ChordTone] = []
    for degree, semitones in table:
        if semitones % 12 in present:
            continue
        fills.append(ChordTone(semitones % 12, ROLE_EXTENSION, degree))
        present.add(semitones % 12)
    return fills


def _doubling_sequence(chord: Chord, extra_voices: int) -> List[ChordTone]:
    """
    Pick which tones to double, in order, when voices outnumber chord tones.

    The root is deliberately favoured over and over: with six voices on a
    plain triad, three roots plus two fifths reads far better than doubling
    the major third twice, which sounds thick and is a textbook cadence
    error. The third is only doubled once, and only after root and fifth.
    """
    order = _doubling_order(chord)
    if not order:
        return []

    root = next((t for t in order if t.role == ROLE_ROOT), None)
    fifth = next((t for t in order if t.role == ROLE_FIFTH), None)
    third = next((t for t in order if t.role == ROLE_THIRD), None)

    # Preference cycle: root, fifth, root, third, then root/fifth forever.
    cycle: List[ChordTone] = []
    for candidate in (root, fifth, root, third):
        if candidate is not None:
            cycle.append(candidate)
    if not cycle:
        cycle = order

    result: List[ChordTone] = []
    idx = 0
    while len(result) < extra_voices:
        if idx < len(cycle):
            result.append(cycle[idx])
        else:
            # Beyond the cycle keep alternating root and fifth only.
            tail = [t for t in (root, fifth) if t is not None] or order
            result.append(tail[(idx - len(cycle)) % len(tail)])
        idx += 1
    return result


def build_voicing_plan(
    chord: Chord,
    voice_count: int,
    forced_omissions: Optional[Sequence[str]] = None,
    special_fills: bool = False,
    allow_major_sixth_on_minor: bool = False,
    colour_appetite: float = 1.0,
    rng: Optional[random.Random] = None,
    may_swap_seventh: bool = False,
) -> VoicingPlan:
    """
    Decide which chord degree each voice sings.

    ``forced_omissions`` lets the caller (i.e. the user, via the warning
    dialog) pin down exactly which degrees to drop; otherwise the default
    omission priority is used.

    The returned degrees are ordered from the lowest voice upwards, with the
    root -- or the slash bass, when present -- placed in the bass voice.
    """
    if voice_count < 1:
        raise ValueError("voice_count must be at least 1")

    tones = list(chord.tones)
    omitted: List[ChordTone] = []
    doubled: List[ChordTone] = []
    added: List[ChordTone] = []
    swapped: Optional[ChordTone] = None

    # La séptima cambiada por un color. Va antes que todo lo demás porque el
    # color que entra tiene que pasar por la omisión y por el reparto como
    # una nota más del acorde; el que decide si este acorde puede permitirlo
    # es quien llama --- una dominante no puede, su séptima es la mitad de
    # lo que la vuelve dominante.
    if (may_swap_seventh and special_fills and colour_appetite > 0.0
            and not forced_omissions):
        picker = rng or random
        if picker.random() < colour_appetite * SEVENTH_SWAP_SHARE:
            seventh = next((t for t in tones if t.role == ROLE_SEVENTH), None)
            colour = (_seventh_swap(chord, allow_major_sixth_on_minor, picker)
                      if seventh is not None else None)
            if colour is not None:
                tones = [t for t in tones if t is not seventh]
                tones.append(colour)
                omitted.append(seventh)
                added.append(colour)
                swapped = seventh

    if forced_omissions:
        wanted = set(forced_omissions)
        keep = [t for t in tones if t.degree not in wanted]
        omitted = [t for t in tones if t.degree in wanted]
        tones = keep

    if len(tones) > voice_count:
        order = [t for t in _omission_order(chord) if t in tones]
        surplus = len(tones) - voice_count
        drop = order[:surplus]
        omitted.extend(drop)
        tones = [t for t in tones if t not in drop]

    if len(tones) < voice_count:
        missing = voice_count - len(tones)
        if special_fills and colour_appetite > 0.0:
            # Each spare voice is decided separately, and by chance: at a low
            # setting most of them still double, at a high one most take a
            # colour tone. Filling every spare voice unconditionally turned
            # the dial into an on/off switch -- nudging it at all produced a
            # fully coloured chord.
            #
            # Which colour is drawn at random too. Walking a fixed list meant
            # the ninth came first every single time, so that was the only
            # colour anyone ever heard.
            fills = _special_fill_tones(chord, allow_major_sixth_on_minor,
                                        colour_appetite)
            picker = rng or random
            available = list(fills)
            for _ in range(missing):
                if not available or picker.random() > colour_appetite:
                    continue
                tone = picker.choice(available)
                available.remove(tone)
                tones.append(tone)
                added.append(tone)
            missing = voice_count - len(tones)
        for tone in _doubling_sequence(chord, missing):
            tones.append(tone)
            doubled.append(tone)

    degrees = _order_for_voices(chord, tones)
    return VoicingPlan(chord=chord, degrees=degrees, omitted=omitted,
                       doubled=doubled, added=added,
                       swapped_seventh=swapped)


def _order_for_voices(chord: Chord, tones: List[ChordTone]) -> List[ChordTone]:
    """
    Order the selected tones from the bass voice upwards.

    The bass takes the slash bass note if the symbol has one, otherwise the
    root when it is present. The remaining tones are stacked by their
    interval above the root, which keeps the default shape close to a
    textbook close-position voicing before the GA starts moving octaves
    around.
    """
    remaining = list(tones)
    bass_tone: Optional[ChordTone] = None

    if chord.bass_pc is not None:
        for tone in remaining:
            if chord.pitch_class_of(tone) == chord.bass_pc:
                bass_tone = tone
                break
    if bass_tone is None:
        for tone in remaining:
            if tone.role == ROLE_ROOT:
                bass_tone = tone
                break
    if bass_tone is None:
        # Rootless voicing (the root was omitted to fit the voice count).
        # Jazz practice puts a guide tone at the bottom -- the third or the
        # seventh -- rather than whichever tone happens to sit lowest above
        # the absent root, which would strand a 9th in the bass.
        for role in (ROLE_THIRD, ROLE_SEVENTH, ROLE_FIFTH):
            candidates = [t for t in remaining if t.role == role]
            if candidates:
                bass_tone = min(candidates, key=lambda t: t.semitones)
                break
    if bass_tone is None:
        bass_tone = min(remaining, key=lambda t: t.semitones)

    remaining.remove(bass_tone)
    remaining.sort(key=lambda t: t.semitones)
    return [bass_tone] + remaining


def slash_bass_pitch_class(chord: Chord) -> Optional[int]:
    """
    Return the pitch class the bass voice is pinned to, if any.

    For a slash chord such as ``C/G`` the bass must sing G; the GA is only
    free to pick the octave. Returns None when the bass is unconstrained.
    """
    return chord.bass_pc



#: How an added colour tone is written in a chord symbol.
_ADDED_SUFFIX = {"9": "add9", "11": "add11", "6": "6", "4": "sus4"}


def symbol_with_added(plan: VoicingPlan) -> str:
    """
    Name the chord the way it is actually voiced.

    A C major triad voiced with an added ninth is a Cadd9, and printing it as
    plain C hides exactly the decision the colour setting was there to make.
    Only the tones the plan really added are reported, so a chord that ended
    up doubling instead keeps its plain name.
    """
    base = plan.chord.symbol
    if plan.swapped_seventh is not None:
        # La séptima ya no está, así que el nombre no puede seguir
        # diciéndola: "Dm7" con la séptima cambiada por una sexta es "Dm6",
        # no "Dm76".
        for suffix in ("maj7", "Maj7", "M7", "7"):
            if base.endswith(suffix):
                base = base[:-len(suffix)]
                break
    if not plan.added:
        return base
    suffixes = []
    for tone in plan.added:
        suffix = _ADDED_SUFFIX.get(tone.degree)
        if suffix and suffix not in suffixes:
            suffixes.append(suffix)
    if not suffixes:
        return base
    # La sexta se pega al nombre --- "C6" --- pero sólo si no quedó una
    # séptima adelante. Sobre un acorde que ya la lleva, pegarla daba
    # "Cmaj76" y "Am76", que no es el nombre de nada: dos cifras seguidas se
    # leen como una sola.
    keeps_seventh = (plan.swapped_seventh is None
                     and any(t.role == ROLE_SEVENTH for t in plan.chord.tones))
    if suffixes == ["6"] and not keeps_seventh:
        return f"{base}6"
    if len(suffixes) == 1 and not (keeps_seventh and suffixes == ["6"]):
        return base + suffixes[0]
    # Several colours read better listed than concatenated: C(9,11) rather
    # than Cadd9(add11).
    numbers = [s.replace("add", "") for s in suffixes]
    return f"{base}({','.join(numbers)})"
