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

import base64
import io
import math
import tkinter as tk
from typing import Callable, Dict, Optional, Sequence, Tuple

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


#: Dónde está uno en la escuelita: cuánto de cada unidad está aprobado (de 0
#: a 1), cuál es la que sigue (None si ya no queda ninguna), su nombre corto
#: y si ya se graduó. Sin dato se dibuja el ejemplo de siempre.
SchoolState = Tuple[Tuple[float, ...], Optional[int], str, bool]

SCHOOL_EXAMPLE: SchoolState = ((1.0, 1.0) + (0.0,) * 6, 2, "Oído", False)

#: Cuántas veces más grande se dibuja el recorrido antes de achicarlo. Los
#: óvalos de un lienzo de Tk no tienen suavizado y en la tarjeta se veían
#: pixelados; dibujado al cuádruple y reducido, el borde queda suave.
_SUPERSAMPLE = 4


def _rgb(colour: str) -> Tuple[int, int, int]:
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


def school_image(width: int, height: int, k: float, accent: str,
                 colours: Dict[str, str], state: SchoolState):
    """El recorrido de las ocho unidades, como imagen con transparencia.

    Va aparte del lienzo para poder probarlo sin abrir una ventana. Lo de
    adentro de los círculos es transparente: se ve el fondo de la tarjeta,
    también cuando cambia de color con el mouse encima.
    """
    from PIL import Image, ImageDraw

    share, current, _label, graduated = state
    done = [part >= 1.0 for part in share]
    stations = len(share)
    n = _SUPERSAMPLE
    image = Image.new("RGBA", (width * n, height * n), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    lit, faint = _rgb(accent) + (255,), _rgb(colours["faint"]) + (255,)
    gold, surface = _rgb(colours["gold"]) + (255,), _rgb(colours["surface"]) + (255,)
    y = ((TOOL_HEIGHT * k) / 2 - 4 * k) * n
    x0, x1 = 36 * n, (width - 68) * n
    gap = (x1 - x0) / (stations - 1)
    radii = [(10 if i == current else 8 if done[i] else 6) * k * n
             for i in range(stations)]
    for station in range(stations - 1):
        reached = done[station] and (done[station + 1] or station + 1 == current)
        draw.line((x0 + station * gap + radii[station], y,
                   x0 + (station + 1) * gap - radii[station + 1], y),
                  fill=lit if reached else faint, width=int((3 if reached else 2) * n))
    for station in range(stations):
        x, r = x0 + station * gap, radii[station]
        box = (x - r, y - r, x + r, y + r)
        if done[station]:
            draw.ellipse(box, fill=lit)
            draw.line(((x - 0.45 * r, y + 0.02 * r), (x - 0.12 * r, y + 0.36 * r),
                       (x + 0.48 * r, y - 0.34 * r)),
                      fill=surface, width=int(max(2.0 * n, r * 0.24)),
                      joint="curve")
        else:
            # Lo aprobado a medias es un arco del color de la escuelita sobre
            # el aro apagado, desde arriba y en el sentido del reloj. La que
            # sigue va más grande; si todavía no tiene nada, el aro entero
            # encendido, como siempre.
            thick = int((3 if station == current else 2) * n)
            if station == current and share[station] <= 0:
                draw.ellipse(box, outline=lit, width=thick)
            else:
                draw.ellipse(box, outline=faint, width=thick)
            if share[station] > 0:
                draw.arc(box, -90, -90 + 360 * share[station], fill=lit,
                         width=int(3 * n))
    # La línea de puntos hasta la estrella, y la estrella: dorada siempre,
    # más grande y con el tramo encendido cuando ya no queda unidad.
    star_x = (width - 24) * n
    finished = current is None
    start = x1 + radii[-1]
    end = star_x - 12 * k * n
    dash = 3 * n
    position = start
    while position < end:
        draw.line((position, y, min(end, position + dash), y),
                  fill=lit if finished else faint, width=int(2 * n))
        position += 2 * dash
    radius = (10 if finished else 8) * k * n
    inner = radius * 0.45
    # La punta de arriba está más lejos del centro que las de abajo: se la
    # baja lo justo para que lo centrado en la línea sea el contorno.
    shift = radius * (1 - math.cos(math.radians(36))) / 2
    points = []
    for corner in range(10):
        angle = math.radians(-90 + corner * 36)
        reach = radius if corner % 2 == 0 else inner
        points.append((star_x + reach * math.cos(angle),
                       y + shift + reach * math.sin(angle)))
    draw.polygon(points, fill=gold)
    if graduated:
        ring = radius * 1.55
        draw.ellipse((star_x - ring, y - ring, star_x + ring, y + ring),
                     outline=gold, width=int(2 * n))
    return image.resize((width, height), Image.LANCZOS)


def _school(canvas: tk.Canvas, accent: str, colours: Dict[str, str],
            width: int, state: Optional[SchoolState] = None) -> None:
    """El recorrido de las ocho unidades, con la que toca ahora marcada."""
    state = state or SCHOOL_EXAMPLE
    k = _scale(canvas, TOOL_HEIGHT)
    height = int(round(TOOL_HEIGHT * k))
    try:
        picture = school_image(width, height, k, accent, colours, state)
    except Exception:                                       # noqa: BLE001
        return
    buffer = io.BytesIO()
    picture.save(buffer, "PNG")
    # `tk.PhotoImage` y no el de PIL: el de tkinter tiene apagado su
    # finalizador (ver `app._keep_tk_off_the_worker_thread`) y el de PIL
    # borraría la imagen desde el hilo que pase a recolectar. Por lo mismo
    # la anterior se borra a mano, acá, en el hilo de la ventana.
    old = getattr(canvas, "_school_photo", None)
    photo = tk.PhotoImage(master=canvas,
                          data=base64.b64encode(buffer.getvalue()))
    canvas.create_image(0, 0, anchor="nw", image=photo)
    canvas._school_photo = photo
    if old is not None:
        try:
            canvas.tk.call("image", "delete", old.name)
        except tk.TclError:
            pass
    share, current, label, graduated = state
    stations = len(share)
    x0, x1 = 36, width - 68
    gap = (x1 - x0) / (stations - 1)
    y = (TOOL_HEIGHT * k) / 2 - 4 * k
    if current is None:
        x, text = width - 24, ("Graduación" if not graduated else "")
        below = 10 * k
    else:
        x, text, below = x0 + current * gap, label, 10 * k
    if text:
        canvas.create_text(x, y + below + 12 * k, text=tr(text), fill=accent,
                           font=colours["font_caption"])


#: Qué dibujo lleva cada herramienta, por su clave.
TOOL_PICTURES: Dict[str, Callable[..., None]] = {
    "lab": _harmonics,
    "analysis": _analysis,
    "school": _school,
}


def draw_tool(canvas: tk.Canvas, key: str, accent: str,
              colours: Dict[str, str], width: int, state=None) -> None:
    """El dibujo de una herramienta; nada si la clave no tiene uno.

    `state` es lo que el dibujo necesita saber del usuario: por ahora sólo
    la escuelita, que dibuja dónde anda (`SchoolState`).
    """
    picture = TOOL_PICTURES.get(key)
    if picture is None:
        return
    if state is not None:
        picture(canvas, accent, colours, width, state)
    else:
        picture(canvas, accent, colours, width)
