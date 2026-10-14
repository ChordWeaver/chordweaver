"""
Los dibujos de las tarjetas de la pantalla inicial.

Cada modo se distingue por una sola cosa: qué ponés vos y qué escribe el
programa. Con un párrafo y tres pasos numerados eso había que leerlo; acá
se ve. A la izquierda lo tuyo, en blanco, y a la derecha, en el color del
modo, lo que el programa escribe a partir de eso. Lo de la izquierda es
distinto en cada modo, que es lo que permite distinguirlos sin leer: fichas
de cifrado, tres opciones o una melodía sola.

Las herramientas llevan un dibujo de lo que hay adentro: los armónicos de
una nota, una partitura con el cifrado que le pone el analizador y el
recorrido de la escuelita.

No importa `app`: recibe la paleta por parámetro, igual que `staff`.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import Callable, Dict, Sequence, Tuple

from engine.i18n import tr
from staff import Engraver

#: Alto del dibujo de un modo y del de una herramienta, en píxeles, en la
#: ventana más chica. En una más alta el lienzo crece y todo lo de adentro
#: crece con él (`_scale`): la medida de base es la que entra en la mínima.
FLOW_HEIGHT = 130
TOOL_HEIGHT = 84

#: La misma progresión en los tres modos, de grave a agudo: así lo único que
#: cambia entre una tarjeta y otra es quién escribe cada cosa.
CHORDS: Tuple[Tuple[str, Tuple[int, int, int, int]], ...] = (
    ("C", (48, 55, 64, 76)), ("Am", (45, 57, 64, 76)),
    ("F", (41, 57, 65, 77)), ("G", (43, 55, 62, 74)))

#: La melodía del Armonizador: la voz de arriba de esos cuatro acordes.
MELODY = (76, 76, 77, 74)

_LETTERS = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}
_F5 = 77          # la quinta línea del pentagrama de sol
_A3 = 57          # la quinta línea del de fa


def _mix(first: str, second: str, amount: float) -> str:
    """Un color entre dos, en formato #rrggbb."""
    a = [int(first[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(second[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}"
                         for x, y in zip(a, b))


def _scale(canvas: tk.Canvas, base: int) -> float:
    """Cuánto más alto que la medida de base es el lienzo."""
    try:
        return max(1.0, float(canvas.cget("height")) / base)
    except (tk.TclError, ValueError):
        return 1.0


def _step(pitch: int) -> int:
    """La altura en grados de la escala, para ubicarla en el pentagrama."""
    return _LETTERS[pitch % 12] + 7 * (pitch // 12)


def _lines(canvas: tk.Canvas, x0: float, x1: float, top: float,
           space: float, colour: str) -> None:
    for line in range(5):
        y = top + line * space
        canvas.create_line(x0, y, x1, y, fill=colour)


def _system(canvas: tk.Canvas, x0: float, x1: float, top: float,
            space: float, voices: Sequence[str], symbols: str,
            colours: Dict[str, str]) -> None:
    """Un sistema de dos pentagramas con los cuatro acordes y su cifrado."""
    engraver = Engraver(canvas, space)
    line = colours["faint"]
    bass_top = top + 7 * space
    bottom = bass_top + 4 * space
    _lines(canvas, x0 + 8, x1, top, space, line)
    _lines(canvas, x0 + 8, x1, bass_top, space, line)
    engraver.brace(x0, top, bottom, line)
    engraver.clef(x0 + 11, top + 3 * space, True, line)
    engraver.clef(x0 + 11, bass_top + space, False, line)
    canvas.create_line(x0 + 8, top, x0 + 8, bottom, fill=line)
    canvas.create_line(x1, top, x1, bottom, fill=line)
    left = x0 + 8 + 3.4 * space
    column = (x1 - left) / len(CHORDS)
    for position, (name, pitches) in enumerate(CHORDS):
        x = left + column * (position + 0.5)
        canvas.create_text(x, top - 2.6 * space, text=name, fill=symbols,
                           font=colours["font_symbol"])
        for voice, pitch in enumerate(pitches):
            if voice >= 2:
                y = top + (_step(_F5) - _step(pitch)) * space / 2
            else:
                y = bass_top + (_step(_A3) - _step(pitch)) * space / 2
            engraver.head(x, y, 4.0, voices[voice])


def _chip(canvas: tk.Canvas, box: Tuple[float, float, float, float],
          text: str, colours: Dict[str, str], font) -> None:
    """Una ficha redondeada con su texto, como las de la pantalla de acordes."""
    x0, y0, x1, y1 = box
    r = 7
    # Cada punto de las rectas va dos veces: con el polígono suavizado, un
    # punto suelto se redondea y el borde salía con una muesca.
    points = [x0 + r, y0, x0 + r, y0, x1 - r, y0, x1 - r, y0, x1, y0,
              x1, y0 + r, x1, y0 + r, x1, y1 - r, x1, y1 - r, x1, y1,
              x1 - r, y1, x1 - r, y1, x0 + r, y1, x0 + r, y1, x0, y1,
              x0, y1 - r, x0, y1 - r, x0, y0 + r, x0, y0 + r, x0, y0]
    canvas.create_polygon(points, smooth=True, outline=colours["faint"],
                          fill=colours["chip"], width=1)
    canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=text,
                       fill=colours["text"], font=font)


def draw_flow(canvas: tk.Canvas, key: str, accent: str,
              colours: Dict[str, str], width: int) -> None:
    """
    Lo que ponés vos, una flecha, y lo que escribe el programa.

    `colours` trae `text` (lo tuyo), `muted`, `faint` (líneas), `chip` (el
    fondo de una ficha) y las fuentes `font_caption`, `font_symbol`,
    `font_chip` y `font_option`.
    """
    k = _scale(canvas, FLOW_HEIGHT)
    mine = colours["text"]
    split = int(width * 0.34)
    start = split + 34
    middle = 78 * k
    for x, text in ((2, tr("VOS")), (start, tr("EL PROGRAMA"))):
        canvas.create_text(x, 10, text=text, anchor="w",
                           fill=colours["muted"], font=colours["font_caption"])
    canvas.create_line(split + 6, middle, split + 26, middle,
                       fill=colours["muted"], width=2, arrow="last",
                       arrowshape=(9, 10, 4))
    if key == "manual":
        # Las fichas de cifrado: lo único que pone quien usa el Organizador.
        chip_w = (split - 10) / 2
        chip_h = 26 * k
        for position, (name, _pitches) in enumerate(CHORDS):
            row, column = divmod(position, 2)
            x0 = 2 + column * (chip_w + 6)
            y0 = middle - chip_h - 4 * k + row * (chip_h + 8 * k)
            _chip(canvas, (x0, y0, x0 + chip_w, y0 + chip_h), name, colours,
                  colours["font_chip"])
        _system(canvas, start, width - 4, 42 * k, 7.0 * k, [accent] * 4,
                mine, colours)
    elif key == "random":
        # Tres opciones y nada más: el cifrado también lo escribe el
        # programa, y por eso va en su color.
        options = (tr("Do mayor"), tr("8 compases"), tr("con préstamos"))
        option_h = 24 * k
        top = middle - (3 * option_h + 2 * 7 * k) / 2
        for position, text in enumerate(options):
            y0 = top + position * (option_h + 7 * k)
            _chip(canvas, (2, y0, split - 2, y0 + option_h), text, colours,
                  colours["font_option"])
        _system(canvas, start, width - 4, 42 * k, 7.0 * k, [accent] * 4,
                accent, colours)
    else:
        # Una melodía sola, que vuelve arriba en blanco: el programa no la
        # toca y escribe todo lo demás.
        space = 6.0 * k
        engraver = Engraver(canvas, space)
        top = middle - 2 * space
        _lines(canvas, 2, split - 2, top, space, colours["faint"])
        engraver.clef(4, top + 3 * space, True, colours["faint"])
        left = 4 + 3.4 * space
        column = (split - 2 - left) / len(MELODY)
        for position, pitch in enumerate(MELODY):
            engraver.head(left + column * (position + 0.5),
                          top + (_step(_F5) - _step(pitch)) * space / 2, 4.0,
                          mine)
        _system(canvas, start, width - 4, 42 * k, 7.0 * k,
                [accent, accent, accent, mine], accent, colours)


def _harmonics(canvas: tk.Canvas, accent: str, colours: Dict[str, str],
               width: int) -> None:
    """Los primeros doce armónicos de una nota, cada vez más débiles."""
    base = TOOL_HEIGHT * _scale(canvas, TOOL_HEIGHT) - 14
    count = 12
    gap = (width - 16) / count
    for number in range(1, count + 1):
        height = (base - 8) / number ** 0.8
        x = 8 + (number - 1) * gap + gap * 0.2
        fill = accent if number == 1 else _mix(colours["card"], accent, 0.75)
        canvas.create_rectangle(x, base - height, x + gap * 0.6, base,
                                fill=fill, outline="")
        canvas.create_text(x + gap * 0.3, base + 9, text=str(number),
                           fill=colours["muted"], font=colours["font_tiny"])


def _analysis(canvas: tk.Canvas, accent: str, colours: Dict[str, str],
              width: int) -> None:
    """Notas escritas en blanco y, en color, lo que el analizador les pone."""
    k = _scale(canvas, TOOL_HEIGHT)
    space = 7.0 * k
    engraver = Engraver(canvas, space)
    top = 20 * k
    _lines(canvas, 4, width - 4, top, space, colours["faint"])
    engraver.clef(6, top + 3 * space, True, colours["faint"])
    chords = (("C", "I", (60, 64, 67)), ("Am", "vi", (60, 64, 69)),
              ("Dm7", "ii7", (62, 65, 72)), ("G7", "V7", (59, 65, 67)),
              ("C", "I", (60, 64, 72)))
    left = 6 + 3.4 * space
    column = (width - 4 - left) / len(chords)
    head = engraver.head_width(4.0)
    for position, (name, roman, pitches) in enumerate(chords):
        x = left + column * (position + 0.5)
        canvas.create_text(x, top - 12 * k, text=name, fill=accent,
                           font=colours["font_symbol"])
        below = None
        for pitch in sorted(pitches):
            if pitch <= 60:
                # El do central lleva su línea adicional.
                canvas.create_line(x - head * 0.8, top + 5 * space,
                                   x + head * 0.8, top + 5 * space,
                                   fill=colours["faint"])
            # Dos notas a distancia de segunda no caben una encima de la
            # otra: la de arriba se corre al costado, como se escribe.
            shift = (head if below is not None
                     and _step(pitch) - _step(below) == 1 else 0.0)
            engraver.head(x + shift, top + (_step(_F5) - _step(pitch))
                          * space / 2, 4.0, colours["text"])
            below = pitch if not shift else None
        canvas.create_text(x, top + 52 * k, text=roman, fill=accent,
                           font=colours["font_roman"])


def _check(canvas: tk.Canvas, x: float, y: float, radius: float,
           colour: str) -> None:
    """Una tilde dibujada, centrada en (x, y) dentro de un círculo."""
    canvas.create_line(x - 0.45 * radius, y + 0.02 * radius,
                       x - 0.12 * radius, y + 0.36 * radius,
                       x + 0.48 * radius, y - 0.34 * radius,
                       fill=colour, width=max(2.0, radius * 0.24),
                       capstyle="round", joinstyle="round")


def _star(canvas: tk.Canvas, x: float, y: float, radius: float,
          colour: str) -> None:
    """
    Una estrella de cinco puntas centrada de verdad en (x, y).

    Dibujada y no escrita: el carácter de estrella de una fuente no cae en
    el centro de su renglón, y al lado de la línea del recorrido se veía
    corrido para abajo. Una estrella tiene la punta de arriba más lejos del
    centro que las de abajo, así que se la baja lo justo para que lo
    centrado sea su contorno.
    """
    inner = radius * 0.45
    shift = radius * (1 - math.cos(math.radians(36))) / 2
    points = []
    for corner in range(10):
        angle = math.radians(-90 + corner * 36)
        reach = radius if corner % 2 == 0 else inner
        points += [x + reach * math.cos(angle),
                   y + shift + reach * math.sin(angle)]
    canvas.create_polygon(points, fill=colour, outline="")


def _school(canvas: tk.Canvas, accent: str, colours: Dict[str, str],
            width: int) -> None:
    """El recorrido de las ocho unidades: dos aprobadas y la tercera en curso."""
    k = _scale(canvas, TOOL_HEIGHT)
    y = (TOOL_HEIGHT * k) / 2 - 4 * k
    stations = 8
    x0, x1 = 36, width - 68
    gap = (x1 - x0) / (stations - 1)
    radii = [8 * k, 8 * k, 10 * k] + [6 * k] * 5
    # Los tramos van de borde a borde y los círculos quedan huecos: así lo
    # que se ve adentro es el fondo de la tarjeta también cuando la tarjeta
    # cambia de color con el mouse encima.
    for station in range(stations - 1):
        done = station < 2
        canvas.create_line(x0 + station * gap + radii[station], y,
                           x0 + (station + 1) * gap - radii[station + 1], y,
                           fill=accent if done else colours["faint"],
                           width=3 if done else 2)
    for station in range(stations):
        x = x0 + station * gap
        radius = radii[station]
        box = (x - radius, y - radius, x + radius, y + radius)
        if station < 2:
            canvas.create_oval(*box, fill=accent, outline="")
            _check(canvas, x, y, radius, colours["surface"])
        elif station == 2:
            canvas.create_oval(*box, outline=accent, width=3)
        else:
            canvas.create_oval(*box, outline=colours["faint"], width=2)
    star = width - 24
    canvas.create_line(x1 + radii[-1], y, star - 12 * k, y,
                       fill=colours["faint"], width=2, dash=(3, 3))
    _star(canvas, star, y, 8 * k, colours["gold"])
    canvas.create_text(x0 + 2 * gap, y + radii[2] + 12 * k,
                       text=tr("Oído"), fill=accent,
                       font=colours["font_caption"])


#: Qué dibujo lleva cada herramienta, por su clave.
TOOL_PICTURES: Dict[str, Callable[[tk.Canvas, str, Dict[str, str], int],
                                  None]] = {
    "lab": _harmonics,
    "analysis": _analysis,
    "school": _school,
}


def draw_tool(canvas: tk.Canvas, key: str, accent: str,
              colours: Dict[str, str], width: int) -> None:
    """El dibujo de una herramienta; nada si la clave no tiene uno."""
    picture = TOOL_PICTURES.get(key)
    if picture is not None:
        picture(canvas, accent, colours, width)
