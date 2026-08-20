# -*- coding: utf-8 -*-
#
# Tipos de Cython para `fitness.py`. **No es código que corra.**
#
# Este archivo lo lee `build_engine.py` al compilar y nadie más: Python lo
# ignora por completo, y sin él `fitness.py` sigue siendo el mismo módulo de
# librería estándar de siempre. Los tipos van acá justamente para que el
# `.py` no se entere de que existe Cython --- se puede leer, editar y correr
# sin tener nada instalado, que es la promesa del motor.
#
# Sólo están declaradas las funciones que la búsqueda pisa millones de veces
# por corrida. El resto del archivo compila sin tipos, como estaba.
#
# Tres reglas que hay que respetar al tocar esto:
#
# 1. **Una firma de acá tiene que coincidir con la del `.py`.** Si no, la
#    compilación falla --- que es lo que uno quiere --- pero el `.py` se
#    queda andando, así que el error se ve recién al compilar.
# 2. **`cdef` esconde la función de Python.** Las ocho de abajo son privadas
#    de `fitness.py` y nadie las importa; verificado con grep antes de
#    declararlas así. `_context_at` NO puede ser `cdef` porque
#    `engine/flourish.py` la usa, y por eso va `cpdef`.
# 3. **Una función con un generador adentro no se puede declarar acá.** Un
#    `sum(1 for i in ...)` es un closure, y Cython no los soporta dentro de
#    una `cpdef` ni de una `cdef`: la compilación se cae con "closures inside
#    cpdef functions not yet supported". Por eso faltan cuatro que son de las
#    más calientes que hay --- `range_violations`, `has_melodic_tritone`,
#    `_unison_pairs` y `_crossing_count`, todas de un `sum(...)` o un
#    `any(...)` de una línea. Igual se compilan, sólo que sin tipos.
#    Reescribirlas como bucles explícitos las haría declarables, pero eso es
#    tocar el `.py` para complacer al compilador, que es justamente lo que
#    este archivo existe para no hacer.
#
# Sobre los tipos elegidos: los enteros van en `long` sólo donde el valor sale
# de una altura MIDI o de contar cosas --- ahí no hay forma de que aparezca
# un float. Donde la cuenta mezcla un campo del perfil de género
# (`max_upper_spacing`, `edge_margin`, `final_ideal_span`) el acumulador va
# en `double`: hoy los tres son `int` en los cuatro perfiles y no los toca ni
# la interfaz ni el CLI, pero si alguna vez uno pasa a ser fraccionario un
# acumulador entero lo truncaría **en silencio** y la música cambiaría sin
# que fallara ningún test. Las tres se multiplican por un peso float en el
# evaluador, así que en `double` dan exactamente lo mismo y no queda filo.

cimport cython


# -- detección de intervalos: sólo alturas MIDI, todo entero ----------------

@cython.locals(interval_before=long, interval_after=long,
               motion_a=long, motion_b=long, similar_motion=bint,
               is_fifth=bint, is_octave=bint)
cpdef parallel_interval_violation(previous, current, long voice_a, long voice_b)

@cython.locals(interval_after=long, motion_low=long, motion_high=long)
cpdef bint direct_perfect_violation(previous, current, long lowest, long highest)

@cython.locals(count=long, i=long, j=long)
cpdef bint has_harmonic_tritone(chord_pitches)


# -- los ayudantes privados del evaluador ----------------------------------

@cython.locals(excess=double, i=long, gap=long)
cdef double _spacing_excess(pitches, profile)

@cython.locals(strain=long, i=long, pitch=long)
cdef double _tessitura_strain(pitches, voices, profile)

@cython.locals(middle=long)
cdef long _bass_register_excess(pitches, voices)

cdef double _final_span_excess(pitches, profile)

@cython.locals(count=long, i=long, j=long)
cdef long _contrary_pairs(movements)

cpdef _context_at(settings, long index)

cdef bint _same_harmony(settings, long first, long second)
