# -*- coding: utf-8 -*-
"""
La escuelita: lo que se enseña, en qué orden, y quién corrige.

Los tres modos escriben música y el analizador la lee. La escuelita usa a
los dos al revés de como los usa todo el mundo: **el alumno escribe y el
analizador corrige**. No hay acá un segundo juez de contrapunto ni una
tabla de respuestas: cada ejercicio de escritura se le pasa entero a
:func:`engine.analysis.analyse`, y lo que el analizador dice de esa
partitura ---qué acorde es cada compás, qué movimiento hacen dos voces,
dónde hay quintas paralelas, con qué cadencia termina--- es la corrección.
Un juez propio se desincroniza con el analizador en el primer cambio, y
entonces la escuelita aprobaría lo que el analizador marca en rojo.

Por la misma razón las reglas de los estilos no se escriben acá: salen de
:data:`engine.fitness.GENRE_PROFILES` ---qué prohíbe y qué castiga cada
perfil--- y se detectan con las mismas funciones que usa el evaluador. Y la
serie armónica sale de :mod:`engine.harmonics`, que es lo que suena en el
experimentador.

Qué hay acá
-----------
* :data:`UNITS` --- las cinco unidades, con sus lecciones y ejercicios. Cada
  lección cita la entrada del libro que la sostiene: la teoría es la del
  libro, con sus palabras y sus ejemplos, y la escuelita la pone a prueba.
* :func:`grade` --- la corrección. Devuelve un :class:`Verdict` con qué está
  mal y **dónde**: compás y voces, con el vocabulario del analizador.
* :class:`Progress` --- qué ejercicios están aprobados, en ``school.json``.
* :data:`GRADUATION` --- la escena del final, y el logro que deja.

Este módulo no dibuja nada y no importa nada de la interfaz, igual que el
resto de ``engine/``. Las cadenas castellanas de las tablas se traducen
donde se dibujan; las de la corrección, al corregir, como hace el
analizador con sus hallazgos.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from . import analysis, harmonics, history, i18n
from .theory import VOICE_CATALOG
from .fitness import (GENRE_PROFILES, _crossing_count, has_harmonic_tritone,
                      has_melodic_tritone, parallel_interval_violation)
from .story import NARRATOR, Line
from .style import ChordContext, minor_ninth_penalty
from .visitors import BACH, CREATOR, GREGORY
from engine.i18n import N, tr, trf

_FILENAME = "school.json"

#: El logro que deja la graduación. Tres estrellas: es lo último que la
#: escuelita tiene para dar y se gana aprobando treinta y tantos ejercicios.
AWARD = "legend_born"

#: Con qué variable de entorno se fuerza la escena del final al abrir el
#: programa. Es la hermana de ``CHORDWEAVER_VISIT``: llegar a la graduación
#: de verdad lleva todos los ejercicios, y mirar la escena dos veces sin
#: esto es imposible.
FORCE_VAR = "CHORDWEAVER_GRADUATION"

#: Cuánto dura cada nota de un ejercicio, en negras. Siempre una redonda: un
#: acorde por compás. Es lo que hace que «el compás 3» quiera decir «el
#: tercer acorde» en todas las correcciones, y lo que deja al alumno elegir
#: sólo la altura ---que es lo que se está enseñando--- sin tener que pensar
#: además en figuras.
FIGURE = 4.0

#: El nombre de cada carril del sistema, de grave a agudo. Salen del
#: catálogo de voces del motor (`theory.VOICE_CATALOG`), que es donde el
#: programa entero los nombra y donde está su traducción, y son los mismos
#: de ``staff.GRAND_VOICES`` dados vuelta ---lo vigila un test---: el
#: sistema de dos pentagramas no se puede importar desde ``engine/``. Las
#: correcciones nombran las voces así, que es como las nombra el analizador.
VOICE_NAMES = tuple(VOICE_CATALOG[key].label for key in ("B", "T", "A", "S"))

BASS, TENOR, ALTO, SOPRANO = 0, 1, 2, 3

# -- las clases de ejercicio --------------------------------------------------
#: Escribir lo que falta de un fragmento.
WRITE = "write"
#: Corregir un fragmento que está mal, sin tocar el bajo ni los acordes.
FIX = "fix"
#: Mirar un fragmento y elegir la respuesta.
CHOOSE = "choose"
#: Lo mismo, pero sin ver la partitura hasta haber contestado.
HEAR = "hear"
#: La serie armónica: mirar el gráfico, escuchar y elegir.
TONE = "tone"

#: Las clases que se escriben en el pentagrama.
WRITTEN = (WRITE, FIX)


# ---------------------------------------------------------------------------
# Las tablas
# ---------------------------------------------------------------------------

Chord = Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]


@dataclass(frozen=True)
class Option:
    """Una respuesta posible. ``value`` es lo que se compara; ``label``, lo
    que se lee."""

    value: str
    label: str


@dataclass(frozen=True)
class Exercise:
    """
    Un ejercicio.

    ``chords`` es el fragmento, un acorde por compás y cuatro voces por
    acorde de grave a agudo ---bajo, tenor, alto, soprano---. ``None`` en un
    ejercicio de escritura es lo que el alumno tiene que escribir; en los
    demás, una voz que no está. ``lanes`` dice qué voces forman parte del
    fragmento: un ejercicio a dos voces no le muestra al alumno dos voces
    vacías esperando algo.

    ``solution`` y ``mistake`` son una respuesta buena y una mala, enteras.
    No se le muestran a nadie: están para que la suite pruebe que la
    corrección aprueba lo que tiene que aprobar y rechaza lo que tiene que
    rechazar, ejercicio por ejercicio.
    """

    key: str
    kind: str
    prompt: str
    rule: str
    chords: Tuple[Chord, ...] = ()
    lanes: Tuple[int, ...] = (BASS, TENOR, ALTO, SOPRANO)
    fifths: int = 0
    #: La tonalidad en la que se lee, que es la que dice la consigna. Se le
    #: impone al analizador ---ver :func:`read`--- porque un fragmento de
    #: cuatro acordes que termina en una cadencia rota se lee, solo, en la
    #: tonalidad del acorde donde para.
    tonic: int = 0
    mode: str = "major"
    params: Tuple[Tuple[str, Any], ...] = ()
    options: Tuple[Option, ...] = ()
    solution: Tuple[Chord, ...] = ()
    mistake: Tuple[Chord, ...] = ()

    def param(self, name: str, default: Any = None) -> Any:
        for key, value in self.params:
            if key == name:
                return value
        return default

    @property
    def bars(self) -> int:
        return len(self.chords)


@dataclass(frozen=True)
class Lesson:
    """Una lección: qué se explica, qué entrada del libro la sostiene, y
    con qué se practica."""

    key: str
    title: str
    #: La explicación, en dos o tres párrafos cortos. Va con las palabras
    #: del libro: lo que acá se resume allá está dicho entero.
    text: Tuple[str, ...]
    #: La entrada del libro que la sostiene, por su clave.
    cite: str
    #: Qué párrafo de esa entrada se transcribe como cita. Es el que dice la
    #: regla que los ejercicios ponen a prueba.
    quote: int
    exercises: Tuple[Exercise, ...]
    #: Si la lección ofrece abrir el experimentador de armónicos.
    lab: bool = False


@dataclass(frozen=True)
class Unit:
    key: str
    numeral: str
    title: str
    #: El nombre corto, para el recorrido de arriba de la pantalla.
    short: str
    lessons: Tuple[Lesson, ...]


# ---------------------------------------------------------------------------
# Unidad 1 · Movimientos de contrapunto
# ---------------------------------------------------------------------------
#
# Todo en Do mayor y con redondas. Las alturas son MIDI: 48 es do3, 60 el
# do central, 72 do5.

_MOTION_OPTIONS = (
    Option(analysis.MOTION_CONTRARY, N("Contrario")),
    Option(analysis.MOTION_OBLIQUE, N("Oblicuo")),
    Option(analysis.MOTION_SIMILAR, N("Directo")),
    Option(analysis.MOTION_PARALLEL, N("Paralelo")),
)

_PAIR_OPTIONS = (
    Option("Bajo|Tenor", "Bajo y Tenor"),
    Option("Bajo|Alto", "Bajo y Alto"),
    Option("Tenor|Alto", "Tenor y Alto"),
    Option("Alto|Soprano", "Alto y Soprano"),
)

_UNIT_COUNTERPOINT = Unit(
    "contrapunto", "1", "Movimientos de contrapunto", N("Movimientos"),
    (
        Lesson(
            "movimientos", "Los cuatro movimientos",
            ("Entre un acorde y el siguiente, dos voces cualesquiera sólo "
             "pueden hacer cuatro cosas: ir en direcciones contrarias, que "
             "una se quede quieta y la otra se mueva, ir para el mismo lado "
             "cambiando de distancia, o ir para el mismo lado conservándola.",
             "Contrario, oblicuo, directo y paralelo. El analizador mide cada "
             "paso contra la nota anterior de cada voz y lo nombra con esas "
             "cuatro palabras: son las mismas con las que te va a corregir."),
            "movimientos", 5,
            (
                Exercise(
                    "mov_reconocer", CHOOSE,
                    "Mirá el bajo y la soprano entre el compás 2 y el 3. "
                    "¿Qué movimiento hacen?",
                    "motion_at",
                    chords=((48, None, None, 72), (50, None, None, 71),
                            (52, None, None, 76), (53, None, None, 76)),
                    lanes=(BASS, SOPRANO),
                    params=(("pair", (BASS, SOPRANO)), ("step", 2)),
                    options=_MOTION_OPTIONS),
                Exercise(
                    "mov_contrario", WRITE,
                    "El bajo sube por grados: do, re, mi, fa. Escribí la "
                    "soprano, una redonda por compás, de manera que cada "
                    "paso sea movimiento contrario.",
                    "motions",
                    chords=((48, None, None, None), (50, None, None, None),
                            (52, None, None, None), (53, None, None, None)),
                    lanes=(BASS, SOPRANO),
                    params=(("pair", (BASS, SOPRANO)),
                            ("kinds", (analysis.MOTION_CONTRARY,) * 3)),
                    solution=((48, None, None, 76), (50, None, None, 74),
                              (52, None, None, 72), (53, None, None, 71)),
                    mistake=((48, None, None, 72), (50, None, None, 74),
                             (52, None, None, 72), (53, None, None, 77))),
                Exercise(
                    "mov_tres", WRITE,
                    "Ahora un movimiento distinto en cada paso: escribí la "
                    "soprano para que con el bajo haga contrario, después "
                    "oblicuo y al final directo. Ojo: directo no es "
                    "paralelo.",
                    "motions",
                    chords=((48, None, None, None), (53, None, None, None),
                            (52, None, None, None), (57, None, None, None)),
                    lanes=(BASS, SOPRANO),
                    params=(("pair", (BASS, SOPRANO)),
                            ("kinds", (analysis.MOTION_CONTRARY,
                                       analysis.MOTION_OBLIQUE,
                                       analysis.MOTION_SIMILAR))),
                    solution=((48, None, None, 72), (53, None, None, 69),
                              (52, None, None, 69), (57, None, None, 71)),
                    mistake=((48, None, None, 72), (53, None, None, 69),
                             (52, None, None, 69), (57, None, None, 74))),
            )),
        Lesson(
            "paralelas", "Quintas y octavas paralelas",
            ("Si dos voces están a una quinta y se mueven para el mismo lado "
             "la misma distancia, siguen a una quinta: eso es una quinta "
             "paralela. Con la octava pasa lo mismo.",
             "El oído deja de escuchar dos voces y escucha una sola con un "
             "timbre raro. Por eso el barroco las prohíbe de plano, y por eso "
             "el analizador las marca en rojo. La salida es la del libro: "
             "mover una de las dos al revés, o dejarla quieta si el acorde "
             "siguiente comparte esa nota."),
            "paralelas", 1,
            (
                Exercise(
                    "par_donde", CHOOSE,
                    "En este fragmento hay quintas paralelas, una sola vez. "
                    "¿Entre qué dos voces?",
                    "parallel_pair",
                    chords=((48, 55, 64, 72), (53, 57, 60, 69),
                            (55, 59, 62, 67), (48, 55, 64, 72)),
                    options=_PAIR_OPTIONS),
                Exercise(
                    "par_corregir", FIX,
                    "Del compás 1 al 2 hay quintas y octavas paralelas. "
                    "Corregilas moviendo el tenor, el alto o la soprano: el "
                    "bajo no se toca y cada compás tiene que seguir siendo "
                    "el mismo acorde.",
                    "clean",
                    chords=((48, 55, 64, 72), (50, 57, 65, 74),
                            (43, 55, 62, 71), (48, 55, 64, 72)),
                    solution=((48, 55, 64, 72), (50, 53, 62, 69),
                              (43, 55, 62, 71), (48, 55, 64, 72)),
                    mistake=((48, 55, 64, 72), (50, 57, 62, 69),
                             (43, 55, 62, 71), (48, 55, 64, 72))),
                Exercise(
                    "par_directa", CHOOSE,
                    "El bajo y la soprano llegan a una quinta moviéndose para "
                    "el mismo lado, y la soprano llega saltando. ¿Qué es?",
                    "direct_kind",
                    chords=((48, 52, 60, 64), (55, 59, 62, 74),
                            (48, 55, 64, 72)),
                    options=(
                        Option("paralela", "Quintas paralelas: se prohíben"),
                        Option("oculta", "Una quinta directa: se penaliza, "
                                         "no se prohíbe"),
                        Option("ninguna", "Nada: llegaron por movimiento "
                                          "contrario"),
                    )),
            )),
        Lesson(
            "cruces", "Saltos, cruces y espaciado",
            ("Dos voces se cruzan cuando la de abajo pasa a estar por encima "
             "de la de arriba. Se escucha confuso, y por eso los tres estilos "
             "lo prohíben de entrada.",
             "Lo mismo con los saltos: una voz que salta mucho es difícil de "
             "cantar y de seguir. Lo normal es que las voces de arriba vayan "
             "juntas y el bajo más separado, como la mano derecha y la "
             "izquierda de un pianista."),
            "saltos", 1,
            (
                Exercise(
                    "cruce_corregir", FIX,
                    "En el compás 2 el alto canta por encima de la soprano. "
                    "Corregilo sin tocar el bajo y sin cambiar los acordes, "
                    "y sin que aparezcan paralelas nuevas.",
                    "clean",
                    chords=((48, 55, 64, 72), (53, 57, 72, 69),
                            (55, 59, 62, 67), (48, 55, 64, 72)),
                    solution=((48, 55, 64, 72), (53, 57, 65, 72),
                              (55, 59, 62, 67), (48, 55, 64, 72)),
                    mistake=((48, 55, 64, 72), (53, 57, 72, 69),
                             (55, 59, 62, 67), (48, 55, 64, 72))),
            )),
    ),
)


# ---------------------------------------------------------------------------
# Unidad 2 · Armonías
# ---------------------------------------------------------------------------

_FUNCTION_OPTIONS = (
    Option("tonic", "Tónica"),
    Option("subdominant", N("Subdominante")),
    Option("dominant", N("Dominante")),
)

_UNIT_HARMONY = Unit(
    "armonias", "2", "Armonías", "Armonías",
    (
        Lesson(
            "acorde", "El acorde y su tercera",
            ("Una tríada es una fundamental, la nota que está una tercera "
             "más arriba y la que está una quinta más arriba: do-mi-sol es "
             "do mayor, C.",
             "Si la tercera está un semitono más abajo el acorde es menor y "
             "suena más oscuro. Toda la diferencia entre mayor y menor está "
             "en esa única nota, y por eso es la que nunca se omite."),
            "acorde", 1,
            (
                Exercise(
                    "ac_menor", WRITE,
                    "Escribí La menor (Am) a cuatro voces, en La menor, con "
                    "la fundamental en el bajo.",
                    "chord",
                    chords=((None, None, None, None),),
                    tonic=9, mode="minor",
                    params=(("root", 9), ("quality", "m"), ("inversion", 0)),
                    solution=((45, 57, 64, 72),),
                    mistake=((48, 57, 64, 69),)),
                Exercise(
                    "ac_oido", HEAR,
                    "Escuchá el acorde sin mirarlo. ¿Es mayor o menor?",
                    "quality",
                    chords=((50, 57, 65, 74),),
                    tonic=2, mode="minor",
                    options=(Option("major", N("Mayor")),
                             Option("minor", N("Menor")))),
            )),
        Lesson(
            "grados", "La escala y los grados",
            ("Sobre cada nota de la escala se arma un acorde con notas de la "
             "escala, y se numeran con números romanos: I, ii, iii, IV, V, "
             "vi, vii°. Mayúscula es mayor y minúscula es menor.",
             "El número romano no dice cómo se llama el acorde sino qué papel "
             "cumple, y es el mismo en cualquier tonalidad."),
            "escala", 1,
            (
                Exercise(
                    "grado", CHOOSE,
                    "Esto está en Sol mayor. ¿Qué grado es el acorde del "
                    "compás 2?",
                    "degree_at",
                    chords=((43, 59, 62, 67), (52, 59, 64, 67),
                            (50, 57, 62, 66), (43, 55, 62, 67)),
                    fifths=1, tonic=7,
                    params=(("bar", 2),),
                    options=(Option("ii", "ii"), Option("iii", "iii"),
                             Option("IV", "IV"), Option("vi", "vi"))),
            )),
        Lesson(
            "inversiones", "Qué nota va en el bajo",
            ("Un acorde puede cantarse con cualquiera de sus notas abajo. Con "
             "la fundamental en el bajo está en estado fundamental; con la "
             "tercera, en primera inversión; con la quinta, en segunda.",
             "El bajo cifrado las anota con números: nada para el estado "
             "fundamental, 6 para la primera inversión y 6/4 para la "
             "segunda. Son los números que el analizador escribe debajo del "
             "pentagrama."),
            "inversiones", 1,
            (
                Exercise(
                    "inv_primera", WRITE,
                    "En Do mayor: escribí Sol mayor (G) en primera inversión, "
                    "con la tercera (si) en el bajo.",
                    "chord",
                    chords=((None, None, None, None),),
                    params=(("root", 7), ("quality", ""), ("inversion", 1)),
                    solution=((47, 55, 62, 67),),
                    mistake=((43, 55, 62, 71),)),
                Exercise(
                    "inv_reconocer", CHOOSE,
                    "Este acorde es Fa mayor. ¿Cómo está cantado?",
                    "inversion_at",
                    chords=((48, 57, 65, 72),),
                    params=(("bar", 1),),
                    options=(Option("0", N("Estado fundamental")),
                             Option("1", "Primera inversión (6)"),
                             Option("2", "Segunda inversión (6/4)"))),
            )),
        Lesson(
            "funciones", "Las tres funciones",
            ("Tónica es la casa: I, y de refilón vi y iii. Subdominante es "
             "salir de casa: IV y ii. Dominante es la tensión máxima: V y "
             "vii°, con la sensible tirando hacia la tónica.",
             "El recorrido típico es casa, salgo, tensión, vuelvo. Lo que "
             "importa de un acorde no es su nombre: es en cuál de las tres "
             "casillas cae."),
            "funciones", 1,
            (
                Exercise(
                    "funcion", CHOOSE,
                    "En Do mayor. ¿Qué función cumple el acorde del "
                    "compás 2?",
                    "function_at",
                    chords=((48, 55, 64, 72), (45, 57, 64, 72),
                            (41, 57, 65, 72), (43, 55, 62, 71)),
                    params=(("bar", 2),),
                    options=_FUNCTION_OPTIONS),
            )),
        Lesson(
            "septimas", "Las séptimas",
            ("A una tríada se le puede apilar una nota más, la séptima. G se "
             "convierte en G7 y deja de ser un lugar donde quedarse: la "
             "séptima es un intervalo tenso y pide resolver.",
             "Resuelve bajando un grado. Y el V7 trae además la sensible, que "
             "sube a la tónica: en G7 a C, el fa baja a mi y el si sube a "
             "do."),
            "septima", 2,
            (
                Exercise(
                    "sept_escribir", WRITE,
                    "Escribí G7 a cuatro voces, una nota por voz (sol, si, "
                    "re y fa), con el sol en el bajo.",
                    "chord",
                    chords=((None, None, None, None),),
                    params=(("root", 7), ("quality", "7"), ("inversion", 0),
                            ("complete", True)),
                    solution=((43, 59, 62, 65),),
                    mistake=((43, 59, 62, 67),)),
                Exercise(
                    "sept_resolver", WRITE,
                    "El compás 1 es G7, con la séptima (fa) en el tenor "
                    "y la sensible (si) en el alto. Escribí el C del "
                    "compás 2 de manera que la séptima baje un grado y la "
                    "sensible suba a la tónica.",
                    "resolution",
                    chords=((43, 53, 59, 67), (None, None, None, None)),
                    params=(("bar", 1),),
                    solution=((43, 53, 59, 67), (48, 52, 60, 67)),
                    mistake=((43, 53, 59, 67), (48, 55, 60, 64))),
            )),
    ),
)


# ---------------------------------------------------------------------------
# Unidad 3 · Cadencias
# ---------------------------------------------------------------------------

_CADENCE_OPTIONS = (
    Option("autentica", "Auténtica"),
    Option("plagal", "Plagal"),
    Option("rota", N("Rota")),
    Option("semi", N("Semicadencia")),
)

_UNIT_CADENCES = Unit(
    "cadencias", "3", N("Cadencias"), N("Cadencias"),
    (
        Lesson(
            "autentica", "La cadencia auténtica: V - I",
            ("La más común de todas y la que define la tonalidad: el quinto "
             "grado, con la sensible adentro, resuelve en la tónica.",
             "Si los dos acordes tienen la fundamental en el bajo, el "
             "analizador la llama perfecta; si alguno está invertido, "
             "imperfecta."),
            "autentica", 0,
            (
                Exercise(
                    "cad_autentica", WRITE,
                    "En Sol mayor. Están escritos el I y el IV: completá los "
                    "compases 3 y 4 para cerrar con una cadencia auténtica "
                    "perfecta, sin paralelas.",
                    "cadence",
                    chords=((43, 59, 62, 67), (48, 60, 64, 67),
                            (None, None, None, None),
                            (None, None, None, None)),
                    fifths=1, tonic=7,
                    params=(("kinds", ("cadencia auténtica perfecta",)),),
                    # El I final con su tercera (si) en el tenor, que
                    # sube desde el la. Con sol en el tenor la respuesta
                    # modelo cerraba en un Sol sin tercera, y la suite lo
                    # aprobaba porque la corrección miraba sólo el nombre.
                    solution=((43, 59, 62, 67), (48, 60, 64, 67),
                              (50, 57, 62, 66), (43, 59, 62, 67)),
                    mistake=((43, 59, 62, 67), (48, 60, 64, 67),
                             (45, 57, 64, 72), (50, 57, 66, 69))),
            )),
        Lesson(
            "plagal", N("Cadencia plagal: IV - I"),
            ("La subdominante cierra directamente sobre la tónica, sin pasar "
             "por la dominante. Es el «amén» de los himnos.",
             "Suena más blanda y más antigua que la auténtica, justamente "
             "porque le falta la sensible tirando."),
            "plagal", 0,
            (
                Exercise(
                    "cad_plagal", WRITE,
                    "En Fa mayor. Completá los compases 3 y 4 con una "
                    "cadencia plagal: el IV y después el I.",
                    "cadence",
                    chords=((41, 57, 60, 65), (50, 57, 62, 65),
                            (None, None, None, None),
                            (None, None, None, None)),
                    fifths=-1, tonic=5,
                    params=(("kinds", ("cadencia plagal",)),),
                    solution=((41, 57, 60, 65), (50, 57, 62, 65),
                              (46, 58, 62, 65), (41, 57, 60, 65)),
                    mistake=((41, 57, 60, 65), (50, 57, 62, 65),
                             (48, 55, 64, 67), (41, 57, 60, 65))),
            )),
        Lesson(
            "rota", N("Cadencia rota"),
            ("El V prepara la tónica y en el último momento cae en el sexto "
             "grado: en Do mayor, G va a Am en vez de a C.",
             "La resolución se posterga y la frase, que parecía terminada, "
             "sigue. Es un recurso de continuidad."),
            "deceptive", 0,
            (
                Exercise(
                    "cad_rota", WRITE,
                    "En Do mayor. El compás 3 es la dominante: escribí el "
                    "compás 4 para que la cadencia sea rota.",
                    "cadence",
                    chords=((48, 55, 64, 72), (41, 57, 65, 72),
                            (43, 55, 62, 71), (None, None, None, None)),
                    params=(("kinds", ("cadencia rota",)),),
                    solution=((48, 55, 64, 72), (41, 57, 65, 72),
                              (43, 55, 62, 71), (45, 52, 60, 72)),
                    mistake=((48, 55, 64, 72), (41, 57, 65, 72),
                             (43, 55, 62, 71), (48, 52, 60, 72))),
            )),
        Lesson(
            "semicadencia", "Terminar en la dominante",
            ("No toda frase cierra. Terminar en el V deja la música colgada: "
             "es la semicadencia.",
             "Sirve para partir una idea larga en dos mitades, la primera de "
             "las cuales queda abierta: pregunta y respuesta."),
            "dominante_final", 0,
            (
                Exercise(
                    "cad_semi", WRITE,
                    "En Re mayor. Completá los compases 3 y 4 de manera que "
                    "la frase quede colgada sobre el V.",
                    "cadence",
                    chords=((50, 57, 66, 74), (47, 59, 62, 74),
                            (None, None, None, None),
                            (None, None, None, None)),
                    fifths=2, tonic=2,
                    params=(("kinds", ("semicadencia",)),),
                    solution=((50, 57, 66, 74), (47, 59, 62, 74),
                              (43, 59, 67, 74), (45, 57, 64, 73)),
                    mistake=((50, 57, 66, 74), (47, 59, 62, 74),
                             (43, 59, 67, 74), (50, 57, 66, 74))),
            )),
        Lesson(
            "reconocer", "Reconocer una cadencia",
            ("Una cadencia es la manera de terminar una frase: el gesto que "
             "dice «hasta acá». Se reconoce por los dos últimos acordes y por "
             "lo que hacen con la tónica.",
             "La auténtica llega desde el V; la plagal, desde el IV; la rota "
             "promete la tónica y entrega el sexto grado; la semicadencia ni "
             "siquiera llega."),
            "autentica", 2,
            (
                Exercise(
                    "cad_ver", CHOOSE,
                    "En La menor. ¿Con qué cadencia termina?",
                    "cadence_kind",
                    chords=((45, 57, 64, 72), (50, 57, 65, 74),
                            (52, 56, 64, 71), (53, 57, 60, 69)),
                    tonic=9, mode="minor",
                    options=_CADENCE_OPTIONS),
                Exercise(
                    "cad_oir", HEAR,
                    "En Do mayor, sin partitura: escuchá cómo termina. ¿Qué "
                    "cadencia es?",
                    "cadence_kind",
                    chords=((48, 55, 64, 72), (45, 57, 64, 72),
                            (41, 57, 65, 72), (43, 55, 62, 71)),
                    options=_CADENCE_OPTIONS),
            )),
    ),
)


# ---------------------------------------------------------------------------
# Unidad 4 · Particularidades por género
# ---------------------------------------------------------------------------
#
# Las reglas que se preguntan acá no se inventan: cada una mira un campo de
# un perfil del motor ---ver `STYLE_RULES`--- y se detecta con las funciones
# del evaluador.

_RULE_OPTIONS_BAROQUE = (
    Option("paralelas", N("Quintas paralelas")),
    Option("salto_tritono", "Salto de tritono en una voz"),
    Option("cruce", "Cruce de voces"),
    Option("tritono", "Tritono entre dos voces"),
)

_RULE_OPTIONS_GREGORIAN = (
    Option("paralelas", N("Quintas paralelas")),
    Option("tritono", "Tritono entre dos voces"),
    Option("salto_grande", "Salto de más de una cuarta"),
    Option("cruce", "Cruce de voces"),
)

_RULE_OPTIONS_JAZZ = (
    Option("paralelas", N("Quintas paralelas")),
    Option("tritono", "Tritono entre dos voces"),
    Option("novena_menor", "Novena menor sobre una nota que no es la "
                           "fundamental"),
    Option("cruce", "Cruce de voces"),
)

_GENRE_OPTIONS = (
    Option("classical", N("Barroco")),
    Option("gregorian", N("Gregoriano")),
    Option("jazz", "Jazz"),
)

_UNIT_STYLES = Unit(
    "estilos", "4", "Particularidades por género", N("Estilos"),
    (
        Lesson(
            "barroco", N("Barroco"),
            ("El contrapunto de la práctica común, el más reglado de los "
             "tres. Prohíbe quintas y octavas paralelas, premia el movimiento "
             "contrario, castiga los saltos de tritono y de séptima, y vigila "
             "que las voces no se crucen.",
             "Prohibir y castigar no son lo mismo: una solución con quintas "
             "paralelas se descarta entera; un salto de tritono sólo cuesta "
             "más."),
            "barroco", 1,
            (
                Exercise(
                    "gen_barroco", CHOOSE,
                    "Este fragmento está escrito para el estilo Barroco. "
                    "¿Qué regla del estilo rompe?",
                    "style_rule",
                    chords=((48, 55, 64, 72), (50, 53, 62, 69),
                            (43, 59, 62, 67), (48, 60, 64, 67)),
                    params=(("genre", "classical"),),
                    options=_RULE_OPTIONS_BAROQUE),
                Exercise(
                    "gen_prohibido", CHOOSE,
                    "Estas son las quintas paralelas de la unidad 1. ¿En qué "
                    "estilo hacen que la solución se descarte entera?",
                    "style_forbids",
                    chords=((48, 55, 64, 72), (50, 57, 65, 74),
                            (43, 55, 62, 71), (48, 55, 64, 72)),
                    params=(("rule", "paralelas"),),
                    options=_GENRE_OPTIONS),
            )),
        Lesson(
            "gregoriano", "Gregoriano y organum",
            ("Escritura modal, anterior a la tonalidad: líneas casi siempre "
             "por grado conjunto y el tritono evitado con insistencia, ni "
             "saltado por una voz ni sonando entre dos.",
             "En cambio tolera las quintas y octavas paralelas, porque el "
             "organum —la forma más antigua de cantar a varias voces— "
             "consiste en doblar la melodía en paralelo: la vox principalis "
             "lleva el canto y la organalis la acompaña debajo."),
            "gregoriano", 1,
            (
                Exercise(
                    "gen_gregoriano", CHOOSE,
                    "Este fragmento está escrito para el estilo Gregoriano. "
                    "¿Qué regla del estilo rompe?",
                    "style_rule",
                    chords=((50, 57, 62, 69), (52, 59, 64, 71),
                            (53, 59, 65, 71), (50, 57, 62, 69)),
                    tonic=2, mode="dorian",
                    params=(("genre", "gregorian"),),
                    options=_RULE_OPTIONS_GREGORIAN),
                Exercise(
                    "gen_organum", WRITE,
                    "La soprano es la vox principalis. Escribí debajo, en el "
                    "alto, la vox organalis: la misma melodía, nota por nota, "
                    "una quinta justa más abajo.",
                    "organum",
                    chords=((None, None, None, 74), (None, None, None, 76),
                            (None, None, None, 74), (None, None, None, 72)),
                    lanes=(ALTO, SOPRANO),
                    tonic=2, mode="dorian",
                    params=(("upper", SOPRANO), ("lower", ALTO),
                            ("interval", 7)),
                    solution=((None, None, 67, 74), (None, None, 69, 76),
                              (None, None, 67, 74), (None, None, 65, 72)),
                    mistake=((None, None, 67, 74), (None, None, 72, 76),
                             (None, None, 67, 74), (None, None, 65, 72))),
            )),
        Lesson(
            "jazz", "Jazz",
            ("Acá lo que manda es cómo se encadenan la tercera y la séptima "
             "de cada acorde: las guide tones. Son las que dicen si un acorde "
             "es mayor, menor o dominante; el resto es relleno.",
             "Se conectan por grado conjunto, se mantienen las notas que dos "
             "acordes comparten y se evitan las novenas menores. Las "
             "paralelas y los tritonos, en cambio, pasan sin problema."),
            "jazz", 1,
            (
                Exercise(
                    "gen_jazz", CHOOSE,
                    "Un ii-V-I escrito para el estilo Jazz, con quintas "
                    "paralelas y un tritono a la vista. ¿Qué regla del estilo "
                    "rompe?",
                    "style_rule",
                    chords=((50, 57, 65, 72), (43, 50, 65, 71),
                            (48, 52, 65, 71)),
                    params=(("genre", "jazz"),),
                    options=_RULE_OPTIONS_JAZZ),
                Exercise(
                    "gen_guias", WRITE,
                    "Dm7 - G7 - Cmaj7 en jazz. El bajo y la soprano están "
                    "escritos: completá el tenor y el alto con las guide "
                    "tones de cada acorde, moviéndose por grado o quedándose "
                    "quietas.",
                    "guide_tones",
                    chords=((50, None, None, 69), (43, None, None, 67),
                            (48, None, None, 67)),
                    params=(("lanes", (TENOR, ALTO)),),
                    solution=((50, 53, 60, 69), (43, 53, 59, 67),
                              (48, 52, 59, 67)),
                    mistake=((50, 57, 62, 69), (43, 55, 62, 67),
                             (48, 55, 64, 67))),
            )),
    ),
)


# ---------------------------------------------------------------------------
# Unidad 5 · Serie armónica
# ---------------------------------------------------------------------------

_UNIT_HARMONICS = Unit(
    "serie", "5", "La serie armónica", "Serie armónica",
    (
        Lesson(
            "serie", "La serie armónica",
            ("Nada vibra de una sola manera. Una cuerda vibra entera y, al "
             "mismo tiempo, en mitades, en tercios, en cuartos: cada división "
             "suena al doble, al triple, al cuádruple de la frecuencia.",
             "Si la cuerda entera da 110 hercios, arriba suenan 220, 330, "
             "440, 550: los múltiplos enteros, sin excepción y sin hueco. Lo "
             "que llamamos «la nota» es el primero de la lista."),
            "fisica_serie", 2,
            (
                Exercise(
                    "arm_hercios", TONE,
                    "Una cuerda da 110 hercios: es un la2. ¿Cuántos hercios "
                    "da su quinto armónico?",
                    "partial_hz",
                    params=(("midi", 45), ("number", 5)),
                    options=(Option("330", "330 Hz"), Option("440", "440 Hz"),
                             Option("550", "550 Hz"),
                             Option("660", "660 Hz"))),
                Exercise(
                    "arm_oido", TONE,
                    "Suenan juntos la fundamental, un la2, y uno solo de "
                    "sus armónicos. Escuchalo. ¿Cuál es?",
                    "partial_heard",
                    params=(("midi", 45), ("number", 3), ("hidden", True)),
                    options=(Option("2", "El 2º: la octava"),
                             Option("3", "El 3º: la quinta, una octava "
                                         "más arriba"),
                             Option("4", "El 4º: dos octavas"),
                             Option("5", "El 5º: la tercera mayor, dos "
                                         "octavas más arriba"))),
            ), lab=True),
        Lesson(
            "intervalos", "De los armónicos a los intervalos",
            ("El segundo armónico es la octava. El tercero es la quinta. El "
             "quinto es la tercera mayor.",
             "No es casualidad que la música haya empezado por octavas y "
             "quintas y haya tardado siglos en aceptar la tercera: es el "
             "orden en que aparecen."),
            "fisica_serie", 4,
            (
                Exercise(
                    "arm_escribir", WRITE,
                    "La fundamental es do3. Escribí en la soprano, con una "
                    "redonda, la nota del piano más cercana a su tercer "
                    "armónico.",
                    "harmonic_note",
                    chords=((None, None, None, None),),
                    lanes=(SOPRANO,),
                    params=(("midi", 48), ("number", 3)),
                    solution=((None, None, None, 67),),
                    mistake=((None, None, None, 64),)),
                Exercise(
                    "arm_tercera", TONE,
                    "Mirá la serie de do3. ¿En qué armónico aparece por "
                    "primera vez la tercera mayor?",
                    "first_interval",
                    params=(("midi", 48), ("semitones", 4)),
                    options=(Option("3", "En el 3º"), Option("4", "En el 4º"),
                             Option("5", "En el 5º"),
                             Option("6", "En el 6º"))),
            ), lab=True),
        Lesson(
            "temperamento", "Por qué el piano está afinado mal",
            ("Los armónicos caen donde la física los pone, y la física no "
             "sabe nada de teclas. El tercero cae dos centésimas de semitono "
             "por encima de la quinta del piano; el quinto, catorce por "
             "debajo de la tercera.",
             "El séptimo es el caso serio: no hay ninguna tecla ahí. El "
             "temperamento igual reparte el error parejo entre las doce "
             "notas, y es un acuerdo, no una verdad."),
            "fisica_temperamento", 2,
            (
                Exercise(
                    "arm_septimo", TONE,
                    "El séptimo armónico de la2 cae cerca del sol del piano. "
                    "¿Cuánto se aparta de la tecla?",
                    "partial_cents",
                    params=(("midi", 45), ("number", 7)),
                    options=(Option("2", "Dos centésimas por encima"),
                             Option("-14", "Catorce centésimas por debajo"),
                             Option("-31", "Treinta y una centésimas por "
                                           "debajo"),
                             Option("0", "Nada: cae justo en la tecla"))),
                Exercise(
                    "arm_lejos", TONE,
                    "De estos cuatro armónicos de la2, ¿cuál cae más lejos "
                    "de cualquier tecla del piano?",
                    "furthest",
                    params=(("midi", 45), ("numbers", (3, 5, 7, 8))),
                    options=(Option("3", N("El 3º")), Option("5", N("El 5º")),
                             Option("7", N("El 7º")), Option("8", N("El 8º")))),
            ), lab=True),
    ),
)


#: Las cinco unidades, en el orden en que se aprueban.
UNITS: Tuple[Unit, ...] = (_UNIT_COUNTERPOINT, _UNIT_HARMONY, _UNIT_CADENCES,
                           _UNIT_STYLES, _UNIT_HARMONICS)


def lessons() -> List[Lesson]:
    """Todas las lecciones, en orden."""
    return [lesson for unit in UNITS for lesson in unit.lessons]


def exercises() -> List[Exercise]:
    """Todos los ejercicios, en orden."""
    return [exercise for lesson in lessons() for exercise in lesson.exercises]


def lesson(key: str) -> Optional[Lesson]:
    return next((item for item in lessons() if item.key == key), None)


def exercise(key: str) -> Optional[Exercise]:
    return next((item for item in exercises() if item.key == key), None)


def unit_of(lesson_key: str) -> Optional[Unit]:
    for unit in UNITS:
        if any(item.key == lesson_key for item in unit.lessons):
            return unit
    return None


def lesson_of(exercise_key: str) -> Optional[Lesson]:
    for item in lessons():
        if any(entry.key == exercise_key for entry in item.exercises):
            return item
    return None


# ---------------------------------------------------------------------------
# Del fragmento al pentagrama, y del pentagrama al analizador
# ---------------------------------------------------------------------------

Line_ = List[Tuple[Optional[int], float]]


def lines_from(chords: Sequence[Chord],
               lanes: Sequence[int] = (BASS, TENOR, ALTO, SOPRANO)
               ) -> List[Line_]:
    """
    Las cuatro voces de un fragmento, como las lee y escribe el sistema.

    Una casilla vacía en el medio es un silencio ---la voz calla ese
    compás--- y las del final no se escriben: es lo que queda para el
    alumno, y el pentagrama tiene que dejarlo agregar ahí sin encontrarse
    silencios puestos.
    """
    out: List[Line_] = []
    for lane in range(len(VOICE_NAMES)):
        if lane not in lanes:
            out.append([])
            continue
        line: Line_ = [(chord[lane], FIGURE) for chord in chords]
        while line and line[-1][0] is None:
            line.pop()
        out.append(line)
    return out


def given_lines(item: Exercise) -> List[Line_]:
    """Lo que el pentagrama muestra al abrir el ejercicio."""
    return lines_from(item.chords, item.lanes)


def cells(lines: Sequence[Line_]) -> Dict[Tuple[int, int], Optional[int]]:
    """
    Qué altura canta cada voz al empezar cada compás.

    Por compás y no por nota porque los ejercicios son de un acorde por
    compás: la pregunta es siempre «qué canta el alto en el compás 3». Lo
    que no arranca justo en la barra ---una nota partida a mano--- cuenta
    por la que suena en ese instante.
    """
    out: Dict[Tuple[int, int], Optional[int]] = {}
    for lane, line in enumerate(lines):
        moment = 0.0
        for pitch, duration in line:
            start_bar = int(moment // FIGURE + 1e-9)
            end = moment + duration
            bar_start = start_bar * FIGURE
            # Cada barra que esta nota ocupa desde su comienzo.
            while bar_start < end - 1e-6:
                if bar_start >= moment - 1e-6:
                    out[(start_bar + 1, lane)] = pitch
                start_bar += 1
                bar_start = start_bar * FIGURE
            moment = end
    return out


def editable_lanes(item: Exercise) -> Tuple[int, ...]:
    """Las voces en las que el alumno escribe."""
    if item.kind == WRITE:
        return tuple(lane for lane in item.lanes
                     if any(chord[lane] is None for chord in item.chords))
    if item.kind == FIX:
        return tuple(lane for lane in item.lanes if lane != BASS)
    return ()


def locked(item: Exercise) -> Dict[Tuple[int, int], Optional[int]]:
    """
    Las casillas que vienen dadas y no se pueden tocar.

    En un ejercicio de escritura, lo escrito; en uno de corrección, el bajo
    entero ---la consigna es corregir sin cambiar los acordes, y el bajo es
    lo que los sostiene---; en uno de mirar, todo.
    """
    out: Dict[Tuple[int, int], Optional[int]] = {}
    for bar, chord in enumerate(item.chords, start=1):
        for lane in item.lanes:
            if item.kind == WRITE and chord[lane] is None:
                continue
            if item.kind == FIX and lane != BASS:
                continue
            out[(bar, lane)] = chord[lane]
    return out


def tampered(item: Exercise, lines: Sequence[Line_]
             ) -> Optional[Tuple[int, int]]:
    """El primer ``(compás, voz)`` dado que alguien cambió, o None."""
    written = cells(lines)
    for (bar, lane), pitch in sorted(locked(item).items()):
        if written.get((bar, lane)) != pitch:
            return bar, lane
    # Lo que se escriba en una voz que no es del ejercicio también es tocar
    # lo dado: esa voz viene vacía y vacía se tiene que quedar.
    for lane, line in enumerate(lines):
        if lane in item.lanes:
            continue
        if any(pitch is not None for pitch, _d in line):
            return 1, lane
    # Y nada después del último compás: no se corrige pero suena al
    # escuchar, así que se puede usar para colar una respuesta.
    for lane, line in enumerate(lines):
        moment = 0.0
        for pitch, duration in line:
            if pitch is not None and moment >= item.bars * FIGURE - 1e-9:
                return item.bars, lane
            moment += duration
    return None


def score_of(item: Exercise, lines: Sequence[Line_]) -> analysis.Score:
    """
    La partitura que se le pasa al analizador: lo mismo que haría el
    analizador con lo que hay en su pentagrama.

    Sólo las voces que tienen algo escrito, con los nombres del sistema.
    """
    parts: List[analysis.Part] = []
    for lane, line in enumerate(lines):
        if not any(pitch is not None for pitch, _d in line):
            continue
        notes, moment = [], 0.0
        for pitch, duration in line:
            if pitch is not None:
                notes.append(analysis.Note(pitch=pitch, onset=moment,
                                           duration=duration))
            moment += duration
        parts.append(analysis.Part(name=VOICE_NAMES[lane], notes=notes))
    return analysis.Score(parts=parts, fifths=item.fifths, beats=4,
                          beat_type=4, title=item.key)


def read(item: Exercise, lines: Sequence[Line_]) -> analysis.Analysis:
    """
    Analizar lo escrito, en la tonalidad que dice la consigna.

    El analizador deduce la tonalidad solo y lo hace bien con una pieza
    entera; con cuatro acordes, el último pesa más que todo lo demás junto
    ---es lo que debe hacer: una pieza termina en su tónica---, y un
    fragmento que termina en una cadencia rota se lee en la tonalidad del
    sexto grado. El alumno no escribió en esa tonalidad: escribió en la que
    le pidieron. Así que los acordes, las inversiones y el contrapunto los
    lee el analizador como siempre, y la función de cada acorde y la cadencia
    se vuelven a pedir con la tonalidad de la consigna, que es lo que haría
    cualquiera que corrige un ejercicio.
    """
    result = analysis.analyse(score_of(item, lines))
    if not result.segments:
        return result
    key = analysis.KeyReading(tonic_pc=item.tonic, mode_key=item.mode,
                              fifths=item.fifths, confidence=1.0,
                              reasons=["la tonalidad de la consigna"])
    segments = result.segments
    for index, segment in enumerate(segments):
        following = segments[index + 1] if index + 1 < len(segments) else None
        analysis.label_segment(segment, key, following)
        segment.figure = analysis.baroque_figure(
            segment.reading, segment.pitches, key, segment.sounding_pcs,
            segment.figured_extras)
    result.key = key
    result.cadences = analysis.relate(segments, key)
    result.groups = analysis.foreign_groups(segments, key)
    return result


#: El análisis del fragmento de partida de cada ejercicio. Lo dado no cambia
#: nunca ---el ejercicio es una constante---, y sin esto se lo volvía a
#: analizar en cada corrección, y dos veces en las de elegir: una para sacar
#: la respuesta y otra para dibujarla. Va por idioma porque el analizador
#: escribe sus explicaciones en el idioma de la pantalla al analizar: con un
#: solo análisis, cambiar de idioma dejaba los rótulos en el anterior.
_GIVEN: Dict[Tuple[Exercise, str], analysis.Analysis] = {}


def given_reading(item: Exercise) -> analysis.Analysis:
    """
    :func:`read` de lo que el ejercicio trae escrito, hecho una sola vez.

    Lo devuelto es compartido: se lee y se dibuja, no se modifica.
    """
    key = (item, i18n.language())
    result = _GIVEN.get(key)
    if result is None:
        result = read(item, given_lines(item))
        _GIVEN[key] = result
    return result


# ---------------------------------------------------------------------------
# Cómo se dice lo que se encontró
# ---------------------------------------------------------------------------

def voice_name(name: str) -> str:
    return tr(name)


def say_pc(pc: int, flats: bool = False) -> str:
    """Una nota, como se nombra en la prosa: «fa», o «F» en inglés."""
    name = i18n.note_name(pc % 12, flats)
    return name.lower() if i18n.is_default() else name


def say_pitch(pitch: int, flats: bool = False) -> str:
    """Una altura con su octava: «sol4»."""
    return f"{say_pc(pitch, flats)}{pitch // 12 - 1}"


#: Los intervalos dentro de la octava, por semitonos.
INTERVAL_NAMES = {
    0: "unísono u octava", 1: N("segunda menor"), 2: N("segunda mayor"),
    3: N("tercera menor"), 4: N("tercera mayor"), 5: N("cuarta justa"),
    6: N("tritono"), 7: N("quinta justa"), 8: N("sexta menor"),
    9: N("sexta mayor"), 10: "séptima menor", 11: "séptima mayor",
}

#: Palabras sueltas que la corrección le pasa a `tr()` desde una variable
#: ---los movimientos y las cadencias que devuelve el analizador---. La
#: cosecha del catálogo no las ve: una palabra sin acento no parece prosa.
#: Marcadas acá se traducen, y de paso se traducen también en el
#: analizador, que las dibuja igual. Los nombres de las voces no van: los
#: marca `app.VOICE_NAMES` y los traduce `en_engine`, con el catálogo de
#: voces.
GLOSSARY = (
    N("contrario"), N("oblicuo"), N("directo"), N("paralelo"), N("quieto"),
    N("semicadencia"), N("cadencia rota"), N("cadencia plagal"),
    N("Quintas paralelas"), N("Octavas paralelas"), N("Quinta oculta"),
    N("Octava oculta"),
)

#: Qué es cada clase de movimiento, para explicar una corrección. Las mismas
#: cuatro definiciones del libro.
MOTION_REASONS = {
    analysis.MOTION_CONTRARY: "una sube y la otra baja",
    analysis.MOTION_OBLIQUE: "una se queda quieta y la otra se mueve",
    analysis.MOTION_SIMILAR: "las dos van para el mismo lado y la distancia "
                             "entre ellas cambia",
    analysis.MOTION_PARALLEL: "las dos van para el mismo lado y conservan "
                              "el intervalo",
    analysis.MOTION_STATIC: "ninguna de las dos se mueve",
}

FUNCTION_NAMES = {"tonic": "tónica", "subdominant": N("subdominante"),
                  "dominant": N("dominante")}

#: Cómo se agrupa cada cadencia que nombra el analizador entre las cuatro
#: que se enseñan. La frigia no está entre las opciones: en un ejercicio de
#: cuatro acordes no aparece, y si aparece la corrección lo dice.
CADENCE_GROUPS = {
    "cadencia auténtica perfecta": "autentica",
    "cadencia auténtica imperfecta": "autentica",
    "cadencia plagal": "plagal",
    "cadencia rota": "rota",
    "semicadencia": "semi",
}


@dataclass
class Remark:
    """Algo que la corrección tiene para decir, y dónde."""

    text: str
    #: Compás donde pasa, contado desde 1; ``until`` es el último compás
    #: del tramo cuando es un paso entre dos. Cero es «en ninguno».
    bar: int = 0
    until: int = 0
    #: Las voces involucradas, por nombre.
    voices: Tuple[str, ...] = ()
    #: ``"grave"`` es lo que impide aprobar, ``"nota"`` es un comentario y
    #: ``"bien"`` explica por qué lo que se hizo está bien.
    severity: str = "grave"


@dataclass
class Verdict:
    """El resultado de corregir un ejercicio."""

    passed: bool
    remarks: List[Remark] = field(default_factory=list)
    #: El análisis de lo que se escribió, para dibujarlo sobre el sistema.
    result: Optional[analysis.Analysis] = None
    #: La respuesta correcta, en los ejercicios de elegir.
    answer: str = ""

    @property
    def problems(self) -> List[Remark]:
        return [r for r in self.remarks if r.severity == "grave"]


def _verdict(remarks: List[Remark], result=None, answer: str = "") -> Verdict:
    return Verdict(passed=not any(r.severity == "grave" for r in remarks),
                   remarks=remarks, result=result, answer=answer)


def _names(result: analysis.Analysis, indices: Sequence[int]) -> Tuple[str, ...]:
    parts = result.score.parts
    return tuple(parts[i].name for i in indices if 0 <= i < len(parts))


def _part_index(result: analysis.Analysis, lane: int) -> int:
    """Dónde quedó una voz en el análisis, que las ordena por registro."""
    for index, part in enumerate(result.score.parts):
        if part.name == VOICE_NAMES[lane]:
            return index
    return -1


def _segment_at(result: analysis.Analysis, bar: int):
    for segment in result.segments:
        if segment.bar_index == bar:
            return segment
    return None


def _reading_name(segment) -> str:
    """Cómo se lee un acorde en una corrección: «G (V)»."""
    if segment is None or segment.reading is None:
        return tr("un acorde que no se pudo nombrar")
    numeral = segment.numeral or "?"
    return f"{segment.reading.symbol} ({numeral})"


# ---------------------------------------------------------------------------
# La corrección: lo que se escribe
# ---------------------------------------------------------------------------

def _missing(item: Exercise, lines: Sequence[Line_]) -> List[Remark]:
    """Lo que falta escribir y lo que se escribió de más."""
    written = cells(lines)
    remarks: List[Remark] = []
    for bar in range(1, item.bars + 1):
        for lane in editable_lanes(item):
            if written.get((bar, lane)) is None:
                remarks.append(Remark(
                    trf("Falta escribir {voice} en el compás {bar}.",
                        voice=voice_name(VOICE_NAMES[lane]), bar=bar),
                    bar=bar, voices=(VOICE_NAMES[lane],)))
    for lane, line in enumerate(lines):
        last_sound = 0.0
        moment = 0.0
        for pitch, duration in line:
            moment += duration
            if pitch is not None:
                last_sound = moment
        if last_sound > item.bars * FIGURE + 1e-6:
            remarks.append(Remark(
                trf("{voice} tiene notas después del compás {bar}, que es "
                    "donde termina el ejercicio.",
                    voice=voice_name(VOICE_NAMES[lane]), bar=item.bars),
                bar=item.bars, voices=(VOICE_NAMES[lane],)))
    return remarks


def _counterpoint_faults(result: analysis.Analysis,
                         kinds=("quintas_paralelas", "octavas_paralelas",
                                "cruce")) -> List[Remark]:
    """Las faltas graves que encontró el analizador, con su lugar."""
    remarks: List[Remark] = []
    for finding in result.findings:
        if finding.kind not in kinds or finding.severity != "grave":
            continue
        names = _names(result, finding.voices)
        pair = trf("{voice} y {voice2}", voice=voice_name(names[0]),
                   voice2=voice_name(names[-1])) if names else ""
        if finding.kind == "cruce":
            text = trf("Cruce de voces en el compás {bar}: {voice} canta por "
                       "encima de {voice2}.", bar=finding.bar_index,
                       voice=voice_name(names[0]), voice2=voice_name(names[-1]))
            remarks.append(Remark(text, bar=finding.bar_index,
                                  voices=names))
            continue
        label = tr(finding.label)
        text = trf("{label} entre {pair}, del compás {before} al {bar}.",
                   label=label, pair=pair, before=max(1, finding.bar_index - 1),
                   bar=finding.bar_index)
        remarks.append(Remark(text, bar=max(1, finding.bar_index - 1),
                              until=finding.bar_index, voices=names))
    return remarks


def _check_motions(item: Exercise, result: analysis.Analysis) -> List[Remark]:
    low, high = item.param("pair", (BASS, SOPRANO))
    wanted = item.param("kinds", ())
    a, b = _part_index(result, low), _part_index(result, high)
    remarks: List[Remark] = []
    reports = {report.bar_index: report for report in result.motions}
    for step, kind in enumerate(wanted, start=1):
        report = reports.get(step)
        found = None
        if report is not None:
            found = report.pairs.get((min(a, b), max(a, b)))
        pair = trf("{voice} y {voice2}", voice=voice_name(VOICE_NAMES[low]),
                   voice2=voice_name(VOICE_NAMES[high]))
        if found == kind:
            remarks.append(Remark(
                trf("Del compás {bar} al {next}: {pair}, movimiento {kind}.",
                    bar=step, next=step + 1, pair=pair, kind=tr(kind)),
                bar=step, until=step + 1,
                voices=(VOICE_NAMES[low], VOICE_NAMES[high]),
                severity="bien"))
            continue
        heard = tr(found) if found else tr("ninguno")
        reason = tr(MOTION_REASONS.get(found, "")) if found else ""
        remarks.append(Remark(
            trf("Del compás {bar} al {next}, {pair} hacen movimiento "
                "{heard}, porque {reason}. Acá se pedía {kind}.",
                bar=step, next=step + 1, pair=pair, heard=heard,
                reason=reason, kind=tr(kind)),
            bar=step, until=step + 1,
            voices=(VOICE_NAMES[low], VOICE_NAMES[high])))
    return remarks


def _written_bars(item: Exercise, lines: Sequence[Line_]) -> List[int]:
    """Los compases donde el alumno escribió algo que no venía dado."""
    written = cells(lines)
    lanes = editable_lanes(item)
    return [bar for bar, chord in enumerate(item.chords, start=1)
            if any(written.get((bar, lane)) != chord[lane] for lane in lanes)]


def _missing_thirds(item: Exercise, result: analysis.Analysis,
                    lines: Sequence[Line_], skip: Sequence[int] = ()
                    ) -> List[Remark]:
    """
    Los acordes sin tercera que escribió el alumno.

    El analizador nombra igual un acorde al que le falta la tercera ---re,
    re, re y la se lee Dm, porque la tonalidad dice menor--- y la anota en
    ``missing``. Mirando sólo el nombre, la corrección aprobaba un acorde
    hueco, que no es mayor ni menor: es lo mismo que ya marca
    :func:`_check_chord`. Sólo en los compases que escribió el alumno: un
    acorde dado no es culpa suya. ``skip`` son los compases que ya tienen
    otra falta que lo explica.
    """
    flats = item.fifths < 0
    remarks: List[Remark] = []
    for bar in _written_bars(item, lines):
        if bar in skip:
            continue
        segment = _segment_at(result, bar)
        if segment is None or segment.reading is None:
            continue
        reading = segment.reading
        if "third" not in reading.missing:
            continue
        third = next((pc for pc, role, _s in reading.tones
                      if role == "third"), None)
        if third is None:
            text = trf("Falta {role}: es la nota que define el acorde.",
                       role=tr("la tercera"))
        else:
            text = trf("En el compás {bar}, {chord} no tiene tercera: falta "
                       "{note}, que es la nota que dice si el acorde es mayor "
                       "o menor.", bar=bar, chord=reading.symbol,
                       note=say_pc(third, flats))
        remarks.append(Remark(text, bar=bar))
    return remarks


def _check_same_chords(item: Exercise, result: analysis.Analysis,
                       lines: Sequence[Line_]) -> List[Remark]:
    """Que cada compás siga siendo el acorde que era, y entero."""
    before = given_reading(item)
    remarks: List[Remark] = []
    for bar in range(1, item.bars + 1):
        was = _segment_at(before, bar)
        now = _segment_at(result, bar)
        if was is None or was.reading is None:
            continue
        same = (now is not None and now.reading is not None
                and now.reading.root_pc == was.reading.root_pc
                and now.reading.quality == was.reading.quality)
        if not same:
            remarks.append(Remark(
                trf("En el compás {bar} el acorde cambió: era {was} y ahora "
                    "se lee {now}. Se corrige moviendo las voces, no "
                    "cambiando la armonía.", bar=bar,
                    was=was.reading.symbol,
                    now=(now.reading.symbol if now is not None and now.reading
                         else tr("otra cosa"))),
                bar=bar))
    # El mismo nombre no alcanza: un Dm sin fa se sigue leyendo Dm.
    remarks += _missing_thirds(item, result, lines,
                               skip=[r.bar for r in remarks])
    return remarks


def _check_chord(item: Exercise, result: analysis.Analysis) -> List[Remark]:
    root, quality = item.param("root"), item.param("quality", "")
    inversion = item.param("inversion", 0)
    segment = _segment_at(result, 1)
    flats = item.fifths < 0
    if segment is None or segment.reading is None:
        return [Remark(tr("El analizador no encuentra un acorde en lo que "
                          "escribiste: hacen falta al menos tres voces "
                          "sonando juntas."), bar=1)]
    reading = segment.reading
    remarks: List[Remark] = []
    if reading.root_pc != root or reading.quality != quality:
        # El acorde que se pidió puede estar escrito con una nota menos: se
        # dice eso, que es lo útil, y no sólo cómo se lee lo que quedó.
        remarks.append(Remark(
            trf("Lo que escribiste se lee {symbol}, no {wanted}.",
                symbol=reading.symbol, wanted=_chord_symbol(root, quality,
                                                            flats)),
            bar=1))
        if quality == "7" and reading.root_pc == root and reading.quality == "":
            remarks.append(Remark(
                trf("Le falta la séptima ({note}): sin ella es una tríada.",
                    note=say_pc(root + 10, flats)), bar=1))
        return remarks
    for role, label in (("third", "la tercera"), ("seventh", "la séptima")):
        if role in reading.missing and (role == "third"
                                        or item.param("complete")):
            remarks.append(Remark(
                trf("Falta {role}: es la nota que define el acorde.",
                    role=tr(label)), bar=1))
    if reading.inversion != inversion:
        names = {0: "la fundamental", 1: "la tercera", 2: "la quinta",
                 3: "la séptima"}
        state = {0: "estado fundamental", 1: "primera inversión",
                 2: "segunda inversión", 3: "tercera inversión"}
        bass = reading.bass_pc if reading.bass_pc is not None else root
        stack = [pc for pc, _role, _size in reading.tones]
        target = stack[inversion] if inversion < len(stack) else root
        if reading.inversion < 0:
            # El analizador dice -1 cuando el bajo no es nota del acorde.
            # Llevado a cero con un `max`, la corrección le decía a quien
            # puso un do debajo de un Sol «la fundamental: estado
            # fundamental», que es justo lo que no es.
            text = trf("El bajo canta {note}, que no es nota de {chord}: así "
                       "no es ninguna inversión. Se pidió {wanted_state}, con "
                       "{wanted_role} ({target}) en el bajo.",
                       note=say_pc(bass, flats),
                       chord=_chord_symbol(reading.root_pc, reading.quality,
                                           flats),
                       wanted_state=tr(state[inversion]),
                       wanted_role=tr(names[inversion]),
                       target=say_pc(target, flats))
        else:
            text = trf("El bajo canta {note}, {role}: eso es {state}. Se "
                       "pidió {wanted_state}, con {wanted_role} ({target}) en "
                       "el bajo.",
                       note=say_pc(bass, flats),
                       role=tr(names.get(reading.inversion, N("otra nota"))),
                       state=tr(state.get(reading.inversion, N("otra cosa"))),
                       wanted_state=tr(state[inversion]),
                       wanted_role=tr(names[inversion]),
                       target=say_pc(target, flats))
        remarks.append(Remark(text, bar=1, voices=("Bajo",)))
    if not remarks:
        text = (trf("El analizador lee {symbol}, cifrado {figure}: justo lo "
                    "que se pidió.", symbol=reading.symbol,
                    figure=segment.figure) if segment.figure else
                trf("El analizador lee {symbol}, en estado fundamental: justo "
                    "lo que se pidió.", symbol=reading.symbol))
        remarks.append(Remark(text, bar=1, severity="bien"))
    return remarks


def _chord_symbol(root: int, quality: str, flats: bool) -> str:
    names = analysis.FLAT_NAMES if flats else analysis.SHARP_NAMES
    return names[root % 12] + quality


def _check_resolution(item: Exercise, result: analysis.Analysis,
                      lines: Sequence[Line_]) -> List[Remark]:
    """La séptima baja un grado y la sensible sube a la tónica."""
    bar = item.param("bar", 1)
    written = cells(lines)
    remarks: List[Remark] = []
    segment = _segment_at(result, bar)
    following = _segment_at(result, bar + 1)
    if following is None or following.reading is None or \
            following.reading.root_pc != item.tonic:
        return [Remark(
            trf("El compás {bar} se lee {chord}: tiene que ser la tónica "
                "({tonic}).", bar=bar + 1, chord=_reading_name(following),
                tonic=_chord_symbol(item.tonic, "", item.fifths < 0)),
            bar=bar + 1)]
    if segment is None or segment.reading is None:
        # La misma guarda que en `_check_chord`: hoy la dominante viene
        # escrita, pero un ejercicio que la pida tiene que poder corregirse
        # aunque el alumno deje ese compás sin acorde.
        return [Remark(tr("El analizador no encuentra un acorde en lo que "
                          "escribiste: hacen falta al menos tres voces "
                          "sonando juntas."), bar=bar)]
    reading = segment.reading
    seventh = next((pc for pc, role, _s in reading.tones if role == "seventh"),
                   None)
    third = next((pc for pc, role, _s in reading.tones if role == "third"),
                 None)
    for lane in item.lanes:
        before = written.get((bar, lane))
        after = written.get((bar + 1, lane))
        if before is None or after is None:
            continue
        name = voice_name(VOICE_NAMES[lane])
        move = after - before
        if seventh is not None and before % 12 == seventh:
            if move in (-1, -2):
                remarks.append(Remark(
                    trf("La séptima ({note}, en {voice}) baja un grado a "
                        "{target}.", note=say_pc(before), voice=name,
                        target=say_pc(after)),
                    bar=bar, until=bar + 1, voices=(VOICE_NAMES[lane],),
                    severity="bien"))
            else:
                remarks.append(Remark(
                    trf("La séptima ({note}, en {voice}) va a {target}: "
                        "tiene que bajar un grado.", note=say_pc(before),
                        voice=name, target=say_pc(after)),
                    bar=bar, until=bar + 1, voices=(VOICE_NAMES[lane],)))
        if third is not None and before % 12 == third:
            if move == 1:
                remarks.append(Remark(
                    trf("La sensible ({note}, en {voice}) sube a la tónica.",
                        note=say_pc(before), voice=name),
                    bar=bar, until=bar + 1, voices=(VOICE_NAMES[lane],),
                    severity="bien"))
            else:
                remarks.append(Remark(
                    trf("La sensible ({note}, en {voice}) va a {target}: "
                        "tiene que subir un semitono, a la tónica.",
                        note=say_pc(before), voice=name,
                        target=say_pc(after)),
                    bar=bar, until=bar + 1, voices=(VOICE_NAMES[lane],)))
    return remarks


def _check_cadence(item: Exercise, result: analysis.Analysis,
                   lines: Sequence[Line_]) -> List[Remark]:
    # El analizador reconoce la cadencia por el nombre de los acordes, y un
    # Sol sin si se sigue llamando Sol: la cadencia salía «perfecta» con el
    # acorde final hueco. Las terceras se miran aparte.
    return (_cadence_reading(item, result)
            + _missing_thirds(item, result, lines))


def _cadence_reading(item: Exercise, result: analysis.Analysis
                     ) -> List[Remark]:
    """Qué cadencia leyó el analizador en los dos últimos acordes."""
    wanted = item.param("kinds", ())
    segments = result.segments
    if len(segments) < 2:
        return [Remark(tr("Hacen falta al menos dos acordes para que haya "
                          "cadencia."), bar=item.bars)]
    last = len(segments) - 1
    found = next((c for c in result.cadences if c.index == last), None)
    before, after = segments[last - 1], segments[last]
    where = dict(bar=before.bar_index, until=after.bar_index)
    pair = f"{_reading_name(before)} - {_reading_name(after)}"
    if found is not None and found.kind in wanted:
        return [Remark(trf("{pair}: {kind}. {detail}.", pair=pair,
                           kind=tr(found.kind).capitalize(),
                           detail=tr(found.detail).capitalize()),
                       severity="bien", **where)]
    if found is not None:
        return [Remark(trf("Los dos últimos acordes se leen {pair}: eso es "
                           "una {kind}, no una {wanted}.", pair=pair,
                           kind=tr(found.kind), wanted=tr(wanted[0])),
                       **where)]
    function = tr(FUNCTION_NAMES.get(after.function, after.function or "?"))
    return [Remark(trf("Los dos últimos acordes se leen {pair}, y el último "
                       "es {function}: la frase no cierra con una {wanted}.",
                       pair=pair, function=function, wanted=tr(wanted[0])),
                   **where)]


def _check_organum(item: Exercise, lines: Sequence[Line_]) -> List[Remark]:
    upper, lower = item.param("upper"), item.param("lower")
    interval = item.param("interval", 7)
    written = cells(lines)
    remarks: List[Remark] = []
    for bar in range(1, item.bars + 1):
        high, low = written.get((bar, upper)), written.get((bar, lower))
        if high is None or low is None:
            continue
        distance = high - low
        if distance == interval:
            continue
        if distance <= 0:
            text = trf("En el compás {bar} la organalis ({note}) no está "
                       "debajo de la principalis: va una quinta justa más "
                       "abajo.", bar=bar, note=say_pitch(low))
        else:
            text = trf("En el compás {bar} la organalis está a una {name} "
                       "de la principalis ({semitones} semitonos): va a la "
                       "quinta justa, siete semitonos más abajo, que sería "
                       "{target}.", bar=bar,
                       name=tr(INTERVAL_NAMES[distance % 12]),
                       semitones=distance, target=say_pitch(high - interval))
        remarks.append(Remark(text, bar=bar,
                              voices=(VOICE_NAMES[lower], VOICE_NAMES[upper])))
    if not remarks:
        remarks.append(Remark(
            tr("Cada nota de la organalis está una quinta justa debajo de la "
               "principalis, y las dos se mueven en paralelo: es el organum "
               "más antiguo que hay."), severity="bien"))
    return remarks


def _check_guide_tones(item: Exercise, result: analysis.Analysis,
                       lines: Sequence[Line_]) -> List[Remark]:
    lanes = item.param("lanes", (TENOR, ALTO))
    written = cells(lines)
    remarks: List[Remark] = []
    for bar in range(1, item.bars + 1):
        segment = _segment_at(result, bar)
        if segment is None or segment.reading is None:
            continue
        reading = segment.reading
        roles = {pc: role for pc, role, _s in reading.tones}
        guides = {pc for pc, role in roles.items()
                  if role in ("third", "seventh")}
        names = {"root": "la fundamental", "third": "la tercera",
                 "fifth": "la quinta", "seventh": "la séptima"}
        sung = {written.get((bar, lane)) for lane in lanes}
        for lane in lanes:
            pitch = written.get((bar, lane))
            if pitch is None or pitch % 12 in guides:
                continue
            role = roles.get(pitch % 12)
            remarks.append(Remark(
                trf("En el compás {bar}, {voice} canta {note}, que es {role} "
                    "de {chord}: las guide tones son la tercera y la "
                    "séptima.", bar=bar, voice=voice_name(VOICE_NAMES[lane]),
                    note=say_pc(pitch),
                    role=tr(names.get(role, "una nota de afuera")),
                    chord=reading.symbol),
                bar=bar, voices=(VOICE_NAMES[lane],)))
        if guides and not guides <= {p % 12 for p in sung if p is not None}:
            missing = sorted(guides - {p % 12 for p in sung if p is not None})
            if not any(r.bar == bar for r in remarks):
                remarks.append(Remark(
                    trf("En el compás {bar} falta {notes} en el tenor o el "
                        "alto.", bar=bar,
                        notes=", ".join(say_pc(pc) for pc in missing)),
                    bar=bar))
        if bar == 1:
            continue
        for lane in lanes:
            before, after = written.get((bar - 1, lane)), written.get((bar, lane))
            if before is None or after is None:
                continue
            if abs(after - before) > 2:
                remarks.append(Remark(
                    trf("Del compás {before} al {bar}, {voice} salta de "
                        "{a} a {b}: las guide tones se conectan por grado "
                        "o se quedan quietas.", before=bar - 1, bar=bar,
                        voice=voice_name(VOICE_NAMES[lane]),
                        a=say_pc(before), b=say_pc(after)),
                    bar=bar - 1, until=bar, voices=(VOICE_NAMES[lane],)))
    if not remarks:
        remarks.append(Remark(
            tr("La séptima de cada acorde pasa a ser la tercera del "
               "siguiente y la tercera queda quieta como séptima: dos notas "
               "llevan toda la progresión."), severity="bien"))
    return remarks


def _check_harmonic_note(item: Exercise, lines: Sequence[Line_]
                         ) -> List[Remark]:
    fundamental = item.param("midi", 48)
    number = item.param("number", 3)
    frequency = harmonics.Spectrum(midi=fundamental).fundamental * number
    target, cents = harmonics.nearest_note(frequency)
    written = cells(lines)
    pitch = next((written.get((1, lane)) for lane in editable_lanes(item)
                  if written.get((1, lane)) is not None), None)
    if pitch is None:
        return [Remark(tr("Falta escribir la nota."), bar=1)]
    if pitch == target:
        return [Remark(trf("El armónico {number} de {base} da {hz} hercios: "
                           "la tecla más cercana es {note}, a {cents} "
                           "centésimas.", number=number,
                           base=say_pitch(fundamental),
                           hz=int(round(frequency)), note=say_pitch(target),
                           cents=f"{cents:+.1f}"),
                       bar=1, severity="bien")]
    remarks = [Remark(trf("Escribiste {note}. El armónico {number} de {base} "
                          "da {hz} hercios, y eso cae en {target}.",
                          note=say_pitch(pitch), number=number,
                          base=say_pitch(fundamental),
                          hz=int(round(frequency)),
                          target=say_pitch(target)), bar=1)]
    if pitch % 12 == target % 12:
        remarks.append(Remark(tr("Es la nota correcta, pero en otra octava: "
                                 "cada armónico tiene una altura exacta, no "
                                 "sólo un nombre."), bar=1, severity="nota"))
    else:
        base = harmonics.Spectrum(midi=fundamental).fundamental
        for other in range(1, harmonics.PARTIAL_COUNT + 1):
            if harmonics.nearest_note(base * other)[0] == pitch:
                remarks.append(Remark(
                    trf("Lo que escribiste es el armónico {other}.",
                        other=other), bar=1, severity="nota"))
                break
    return remarks


def grade_written(item: Exercise, lines: Sequence[Line_]) -> Verdict:
    """Corregir lo que el alumno escribió en el pentagrama."""
    remarks = _missing(item, lines)
    touched = tampered(item, lines)
    if touched is not None:
        bar, lane = touched
        remarks.insert(0, Remark(
            trf("{voice} en el compás {bar} venía escrito y cambió.",
                voice=voice_name(VOICE_NAMES[lane]), bar=bar),
            bar=bar, voices=(VOICE_NAMES[lane],)))
    if any(r.severity == "grave" for r in remarks):
        return _verdict(remarks)
    if item.rule == "harmonic_note":
        return _verdict(_check_harmonic_note(item, lines))
    result = read(item, lines)
    rule = item.rule
    if rule == "motions":
        remarks += _check_motions(item, result)
    elif rule == "clean":
        remarks += _check_same_chords(item, result, lines)
        remarks += _counterpoint_faults(result)
    elif rule == "chord":
        remarks += _counterpoint_faults(result, ("cruce",))
        remarks += _check_chord(item, result)
    elif rule == "resolution":
        remarks += _check_resolution(item, result, lines)
        remarks += _counterpoint_faults(result)
    elif rule == "cadence":
        remarks += _check_cadence(item, result, lines)
        remarks += _counterpoint_faults(result)
    elif rule == "organum":
        remarks += _check_organum(item, lines)
    elif rule == "guide_tones":
        remarks += _check_guide_tones(item, result, lines)
        remarks += _counterpoint_faults(result, ("cruce",))
    if rule == "clean" and not any(r.severity == "grave" for r in remarks):
        remarks.append(Remark(
            tr("Los acordes son los mismos y el analizador ya no encuentra "
               "paralelas ni cruces."), severity="bien"))
    return _verdict(remarks, result)


# ---------------------------------------------------------------------------
# Las reglas de los estilos
# ---------------------------------------------------------------------------
#
# Cada regla dice **de qué campo del perfil sale** y cómo se la encuentra en
# un fragmento. Así la pregunta «¿qué regla rompe?» se contesta mirando el
# perfil de verdad: si mañana el gregoriano deja de prohibir el trítono
# armónico, el ejercicio cambia de respuesta solo ---y el test que lo
# vigila avisa que hay que cambiarle el fragmento---.

def _steps(chords: Sequence[Chord]):
    for index in range(1, len(chords)):
        yield index, chords[index - 1], chords[index]


def _find_parallels(chords, _segments, _profile
                    ) -> List[Tuple[int, int, Tuple[int, int]]]:
    found = []
    for index, before, after in _steps(chords):
        lanes = [lane for lane in range(4)
                 if before[lane] is not None and after[lane] is not None]
        for i, a in enumerate(lanes):
            for b in lanes[i + 1:]:
                fifth, _octave = parallel_interval_violation(
                    [before[a], before[b]], [after[a], after[b]], 0, 1)
                if fifth:
                    found.append((index, index + 1, (a, b)))
    return found


def _find_harmonic_tritone(chords, _segments, _profile):
    found = []
    for bar, chord in enumerate(chords, start=1):
        sounding = [(lane, p) for lane, p in enumerate(chord) if p is not None]
        if not has_harmonic_tritone([p for _l, p in sounding]):
            continue
        for i, (a, pa) in enumerate(sounding):
            for b, pb in sounding[i + 1:]:
                if (pb - pa) % 12 == 6:
                    found.append((bar, bar, (a, b)))
    return found


def _find_tritone_leap(chords, _segments, _profile):
    # Qué es un salto de trítono lo decide el evaluador, no esta función:
    # primero se le pregunta por el paso entero ---lo mismo que mira la
    # búsqueda--- y después voz por voz, para decir cuál fue.
    found = []
    for index, before, after in _steps(chords):
        lanes = [lane for lane in range(4)
                 if before[lane] is not None and after[lane] is not None]
        if not has_melodic_tritone([before[lane] for lane in lanes],
                                   [after[lane] for lane in lanes]):
            continue
        for lane in lanes:
            if has_melodic_tritone([before[lane]], [after[lane]]):
                found.append((index, index + 1, (lane,)))
    return found


def _find_big_leap(chords, _segments, profile):
    """Los saltos más grandes que el techo del estilo."""
    limit = profile.style_max_leap
    found = []
    for index, before, after in _steps(chords):
        for lane in range(4):
            if before[lane] is None or after[lane] is None:
                continue
            if abs(after[lane] - before[lane]) > limit:
                found.append((index, index + 1, (lane,)))
    return found


def _find_crossing(chords, _segments, _profile):
    # El cruce lo cuenta el evaluador sobre las voces que suenan, de grave a
    # agudo, que es como se las pasa la búsqueda: una voz que calla no
    # separa a las de al lado. Primero el acorde entero y después cada par
    # vecino, para decir cuáles se cruzaron.
    found = []
    for bar, chord in enumerate(chords, start=1):
        sounding = [(lane, p) for lane, p in enumerate(chord) if p is not None]
        if not _crossing_count([p for _l, p in sounding]):
            continue
        for (low, a), (high, b) in zip(sounding, sounding[1:]):
            if _crossing_count([a, b]):
                found.append((bar, bar, (low, high)))
    return found


def _find_minor_ninth(chords, segments, _profile):
    found = []
    for bar, chord in enumerate(chords, start=1):
        segment = next((s for s in segments if s.bar_index == bar), None)
        if segment is None or segment.reading is None:
            continue
        context = ChordContext(root_pc=segment.reading.root_pc)
        sounding = [(lane, p) for lane, p in enumerate(chord) if p is not None]
        if not minor_ninth_penalty([p for _l, p in sounding], context, 1.0):
            continue
        for i, (a, pa) in enumerate(sounding):
            for b, pb in sounding[i + 1:]:
                if pb - pa == 13 and pa % 12 != context.root_pc:
                    found.append((bar, bar, (a, b)))
    return found


@dataclass(frozen=True)
class StyleRule:
    """Una regla de estilo, atada al campo del perfil que la enciende."""

    key: str
    label: str
    #: Si el perfil la tiene. Recibe un `GenreProfile`.
    active: Any
    #: Si el perfil la tiene como **prohibición**: la solución se descarta
    #: entera. Las demás se castigan con peso.
    forbidden: Any
    find: Any


STYLE_RULES: Tuple[StyleRule, ...] = (
    StyleRule("paralelas", N("Quintas paralelas"),
              lambda p: p.forbid_parallel_fifths,
              lambda p: p.forbid_parallel_fifths, _find_parallels),
    StyleRule("tritono", "Tritono entre dos voces",
              lambda p: p.forbid_harmonic_tritone,
              lambda p: p.forbid_harmonic_tritone, _find_harmonic_tritone),
    StyleRule("salto_tritono", "Salto de tritono en una voz",
              lambda p: p.forbid_melodic_tritone
              or 6 in p.forbidden_melodic_intervals,
              lambda p: p.forbid_melodic_tritone, _find_tritone_leap),
    # El gregoriano es el único que pone un techo a los saltos, y el techo
    # es de cinco semitonos: una cuarta justa. El rótulo lo dice así, y un
    # test vigila que el número siga siendo ése.
    StyleRule("salto_grande", "Salto de más de una cuarta",
              lambda p: p.style_max_leap is not None,
              lambda p: False, _find_big_leap),
    StyleRule("cruce", "Cruce de voces",
              lambda p: p.forbid_voice_crossing,
              lambda p: p.forbid_voice_crossing, _find_crossing),
    StyleRule("novena_menor", "Novena menor sobre una nota que no es la "
                              "fundamental",
              lambda p: p.weight_minor_ninth > 0,
              lambda p: False, _find_minor_ninth),
)

RULES_BY_KEY = {rule.key: rule for rule in STYLE_RULES}

#: Por qué un estilo deja pasar algo que otro castiga. Son las razones del
#: libro, dichas con sus palabras.
TOLERATED_BECAUSE = {
    ("paralelas", "gregorian"): "el organum consiste justamente en doblar "
                                "la melodía en paralelo",
    ("paralelas", "jazz"): "con acordes tan densos el efecto no llega a "
                           "escucharse",
    ("tritono", "classical"): "está adentro de cada acorde de séptima de "
                              "dominante, y es lo que lo hace tirar",
    ("tritono", "jazz"): "los tritonos pasan sin problema",
}

GENRE_NAMES = {"classical": N("Barroco"), "gregorian": N("Gregoriano"),
               "jazz": "Jazz"}


def style_violations(item: Exercise, genre: str) -> Dict[str, list]:
    """Qué reglas del estilo rompe el fragmento, y dónde."""
    profile = GENRE_PROFILES[genre]
    result = given_reading(item)
    out: Dict[str, list] = {}
    for rule in STYLE_RULES:
        if not rule.active(profile):
            continue
        found = rule.find(item.chords, result.segments, profile)
        if found:
            out[rule.key] = found
    return out


def _where(found) -> Tuple[int, int, Tuple[str, ...]]:
    first, until, lanes = found[0]
    return first, until, tuple(VOICE_NAMES[lane] for lane in lanes)


def _where_text(first: int, until: int, voices: Tuple[str, ...]) -> str:
    names = trf("{voice} y {voice2}", voice=voice_name(voices[0]),
                voice2=voice_name(voices[-1])) if len(voices) > 1 \
        else voice_name(voices[0])
    if first == until:
        return trf("{names}, en el compás {bar}", names=names, bar=first)
    return trf("{names}, del compás {bar} al {until}", names=names, bar=first,
               until=until)


# ---------------------------------------------------------------------------
# La corrección: lo que se elige
# ---------------------------------------------------------------------------

def correct_choice(item: Exercise) -> str:
    """La respuesta correcta, calculada y no escrita a mano."""
    return _answer(item)[0]


def _answer(item: Exercise) -> Tuple[str, List[Remark]]:
    """La respuesta y su explicación, sacadas del analizador o del motor."""
    rule = item.rule
    if item.kind == TONE:
        return _tone_answer(item)
    result = given_reading(item)
    if rule == "motion_at":
        low, high = item.param("pair")
        step = item.param("step")
        a, b = _part_index(result, low), _part_index(result, high)
        report = next((r for r in result.motions if r.bar_index == step), None)
        kind = report.pairs.get((min(a, b), max(a, b)), "") if report else ""
        given = given_lines(item)
        moves = []
        for lane in (low, high):
            line = [p for p, _d in given[lane]]
            before, after = line[step - 1], line[step]
            # Tres frases enteras y no un verbo pegado: «sube de re a mi» y
            # «se queda en re» no se arman igual en ningún idioma.
            name = voice_name(VOICE_NAMES[lane])
            if after > before:
                moves.append(trf("{voice} sube de {a} a {b}", voice=name,
                                 a=say_pitch(before), b=say_pitch(after)))
            elif after < before:
                moves.append(trf("{voice} baja de {a} a {b}", voice=name,
                                 a=say_pitch(before), b=say_pitch(after)))
            else:
                moves.append(trf("{voice} se queda en {a}", voice=name,
                                 a=say_pitch(before)))
        text = trf("Del compás {bar} al {next}: {moves}. {reason}: movimiento "
                   "{kind}.", bar=step, next=step + 1,
                   moves="; ".join(moves),
                   reason=tr(MOTION_REASONS.get(kind, "")).capitalize(),
                   kind=tr(kind))
        return kind, [Remark(text, bar=step, until=step + 1,
                             voices=(VOICE_NAMES[low], VOICE_NAMES[high]),
                             severity="bien")]
    if rule == "parallel_pair":
        finding = next((f for f in result.findings
                        if f.kind == "quintas_paralelas"
                        and f.severity == "grave"), None)
        if finding is None:
            return "", []
        names = _names(result, finding.voices)
        text = trf("{voice} y {voice2} están a una quinta justa en el compás "
                   "{before} y siguen a una quinta en el {bar}, moviéndose "
                   "para el mismo lado.", voice=voice_name(names[0]),
                   voice2=voice_name(names[-1]),
                   before=finding.bar_index - 1, bar=finding.bar_index)
        return "|".join(names), [Remark(text, bar=finding.bar_index - 1,
                                        until=finding.bar_index,
                                        voices=names, severity="bien")]
    if rule == "direct_kind":
        kinds = {f.kind for f in result.findings}
        hidden = next((f for f in result.findings
                       if f.kind == "quintas_ocultas"), None)
        if "quintas_paralelas" in kinds:
            return "paralela", []
        if hidden is not None:
            names = _names(result, hidden.voices)
            text = trf("Antes no estaban a una quinta y llegan a una moviéndose "
                       "para el mismo lado, con la soprano saltando: el "
                       "analizador la marca como «{label}», un aviso y no una "
                       "falta. El libro la llama quinta directa: se penaliza, "
                       "no se prohíbe.", label=tr(hidden.label))
            return "oculta", [Remark(text, bar=hidden.bar_index,
                                     until=hidden.bar_index + 1, voices=names,
                                     severity="bien")]
        return "ninguna", []
    if rule == "quality":
        segment = _segment_at(result, 1)
        reading = segment.reading if segment else None
        if reading is None:
            return "", []
        third = next((pc for pc, role, _s in reading.tones if role == "third"),
                     None)
        minor = reading.quality in ("m", "m7", "dim", "m7b5", "dim7")
        third_name = say_pc(third if third is not None else 0)
        text = (trf("Es {symbol}: la tercera, {third}, está a tres semitonos "
                    "de la fundamental.", symbol=reading.symbol,
                    third=third_name) if minor else
                trf("Es {symbol}: la tercera, {third}, está a cuatro "
                    "semitonos de la fundamental.", symbol=reading.symbol,
                    third=third_name))
        return ("minor" if minor else "major"), [Remark(text, bar=1,
                                                       severity="bien")]
    if rule == "degree_at":
        bar = item.param("bar")
        segment = _segment_at(result, bar)
        if segment is None:
            return "", []
        text = trf("El compás {bar} es {symbol}: sobre el {degree}º grado de "
                   "la escala, y por eso {numeral}.", bar=bar,
                   symbol=segment.symbol,
                   degree=analysis._ROMAN.index(segment.numeral.upper()
                                                .rstrip("°ø+")) + 1
                   if segment.numeral.upper().rstrip("°ø+") in analysis._ROMAN
                   else "?",
                   numeral=segment.numeral)
        return segment.numeral, [Remark(text, bar=bar, severity="bien")]
    if rule == "inversion_at":
        bar = item.param("bar", 1)
        segment = _segment_at(result, bar)
        if segment is None or segment.reading is None:
            return "", []
        reading = segment.reading
        roles = {0: "la fundamental", 1: "la tercera", 2: "la quinta"}
        text = trf("El bajo canta {note}, que es {role} de {symbol}: el "
                   "analizador lo cifra {figure}.",
                   note=say_pc(reading.bass_pc if reading.bass_pc is not None
                               else reading.root_pc),
                   role=tr(roles.get(reading.inversion, "otra nota")),
                   symbol=_chord_symbol(reading.root_pc, reading.quality,
                                        False),
                   figure=segment.figure or tr("sin número"))
        return str(reading.inversion), [Remark(text, bar=bar,
                                               voices=("Bajo",),
                                               severity="bien")]
    if rule == "function_at":
        bar = item.param("bar")
        segment = _segment_at(result, bar)
        if segment is None:
            return "", []
        text = trf("El compás {bar} es {symbol}, el {numeral}: función de "
                   "{function}.", bar=bar, symbol=segment.symbol,
                   numeral=segment.numeral,
                   function=tr(FUNCTION_NAMES.get(segment.function, "?")))
        return segment.function, [Remark(text, bar=bar, severity="bien")]
    if rule == "cadence_kind":
        last = len(result.segments) - 1
        found = next((c for c in result.cadences if c.index == last), None)
        if found is None:
            return "", []
        before, after = result.segments[last - 1], result.segments[last]
        text = trf("Termina {pair}: {kind}. {detail}.",
                   pair=f"{_reading_name(before)} - {_reading_name(after)}",
                   kind=tr(found.kind), detail=tr(found.detail).capitalize())
        return CADENCE_GROUPS.get(found.kind, ""), [
            Remark(text, bar=before.bar_index, until=after.bar_index,
                   severity="bien")]
    if rule == "style_rule":
        genre = item.param("genre")
        broken = style_violations(item, genre)
        offered = {option.value for option in item.options}
        keys = [key for key in broken if key in offered]
        if len(keys) != 1:
            return "", []
        key = keys[0]
        first, until, voices = _where(broken[key])
        profile = GENRE_PROFILES[genre]
        fields = dict(rule=tr(RULES_BY_KEY[key].label),
                      where=_where_text(first, until, voices),
                      genre=tr(GENRE_NAMES[genre]))
        text = (trf("{rule}: {where}. El {genre} lo prohíbe.", **fields)
                if RULES_BY_KEY[key].forbidden(profile) else
                trf("{rule}: {where}. El {genre} lo castiga.", **fields))
        return key, [Remark(text, bar=first, until=until, voices=voices,
                            severity="bien")]
    if rule == "style_forbids":
        key = item.param("rule")
        strict = [genre for genre in GENRE_NAMES
                  if RULES_BY_KEY[key].forbidden(GENRE_PROFILES[genre])]
        if len(strict) != 1:
            return "", []
        found = RULES_BY_KEY[key].find(item.chords, result.segments,
                                       GENRE_PROFILES[strict[0]])
        first, until, voices = _where(found) if found else (0, 0, ())
        text = trf("Sólo el {genre} las prohíbe de plano: una solución que "
                   "las tenga se descarta entera, no importa lo bien que esté "
                   "todo lo demás.", genre=tr(GENRE_NAMES[strict[0]]))
        return strict[0], [Remark(text, bar=first, until=until, voices=voices,
                                  severity="bien")]
    return "", []


#: Qué mirar cuando la respuesta elegida no es, por clase de pregunta. Son
#: pistas y no la respuesta: dicen dónde está lo que hay que ver, que es lo
#: que haría un profesor con el cuaderno en la mano.
HINTS = {
    "parallel_pair": "Buscá dos voces que estén a una quinta justa y sigan a "
                     "una quinta en el acorde siguiente, moviéndose para el "
                     "mismo lado.",
    "direct_kind": "Fijate qué intervalo hay entre el bajo y la soprano en el "
                   "compás 1, y hacia dónde va cada una.",
    "quality": "Escuchá la tercera: en el acorde menor está un semitono más "
               "abajo, y el acorde suena más oscuro.",
    "degree_at": "Contá desde la tónica: el I es el acorde que se arma sobre "
                 "la primera nota de la escala.",
    "inversion_at": "Mirá qué nota está abajo de todo, en el bajo, y qué "
                    "papel cumple en el acorde.",
    "function_at": "Tónica es el I, y de refilón el vi y el iii; "
                   "subdominante, el IV y el ii; dominante, el V y el vii°.",
    "cadence_kind": "Mirá los dos últimos acordes: de qué grado sale el "
                    "penúltimo y si el último es la tónica.",
    "partial_hz": "Un armónico es la fundamental multiplicada por su número.",
    "partial_heard": "La octava suena como la misma nota más aguda; la quinta, "
                     "como otra nota que encaja con la fundamental.",
    "first_interval": "Mirá los nombres de las notas debajo de cada barra: la "
                      "tercera mayor de do es mi.",
    "partial_cents": "El libro lo cuenta en el capítulo de física: el séptimo "
                     "es «el caso serio».",
    "furthest": "El libro lo cuenta en el capítulo de física: hay uno que no "
                "tiene ninguna tecla cerca.",
}


def _wrong_choice(item: Exercise, chosen: str, answer: str) -> List[Remark]:
    """
    Por qué lo elegido no es, sin decir cuál es.

    Decir la respuesta correcta junto con el error convertía el segundo
    intento en copiar. Lo que se dice es qué tiene de malo lo elegido ---si
    hay algo concreto---, y dónde mirar.
    """
    if item.rule == "motion_at":
        step = item.param("step")
        return [Remark(
            trf("En un movimiento {kind}, {definition}. Mirá otra vez hacia "
                "dónde va cada voz del compás {bar} al {next}.",
                kind=tr(chosen), definition=tr(MOTION_REASONS.get(chosen, "")),
                bar=step, next=step + 1),
            bar=step, until=step + 1, severity="nota")]
    if item.rule == "parallel_pair":
        label = next((tr(o.label) for o in item.options if o.value == chosen),
                     chosen)
        return [Remark(trf("Entre {pair} no hay quintas paralelas.",
                           pair=label), severity="nota"),
                Remark(tr(HINTS["parallel_pair"]), severity="nota")]
    if item.rule == "style_rule":
        genre = item.param("genre")
        profile = GENRE_PROFILES[genre]
        rule = RULES_BY_KEY.get(chosen)
        if rule is None:
            return []
        if not rule.active(profile):
            why = TOLERATED_BECAUSE.get((chosen, genre), "")
            text = (trf("En el {genre} eso no se castiga: {why}.",
                        genre=tr(GENRE_NAMES[genre]), why=tr(why)) if why else
                    trf("En el {genre} eso no se castiga.",
                        genre=tr(GENRE_NAMES[genre])))
            return [Remark(text, severity="nota")]
        text = (trf("El {genre} lo prohíbe, pero en este fragmento no pasa.",
                    genre=tr(GENRE_NAMES[genre])) if rule.forbidden(profile)
                else trf("El {genre} lo castiga, pero en este fragmento no "
                         "pasa.", genre=tr(GENRE_NAMES[genre])))
        return [Remark(text, severity="nota")]
    if item.rule == "style_forbids":
        rule = RULES_BY_KEY[item.param("rule")]
        why = TOLERATED_BECAUSE.get((rule.key, chosen), "")
        if why:
            return [Remark(trf("En el {genre} se toleran: {why}.",
                               genre=tr(GENRE_NAMES.get(chosen, chosen)),
                               why=tr(why)), severity="nota")]
        return []
    hint = HINTS.get(item.rule, "")
    return [Remark(tr(hint), severity="nota")] if hint else []


def _tone_answer(item: Exercise) -> Tuple[str, List[Remark]]:
    midi = item.param("midi", 45)
    base = harmonics.Spectrum(midi=midi).fundamental
    rule = item.rule
    if rule == "partial_hz":
        number = item.param("number")
        hz = int(round(harmonics.Partial(number).frequency(base)))
        text = trf("{number} veces {base} hercios: {hz}. Los armónicos son "
                   "los múltiplos enteros de la fundamental.", number=number,
                   base=int(round(base)), hz=hz)
        return str(hz), [Remark(text, severity="bien")]
    if rule == "partial_heard":
        number = item.param("number")
        note, _cents = harmonics.nearest_note(base * number)
        text = trf("Era el {number}º: {hz} hercios, que cae en {note}.",
                   number=number, hz=int(round(base * number)),
                   note=say_pitch(note))
        return str(number), [Remark(text, severity="bien")]
    if rule == "first_interval":
        semitones = item.param("semitones", 4)
        for number in range(1, harmonics.PARTIAL_COUNT + 1):
            note, cents = harmonics.nearest_note(base * number)
            if (note - midi) % 12 == semitones:
                text = trf("El {number}º armónico de {base} cae en {note}, "
                           "{cents} centésimas de la tecla: es la tercera "
                           "mayor, y antes no aparece.", number=number,
                           base=say_pitch(midi), note=say_pitch(note),
                           cents=f"{cents:+.1f}")
                return str(number), [Remark(text, severity="bien")]
        return "", []
    if rule == "partial_cents":
        number = item.param("number")
        note, cents = harmonics.nearest_note(base * number)
        nearest = min(item.options, key=lambda o: abs(float(o.value) - cents))
        text = trf("El {number}º armónico da {hz} hercios; el {note} del "
                   "piano está a {cents} centésimas de semitono.",
                   number=number, hz=int(round(base * number)),
                   note=say_pitch(note), cents=f"{cents:+.1f}")
        return nearest.value, [Remark(text, severity="bien")]
    if rule == "furthest":
        numbers = item.param("numbers", ())
        offs = {n: harmonics.nearest_note(base * n)[1] for n in numbers}
        worst = max(numbers, key=lambda n: abs(offs[n]))
        listed = "; ".join(trf("el {n}º, {cents}", n=n, cents=f"{offs[n]:+.1f}")
                           for n in numbers)
        text = trf("En centésimas de semitono respecto de la tecla más "
                   "cercana: {listed}. El {worst}º no tiene ninguna tecla "
                   "cerca.", listed=listed, worst=worst)
        return str(worst), [Remark(text, severity="bien")]
    return "", []


def grade_choice(item: Exercise, chosen: str) -> Verdict:
    """Corregir una respuesta elegida."""
    answer, explanation = _answer(item)
    result = given_reading(item) if item.kind != TONE else None
    if chosen == answer:
        return Verdict(True, explanation, result, answer)
    # La explicación de por qué no es va primero y en grave: «Bajo y Tenor
    # no es» seguido de «entre Bajo y Tenor no hay quintas paralelas» decía
    # dos veces lo mismo, y lo que importaba quedaba en gris abajo. El
    # «no es» solo queda cuando no hay nada más concreto que decir.
    remarks = _wrong_choice(item, chosen, answer)
    if remarks:
        first = remarks[0]
        remarks[0] = Remark(first.text, first.bar, first.until, first.voices,
                            "grave")
    else:
        label = next((tr(o.label) for o in item.options
                      if o.value == chosen), chosen)
        remarks = [Remark(trf("«{label}» no es.", label=label))]
    return Verdict(False, remarks, result, answer)


def grade(item: Exercise, lines: Optional[Sequence[Line_]] = None,
          chosen: str = "") -> Verdict:
    """La corrección de cualquier ejercicio."""
    if item.kind in WRITTEN:
        return grade_written(item, lines if lines is not None
                             else given_lines(item))
    return grade_choice(item, chosen)


def spectrum_for(item: Exercise) -> harmonics.Spectrum:
    """
    Lo que suena en un ejercicio de la serie armónica.

    La receta del diente de sierra ---todos los armónicos, cada uno la
    enésima parte del anterior---, que es la del gráfico del libro. En el
    de reconocer de oído suenan sólo la fundamental y el armónico que hay
    que adivinar: con los doce a la vez no se oye ninguno.
    """
    spectrum = harmonics.build("Diente de sierra", item.param("midi", 45))
    if item.rule == "partial_heard":
        number = item.param("number")
        for partial in spectrum.partials:
            if partial.number == 1:
                partial.gain = 1.0
            elif partial.number == number:
                partial.gain = 0.8
            else:
                partial.muted = True
    return spectrum


def asked_partial(item: Exercise) -> int:
    """Qué barra del gráfico es la pregunta, para marcarla. Cero: ninguna."""
    if item.rule in ("partial_hz", "partial_cents"):
        return int(item.param("number", 0))
    return 0


# ---------------------------------------------------------------------------
# Lo que este usuario lleva aprobado
# ---------------------------------------------------------------------------

def school_path() -> str:
    return os.path.join(history.base_directory(), _FILENAME)


class Progress:
    """
    Qué ejercicios están aprobados y si la graduación ya se vio.

    Mismas reglas que el resto de los registros: se guarda sólo cuando algo
    cambió, y un archivo roto o de otra versión no puede impedir que el
    programa arranque. Un ejercicio que ya no existe se olvida en silencio.

    **La graduación se marca al terminar la escena**, no al aprobar el último
    ejercicio: si el programa se cerrara en el medio, el usuario perdería
    una escena que no vuelve a ocurrir.
    """

    def __init__(self, passed: Optional[Dict[str, str]] = None,
                 graduated: str = "", path: Optional[str] = None):
        known = {item.key for item in exercises()}
        self.passed: Dict[str, str] = {k: str(v) for k, v in
                                       (passed or {}).items() if k in known}
        self.graduated = str(graduated or "")
        self.path = path

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Progress":
        target = path or school_path()
        if not os.path.exists(target):
            return cls(path=path)
        try:
            with open(target, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        # `ValueError` cubre también un byte que no es UTF-8: un archivo
        # editado en otra codificación no puede impedir que el programa abra.
        except (ValueError, OSError):
            return cls(path=path)
        if not isinstance(raw, dict):
            return cls(path=path)
        passed = raw.get("passed", {})
        if not isinstance(passed, dict):
            passed = {}
        # Sólo un texto cuenta como graduación: `str(None)` es «None», que no
        # está vacío, y la escena final no se jugaba nunca.
        graduated = raw.get("graduated", "")
        if not isinstance(graduated, str):
            graduated = ""
        return cls(passed, graduated, path=path)

    def save(self) -> None:
        target = self.path or school_path()
        try:
            with open(target, "w", encoding="utf-8") as handle:
                json.dump({"passed": self.passed, "graduated": self.graduated},
                          handle, indent=2, ensure_ascii=False)
        except OSError:
            pass          # una carpeta de sólo lectura no puede romper nada

    # -- consultas ----------------------------------------------------------

    def has(self, exercise_key: str) -> bool:
        return exercise_key in self.passed

    def lesson_done(self, item: Lesson) -> bool:
        return all(self.has(entry.key) for entry in item.exercises)

    def lesson_open(self, item: Lesson) -> bool:
        """
        ¿Se puede entrar a esta lección?

        En orden: una lección se abre cuando la anterior está aprobada
        entera. Es lo que hace que la unidad de cadencias no se pueda
        empezar sin saber qué es una quinta paralela, que es lo primero que
        la corrección de una cadencia va a mirar.
        """
        for other in lessons():
            if other.key == item.key:
                return True
            if not self.lesson_done(other):
                return False
        return False

    def unit_done(self, unit: Unit) -> bool:
        return all(self.lesson_done(item) for item in unit.lessons)

    def current(self) -> Lesson:
        """La primera lección con algo pendiente, o la última."""
        for item in lessons():
            if not self.lesson_done(item):
                return item
        return lessons()[-1]

    def counts(self) -> Tuple[int, int]:
        everything = exercises()
        return sum(1 for item in everything if self.has(item.key)), len(everything)

    def all_done(self) -> bool:
        done, total = self.counts()
        return done == total

    def graduation_due(self) -> bool:
        return self.all_done() and not self.graduated

    # -- lo que pasa ---------------------------------------------------------

    def mark_passed(self, exercise_key: str) -> bool:
        """Dar un ejercicio por aprobado. ``True`` sólo la primera vez."""
        if exercise_key in self.passed or exercise(exercise_key) is None:
            return False
        self.passed[exercise_key] = datetime.now().isoformat(timespec="seconds")
        self.save()
        return True

    def mark_graduated(self) -> bool:
        if self.graduated:
            return False
        self.graduated = datetime.now().isoformat(timespec="seconds")
        self.save()
        return True


def graduation_forced(environ=None) -> bool:
    """Si la variable de entorno pide la escena del final."""
    source = os.environ if environ is None else environ
    raw = str(source.get(FORCE_VAR, "")).strip().lower()
    return bool(raw) and raw not in ("0", "no", "off", "false")


# ---------------------------------------------------------------------------
# La graduación
# ---------------------------------------------------------------------------
#
# Tres que ya vinieron a ver al usuario, en el orden de lo que se estudió:
# Gregorio, que estaba cuando dos voces empezaron a ser dos; Bach, que
# enseñaba armonía en una escuela de verdad; y el creador, que sabe de qué
# está hecho el sonido y además sabe que esto es un programa ---y es el
# único que puede decir, sin romper nada, quién corrigió los ejercicios---.
#
# Los del sendero no vienen. Cada usuario conoce a uno solo de los tres, y
# una ceremonia que trajera a los otros dos le contaría un camino que no
# eligió.
#
# No hay objeto. El cuarto objeto lo deja la entidad, y un diploma de papel
# sería un quinto; lo que queda de la graduación es el logro y un pentagrama
# vacío donde iría el nombre, que el usuario nunca dijo.

_GRADUATION_GREGORY: Tuple[Line, ...] = (
    Line(NARRATOR, "El último ejercicio queda corregido. Nadie lo marca en "
                   "rojo."),
    Line(NARRATOR, "Muy lejos, alguien sostiene una nota sola. Otra voz se "
                   "le pone debajo, a una quinta, y la sigue."),
    Line(GREGORY, "Así empezó todo. Una voz y su sombra.", pose="canto",
         cue="reveal"),
    Line(GREGORY, "Vos empezaste por donde nosotros terminamos: por la sombra "
                  "que se suelta y camina por su cuenta.", pose="normal"),
    Line(GREGORY, "Contrario, oblicuo, directo, paralelo. Cuatro palabras. A "
                  "nosotros nos llevó cuatrocientos años poder decirlas.",
         pose="canto"),
    Line(GREGORY, "Yo no firmo nada: lo único que me atribuyen no lo escribí. "
                  "Pero puedo hacer lo que sé hacer.", pose="normal"),
    Line(GREGORY, "Que se cante el primer renglón.", pose="canto"),
    Line(NARRATOR, "La nota sola sube un grado. La de abajo la sigue, sin "
                   "soltarla."),
)

_GRADUATION_BACH: Tuple[Line, ...] = (
    Line(NARRATOR, "Un golpe seco sobre la mesa, como quien pide que se "
                   "presten los cuadernos."),
    Line(BACH, "Treinta y tres ejercicios.", pose="normal", cue="reveal"),
    Line(BACH, "En Leipzig enseñaba en la escuela de Santo Tomás. Los alumnos "
               "me traían un bajo y yo les devolvía el cuaderno con los "
               "errores señalados en el margen.", pose="gesto"),
    Line(BACH, "Todos tenían quintas paralelas la primera vez. Todos. Los que "
               "después escribieron bien no son los que no las tuvieron: son "
               "los que volvieron a traer el cuaderno.", pose="normal"),
    Line(BACH, "Aprendiste qué es cada acorde, adónde quiere ir y cómo se "
               "termina una frase: llegando, descansando, engañando o "
               "dejándola en el aire.", pose="gesto"),
    Line(BACH, "Al principio de mis partituras escribía dos letras: J. J., "
               "«Jesús, ayudame». Al final, otras tres: S. D. G.",
         pose="normal"),
    Line(BACH, "Lo que va en el medio es trabajo. El tuyo está completo.",
         pose="gesto"),
    Line(NARRATOR, "Se va sin despedirse. El clave sigue sonando un compás "
                   "más."),
)

_GRADUATION_CREATOR: Tuple[Line, ...] = (
    Line(NARRATOR, "El ventilador de la máquina se calla. Otra vez."),
    Line(CREATOR, "Llegaste al final de lo que este programa sabe enseñar.",
         pose="normal", cue="reveal"),
    Line(CREATOR, "Te debo una aclaración: ninguna corrección la escribí yo. "
                  "Las escribió el analizador, el mismo que lee a Bach.",
         pose="brazos"),
    Line(CREATOR, "No hubo ninguna trampa ni ninguna tabla de respuestas. Te "
                  "midió con la misma vara con la que mide todo lo demás.",
         pose="normal"),
    Line(CREATOR, "Y lo último que estudiaste es lo primero que existió: una "
                  "cuerda vibrando en mitades, en tercios, en cuartos. Las "
                  "quintas, las cadencias, los estilos: todo sale de esa "
                  "escalera.", pose="brazos"),
    Line(CREATOR, "Hay una costumbre vieja. Al que termina se le da un papel "
                  "con su nombre.", pose="normal"),
    Line(CREATOR, "Yo no tengo tu nombre. Nunca me lo dijiste.",
         pose="brazos"),
    Line(NARRATOR, "Donde iría el nombre hay un pentagrama vacío."),
    Line(CREATOR, "Escribí ahí lo que quieras. Ya sabés cómo.",
         pose="normal"),
    Line(CREATOR, "Dicen que las leyendas nacen. No es cierto: se escriben de "
                  "a una nota, y alguien las corrige.", pose="brazos"),
    Line(NARRATOR, "En algún lugar, alguien anota algo en una lista muy "
                   "corta."),
)

#: Las tres escenas, en orden: ``(quién, líneas, nombre, línea sobre el
#: negro)``. Se encolan juntas y se tocan de un solo pestañeo largo.
GRADUATION: Tuple[Tuple[str, Tuple[Line, ...], str, str], ...] = (
    (GREGORY, _GRADUATION_GREGORY, "Gregorio I",
     "—  el último ejercicio, corregido  —"),
    (BACH, _GRADUATION_BACH, "Johann Sebastian Bach", ""),
    (CREATOR, _GRADUATION_CREATOR, "El creador", ""),
)

#: El rótulo de arriba de todo, mientras dura la ceremonia.
GRADUATION_TITLE = "—  fin de curso  —"
