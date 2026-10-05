# -*- coding: utf-8 -*-
"""
Con qué suena el programa cuando toca música.

Todas las notas que el programa reproduce ---los resultados de los tres
modos, la melodía dibujada, el historial, el analizador, las piezas del
sendero--- pasan por :func:`mix`. Es el único lugar donde una altura y una
duración se convierten en una onda, así que cambiar de timbre es cambiar
de receta y no recorrer cinco pantallas buscando dónde se suma un seno.

No pasan por acá los ruidos del ambiente ni los de las cinemáticas
(`ambience.py`): no son notas de la pieza, son la habitación donde suena.
Tampoco el experimentador de armónicos, que sintetiza su propio espectro
porque ahí el timbre **es** el experimento.

Qué hay
-------
* Las recetas sintetizadas (:data:`TIMBRES`): la cuerda pulsada de siempre,
  cuatro más que suenan distinto entre sí y una que no sirve para nada.
* Un lector de WAV escrito a mano (:func:`read_sample`) que entiende el
  trozo ``smpl`` ---qué nota representa la muestra y qué tramo se repite---,
  que es exactamente lo que escribe `harmonics.write_instrument`. Con eso el
  timbre que alguien armó en el experimentador pasa a tocar las piezas.
* La sonoridad (:func:`loudness`): cada timbre se lleva al mismo volumen
  **percibido** que el de siempre. Cambiar de timbre no puede ser cambiar de
  volumen, y medido por pico no alcanza: un órgano sostenido y una cuerda
  que se apaga pueden tener el mismo pico y sonar uno el doble que la otra.

Este módulo no importa nada de la interfaz ni de `audio.py` (es al revés:
`audio` lo importa a él), y no levanta excepciones al sintetizar. Lo único
que puede fallar es leer un archivo, y eso falla con :class:`TimbreError`,
que trae el mensaje listo para mostrar.
"""

from __future__ import annotations

import math
import operator
import os
import random
import struct
import sys
import threading
from array import array
from dataclasses import dataclass, field
from itertools import accumulate, repeat
from typing import Dict, List, Optional, Sequence, Tuple

from engine.i18n import N, trf

#: La frecuencia de muestreo de todo el sonido del programa. Vive acá y no en
#: `audio.py` porque `audio` importa este módulo: al revés sería circular.
#: `audio.SAMPLE_RATE` es este mismo número.
SAMPLE_RATE = 44100

#: El largo de las tablas de onda. Una potencia de dos para que dar la
#: vuelta sea un ``&`` y no un módulo; 4096 puntos leídos sin interpolar
#: dejan el error de cuantización unos sesenta decibeles abajo, que es menos
#: de lo que se oye por los parlantes de una computadora con cuatro voces
#: sonando encima.
TABLE_SIZE = 4096
_MASK = TABLE_SIZE - 1

#: Por encima de esto un armónico ya no se escribe: pasado Nyquist se
#: reflejaría y aparecería como una nota grave que nadie tocó.
_HIGHEST = 0.45 * SAMPLE_RATE


class TimbreError(Exception):
    """Un archivo que no se puede usar como timbre. El mensaje se muestra."""


# ---------------------------------------------------------------------------
# Las recetas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Timbre:
    """Un timbre que se puede elegir: su clave, su nombre y una línea."""

    key: str
    #: Nombre visible, en castellano. Se traduce al dibujarlo.
    label: str
    #: Qué es, en una línea, para debajo del desplegable.
    blurb: str
    #: Cuántas versiones distintas tiene una misma nota. Las recetas
    #: normales son deterministas y tienen una sola; la flauta tiene varias
    #: porque un chico soplando no repite nunca el mismo error.
    variants: int = 1


#: La de siempre. Es la clave que se guarda en las preferencias cuando no se
#: eligió nada y la referencia de volumen de todas las demás.
DEFAULT = "pluck"

#: La que lee un archivo. No es una receta: sin archivo no suena.
SAMPLE = "sample"

TIMBRES: Tuple[Timbre, ...] = (
    Timbre("pluck", N("Cuerda pulsada"),
           N("El de siempre: tres armónicos y una caída. Seco a propósito, "
             "para seguir las voces de oído.")),
    Timbre("organ", N("Órgano"),
           N("Un registro lleno de tubos: la nota y sus octavas, sostenida "
             "sin caer. Deja oír cada voz entera hasta el acorde siguiente.")),
    Timbre("strings", N("Cuerdas frotadas"),
           N("Una fila de cuerdas con arco: entrada suave, vibrato que llega "
             "tarde y dos instrumentos apenas desafinados entre sí.")),
    Timbre("harpsichord", N("Clave"),
           N("Una cuerda pellizcada cerca del borde: brillo al atacar que se "
             "apaga rápido y un cuerpo que sigue sonando.")),
    Timbre("choir", N("Coro «aah»"),
           N("Tres cantantes por voz cantando una «a»: la vocal la dan los "
             "formantes, zonas fijas del espectro que refuerza la garganta.")),
    Timbre("recorder", N("Flauta dulce de la escuela"),
           N("Soplada de más, desafinada y con algún chillido. No sirve "
             "para nada y es exactamente así como sonaba."), variants=4),
    Timbre(SAMPLE, N("Muestra cargada (WAV)"),
           N("Un timbre guardado desde el experimentador de armónicos, o "
             "cualquier WAV: se lo lleva a cada nota y se repite su bucle "
             "mientras la nota dure.")),
)

_BY_KEY: Dict[str, Timbre] = {item.key: item for item in TIMBRES}

#: Las claves en el orden del desplegable.
KEYS: Tuple[str, ...] = tuple(item.key for item in TIMBRES)


def label_of(key: str) -> str:
    """El nombre castellano de un timbre; el de siempre si no existe."""
    return _BY_KEY.get(key, _BY_KEY[DEFAULT]).label


def key_for_label(label: str) -> str:
    """De vuelta: qué clave tiene un nombre castellano."""
    for item in TIMBRES:
        if item.label == label:
            return item.key
    return DEFAULT


def blurb_of(key: str) -> str:
    return _BY_KEY.get(key, _BY_KEY[DEFAULT]).blurb


# -- piezas de síntesis -----------------------------------------------------

def _frequency(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


_BASE: List[float] = [math.sin(2.0 * math.pi * i / TABLE_SIZE)
                      for i in range(TABLE_SIZE)]


def _table(amplitudes: Sequence[Tuple[int, float]]) -> List[float]:
    """
    Un ciclo de la onda, sumando armónicos.

    Se arma leyendo un seno ya calculado salteado ``k`` lugares en vez de
    llamar a ``sin`` por punto: el coro arma una tabla por altura y con la
    trigonometría entera cada una tardaba lo que tarda tocar media nota.

    Con muchos armónicos, cada uno arranca desfasado según la receta de
    Schroeder (``π·k·(k−1)/H``). Todos en fase cero se apilan en un pico
    angosto: la misma sonoridad con el doble de pico, y seis voces así
    llegaban al techo de la mezcla y bajaban la pieza entera. Para un sonido
    sostenido el oído no distingue la fase de los armónicos, así que no
    cambia el timbre; sólo deja de estorbar.
    """
    table = [0.0] * TABLE_SIZE
    count = max((number for number, _gain in amplitudes), default=1)
    spread = len(amplitudes) > 6
    for number, gain in amplitudes:
        if gain == 0.0:
            continue
        shift = (int(round(TABLE_SIZE * number * (number - 1) / (2.0 * count)))
                 if spread else 0)
        row = [gain * _BASE[(number * i + shift) & _MASK]
               for i in range(TABLE_SIZE)]
        table = list(map(operator.add, table, row))
    return table


_TABLES: Dict[tuple, List[float]] = {}
_TABLE_LOCK = threading.Lock()


def _cached_table(key: tuple, amplitudes) -> List[float]:
    """Las tablas viven mientras viva el programa: son pocas y caras."""
    with _TABLE_LOCK:
        table = _TABLES.get(key)
    if table is None:
        table = _table(amplitudes() if callable(amplitudes) else amplitudes)
        with _TABLE_LOCK:
            _TABLES[key] = table
    return table


def _fitting(frequency: float, most: int) -> int:
    """Cuántos armónicos entran debajo de Nyquist, hasta ``most``."""
    return max(1, min(most, int(_HIGHEST / max(frequency, 1.0))))


def _read(table: List[float], frequency: float, length: int,
          offsets: Optional[Sequence[float]] = None,
          phase: float = 0.0) -> List[float]:
    """
    Leer una tabla a una frecuencia, con la fase calculada y no acumulada.

    ``offsets`` corre la fase muestra por muestra ---en lugares de la tabla---
    y es como se escribe el vibrato: modulación de fase, la misma
    equivalencia que usa `harmonics.render_sample`. Sumando incrementos
    distintos en cada muestra habría que recorrer la nota en un bucle de
    Python; así es una sola comprensión.

    ``phase`` es desde dónde arranca. Ver :func:`_phase`.
    """
    step = TABLE_SIZE * frequency / SAMPLE_RATE
    if offsets is None:
        return [table[int(i * step + phase) & _MASK] for i in range(length)]
    return [table[int(i * step + o + phase) & _MASK]
            for i, o in zip(range(length), offsets)]


def _phase(midi: int, salt: int = 0) -> float:
    """
    Desde qué punto del ciclo arranca una nota: fijo por altura, no cero.

    Arrancando todas en cero, una octava entre dos voces suma sus armónicos
    comunes siempre igual ---en fase exacta, para siempre, porque la octava
    temperada es exactamente el doble---, y el volumen de un acorde pasaba
    a depender de qué octavas tenía. Un instrumento de verdad no arranca en
    ningún lugar en particular.
    """
    return float(((midi * 2654435761) + salt * 40503) % TABLE_SIZE)


def _decay(length: int, seconds: float) -> List[float]:
    """Una caída exponencial con constante de tiempo ``seconds``."""
    if length <= 0:
        return []
    ratio = math.exp(-1.0 / (max(seconds, 1e-4) * SAMPLE_RATE))
    return list(accumulate(repeat(ratio, length - 1), operator.mul,
                           initial=1.0))


def _held(seconds: float, length: int, attack: float,
          release: float) -> List[float]:
    """
    La envolvente de un sonido sostenido: entra, se queda y sale.

    Entrada y salida con medio coseno: una rampa recta arranca y termina
    con un quiebre que el oído toma como un clic, sobre todo en los graves.
    Después de la salida, silencio: el instrumento ya no suena aunque el
    lugar de la nota siga abierto para la cola de los pulsados.
    """
    rise = max(1, int(attack * SAMPLE_RATE))
    hold = max(rise, int(seconds * SAMPLE_RATE))
    fall = max(1, int(release * SAMPLE_RATE))
    shape = [0.5 - 0.5 * math.cos(math.pi * i / rise) for i in range(rise)]
    shape += [1.0] * (hold - rise)
    shape += [0.5 + 0.5 * math.cos(math.pi * i / fall) for i in range(fall)]
    if len(shape) < length:
        shape += [0.0] * (length - len(shape))
    return shape[:length]


#: La forma del vibrato, una por ``(velocidad, demora, fase)``: la más larga
#: que se pidió, y cada nota se lleva el principio. Antes iba una lista por
#: **largo** de nota, hasta sesenta y cinco, y no se soltaban nunca: con el
#: coro o las cuerdas sobre una pieza con muchas duraciones distintas eran
#: de decenas a cientos de megas retenidos. En `array` de dobles y no en
#: lista: ocho bytes por muestra en vez de treinta y dos.
_WOBBLES: Dict[tuple, array] = {}

#: Cuántas formas distintas se guardan. Las recetas de hoy usan cinco (dos
#: las cuerdas y tres el coro); el tope es para que una receta futura con
#: fases sueltas no la haga crecer sin fin.
_WOBBLE_SHAPES = 16

#: Hasta qué largo se guarda cada forma: una redonda lenta con su cola
#: entra. Lo que pase de acá ---una pedal de varios compases--- se calcula
#: cada vez y no se guarda, y así la caché entera queda en unos pocos megas
#: sin importar qué se toque.
_WOBBLE_KEPT = int(4.0 * SAMPLE_RATE)


def _wobble_span(rate: float, delay: float, phase: float, start: int,
                 stop: int):
    """Las muestras ``start..stop`` de la forma. La única cuenta."""
    step = 2.0 * math.pi * rate / SAMPLE_RATE
    ramp = max(1.0, delay * SAMPLE_RATE)
    return (min(1.0, i / ramp) * math.sin(step * i + phase)
            for i in range(start, stop))


def _wobble(rate: float, delay: float, length: int,
            phase: float = 0.0) -> Sequence[float]:
    """
    La forma del vibrato: un seno que llega de a poco.

    Un instrumentista no vibra desde el ataque: la nota sale derecha y el
    vibrato aparece después. Arrancando de golpe suena a sintetizador.
    """
    key = (rate, delay, phase)
    kept = min(length, _WOBBLE_KEPT)
    shape = _WOBBLES.get(key)
    if shape is None or len(shape) < kept:
        known = 0 if shape is None else len(shape)
        # Una copia que crece, y no la guardada estirada en su lugar: otro
        # hilo puede estar leyéndola.
        grown = array("d", shape if shape is not None else ())
        grown.extend(_wobble_span(rate, delay, phase, known, kept))
        if shape is None and len(_WOBBLES) >= _WOBBLE_SHAPES:
            _WOBBLES.clear()
        _WOBBLES[key] = grown
        shape = grown
    out = shape[:kept]
    if length > kept:
        out.extend(_wobble_span(rate, delay, phase, kept, length))
    return out


def _vibrato(frequency: float, cents: float, rate: float, delay: float,
             length: int, phase: float = 0.0) -> List[float]:
    """
    El vibrato como corrimiento de fase, en lugares de la tabla.

    La frecuencia que oscila ``Δf`` alrededor de ``f`` a ``r`` vueltas por
    segundo es, escrita como fase, un seno de amplitud ``Δf / (2π r)``
    ciclos. Por eso la profundidad crece con la altura: el vibrato se mide
    en cents, no en hercios.
    """
    deviation = frequency * (2.0 ** (cents / 1200.0) - 1.0)
    depth = TABLE_SIZE * deviation / (2.0 * math.pi * rate)
    return [depth * v for v in _wobble(rate, delay, length, phase)]


_NOISE: List[float] = []


def _noise() -> List[float]:
    """
    Un segundo de soplido, siempre el mismo.

    Ruido blanco derivado una vez ---la diferencia entre muestras vecinas---,
    que se lleva los graves y deja el siseo del aire. Sembrado fijo: dos
    reproducciones de la misma pieza suenan iguales.
    """
    if not _NOISE:
        rng = random.Random(1717)
        white = [rng.uniform(-1.0, 1.0) for _ in range(SAMPLE_RATE + 1)]
        # Armada aparte y puesta de una vez: dos sonidos que arrancan juntos
        # en hilos distintos leían la lista a medio llenar.
        ready = [0.5 * (white[i + 1] - white[i]) for i in range(SAMPLE_RATE)]
        if not _NOISE:
            _NOISE[:] = ready
    return _NOISE


def _times(a: List[float], b: Sequence[float]) -> List[float]:
    return list(map(operator.mul, a, b))


def _plus(a: List[float], b: Sequence[float]) -> List[float]:
    return list(map(operator.add, a, b))


# -- las recetas, una por una ------------------------------------------------

def _pluck(midi: int, seconds: float, length: int, _variant: int) -> List[float]:
    """
    La de siempre, igual que antes de que hubiera otras.

    Fundamental, un poco de segundo y tercer armónico y una caída que se
    estira con la nota. Una sinusoide pelada suena a señal de prueba y
    cuesta separar las voces; esto alcanza para que el oído las siga.
    """
    table = _cached_table(("pluck",), ((1, 1.0), (2, 0.32), (3, 0.14)))
    tone = _read(table, _frequency(midi), length, phase=_phase(midi))
    shape = _decay(length, max(seconds, 0.05) / 2.2)
    rise = min(length, int(0.012 * SAMPLE_RATE))
    for i in range(rise):
        shape[i] *= i / (0.012 * SAMPLE_RATE)
    return _times(tone, shape)


#: El registro del órgano: principal de 8', octava de 4', quinta de 2⅔',
#: lleno de 2' y un poco de mixtura arriba. Pesos de oído.
_ORGAN = ((1, 1.0), (2, 0.62), (3, 0.30), (4, 0.36), (5, 0.05), (6, 0.15),
          (8, 0.16), (10, 0.04), (12, 0.06))


def _organ(midi: int, seconds: float, length: int, _variant: int) -> List[float]:
    """
    Un tubo de órgano: entra, se queda quieto y sale.

    Sin vibrato y sin caída: un órgano sostiene exactamente igual hasta que
    se suelta la tecla, y eso es lo que lo hace bueno para oír conducción de
    voces --- cada voz se escucha entera hasta que se mueve.
    """
    frequency = _frequency(midi)
    count = _fitting(frequency, 12)
    table = _cached_table(("organ", count),
                          tuple(p for p in _ORGAN if p[0] <= count))
    tone = _read(table, frequency, length, phase=_phase(midi))
    return _times(tone, _held(seconds, length, 0.03, 0.08))


def _strings(midi: int, seconds: float, length: int, _variant: int) -> List[float]:
    """
    Dos cuerdas frotadas al unísono, apenas desafinadas entre sí.

    El arco da una onda en diente de sierra ---todos los armónicos, cada
    uno más débil que el anterior---; un poco más apagada que la de manual
    para que no suene a sintetizador. Dos copias a seis cents de distancia
    y con vibratos a distinta velocidad hacen la fila: una sola suena a un
    instrumento solista y bastante pobre.
    """
    frequency = _frequency(midi)
    count = _fitting(frequency, 18)
    table = _cached_table(
        ("strings", count),
        lambda: tuple((n, (1.15 if 2 <= n <= 4 else 1.0) / n ** 1.15)
                      for n in range(1, count + 1)))
    low = frequency * 2.0 ** (-6.0 / 1200.0)
    high = frequency * 2.0 ** (6.0 / 1200.0)
    first = _read(table, low, length,
                  _vibrato(low, 11.0, 5.3, 0.35, length), _phase(midi))
    second = _read(table, high, length,
                   _vibrato(high, 11.0, 5.9, 0.42, length, phase=1.7),
                   _phase(midi, 1))
    tone = _plus(first, second)
    return _times(tone, _held(seconds, length, 0.13, 0.24))


#: Dónde pellizca el clave: cerca del borde de la cuerda, que es lo que le
#: da tantos armónicos agudos. El armónico que tiene un nodo justo en el
#: punto pellizcado no suena, y de ahí sale el color.
_PLUCK_POINT = 0.11


def _harpsichord(midi: int, seconds: float, length: int,
                 _variant: int) -> List[float]:
    """
    Un clave en dos capas: el brillo del pellizco y el cuerpo de la cuerda.

    Una cuerda de verdad apaga sus armónicos agudos mucho antes que la
    fundamental. Eso, escrito armónico por armónico, son veinte senos por
    muestra; partido en dos capas con su propia caída ---una brillante que
    muere en décimas y una redonda que sigue--- se oye igual y cuesta dos.
    Los graves sostienen más que los agudos, como en el instrumento.
    Al soltar, el apagador corta en un par de centésimas.
    """
    frequency = _frequency(midi)
    count = _fitting(frequency, 30)
    bright = _cached_table(
        ("harpsichord", count),
        lambda: tuple((n, abs(math.sin(math.pi * n * _PLUCK_POINT)) / n ** 0.6)
                      for n in range(1, count + 1)))
    body = _cached_table(("harpsichord-body",),
                         ((1, 1.0), (2, 0.45), (3, 0.22), (4, 0.10)))
    scale = (220.0 / frequency)
    shine = _times(_read(bright, frequency, length, phase=_phase(midi)),
                   _decay(length, 0.11 * scale ** 0.25))
    ring = _times(_read(body, frequency, length, phase=_phase(midi, 1)),
                  _decay(length, 1.7 * scale ** 0.35))
    tone = [0.8 * a + 0.55 * b for a, b in zip(shine, ring)]
    # El pellizco: unos milisegundos de ruido, que es el plectro.
    click = min(length, int(0.006 * SAMPLE_RATE))
    hiss = _noise()
    for i in range(click):
        tone[i] += 0.3 * hiss[(midi * 977 + i) % SAMPLE_RATE] * (1.0 - i / click)
    # El apagador, al soltar la tecla.
    stop = int(seconds * SAMPLE_RATE)
    if stop < length:
        damper = _decay(length - stop, 0.03)
        tone[stop:] = _times(tone[stop:], damper)
    rise = min(length, int(0.0015 * SAMPLE_RATE))
    for i in range(rise):
        tone[i] *= i / max(1, rise)
    return tone


#: Los formantes de una «a» cantada: centro, ancho y cuánto refuerza cada
#: uno. Promedio entre voces de hombre y de mujer, que es lo que hace un coro.
_FORMANTS = ((750.0, 110.0, 1.0), (1150.0, 130.0, 0.55),
             (2700.0, 190.0, 0.22), (3500.0, 260.0, 0.10))


def _vowel(frequency: float) -> Tuple[Tuple[int, float], ...]:
    """
    La serie de la garganta pasada por la boca abierta en «a».

    La fuente cae parejo con la altura del armónico; los formantes no se
    mueven con la nota. Por eso un bajo y una soprano cantando la misma
    vocal tienen barras distintas, y por eso esta tabla se arma por altura.
    """
    out = []
    count = _fitting(frequency, 48)
    for n in range(1, count + 1):
        hz = n * frequency
        if hz > 6000.0:
            break
        lift = 0.06
        for centre, width, gain in _FORMANTS:
            lift += gain / math.sqrt(1.0 + ((hz - centre) / (0.5 * width)) ** 2)
        out.append((n, lift / n))
    return tuple(out)


#: Los tres cantantes de cada voz: cuánto se desafina cada uno, a qué
#: velocidad vibra y desde qué fase. Distintos a propósito: tres vibratos
#: iguales se suman y suenan a uno solo más fuerte.
_SINGERS = ((-9.0, 4.8, 0.0), (1.0, 5.3, 2.1), (8.0, 5.9, 4.2))


def _choir(midi: int, seconds: float, length: int, _variant: int) -> List[float]:
    """Tres voces cantando «aah», con su vocal y su vibrato cada una."""
    frequency = _frequency(midi)
    table = _cached_table(("choir", midi), lambda: _vowel(frequency))
    tone = [0.0] * length
    for singer, (cents, rate, phase) in enumerate(_SINGERS):
        sung = frequency * 2.0 ** (cents / 1200.0)
        tone = _plus(tone, _read(table, sung, length,
                                 _vibrato(sung, 16.0, rate, 0.28, length,
                                          phase), _phase(midi, singer)))
    return _times(tone, _held(seconds, length, 0.16, 0.30))


#: La flauta dulce: casi un seno, con el tercer armónico que le da lo hueco.
_RECORDER = ((1, 1.0), (2, 0.10), (3, 0.20), (4, 0.02), (5, 0.06))

#: Cada cuántas muestras se recalcula el soplido. La afinación y el volumen
#: de un chico soplando no cambian más rápido que eso, y calcularlos
#: muestra por muestra triplicaba lo que tarda la nota.
_CONTROL = 32


def _recorder(midi: int, seconds: float, length: int,
              variant: int) -> List[float]:
    """
    La flauta dulce de la escuela, tocada por alguien de once años.

    Lo que la hace graciosa es lo mismo que la hacía insoportable en el
    acto del colegio, y cada cosa está escrita aparte:

    * **soplada de más**: suena alta, y cada nota se desafina para un lado
      distinto, porque la presión del aire es la afinación;
    * **la entrada**: la nota arranca abajo y sube hasta donde llega, que
      es lo que pasa cuando el aire tarda en ordenarse;
    * **el aire que se escapa**: un siseo encima de todo;
    * **el chillido**: de vez en cuando el soplido se pasa y la flauta salta
      una octava ---el famoso «piiii»--- antes de caer a la nota.

    Es determinista ---misma pieza, mismos chillidos--- pero no repite: la
    misma nota tiene cuatro versiones y el mezclador las va turnando.
    """
    rng = random.Random(midi * 1000003 + int(round(seconds * 1000)) * 31
                        + variant * 7919)
    frequency = _frequency(midi)
    table = _cached_table(("recorder",), _RECORDER)
    blown = 18.0 + rng.uniform(-40.0, 45.0)
    shaky = (rng.uniform(2.6, 3.6), rng.uniform(5.0, 6.5),
             rng.uniform(0.0, 6.28), rng.uniform(0.0, 6.28))
    squeaks: List[Tuple[float, float, float]] = []
    # Uno de cada diez ataques chilla, y alguna nota larga se escapa en el
    # medio. Más seguido deja de ser gracioso: con cuatro voces, cada
    # acorde tendría uno.
    if rng.random() < 0.1:
        squeaks.append((0.0, rng.uniform(0.07, 0.16),
                        1200.0 + rng.uniform(15.0, 70.0)))
    if seconds > 0.9 and rng.random() < 0.08:
        start = rng.uniform(0.3, seconds - 0.3)
        squeaks.append((start, start + rng.uniform(0.08, 0.15),
                        1200.0 + rng.uniform(15.0, 70.0)))

    def cents_at(t: float) -> float:
        value = (blown - 95.0 * math.exp(-t / 0.045)
                 + 9.0 * math.sin(2.0 * math.pi * shaky[0] * t + shaky[2])
                 + 6.0 * math.sin(2.0 * math.pi * shaky[1] * t + shaky[3]))
        for begin, end, jump in squeaks:
            if begin - 0.01 < t < end + 0.01:
                edge = min(1.0, (t - begin + 0.01) / 0.01,
                           (end + 0.01 - t) / 0.01)
                value += jump * edge
        return value

    def loud_at(t: float) -> float:
        level = (1.0 + 0.35 * math.exp(-t / 0.05)
                 + 0.12 * math.sin(2.0 * math.pi * 4.3 * t + shaky[3]))
        for begin, end, _jump in squeaks:
            if begin <= t <= end:
                level *= 1.45
        return level

    steps = length // _CONTROL + 1
    increments: List[float] = []
    levels: List[float] = []
    breath: List[float] = []
    step = TABLE_SIZE * frequency / SAMPLE_RATE
    for index in range(steps):
        t = index * _CONTROL / SAMPLE_RATE
        increments.append(step * 2.0 ** (cents_at(t) / 1200.0))
        levels.append(loud_at(t))
        breath.append(0.07 + 0.25 * math.exp(-t / 0.03))

    def spread(values: List[float]) -> List[float]:
        return [v for v in values for _ in _HOLD][:length]

    phases = accumulate(spread(increments), initial=_phase(midi))
    tone = _times([table[int(p) & _MASK] for p in phases], spread(levels))
    hiss = _noise()
    offset = rng.randrange(SAMPLE_RATE)
    air = (hiss[offset:] + hiss[:offset]) * (length // SAMPLE_RATE + 1)
    air = _times(air[:length], spread(breath))
    return _times(_plus(tone, air), _held(seconds, length, 0.02, 0.045))


_HOLD = range(_CONTROL)


_RECIPES = {
    "pluck": _pluck,
    "organ": _organ,
    "strings": _strings,
    "harpsichord": _harpsichord,
    "choir": _choir,
    "recorder": _recorder,
}


# ---------------------------------------------------------------------------
# Muestras: el timbre desde un archivo
# ---------------------------------------------------------------------------

#: Cuánto de un archivo se lee como mucho. Una muestra de sampler dura un
#: par de segundos; si alguien elige una canción entera, con esto alcanza
#: para tener un timbre y no se lleva la memoria de la máquina.
MAX_SECONDS = 8.0

#: La salida de una nota de muestra: medio coseno de este largo. Es lo que
#: hace que una muestra cortada en medio de su bucle no chasquee al soltar.
SAMPLE_RELEASE = 0.16

#: Cuando el archivo no dice qué nota es y no se la puede oír, se la toma
#: como el La de 440, que es la nota con la que se afina todo.
FALLBACK_ROOT = 69.0


@dataclass
class Sample:
    """
    Una muestra lista para tocar: mono, en flotantes y con su bucle.

    ``loop_end`` es **inclusivo**, como en el trozo ``smpl``: la última
    muestra que todavía pertenece al bucle. ``root`` es la nota MIDI que
    representa, con decimales cuando el archivo trae fracción o cuando la
    afinación se dedujo oyéndola.
    """

    path: str
    data: List[float]
    rate: int
    root: float
    loop_start: int
    loop_end: int
    #: Si el bucle y la nota vinieron del archivo o se dedujeron.
    from_smpl: bool = True
    #: El volumen que la iguala a la cuerda pulsada. Se mide la primera
    #: vez que suena, en el hilo del sonido.
    level: Optional[float] = field(default=None, repr=False)
    #: Lo que lee :func:`_sampled`, con el bucle para el que se armó.
    _source: Optional[Tuple[int, int, List[float]]] = field(
        default=None, init=False, repr=False, compare=False)

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def source(self) -> List[float]:
        """
        El sonido hasta el final del bucle, con una muestra de más.

        La de más es igual a la del comienzo del bucle: así la
        interpolación del último tramo cae sobre la vuelta y no sobre la
        cola. Se arma una vez por muestra: armándola en cada nota se
        copiaban hasta `MAX_SECONDS` de flotantes por cada altura distinta.
        Se vuelve a armar sólo si alguien movió el bucle.
        """
        built = self._source
        if built is None or built[:2] != (self.loop_start, self.loop_end):
            source = self.data[:self.loop_end + 1]
            source.append(self.data[self.loop_start])
            built = (self.loop_start, self.loop_end, source)
            self._source = built
        return built[2]


def _decode(body: bytes, tag: int, channels: int, bits: int,
            limit: int) -> List[float]:
    """Los cuadros de ``data`` a flotantes entre -1 y 1, mezclados a mono."""
    width = bits // 8
    frames = min(len(body) // (width * channels), limit)
    body = body[:frames * width * channels]
    if tag == 3 and bits in (32, 64):
        values = array("f" if bits == 32 else "d")
        values.frombytes(body)
        if sys.byteorder == "big":
            values.byteswap()
        scale = 1.0
    elif tag == 1 and bits == 8:
        values = [b - 128 for b in body]        # el de ocho es sin signo
        scale = 1.0 / 128.0
    elif tag == 1 and bits == 16:
        values = array("h")
        values.frombytes(body)
        if sys.byteorder == "big":
            values.byteswap()
        scale = 1.0 / 32768.0
    elif tag == 1 and bits == 24:
        values = [int.from_bytes(body[i:i + 3], "little", signed=True)
                  for i in range(0, len(body), 3)]
        scale = 1.0 / 8388608.0
    elif tag == 1 and bits == 32:
        values = array("i")
        values.frombytes(body)
        if sys.byteorder == "big":
            values.byteswap()
        scale = 1.0 / 2147483648.0
    else:
        raise TimbreError(trf(
            "El WAV está en un formato que no se puede leer ({bits} bits, "
            "codificación {tag}). Guardalo como PCM de 16 o 24 bits.",
            bits=bits, tag=tag))
    if channels == 1:
        return [v * scale for v in values]
    share = scale / channels
    return [sum(values[i:i + channels]) * share
            for i in range(0, len(values), channels)]


def read_sample(path: str) -> Sample:
    """
    Leer un WAV como muestra de sampler.

    A mano, como todo lo que el programa lee y escribe: el módulo ``wave``
    de la biblioteca estándar no sabe nada del trozo ``smpl``, que es justo
    lo que convierte un archivo en un instrumento ---qué nota es y qué tramo
    se repite---. Entiende PCM de 8, 16, 24 y 32 bits y flotante de 32 y
    64, en cualquier cantidad de canales (se mezclan a uno).

    Sin ``smpl`` ---un WAV cualquiera--- la nota se deduce oyéndola y se
    repite la segunda mitad, con el empalme fundido para que no chasquee.
    Cualquier cosa que no se pueda leer levanta :class:`TimbreError` con el
    motivo escrito para el usuario.
    """
    name = os.path.basename(path)
    try:
        with open(path, "rb") as handle:
            head = handle.read(12)
            if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
                raise TimbreError(trf("{name} no es un archivo WAV.", name=name))
            fmt, data, smpl = _read_chunks(handle)
    except OSError as exc:
        raise TimbreError(trf("No se pudo abrir {name}: {reason}", name=name,
                              reason=exc.strerror or str(exc))) from exc
    if fmt is None or len(fmt) < 16 or data is None:
        raise TimbreError(trf("{name} no trae sonido que se pueda leer.",
                              name=name))
    tag, channels, rate, _rate_bytes, _align, bits = struct.unpack_from(
        "<HHIIHH", fmt)
    if tag == 0xFFFE and len(fmt) >= 26:
        # WAVE_FORMAT_EXTENSIBLE: el formato de verdad son los dos primeros
        # bytes del GUID que viene al final.
        tag = struct.unpack_from("<H", fmt, 24)[0]
    if not (1 <= channels <= 8 and 4000 <= rate <= 384000 and bits % 8 == 0
            and bits):
        raise TimbreError(trf("{name} tiene un encabezado que no tiene "
                              "sentido.", name=name))
    samples = _decode(data, tag, channels, bits, int(MAX_SECONDS * rate))
    if len(samples) < max(64, rate // 50):
        raise TimbreError(trf("{name} es demasiado corto para sacarle un "
                              "timbre.", name=name))
    # Un WAV en flotante puede traer NaN o infinitos ---un programa que
    # exportó mal, un archivo dañado--- y se leía igual: el error saltaba
    # recién al tocar, en el hilo del sonido, cuando `audio.encode` pasa la
    # mezcla a enteros. Se mira después de mezclar a mono porque dos
    # canales enormes pueden sumar infinito.
    if not all(map(math.isfinite, samples)):
        raise TimbreError(trf("{name} trae valores que no son sonido "
                              "(infinitos o indefinidos). Volvé a exportarlo "
                              "desde el programa que lo hizo.", name=name))
    if max(abs(v) for v in samples) < 1e-4:
        raise TimbreError(trf("{name} está en silencio.", name=name))

    root: Optional[float] = None
    start = end = -1
    if smpl is not None and len(smpl) >= 36:
        unity, fraction = struct.unpack_from("<II", smpl, 12)
        loops = struct.unpack_from("<I", smpl, 28)[0]
        if unity <= 127:
            root = unity + fraction / 4294967296.0
        if loops and len(smpl) >= 36 + 24:
            start, end = struct.unpack_from("<II", smpl, 36 + 8)
    from_smpl = root is not None and 0 <= start < end < len(samples)
    if root is None:
        root = detect_root(samples, rate)
    if not (0 <= start < end < len(samples)):
        start, end = _seamless_half(samples, rate)
    return Sample(path=path, data=samples, rate=rate, root=root,
                  loop_start=start, loop_end=end, from_smpl=from_smpl)


def _read_chunks(handle) -> Tuple[Optional[bytes], Optional[bytes],
                                 Optional[bytes]]:
    """
    Los trozos ``fmt``, ``data`` y ``smpl``, leyendo del sonido sólo lo que
    se usa.

    Se recorren los encabezados con `seek` y del sonido se leen como mucho
    `MAX_SECONDS`. Leyendo el archivo entero, una grabación larga elegida
    como timbre ocupaba cientos de megas y demoraba la apertura del
    programa, que la carga al arrancar.
    """
    fmt = data = smpl = None
    deferred = None
    while True:
        header = handle.read(8)
        if len(header) < 8:
            break
        chunk, size = header[:4], struct.unpack("<I", header[4:])[0]
        start = handle.tell()
        if chunk == b"fmt " and fmt is None:
            fmt = handle.read(size)
        elif chunk == b"smpl" and smpl is None:
            smpl = handle.read(min(size, 1 << 16))
        elif chunk == b"data" and data is None:
            if fmt is not None and len(fmt) >= 16:
                data = handle.read(min(size, _data_budget(fmt)))
            else:
                deferred = (start, size)
        handle.seek(start + size + (size & 1))
    if data is None and deferred is not None and fmt is not None \
            and len(fmt) >= 16:
        handle.seek(deferred[0])
        data = handle.read(min(deferred[1], _data_budget(fmt)))
    return fmt, data, smpl


def _data_budget(fmt: bytes) -> int:
    """Cuántos bytes de sonido alcanzan para `MAX_SECONDS`."""
    _tag, channels, rate, _rate_bytes, align, bits = struct.unpack_from(
        "<HHIIHH", fmt)
    align = align or max(1, channels) * max(1, bits // 8)
    return int(MAX_SECONDS * max(1, rate) + 1) * max(1, align)


def detect_root(samples: Sequence[float], rate: int) -> float:
    """
    Qué nota es, oyéndola: autocorrelación sobre un tramo del medio.

    Lo simple que alcanza para una muestra de un instrumento: se busca cada
    cuántas muestras la onda se parece a sí misma. Se toma el primer
    retardo que llega cerca del mejor ---no el mejor a secas--- porque una
    onda que se repite cada ``p`` también se repite cada ``2p``, y quedarse
    con el máximo daba la nota una octava abajo. Si nada se parece lo
    suficiente (un ruido, un golpe) la nota es el La de 440.
    """
    window = min(len(samples) // 2, 4096)
    middle = len(samples) // 2
    frame = list(samples[max(0, middle - window // 2):
                         max(0, middle - window // 2) + window])
    shortest = max(2, rate // 1600)
    longest = min(len(frame) // 2, rate // 40)
    if longest <= shortest:
        return FALLBACK_ROOT
    energy = sum(v * v for v in frame)
    if energy <= 0.0:
        return FALLBACK_ROOT
    # La energía de cada tramo sale de una suma acumulada: recalcularla
    # retardo por retardo era casi todo el tiempo de la búsqueda.
    running = list(accumulate((v * v for v in frame), initial=0.0))
    size = len(frame)
    scores = {}
    for lag in range(shortest, longest + 1):
        top = sum(map(operator.mul, frame[:-lag], frame[lag:]))
        norm = math.sqrt((running[size - lag] - running[0])
                         * (running[size] - running[lag]))
        scores[lag] = top / norm if norm > 0.0 else 0.0
    # Los primeros retardos se parecen siempre: una onda grave cambia poco
    # de una muestra a la siguiente. Se busca recién después del primer
    # valle, que es donde la onda dejó de parecerse a sí misma.
    dip = next((l for l in range(shortest, longest + 1) if scores[l] < 0.2),
               None)
    if dip is None:
        return FALLBACK_ROOT
    after = range(dip, longest + 1)
    best = max(scores[l] for l in after)
    if best < 0.6:
        return FALLBACK_ROOT
    lag = next(l for l in after
               if scores[l] >= 0.9 * best
               and scores[l] >= scores.get(l - 1, -1.0)
               and scores[l] >= scores.get(l + 1, -1.0))
    # Interpolación parabólica entre los vecinos: sin esto la nota queda
    # redondeada a una muestra entera de período, que en los agudos son
    # varios cents.
    left, centre, right = (scores.get(lag - 1, scores[lag]), scores[lag],
                           scores.get(lag + 1, scores[lag]))
    bend = left - 2.0 * centre + right
    exact = lag + (0.5 * (left - right) / bend if bend < 0.0 else 0.0)
    frequency = rate / exact
    return 69.0 + 12.0 * math.log2(frequency / 440.0)


def _seamless_half(samples: List[float], rate: int) -> Tuple[int, int]:
    """
    El bucle de un WAV que no trae uno: la segunda mitad, fundida.

    Repetir un tramo cualquiera chasquea en el empalme, porque la onda no
    termina donde empezó. Se funde el final del bucle con lo que sonaba
    justo antes del comienzo: así, al saltar de la última muestra a la
    primera, la onda sigue como si no hubiera saltado. Modifica la lista.
    """
    start = len(samples) // 2
    end = len(samples) - 1
    fade = min(int(0.05 * rate), (end - start + 1) // 4, start)
    for i in range(fade):
        weight = (i + 1) / (fade + 1)
        position = end - fade + 1 + i
        samples[position] = (samples[position] * (1.0 - weight)
                             + samples[start - fade + i] * weight)
    return start, end


def _sampled(sample: Sample, midi: int, seconds: float,
             length: int) -> List[float]:
    """
    Una nota tocada con la muestra: transpuesta, sostenida y soltada.

    Transponer es leer más rápido o más lento: la razón entre las dos
    frecuencias es ``2^((nota − nota de la muestra)/12)``, corregida por la
    frecuencia de muestreo del archivo, e interpolando entre las dos
    muestras vecinas. Al llegar al final del bucle se vuelve a su comienzo
    mientras la nota dure; al soltar, medio coseno hasta el silencio.
    """
    ratio = (2.0 ** ((midi - sample.root) / 12.0)) * sample.rate / SAMPLE_RATE
    start, end = sample.loop_start, sample.loop_end
    span = end - start + 1
    source = sample.source()
    limit = end + 1
    places = [q if (q := j * ratio) < limit else start + (q - start) % span
              for j in range(length)]
    tone = [(a := source[(i := int(p))]) + (source[i + 1] - a) * (p - i)
            for p in places]
    shape = _held(seconds, length, 0.003, SAMPLE_RELEASE)
    return _times(tone, shape)


# ---------------------------------------------------------------------------
# Elegir, mezclar y medir
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Choice:
    """Lo que está sonando: una receta, o la muestra con su archivo."""

    key: str = DEFAULT
    sample: Optional[Sample] = None

    @property
    def variants(self) -> int:
        return _BY_KEY.get(self.key, _BY_KEY[DEFAULT]).variants


_current = Choice()


def current() -> Choice:
    """El timbre con el que suena todo. Se lee desde el hilo del sonido."""
    return _current


def choose(key: str, path: str = "") -> Choice:
    """
    Armar un timbre sin ponerlo: para probarlo antes de elegirlo.

    Una clave que no existe da el de siempre ---una preferencia guardada por
    una versión futura no puede dejar el programa mudo---; la muestra sin
    archivo, o con uno que no se puede leer, levanta :class:`TimbreError`.
    """
    if key == SAMPLE:
        if not path:
            raise TimbreError(trf("Todavía no se cargó ningún WAV."))
        return Choice(SAMPLE, read_sample(path))
    if key not in _RECIPES:
        key = DEFAULT
    return Choice(key)


def use(key: str, path: str = "") -> Choice:
    """
    Poner un timbre para todo lo que suene de acá en adelante.

    Si no se puede, el que queda es el de siempre y la excepción sube con
    el motivo: el programa nunca se queda con un timbre a medio cargar.
    El reemplazo es una sola asignación, así que el hilo que está sonando
    termina con el timbre con el que empezó.
    """
    global _current
    try:
        _current = choose(key, path)
    except TimbreError:
        _current = Choice()
        raise
    return _current


def render_note(choice: Choice, midi: int, seconds: float, length: int,
                variant: int = 0) -> List[float]:
    """
    Una nota sola, sin nivel: ``length`` muestras de las que suena ``seconds``.

    Lo que sobra después de ``seconds`` es la cola: la cuerda pulsada la
    llena con su caída y los timbres sostenidos con su salida y silencio.
    """
    if length <= 0:
        return []
    if choice.key == SAMPLE and choice.sample is not None:
        return _sampled(choice.sample, midi, seconds, length)
    recipe = _RECIPES.get(choice.key, _pluck)
    return recipe(midi, seconds, length, variant % max(1, choice.variants))


def mix(events: Sequence[Tuple[int, int, float, int, float]], total: int,
        choice: Optional[Choice] = None,
        level: Optional[float] = None) -> List[float]:
    """
    Sumar notas en un búfer: ``(altura, comienzo, segundos, largo, ganancia)``.

    Cada nota se sintetiza una sola vez por altura y duración: un coral
    repite las mismas notas acorde tras acorde ---la voz que se queda quieta
    es la misma nota otra vez--- y sintetizarla de nuevo era casi todo el
    tiempo de una reproducción. La suma va por tramos, no muestra por
    muestra.

    El nivel del timbre ---lo que lo iguala en sonoridad a la cuerda de
    siempre--- entra acá, así que quien llama sigue pensando en las
    ganancias de antes. ``level`` lo reemplaza: es lo que usa la medición,
    que necesita el timbre tal como sale de la receta.
    """
    choice = choice or current()
    if level is None:
        level = level_of(choice)
    buffer = [0.0] * max(0, total)
    raw: Dict[tuple, List[float]] = {}
    scaled: Dict[tuple, List[float]] = {}
    turns: Dict[tuple, int] = {}
    variants = max(1, choice.variants)
    for pitch, start, seconds, length, gain in events:
        length = min(length, total - start)
        if length <= 0 or start < 0:
            continue
        note = (pitch, round(seconds, 4), length)
        variant = turns.get(note, 0) % variants
        turns[note] = turns.get(note, 0) + 1
        key = note + (variant,)
        wave = raw.get(key)
        if wave is None:
            wave = render_note(choice, pitch, seconds, length, variant)
            raw[key] = wave
        amount = gain * level
        ready = scaled.get(key + (amount,))
        if ready is None:
            ready = [amount * v for v in wave]
            scaled[key + (amount,)] = ready
        buffer[start:start + length] = _plus(buffer[start:start + length],
                                             ready)
    return buffer


# -- sonoridad --------------------------------------------------------------

def _biquad(signal: Sequence[float], b0: float, b1: float, b2: float,
            a1: float, a2: float) -> List[float]:
    out = []
    x1 = x2 = y1 = y2 = 0.0
    append = out.append
    for x in signal:
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        append(y)
    return out


def _k_weighted(signal: Sequence[float], rate: int) -> List[float]:
    """
    El filtro de la norma ITU-R BS.1770: el oído, aproximado en dos pasos.

    Un estante que levanta cuatro decibeles por encima de unos 1700 Hz ---la
    cabeza refuerza esa zona--- y un pasa altos en unos 38 Hz, porque los
    graves extremos se oyen mucho menos de lo que pesan. Los coeficientes
    salen de las fórmulas de la norma para cualquier frecuencia de muestreo.
    """
    gain, centre, q = 3.999843853973347, 1681.974450955533, 0.7071752369554196
    k = math.tan(math.pi * centre / rate)
    vh = 10.0 ** (gain / 20.0)
    vb = vh ** 0.4996667741545416
    a0 = 1.0 + k / q + k * k
    shelf = _biquad(signal, (vh + vb * k / q + k * k) / a0,
                    2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0,
                    2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0)
    centre, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * centre / rate)
    a0 = 1.0 + k / q + k * k
    return _biquad(shelf, 1.0, -2.0, 1.0, 2.0 * (k * k - 1.0) / a0,
                   (1.0 - k / q + k * k) / a0)


def loudness(signal: Sequence[float], rate: int = SAMPLE_RATE) -> float:
    """
    Sonoridad integrada en LUFS, como la mide la radio.

    Ponderada con el filtro de la norma y **con compuerta**: bloques de
    400 ms, y se descartan los que están en silencio y los que quedan diez
    unidades por debajo del promedio. Sin compuerta, la cola de una cuerda
    que se apaga cuenta como volumen y un órgano que corta seco se mide
    más bajo de lo que suena. Devuelve -120 para el silencio.
    """
    if not signal:
        return -120.0
    weighted = _k_weighted(signal, rate)
    energy = list(accumulate((v * v for v in weighted), initial=0.0))
    block = max(1, int(0.4 * rate))
    hop = max(1, int(0.1 * rate))
    if len(weighted) < block:
        block = len(weighted)
    means = [(energy[i + block] - energy[i]) / block
             for i in range(0, len(weighted) - block + 1, hop)]

    def lufs(power: float) -> float:
        return -0.691 + 10.0 * math.log10(power) if power > 0.0 else -120.0

    kept = [m for m in means if lufs(m) > -70.0]
    if not kept:
        return -120.0
    gate = lufs(sum(kept) / len(kept)) - 10.0
    kept = [m for m in kept if lufs(m) > gate]
    return lufs(sum(kept) / len(kept))


#: Con qué se mide cada timbre para igualarlo: un coral de cuatro voces en
#: los registros de siempre, a la velocidad de siempre. Lo que el programa
#: toca casi siempre, así que es contra eso que tiene que sonar parejo.
CALIBRATION_CHORDS = ((48, 55, 64, 72), (45, 57, 64, 72), (41, 57, 65, 69),
                      (43, 55, 62, 71), (48, 55, 64, 72))
#: En segundos: blancas y negras a la velocidad de siempre. Las dos, porque
#: la cuerda pulsada se apaga en proporción a la nota y los demás no: medido
#: sólo con blancas, el clave sonaba bastante más fuerte en un pasaje rápido.
CALIBRATION_SECONDS = (1.25, 0.625, 0.625, 1.25, 1.25)
CALIBRATION_TAIL = 0.7

_LEVELS: Dict[str, float] = {}
_LEVEL_LOCK = threading.Lock()


def level_of(choice: Choice) -> float:
    """
    Cuánto hay que multiplicar este timbre para que suene como la cuerda.

    Se mide una vez por timbre ---y una vez por archivo---, la primera vez
    que hace falta, sobre :data:`CALIBRATION_CHORDS`. Medido y no anotado a
    mano: una receta retocada se iguala sola. La cuerda pulsada vale 1 por
    definición: es la que el programa tuvo siempre y contra la que están
    puestas todas las ganancias de `audio.py`.
    """
    if choice.key == DEFAULT:
        return 1.0
    if choice.key == SAMPLE and choice.sample is not None:
        if choice.sample.level is None:
            choice.sample.level = _level_against_default(choice)
        return choice.sample.level
    with _LEVEL_LOCK:
        known = _LEVELS.get(choice.key)
    if known is None:
        known = _level_against_default(choice)
        with _LEVEL_LOCK:
            _LEVELS[choice.key] = known
    return known


def _level_against_default(choice: Choice) -> float:
    reference = _reference_loudness()
    events, total = _calibration_events()
    measured = loudness(mix(events, total, choice, level=1.0))
    if measured <= -119.0:
        return 1.0
    return 10.0 ** ((reference - measured) / 20.0)


_REFERENCE: List[float] = []


def _reference_loudness() -> float:
    if not _REFERENCE:
        events, total = _calibration_events()
        _REFERENCE.append(loudness(mix(events, total, Choice(DEFAULT),
                                       level=1.0)))
    return _REFERENCE[0]


def _calibration_events():
    events = []
    position = 0.0
    for chord, seconds in zip(CALIBRATION_CHORDS, CALIBRATION_SECONDS):
        start = int(position * SAMPLE_RATE)
        length = int((seconds + CALIBRATION_TAIL) * SAMPLE_RATE)
        events.extend((pitch, start, seconds, length, 1.0) for pitch in chord)
        position += seconds
    total = int((position + CALIBRATION_TAIL) * SAMPLE_RATE)
    return events, total
