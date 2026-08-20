# -*- coding: utf-8 -*-
#
# Tipos de Cython para `style.py`. Ver la cabecera de `fitness.pxd`: valen
# las mismas tres reglas y el mismo motivo para que esto viva aparte del
# `.py`.
#
# Acá están declaradas las reglas idiomáticas que el evaluador llama **una
# vez por acorde y una por transición**, que son las que aparecen en el
# perfil con más de un millón de llamadas por corrida. Todas van `cpdef`
# --- nunca `cdef` --- porque `style.py` es la biblioteca de reglas del
# motor: `fitness.py` las importa por nombre, `audit.py` las mide sueltas y
# `tests.py` las prueba una por una. Esconderlas de Python rompería las tres
# cosas de una.
#
# Los pesos son floats por definición --- salen de los perfiles de género,
# donde se calibran a mano --- así que todo lo que los toca va en `double`.
# Los índices y las alturas van en `long`. Nada mezcla las dos cosas de un
# modo que pueda truncar: el patrón de estas funciones es siempre acumular
# `peso * (cuenta entera)`.
#
# Lo que **no** está acá y podría parecer que falta: `melodic_interval_penalty`
# recibe `max_leap: Optional[int]`, que llega en `None` en los géneros que no
# lo usan. Un `long` no puede ser None, y tiparlo obligaría a que el estilo
# gregoriano y el jazz pasaran un número inventado. Y `common_tone_reward` es
# un `sum(1 for ...)` de una línea: un generador es un closure, y Cython no
# los soporta dentro de una `cpdef`. Ver la regla 3 en `fitness.pxd`.

cimport cython


@cython.locals(counts=dict, pitch=long, pc=long, cost=double)
cpdef double doubling_penalty(pitches, context, double third_weight,
                              double leading_tone_weight,
                              double seventh_weight)

# `leading` no se tipa: es `context.leading_tone_pc`, un `Optional[int]`.
@cython.locals(cost=double, index=long, before=long, after=long,
               motion=long, pc=long)
cpdef double tendency_tone_penalty(previous, current, context,
                                   double seventh_weight,
                                   double leading_tone_weight)

@cython.locals(reward=double, index=long, before=long, after=long)
cpdef double guide_tone_reward(previous, current, previous_context,
                               current_context, double weight)

@cython.locals(bass_motion=long, reward=double, index=long, motion=long)
cpdef double bass_contrary_reward(previous, current, double weight)

@cython.locals(cost=double, index=long, leap=long, answer=long)
cpdef double leap_compensation_penalty(before_previous, previous, current,
                                       long leap_threshold, double weight)
