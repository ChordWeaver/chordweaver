# -*- coding: utf-8 -*-
"""
Fitness evaluation for the voice-leading genetic algorithm.

Design
------
Fitness is a **cost**: lower is better, and the GA minimises it.

Costs come in two flavours:

* **Hard constraints** -- anything the user explicitly switched on, plus the
  vocal ranges. Violating one of these does not make the candidate expensive,
  it makes it *invalid*: the chromosome is annulled with an infinite cost so
  it can never win. This is what the user asked for: "anular el cromosoma si
  viola cualquier parametro elegido por el usuario".
* **Weighted penalties** -- musical preferences that vary by genre. Total
  voice movement carries by far the largest weight, because minimising motion
  is the whole point of the exercise; everything else nudges the result.

Genre profiles only change *weights and defaults*, never the mechanics. That
keeps a single well-tested evaluator for all four genres, and it leaves room
for the planned future feature where ~40% of the fitness will come from
genre-idiomatic chord choice rather than pure voice leading.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from .style import (
    ChordContext,
    ambitus_penalty,
    cadential_six_four,
    repose_dissonances,
    cadence_consonance_penalty,
    perfect_consonance_reward,
    repose_root_position_penalty,
    bass_contrary_reward,
    common_tone_reward,
    doubling_penalty,
    guide_tone_reward,
    harmonic_dissonance_penalty,
    leap_compensation_penalty,
    melodic_interval_penalty,
    melody_clash_penalty,
    minor_ninth_penalty,
    organum_interval_reward,
    organum_parallel_reward,
    tendency_tone_penalty,
    voice_overlap_count,
)
from .theory import VoicePart

INFINITE_COST = float("inf")

# Interval sizes in semitones.
PERFECT_FIFTH = 7
OCTAVE = 12
TRITONE = 6


# ---------------------------------------------------------------------------
# Genre profiles
# ---------------------------------------------------------------------------

@dataclass
class GenreProfile:
    """Weights and default switches for one musical style.

    Every field is exposed in the parameters screen, so these values are
    starting points rather than hard-coded behaviour.
    """

    key: str
    label: str
    description: str
    #: Whether the style appears as a card on the genre screen. The
    #: chorale profile is reached through a switch inside the baroque one
    #: instead of standing on its own, so it stays in the table -- every
    #: lookup is by key -- while never being offered as a separate style.
    selectable: bool = True

    # --- hard-constraint defaults (the user can flip any of them) ----------
    forbid_parallel_fifths: bool = False
    forbid_parallel_octaves: bool = False
    forbid_melodic_tritone: bool = False
    forbid_harmonic_tritone: bool = False
    #: Voice crossing is a genuine error in part writing, not a preference:
    #: as a mere weighted penalty the optimiser happily buys a crossing
    #: whenever it saves a few semitones of motion. Kept switchable because
    #: dense six-voice textures occasionally need it.
    forbid_voice_crossing: bool = True
    allow_special_voicings: bool = True
    #: When a chord has fewer notes than voices, fill the gap with a colour
    #: tone (9th, 11th, 6th, 4th) instead of doubling the root or fifth.
    special_voicing_fills: bool = False
    #: Reward per voice singing a colour tone (a ninth, eleventh, sixth or
    #: fourth added to fill the chord out) rather than a doubling. Negative
    #: values make them sought after. This is what lets the same switch mean
    #: "a hint of colour" for one style and "colour everywhere" for another.
    weight_colour_tone: float = 0.0
    #: Cost per pair of voices landing on the exact same pitch. A unison is
    #: not a doubling: the two parts stop being independent, and on the page
    #: they collapse into a single notehead, so a six-voice chord can look
    #: like a four-voice one. Doubling at the octave is fine and untouched.
    #:
    #: A cuatro voces esto no se notaba, porque a cuatro voces no pasaba: los
    #: registros apenas se tocan y el reparto sale solo. A seis, las voces del
    #: medio comparten media octava y el unísono aparecía en uno de cada
    #: catorce acordes. Medido sobre 160 acordes de barroco y coral a seis
    #: voces, con la búsqueda del tamaño de fábrica (200x300):
    #:
    #:     peso  250 -> 3,8% barroco / 0,6% coral
    #:     peso 1000 -> 0,6% barroco / 0,0% coral
    #:
    #: y el movimiento medio por voz sube de 2,21 a 2,30 semitonos, o sea
    #: nada. Más arriba de 1000 no mejora --- se probó 1500 --- y lo único que
    #: se consigue es que esta regla le gane a las demás por goleada.
    weight_unison: float = 1000.0
    #: Cost for a plain triad whose bass sings the fifth. Common practice
    #: treats that six-four as a dissonance needing preparation, so it turns
    #: up as a cadential ornament rather than as a free choice.
    #:
    #: Dominant sevenths are exempt. A major triad with a minor seventh over
    #: its fifth is standard writing in both common practice and jazz -- it
    #: is the ordinary second inversion of a V7, not the dissonant six-four
    #: the rule is about, and charging for it fought the style instead of
    #: enforcing it.
    #:
    #: El 6/4 **cadencial** también está exento, y por la misma razón al
    #: revés: es el único lugar donde la fórmula se escribe a propósito, y
    #: cobrárselo era prohibir justo lo que el estilo viene a enseñar. Lo
    #: exento es el 6/4 de verdad ---5-1-3 desde el bajo---; la dominante con
    #: la quinta abajo y la tercera en el medio sigue pagando, que es lo que
    #: empuja a la búsqueda hacia la disposición correcta en vez de hacia
    #: cualquiera que tenga la quinta en el bajo.
    weight_six_four: float = 0.0
    #: Premio (negativo) para el 6/4 cadencial: la dominante mayor cantada
    #: 5-1-3 y resolviendo a donde apunta.
    #:
    #: Hace falta un premio y no alcanza con levantar el castigo. El bajo en
    #: la fundamental casi siempre está más cerca del acorde anterior y del
    #: siguiente, así que en movimiento puro la disposición llana gana
    #: siempre: medido sobre diez progresiones de ocho acordes en barroco a
    #: cuatro voces por cada valor, con el castigo levantado y sin premio el
    #: 6/4 aparecía en el 25% de las dominantes que resuelven, y con premio
    #: en el 65%. Entre
    #: -40 y -70 el número no se mueve ---la disposición ya ganó, pagar más
    #: no la hace ganar dos veces--- y el movimiento medio sube un 1%, así
    #: que el valor está en el medio de esa meseta. Es el mismo motivo por el
    #: que los gestos de época viven en `flourish` y no acá ---un adorno sólo
    #: gana si se lo paga--- con la diferencia de que éste es una elección de
    #: disposición dentro de un acorde, que es exactamente lo que el
    #: evaluador decide.
    weight_cadential_six_four: float = 0.0

    # --- weighted preferences ---------------------------------------------
    #: Cost per semitone of total voice movement. The dominant term.
    weight_motion: float = 10.0
    #: Extra cost per semitone beyond `max_leap` in a single voice, so small
    #: steps stay cheap but wide leaps become progressively expensive.
    weight_leap: float = 6.0
    max_leap: int = 4
    #: Cost for each pair of voices that cross.
    weight_crossing: float = 60.0
    #: Cost per semitone of spacing beyond an octave between adjacent upper
    #: voices (the bass is exempt: bass-to-tenor tenths are idiomatic).
    weight_spacing: float = 12.0
    max_upper_spacing: int = OCTAVE
    #: Cost when two consecutive chords sound identical (same notes), which
    #: is the cheapest possible motion and therefore a tempting degenerate
    #: solution for a minimiser.
    weight_static_repeat: float = 120.0
    #: Reward (negative cost) per pair of voices moving in contrary motion.
    weight_contrary_bonus: float = 0.0
    #: Cost per voice that moves by leap instead of by step.
    weight_stepwise: float = 0.0
    #: Cost per semitone that the overall chord span exceeds `ideal_span`,
    #: used to pull jazz voicings into a close cluster.
    weight_span: float = 0.0
    ideal_span: int = 24
    #: Cost when a voice sits within `edge_margin` semitones of its range
    #: limit, discouraging solutions that are technically legal but strained.
    weight_tessitura: float = 3.0
    edge_margin: int = 2
    #: Cost per semitone que la voz más grave se aleja hacia arriba del centro
    #: de su registro.
    #:
    #: `weight_tessitura` sólo mira los bordes ---dos semitonos--- y el bajo
    #: llega hasta el do central, así que un bajo cantando en la octava del
    #: tenor está dentro del rango y no le cuesta nada. Salía: en una de cada
    #: diez corales el bajo terminaba en la3-do4, que es un registro que un
    #: bajo no canta y que además deja al tenor pegado o cruzado encima. El
    #: bajo es el único que tiene esta regla porque es el único cuya función
    #: le exige estar abajo: la soprano lleva la melodía y tiene que poder
    #: subir, y las voces del medio están sujetas por el espaciado.
    weight_bass_register: float = 0.0
    #: Cost per semitone que el **último** acorde abre más allá de
    #: `final_ideal_span`, medido de la voz más grave a la más aguda.
    #:
    #: Sólo el último. Ahí el oído se apoya y una disposición desparramada
    #: suena a que la pieza no cerró; y como el acorde final es el único que
    #: no tiene un acorde siguiente que lo sujete, era donde la soprano se
    #: escapaba a un agudo lejano sin que nada se lo cobrara. Comprimirlo tira
    #: hacia adentro también el salto con el que se llega a él.
    weight_final_span: float = 0.0
    final_ideal_span: int = 19
    #: Cost for a direct (hidden) fifth or octave into a perfect interval
    #: approached by similar motion in the outer voices.
    weight_direct_fifths: float = 0.0

    # --- genre-idiomatic counterpoint rules (see engine/style.py) ---------
    #: Doubling costs. The leading tone is the strictest: two of them imply
    #: parallel octaves however they resolve.
    weight_double_third: float = 0.0
    weight_double_leading_tone: float = 0.0
    weight_double_seventh: float = 0.0
    #: Tendency tones of the previous chord failing to resolve.
    weight_unresolved_seventh: float = 0.0
    weight_unresolved_leading_tone: float = 0.0
    #: Voice overlap between adjacent chords (subtler than crossing).
    weight_overlap: float = 0.0
    #: Rewards (negative): held common tones, upper voices against the bass,
    #: and jazz guide tones connecting by step.
    weight_common_tone: float = 0.0
    weight_bass_contrary: float = 0.0
    weight_guide_tone: float = 0.0
    #: A leap that is not answered by motion in the opposite direction.
    weight_leap_compensation: float = 0.0
    leap_compensation_threshold: int = 5
    #: Melodic intervals the style does not sing, plus a hard-ish ceiling.
    forbidden_melodic_intervals: tuple = ()
    weight_forbidden_melodic: float = 0.0
    style_max_leap: Optional[int] = None
    #: Harmonic colour: seconds/sevenths between voices (modal), and minor
    #: ninths above a non-root tone (the jazz avoid-note test).
    weight_harmonic_dissonance: float = 0.0
    weight_minor_ninth: float = 0.0

    # --- balance between "move as little as possible" and "sound like the
    # style". Both are multipliers applied at the very end, so the user can
    # slide the emphasis without having to understand any individual weight.
    # 1.0 / 1.0 is the tuned default; raising style_emphasis makes the search
    # accept extra movement in exchange for idiomatic writing.
    motion_emphasis: float = 1.0
    style_emphasis: float = 1.0


    # --- consonance at the points of repose (first and last chord) --------
    #: Baroque practice measures consonance from the bass: every interval
    #: between the bass and an upper voice should be a third, fifth, sixth,
    #: octave or their compounds. Weighted by default so a slightly rough
    #: cadence can still win if it is much smoother; set
    #: `cadence_consonance_required` to make it a hard constraint instead.
    weight_cadence_consonance: float = 0.0
    cadence_consonance_required: bool = False
    #: Cost when a chord of repose is sung inverted rather than with its root
    #: in the bass. Consonance measured from the bass cannot see the
    #: difference -- over the third of a Cmaj7 the upper voices form a third,
    #: a fifth and a sixth, all consonant -- so 3-5-7-1 scored as well as
    #: 1-3-5-7 and then won on movement, being the more compact of the two.
    #: Sized to outweigh the few semitones the bass saves by staying put.
    #: Slash chords, rootless voicings and three-part textures are exempt
    #: (see :func:`style.root_position_penalty`).
    weight_root_position: float = 0.0

    # --- the given melody, in the harmonising mode only -------------------
    #: Cost per voice sounding a semitone away from the note the user wrote.
    #: Shared by every genre: a minor second against the melody is harsh in
    #: all of them. It only ever fires when ``RunSettings.melody_voice`` is
    #: set, which is to say only when there *is* a given melody, so the other
    #: two modes never see it.
    weight_melody_clash: float = 90.0
    #: How much heavier that cost is on the first and last chord, where the
    #: ear settles and the clash is least forgivable.
    melody_clash_repose_factor: float = 4.0

    # --- organum, in the modal style only --------------------------------
    #: Reward (negative) for the vox organalis sitting a perfect fourth,
    #: fifth or octave below the vox principalis.
    weight_organum_interval: float = 0.0
    #: Reward (negative) for that pair moving in parallel from one chord to
    #: the next, which is the whole gesture organum is made of.
    weight_organum_parallel: float = 0.0

    #: Modal ambitus: cost per semitone a voice's whole line exceeds this
    #: span across the piece.
    weight_ambitus: float = 0.0
    max_ambitus: int = 12
    #: Reward (negative) per perfect consonance above the bass, which is what
    #: gives organum its sound.
    weight_perfect_consonance: float = 0.0


CLASSICAL = GenreProfile(
    key="classical",
    label="Barroco",
    description=(
        "Common-practice part writing: parallel perfect intervals are barred, "
        "contrary motion is rewarded and leaps are kept small."
    ),
    forbid_parallel_fifths=True,
    forbid_parallel_octaves=True,
    weight_motion=10.0,
    weight_leap=7.0,
    max_leap=4,
    weight_crossing=80.0,
    weight_spacing=14.0,
    weight_contrary_bonus=-4.0,
    weight_direct_fifths=25.0,
    weight_tessitura=4.0,
    weight_bass_register=4.0,
    weight_final_span=6.0,
    weight_six_four=55.0,
    weight_cadential_six_four=-45.0,
    # Species-counterpoint idiom: no melodic tritones or sevenths, leaps
    # answered by contrary motion, thirds doubled reluctantly.
    weight_double_third=30.0,
    weight_double_leading_tone=90.0,
    weight_double_seventh=45.0,
    weight_unresolved_seventh=45.0,
    weight_unresolved_leading_tone=55.0,
    weight_overlap=45.0,
    weight_common_tone=-6.0,
    weight_bass_contrary=-5.0,
    weight_leap_compensation=20.0,
    leap_compensation_threshold=5,
    forbidden_melodic_intervals=(6, 10, 11),
    weight_forbidden_melodic=70.0,
    weight_cadence_consonance=35.0,
    # Subido de 70. La auditoría por defecto concreto encontraba finales con
    # la tercera en el bajo --- un Do mayor terminando sobre mi --- que en
    # esta escritura no se hacen: la pieza empieza y termina apoyada en su
    # fundamental. A 70 el ahorro de mover el bajo unos semitonos alcanzaba
    # para comprarlo.
    weight_root_position=110.0,
)

CHORALE = GenreProfile(
    key="chorale",
    label="Barroco",
    selectable=False,
    description=(
        "Bach-style chorale writing: like the classical profile but stricter "
        "about spacing and tessitura, and even more reluctant to leap."
    ),
    forbid_parallel_fifths=True,
    forbid_parallel_octaves=True,
    weight_motion=12.0,
    weight_leap=10.0,
    max_leap=3,
    weight_crossing=120.0,
    weight_spacing=25.0,
    max_upper_spacing=OCTAVE,
    weight_contrary_bonus=-5.0,
    weight_direct_fifths=35.0,
    weight_stepwise=4.0,
    weight_tessitura=6.0,
    # El coral es el que más lo necesita: es el perfil que más aprieta el
    # espaciado entre las voces de arriba, y con la soprano alta la manera
    # más barata de cerrar esos huecos era subir el bajo con ellas.
    weight_bass_register=7.0,
    weight_final_span=9.0,
    weight_static_repeat=150.0,
    weight_six_four=70.0,
    weight_cadential_six_four=-45.0,
    # Bach chorale idiom, stricter than the classical profile throughout.
    weight_double_third=45.0,
    weight_double_leading_tone=140.0,
    weight_double_seventh=70.0,
    weight_unresolved_seventh=70.0,
    weight_unresolved_leading_tone=85.0,
    weight_overlap=70.0,
    weight_common_tone=-9.0,
    weight_bass_contrary=-8.0,
    weight_leap_compensation=28.0,
    leap_compensation_threshold=4,
    forbidden_melodic_intervals=(6, 10, 11),
    weight_forbidden_melodic=90.0,
    weight_cadence_consonance=45.0,
    # Y el coral más todavía, que es donde más se notaba: cinco de cada
    # veinticinco corridas cerraban en primera inversión.
    weight_root_position=150.0,
)

GREGORIAN = GenreProfile(
    key="gregorian",
    label="Gregoriano",
    description=(
        "Modal writing: the tritone is treated as the diabolus in musica, "
        "motion is overwhelmingly stepwise and parallel perfect intervals are "
        "tolerated because organum is built on them."
    ),
    forbid_parallel_fifths=False,
    forbid_parallel_octaves=False,
    # "Mi contra fa est diabolus in musica" bans the interval itself, not
    # merely the leap: a tritone sounding between two voices was as
    # forbidden as one sung melodically. Both switches therefore start on.
    forbid_melodic_tritone=True,
    forbid_harmonic_tritone=True,
    allow_special_voicings=False,
    weight_motion=14.0,
    weight_leap=22.0,
    max_leap=2,
    weight_stepwise=34.0,
    weight_crossing=50.0,
    weight_spacing=10.0,
    weight_contrary_bonus=0.0,
    weight_tessitura=5.0,
    weight_bass_register=4.0,
    weight_final_span=5.0,
    # Modal idiom: near-exclusively stepwise, narrow ambitus, dissonant
    # seconds and sevenths discouraged, parallel perfect motion left alone.
    weight_common_tone=-8.0,
    weight_leap_compensation=35.0,
    leap_compensation_threshold=4,
    forbidden_melodic_intervals=(6, 10, 11),
    weight_forbidden_melodic=120.0,
    style_max_leap=5,
    # Measured ambitus in real solutions sits near 5 semitones, so a
    # threshold of 9 never fired at all. Set just below typical so the rule
    # actually bites, which is the point of having it.
    weight_ambitus=30.0,
    max_ambitus=5,
    weight_perfect_consonance=-22.0,
    weight_harmonic_dissonance=26.0,
    weight_overlap=30.0,
    weight_cadence_consonance=50.0,
    weight_root_position=130.0,
    # Organum. Sized to be worth paying real movement for: the parallel is
    # the point of the style, not a bonus it collects when convenient.
    weight_organum_interval=-75.0,
    weight_organum_parallel=-190.0,
)

JAZZ = GenreProfile(
    key="jazz",
    label="Jazz",
    description=(
        "Extended harmony: parallel motion and tritones are fine by default, "
        "voicings are pulled into a close cluster and colour tones are kept."
    ),
    forbid_parallel_fifths=False,
    forbid_parallel_octaves=False,
    forbid_melodic_tritone=False,
    forbid_harmonic_tritone=False,
    allow_special_voicings=True,
    weight_motion=10.0,
    weight_leap=4.0,
    max_leap=5,
    weight_crossing=40.0,
    weight_spacing=6.0,
    max_upper_spacing=OCTAVE + 3,
    weight_span=5.0,
    ideal_span=22,
    weight_contrary_bonus=0.0,
    weight_tessitura=2.0,
    # Flojo a propósito: el jazz escribe bajos más altos que el coral y usa
    # el registro grave con otro criterio. Y el cierre ya está comprimido por
    # `weight_span`, que en este estilo corre en todos los acordes.
    weight_bass_register=2.0,
    weight_final_span=4.0,
    final_ideal_span=22,
    weight_static_repeat=90.0,
    weight_six_four=35.0,
    # Jazz idiom: guide tones (3rd and 7th) connect by step, sevenths fall,
    # common tones are held, minor ninths above a non-root tone avoided.
    weight_guide_tone=-34.0,
    weight_unresolved_seventh=25.0,
    weight_common_tone=-10.0,
    weight_minor_ninth=45.0,
    weight_double_seventh=30.0,
    weight_overlap=15.0,
    # Jazz cadences routinely end on a major seventh, which is a dissonance
    # against the bass, so this stays gentle.
    weight_cadence_consonance=8.0,
    weight_root_position=110.0,
)

GENRE_PROFILES: Dict[str, GenreProfile] = {
    profile.key: profile
    for profile in (CLASSICAL, CHORALE, GREGORIAN, JAZZ)
}


# ---------------------------------------------------------------------------
# Run settings
# ---------------------------------------------------------------------------

@dataclass
class RunSettings:
    """Everything the fitness function needs that is not the chromosome.

    Built by the UI from the genre profile plus the user's switch overrides,
    so the engine never has to know where a value came from.

    ``required_pitch_classes[i]`` lists the tones that must sound in chord
    ``i``. Because the GA may hand any chord tone to any voice, nothing else
    stops it from quietly dropping the third of every chord to save motion --
    coverage has to be enforced as a hard constraint.
    """

    profile: GenreProfile
    voices: List[VoicePart]
    required_pitch_classes: Optional[List[List[int]]] = None
    #: Pitch classes that count as added colour in each slot, so the
    #: evaluator can reward reaching for them.
    colour_pitch_classes: Optional[List[List[int]]] = None
    #: Harmonic facts per chord slot, needed by the genre-idiomatic rules
    #: (doubling, tendency-tone resolution, guide tones). Optional so plain
    #: voice-leading scoring still works without any chord context.
    chord_contexts: Optional[List[ChordContext]] = None
    #: Index of the voice carrying a melody the user wrote, when there is
    #: one. Set only by the harmonising mode; ``None`` everywhere else, which
    #: is what keeps the melody rules from touching the other two modes.
    melody_voice: Optional[int] = None
    #: Index of the voice carrying the vox principalis, when the style is
    #: writing organum. The vox organalis is always the voice immediately
    #: below it, so one number describes the pair. ``None`` switches the
    #: organum rules off entirely.
    principalis_voice: Optional[int] = None

    def with_overrides(self, **kwargs) -> "RunSettings":
        """Return a copy whose profile has the given fields replaced."""
        return RunSettings(
            profile=replace(self.profile, **kwargs),
            voices=self.voices,
            required_pitch_classes=self.required_pitch_classes,
            chord_contexts=self.chord_contexts,
            colour_pitch_classes=self.colour_pitch_classes,
            melody_voice=self.melody_voice,
            principalis_voice=self.principalis_voice,
        )


# ---------------------------------------------------------------------------
# Constraint checks
# ---------------------------------------------------------------------------

def parallel_interval_violation(
    previous: Sequence[int],
    current: Sequence[int],
    voice_a: int,
    voice_b: int,
) -> Tuple[bool, bool]:
    """
    Detect parallel fifths / octaves between one pair of voices.

    A violation needs three things at once: the interval is a perfect fifth
    (or octave/unison) *before*, the same perfect interval *after*, and both
    voices actually moving in the same direction. Two voices holding a fifth
    while nothing moves is not a parallel fifth, and neither is a fifth
    reached by contrary motion.

    Returns (parallel_fifth, parallel_octave).
    """
    interval_before = (previous[voice_b] - previous[voice_a]) % OCTAVE
    interval_after = (current[voice_b] - current[voice_a]) % OCTAVE

    motion_a = current[voice_a] - previous[voice_a]
    motion_b = current[voice_b] - previous[voice_b]
    similar_motion = (
        motion_a != 0
        and motion_b != 0
        and ((motion_a > 0) == (motion_b > 0))
    )
    if not similar_motion:
        return False, False

    is_fifth = interval_before == PERFECT_FIFTH and interval_after == PERFECT_FIFTH
    is_octave = interval_before == 0 and interval_after == 0
    return is_fifth, is_octave


def direct_perfect_violation(
    previous: Sequence[int],
    current: Sequence[int],
    lowest: int,
    highest: int,
) -> bool:
    """
    Detect a direct (hidden) fifth or octave between the outer voices.

    Classical practice frowns on reaching a perfect fifth or octave by
    similar motion in the outer voices when the upper voice leaps. This is a
    weighted penalty rather than a hard rule, since even Bach breaks it.
    """
    interval_after = (current[highest] - current[lowest]) % OCTAVE
    if interval_after not in (0, PERFECT_FIFTH):
        return False

    motion_low = current[lowest] - previous[lowest]
    motion_high = current[highest] - previous[highest]
    if motion_low == 0 or motion_high == 0:
        return False
    if (motion_low > 0) != (motion_high > 0):
        return False
    # Only penalised when the top voice arrives by leap.
    return abs(motion_high) > 2


def has_melodic_tritone(previous: Sequence[int], current: Sequence[int]) -> bool:
    """True if any single voice moves by a tritone between the two chords."""
    return any(abs(current[i] - previous[i]) == TRITONE for i in range(len(current)))


def has_harmonic_tritone(chord_pitches: Sequence[int]) -> bool:
    """True if any pair of voices sounds a tritone within the same chord."""
    count = len(chord_pitches)
    for i in range(count):
        for j in range(i + 1, count):
            if (chord_pitches[j] - chord_pitches[i]) % OCTAVE == TRITONE:
                return True
    return False


def range_violations(chord_pitches: Sequence[int], voices: Sequence[VoicePart]) -> int:
    """Count voices singing outside their configured range."""
    return sum(
        1 for i, pitch in enumerate(chord_pitches) if not voices[i].contains(pitch)
    )


# ---------------------------------------------------------------------------
# Fitness
# ---------------------------------------------------------------------------

@dataclass
class FitnessBreakdown:
    """Per-term cost report, used by the UI and by the test suite."""

    total: float = 0.0
    motion: float = 0.0
    leaps: float = 0.0
    crossing: float = 0.0
    spacing: float = 0.0
    static_repeat: float = 0.0
    contrary_bonus: float = 0.0
    stepwise: float = 0.0
    span: float = 0.0
    tessitura: float = 0.0
    direct_perfect: float = 0.0
    style: float = 0.0
    #: Cost of the progression itself, added by the generative search.
    harmony: float = 0.0
    #: Cost of the passing-tone decisions.
    passing: float = 0.0
    cadence: float = 0.0
    valid: bool = True
    violation: str = ""

    def as_dict(self) -> Dict[str, float]:
        return {
            "total": self.total,
            "motion": self.motion,
            "leaps": self.leaps,
            "crossing": self.crossing,
            "spacing": self.spacing,
            "static_repeat": self.static_repeat,
            "contrary_bonus": self.contrary_bonus,
            "stepwise": self.stepwise,
            "span": self.span,
            "tessitura": self.tessitura,
            "direct_perfect": self.direct_perfect,
            "style": self.style,
            "harmony": self.harmony,
            "passing": self.passing,
            "cadence": self.cadence,
        }


def evaluate(
    chords: Sequence[Sequence[int]],
    settings: RunSettings,
    explain: bool = False,
) -> FitnessBreakdown:
    """
    Score a full progression.

    ``chords[i]`` is the list of MIDI pitches for chord ``i``, ordered from
    the lowest voice to the highest. Returns a :class:`FitnessBreakdown`
    whose ``total`` is the cost to minimise; invalid candidates come back
    with ``total = inf`` and ``valid = False``.
    """
    profile = settings.profile
    voices = settings.voices
    result = FitnessBreakdown()

    if not chords:
        return result

    # --- per-chord checks --------------------------------------------------
    for index, pitches in enumerate(chords):
        # Vocal ranges are always a hard constraint: the user asked for any
        # GA that breaks them to be heavily penalised, and a note a singer
        # cannot reach makes the whole solution worthless.
        if range_violations(pitches, voices):
            result.valid = False
            result.violation = f"chord {index}: a voice is outside its range"
            result.total = INFINITE_COST
            return result

        if profile.forbid_harmonic_tritone and has_harmonic_tritone(pitches):
            result.valid = False
            result.violation = f"chord {index}: harmonic tritone"
            result.total = INFINITE_COST
            return result

        # The chord must still be the chord the user asked for.
        if settings.required_pitch_classes is not None:
            sounded = {p % 12 for p in pitches}
            missing = [
                pc for pc in settings.required_pitch_classes[index] if pc not in sounded
            ]
            if missing:
                result.valid = False
                result.violation = f"chord {index}: missing required chord tone(s)"
                result.total = INFINITE_COST
                return result

        crossings = _crossing_count(pitches)
        if crossings and profile.forbid_voice_crossing:
            result.valid = False
            result.violation = f"chord {index}: voice crossing"
            result.total = INFINITE_COST
            return result
        result.crossing += profile.weight_crossing * crossings
        result.spacing += profile.weight_spacing * _spacing_excess(pitches, profile)
        result.tessitura += profile.weight_tessitura * _tessitura_strain(pitches, voices, profile)
        if profile.weight_bass_register:
            result.tessitura += (profile.weight_bass_register
                                 * _bass_register_excess(pitches, voices))
        # Sólo el último acorde: es donde el oído se apoya y el único que no
        # tiene un acorde después que sujete a la voz de arriba.
        if profile.weight_final_span and index == len(chords) - 1:
            result.spacing += (profile.weight_final_span
                               * _final_span_excess(pitches, profile))

        if profile.weight_unison:
            result.style += profile.weight_unison * _unison_pairs(pitches)

        # El 6/4: castigado en general, exento y premiado cuando es el
        # cadencial. Las dos preguntas necesitan el acorde que sigue, que es
        # lo que dice si esta dominante resuelve o simplemente pasa.
        if profile.weight_six_four or profile.weight_cadential_six_four:
            context = _context_at(settings, index)
            following = _context_at(settings, index + 1)
            cadential = cadential_six_four(pitches, context, following)
            if cadential and profile.weight_cadential_six_four:
                result.style += profile.weight_cadential_six_four
            if (profile.weight_six_four
                    and not cadential
                    and context is not None
                    and context.fifth_pc is not None
                    and not context.is_dominant
                    and pitches[0] % 12 == context.fifth_pc):
                result.style += profile.weight_six_four

        # --- genre-idiomatic per-chord rules ---
        context = _context_at(settings, index)
        if context is not None:
            result.style += doubling_penalty(
                pitches,
                context,
                profile.weight_double_third,
                profile.weight_double_leading_tone,
                profile.weight_double_seventh,
            )
            result.style += minor_ninth_penalty(pitches, context, profile.weight_minor_ninth)
        result.style += harmonic_dissonance_penalty(
            pitches, profile.weight_harmonic_dissonance
        )

        if profile.weight_colour_tone and settings.colour_pitch_classes:
            colours = set(settings.colour_pitch_classes[index]) if index < len(
                settings.colour_pitch_classes) else set()
            if colours:
                result.style += profile.weight_colour_tone * sum(
                    1 for p in pitches if p % 12 in colours
                )
        result.style += perfect_consonance_reward(
            pitches, profile.weight_perfect_consonance
        )
        result.style += organum_interval_reward(
            pitches, settings.principalis_voice, profile.weight_organum_interval
        )
        if profile.weight_melody_clash and settings.melody_voice is not None:
            # Heavier at the two points of repose: everywhere else the ear is
            # still travelling and a passing rub is survivable.
            at_repose = index == 0 or index == len(chords) - 1
            result.style += melody_clash_penalty(
                pitches,
                settings.melody_voice,
                profile.weight_melody_clash * (
                    profile.melody_clash_repose_factor if at_repose else 1.0),
            )
        if profile.weight_span:
            excess = (pitches[-1] - pitches[0]) - profile.ideal_span
            if excess > 0:
                result.span += profile.weight_span * excess

    # --- transition checks -------------------------------------------------
    voice_count = len(voices)
    for index in range(1, len(chords)):
        previous = chords[index - 1]
        current = chords[index]

        if profile.forbid_melodic_tritone and has_melodic_tritone(previous, current):
            result.valid = False
            result.violation = f"transition {index - 1}->{index}: melodic tritone"
            result.total = INFINITE_COST
            return result

        for a in range(voice_count):
            for b in range(a + 1, voice_count):
                fifth, octave = parallel_interval_violation(previous, current, a, b)
                if fifth and profile.forbid_parallel_fifths:
                    result.valid = False
                    result.violation = f"transition {index - 1}->{index}: parallel fifths"
                    result.total = INFINITE_COST
                    return result
                if octave and profile.forbid_parallel_octaves:
                    result.valid = False
                    result.violation = f"transition {index - 1}->{index}: parallel octaves"
                    result.total = INFINITE_COST
                    return result

        # Motion: the dominant term.
        movements = [current[i] - previous[i] for i in range(voice_count)]
        result.motion += profile.weight_motion * sum(abs(m) for m in movements)

        # Leaps beyond the profile's comfortable step size.
        for movement in movements:
            excess = abs(movement) - profile.max_leap
            if excess > 0:
                result.leaps += profile.weight_leap * excess
        if profile.weight_stepwise:
            result.stepwise += profile.weight_stepwise * sum(
                1 for m in movements if abs(m) > 2
            )

        # Two consecutive chords sounding exactly the same is free motion, so
        # without this term a minimiser is tempted to stand still.
        #
        # It only applies when the harmony actually changed. The user picks
        # the chords here, so writing E7 twice in a row is a request to hear
        # E7 twice, and holding every voice is the correct answer rather
        # than a dodge -- charging for it forced pointless re-voicings of a
        # chord that never moved.
        if list(previous) == list(current) and not _same_harmony(settings, index - 1, index):
            result.static_repeat += profile.weight_static_repeat

        if profile.weight_contrary_bonus:
            result.contrary_bonus += profile.weight_contrary_bonus * _contrary_pairs(movements)

        if profile.weight_direct_fifths and voice_count >= 2:
            if direct_perfect_violation(previous, current, 0, voice_count - 1):
                result.direct_perfect += profile.weight_direct_fifths

        # --- genre-idiomatic per-transition rules ---
        result.style += profile.weight_overlap * voice_overlap_count(previous, current)
        result.style += common_tone_reward(previous, current, profile.weight_common_tone)
        result.style += bass_contrary_reward(previous, current, profile.weight_bass_contrary)
        result.style += organum_parallel_reward(
            previous, current, settings.principalis_voice,
            profile.weight_organum_parallel,
        )
        result.style += melodic_interval_penalty(
            previous,
            current,
            profile.forbidden_melodic_intervals,
            profile.style_max_leap,
            profile.weight_forbidden_melodic,
        )
        result.style += leap_compensation_penalty(
            chords[index - 2] if index >= 2 else None,
            previous,
            current,
            profile.leap_compensation_threshold,
            profile.weight_leap_compensation,
        )

        previous_context = _context_at(settings, index - 1)
        current_context = _context_at(settings, index)
        if previous_context is not None:
            result.style += tendency_tone_penalty(
                previous,
                current,
                previous_context,
                profile.weight_unresolved_seventh,
                profile.weight_unresolved_leading_tone,
            )
            if current_context is not None:
                result.style += guide_tone_reward(
                    previous, current, previous_context, current_context,
                    profile.weight_guide_tone,
                )

    result.style += ambitus_penalty(chords, profile.max_ambitus, profile.weight_ambitus)

    # Ambitus is a property of a whole line, so it is measured once over the
    # finished progression rather than chord by chord.

    # --- consonance at the points of repose (first and last chord) -------
    if profile.cadence_consonance_required:
        for position in ({0, len(chords) - 1} if len(chords) > 1 else {0}):
            if repose_dissonances(chords[position]):
                result.valid = False
                result.violation = (
                    f"chord {position}: dissonance against the bass in a "
                    f"chord of repose"
                )
                result.total = INFINITE_COST
                return result
    result.cadence = cadence_consonance_penalty(
        chords, profile.weight_cadence_consonance
    )
    result.cadence += repose_root_position_penalty(
        chords, settings.chord_contexts, profile.weight_root_position
    )

    # The two emphases let the user slide between "move as little as
    # possible" and "sound like the style" without touching any individual
    # weight. Applied at the end so the tuned balance inside each group is
    # preserved and only their relative importance changes.
    motion_group = (
        result.motion
        + result.leaps
        + result.static_repeat
    ) * profile.motion_emphasis
    style_group = (
        result.style
        + result.crossing
        + result.spacing
        + result.contrary_bonus
        + result.stepwise
        + result.span
        + result.tessitura
        + result.direct_perfect
        + result.cadence
    ) * profile.style_emphasis

    result.total = motion_group + style_group
    return result


def _legacy_total(result: "FitnessBreakdown") -> float:
    """Unweighted sum of every term, kept for diagnostics and tests."""
    return (
        result.motion
        + result.leaps
        + result.crossing
        + result.spacing
        + result.static_repeat
        + result.contrary_bonus
        + result.stepwise
        + result.span
        + result.tessitura
        + result.direct_perfect
        + result.style
        + result.cadence
    )


def _same_harmony(settings: RunSettings, first: int, second: int) -> bool:
    """
    True when two slots hold the same chord.

    Compared through the tones each slot requires, which is what the search
    actually has to satisfy: two slots asking for the same set of pitch
    classes are the same harmony however their symbols were typed.
    """
    required = settings.required_pitch_classes
    if required and 0 <= first < len(required) and 0 <= second < len(required):
        return set(required[first]) == set(required[second])

    contexts = settings.chord_contexts
    if contexts and 0 <= first < len(contexts) and 0 <= second < len(contexts):
        a, b = contexts[first], contexts[second]
        return (a.root_pc, a.third_pc, a.fifth_pc, a.seventh_pc) == (
            b.root_pc, b.third_pc, b.fifth_pc, b.seventh_pc
        )
    return False


def _context_at(settings: RunSettings, index: int) -> Optional[ChordContext]:
    """Chord context for a slot, or None when the caller supplied none."""
    contexts = settings.chord_contexts
    if not contexts or index < 0 or index >= len(contexts):
        return None
    return contexts[index]


def _unison_pairs(pitches: Sequence[int]) -> int:
    """Pairs of voices sounding the identical pitch, not merely the octave."""
    seen: Dict[int, int] = {}
    for pitch in pitches:
        seen[pitch] = seen.get(pitch, 0) + 1
    return sum(count - 1 for count in seen.values() if count > 1)


def _crossing_count(pitches: Sequence[int]) -> int:
    """Number of adjacent voice pairs that are out of order (lower above higher)."""
    return sum(1 for i in range(len(pitches) - 1) if pitches[i] > pitches[i + 1])


def _spacing_excess(pitches: Sequence[int], profile: GenreProfile) -> int:
    """
    Total semitones by which adjacent upper voices exceed the spacing limit.

    The bass-to-next-voice gap is skipped on purpose: a wide gap above the
    bass is normal, while a gap between two upper voices leaves a hole in the
    texture.
    """
    excess = 0
    for i in range(1, len(pitches) - 1):
        gap = pitches[i + 1] - pitches[i]
        if gap > profile.max_upper_spacing:
            excess += gap - profile.max_upper_spacing
    return excess


def _tessitura_strain(
    pitches: Sequence[int],
    voices: Sequence[VoicePart],
    profile: GenreProfile,
) -> int:
    """Count voices sitting right at the edge of their comfortable range."""
    strain = 0
    for i, pitch in enumerate(pitches):
        voice = voices[i]
        if pitch - voice.low < profile.edge_margin or voice.high - pitch < profile.edge_margin:
            strain += 1
    return strain


def _bass_register_excess(
    pitches: Sequence[int],
    voices: Sequence[VoicePart],
) -> int:
    """Semitonos que la voz más grave sube por encima del centro de su registro.

    El centro y no el borde: el borde ya lo vigila `_tessitura_strain`, y el
    problema del bajo agudo ocurre entero dentro del rango legal.
    """
    if not pitches or not voices:
        return 0
    voice = voices[0]
    middle = (voice.low + voice.high) // 2
    return max(0, pitches[0] - middle)


def _final_span_excess(pitches: Sequence[int], profile: GenreProfile) -> int:
    """Cuánto se abre el acorde final más allá de lo que se le pide."""
    if len(pitches) < 2:
        return 0
    return max(0, (max(pitches) - min(pitches)) - profile.final_ideal_span)


def _contrary_pairs(movements: Sequence[int]) -> int:
    """Number of voice pairs moving in opposite directions."""
    count = 0
    for i in range(len(movements)):
        for j in range(i + 1, len(movements)):
            if movements[i] * movements[j] < 0:
                count += 1
    return count
