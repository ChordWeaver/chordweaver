# -*- coding: utf-8 -*-
"""
Los ruidos del modo historia, sintetizados acá mismo.

Mismo criterio que ``engine/audio.py`` y por las mismas razones: no entra
ninguna librería de audio y no se empaqueta ningún archivo de sonido. Todo
--- el viento, los pájaros, el blip de cada personaje, los vientos que cierran
un tema, el coro --- se calcula con la biblioteca estándar y se escribe a un
WAV temporal. Así el ejecutable no crece, no hay nada que licenciar y el
programa suena igual en cualquier máquina.

Cómo suena cada cosa
--------------------
El viento es ruido blanco pasado por un filtro de un polo y modulado por
ráfagas lentas; los pájaros son barridos cortos de sinusoide bien arriba; el
blip es una onda casi cuadrada de setenta milisegundos, con una altura y un
timbre distintos por personaje --- es lo que hace que se reconozca quién
habla sin leer el nombre. El coro son quintas y octavas paralelas sobre un
timbre de vocal, que es literalmente el organum del que habla el libro. Los
vientos del final de jazz son una frase de tres acordes con un timbre de
caña.

Cómo se reproduce
-----------------
Windows sabe tocar un solo sonido por proceso a través de ``winsound``, y
acá hacen falta dos a la vez: la cama de ambiente por debajo y el blip de
cada letra por encima. Por eso el camino principal es **MCI**, la interfaz
de multimedia de Windows, llamada por ``ctypes`` --- que es biblioteca
estándar. MCI abre cada archivo con un alias propio y los alias suenan
simultáneos. Si algo de eso falla se cae a ``winsound``, y si tampoco está,
a los reproductores de línea de comandos que ya usa ``audio.py``.

Nada de esto puede romper la aplicación: **el sonido es decoración**. Cada
llamada está envuelta, cada error se traga y el peor caso posible es que la
cinemática ocurra en silencio.
"""

from __future__ import annotations

import contextlib
import hashlib
import math
import os
import platform
import random
import struct
import subprocess
import sys
import tempfile
import threading
import wave
from typing import Callable, Dict, List, Optional, Sequence

#: A 44100, como cualquier cosa que se escuche en serio.
#:
#: Estuvo a la mitad mucho tiempo con el argumento de que acá no hay que
#: juzgar una conducción de voces sino ambientar, y de que la mitad de
#: muestras es la mitad de tiempo de síntesis. Era falso donde más importa:
#: a 22050 no existe nada por encima de los 11 kHz, y ahí es exactamente
#: donde vive el brillo de un metal, el filo de un grito y el aire de una
#: cuerda pulsada. Todo sonaba **tapado**, como a través de una pared, y
#: ninguna cantidad de volumen arregla eso.
#:
#: Duplicar el número de muestras duplica el tiempo de síntesis y no cambia
#: nada más: todo lo de este módulo está escrito en segundos y en hertz, no
#: en muestras. Las dos únicas cosas que sí estaban en muestras --- el corte
#: de los filtros de un polo y los retardos de la reverberación --- se
#: corrigen con `_RATE`.
SAMPLE_RATE = 44100

#: Cuánto hay que corregir lo que estaba calibrado a 22050.
_RATE = SAMPLE_RATE / 22050.0

_TWO_PI = 2.0 * math.pi


# ---------------------------------------------------------------------------
# Ladrillos
# ---------------------------------------------------------------------------

def _buffer(seconds: float) -> List[float]:
    return [0.0] * int(seconds * SAMPLE_RATE)


def _noise(buffer: List[float], gain: float, cutoff: float,
           rng: random.Random, envelope: Optional[Callable[[float], float]] = None
           ) -> None:
    """
    Ruido blanco pasado por un filtro de un polo, sumado al buffer.

    ``cutoff`` va de 0 a 1: cuanto más chico, más grave y más parecido a
    viento; cerca de 1 queda el siseo áspero que sirve para el fuego.

    El valor se corrige por la frecuencia de muestreo, así que el color de un
    ruido no cambia si mañana se cambia `SAMPLE_RATE`: el mismo número quiere
    decir el mismo corte en hertz.
    """
    cutoff = min(1.0, cutoff / _RATE)
    state = 0.0
    total = len(buffer)
    for index in range(total):
        state += cutoff * (rng.uniform(-1.0, 1.0) - state)
        level = gain if envelope is None else gain * envelope(index / total)
        buffer[index] += state * level


def _tone(buffer: List[float], frequency: float, gain: float,
          start: float, seconds: float,
          envelope: Optional[Callable[[float], float]] = None,
          harmonics: Sequence[float] = (1.0,),
          vibrato: float = 0.0, glide: float = 1.0) -> None:
    """
    Un tono con sus armónicos, sumado al buffer.

    ``harmonics`` son las amplitudes del fundamental, el segundo armónico, el
    tercero…; ``glide`` es la razón entre la frecuencia final y la inicial,
    que es lo que hace el chirrido de un pájaro o el barrido del fuego.
    """
    first = int(start * SAMPLE_RATE)
    length = min(int(seconds * SAMPLE_RATE), max(0, len(buffer) - first))
    if length <= 0:
        return
    angles = [0.0] * len(harmonics)
    for offset in range(length):
        position = offset / length
        shape = 1.0 if envelope is None else envelope(position)
        if shape <= 0.0:
            # El ángulo tiene que seguir avanzando igual: cortar el bucle
            # dejaría un salto de fase en cuanto la envolvente vuelva a
            # abrirse.
            shape = 0.0
        bend = frequency * (1.0 + (glide - 1.0) * position)
        if vibrato:
            bend *= 1.0 + vibrato * math.sin(_TWO_PI * 5.5 * offset / SAMPLE_RATE)
        value = 0.0
        for number, amplitude in enumerate(harmonics, start=1):
            if amplitude:
                value += amplitude * math.sin(angles[number - 1])
            angles[number - 1] += _TWO_PI * bend * number / SAMPLE_RATE
        buffer[first + offset] += value * gain * shape


def _square(buffer: List[float], frequency: float, gain: float,
            start: float, seconds: float,
            envelope: Optional[Callable[[float], float]] = None) -> None:
    """
    Una onda casi cuadrada: los primeros armónicos impares.

    Es el timbre de las voces de los juegos de dos dimensiones, y sale de
    sumar tres senos en vez de conmutar entre dos valores, que produciría un
    aliasing áspero a esta frecuencia de muestreo.
    """
    _tone(buffer, frequency, gain, start, seconds, envelope,
          harmonics=(1.0, 0.0, 0.34, 0.0, 0.18))


def _fade(position: float, attack: float = 0.02, release: float = 0.2) -> float:
    """Envolvente trapezoidal, en fracción de la duración."""
    if position < attack:
        return position / attack
    if position > 1.0 - release:
        return max(0.0, (1.0 - position) / release)
    return 1.0


def _pluck(position: float) -> float:
    return math.exp(-5.5 * position) * min(1.0, position / 0.01)


def _swell(position: float) -> float:
    """Sube y baja: la ráfaga de viento, la luz que se abre."""
    return math.sin(math.pi * position) ** 1.5


def _seamless(buffer: List[float], seconds: float = 0.45) -> List[float]:
    """
    Preparar un buffer para que se repita sin costura.

    La cola se mezcla dentro de la cabeza con un cruce lineal y después se
    recorta: el último instante del bucle y el primero pasan a ser la misma
    señal, así que el empalme deja de escucharse como un golpe.
    """
    span = min(int(seconds * SAMPLE_RATE), len(buffer) // 3)
    if span <= 0:
        return buffer
    head = len(buffer) - span
    for offset in range(span):
        weight = offset / span
        buffer[offset] = buffer[offset] * weight + buffer[head + offset] * (1.0 - weight)
    return buffer[:head]


def _polish(buffer: List[float], cutoff: float,
            cutoff_end: Optional[float] = None) -> List[float]:
    """
    Filtro de un polo sobre el buffer entero, opcionalmente cerrándose.

    Es lo que separa un ruido de una explosión: el ruido blanco crudo se
    escucha como siseo de cinta, y lo que hace que se lea como aire, fuego
    o distancia es que los agudos se vayan yendo. ``cutoff_end`` es el
    corte al final; sin él, el filtro es fijo.
    """
    cutoff = min(1.0, cutoff / _RATE)
    if cutoff_end is not None:
        cutoff_end = min(1.0, cutoff_end / _RATE)
    state = 0.0
    total = len(buffer) or 1
    for index, value in enumerate(buffer):
        step = cutoff if cutoff_end is None else (
            cutoff + (cutoff_end - cutoff) * (index / total))
        state += step * (value - state)
        buffer[index] = state
    return buffer


def _band(buffer: List[float], gain: float, centre: float, q: float,
          rng: random.Random,
          envelope: Optional[Callable[[float], float]] = None,
          sweep: Optional[Callable[[float], float]] = None) -> None:
    """
    Ruido pasado por un filtro **resonante**, sumado al buffer.

    Es la diferencia entre un siseo y algo. Un filtro de un polo --- el que
    usa :func:`_noise` --- sólo sabe apagar los agudos, y con eso el viento
    suena a cinta de casete; un resonante deja pasar una banda angosta
    alrededor de una frecuencia, que es lo que hace el aire cuando se cuela
    por un hueco. Silbidos, gargantas, cuerpos de metal: todo lo que tiene
    una nota sin ser una nota sale de acá.

    ``q`` es lo angosto de la banda: 2 es un color, 20 es casi un silbato.
    ``sweep`` mueve la frecuencia a lo largo del sonido --- devuelve un
    multiplicador --- y los coeficientes se recalculan cada tanto y no en
    cada muestra, porque el filtro no cambia de carácter en un milisegundo y
    calcular tres senos por muestra sí se nota.
    """
    total = len(buffer) or 1
    x1 = x2 = y1 = y2 = 0.0
    b0 = b2 = a1 = a2 = 0.0
    every = 128
    for index in range(total):
        if index % every == 0:
            position = index / total
            frequency = centre * (1.0 if sweep is None else sweep(position))
            frequency = min(max(20.0, frequency), SAMPLE_RATE * 0.45)
            w0 = _TWO_PI * frequency / SAMPLE_RATE
            alpha = math.sin(w0) / (2.0 * q)
            a0 = 1.0 + alpha
            b0, b2 = alpha / a0, -alpha / a0
            a1, a2 = -2.0 * math.cos(w0) / a0, (1.0 - alpha) / a0
        x0 = rng.uniform(-1.0, 1.0)
        y0 = b0 * x0 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, x0
        y2, y1 = y1, y0
        level = gain if envelope is None else gain * envelope(index / total)
        buffer[index] += y0 * level


#: Los retardos de la reverberación, en muestras a 22050 Hz. Son números
#: primos entre sí a propósito: si dos peines compartieran divisor sus ecos
#: caerían encima y se oiría el período en vez de una cola.
_COMBS = (663, 809, 941, 1105)
_ALLPASS = (331, 219)


def _reverb(buffer: List[float], mix: float = 0.30, decay: float = 0.80,
            size: float = 1.0, damp: float = 0.32) -> List[float]:
    """
    Reverberación de Schroeder: cuatro peines en paralelo y dos pasa-todo.

    Es lo único que faltaba para que estos sonidos dejaran de sonar a
    laboratorio. Un golpe seco, un grito o una campana **existen en un
    lugar**, y lo que dice cuál es ese lugar no es el sonido sino lo que
    vuelve de las paredes. Sin cola, todo pasaba en el vacío.

    ``decay`` es cuánto se realimenta cada peine --- cuánto dura la cola ---,
    ``size`` estira los retardos (una sala más grande) y ``damp`` es el
    filtro dentro del lazo: los agudos se apagan antes que los graves, igual
    que en cualquier ambiente de verdad.

    **En un bucle va antes del empalme**, nunca después: la cola de la
    reverberación es justo lo que el cruce de :func:`_seamless` tiene que
    fundir contra la cabeza.
    """
    total = len(buffer)
    wet = [0.0] * total
    for delay in _COMBS:
        length = max(8, int(delay * size * _RATE))
        line = [0.0] * length
        cursor = 0
        store = 0.0
        for index in range(total):
            got = line[cursor]
            wet[index] += got
            store = got * (1.0 - damp) + store * damp
            line[cursor] = buffer[index] + store * decay
            cursor += 1
            if cursor >= length:
                cursor = 0
    share = 1.0 / len(_COMBS)
    for index in range(total):
        wet[index] *= share
    for delay in _ALLPASS:
        length = max(4, int(delay * size * _RATE))
        line = [0.0] * length
        cursor = 0
        for index in range(total):
            value = wet[index]
            got = line[cursor]
            wet[index] = got - value * 0.5
            line[cursor] = value + got * 0.5
            cursor += 1
            if cursor >= length:
                cursor = 0
    for index in range(total):
        buffer[index] = buffer[index] * (1.0 - mix) + wet[index] * mix
    return buffer


def _saturate(buffer: List[float], drive: float = 2.0) -> List[float]:
    """
    Saturación blanda: lo que le falta a un sonido para sonar violento.

    Un seno puro nunca suena a rugido por más grave que sea. Pasarlo por una
    curva que se aplana en los extremos le agrega los armónicos que produce
    cualquier cosa que se está rompiendo --- una garganta, un parlante, el
    aire --- y eso es lo que el oído lee como fuerza.
    """
    for index, value in enumerate(buffer):
        pushed = value * drive
        buffer[index] = pushed / (1.0 + abs(pushed))
    return buffer


def _ring(buffer: List[float], frequency: float, depth: float = 1.0,
          start: float = 0.0) -> List[float]:
    """
    Modulación en anillo: multiplicar por un seno.

    Cada componente se parte en dos --- una por encima y otra por debajo de
    la frecuencia moduladora --- y ninguna de las dos guarda relación armónica
    con lo que había. Es la manera más rápida de que algo deje de sonar a
    animal y empiece a sonar a otra cosa; con poca profundidad, apenas
    ensucia.
    """
    first = int(start * SAMPLE_RATE)
    for index in range(first, len(buffer)):
        phase = _TWO_PI * frequency * (index - first) / SAMPLE_RATE
        wobble = 1.0 - depth + depth * math.sin(phase)
        buffer[index] *= wobble
    return buffer


def _normalise(buffer: List[float], peak: float = 0.8) -> List[float]:
    """
    Llevar el pico al nivel pedido.

    Es lo que mantiene todos los sonidos del programa a un volumen parejo.
    Antes cada uno salía con la ganancia que le hubiera quedado de sumar sus
    capas, así que el zorro reventaba y el bordón de la entidad no se oía:
    dos problemas distintos con la misma causa.
    """
    top = 0.0
    for value in buffer:
        if value > top:
            top = value
        elif -value > top:
            top = -value
    if top <= 1e-9:
        return buffer
    scale = peak / top
    for index in range(len(buffer)):
        buffer[index] *= scale
    return buffer


#: Dónde empieza a apretar el limitador y con qué margen para hacerlo.
_KNEE = 0.55
_KNEE_SPAN = 0.45


def _loudness(buffer: List[float], power: float, ceiling: float = 0.90,
              tail: float = 0.45) -> List[float]:
    """
    Llevar el sonido a un volumen **percibido**, y no a un pico.

    El pico no dice nada sobre cuánto se escucha algo. Un golpe seco con un
    pico de 0,9 y una campana con el mismo pico suenan a volúmenes
    completamente distintos, porque lo que el oído mide es la energía
    promedio y no el instante más alto. Nivelar por pico ---que es lo que se
    hacía--- dejaba todo el programa sonando a la mitad de lo que debería: el
    ruido de la aparición tenía el pico donde había que tenerlo y aun así el
    viento se lo comía entero.

    Así que primero se lleva la energía promedio a donde se la quiere, y
    después se sujetan los picos que se hayan ido de rango con una curva
    blanda ---no un recorte, que suena a rotura--- y recién al final se pone
    el techo. El resultado es varias veces más fuerte que el mismo sonido
    nivelado por pico, y no distorsiona.
    """
    total = len(buffer) or 1
    # La cola: los últimos milisegundos bajan a cero con una curva suave.
    #
    # Un archivo que termina mientras todavía suena algo se corta en seco, y
    # eso se escucha como un chasquido --- el canto de Gregorio terminaba al
    # 42% de su volumen máximo. La reverberación empeoró el problema: le
    # agrega segundos de cola a todo, y lo que no entra en el archivo se
    # pierde de golpe.
    #
    # No reemplaza a darle largo suficiente al buffer: con la cola bien
    # apagada esto no se oye, y con el buffer corto se oye como un fundido
    # apurado. Es la red de seguridad, no la solución.
    #
    # **Los bucles pasan con `tail=0`**: ahí el final y el principio son el
    # mismo punto, y apagar el final rompería justo el empalme que
    # `_seamless` acaba de armar.
    if tail > 0.0:
        span = min(int(tail * SAMPLE_RATE), total // 3)
        for offset in range(span):
            position = offset / span
            buffer[total - span + offset] *= 0.5 + 0.5 * math.cos(
                math.pi * position)
    energy = 0.0
    for value in buffer:
        energy += value * value
    current = math.sqrt(energy / total)
    if current <= 1e-9:
        return buffer
    gain = power / current
    for index in range(total):
        value = buffer[index] * gain
        # Curva blanda: por debajo del codo no toca nada, y de ahí para
        # arriba va apretando en vez de cortar.
        #
        # El codo arrancaba en 0,7 y la curva era corta, así que lo que
        # entraba en ella se doblaba de golpe --- y en un grito o un rugido
        # eso es mucha señal: el zorro tenía el 8% de sus muestras adentro de
        # la curva y se escuchaba rasposo de una manera que no era la que se
        # buscaba. Con el codo más abajo y la curva más larga, la misma
        # cantidad de señal se comprime el doble de suave.
        if value > _KNEE:
            value = _KNEE + _KNEE_SPAN * math.tanh((value - _KNEE) / _KNEE_SPAN)
        elif value < -_KNEE:
            value = -_KNEE - _KNEE_SPAN * math.tanh((-value - _KNEE) / _KNEE_SPAN)
        buffer[index] = value
    # El techo **sólo baja**. Llamar a `_normalise` sin más subía todo lo que
    # hubiera quedado por debajo, y eso deshace el trabajo: un bordón tiene
    # los picos apenas por encima de su promedio, así que estirarlo hasta el
    # techo lo devolvía al volumen de un golpe. Los que ya están por debajo
    # se quedan donde el promedio los dejó.
    top = 0.0
    for value in buffer:
        if value > top:
            top = value
        elif -value > top:
            top = -value
    if top > ceiling:
        _normalise(buffer, ceiling)
    return buffer


#: A qué volumen **percibido** sale cada familia de sonidos.
#:
#: Las camas de ambiente van por debajo porque suenan durante minutos y por
#: debajo de todo lo demás; los golpes van arriba porque duran un segundo y
#: tienen que interrumpir. Los huevos de pascua, todavía más: son un chiste y
#: el chiste es el susto.
#: **La cama va bien abajo.** Suena durante minutos y, sobre todo, suena
#: mientras alguien habla: lo único que hace de voz en una cinemática son los
#: blips, que duran cuarenta milésimas cada uno, así que un colchón de viento
#: parejo los tapa sin esfuerzo. A 0,11 el señor del sombrero directamente no
#: se escuchaba; a 0,065 se lo escuchaba con el viento encima. Es ambiente:
#: tiene que estar y no tiene que notarse.
POWER_BED = 0.045

#: Y el de una cama que suena sola, sin nadie hablando encima. La visión no
#: tiene diálogo, así que ahí el viento **es** la escena y puede ocupar el
#: lugar que en las otras le corresponde a la voz.
POWER_SOLO = 0.095
POWER_HIT = 0.27
POWER_JOKE = 0.31
#: Y las letras del diálogo, que suenan cada tres caracteres: fuertes para
#: que se oigan sobre la cama, cortísimas para que no cansen.
POWER_BLIP = 0.17

#: El techo de picos de cada familia. Nadie llega a 1,0: un poco de aire
#: arriba es lo que evita que la placa de sonido recorte por su cuenta.
LEVEL_BED = 0.70
LEVEL_HIT = 0.90
LEVEL_JOKE = 0.92
LEVEL_BLIP = 0.55


def _encode(buffer: Sequence[float], gain: float = 1.0) -> bytes:
    frames = bytearray()
    for value in buffer:
        value *= gain
        clamped = -1.0 if value < -1.0 else (1.0 if value > 1.0 else value)
        frames += struct.pack("<h", int(clamped * 32000))
    return bytes(frames)


# ---------------------------------------------------------------------------
# Los sonidos
# ---------------------------------------------------------------------------

def _valley_bed() -> bytes:
    """
    Viento de valle con pájaros: la cama que suena mientras habla la figura.

    Doce segundos preparados para repetirse. Lo que hace que suene a aire y
    no a siseo son las capas **resonantes**: bandas angostas que se pasean de
    frecuencia despacio, cada una a su ritmo, que es lo que hace el viento
    cuando se cuela entre las cosas. Debajo va un ruido grave ancho ---el
    cuerpo--- y encima dos silbidos apenas insinuados.

    Los pájaros caen en momentos fijados por una semilla constante, para que
    la escena suene siempre igual, y llevan la cola de la reverberación
    encima: un pájaro sin cola suena adentro de la habitación, y éstos están
    lejos.
    """
    rng = random.Random(1337)
    seconds = 12.0
    buffer = _buffer(seconds)

    def gusts(period: float, depth: float, phase: float = 0.0):
        def shape(position: float) -> float:
            wave = math.sin(_TWO_PI * (position * period + phase))
            return max(0.05, 1.0 - depth + depth * (0.5 + 0.5 * wave))
        return shape

    def drift(period: float, span: float, phase: float = 0.0):
        def shape(position: float) -> float:
            return 1.0 + span * math.sin(_TWO_PI * (position * period + phase))
        return shape

    # El cuerpo: aire grave y ancho, con ráfagas largas.
    _noise(buffer, 0.30, 0.020, rng, gusts(1.0, 0.55))
    _noise(buffer, 0.10, 0.006, rng, gusts(0.5, 0.40, 0.3))
    # Y las bandas que le dan la voz. Tres, a distinta altura y con distinto
    # paseo: si fueran una sola se escucharía la nota.
    _band(buffer, 0.34, 220.0, 3.5, rng, gusts(2.0, 0.75), drift(1.0, 0.35))
    _band(buffer, 0.20, 620.0, 6.0, rng, gusts(3.0, 0.85, 0.4),
          drift(2.0, 0.28, 0.5))
    _band(buffer, 0.09, 1450.0, 9.0, rng, gusts(5.0, 0.90, 0.7),
          drift(3.0, 0.22, 0.2))

    # Los pájaros: barridos cortos bien arriba, de a dos o tres seguidos,
    # como canta un pájaro de verdad.
    moment = 0.9
    while moment < seconds - 1.5:
        base = rng.uniform(2100.0, 3400.0)
        for repeat in range(rng.randint(2, 3)):
            _tone(buffer, base * rng.uniform(0.94, 1.06), 0.050,
                  moment + repeat * 0.13, 0.09,
                  envelope=lambda p: math.exp(-6.0 * p) * min(1.0, p / 0.05),
                  glide=rng.uniform(1.15, 1.45))
        moment += rng.uniform(2.2, 3.6)

    _reverb(buffer, mix=0.22, decay=0.78, size=1.4)
    return _encode(_loudness(_seamless(buffer), POWER_BED, LEVEL_BED, tail=0.0))


def _wind_gust() -> bytes:
    """
    La ráfaga de la aparición y de la partida del señor del sombrero.

    Una ráfaga no es ruido más fuerte: es ruido que **cambia de color**
    mientras pasa. La banda resonante sube de frecuencia con la ráfaga y baja
    al irse, y eso solo ya se lee como algo que se acerca y se aleja. Debajo,
    el roce grave de una tela larga.
    """
    rng = random.Random(7)
    buffer = _buffer(3.0)
    _noise(buffer, 0.42, 0.045, rng, _swell)
    _noise(buffer, 0.20, 0.010, rng, lambda p: _swell(p) ** 0.6)
    _band(buffer, 0.55, 480.0, 4.0, rng, _swell,
          lambda p: 0.55 + 1.5 * math.sin(math.pi * p) ** 1.2)
    _band(buffer, 0.22, 1600.0, 10.0, rng, lambda p: _swell(p) ** 2.0,
          lambda p: 0.8 + 0.6 * p)
    _tone(buffer, 58.0, 0.10, 0.2, 2.4,
          envelope=_swell, harmonics=(1.0, 0.4, 0.15))
    _reverb(buffer, mix=0.26, decay=0.80, size=1.5)
    return _encode(_loudness(buffer, POWER_HIT, LEVEL_HIT))


def _hellfire() -> bytes:
    """El señor desapareciendo en llamas: rugido grave y siseo que sube."""
    rng = random.Random(66)
    buffer = _buffer(2.4)
    _noise(buffer, 0.5, 0.6, rng,
           lambda p: math.exp(-2.4 * p) * min(1.0, p / 0.02))
    _noise(buffer, 0.30, 0.05, rng, lambda p: math.exp(-1.6 * p))
    _tone(buffer, 78.0, 0.28, 0.0, 1.6,
          envelope=lambda p: math.exp(-2.0 * p), harmonics=(1.0, 0.5, 0.3),
          glide=0.55)
    # El chasquido del principio.
    _tone(buffer, 340.0, 0.22, 0.0, 0.25,
          envelope=lambda p: math.exp(-14.0 * p), glide=0.3)
    _reverb(buffer, mix=0.26, decay=0.84, size=2.0)
    return _encode(_loudness(buffer, POWER_HIT, LEVEL_HIT))


#: Una vocal cantada: fundamental fuerte y unos pocos armónicos, con
#: vibrato. Sin formantes de verdad, pero alcanza para que se lea como voz y
#: no como un órgano.
_VOICE = (1.0, 0.42, 0.22, 0.10, 0.05)


def _organum(rising: bool) -> bytes:
    """
    El coro: una línea modal doblada en quintas y octavas.

    Es organum literal --- la voz principal y su sombra a la quinta ---
    porque es lo que corresponde al capítulo del libro que habla del canto
    llano, y porque es lo que suena antiguo sin sonar a acorde de iglesia
    del siglo diecinueve.
    """
    line = [62, 64, 65, 67, 69] if rising else [69, 67, 65, 64, 62]
    # Con 3,4 segundos el archivo se terminaba mientras la cola de la
    # reverberación todavía sonaba fuerte, y el corte se oía como un clic.
    # La nave tiene que poder terminar de vaciarse adentro del archivo.
    buffer = _buffer(7.2)
    step, hold = 0.42, 1.5
    for index, midi in enumerate(line):
        start = index * step
        last = index == len(line) - 1
        length = hold if last else step * 2.2
        gain = 0.15 if last else 0.11
        for interval in (0, 7, 12):
            _tone(buffer, 440.0 * 2.0 ** ((midi + interval - 69) / 12.0),
                  gain * (1.0 if interval == 0 else 0.62),
                  start, length,
                  envelope=lambda p: _fade(p, 0.22, 0.45),
                  harmonics=_VOICE, vibrato=0.004)
    # Una iglesia. Es el único sonido del programa que **tiene** que sonar a
    # un lugar concreto, y ese lugar es grande y de piedra.
    _reverb(buffer, mix=0.40, decay=0.90, size=3.4, damp=0.30)
    return _encode(_loudness(buffer, POWER_HIT, LEVEL_HIT))


def _sax_outro() -> bytes:
    """
    El final de un tema: un ii-V-I con timbre de caña.

    Escrito acá y no tomado de ningún lado --- un final de jazz de tres
    acordes es de dominio de cualquiera, y sintetizarlo evita la única
    dependencia que este programa nunca quiso tener.
    """
    buffer = _buffer(3.6)
    reed = (1.0, 0.55, 0.40, 0.22, 0.14, 0.08)

    # Cm7 - F7 - Bb6, con la frase arriba resolviendo por grado conjunto.
    chords = [((60, 63, 67, 70), 0.0, 0.75),
              ((58, 62, 65, 69), 0.75, 0.75),
              ((58, 62, 65, 70), 1.5, 2.0)]
    for pitches, start, length in chords:
        for midi in pitches:
            _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), 0.055,
                  start, length, envelope=lambda p: _fade(p, 0.06, 0.35),
                  harmonics=(1.0, 0.3, 0.16), vibrato=0.003)

    phrase = [(74, 0.0, 0.30), (72, 0.30, 0.22), (70, 0.52, 0.23),
              (69, 0.75, 0.45), (67, 1.20, 0.30), (70, 1.50, 2.0)]
    for midi, start, length in phrase:
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), 0.16,
              start, length, envelope=lambda p: _fade(p, 0.05, 0.30),
              harmonics=reed, vibrato=0.006)
    # Un club, no una catedral: cola corta y oscura.
    _reverb(buffer, mix=0.24, decay=0.78, size=1.5)
    return _encode(_loudness(buffer, POWER_HIT * 0.9, LEVEL_HIT))


def _light_bed() -> bytes:
    """La cama de la escena divina: un acorde quieto que respira."""
    buffer = _buffer(10.0)
    for midi, gain in ((50, 0.10), (57, 0.07), (62, 0.05), (69, 0.035),
                       (74, 0.022)):
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), gain, 0.0, 10.0,
              envelope=lambda p: 0.75 + 0.25 * math.sin(_TWO_PI * p * 2.0),
              harmonics=_VOICE, vibrato=0.003)
    _reverb(buffer, mix=0.30, decay=0.88, size=3.0)
    return _encode(_loudness(_seamless(buffer, 0.8), POWER_BED, LEVEL_BED, tail=0.0))


#: La voz de cada personaje mientras escribe el diálogo: frecuencia, cuánto
#: dura el blip y con qué timbre. Es lo único que suena mientras se lee, así
#: que la diferencia entre uno y otro tiene que oírse enseguida.
_BLIPS = {
    "devil": (168.0, 0.075, "square"),
    "django": (330.0, 0.060, "pluck"),
    "jesus": (622.0, 0.090, "bell"),
    "narrator": (240.0, 0.045, "soft"),
    # Las visitas. Bach suena a cuerda pulsada porque el clave se pulsa ---
    # no tiene matices, o suena o no suena, que es bastante lo que él dice
    # del oficio ---; Gregorio, a voz sin agudos; y la entidad, a algo grave
    # que no termina de ser una voz.
    "bach": (392.0, 0.055, "pluck"),
    "gregory": (208.0, 0.070, "soft"),
    "watcher": (96.0, 0.085, "soft"),
}


def _blip(key: str) -> bytes:
    frequency, seconds, flavour = _BLIPS.get(key, _BLIPS["narrator"])
    buffer = _buffer(seconds + 0.03)
    if flavour == "square":
        _square(buffer, frequency, 0.32, 0.0, seconds,
                envelope=lambda p: math.exp(-4.0 * p))
        _noise(buffer, 0.05, 0.5, random.Random(3),
               lambda p: math.exp(-16.0 * p))
    elif flavour == "pluck":
        _tone(buffer, frequency, 0.30, 0.0, seconds, envelope=_pluck,
              harmonics=(1.0, 0.5, 0.28, 0.12))
    elif flavour == "bell":
        _tone(buffer, frequency, 0.20, 0.0, seconds,
              envelope=lambda p: math.exp(-3.4 * p), harmonics=(1.0, 0.0, 0.3))
        _tone(buffer, frequency * 1.5, 0.10, 0.0, seconds,
              envelope=lambda p: math.exp(-4.6 * p))
    else:
        _tone(buffer, frequency, 0.16, 0.0, seconds,
              envelope=lambda p: math.exp(-8.0 * p), harmonics=(1.0, 0.2))
    # Todos al mismo nivel. Suenan una vez cada tres letras y durante minutos:
    # que uno esté al doble que otro se nota mucho más que en un golpe suelto,
    # y lo que se escuchaba era que un personaje hablaba más fuerte que otro.
    return _encode(_loudness(buffer, POWER_BLIP, LEVEL_BLIP))


def _chime() -> bytes:
    """El destello de algo que se desbloquea."""
    buffer = _buffer(1.6)
    for index, midi in enumerate((76, 83, 88)):
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), 0.16,
              index * 0.09, 1.4 - index * 0.1,
              envelope=lambda p: math.exp(-3.0 * p) * min(1.0, p / 0.01),
              harmonics=(1.0, 0.0, 0.22, 0.0, 0.08))
    _reverb(buffer, mix=0.30, decay=0.84, size=2.0)
    return _encode(_loudness(buffer, POWER_HIT * 0.8, LEVEL_HIT))


#: Las tres estrellas, como acordes.
#:
#: La primera es una triada mayor pelada; la segunda le agrega la sexta y
#: una octava por arriba; la tercera es la misma triada abierta en dos
#: octavas con la novena adentro. Es a proposito que sea el mismo acorde
#: las tres veces: lo que mejora no es la armonia sino cuanta hay. Una
#: fanfarria distinta por estrella se habria leido como tres premios
#: distintos, y son el mismo premio tres veces mas grande.
_STAR_CHORDS = (
    ((60, 64, 67), 2.6),
    ((60, 64, 67, 69, 72), 3.4),
    ((48, 60, 64, 67, 74, 79, 84), 4.6),
)


def _fanfare(level: int) -> bytes:
    """
    La estrella que se gana, en tres tamanos.

    Metal: muchos armonicos impares y un ataque corto. Las notas entran
    escalonadas de abajo hacia arriba --- un acorde entero de golpe suena a
    teclado, y escalonado suena a gente ---, y el escalon se acorta con el
    nivel, asi que la tercera estrella llega casi de una pieza.
    """
    midis, seconds = _STAR_CHORDS[max(0, min(2, level - 1))]
    # La cola de la reverberacion tiene que entrar en el archivo: cortarla
    # se escucha como un clic, y aca la cola es media fanfarria.
    buffer = _buffer(seconds + 1.4)
    #: Boquilla de metal: el segundo y el tercer armonico casi tan fuertes
    #: como el fundamental es lo que separa una trompeta de una flauta.
    brass = (1.0, 0.70, 0.52, 0.36, 0.24, 0.15, 0.09)
    step = 0.14 - 0.035 * (level - 1)
    for index, midi in enumerate(midis):
        start = index * step
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0),
              0.085 + 0.012 * level, start, seconds - start,
              envelope=lambda p: _fade(p, 0.035, 0.55), harmonics=brass)
    # Un poco de aspereza, y solo en la ultima: es la diferencia entre un
    # acorde que suena y un acorde que empuja.
    if level >= 3:
        buffer = _saturate(buffer, drive=1.5)
    # Una sala grande, y mas grande cuanto mas alta la estrella: lo que
    # dice que algo es importante no es el volumen sino el lugar donde
    # pasa.
    _reverb(buffer, mix=0.24 + 0.07 * level, decay=0.80 + 0.03 * level,
            size=1.6 + 0.7 * level)
    return _encode(_loudness(buffer, POWER_HIT * (0.72 + 0.09 * level),
                             LEVEL_HIT))


def _egg_found() -> bytes:
    """
    El huevo que aparece: cuatro notas que suben y una que se rie.

    No es una fanfarria y no tiene que serlo --- un huevo de pascua que se
    anuncia deja de ser un huevo ---, asi que va corto, chico y con la
    ultima nota fuera del acorde: la sexta aumentada que no resuelve, que
    es la manera mas vieja que hay de guinar un ojo.
    """
    buffer = _buffer(2.4)
    #: Campanita de caja de musica: fundamental fuerte y un par de
    #: armonicos altos sueltos, sin nada en el medio.
    box = (1.0, 0.0, 0.30, 0.0, 0.16, 0.0, 0.07)
    for index, midi in enumerate((72, 76, 79, 84, 82)):
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), 0.115,
              index * 0.085, 1.5 - index * 0.05,
              envelope=lambda p: math.exp(-4.2 * p) * min(1.0, p / 0.008),
              harmonics=box)
    _reverb(buffer, mix=0.26, decay=0.78, size=1.4)
    return _encode(_loudness(buffer, POWER_HIT * 0.78, LEVEL_HIT))


def _egg_prize() -> bytes:
    """
    Los seis huevos completos: la misma caja de musica, abierta entera.

    Es el premio de encontrarlos todos, asi que tiene que sonar a lo mismo
    y mas: la misma campanita, pero subiendo dos octavas en vez de una, con
    la caja resonando debajo y una sala de verdad atras. Una fanfarria de
    metal habria sonado a estrella, y una estrella se gana estudiando ---
    esto se gana buscando.

    **Todo lo que suena aca es del mismo acorde de do mayor.** El hallazgo
    suelto cierra con una nota de afuera que no resuelve --- la guinada ---
    y esta *no*: aquello es un chiste de un segundo y esto es lo ultimo que
    el programa tiene para dar. Una disonancia colgada al final de un premio
    no se lee como una guinada sino como algo que quedo sin terminar.
    """
    # Cinco segundos y medio para tres de campanas: lo que sobra es la cola,
    # que en un sonido de campana es la mitad de lo que uno escucha.
    buffer = _buffer(5.5)
    box = (1.0, 0.0, 0.30, 0.0, 0.16, 0.0, 0.07)
    subida = (60, 64, 67, 72, 76, 79, 84, 88, 91, 96)
    for index, midi in enumerate(subida):
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), 0.075,
              index * 0.075, 3.2 - index * 0.12,
              envelope=lambda p: math.exp(-2.6 * p) * min(1.0, p / 0.006),
              harmonics=box)
    # La nota que corona, arriba de todo y sola, cuando la subida ya se
    # apago. Es la tercera del mismo acorde --- mi, dos octavas y media por
    # encima de la fundamental de la caja ---, asi que llega tarde sin
    # discutirle nada a lo que ya esta sonando.
    _tone(buffer, 440.0 * 2.0 ** ((100 - 69) / 12.0), 0.11, 0.95, 2.4,
          envelope=lambda p: math.exp(-2.2 * p) * min(1.0, p / 0.006),
          harmonics=box)
    # Y la caja sosteniendo debajo, que es lo que la separa del hallazgo
    # suelto: aquel dura un segundo y este se queda.
    for midi in (48, 55, 60, 64):
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), 0.055, 0.10, 3.6,
              envelope=lambda p: math.exp(-1.1 * p) * min(1.0, p / 0.02),
              harmonics=box)
    _reverb(buffer, mix=0.34, decay=0.86, size=2.6)
    return _encode(_loudness(buffer, POWER_HIT * 0.86, LEVEL_HIT))


# ---------------------------------------------------------------------------
# Las visitas
# ---------------------------------------------------------------------------
#
# Todos van *a pedido*: una visita ocurre una vez en la vida del programa y
# sintetizarlos en cada arranque sería pagarlos siempre para usarlos casi
# nunca. Es el mismo trato que tienen los huevos de pascua.

def _clavier() -> bytes:
    """
    La llegada de Bach: un arpegio de clave.

    El clave no tiene matices --- la cuerda se pulsa con una púa y suena
    siempre igual de fuerte --- así que todas las notas van con la misma
    ganancia y la misma envolvente. Es un do menor arpegiado hacia arriba con
    la tercera de Picardía al final: mayor, que es como cierra él.
    """
    buffer = _buffer(4.6)
    #: Cuerdas pulsadas: muchos armónicos y ninguno dominante.
    wire = (1.0, 0.62, 0.48, 0.34, 0.26, 0.18, 0.12)
    line = [(48, 0.00), (55, 0.11), (60, 0.22), (63, 0.33), (67, 0.44),
            (72, 0.55), (75, 0.66), (79, 0.77)]
    for midi, start in line:
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), 0.085, start,
              2.6 - start, envelope=_pluck, harmonics=wire)
    # El acorde final, ya en mayor, sostenido debajo de la cola del arpegio.
    for midi in (48, 64, 67, 76):
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), 0.075, 0.9, 1.7,
              envelope=lambda p: math.exp(-1.6 * p) * min(1.0, p / 0.006),
              harmonics=wire)
    # Una sala de música, chica y con madera: el clave no se tocaba en una
    # catedral.
    _reverb(buffer, mix=0.22, decay=0.76, size=1.3)
    return _encode(_loudness(buffer, POWER_HIT * 0.85, LEVEL_HIT))


def _plainchant() -> bytes:
    """
    La llegada de Gregorio: organum a la quinta, sin acompañamiento.

    Es literalmente lo que él viene a explicar --- la misma línea corriendo
    cuatro escalones más abajo --- y por eso no lleva ni un acorde debajo:
    en el año novecientos no había ninguno.
    """
    # Siete segundos para cuatro de canto: los tres que sobran son la nave
    # vaciándose. En una iglesia de piedra una nota tarda eso en apagarse, y
    # cortarla antes es lo que hace que suene a grabación y no a lugar.
    buffer = _buffer(7.0)
    line = [(65, 0.0, 0.9), (67, 0.9, 0.7), (69, 1.6, 0.8), (67, 2.4, 0.6),
            (65, 3.0, 1.4)]
    for midi, start, length in line:
        for interval in (0, -7):
            _tone(buffer, 440.0 * 2.0 ** ((midi + interval - 69) / 12.0),
                  0.14 if interval == 0 else 0.10, start, length,
                  envelope=lambda p: _fade(p, 0.18, 0.30),
                  harmonics=_VOICE, vibrato=0.002)
    # Piedra otra vez, y más grande que la del coro: el organum se cantaba en
    # naves donde una nota tarda cuatro segundos en apagarse, y esa cola es
    # parte de por qué las quintas suenan como suenan.
    _reverb(buffer, mix=0.44, decay=0.91, size=3.6, damp=0.28)
    return _encode(_loudness(buffer, POWER_HIT * 0.9, LEVEL_HIT))


def _toll() -> bytes:
    """
    La entidad: una campana grande, con los parciales de una campana.

    Una campana no tiene armónicos: tiene **parciales**, y están en unas
    proporciones que no son múltiplos enteros ---0,5, 1, 1,2, 1,5, 2, 2,7---
    porque el metal no vibra como una cuerda. Eso es lo que hace que el oído
    no le encuentre una nota clara, y es lo que la vuelve incómoda sin que
    uno pueda decir qué tiene.

    El golpe del badajo es ruido de un instante, cada parcial se apaga a su
    propio ritmo ---los agudos primero, como en el metal de verdad--- y
    debajo queda el zumbido grave, que es el que dura.
    """
    rng = random.Random(9)
    buffer = _buffer(6.0)
    base = 68.0
    for ratio, gain, decay in ((0.50, 0.30, 0.45), (1.00, 0.26, 0.60),
                               (1.19, 0.17, 0.95), (1.56, 0.12, 1.30),
                               (2.00, 0.10, 1.70), (2.66, 0.06, 2.40),
                               (3.01, 0.04, 3.20), (4.07, 0.025, 4.20)):
        _tone(buffer, base * ratio, gain, 0.0, 6.0,
              envelope=lambda p, d=decay: (math.exp(-d * p * 6.0)
                                           * min(1.0, p / 0.002)))
    # El badajo.
    _noise(buffer, 0.35, 0.45, rng,
           lambda p: math.exp(-140.0 * p) * min(1.0, p / 0.0006))
    _band(buffer, 0.30, 1900.0, 6.0, rng,
          lambda p: math.exp(-60.0 * p))
    _reverb(buffer, mix=0.40, decay=0.90, size=3.0, damp=0.45)
    return _encode(_loudness(buffer, POWER_HIT, LEVEL_HIT))


def _hollow() -> bytes:
    """
    La cama de la entidad: un bordón que late y no llega a ser una nota.

    Dos graves separados por menos de un hercio, así que lo único que se
    mueve es la interferencia entre los dos: sube y baja sola cada dos
    segundos y medio, y no hay ni melodía ni pulso. Encima, una banda
    resonante que se pasea muy despacio ---el único movimiento de todo el
    sonido--- y un roce de aire casi inaudible que impide que se lea como un
    tono de prueba.
    """
    rng = random.Random(31)
    seconds = 8.0
    buffer = _buffer(seconds)
    for frequency, gain in ((41.2, 0.26), (41.65, 0.24), (61.8, 0.10),
                            (82.4, 0.055), (123.5, 0.022)):
        _tone(buffer, frequency, gain, 0.0, seconds,
              harmonics=(1.0, 0.20, 0.07))
    _band(buffer, 0.10, 240.0, 5.0, rng, None,
          lambda p: 1.0 + 0.45 * math.sin(_TWO_PI * p))
    _noise(buffer, 0.05, 0.006, rng)
    _reverb(buffer, mix=0.28, decay=0.86, size=2.6)
    return _encode(_loudness(_seamless(buffer, 0.7), POWER_BED, LEVEL_BED, tail=0.0))


def _gale() -> bytes:
    """
    El viento de la visión, que es el del valle pero sin nadie adentro.

    Más grave, más grande y sin pájaros: lo que hay que sentir es que no hay
    nadie en kilómetros. La banda de abajo se pasea muy despacio ---un
    frente de aire tarda en pasar--- y la de arriba silba de a ratos, que es
    el único detalle que dice que hay algo material ahí afuera: alambrados,
    postes, pasto.
    """
    rng = random.Random(1938)
    seconds = 10.0
    buffer = _buffer(seconds)

    def gusts(period: float, depth: float, phase: float = 0.0):
        def shape(position: float) -> float:
            wave = math.sin(_TWO_PI * (position * period + phase))
            return max(0.05, 1.0 - depth + depth * (0.5 + 0.5 * wave))
        return shape

    def drift(period: float, span: float, phase: float = 0.0):
        def shape(position: float) -> float:
            return 1.0 + span * math.sin(_TWO_PI * (position * period + phase))
        return shape

    _noise(buffer, 0.40, 0.024, rng, gusts(1.0, 0.65))
    _noise(buffer, 0.16, 0.006, rng, gusts(0.5, 0.45, 0.35))
    _band(buffer, 0.42, 165.0, 3.0, rng, gusts(1.0, 0.70), drift(1.0, 0.40))
    _band(buffer, 0.26, 520.0, 5.5, rng, gusts(2.0, 0.85, 0.4),
          drift(2.0, 0.35, 0.6))
    _band(buffer, 0.13, 1250.0, 12.0, rng, gusts(3.0, 0.92, 0.15),
          drift(3.0, 0.30, 0.1))
    _tone(buffer, 41.0, 0.09, 0.0, seconds,
          envelope=lambda p: 0.6 + 0.4 * math.sin(_TWO_PI * p * 2.0),
          harmonics=(1.0, 0.3))
    _reverb(buffer, mix=0.20, decay=0.82, size=1.8)
    return _encode(_loudness(_seamless(buffer, 0.9), POWER_SOLO, LEVEL_BED,
                             tail=0.0))


def _train() -> bytes:
    """
    El tren que cruza a lo lejos: bufidos, juntas de riel, rumor y silbato.

    Lo que hace que un tren suene a tren es el ritmo, no el timbre. Van dos
    ritmos encimados y desfasados: el **bufido** de la locomotora ---cuatro
    por vuelta de rueda, ruido soplado por una banda grave--- y el **clac**
    de las juntas de riel, que es metálico, agudo y llega de a pares porque
    cada vagón tiene dos ejes.

    El silbato es un acorde y no una nota: los silbatos de vapor tienen
    varios tubos afinados juntos a propósito, y por eso suenan a lamento y no
    a pito de árbitro. Éste es menor con la séptima encima.

    Todo pasa: entra desde lejos, cruza y se va, y a medida que se aleja
    pierde los agudos, que es lo único que hace la distancia con el sonido.
    """
    rng = random.Random(1927)
    seconds = 8.0
    buffer = _buffer(seconds)

    def distance(position: float) -> float:
        """Más fuerte en el medio: es cuando está justo enfrente."""
        return 0.10 + 0.90 * math.sin(math.pi * position) ** 1.6

    # El rumor: la masa entera moviéndose.
    _noise(buffer, 0.22, 0.008, rng, distance)
    _tone(buffer, 33.0, 0.14, 0.0, seconds,
          envelope=distance, harmonics=(1.0, 0.45, 0.18))
    _band(buffer, 0.20, 120.0, 2.5, rng, distance)

    # Los bufidos de la chimenea: chas-chas-chas-chas, acelerando apenas.
    moment = 0.30
    while moment < seconds - 0.4:
        local = distance(moment / seconds)
        puff = _buffer(0.30)
        _band(puff, 1.0, 210.0, 1.6, rng,
              lambda p: math.exp(-9.0 * p) * min(1.0, p / 0.01))
        _noise(puff, 0.35, 0.30, rng,
               lambda p: math.exp(-14.0 * p) * min(1.0, p / 0.006))
        first = int(moment * SAMPLE_RATE)
        for offset, value in enumerate(puff):
            if first + offset < len(buffer):
                buffer[first + offset] += value * 0.55 * local
        moment += 0.235 - 0.03 * local

    # Y las juntas: dos golpes secos y metálicos por vagón.
    moment = 0.55
    while moment < seconds - 0.4:
        local = distance(moment / seconds)
        for offset in (0.0, 0.10):
            for frequency, gain in ((1350.0, 0.055), (2400.0, 0.030),
                                    (760.0, 0.045)):
                _tone(buffer, frequency, gain * local, moment + offset, 0.06,
                      envelope=lambda p: math.exp(-32.0 * p))
        moment += rng.uniform(0.62, 0.70)

    # El silbato, una sola vez y antes de pasar: se oye venir.
    for midi, gain in ((69, 0.16), (72, 0.13), (76, 0.09), (79, 0.05)):
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), gain, 1.30, 1.70,
              envelope=lambda p: _fade(p, 0.14, 0.40),
              harmonics=(1.0, 0.28, 0.10), vibrato=0.005)
    # El aire del silbato, que es la mitad de por qué se reconoce.
    _band(buffer, 0.20, 900.0, 12.0, rng,
          lambda p: _fade(p, 0.14, 0.40) if 0.16 < p < 0.38 else 0.0)

    _reverb(buffer, mix=0.30, decay=0.86, size=2.2)
    _polish(buffer, 0.55, 0.10)
    return _encode(_loudness(buffer, POWER_HIT, LEVEL_HIT))


def _owls() -> bytes:
    """
    Dos búhos, uno lejos del otro.

    El canto es casi una sinusoide ---por eso un búho se imita soplando en
    las manos--- así que lleva un solo armónico débil y nada más. Lo que lo
    vuelve un animal y no una flauta son dos detalles: el soplido de aire al
    empezar cada nota, y que la altura cae un poco mientras dura.

    El segundo contesta más agudo, más lejos y con más cola. Dos animales, no
    uno con eco.
    """
    rng = random.Random(3)
    buffer = _buffer(7.0)

    def hoot(start: float, frequency: float, length: float, gain: float):
        _tone(buffer, frequency, gain, start, length,
              envelope=lambda p: _fade(p, 0.26, 0.46),
              harmonics=(1.0, 0.07), vibrato=0.006, glide=0.92)
        # El aire de la primera décima: es lo único que separa un búho de un
        # tono puro.
        _band(buffer, gain * 0.22, frequency * 2.0, 7.0, rng,
              lambda p, s=start, l=length: (
                  math.exp(-26.0 * (p - s / 7.0) * 7.0 / max(l, 0.01))
                  if 0.0 <= p - s / 7.0 < 0.05 else 0.0))

    # Hoo — hoo-hoo — hoooo, que es como llama un búho de verdad.
    for start, length in ((0.0, 0.52), (0.90, 0.26), (1.26, 0.28),
                          (1.80, 0.72)):
        hoot(start, 226.0, length, 0.26)
    # Y el que contesta, cuatro segundos después y desde más lejos.
    for start, length in ((4.20, 0.44), (4.98, 0.24), (5.30, 0.58)):
        hoot(start, 303.0, length, 0.10)

    _reverb(buffer, mix=0.34, decay=0.86, size=2.4)
    return _encode(_loudness(buffer, POWER_HIT * 0.9, LEVEL_HIT))


def _crossroads() -> bytes:
    """
    El ruido con el que aparece el de la visión.

    No es un susto: es algo que ya estaba y que recién ahora se deja oír. Por
    eso todo entra desde abajo y desde el silencio ---dos graves separados
    por un tritono, el mismo intervalo que el señor del sombrero--- y por eso
    no hay ningún golpe en el ataque.

    Encima van dos cosas que no pertenecen a ninguna escala: unos parciales
    metálicos afinados a distancias que ningún instrumento produce, y un
    aullido de aire que baja hasta perderse. La cola de reverberación es
    enorme a propósito: lo que tiene que quedar después es la sensación de
    que el campo es más grande de lo que se ve.
    """
    rng = random.Random(1911)
    seconds = 6.0
    buffer = _buffer(seconds)

    def rise(position: float) -> float:
        return math.sin(math.pi * min(1.0, position * 1.15)) ** 0.85

    for frequency, gain in ((38.5, 0.34), (54.4, 0.26), (77.0, 0.14)):
        _tone(buffer, frequency, gain, 0.0, 5.2, envelope=rise,
              harmonics=(1.0, 0.45, 0.24, 0.12), vibrato=0.003)
    # Y un golpe sordo en el arranque. Sin él, el sonido *aparecía* sin que
    # se pudiera decir cuándo había empezado --- que es elegante en un
    # ambiente y es exactamente lo contrario de lo que hace falta acá: la
    # figura ya está parada en el camino y el ruido tiene que llegar con
    # ella, no colarse por detrás.
    _tone(buffer, 46.0, 0.42, 0.0, 2.2,
          envelope=lambda p: math.exp(-3.4 * p) * min(1.0, p / 0.004),
          harmonics=(1.0, 0.5, 0.2), glide=0.6)
    _noise(buffer, 0.30, 0.30, rng,
           lambda p: math.exp(-22.0 * p * 6.0) * min(1.0, p / 0.001))
    # Los parciales inarmónicos: metal que nadie golpeó.
    for ratio, gain, start in ((7.31, 0.045, 0.5), (10.77, 0.032, 0.9),
                               (14.09, 0.020, 1.4)):
        _tone(buffer, 38.5 * ratio, gain, start, 4.0,
              envelope=lambda p: math.sin(math.pi * p) ** 1.5,
              vibrato=0.004)
    # El aullido: una banda angosta que baja de mil a cien.
    _band(buffer, 0.30, 1000.0, 9.0, rng,
          lambda p: math.sin(math.pi * min(1.0, p * 1.3)) ** 1.4,
          lambda p: 1.0 - 0.90 * p)
    # Y el aire de fondo, que es lo que impide que se lea como un sintetizador.
    _noise(buffer, 0.16, 0.020, rng, rise)
    _reverb(buffer, mix=0.42, decay=0.90, size=3.2, damp=0.4)
    return _encode(_loudness(buffer, POWER_HIT, LEVEL_HIT))


# ---------------------------------------------------------------------------
# Los huevos de pascua
# ---------------------------------------------------------------------------
#
def _tritone() -> bytes:
    """
    El intervalo con el que el señor cambia de cara.

    *Diabolus in musica*: sol y do sostenido, tres tonos justos, el intervalo
    que la práctica común prohibió durante siglos y que el libro explica en
    su capítulo de disonancias. Suena entero de una vez ---no es una melodía,
    es un golpe--- con la quinta que uno espera **ausente**: lo que raspa es
    justamente que no esté.

    Lo que lo volvió oscuro es lo que tiene alrededor del golpe. Antes hay un
    ruido que **crece hacia adentro**, como si el golpe tirara del aire; el
    golpe mismo está saturado, que es lo que le da el cuerpo de algo roto; y
    después queda una cola larga de reverberación con las dos notas batiendo
    entre ellas, sin llegar nunca a ponerse de acuerdo.
    """
    rng = random.Random(666)
    seconds = 5.6
    buffer = _buffer(seconds)
    strike = 0.42

    # Lo que pasa **antes**: aire que se junta y se va hacia el golpe.
    _band(buffer, 0.30, 300.0, 4.0, rng,
          lambda p: max(0.0, (p / (strike / seconds))) ** 3.0
          if p < strike / seconds else 0.0,
          lambda p: 0.6 + 2.2 * p)

    def hit(position: float) -> float:
        return math.exp(-1.5 * position) * min(1.0, position / 0.003)

    # Sol2 y Do#3: el tritono, abajo, donde más golpea. Armónicos impares
    # marcados, que es lo que hace que dos notas juntas suenen a metal.
    for frequency, gain in ((98.0, 0.34), (138.59, 0.32)):
        _tone(buffer, frequency, gain, strike, seconds - strike, envelope=hit,
              harmonics=(1.0, 0.22, 0.55, 0.14, 0.34, 0.10, 0.20),
              vibrato=0.002)
        # La octava por encima, más corta: le da el filo sin subirle el peso.
        _tone(buffer, frequency * 2, gain * 0.30, strike, 1.4,
              envelope=lambda p: math.exp(-4.0 * p) * min(1.0, p / 0.003),
              harmonics=(1.0, 0.3, 0.18))
    # El sub, una octava y media debajo del sol: es lo que se siente antes de
    # oírse.
    _tone(buffer, 49.0, 0.30, strike, seconds - strike,
          envelope=lambda p: math.exp(-1.2 * p) * min(1.0, p / 0.006),
          harmonics=(1.0, 0.5, 0.25), vibrato=0.010)
    # El impacto: ruido de un instante, sin el cual el acorde entra sin
    # haber golpeado nada.
    _noise(buffer, 0.55, 0.55, rng,
           lambda p: math.exp(-40.0 * max(0.0, p - strike / seconds) * seconds)
           if p >= strike / seconds else 0.0)
    _saturate(buffer, 1.3)
    _reverb(buffer, mix=0.34, decay=0.88, size=2.6, damp=0.42)
    _polish(buffer, 0.85, 0.14)
    return _encode(_loudness(buffer, POWER_HIT, LEVEL_HIT))


# Estos tres NO los sintetiza `prepare`: se hacen a pedido, la primera vez
# que alguien da con la combinación que los dispara. Son sonidos que la
# enorme mayoría de las partidas no va a escuchar nunca, y hacer esperar a
# la historia mientras se calculan sería pagarlos todas las veces para
# usarlos casi ninguna. Ver `summon`.

def _zombie() -> bytes:
    """
    El rugido: un gruñido grave que baja, se rompe y termina en agua.

    Un gruñido es una voz que no logra cerrar: las cuerdas vocales golpean
    irregularmente y el resultado tiene, encima del tono, dos temblores
    rápidos que no son múltiplos entre sí. Eso es todo el efecto ---la
    aspereza sale de que los dos temblores nunca coincidan--- y encima van
    dos bandas resonantes que hacen de garganta y boca.

    Baja casi una octava mientras dura, se satura al final ---la garganta se
    rompe--- y cierra con el chasquido húmedo de algo que traga.
    """
    rng = random.Random(1968)
    buffer = _buffer(3.0)

    def growl(position: float) -> float:
        shape = _fade(position, attack=0.05, release=0.42)
        rough = (0.62
                 + 0.24 * math.sin(_TWO_PI * 27.0 * position * 3.0)
                 + 0.14 * math.sin(_TWO_PI * 41.0 * position * 3.0))
        return shape * rough

    _tone(buffer, 92.0, 0.36, 0.0, 2.8, envelope=growl,
          harmonics=(1.0, 0.78, 0.60, 0.44, 0.32, 0.22, 0.15), vibrato=0.02,
          glide=0.55)
    # Una segunda voz desafinada por debajo: dos gargantas, no una.
    _tone(buffer, 61.0, 0.24, 0.06, 2.6, envelope=growl,
          harmonics=(1.0, 0.55, 0.34, 0.2), glide=0.62)
    # La garganta y la boca: dos formantes, que es lo que separa un animal de
    # un motor. Van con la banda más angosta ---q más alto--- de lo que
    # estaban: un resonador ancho deja pasar casi todo el ruido que le entra,
    # y lo que se escuchaba era el ruido y no la garganta.
    _band(buffer, 0.30, 420.0, 7.0, rng, growl,
          lambda p: 1.0 - 0.35 * p)
    _band(buffer, 0.14, 980.0, 10.0, rng, lambda p: growl(p) * 0.7,
          lambda p: 1.0 - 0.25 * p)
    # El aire de la garganta, y **poco**: es el aliento de algo que ruge, no
    # una tormenta. Con el triple de ruido, lo que quedaba era un rugido
    # sonando detrás de una cascada.
    _noise(buffer, 0.07, 0.10, rng,
           lambda p: _fade(p, attack=0.08, release=0.5) ** 1.6)
    _saturate(buffer, 1.35)
    # El chasquido húmedo del final, cuando el rugido se corta.
    _tone(buffer, 190.0, 0.30, 2.62, 0.34,
          envelope=lambda p: math.exp(-8.0 * p), glide=0.35)
    _band(buffer, 0.26, 700.0, 3.0, rng,
          lambda p: math.exp(-40.0 * max(0.0, p - 0.874) * 3.0)
          if p >= 0.874 else 0.0, lambda p: 1.0 - 0.6 * p)
    _reverb(buffer, mix=0.24, decay=0.80, size=1.6)
    return _encode(_loudness(buffer, POWER_JOKE, LEVEL_JOKE))


def _fox_scream() -> bytes:
    """
    El grito del zorro: corto, agudo y desagradable a propósito.

    Un zorro no aúlla: grita, y suena a alguien. Lo que lo vuelve
    insoportable ---y por lo tanto perfecto para un susto--- son tres cosas:
    la altura sube mientras dura, el vibrato es demasiado rápido para una
    voz, y por encima hay una modulación en anillo que parte cada armónico en
    dos y deja el sonido sin ninguna relación consigo mismo.

    Son dos gritos encadenados, el segundo más agudo, como cuando de verdad
    hay uno en el fondo de una casa a las tres de la mañana.
    """
    rng = random.Random(9)
    buffer = _buffer(1.9)
    for start, base, seconds in ((0.0, 760.0, 0.46), (0.40, 930.0, 0.62)):
        _tone(buffer, base, 0.32, start, seconds,
              envelope=lambda p: math.exp(-2.0 * p) * min(1.0, p / 0.008),
              harmonics=(1.0, 0.62, 0.46, 0.30, 0.22, 0.14), vibrato=0.055,
              glide=1.62)
        # La quinta desafinada por encima: lo que raspa.
        _tone(buffer, base * 1.47, 0.16, start, seconds,
              envelope=lambda p: math.exp(-2.6 * p) * min(1.0, p / 0.008),
              vibrato=0.04, glide=1.55)
        # Y el aire del ataque, corto y arriba.
        _band(buffer, 0.22, base * 2.4, 8.0, rng,
              lambda p, s=start / 1.9: (
                  math.exp(-70.0 * (p - s)) if 0.0 <= p - s < 0.06 else 0.0))
    # El anillo: cada componente se parte en dos y ninguna de las dos es
    # armónica de nada. Poca profundidad --- con más, deja de ser un animal.
    _ring(buffer, 52.0, depth=0.26)
    _saturate(buffer, 1.55)
    _reverb(buffer, mix=0.20, decay=0.74, size=1.1)
    return _encode(_loudness(buffer, POWER_JOKE, LEVEL_JOKE))


def _blast() -> bytes:
    """
    La explosión: el golpe, el rugido y el trueno que rueda y no termina.

    Una explosión grande no suena como una chica más fuerte: suena
    **distinta**, y la diferencia es el tiempo. Primero llega un chasquido
    seco y clarísimo ---el frente de presión---, después el rugido, y
    después, durante segundos, un trueno que va y viene mientras rebota
    contra todo lo que hay alrededor. Eso último es lo que dice el tamaño, y
    es lo que acá hacen la cola de la reverberación y el filtro cerrándose:
    lo lejano pierde los agudos, así que un ruido que se apaga *de arriba
    hacia abajo* se lee como algo enorme y lejos.
    """
    rng = random.Random(1945)
    seconds = 7.5
    buffer = _buffer(seconds)
    # El frente: dura lo que dura un chasquido.
    _noise(buffer, 1.0, 0.72, rng,
           lambda p: math.exp(-70.0 * p * seconds) * min(1.0, p / 0.0008))
    # El rugido: ruido grave que se abre y se apaga despacio.
    _noise(buffer, 0.90, 0.040, rng,
           lambda p: min(1.0, p / 0.02) * math.exp(-2.2 * p * seconds / 5.0))
    # El infrasonido, que casi no se oye: se siente. Cae de sesenta a
    # veintipico, que es el barrido que hace cualquier explosión de verdad.
    _tone(buffer, 62.0, 0.55, 0.0, 5.6,
          envelope=lambda p: math.exp(-1.1 * p) * min(1.0, p / 0.006),
          harmonics=(1.0, 0.35, 0.12), glide=0.38)
    # El trueno que rueda: ruido grave con la amplitud yendo y viniendo, que
    # es exactamente lo que hace el eco de algo grande contra el terreno.
    _band(buffer, 0.55, 90.0, 1.2, rng,
          lambda p: min(1.0, p / 0.06) * math.exp(-1.5 * p)
          * (0.55 + 0.45 * math.sin(_TWO_PI * p * 3.5)),
          lambda p: 1.0 - 0.45 * p)
    # Y el aire que vuelve al final.
    _noise(buffer, 0.14, 0.10, rng,
           lambda p: min(1.0, p / 0.35) * math.exp(-1.4 * p))
    _saturate(buffer, 1.1)
    _reverb(buffer, mix=0.38, decay=0.90, size=3.0, damp=0.5)
    _polish(buffer, 0.9, 0.035)
    return _encode(_loudness(buffer, POWER_JOKE, LEVEL_JOKE))


def _blues() -> bytes:
    """
    Lo último que se oye en la visión: una guitarra sola, con slide.

    Cuando la figura desaparece del camino queda esto, y es lo único de toda
    la escena que se parece a música. Es un giro de blues en mi: la tercera
    menor arrastrada con el cuello de botella ---la nota que en el piano no
    existe y que sólo se puede alcanzar resbalando--- y después el acorde con
    séptima, dejado sonar hasta que se apaga solo.

    La cuerda pulsada es un tono con muchos armónicos y una envolvente que
    cae de golpe y después despacio; el arrastre es el mismo tono con la
    frecuencia moviéndose mientras suena, que es literalmente lo que hace un
    slide.
    """
    rng = random.Random(1938)
    buffer = _buffer(8.0)
    #: Cuerda de acero: muchos parciales y ninguno mandando.
    string = (1.0, 0.66, 0.48, 0.36, 0.26, 0.19, 0.13, 0.09)

    def note(midi: float, start: float, length: float, gain: float,
             glide: float = 1.0):
        _tone(buffer, 440.0 * 2.0 ** ((midi - 69) / 12.0), gain, start, length,
              envelope=lambda p: math.exp(-1.5 * p) * min(1.0, p / 0.004),
              harmonics=string, glide=glide, vibrato=0.004)
        # El roce de la púa: un chasquido de aire encima del ataque.
        _band(buffer, gain * 0.5, 2600.0, 4.0, rng,
              lambda p, s=start / 6.0: (
                  math.exp(-90.0 * (p - s)) if 0.0 <= p - s < 0.05 else 0.0))

    # El arrastre de entrada: entra dos trastes abajo y sube hasta la nota,
    # que es literalmente lo que hace un cuello de botella sobre la cuerda.
    # Antes el arrastre era de un tono y no se oía como arrastre sino como
    # una nota desafinada; con tres semitonos y medio segundo, se oye.
    note(51, 0.00, 1.8, 0.30, glide=2.0 ** (4 / 12.0))
    note(62, 0.62, 1.5, 0.26, glide=2.0 ** (-2 / 12.0))
    note(59, 1.15, 1.7, 0.28, glide=2.0 ** (1 / 12.0))
    # Y el mi con séptima, abierto, dejado sonar.
    for index, midi in enumerate((40, 52, 56, 59, 62, 64)):
        note(midi, 1.85 + index * 0.045, 4.0, 0.17)
    # El vibrato de la mano al final, sobre la nota más aguda.
    _tone(buffer, 440.0 * 2.0 ** ((64 - 69) / 12.0), 0.07, 2.4, 3.4,
          envelope=lambda p: math.exp(-1.1 * p) * min(1.0, p / 0.05),
          harmonics=string, vibrato=0.012)
    _reverb(buffer, mix=0.34, decay=0.88, size=2.6)
    return _encode(_loudness(buffer, POWER_HIT, LEVEL_HIT))


#: Cómo se arma cada sonido, y si está pensado para repetirse en bucle.
_RECIPES: Dict[str, tuple] = {
    "valley": (_valley_bed, True),
    "light": (_light_bed, True),
    "wind": (_wind_gust, False),
    "hellfire": (_hellfire, False),
    "choir_up": (lambda: _organum(True), False),
    "choir_down": (lambda: _organum(False), False),
    "sax": (_sax_outro, False),
    "chime": (_chime, False),
    "tritone": (_tritone, False),
    "blip_devil": (lambda: _blip("devil"), False),
    "blip_django": (lambda: _blip("django"), False),
    "blip_jesus": (lambda: _blip("jesus"), False),
    "blip_narrator": (lambda: _blip("narrator"), False),
    "blip_bach": (lambda: _blip("bach"), False),
    "blip_gregory": (lambda: _blip("gregory"), False),
    "blip_watcher": (lambda: _blip("watcher"), False),
    "clavier": (_clavier, False),
    "plainchant": (_plainchant, False),
    "toll": (_toll, False),
    "hollow": (_hollow, True),
    "gale": (_gale, True),
    "crossroads": (_crossroads, False),
    "train": (_train, False),
    "owls": (_owls, False),
    "blues": (_blues, False),
    "zombie": (_zombie, False),
    "fox": (_fox_scream, False),
    "blast": (_blast, False),
    "star_one": (lambda: _fanfare(1), False),
    "star_two": (lambda: _fanfare(2), False),
    "star_three": (lambda: _fanfare(3), False),
    "egg_found": (_egg_found, False),
    "egg_prize": (_egg_prize, False),
}

#: Los que `prepare` NO sintetiza. Se hacen a pedido con `summon`, porque
#: casi ninguna sesión los va a necesitar y el modo historia no tiene por
#: qué esperarlos.
_ON_DEMAND = frozenset({"zombie", "fox", "blast",
                        # Las visitas: cada una ocurre una vez en la vida del
                        # programa, así que se sintetizan cuando toca y no en
                        # cada arranque. Los blips no --- son cuarenta
                        # milisegundos cada uno --- y encima tienen que estar
                        # listos apenas se abre la boca.
                        "clavier", "plainchant", "toll", "hollow",
                        "gale", "crossroads", "train", "owls", "blues",
                        # Las estrellas y los huevos. Una sesion cualquiera
                        # no consigue ninguna de las dos cosas, y cuando las
                        # consigue hay un velo a pantalla completa que da de
                        # sobra para sintetizar dos segundos de campanas.
                        "star_one", "star_two", "star_three", "egg_found",
                        "egg_prize"})


# ---------------------------------------------------------------------------
# Dónde quedan los archivos
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_folder: Optional[str] = None
_tag_cache: Optional[str] = None
_files: Dict[str, str] = {}
_ready = threading.Event()
_building = False


#: Cada cuánto cambia de hilo el intérprete mientras se está sintetizando.
#:
#: Sintetizar es un bucle de muestras en Python puro, y con el intervalo de
#: fábrica --- 5 ms --- el hilo que lo corre se queda con el GIL en tandas
#: largas: la ventana entera se clavaba hasta tres segundos seguidos, unos
#: pocos segundos después de abrir el programa, que es cuando arranca
#: `prepare`. Medido sobre la ventana real: 2909 ms de peor pausa con el
#: valor de fábrica, 24 ms con este. Se pone mientras hay un hilo de
#: síntesis vivo y se devuelve como estaba cuando termina el último ---
#: es un ajuste del intérprete entero, no de este módulo.
_FINE_SWITCH = 0.0005
_switch_lock = threading.Lock()
_synthesising = 0
_switch_before: Optional[float] = None


def _breathe_in() -> None:
    global _synthesising, _switch_before
    with _switch_lock:
        if _synthesising == 0:
            try:
                _switch_before = sys.getswitchinterval()
                sys.setswitchinterval(_FINE_SWITCH)
            except (AttributeError, ValueError):
                _switch_before = None
        _synthesising += 1


def _breathe_out() -> None:
    global _synthesising, _switch_before
    with _switch_lock:
        _synthesising = max(0, _synthesising - 1)
        if _synthesising == 0 and _switch_before is not None:
            try:
                sys.setswitchinterval(_switch_before)
            except (AttributeError, ValueError):
                pass
            _switch_before = None


@contextlib.contextmanager
def fine_switching():
    """
    Que el intérprete cambie de hilo seguido mientras dura este bloque.

    Es `_breathe_in` / `_breathe_out` con nombre público, porque la síntesis
    **no es el único** trabajo del programa que se queda con el GIL en tandas
    largas: la búsqueda del algoritmo genético hace exactamente lo mismo
    ---cruzar y mutar son bucles cerrados de Python--- y con progresiones
    largas clavaba la ventana más de un segundo entero, que es tiempo de
    sobra para que Windows deje la pantalla a medio repintar.

    Va acá y no duplicada en `app.py` a propósito: `setswitchinterval` es un
    ajuste **del intérprete entero**, así que dos módulos manejándolo por su
    cuenta se pisarían ---uno lo devolvería a 5 ms mientras el otro todavía
    lo necesita fino---. El contador es uno solo y el valor original vuelve
    cuando sale el último que entró, sea la síntesis o la búsqueda.
    """
    _breathe_in()
    try:
        yield
    finally:
        _breathe_out()


def _tag() -> str:
    """
    La firma de *estas* recetas.

    Es el resumen del código fuente de este módulo, así que cambia sola en
    cuanto se toca un sonido. Es lo que permite guardar los archivos entre
    corridas sin correr el riesgo de que mañana suene la versión vieja de
    algo: si la receta cambió, la carpeta es otra y se sintetiza de nuevo.

    Empaquetado no hay código fuente, así que ahí cae en la versión del
    programa, que es lo mismo con menos resolución: el ejecutable no se
    edita, se reemplaza.
    """
    global _tag_cache
    if _tag_cache is not None:
        return _tag_cache
    try:
        with open(__file__, "rb") as handle:
            digest = hashlib.md5(handle.read()).hexdigest()[:10]
    except (OSError, NameError):                            # noqa: BLE001
        from . import __version__
        digest = str(__version__).replace(".", "-")
    _tag_cache = digest
    return digest


def _cache_folder() -> str:
    """
    Dónde viven los archivos, entre una corrida y la siguiente.

    **No es una carpeta nueva cada vez.** Sintetizar los veintiocho sonidos
    lleva unos veinte segundos, y hacerlo en cada arranque era pagar ese
    precio todos los días para obtener siempre exactamente el mismo
    resultado: son funciones puras con semillas fijas, así que el archivo de
    hoy es idéntico al de ayer, byte por byte.

    Va en el temporal del sistema y no al lado del programa: son archivos
    derivados, no datos del usuario, y borrarlos no le cuesta nada más que
    volver a esperar una vez.
    """
    global _folder
    if _folder is None:
        folder = os.path.join(tempfile.gettempdir(),
                              f"chordweaver-sfx-{_tag()}")
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            folder = tempfile.mkdtemp(prefix="chordweaver-sfx-")
        _folder = folder
    return _folder


def _write(name: str, frames: bytes) -> str:
    """
    Escribir un sonido, entero o nada.

    Se escribe con otro nombre y recién al terminar se lo pone en su lugar.
    Un archivo a medio escribir ---el programa cerrado en la mitad--- se
    quedaría en la carpeta para siempre y la corrida siguiente lo adoptaría
    como bueno, así que el sonido sonaría cortado hasta que alguien borrara
    el temporal a mano.
    """
    folder = _cache_folder()
    path = os.path.join(folder, f"{name}.wav")
    partial = os.path.join(folder, f"{name}.part")
    with wave.open(partial, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(frames)
    try:
        os.replace(partial, path)
    except OSError:
        return partial
    return path


def _adopt_cache() -> None:
    """
    Quedarse con lo que dejó una corrida anterior.

    Son un par de docenas de consultas al sistema de archivos y se hacen una
    vez, antes de ponerse a calcular. Todo lo que ya esté escrito deja de
    ser trabajo.
    """
    folder = _cache_folder()
    with _lock:
        for name in _RECIPES:
            if name in _files:
                continue
            path = os.path.join(folder, f"{name}.wav")
            try:
                if os.path.getsize(path) > 44:
                    _files[name] = path
            except OSError:
                continue


def prepare(on_ready: Optional[Callable[[], None]] = None) -> None:
    """
    Sintetizar todo en un hilo aparte, una sola vez.

    Se llama en cuanto el modo historia se vuelve posible, bastante antes de
    que suene nada: sintetizar los doce sonidos lleva un rato y hacerlo en el
    hilo de la interfaz congelaría la ventana justo cuando aparece el
    personaje. Si la cinemática arranca antes de que esté listo, lo que
    todavía no existe simplemente no suena.
    """
    global _building
    with _lock:
        if _building:
            return
        _building = True

    def work() -> None:
        # Lo que ya está escrito de una corrida anterior no se vuelve a
        # calcular: es la diferencia entre veinte segundos y ninguno.
        _adopt_cache()
        _breathe_in()
        try:
            for name, (maker, _loops) in _RECIPES.items():
                if name in _ON_DEMAND:
                    continue
                with _lock:
                    if name in _files:
                        continue
                try:
                    path = _write(name, maker())
                except Exception:                           # noqa: BLE001
                    continue
                with _lock:
                    _files[name] = path
        finally:
            _breathe_out()
        _ready.set()
        # Y después, sin apuro y sin que nadie espere, los que se hacen «a
        # pedido». Antes se dejaban para el momento en que alguien diera con
        # ellos porque casi ninguna sesión los iba a escuchar, y sintetizar
        # doce sonidos que no se van a usar era regalar veinte segundos de
        # procesador. Con la caché en disco eso cambió: ahora se pagan **una
        # vez en la vida del programa** y no una por arranque, y a cambio la
        # escena que el usuario pida ---la que sea--- se abre al instante en
        # vez de hacerlo esperar con la pantalla quieta. Va al final y con la
        # bandera de listo ya puesta, así que nada de lo que sí hace falta
        # espera por esto.
        _breathe_in()
        try:
            for name in _RECIPES:
                with _lock:
                    if name in _files:
                        continue
                try:
                    path = _write(name, _RECIPES[name][0]())
                except Exception:                           # noqa: BLE001
                    continue
                with _lock:
                    _files[name] = path
        finally:
            _breathe_out()
        # Los alias NO se abren acá. MCI le cuelga cada dispositivo al hilo
        # que lo abrió y se los cierra en silencio cuando ese hilo termina,
        # así que abrirlos desde el hilo de síntesis dejaba doce alias
        # muertos: `play` no fallaba, no se quejaba, y no sonaba nada. Se
        # abren solos en la primera reproducción, que siempre ocurre en el
        # hilo de la interfaz --- el mismo que va a seguir vivo.
        if on_ready is not None:
            on_ready()

    threading.Thread(target=work, daemon=True).start()


def is_ready() -> bool:
    return _ready.is_set()


def made(name: str) -> bool:
    """¿Ya está sintetizado este sonido? Lo pregunta el hilo de la interfaz."""
    with _lock:
        return name in _files


def summon(name: str, on_ready: Optional[Callable[[], None]] = None) -> None:
    """
    Sintetizar un sonido suelto, en un hilo aparte, y avisar cuando esté.

    Es el camino de los huevos de pascua: un sonido que no vale la pena
    calcular en cada arranque, pero que cuando hace falta tiene que estar en
    seguida. Si ya se sintetizó antes, ``on_ready`` se llama de una.

    ``on_ready`` corre en el hilo que sintetiza, así que lo que haga con la
    ventana tiene que volver al hilo de Tk --- y **reproducir también**: MCI
    le cuelga cada alias al hilo que lo abrió. Quien llama a esto agenda el
    ``play`` con ``after``.
    """
    with _lock:
        done = name in _files
    if not done and name in _RECIPES:
        _adopt_cache()
        with _lock:
            done = name in _files
    if done or name not in _RECIPES:
        if on_ready is not None and done:
            on_ready()
        return

    def work() -> None:
        _breathe_in()
        try:
            path = _write(name, _RECIPES[name][0]())
        except Exception:                                   # noqa: BLE001
            return
        finally:
            _breathe_out()
        with _lock:
            _files[name] = path
        if on_ready is not None:
            on_ready()

    threading.Thread(target=work, daemon=True).start()


def summon_all(names: Sequence[str],
               on_ready: Optional[Callable[[], None]] = None) -> None:
    """
    Sintetizar varios sonidos **en un solo hilo** y en el orden pedido.

    Es lo mismo que llamar a :func:`summon` varias veces, salvo por lo único
    que importa: un hilo en vez de cinco. Sintetizar es trabajo de CPU puro y
    en Python los hilos no lo reparten ---se turnan---, así que cinco hilos
    no terminan antes: terminan **más tarde** que uno solo, porque además
    pagan el cambio de contexto. Y acá el intervalo de cambio está bajísimo a
    propósito (`_FINE_SWITCH`, para que la ventana no se clave), lo que
    empeora el problema justo cuando hay varios a la vez: medido, cinco
    hilos tardaban doce segundos en hacer lo que uno hace en ocho.

    El orden también es parte del trato: quien llama pone primero lo que la
    escena necesita antes, así lo urgente está listo mientras lo que recién
    hace falta en el minuto siguiente se sigue calculando.
    """
    pending = [name for name in names if name in _RECIPES]
    if not pending:
        if on_ready is not None:
            on_ready()
        return
    _adopt_cache()
    with _lock:
        pending = [name for name in pending if name not in _files]
    if not pending:
        if on_ready is not None:
            on_ready()
        return

    def work() -> None:
        _breathe_in()
        try:
            for name in pending:
                with _lock:
                    if name in _files:
                        continue
                try:
                    path = _write(name, _RECIPES[name][0]())
                except Exception:                           # noqa: BLE001
                    continue
                with _lock:
                    _files[name] = path
        finally:
            _breathe_out()
        if on_ready is not None:
            on_ready()

    threading.Thread(target=work, daemon=True).start()


# ---------------------------------------------------------------------------
# Reproducción
# ---------------------------------------------------------------------------

_mci = None
#: Cuántos alias se abren por sonido corto. Con uno solo, dos blips seguidos
#: se cortan entre sí; con tres se turnan y el diálogo suena parejo.
_VOICES = 3
_aliases: Dict[str, List[str]] = {}
_turn: Dict[str, int] = {}
_playing: List[str] = []


def _load_mci():
    """La interfaz multimedia de Windows, o ``None`` donde no exista."""
    global _mci
    if _mci is not None:
        return _mci
    if platform.system() != "Windows":
        _mci = False
        return _mci
    try:
        import ctypes

        library = ctypes.WinDLL("winmm")
        library.mciSendStringW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p,
                                           ctypes.c_uint, ctypes.c_void_p]
        _mci = library
    except Exception:                                       # noqa: BLE001
        _mci = False
    return _mci


def _send(command: str) -> bool:
    library = _load_mci()
    if not library:
        return False
    try:
        import ctypes

        answer = ctypes.create_unicode_buffer(128)
        return library.mciSendStringW(command, answer, 127, None) == 0
    except Exception:                                       # noqa: BLE001
        return False


def _open_all() -> None:
    """Abrir un alias por voz y por sonido, para que puedan sonar juntos."""
    if not _load_mci():
        return
    with _lock:
        items = list(_files.items())
    for name, path in items:
        if name in _aliases:
            continue
        opened = []
        for index in range(_VOICES if not _RECIPES[name][1] else 1):
            alias = f"cw_{name}_{index}"
            if _send(f'open "{path}" type waveaudio alias {alias}'):
                opened.append(alias)
        # Se anota incluso cuando no se pudo abrir ninguno: `_play` pregunta
        # justamente por eso para decidir si vale la pena volver a intentar,
        # y sin la anotación un archivo que MCI rechaza hacía reabrir la
        # lista entera en cada blip --- una llamada bloqueante por letra.
        _aliases[name] = opened
        _turn[name] = 0


def play(name: str, loop: bool = False) -> None:
    """Tocar un sonido. Nunca bloquea y nunca levanta nada."""
    try:
        _play(name, loop)
    except Exception:                                       # noqa: BLE001
        pass


def _play(name: str, loop: bool) -> None:
    # Se pregunta por este sonido y no por el conjunto: los huevos de pascua
    # se sintetizan después de que los alias ya están abiertos, y con la
    # condición vieja --- «si no hay ninguno» --- el archivo nuevo no llegaba
    # nunca a tener el suyo. `_open_all` saltea los que ya están.
    with _lock:
        known = name in _files
    if known and name not in _aliases:
        _open_all()
    aliases = _aliases.get(name)
    if aliases:
        index = _turn.get(name, 0) % len(aliases)
        _turn[name] = index + 1
        alias = aliases[index]
        _send(f"stop {alias}")
        _send(f"seek {alias} to start")
        _send(f"play {alias}")
        if loop and alias not in _playing:
            _playing.append(alias)
        return

    # Sin MCI queda un solo sonido por vez. Los blips se descartan --- con un
    # canal único cortarían la cama de ambiente en cada letra --- y lo que
    # sí suena es lo importante: las apariciones y los cierres.
    if name.startswith("blip_"):
        return
    with _lock:
        path = _files.get(name)
    if not path:
        return
    _fallback(path, loop)


def _fallback(path: str, loop: bool) -> None:
    if platform.system() == "Windows":
        try:
            import winsound

            flags = winsound.SND_FILENAME | winsound.SND_ASYNC
            if loop:
                flags |= winsound.SND_LOOP
            winsound.PlaySound(path, flags)
            return
        except Exception:                                   # noqa: BLE001
            pass

    def work() -> None:
        for command in (["afplay", path], ["aplay", "-q", path],
                        ["paplay", path]):
            try:
                subprocess.run(command, check=False)
                return
            except FileNotFoundError:
                continue

    threading.Thread(target=work, daemon=True).start()


def stop(name: str) -> None:
    """Callar un sonido en bucle."""
    try:
        for alias in _aliases.get(name, []):
            _send(f"stop {alias}")
            if alias in _playing:
                _playing.remove(alias)
    except Exception:                                       # noqa: BLE001
        pass


def pump() -> None:
    """
    Sostener los bucles. Hay que llamarla **en cada cuadro** desde el hilo de
    la interfaz --- la cinemática lo hace en su bucle de animación.

    MCI acepta ``play alias repeat`` pero lo ignora para audio: el archivo
    suena una vez y se calla. La primera versión de esto reponía el ``play``
    desde un ``threading.Timer``, y no sonaba: MCI le cuelga cada dispositivo
    al hilo que lo abrió, y aunque el comando no da error, mandado desde otro
    hilo no hace nada. Preguntar y reponer desde el mismo hilo que abrió los
    alias es lo único que funciona, y cuesta una consulta por cama de sonido.

    **El silencio del empalme es esta llamada llegando tarde.** El archivo ya
    está preparado para repetirse sin costura --- `_seamless` cruza la cola
    dentro de la cabeza ---, así que lo único que se escucha en el empalme es
    cuánto tarda alguien en darse cuenta de que terminó. Preguntando cada
    doce cuadros eso eran cuatro décimas de nada; preguntando en cada uno,
    treinta milésimas. Y se repone con un solo comando: `play from 0` en vez
    de `seek` y después `play`, que son dos idas al sistema y dos esperas.
    """
    try:
        for alias in list(_playing):
            if not _query(f"status {alias} mode").startswith("playing"):
                _send(f"play {alias} from 0")
    except Exception:                                       # noqa: BLE001
        pass


def playing(name: str) -> bool:
    """
    ¿Está sonando? Sólo para verificar; el programa no lo consulta.

    Existe porque un `play` que no suena no se queja: MCI devuelve un código
    de error que nadie mira, y sin poder preguntarle al sistema si algo está
    sonando no hay forma de distinguir «no hay sonido» de «no hay parlantes».
    """
    for alias in _aliases.get(name, []):
        answer = _query(f"status {alias} mode")
        if answer.startswith("playing"):
            return True
    return False


def _query(command: str) -> str:
    library = _load_mci()
    if not library:
        return ""
    try:
        import ctypes

        answer = ctypes.create_unicode_buffer(128)
        if library.mciSendStringW(command, answer, 127, None) != 0:
            return ""
        return answer.value
    except Exception:                                       # noqa: BLE001
        return ""


def stop_beds() -> None:
    """
    Callar sólo lo que está en bucle, y dejar terminar lo que suena una vez.

    Es lo que corresponde al cerrar una escena. `stop_all` cortaba también
    los sonidos sueltos, y eso se escuchaba: la figura de luz se va con un
    coro de cinco segundos y la animación de la partida dura tres, así que el
    coro se cortaba a la mitad de una nota. Un sonido de una sola vez ya sabe
    cuándo termina --- termina cuando se acaba --- y dejarlo terminar
    encima del programa que vuelve suena, además, mejor que cortarlo: la cola
    tapa la costura entre la escena y la ventana.

    Lo que sí hay que callar es el bucle, porque ése no se acaba nunca.
    """
    for name, (_maker, loops) in _RECIPES.items():
        if loops:
            stop(name)


def stop_all() -> None:
    """Callar todo, sueltos incluidos. Es el silencio como gesto."""
    try:
        for alias in list(_playing):
            _send(f"stop {alias}")
        _playing.clear()
        if not _load_mci() and platform.system() == "Windows":
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:                                       # noqa: BLE001
        pass
