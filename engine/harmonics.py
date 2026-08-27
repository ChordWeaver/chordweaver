# -*- coding: utf-8 -*-
"""
La serie armónica, desarmada en piezas que se pueden tocar de a una.

Todo lo que suena --- una cuerda, una columna de aire, una voz --- no da una
frecuencia sola: da la suya y además múltiplos enteros de la suya. Ese
apilado es lo único que separa a un violín de una flauta tocando la misma
nota, y es lo que este módulo deja tocar por separado.

Qué hay acá
-----------
* :class:`Partial` --- un armónico y lo que se le puede hacer: apagarlo,
  amplificarlo o correrlo de su frecuencia exacta.
* :class:`Spectrum` --- la nota entera: una fundamental y sus armónicos, más
  la modulación que los afecta a todos.
* :data:`PRESETS` --- las recetas clásicas. Una onda cuadrada no es una forma
  de onda distinta: es la **misma** serie con otras alturas de barra.
* :func:`render` y :func:`play` --- síntesis, con las mismas restricciones
  que el resto del programa: escrita a mano, 44100 Hz, sin librerías.

Este módulo no sabe dibujar y no importa nada de la interfaz. Lo que la
pantalla pinta y lo que el sintetizador suma salen los dos de
:func:`sounding`, así que el gráfico no puede mentir sobre lo que se
escucha: es literalmente la misma lista.
"""

from __future__ import annotations

import math
import os
import struct
import tempfile
import threading
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .audio import SAMPLE_RATE, _play_file, midi_to_frequency, write_wav

#: Cuántos armónicos se ofrecen. Doce llega hasta la tercera octava de la
#: serie, que es donde se termina de ver lo interesante: el séptimo que no
#: entra en ninguna escala y el undécimo que no es ni cuarta ni tritono. Más
#: barras no agregan nada y dejan el gráfico ilegible.
PARTIAL_COUNT = 12

#: Rango de la fundamental que ofrece el experimentador, en MIDI. Dos
#: octavas desde el do grave: por debajo los armónicos agudos se amontonan
#: contra el borde del gráfico y por encima el cuarto ya se va del oído
#: cómodo de unos parlantes de escritorio.
LOWEST_MIDI = 48
HIGHEST_MIDI = 72

#: Cuánto se puede correr un armónico de su lugar exacto, en cents (un cent
#: es la centésima parte de un semitono). Medio semitono para cada lado
#: alcanza para oír todo: unos pocos cents ya dan pulsaciones, y a cincuenta
#: el armónico dejó de pertenecer a la nota.
MAX_SHIFT_CENTS = 50.0

#: El tope de amplificación de un armónico suelto. Cuatro veces: suficiente
#: para sacar de abajo de la alfombra a un armónico agudo que en la receta
#: original vale una centésima.
MAX_GAIN = 4.0


def cents_ratio(cents: float) -> float:
    """El factor de frecuencia que corresponde a un desvío en cents."""
    return 2.0 ** (cents / 1200.0)


@dataclass
class Partial:
    """
    Un armónico de la serie y lo que el usuario le hizo.

    ``number`` es el orden: 1 es la fundamental, 2 el primer armónico, y su
    frecuencia es ``number`` veces la de la fundamental. ``gain`` es la
    altura de la barra --- lo que se oye --- y ``shift`` la corre de su
    múltiplo exacto, que es lo que la vuelve inarmónica.
    """

    number: int
    gain: float = 0.0
    #: Desvío respecto del múltiplo exacto, en cents.
    shift: float = 0.0
    muted: bool = False

    def frequency(self, fundamental: float) -> float:
        """Su frecuencia, ya corrida."""
        return fundamental * self.number * cents_ratio(self.shift)


@dataclass
class Spectrum:
    """Una nota entera: la fundamental, sus armónicos y la modulación."""

    midi: int = 57                       # la3
    partials: List[Partial] = field(default_factory=list)
    #: Qué armónico está aislado. ``0`` es ninguno: suenan todos.
    solo: int = 0
    #: Vibrato: cuánto oscila la afinación de todo el conjunto, en cents, y
    #: a qué velocidad. Es una modulación de frecuencia y mueve la serie
    #: entera, porque en un instrumento de verdad la mano mueve la cuerda y
    #: no un armónico suyo.
    vibrato_cents: float = 0.0
    vibrato_hz: float = 5.5
    #: Trémolo: cuánto oscila el volumen, de 0 a 1, y a qué velocidad.
    tremolo_depth: float = 0.0
    tremolo_hz: float = 5.0

    @property
    def fundamental(self) -> float:
        """La frecuencia de la fundamental, en hercios."""
        return midi_to_frequency(self.midi)

    def partial(self, number: int) -> Optional[Partial]:
        for item in self.partials:
            if item.number == number:
                return item
        return None


# ---------------------------------------------------------------------------
# Las recetas
# ---------------------------------------------------------------------------
#
# Una "forma de onda" no es otra cosa que qué altura tiene cada barra. Es la
# idea central del capítulo de física del libro y por eso las recetas están
# escritas como fórmulas y no como tablas de números: la fórmula **es** la
# explicación.

def _sine(n: int) -> float:
    return 1.0 if n == 1 else 0.0


def _saw(n: int) -> float:
    """Todos los armónicos, cada uno la enésima parte del anterior."""
    return 1.0 / n


def _square(n: int) -> float:
    """Sólo los impares. De ahí sale lo hueco del clarinete."""
    return 1.0 / n if n % 2 else 0.0


def _triangle(n: int) -> float:
    """Impares también, pero cayendo con el cuadrado: mucho más suave."""
    return 1.0 / (n * n) if n % 2 else 0.0


def _plucked(n: int) -> float:
    """La receta que usa el botón «Escuchar» del programa."""
    return {1: 1.0, 2: 0.32, 3: 0.14}.get(n, 0.0)


def _clarinet(n: int) -> float:
    """Impares fuertes y pares apenas insinuados: un tubo tapado."""
    return (1.0 / n) if n % 2 else (0.08 / n)


def _organ(n: int) -> float:
    """Un registro de órgano: la fundamental y sus octavas."""
    return {1: 1.0, 2: 0.55, 4: 0.30, 8: 0.16}.get(n, 0.0)


def _voice(n: int) -> float:
    """
    Una vocal: la serie con un formante, que es una zona reforzada.

    La garganta no atenúa parejo. Refuerza una banda fija de frecuencias
    --- eso es un formante --- y por eso una «a» y una «i» cantadas en la
    misma nota tienen la misma serie con distintas barras levantadas.
    """
    base = 1.0 / n
    if 3 <= n <= 5:
        base *= 2.4
    return base


#: Nombre visible -> qué amplitud tiene cada armónico.
PRESETS: Tuple[Tuple[str, Callable[[int], float]], ...] = (
    ("Seno puro", _sine),
    ("Diente de sierra", _saw),
    ("Cuadrada", _square),
    ("Triangular", _triangle),
    ("Cuerda pulsada", _plucked),
    ("Clarinete", _clarinet),
    ("Órgano", _organ),
    ("Voz cantada", _voice),
)

PRESET_NAMES: Tuple[str, ...] = tuple(name for name, _recipe in PRESETS)

#: Con cuál se abre. El diente de sierra es el único que trae los doce
#: armónicos encendidos, así que es el que muestra la serie completa: abrir
#: en un seno puro sería abrir en un gráfico de una sola barra.
DEFAULT_PRESET = "Diente de sierra"


def build(preset: str = DEFAULT_PRESET, midi: int = 57) -> Spectrum:
    """Una nota nueva, armada con una de las recetas."""
    recipe = dict(PRESETS).get(preset, _saw)
    return Spectrum(midi=midi,
                    partials=[Partial(n, recipe(n))
                              for n in range(1, PARTIAL_COUNT + 1)])


def apply_preset(spectrum: Spectrum, preset: str) -> None:
    """
    Reescribir las amplitudes sin tocar nada más.

    Lo apagado, lo corrido y lo aislado se conservan a propósito: cambiar de
    receta es una pregunta sobre el timbre --- «¿y si esto mismo fuera una
    cuadrada?» --- y devolver todo lo demás a cero convertiría al selector
    en un botón de reiniciar con ocho nombres.
    """
    recipe = dict(PRESETS).get(preset)
    if recipe is None:
        return
    for item in spectrum.partials:
        item.gain = recipe(item.number)


# ---------------------------------------------------------------------------
# Qué suena de verdad
# ---------------------------------------------------------------------------

def sounding(spectrum: Spectrum) -> List[Tuple[Partial, float, float]]:
    """
    Los armónicos que se escuchan: ``(armónico, frecuencia, amplitud)``.

    El aislado gana sobre todo lo demás --- para eso está --- y lo apagado y
    lo que quedó en cero no entra.

    **Ésta es la única lista.** La dibuja el gráfico y la suma el
    sintetizador, así que una barra que se ve es una barra que suena. Con
    dos recorridos distintos, cualquier regla nueva ---el aislado fue una---
    entra en uno solo y el experimento deja de probar nada.
    """
    out: List[Tuple[Partial, float, float]] = []
    base = spectrum.fundamental
    for item in spectrum.partials:
        if spectrum.solo and item.number != spectrum.solo:
            continue
        if item.muted or item.gain <= 0.0:
            continue
        out.append((item, item.frequency(base), item.gain))
    return out


def peak_gain(spectrum: Spectrum) -> float:
    """La barra más alta, o 1.0 si no quedó ninguna. Para escalar el eje."""
    heights = [gain for _p, _f, gain in sounding(spectrum)]
    return max(heights) if heights else 1.0


def nearest_note(frequency: float) -> Tuple[int, float]:
    """
    Qué nota temperada le queda más cerca, y a cuántos cents.

    Es la mitad del asunto del experimentador: el séptimo armónico cae
    treinta y un cents por debajo de la séptima menor del piano y el quinto
    catorce por debajo de la tercera mayor. Esos números son toda la
    discusión sobre afinación, y acá se leen directamente.
    """
    if frequency <= 0.0:
        return 0, 0.0
    exact = 69.0 + 12.0 * math.log2(frequency / 440.0)
    midi = int(round(exact))
    return midi, (exact - midi) * 100.0


# ---------------------------------------------------------------------------
# La serie subarmónica
# ---------------------------------------------------------------------------

def undertones(frequency: float, count: int = PARTIAL_COUNT) -> List[float]:
    """
    La serie subarmónica: la misma división, hacia abajo.

    No la produce ningún cuerpo vibrando por su cuenta --- de ahí que el
    libro la trate como una teoría y no como un hecho ---, pero el cálculo
    es exactamente el espejo del otro: dividir en vez de multiplicar. Vive
    acá y no en el libro porque los números los tiene que dibujar la
    pantalla y una lista escrita a mano se desincroniza.
    """
    return [frequency / n for n in range(1, max(1, count) + 1)]


# ---------------------------------------------------------------------------
# Síntesis
# ---------------------------------------------------------------------------

#: Cuánto dura una nota del experimentador. Larga a propósito: un armónico
#: corrido dos cents produce una pulsación cada medio segundo, y en un
#: pluck de medio segundo eso no se llega a oír.
SECONDS = 2.6

#: Ataque y caída, en segundos. El ataque evita el chasquido de arrancar en
#: medio ciclo; la caída evita el corte seco del final.
ATTACK = 0.02
RELEASE = 0.35

#: Techo de mezcla. Doce armónicos amplificados al máximo suman mucho más
#: que uno, así que la mezcla se normaliza abajo en vez de recortarse.
CEILING = 0.82


def render(spectrum: Spectrum, seconds: float = SECONDS) -> bytes:
    """
    La nota entera a PCM de 16 bits, mono.

    Con fase corriendo y no con una llamada a ``sin`` por muestra y por
    armónico: doce armónicos por dos segundos y medio son un millón y medio
    de puntos, y hacer la trigonometría entera en cada uno tarda lo
    suficiente como para que el botón parezca colgado.

    El vibrato es la excepción y no se puede evitar: mover la afinación es
    mover el incremento de fase, así que ahí la fase avanza distinto en cada
    muestra. La oscilación se calcula **una vez por muestra** y la comparten
    todos los armónicos, que es lo que la deja barata.
    """
    voices = sounding(spectrum)
    total = max(1, int(seconds * SAMPLE_RATE))
    buffer = [0.0] * total
    if not voices:
        return _encode(buffer)

    # La envolvente y las dos oscilaciones, una sola vez para toda la nota.
    attack = max(1, int(ATTACK * SAMPLE_RATE))
    release = max(1, int(RELEASE * SAMPLE_RATE))
    envelope = [1.0] * total
    for index in range(attack):
        envelope[index] = index / attack
    for index in range(release):
        position = total - release + index
        if position >= 0:
            envelope[position] *= 1.0 - index / release

    vibrato = spectrum.vibrato_cents
    tremolo = max(0.0, min(1.0, spectrum.tremolo_depth))
    bend: Optional[List[float]] = None
    if vibrato > 0.0:
        step = 2.0 * math.pi * spectrum.vibrato_hz / SAMPLE_RATE
        bend = [cents_ratio(vibrato * math.sin(step * i)) for i in range(total)]
    pulse: Optional[List[float]] = None
    if tremolo > 0.0:
        step = 2.0 * math.pi * spectrum.tremolo_hz / SAMPLE_RATE
        pulse = [0.5 - 0.5 * math.cos(step * i) for i in range(total)]

    for _item, frequency, gain in voices:
        increment = 2.0 * math.pi * frequency / SAMPLE_RATE
        angle = 0.0
        if bend is None and pulse is None:
            for index in range(total):
                buffer[index] += gain * math.sin(angle) * envelope[index]
                angle += increment
            continue
        for index in range(total):
            level = gain * envelope[index]
            if pulse is not None:
                level *= 1.0 - tremolo * pulse[index]
            buffer[index] += level * math.sin(angle)
            angle += increment * (bend[index] if bend is not None else 1.0)

    return _encode(buffer)


def _encode(buffer: Sequence[float]) -> bytes:
    """
    Llevar la mezcla al techo y empaquetar.

    Se normaliza y no se recorta, en las dos direcciones.

    Hacia abajo, porque una mezcla recortada le agrega armónicos que nadie
    pidió --- precisamente lo que el usuario está tratando de mirar.

    Y hacia arriba, porque aislar es lo primero que se hace acá y el
    duodécimo armónico de un diente de sierra vale ocho centésimas: sonaba
    tan bajo que aislarlo se parecía a haberlo apagado. Lo que se pierde es
    que amplificar suene más fuerte, y no importa: el volumen no es el
    experimento. Amplificar un armónico sigue cambiando lo que se oye,
    porque cambia su peso contra los demás, que es de lo que está hecho un
    timbre.
    """
    highest = max((abs(value) for value in buffer), default=0.0)
    scale = (CEILING / highest) if highest > 0.0 else 1.0
    frames = bytearray()
    for value in buffer:
        sample = value * scale
        sample = -1.0 if sample < -1.0 else (1.0 if sample > 1.0 else sample)
        frames += struct.pack("<h", int(sample * 32767))
    return bytes(frames)


def play(spectrum: Spectrum, seconds: float = SECONDS,
         on_finished: Optional[Callable[[], None]] = None) -> threading.Thread:
    """
    Sintetizar y tocar en un hilo aparte, como el resto del programa.

    Se le pasa una copia del espectro: el usuario puede mover un deslizador
    mientras suena, y sintetizar sobre el objeto vivo daría una nota que
    cambia de timbre en el medio según lo rápido que se mueva la mano.
    """
    frozen = replace(spectrum, partials=[replace(p) for p in spectrum.partials])

    def work() -> None:
        path = ""
        try:
            frames = render(frozen, seconds)
            handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            path = handle.name
            handle.close()
            write_wav(path, frames)
            _play_file(path)
        except Exception:                                   # noqa: BLE001
            pass
        finally:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
            if on_finished is not None:
                on_finished()

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# El timbre, en un archivo que otro programa pueda tocar
# ---------------------------------------------------------------------------
#
# Un WAV suelto no es un instrumento: es un sonido que dura lo que dura. Lo
# que convierte un archivo en el timbre de un instrumento es el trozo
# `smpl` --- la parte del formato que dice **qué nota es** la que está
# grabada y **qué tramo se repite** mientras la tecla siga apretada. Con eso
# adentro, el mismo archivo que acá se escucha una vez pasa a sonar en
# cualquier sampler (TX16Wx, Kontakt, HALion, el AudioFileProcessor de LMMS,
# el Simpler de Live, Polyphone para armar un SoundFont) afinado en el resto
# del teclado y sostenido todo lo que haga falta.
#
# El bucle es la parte delicada. Que no se oiga el empalme exige que el
# tramo repetido sea **exactamente periódico**: cada componente tiene que
# entrar en él un número entero de veces. Por eso acá cada frecuencia se
# acomoda al múltiplo más cercano de `1/duración del bucle`, y el vibrato se
# escribe como modulación de fase y no como una frecuencia que se estira ---
# estirando la frecuencia, la fase acumulada al terminar la vuelta no es la
# misma con la que empezó y el empalme chasquea.
#
# El desvío que introduce ese acomodamiento es de centésimas de cent: menos
# de lo que afina un oído y mil veces menos que el corrimiento más chico que
# el experimentador deja pedir.

#: Cuánto dura, más o menos, el tramo que se repite. Dos segundos son
#: suficientes para que las pulsaciones de un armónico corrido se oigan
#: dentro del bucle en vez de aparecer sólo al empalmar.
SAMPLE_SECONDS = 2.0

#: El ataque va **antes** del bucle y la caída **después**: lo que se repite
#: tiene que estar a volumen parejo, o cada vuelta subiría un poco más.
SAMPLE_ATTACK = 0.014
SAMPLE_TAIL = 0.30


def _loop_frames(fundamental: float, seconds: float) -> int:
    """Cuántas muestras dura el bucle, cerrando un ciclo entero de la nota."""
    cycles = max(1, int(round(seconds * fundamental)))
    return max(2, int(round(cycles * SAMPLE_RATE / fundamental)))


def render_sample(spectrum: Spectrum,
                  seconds: float = SAMPLE_SECONDS) -> Tuple[bytes, int, int]:
    """
    El timbre como muestra de sampler: PCM y dónde empieza y termina el bucle.

    Devuelve ``(frames, comienzo, final)``, los dos últimos en muestras.
    """
    voices = sounding(spectrum)
    loop = _loop_frames(spectrum.fundamental, seconds)
    attack = max(1, int(SAMPLE_ATTACK * SAMPLE_RATE))
    tail = max(1, int(SAMPLE_TAIL * SAMPLE_RATE))
    total = attack + loop + tail
    buffer = [0.0] * total
    if not voices:
        return _encode(buffer), attack, attack + loop - 1

    period = loop / SAMPLE_RATE          # lo que dura una vuelta, en segundos
    step = 2.0 * math.pi / loop

    tremolo = max(0.0, min(1.0, spectrum.tremolo_depth))
    pulse: Optional[List[float]] = None
    if tremolo > 0.0:
        turns = max(1, int(round(spectrum.tremolo_hz * period)))
        pulse = [0.5 - 0.5 * math.cos(step * turns * i) for i in range(total)]

    vibrato = spectrum.vibrato_cents
    wobble: Optional[List[float]] = None
    depth_hz = 0.0
    if vibrato > 0.0:
        turns = max(1, int(round(spectrum.vibrato_hz * period)))
        depth_hz = turns / period        # la velocidad ya acomodada
        wobble = [math.sin(step * turns * i) for i in range(total)]

    for _item, frequency, gain in voices:
        cycles = max(1, int(round(frequency * period)))
        increment = step * cycles
        # El vibrato, escrito como fase: el índice de modulación es la
        # desviación de frecuencia dividida por la velocidad del vibrato,
        # que es la equivalencia de manual entre mover la afinación y mover
        # la fase. Escrito así el bucle cierra exacto.
        index = (0.0 if wobble is None
                 else (cycles / period) * (cents_ratio(vibrato) - 1.0) / depth_hz)
        for position in range(total):
            angle = increment * position
            if wobble is not None:
                angle += index * wobble[position]
            level = gain
            if pulse is not None:
                level *= 1.0 - tremolo * pulse[position]
            buffer[position] += level * math.sin(angle)

    for position in range(attack):
        buffer[position] *= position / attack
    for position in range(tail):
        buffer[attack + loop + position] *= 1.0 - position / tail

    return _encode(buffer), attack, attack + loop - 1


def write_instrument(path: str, spectrum: Spectrum,
                     seconds: float = SAMPLE_SECONDS) -> Tuple[int, int]:
    """
    Escribir el timbre como muestra afinada y con bucle.

    A mano, como todo lo que este programa escribe: el módulo ``wave`` de la
    biblioteca estándar sabe escribir ``fmt`` y ``data`` y nada más, y lo
    que convierte el archivo en un instrumento es justamente el tercer
    trozo.
    """
    frames, start, end = render_sample(spectrum, seconds)
    fmt = struct.pack("<HHIIHH", 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16)
    smpl = struct.pack(
        "<9I", 0, 0, int(round(1e9 / SAMPLE_RATE)), spectrum.midi, 0, 0, 0,
        1, 0) + struct.pack("<6I", 0, 0, start, end, 0, 0)
    chunks = (b"fmt " + struct.pack("<I", len(fmt)) + fmt
              + b"data" + struct.pack("<I", len(frames)) + frames
              + b"smpl" + struct.pack("<I", len(smpl)) + smpl)
    with open(path, "wb") as handle:
        handle.write(b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE")
        handle.write(chunks)
    return start, end
