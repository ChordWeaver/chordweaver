# -*- coding: utf-8 -*-
"""
Las escenas del modo historia: el velo, el personaje y el diálogo.

Es el tercer archivo con interfaz del proyecto, y está aparte por la misma
razón que ``staff.py``: es un widget entero, autosuficiente, que ``app.py``
abre y cierra sin saber cómo está hecho por dentro. No importa nada de
``app`` --- la dependencia va en una sola dirección --- y su paleta es
propia, porque una escena no se pinta con los colores de un formulario.

Los personajes son imágenes
---------------------------
Están en ``assets/story`` como PNG recortados con transparencia, varios por
personaje, y la escena elige cuál mostrar según lo que se esté diciendo. Se
cargan con el ``PhotoImage`` de Tk, que desde 8.6 lee PNG con canal alfa y lo
compone contra lo que haya debajo; no hace falta ninguna librería de imágenes
para correr el programa. Los recortes se prepararon una sola vez, aparte.

Tk sólo sabe escalar una imagen por factores enteros (``subsample`` y
``zoom``), y eso decidió toda la puesta en escena: en vez de un acercamiento
continuo, el personaje aparece **a lo lejos y a oscuras** y se acerca de
golpe, en dos saltos, aprovechando un parpadeo para cambiar de lugar. La
limitación terminó siendo mejor que lo que se quería hacer: no se sabe quién
es hasta que está encima.

Todo sobre un solo lienzo
-------------------------
El fondo, el personaje, el humo y el cuadro de diálogo son elementos de un
único ``tk.Canvas`` que tapa la ventana. Mover un elemento de canvas no
obliga a Tk a recalcular ningún layout, que es exactamente el problema que
tiene animar widgets --- el mismo motivo por el que en ``app.py`` sólo se
anima color y posición de cosas ``place``-adas.
"""

from __future__ import annotations

import math
import os
import random
import tkinter as tk
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from engine import ambience, history, story, visitors

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------

GOLD = "#E8C97A"
GOLD_DEEP = "#C7982F"
GOLD_PALE = "#F6EBC0"
INK = "#E6E8EB"
MUTED = "#98A0AC"
BOX = "#15171C"
BOX_EDGE = "#3A3E48"
BLACK = "#000000"

#: El cielo de cada escena, de arriba hacia abajo.
SKIES = {
    "valley": ("#241E28", "#3A2A2E", "#54382E", "#2A1F1C"),
    "room": ("#16181D", "#1D2029", "#242833", "#191B21"),
    "heaven": ("#1A1C22", "#2A2C38", "#4A4433", "#6B5C36"),
    "ashes": ("#1A0F0F", "#2E1512", "#4A1D14", "#25120F"),
    # El de las visitas. No es un lugar: es la misma habitación de siempre
    # con la luz apagada, y por eso no tiene ni horizonte ni cerros ni luna.
    "void": ("#0B0C10", "#0A0B0E", "#08090C", "#050507"),
    # El cruce de caminos de la visión. Noche abierta, sin luna.
    "crossroads": ("#0A0C12", "#101422", "#161B2A", "#0B0D14"),
}

#: El color que se ve por debajo del negro de una visita.
#:
#: Tk no tiene transparencia: un lienzo tapa lo que hay abajo y no hay forma
#: de que no lo tape. Lo que sí se puede es pintar el negro **tramado** ---
#: uno de cada cuatro píxeles queda sin pintar --- encima del color con el
#: que está pintado el programa, y el efecto es exactamente el de un velo
#: negro con un poco de transparencia por delante de la ventana. Es el mismo
#: truco que el velo de las animaciones de logros, que también es un color
#: plano y no una capa translúcida.
VOID_UNDER = "#14161B"

#: Quién habla, con qué letra y de qué color. Las tres tipografías vienen
#: con Windows y son deliberadamente distintas entre sí: el señor habla en
#: una serifa vieja e inclinada, el guitarrista en una humanista relajada y
#: la voz divina en una serifa de libro. Si alguna faltara, Tk cae en la
#: fuente por defecto y el texto se lee igual.
#:
#: Ninguno tiene nombre. El nombre es la última cosa que entrega el relato, y
#: ponerlo en el cartelito desde la primera línea sería regalarlo.
SPEAKERS: Dict[str, dict] = {
    story.DEVIL: dict(name="? ? ?",
                      font=("Palatino Linotype", 16, "italic"),
                      colour="#E0B978", blip="blip_devil", speed=1.5),
    story.DJANGO: dict(name="? ? ?",
                       font=("Candara", 17), colour="#C7A0EA",
                       blip="blip_django", speed=1.9),
    story.JESUS: dict(name="? ? ?",
                      font=("Constantia", 17), colour="#F3E7C4",
                      blip="blip_jesus", speed=1.3),
    story.NARRATOR: dict(name="",
                         font=("Segoe UI", 14, "italic"), colour=MUTED,
                         blip="blip_narrator", speed=2.1),
    # Las visitas. Bach habla en una serifa de imprenta y bastante rápido
    # --- tiene una cantata que entregar ---; Gregorio en una serifa de libro
    # y despacio; y la entidad en la única tipografía de ancho fijo del
    # programa, que es lo que hace que no se lea como alguien hablando.
    #
    # **Todas tienen que venir con Windows.** Bach hablaba en Book Antiqua,
    # que no viene: viene con Office. Donde no está, Tk no avisa nada ---
    # cae en la fuente por defecto, que es una sans mínima --- así que el
    # personaje más formal del programa hablaba con la peor letra de todas y
    # no había ningún error en ninguna parte.
    visitors.BACH: dict(name="? ? ?",
                        font=("Cambria", 17), colour="#DCC79B",
                        blip="blip_bach", speed=1.8),
    visitors.GREGORY: dict(name="? ? ?",
                           font=("Georgia", 16), colour="#E6DFC6",
                           blip="blip_gregory", speed=1.4),
    visitors.WATCHER: dict(name="? ? ?",
                           font=("Consolas", 15), colour="#98A6B8",
                           blip="blip_watcher", speed=1.1),
}

#: Poses que además suenan. La única, por ahora, es la cara con la que el
#: señor recibe un «no»: el tritono --- *diabolus in musica* --- entra con
#: ella. Es el chiste que el programa entero venía preparando, y es la misma
#: disonancia que el libro explica dos capítulos antes.
POSE_SOUNDS: Dict[str, str] = {"enojado": "tritone"}

#: Milisegundos por cuadro.
FRAME = 33


def mix(colour_a: str, colour_b: str, position: float) -> str:
    """Color intermedio entre dos hex. Igual que el de ``app.py``."""
    position = 0.0 if position < 0.0 else 1.0 if position > 1.0 else position
    left = (int(colour_a[1:3], 16), int(colour_a[3:5], 16), int(colour_a[5:7], 16))
    right = (int(colour_b[1:3], 16), int(colour_b[3:5], 16), int(colour_b[5:7], 16))
    return "#%02X%02X%02X" % tuple(
        int(round(a + (b - a) * position)) for a, b in zip(left, right)
    )


# ---------------------------------------------------------------------------
# Los personajes
# ---------------------------------------------------------------------------

def assets_directory() -> str:
    """Dónde están los recortes. Al lado del programa, como todo lo demás."""
    # `program_directory` y no `base_directory`: los recortes vienen con el
    # programa y no son datos del usuario, así que no los mueve
    # `CHORDWEAVER_DATA_DIR`. Ver el porqué en esa función.
    return os.path.join(history.program_directory(), "assets", "story")


#: Las poses de cada personaje. ``oscuro`` es la silueta que se usa mientras
#: está lejos: se lo ve venir pero no se sabe quién es.
POSES: Dict[str, Dict[str, str]] = {
    story.DEVIL: {"normal": "devil-normal.png",
                  "siniestro": "devil-siniestro.png",
                  "enojado": "devil-enojado.png",
                  "perfil": "devil-perfil.png",
                  "oscuro": "devil-oscuro.png"},
    story.DJANGO: {"normal": "django-normal.png",
                   "feliz": "django-feliz2.png",
                   "quieto": "django-feliz.png",
                   "guitarra": "django-guitarra.png",
                   "oscuro": "django-oscuro.png"},
    story.JESUS: {"normal": "jesus-normal.png",
                  "feliz": "jesus-feliz.png",
                  "sereno": "jesus-sereno.png",
                  "oscuro": "jesus-oscuro.png"},
    visitors.BACH: {"normal": "bach-normal.png",
                    "gesto": "bach-gesto.png",
                    "oscuro": "bach-oscuro.png"},
    visitors.GREGORY: {"normal": "gregory-normal.png",
                       "canto": "gregory-canto.png",
                       "oscuro": "gregory-oscuro.png"},
    # La entidad no tiene más que una pose, y no le falta ninguna: lo único
    # que se ve de ella es la silueta encapuchada. Su recorte ya está a
    # oscuras, así que la pose de lejos es la misma.
    visitors.WATCHER: {"normal": "watcher-normal.png",
                       "oscuro": "watcher-normal.png"},
    # El de la visión. No habla, así que no tiene cara: tiene un frente y una
    # espalda. **Los dos recortes vienen con luz de noche** --- apagados y
    # con un tinte azul, que es de lo que está hecha la luz de la luna --- en
    # vez de irse apagando a medida que se aleja: alguien parado en un camino
    # a la madrugada no se ilumina como si fuera mediodía, y oscurecerlo de a
    # poco hacía que la noche pareciera caer en veinte segundos.
    visitors.ROBERT: {"normal": "robert-frente.png",
                      "frente": "robert-frente.png",
                      "espalda": "robert-espalda.png"},
}

#: Alto al que están guardados los recortes.
#:
#: **Los tres personajes miden lo mismo, y el recorte va ajustado a la
#: figura.** No es una convención decorativa: el retrato se ancla por los
#: pies, así que un archivo con transparencia de sobra abajo deja al
#: personaje flotando, y una figura que no llene el alto se ve más chica que
#: las demás. Media docena de poses estaban guardadas enteras --- la imagen
#: de 1408x768 de la que salieron, con el personaje adentro --- y el efecto
#: era que se achicaba y subía al cambiar de pose en la mitad de una frase.
#: Una pose nueva va recortada al alfa y llevada a este alto antes de
#: dejarla en la carpeta.
ASSET_HEIGHT = 720

#: Los tres planos, como divisor entero del recorte. Enteros porque es lo
#: único que Tk sabe hacer, y de ahí sale que el acercamiento sea a saltos.
STEPS = (4, 2, 1)

#: Cuánto se desenfoca cada plano en el acercamiento. De lejos la figura es
#: un borrón, al segundo salto se adivina, y encima está nítida.
BLURS = (4, 2, 1)

#: Caché de imágenes por (archivo, divisor, desenfoque). Un `PhotoImage`
#: cuesta memoria y tiempo de carga, y la misma pose se pide muchas veces en
#: una escena.
_IMAGES: Dict[Tuple[str, int, int], "tk.PhotoImage"] = {}


def load_pose(speaker: str, pose: str, step: int, blur: int = 1):
    """
    Una pose, al tamaño de un plano. ``None`` si el archivo no está.

    ``blur`` desenfoca sin cambiar el tamaño: se achica de más y se agranda
    de vuelta, así que la figura queda hecha de bloques. Tk no sabe filtrar
    una imagen --- sólo escalarla por factores enteros --- y perder
    resolución es la única forma de perder detalle que tiene. A dos planos
    de distancia alcanza y sobra: lo que se ve venir es una figura, y recién
    de cerca se sabe quién es.
    """
    table = POSES.get(speaker, {})
    name = table.get(pose) or table.get("normal")
    if not name:
        return None
    key = (name, step, blur)
    if key in _IMAGES:
        return _IMAGES[key]
    try:
        image = tk.PhotoImage(file=os.path.join(assets_directory(), name))
        if step * blur > 1:
            image = image.subsample(step * blur)
        if blur > 1:
            image = image.zoom(blur)
    except tk.TclError:
        return None
    _IMAGES[key] = image
    return image


class Portrait:
    """
    El personaje en escena: una imagen que cambia de pose y de plano.

    Guarda el elemento del lienzo y nada más. Cambiar de pose es cambiarle la
    imagen; cambiar de plano es cambiarle la imagen por otra más chica y
    reubicarla para que siga pisando el mismo piso.
    """

    def __init__(self, canvas: tk.Canvas, speaker: str, ground: float,
                 centre: float):
        self.canvas = canvas
        self.speaker = speaker
        self.ground = ground
        self.centre = centre
        self.step = 0
        self.blur = 1
        self.pose = "oscuro"
        self._image = None
        self.item = canvas.create_image(centre, ground, anchor="s")

    def show(self, pose: str, step_index: int, blur: int = 1) -> None:
        """Poner una pose en un plano. El plano 2 es el primer plano."""
        self.pose = pose
        self.step = step_index
        self.blur = blur
        image = load_pose(self.speaker, pose, STEPS[step_index], blur)
        if image is None:
            return
        try:
            self.canvas.itemconfigure(self.item, image=image, state="normal")
        except tk.TclError:
            return
        # La referencia tiene que vivir en algún lado: Tk no se queda con la
        # imagen, y sin esto el recolector se la lleva y el personaje
        # desaparece de la pantalla.
        self._image = image

    def place(self, x: float, y: float) -> None:
        try:
            self.canvas.coords(self.item, x, y)
        except tk.TclError:
            pass

    def hide(self) -> None:
        try:
            self.canvas.itemconfigure(self.item, state="hidden")
        except tk.TclError:
            pass

    @property
    def height(self) -> float:
        return self._image.height() if self._image is not None else ASSET_HEIGHT


# ---------------------------------------------------------------------------
# La escena
# ---------------------------------------------------------------------------

class SoundCues:
    """
    Pedir un sonido para *ahora*, aceptando que puede no existir todavía.

    Los sonidos de las apariciones se sintetizan a pedido y una escena puede
    abrirse antes de que el archivo esté escrito. `ambience.play` de algo que
    no está no falla ni avisa: no hace nada, y el momento pasa en silencio ---
    que es exactamente lo que le pasaba al clave de Bach y a la guitarra de
    la visión.

    Acá el pedido queda anotado y se reintenta en cada cuadro hasta que
    aparezca, con una fecha de vencimiento: un ruido de llegada que suena
    cuatro segundos después de la llegada es peor que ningún ruido.

    Lo usan las dos clases de escena de este archivo. Cada una lleva su
    propio reloj en ``self.tick``, que es lo único que este pedazo necesita
    saber de ellas.
    """

    #: Cuántos cuadros vale la pena esperar. Cuatro segundos: lo que tarda en
    #: sintetizarse el más largo de los sonidos de una escena.
    PATIENCE = 120

    def _init_cues(self) -> None:
        self._pending: List[Tuple[str, int]] = []

    def _cue(self, name: str, patience: int = 0) -> None:
        if not name:
            return
        if ambience.made(name):
            ambience.play(name)
            return
        self._pending.append((name, self.tick + (patience or self.PATIENCE)))

    def _pump_cues(self) -> None:
        if not self._pending:
            return
        for entry in list(self._pending):
            name, deadline = entry
            if ambience.made(name):
                ambience.play(name)
                self._pending.remove(entry)
            elif self.tick > deadline:
                self._pending.remove(entry)


class Cutscene(SoundCues):
    """
    Una escena entera: entrada del personaje, diálogo y salida.

    ``on_choice`` sólo se usa en el ofrecimiento: cuando una línea trae el
    gesto ``choice``, el diálogo se detiene y aparecen las tres respuestas.
    En cualquier otro caso la escena termina sola y llama a ``on_done``.
    """

    BOX_HEIGHT = 250
    MARGIN = 54

    #: Cuánto tarda cada cosa, en cuadros de 33 ms.
    #
    # Tres segundos largos en negro antes de abrir. Es tiempo muerto a
    # propósito: el silencio es la mitad de lo que hace que una escena
    # imponga, y encima de ese negro va la línea que dice dónde estamos.
    #
    # **Todo esto va deliberadamente lento.** La primera versión de estos
    # números era la mitad y la escena entera se sentía apurada: el
    # personaje aparecía, saltaba dos veces y ya estaba hablando, sin
    # dejar un momento para mirarlo. Una cinemática que no se puede
    # contemplar no es una cinemática, es una transición.
    SLEEP_FRAMES = 92          # el negro con el que arranca una escena
    WAKE_FRAMES = 34           # y lo que tarda en abrirse
    HOLD_BLACK = 38            # lo que aguanta en negro entre dos escenas
    # …y lo que aguanta cuando en esa negra hay una línea escrita. Con los
    # 26 cuadros de siempre --- menos de un segundo --- el texto se
    # encendía y se apagaba antes de poder leerlo: el encadenado entre dos
    # tramos pasaba como un parpadeo y se llevaba puesto lo único que tenía
    # para decir.
    HOLD_BLACK_READING = 104
    # El parpadeo cierra despacio y abre todavía más despacio: es el gesto
    # con el que el personaje cambia de lugar sin que se lo vea moverse, y
    # cuanto más dura menos se parece a un corte de montaje.
    BLINK_CLOSE = 12
    BLINK_OPEN = 17
    HOLD_FRAMES = 32           # lo que se queda quieto entre salto y salto

    def __init__(self, app, lines: Sequence[story.Line], *,
                 speaker: str = story.DEVIL, sky: str = "valley",
                 entrance: str = "approach", departure: str = "smoke",
                 bed: str = "", enter_sound: str = "", exit_sound: str = "",
                 choices: Sequence[Tuple[str, str, str]] = (),
                 on_choice: Optional[Callable[[str], None]] = None,
                 on_done: Optional[Callable[[], None]] = None,
                 keepsake: Tuple[str, str] = ("", ""),
                 reveal_name: str = "", font_scale: float = 1.0,
                 title: str = "", opening=True, blackout: bool = False,
                 dream: str = "", leap: bool = False):
        self.app = app
        self.lines = list(lines)
        self.speaker = speaker
        self.sky = sky
        self.entrance = entrance
        #: Si el acercamiento se hace de **un** salto en vez de dos. Se ve
        #: distinto y quiere decir otra cosa: dos saltos son alguien que se
        #: viene acercando y uno solo es alguien que ya estaba acá.
        self.leap = leap
        self.departure = departure
        self.bed = bed
        self.enter_sound = enter_sound
        self.exit_sound = exit_sound
        self.choices = list(choices)
        self.on_choice = on_choice
        self.on_done = on_done
        self.keepsake = keepsake
        self.reveal_name = reveal_name
        self.font_scale = font_scale
        self.title = title
        #: La línea que se lee sobre el negro del principio. Es lo único que
        #: hay en pantalla durante esos dos segundos, así que tiene que
        #: sostenerlos sola: dice dónde estamos, no qué va a pasar.
        self.dream = dream
        #: Cómo arranca. ``True`` cierra los ojos y los abre ya adentro ---
        #: la entrada al relato. ``False`` es seguir hablando sin corte.
        #: ``"dark"`` es despertar de una negra que dejó puesta la escena
        #: anterior: no vuelve a cerrar, sólo aguanta y abre.
        self.opening = opening
        #: Si al terminar deja la pantalla en negro en vez de devolverla. Se
        #: usa cuando atrás viene otra escena: en vez de volver al programa y
        #: entrar de nuevo, la negra se estira y del otro lado ya hay otra
        #: cosa. Un solo pestañeo largo en lugar de dos idas y vueltas.
        self.blackout = blackout

        self.index = 0
        self.revealed = 0.0
        self.typing = False
        self.phase = "sleep"
        self.tick = 0
        self.portrait: Optional[Portrait] = None
        self.particles: List[dict] = []
        self.smoke: List[dict] = []
        self.names: Dict[str, str] = {}
        self._after: Optional[str] = None
        self._closed = False
        self._pause = 0
        self._choice_items: List[Tuple[int, int, str]] = []
        self._hops = 0
        self._last_pose = "normal"
        self._entered = False
        #: Si la cama de ambiente ya arrancó. Puede no arrancar en el primer
        #: cuadro: los sonidos de las visitas se sintetizan a pedido.
        self._bed_on = False
        self._init_cues()

    # -- ciclo de vida ------------------------------------------------------

    def start(self) -> None:
        app = self.app
        app.update_idletasks()
        self.width = max(720, app.winfo_width())
        self.height = max(520, app.winfo_height())
        # El piso: donde apoyan los pies en el primer plano. Bien abajo, para
        # que el personaje quede parado *detrás* del cuadro de diálogo, que
        # es como se para un personaje en cualquier juego de este tipo.
        self.ground = self.height - self.BOX_HEIGHT + 108
        self.horizon = self.height - self.BOX_HEIGHT - 40
        self.centre = self.width * 0.5

        self.canvas = tk.Canvas(app, width=self.width, height=self.height,
                                highlightthickness=0, bd=0,
                                bg=SKIES.get(self.sky, SKIES["valley"])[0])
        self.canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        # `Canvas.lift` es `tag_raise`: sube un elemento del dibujo, no el
        # widget. Para poner el lienzo por encima del resto de la ventana hay
        # que llamar al método que el canvas tapó.
        tk.Misc.lift(self.canvas)
        self._draw_sky()
        self._draw_particles()
        self.backdrop = SKIES.get(self.sky, SKIES["valley"])[2]

        start_step = 0 if self.entrance == "approach" else 2
        self._descent = 0
        self.portrait = Portrait(self.canvas, self.speaker, self.ground,
                                 self.centre)
        self.portrait.show("oscuro" if start_step == 0 else self._pose_now(),
                           start_step, self._blur_for(start_step))
        self._settle(start_step)
        if start_step == 2:
            self._hops = 2
        if self.entrance == "descend":
            # Fuera de la pantalla, por arriba. Sin esto se lo veía parado en
            # el piso un segundo y recién después empezaba a bajar, que es
            # peor que no hacer la entrada.
            self.portrait.place(self.centre, -self.portrait.height * 0.4)

        self._draw_haze()
        self._draw_box()
        self._draw_eyelids()
        self.canvas.bind("<Button-1>", lambda _e: self._poke())
        app.bind("<space>", self._poke_key, add="+")
        app.bind("<Return>", self._poke_key, add="+")

        if self.opening is False:
            # Ya estábamos adentro: se sigue sin volver a cerrar los ojos.
            self.tick = 0
            self._eyelids(0.0)
            if self.entrance == "approach":
                self.phase = "enter"
            else:
                self.phase = "talk"
                self._show_box()
                self._begin_line()
        self._bed_on = False
        self._start_bed()
        # El ruido de la llegada **no** suena acá: acá la pantalla todavía
        # está negra y no entró nadie. Lo dispara la entrada que
        # corresponda --- el primer salto del que se acerca, el primer
        # cuadro del que baja --- y `_show_box` lo cubre para los que
        # simplemente ya están.
        self._loop()

    def close(self, release: bool = True) -> None:
        """
        Cerrar la escena.

        ``release`` en falso deja los atajos de teclado como estaban: cuando
        una escena encadena con la siguiente, la que sigue ya se los ató
        antes de que ésta muera, y soltarlos acá se los sacaría a ella.
        """
        if self._closed:
            return
        self._closed = True
        if self._after is not None:
            try:
                self.app.after_cancel(self._after)
            except Exception:                               # noqa: BLE001
                pass
            self._after = None
        # Sólo el bucle: lo que suena una sola vez se deja terminar. El coro
        # con el que se va la figura de luz dura más que la animación de la
        # partida, y cortarlo era lo que se oía como un tijeretazo. Una cola
        # que sigue sonando encima del programa que vuelve, además, tapa la
        # costura entre la escena y la ventana.
        ambience.stop_beds()
        if release:
            try:
                self.app.unbind("<space>")
                self.app.unbind("<Return>")
            except tk.TclError:
                pass
        try:
            self.canvas.destroy()
        except tk.TclError:
            pass

    # -- el fondo -----------------------------------------------------------

    def _draw_sky(self) -> None:
        """Un degradado hecho con franjas: Tk no sabe pintar otra cosa."""
        if self.sky == "void":
            self._draw_void()
            return
        bands = SKIES.get(self.sky, SKIES["valley"])
        steps = 44
        for index in range(steps):
            position = index / (steps - 1)
            if position < 0.5:
                colour = mix(bands[0], bands[1], position * 2.0)
            else:
                colour = mix(bands[1], bands[2], (position - 0.5) * 2.0)
            top = self.height * position
            self.canvas.create_rectangle(
                0, top, self.width, top + self.height / steps + 2,
                fill=colour, outline=colour)
        if self.sky == "heaven":
            self._draw_rays()

        horizon = self.horizon + 40
        crest = [0, horizon, self.width * 0.18, horizon - 58,
                 self.width * 0.36, horizon - 16, self.width * 0.55, horizon - 74,
                 self.width * 0.74, horizon - 22, self.width, horizon - 54]
        if self.sky == "valley":
            self._draw_valley_sky(bands, horizon)
        self.canvas.create_polygon(
            crest + [self.width, horizon + 4, 0, horizon + 4],
            fill=mix(bands[2], "#000000", 0.55), outline="")
        if self.sky == "valley":
            self._draw_valley_ridge(crest, bands, horizon)
        self.canvas.create_rectangle(0, horizon, self.width, self.height,
                                     fill=bands[3], outline="")
        if self.sky == "valley":
            self._draw_valley_mist(bands, horizon)
        if self.title:
            self.canvas.create_text(
                self.width / 2, 40, text=self.title, fill=GOLD_DEEP,
                font=self._font(("Georgia", 12)))

    def _draw_void(self) -> None:
        """
        El fondo de las visitas: negro por delante de la ventana.

        No hay lugar, no hay hora y no hay clima. Los tres que vienen de
        visita no vienen de ninguna parte --- aparecen donde uno está ---, y
        dibujarles un valle o un cielo los habría mandado a un sitio.

        El negro va tramado sobre el color del programa, así que se lee como
        un velo con un poco de transparencia y no como un telón. Debajo de la
        figura queda un charco de luz apenas más claro: sin él la figura no
        se apoya en nada y se ve recortada y pegada encima.
        """
        self.canvas.create_rectangle(0, 0, self.width, self.height,
                                     fill=VOID_UNDER, outline="")
        floor = self._floor_for(2)
        # El charco: óvalos macizos uno adentro del otro, del color de abajo
        # hacia el negro. Es el mismo degradado por franjas del cielo, pero
        # en redondo --- y por la misma razón que el halo de la luna: dos
        # formas tramadas iguales pintan los mismos píxeles y superponerlas
        # no oscurece nada.
        for step in range(8, 0, -1):
            position = step / 8.0
            radius_x = self.width * 0.30 * position
            radius_y = 78 * position
            self.canvas.create_oval(
                self.centre - radius_x, floor - radius_y,
                self.centre + radius_x, floor + radius_y * 0.55,
                fill=mix(VOID_UNDER, "#2A2E38", 0.35 * (1.0 - position)),
                outline="")
        self.canvas.create_rectangle(0, 0, self.width, self.height,
                                     fill=BLACK, outline="", stipple="gray75")
        if self.title:
            self.canvas.create_text(
                self.width / 2, 40, text=self.title, fill=GOLD_DEEP,
                font=self._font(("Georgia", 12)))

    # -- el valle -----------------------------------------------------------
    #
    # Todo lo de acá abajo se dibuja una sola vez, al abrir la escena, y no
    # se vuelve a tocar: son figuras del lienzo, no widgets, y quedarse
    # quietas no le cuesta nada a la ventana. La semilla es fija, así que el
    # valle es siempre el mismo valle --- vuelve a aparecer tres veces a lo
    # largo del relato y tiene que reconocerse.

    def _sky_at(self, bands, y: float) -> str:
        """El color del cielo a esta altura. Mismo cálculo que el degradado."""
        position = min(1.0, max(0.0, y / max(1.0, self.height)))
        if position < 0.5:
            return mix(bands[0], bands[1], position * 2.0)
        return mix(bands[1], bands[2], (position - 0.5) * 2.0)

    def _draw_valley_sky(self, bands, horizon: float) -> None:
        """Estrellas y luna: lo que convierte un degradado en una noche."""
        rng = random.Random(4)
        ceiling = max(40.0, horizon - 150)
        for _ in range(54):
            x = rng.uniform(0, self.width)
            y = rng.uniform(8, ceiling)
            # Más chicas y más apagadas cerca del horizonte: el aire de abajo
            # es el que se lleva puestas las estrellas de verdad.
            height = 1.0 - y / ceiling
            size = 1.0 + rng.random() * 1.7 * height
            self.canvas.create_oval(
                x, y, x + size, y + size, outline="",
                fill=mix(bands[0], "#FFF4DC", 0.2 + 0.55 * rng.random() * height))

        moon_x, moon_y, radius = self.width * 0.76, horizon - 232, 34.0
        # El halo son óvalos macizos, uno adentro del otro, del color del
        # cielo hacia el de la luna: el mismo degradado por franjas con el
        # que está pintado el cielo, pero en redondo.
        #
        # Con tramas no funciona, y la razón vale la pena: el patrón de un
        # `stipple` se ancla al lienzo y no a la figura, así que dos óvalos
        # tramados iguales pintan **los mismos** píxeles. Tres anillos
        # superpuestos no daban un degradado sino un disco gris parejo con un
        # borde duro --- una diana con la luna en el medio.
        sky_here = self._sky_at(bands, moon_y)
        for index in range(18, 0, -1):
            share = index / 18.0
            scale = 1.02 + 2.3 * share
            self.canvas.create_oval(
                moon_x - radius * scale, moon_y - radius * scale,
                moon_x + radius * scale, moon_y + radius * scale,
                fill=mix(sky_here, "#B7A98A", (1.0 - share) ** 1.8),
                outline="")
        self.canvas.create_oval(
            moon_x - radius, moon_y - radius, moon_x + radius,
            moon_y + radius, fill="#D9CCA9", outline="")
        # Dos mares, para que sea una luna y no un círculo.
        self.canvas.create_oval(
            moon_x - radius * 0.46, moon_y - radius * 0.30,
            moon_x - radius * 0.02, moon_y + radius * 0.24,
            fill="#C6B994", outline="")
        self.canvas.create_oval(
            moon_x + radius * 0.14, moon_y + radius * 0.18,
            moon_x + radius * 0.52, moon_y + radius * 0.60,
            fill="#CCBF9C", outline="")

        # La cadena de atrás, más clara: dos cerros a distinta distancia son
        # lo que le da fondo a la escena. Va antes que la de adelante, que la
        # tapa por abajo.
        far = mix(bands[2], "#000000", 0.30)
        self.canvas.create_polygon(
            [0, horizon - 40, self.width * 0.12, horizon - 96,
             self.width * 0.3, horizon - 52, self.width * 0.47, horizon - 118,
             self.width * 0.66, horizon - 62, self.width * 0.85, horizon - 104,
             self.width, horizon - 58, self.width, horizon + 4, 0, horizon + 4],
            fill=far, outline="")

    def _ridge_y(self, crest, x: float) -> float:
        """La altura de la loma en este punto, interpolando entre sus vértices."""
        points = [(crest[i], crest[i + 1]) for i in range(0, len(crest), 2)]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if x0 <= x <= x1 and x1 > x0:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return points[-1][1]

    def _draw_valley_ridge(self, crest, bands, horizon: float) -> None:
        """Los pinos parados sobre la loma de adelante."""
        rng = random.Random(21)
        ink = mix(bands[2], "#000000", 0.62)
        x = 24.0
        while x < self.width - 20:
            base = self._ridge_y(crest, x) + 3
            tall = rng.uniform(22, 44)
            wide = tall * rng.uniform(0.26, 0.4)
            # Tres faldas superpuestas: un triángulo solo se lee como una
            # cuña y no como un árbol.
            for level in range(3):
                share = level / 3.0
                top = base - tall * (1.0 - share * 0.45)
                half = wide * (0.45 + share * 0.55)
                self.canvas.create_polygon(
                    [x, top, x - half, base - tall * share * 0.42,
                     x + half, base - tall * share * 0.42],
                    fill=ink, outline="")
            self.canvas.create_line(x, base - tall * 0.1, x, base + 2,
                                    fill=ink, width=2)
            x += rng.uniform(26, 74)

    def _draw_valley_mist(self, bands, horizon: float) -> None:
        """
        La niebla que se acuesta al pie de la loma.

        Manchones sueltos de distinto ancho, y no franjas de lado a lado: una
        franja tramada que cruza la pantalla entera no se lee como niebla,
        se lee como un alambrado --- sobre todo con la bruma de la entrada
        encima, que le sube el contraste a todo lo tramado.
        """
        rng = random.Random(33)
        pale = mix(bands[2], "#FFFFFF", 0.15)
        x = -60.0
        while x < self.width:
            width = rng.uniform(140, 340)
            height = rng.uniform(16, 30)
            y = horizon - rng.uniform(14, 52)
            self.canvas.create_oval(x, y, x + width, y + height,
                                    fill=pale, outline="", stipple="gray12")
            x += width * rng.uniform(0.45, 0.8)

    def _draw_rays(self) -> None:
        cx, cy = self.width / 2, self.horizon - 110
        self.rays: List[int] = []
        for index in range(24):
            angle = index * math.pi / 12
            self.rays.append(self.canvas.create_line(
                cx, cy, cx + math.cos(angle) * self.width,
                cy + math.sin(angle) * self.width,
                fill=mix(SKIES["heaven"][1], GOLD_DEEP, 0.16), width=4))

    def _draw_particles(self) -> None:
        """
        Viento, brasas o motas de luz.

        Pocas y baratas: se mueven con ``coords`` y no hay ningún widget en el
        medio, así que treinta cuadros por segundo no le cuestan nada a la
        ventana.
        """
        rng = random.Random(11)
        kind = {"valley": "wind", "ashes": "ember",
                "heaven": "mote", "void": "mote"}.get(self.sky, "wind")
        colour = {"wind": "#6A5A55", "ember": "#D06A2A",
                  "mote": GOLD_PALE}[kind]
        if self.sky == "void":
            # Polvo, no luz: en el negro las motas doradas se leen como
            # chispas y esto no es una aparición mágica, es alguien parado
            # en un cuarto oscuro.
            colour = "#3C4250"
        for _ in range(26):
            x = rng.uniform(0, self.width)
            y = rng.uniform(40, self.horizon + 40)
            if kind == "wind":
                item = self.canvas.create_line(x, y, x + rng.uniform(14, 40), y,
                                               fill=colour, width=1)
            else:
                size = rng.uniform(1.5, 3.5)
                item = self.canvas.create_oval(x, y, x + size, y + size,
                                               fill=colour, outline="")
            self.particles.append({
                "item": item, "kind": kind, "x": x, "y": y,
                "speed": rng.uniform(0.6, 2.6),
                "phase": rng.uniform(0, math.tau),
                "sway": rng.uniform(0.2, 1.1)})

    # -- el párpado ----------------------------------------------------------

    #: Con qué densidad se empaña la escena en cada plano del acercamiento.
    #: Vacío es sin bruma. Tk no tiene transparencia: lo que hace de velo es
    #: un rectángulo tramado, que pinta uno de cada dos píxeles --- o uno de
    #: cada cuatro --- del color del fondo. De lejos eso se lee como aire
    #: espeso, y es lo mismo que hace que no se sepa dónde estamos parados.
    HAZES = ("gray50", "gray25", "")

    def _draw_haze(self) -> None:
        """
        El aire espeso mientras la figura está lejos.

        Va sobre el fondo y sobre el personaje, y por debajo del cuadro de
        diálogo y de los párpados: empaña la escena, no la interfaz. Se
        levanta de a un salto, igual que se acerca la figura, así que el
        acercamiento se ve además como algo que entra en foco.
        """
        self.haze = None
        if self.entrance != "approach":
            return
        bands = SKIES.get(self.sky, SKIES["valley"])
        self.haze = self.canvas.create_rectangle(
            0, 0, self.width, self.height, fill=bands[1], outline="",
            stipple=self.HAZES[0])

    def _lift_haze(self, step_index: int) -> None:
        if self.haze is None:
            return
        stipple = self.HAZES[min(step_index, len(self.HAZES) - 1)]
        try:
            if not stipple:
                self.canvas.delete(self.haze)
                self.haze = None
            else:
                self.canvas.itemconfigure(self.haze, stipple=stipple)
        except tk.TclError:
            self.haze = None

    def _draw_eyelids(self) -> None:
        """
        Dos bandas negras que se cierran desde arriba y desde abajo.

        Sirven para tres cosas distintas con el mismo gesto: entrar a la
        escena --- como quedándose dormido ---, dejar que el personaje cambie
        de lugar sin que se lo vea moverse, y salir. Que sea siempre el mismo
        movimiento es lo que hace que el salto se lea como un pestañeo y no
        como un corte de montaje.
        """
        self.lid_top = self.canvas.create_rectangle(
            0, 0, self.width, 0, fill=BLACK, outline="")
        self.lid_bottom = self.canvas.create_rectangle(
            0, self.height, self.width, self.height, fill=BLACK, outline="")
        # El texto del sueño va por encima de los párpados: es lo único que
        # se ve mientras están cerrados.
        self.dream_text = self.canvas.create_text(
            self.width / 2, self.height * 0.46, text=self.dream, fill=BLACK,
            font=self._font(("Georgia", 23, "italic")),
            width=self.width * 0.66, justify="center", state="hidden")
        self._eyelids(1.0)

    def _eyelids(self, amount: float) -> None:
        """1 es todo negro, 0 es abierto del todo."""
        amount = max(0.0, min(1.0, amount))
        half = self.height * 0.5 * amount
        try:
            self.canvas.coords(self.lid_top, 0, 0, self.width, half)
            self.canvas.coords(self.lid_bottom, 0, self.height - half,
                               self.width, self.height)
            self.canvas.tag_raise(self.lid_top)
            self.canvas.tag_raise(self.lid_bottom)
            self.canvas.tag_raise(self.dream_text)
        except tk.TclError:
            pass

    def _dream(self, amount: float) -> None:
        """
        Encender el texto del sueño.

        En cero no se apaga: se **esconde**. Apagarlo a negro alcanzaba
        mientras la pantalla estaba negra, pero en cuanto los párpados se
        abrían el texto seguía ahí, escrito en negro sobre la escena.
        """
        amount = max(0.0, min(1.0, amount))
        try:
            if amount <= 0.01:
                self.canvas.itemconfigure(self.dream_text, state="hidden")
                return
            self.canvas.itemconfigure(
                self.dream_text, state="normal",
                fill=mix(BLACK, "#C8C2B4", amount))
        except tk.TclError:
            pass

    # -- el cuadro de diálogo ------------------------------------------------

    def _font(self, base) -> tuple:
        family, size = base[0], base[1]
        rest = tuple(base[2:])
        return (family, max(8, int(round(size * self.font_scale)))) + rest

    def _draw_box(self) -> None:
        left, right = self.MARGIN, self.width - self.MARGIN
        top = self.height - self.BOX_HEIGHT
        bottom = self.height - 34
        self.box = self.canvas.create_rectangle(
            left, top, right, bottom, fill=BOX, outline=BOX_EDGE, width=2)
        # El ancho lo pone `_fit_plate` cuando sepa qué nombre va adentro.
        self._plate_top = top
        self.name_plate = self.canvas.create_rectangle(
            left + 22, top - 18, left + 250, top + 16,
            fill=BOX, outline=BOX_EDGE, width=2)
        self.name_text = self.canvas.create_text(
            left + 38, top - 1, text="", anchor="w", fill=GOLD,
            font=self._font(("Georgia", 13, "bold")))
        self.body_text = self.canvas.create_text(
            left + 34, top + 40, text="", anchor="nw", fill=INK,
            width=right - left - 68, font=self._font(("Segoe UI", 14)))
        self.prompt = self.canvas.create_text(
            right - 34, bottom - 22, text="", anchor="e", fill=MUTED,
            font=self._font(("Segoe UI", 11)))
        self.counter = self.canvas.create_text(
            right - 34, top - 1, text="", anchor="e", fill=MUTED,
            font=self._font(("Segoe UI", 10)))
        self._hide_box()

    def _fit_plate(self) -> None:
        """
        Estirar el cartelito hasta donde llegue el nombre.

        Era de ancho fijo, calculado para «? ? ?» y para un nombre corto, así
        que «Johann Sebastian Bach» se salía por la derecha --- y con la
        letra al 180% se salía cualquiera. Se mide el texto ya dibujado y el
        recuadro se acomoda a él, que además lo deja bien con cualquier
        nombre que se agregue después.
        """
        try:
            box = self.canvas.bbox(self.name_text)
            if box is None:
                return
            left = self.MARGIN + 22
            self.canvas.coords(self.name_plate, left, self._plate_top - 18,
                               max(box[2] + 16, left + 120),
                               self._plate_top + 16)
        except tk.TclError:
            pass

    def _box_items(self):
        return (self.box, self.name_plate, self.name_text, self.body_text,
                self.prompt, self.counter)

    def _entrance_sound(self) -> None:
        """El ruido de la llegada, una sola vez y en el momento justo."""
        if self._entered:
            return
        self._entered = True
        self._cue(self.enter_sound)

    def _show_box(self) -> None:
        # Red de seguridad: el que no entra ni caminando ni bajando ya está
        # en escena cuando se abre el cuadro, y ése es su momento.
        self._entrance_sound()
        for item in self._box_items():
            self.canvas.itemconfigure(item, state="normal")

    def _hide_box(self) -> None:
        for item in self._box_items():
            self.canvas.itemconfigure(item, state="hidden")

    # -- el bucle -----------------------------------------------------------

    def _loop(self) -> None:
        if self._closed:
            return
        try:
            if not self.canvas.winfo_exists():
                return
        except tk.TclError:
            return
        self.tick += 1
        # La cama de ambiente no se repite sola: hay que reponerla, y tiene
        # que ser desde este hilo. En **cada** cuadro: el archivo ya está
        # cruzado para empalmar sin costura, así que el silencio que se oía
        # en el empalme era el tiempo que tardábamos en preguntar. Cada doce
        # cuadros eso era casi medio segundo de nada.
        ambience.pump()
        self._start_bed()
        self._pump_cues()
        self._move_particles()
        self._breathe()
        {"sleep": self._step_sleep,
         "enter": self._step_enter,
         "talk": self._step_talk,
         "choose": self._step_idle,
         "leave": self._step_leave}.get(self.phase, self._step_idle)()
        try:
            self._after = self.app.after(FRAME, self._loop)
        except tk.TclError:
            return

    def _start_bed(self) -> None:
        """
        Encender la cama de ambiente en cuanto exista.

        Los sonidos de las visitas se sintetizan a pedido --- cada una ocurre
        una vez en la vida del programa --- así que cuando la escena se abre
        el archivo puede no estar escrito todavía. `ambience.play` de algo
        que no existe no falla: no hace nada, y la escena entera quedaba en
        silencio por haber preguntado medio segundo antes de tiempo. Se
        vuelve a intentar en cada cuadro hasta que suene.
        """
        if not self.bed or self._bed_on or not ambience.made(self.bed):
            return
        ambience.play(self.bed, loop=True)
        self._bed_on = True

    def _move_particles(self) -> None:
        for dot in self.particles:
            dot["phase"] += 0.05
            if dot["kind"] == "wind":
                dot["x"] += dot["speed"] * 1.8
                y = dot["y"] + math.sin(dot["phase"]) * 4.0 * dot["sway"]
                if dot["x"] > self.width + 40:
                    dot["x"] = -40
                length = 14 + dot["speed"] * 9
                self.canvas.coords(dot["item"], dot["x"], y,
                                   dot["x"] + length, y)
            else:
                dot["y"] -= dot["speed"] * 0.55
                x = dot["x"] + math.sin(dot["phase"]) * 8.0 * dot["sway"]
                if dot["y"] < 20:
                    dot["y"] = self.horizon + 40
                size = 2.0 + dot["sway"]
                self.canvas.coords(dot["item"], x, dot["y"],
                                   x + size, dot["y"] + size)

    def _breathe(self) -> None:
        """
        El reposo: un milímetro arriba y un milímetro abajo.

        Es lo único que separa a un personaje de una lámina pegada al fondo, y
        tiene que ser chico --- dos píxeles --- porque en primer plano
        cualquier cosa más grande se lee como si rebotara.
        """
        if self.portrait is None or self.phase not in ("talk", "choose"):
            return
        lift = math.sin(self.tick * 0.075) * 2.0
        self.portrait.place(self.centre,
                            self._floor_for(self.portrait.step) + lift)

    def _floor_for(self, step_index: int) -> float:
        """
        Dónde apoya los pies en cada plano.

        Los tres pisan el mismo suelo, apenas escalonados: lo que sube al que
        está lejos es la perspectiva, no un salto. Puestos sobre la línea del
        horizonte se veían flotando, que es lo que pasa cuando uno confunde
        «más lejos» con «más arriba».
        """
        if step_index >= 2:
            return self.ground
        if step_index == 1:
            return self.horizon + 130
        return self.horizon + 74

    def _settle(self, step_index: int) -> None:
        self.portrait.place(self.centre, self._floor_for(step_index))

    def _blur_for(self, step_index: int) -> int:
        """Cuánto se desenfoca la figura en este plano. Sólo al acercarse."""
        if self.entrance != "approach":
            return 1
        return BLURS[min(step_index, len(BLURS) - 1)]

    def _pose_now(self) -> str:
        """La pose que pide la línea que se está diciendo."""
        if not self.lines:
            return "normal"
        line = self.lines[min(self.index, len(self.lines) - 1)]
        return getattr(line, "pose", "") or self._last_pose

    # -- dormirse y despertar en otro lado ------------------------------------

    def _step_sleep(self) -> None:
        """
        La entrada: se abre desde el negro.

        Es lo que separa el programa de la escena. Sin ese corte la
        cinemática se lee como un cartel que apareció encima de la ventana;
        con él, se lee como abrir los ojos en otro lado.
        """
        # Siempre se entra igual: negro, un silencio, y los ojos que se
        # abren. Cerrarlos primero --- que era lo que hacía --- se lee al
        # revés de lo que uno espera, porque la pantalla que se está tapando
        # es la que uno estaba mirando y no una que se va.
        if self.opening == "dark":
            hold = self.HOLD_BLACK_READING if self.dream else self.HOLD_BLACK
        else:
            hold = self.SLEEP_FRAMES
        if self.tick <= hold:
            self._eyelids(1.0)
            # El texto aparece, se sostiene y se apaga antes de que los ojos
            # se abran: si siguiera encendido mientras se abren, se leería
            # como un cartel encima de la escena y no como algo pensado.
            self._dream(math.sin(math.pi * (self.tick / hold)) ** 0.7)
            return
        self._dream(0.0)
        wake = self.tick - hold
        self._eyelids(1.0 - wake / self.WAKE_FRAMES)
        if wake >= self.WAKE_FRAMES:
            self.tick = 0
            if self.entrance in ("approach", "descend"):
                self.phase = "enter"
            else:
                self.phase = "talk"
                self._show_box()
                self._begin_line()

    #: Cuánto tarda en bajar del cielo. Tres segundos: baja de arriba de
    #: todo y frena al apoyar, y hacerlo rápido convertía una aparición en
    #: un objeto que cae.
    DESCENT_FRAMES = 96

    def _step_descend(self) -> None:
        """
        Bajar del cielo, despacio y frenando al final.

        Al revés que los otros dos, a éste no hace falta esconderlo: no viene
        de lejos ni se acerca a escondidas. Se lo ve venir desde arriba, con
        el halo por delante, y apoya. Los rayos se van abriendo a medida que
        baja: son la única parte del fondo que participa de la entrada.
        """
        if self.tick == 1:
            # La luz se abre cuando empieza a bajar, no cuando ya llegó, y
            # el coro con ella: sonaba desde antes de que la escena se
            # abriera, con los ojos todavía cerrados.
            self._flash()
            self._entrance_sound()
        position = min(1.0, self.tick / self.DESCENT_FRAMES)
        eased = 1.0 - (1.0 - position) ** 2.6
        floor = self._floor_for(2)
        self.portrait.place(self.centre,
                            -self.portrait.height * 0.4
                            + (floor + self.portrait.height * 0.4) * eased)
        for item in getattr(self, "rays", []):
            try:
                self.canvas.itemconfigure(
                    item, fill=mix(SKIES["heaven"][1], GOLD_DEEP,
                                   0.06 + 0.26 * eased),
                    width=int(3 + 6 * eased))
            except tk.TclError:
                break
        if position >= 1.0:
            self.phase = "talk"
            self.tick = 0
            self._show_box()
            self._begin_line()

    def _step_enter(self) -> None:
        if self.entrance == "descend":
            self._step_descend()
            return
        """
        El acercamiento: se queda quieto, uno parpadea, y está más cerca.

        Nunca se lo ve moverse. Aparece lejos y a oscuras --- una figura, no
        una persona ---, y cada parpadeo lo deja un salto más cerca. Al
        segundo está encima, y recién ahí se le ve la cara.
        """
        # El ciclo lleva dos cuadros de más: sin ellos el último paso del
        # parpadeo cae justo afuera del rango y la comprobación de «ya está
        # abierto» no llega a cumplirse nunca, así que el personaje se queda
        # entrando para siempre.
        cycle = self.HOLD_FRAMES + self.BLINK_CLOSE + self.BLINK_OPEN + 2
        position = self.tick % cycle
        if position < self.HOLD_FRAMES:
            return
        step = position - self.HOLD_FRAMES
        if step <= self.BLINK_CLOSE:
            self._eyelids(step / self.BLINK_CLOSE)
            return
        if step == self.BLINK_CLOSE + 1:
            # Con los ojos cerrados: el salto ocurre acá, sin que se vea.
            self._hops = 2 if self.leap else min(2, self._hops + 1)
            near = self._hops >= 2
            self.portrait.show(self._pose_now() if near else "oscuro",
                               self._hops, self._blur_for(self._hops))
            self._settle(self._hops)
            self._lift_haze(self._hops)
            # El ruido de la llegada va con el primer salto, sea el que sea:
            # es cuando el personaje se mueve por primera vez. En `start`
            # sonaba con los ojos todavía cerrados, antes de que hubiera
            # entrado nadie. (`_entrance_sound` se cubre solo para no sonar
            # dos veces.)
            self._entrance_sound()
        opened = step - self.BLINK_CLOSE
        self._eyelids(max(0.0, 1.0 - opened / self.BLINK_OPEN))
        if opened >= self.BLINK_OPEN and self._hops >= 2:
            self.phase = "talk"
            self.tick = 0
            self._show_box()
            self._begin_line()

    def _step_idle(self) -> None:
        return

    # -- el diálogo -----------------------------------------------------------

    def _step_talk(self) -> None:
        if not self.typing:
            self._blink_prompt()
            return
        line = self.lines[self.index]
        style = SPEAKERS.get(line.speaker, SPEAKERS[story.NARRATOR])
        if self._pause > 0:
            self._pause -= 1
            return
        before = self.revealed
        self.revealed = min(len(line.text), self.revealed + style["speed"])
        shown = int(self.revealed)
        self.canvas.itemconfigure(self.body_text, text=line.text[:shown])
        if shown >= len(line.text):
            self._finish_line()
            return
        # Un respiro en la puntuación: es lo que convierte una tira de letras
        # en alguien hablando.
        last = line.text[shown - 1: shown]
        if last in ".…!?":
            self._pause = 14
        elif last in ",;:—":
            self._pause = 7
        if int(before) // 3 != shown // 3:
            ambience.play(style["blip"])

    def _begin_line(self) -> None:
        line = self.lines[self.index]
        style = SPEAKERS.get(line.speaker, SPEAKERS[story.NARRATOR])
        name = self.names.get(line.speaker, style["name"])
        self.canvas.itemconfigure(self.name_text, text=name,
                                  fill=style["colour"])
        self.canvas.itemconfigure(self.name_plate,
                                  state="normal" if name else "hidden")
        self._fit_plate()
        self.canvas.itemconfigure(
            self.body_text, text="", font=self._font(style["font"]),
            fill=style["colour"] if line.speaker == story.NARRATOR else INK)
        self.canvas.itemconfigure(
            self.counter, text=f"{self.index + 1} / {len(self.lines)}")
        self.canvas.itemconfigure(self.prompt, text="")
        self.revealed = 0.0
        self._pause = 0
        self.typing = True
        # La pose sigue a la línea. Mientras habla el narrador, el personaje
        # se queda como estaba: no es él quien habla.
        pose = getattr(line, "pose", "")
        if pose and self.portrait is not None:
            changed = pose != self._last_pose
            self._last_pose = pose
            self.portrait.show(pose, self.portrait.step, self.portrait.blur)
            self._settle(self.portrait.step)
            # Sólo al cambiar: la cara se sostiene varias líneas y el golpe
            # tiene que sonar cuando cambia, no en cada una de ellas.
            if changed and pose in POSE_SOUNDS:
                self._cue(POSE_SOUNDS[pose], patience=30)
        self._apply_cue(line.cue)

    def _apply_cue(self, cue: str) -> None:
        if cue == "shake":
            self._shake()
        elif cue == "flash":
            self._flash()
        elif cue == "reveal" and self.reveal_name:
            self.names[self.lines[self.index].speaker] = self.reveal_name
            self.canvas.itemconfigure(self.name_text, text=self.reveal_name)
            self._fit_plate()
        elif cue == "item":
            self._show_keepsake()
        elif cue == "silence":
            ambience.stop_all()

    def _finish_line(self) -> None:
        self.typing = False
        if self.lines[self.index].cue == "choice" and self.choices:
            self.phase = "choose"
            self._draw_choices()

    def _blink_prompt(self) -> None:
        last = self.index >= len(self.lines) - 1
        text = "Terminar  ▸" if last else "Siguiente  ▸"
        visible = (self.tick // 16) % 2 == 0
        self.canvas.itemconfigure(self.prompt, text=text if visible else "",
                                  fill=GOLD if visible else MUTED)

    def _poke_key(self, _event=None) -> None:
        self._poke()

    def _poke(self) -> None:
        """Un clic o una tecla: completar la línea, o pasar a la siguiente."""
        if self._closed or self.phase != "talk":
            return
        if self.typing:
            line = self.lines[self.index]
            self.revealed = len(line.text)
            self.canvas.itemconfigure(self.body_text, text=line.text)
            self._finish_line()
            return
        if self.index >= len(self.lines) - 1:
            self._leave()
            return
        self.index += 1
        self._begin_line()

    # -- las tres respuestas ---------------------------------------------------

    def _draw_choices(self) -> None:
        self.canvas.itemconfigure(self.prompt, text="")
        left = self.MARGIN + 34
        top = self.height - self.BOX_HEIGHT + 84
        width = self.width - self.MARGIN * 2 - 68
        for index, (key, label, blurb) in enumerate(self.choices):
            y = top + index * 46
            box = self.canvas.create_rectangle(
                left, y, left + width, y + 38, fill=BOX,
                outline=BOX_EDGE, width=1)
            text = self.canvas.create_text(
                left + 18, y + 19, anchor="w",
                text=f"{label}   —   {blurb}", fill=INK,
                font=self._font(("Segoe UI", 12)))
            for item in (box, text):
                self.canvas.tag_bind(item, "<Button-1>",
                                     lambda _e, k=key: self._pick(k))
                self.canvas.tag_bind(
                    item, "<Enter>",
                    lambda _e, b=box, t=text: (
                        self.canvas.itemconfigure(b, outline=GOLD,
                                                  fill="#1E1F26"),
                        self.canvas.itemconfigure(t, fill=GOLD)))
                self.canvas.tag_bind(
                    item, "<Leave>",
                    lambda _e, b=box, t=text: (
                        self.canvas.itemconfigure(b, outline=BOX_EDGE,
                                                  fill=BOX),
                        self.canvas.itemconfigure(t, fill=INK)))
            self._choice_items.append((box, text, key))

    def _pick(self, key: str) -> None:
        if self.phase != "choose":
            return
        self.phase = "picked"
        for box, text, _key in self._choice_items:
            self.canvas.delete(box)
            self.canvas.delete(text)
        self._choice_items = []
        chooser, self.on_choice = self.on_choice, None
        self.close()
        if chooser is not None:
            chooser(key)

    # -- el recuerdo -----------------------------------------------------------

    def _show_keepsake(self) -> None:
        """
        La tarjeta de lo que el personaje entrega.

        Va arriba del todo y no en el medio: en el medio tapaba justo el
        cuadro de diálogo, que es donde está lo que se está diciendo mientras
        se entrega.
        """
        icon, name = self.keepsake
        if not name:
            return
        cx, cy = self.width / 2, 76
        card = self.canvas.create_rectangle(
            cx - 215, cy - 38, cx + 215, cy + 38, fill="#1A1710",
            outline=GOLD, width=2)
        glyph = self.canvas.create_text(
            cx - 162, cy, text=icon or "★", fill=GOLD,
            font=self._font(("Segoe UI Symbol", 26)))
        label = self.canvas.create_text(
            cx - 122, cy - 12, anchor="w", text="Has recibido", fill=MUTED,
            font=self._font(("Segoe UI", 10)))
        title = self.canvas.create_text(
            cx - 122, cy + 10, anchor="w", text=name, fill=GOLD,
            font=self._font(("Georgia", 15, "bold")))
        ambience.play("chime")
        for item in (card, glyph, label, title):
            self.canvas.tag_raise(item)

    # -- efectos ----------------------------------------------------------------

    def _shake(self, frame: int = 0) -> None:
        if self._closed or frame > 10 or self.portrait is None:
            return
        offset = (7 if frame % 2 == 0 else -7) * (1 - frame / 10)
        try:
            self.portrait.place(self.centre + offset,
                                self._floor_for(self.portrait.step))
            self.app.after(28, lambda: self._shake(frame + 1))
        except tk.TclError:
            return

    def _flash(self) -> None:
        veil = self.canvas.create_rectangle(0, 0, self.width, self.height,
                                            fill=GOLD_PALE, outline="")
        self.canvas.tag_lower(veil, self.box)

        def fade(step: int = 0) -> None:
            if self._closed or step > 12:
                try:
                    self.canvas.delete(veil)
                except tk.TclError:
                    pass
                return
            try:
                self.canvas.itemconfigure(
                    veil, fill=mix(GOLD_PALE, self.backdrop, step / 12))
                self.app.after(38, lambda: fade(step + 1))
            except tk.TclError:
                return

        fade()

    # -- el humo -----------------------------------------------------------------

    PUFF_POINTS = 14

    def _make_smoke(self) -> None:
        """
        Las volutas, repartidas sobre el cuerpo y no todas en un punto.

        Lo que tiene que parecer es que se deshace él, no que alguien tiró una
        bomba de humo a sus pies. Cada una lleva su propio perfil irregular,
        sorteado una sola vez: recalcularlo en cada cuadro las haría latir a
        todas juntas.
        """
        rng = random.Random(4)
        self.smoke = []
        unit = max(14.0, self.portrait.height * 0.09)
        top = self.ground - self.portrait.height
        for index in range(40):
            item = self.canvas.create_polygon(0, 0, 1, 1, 2, 2, fill="",
                                              outline="", smooth=True,
                                              splinesteps=12)
            self.canvas.tag_lower(item, self.box)
            self.smoke.append({
                "item": item,
                "x": self.centre + rng.uniform(-2.0, 2.0) * unit,
                "y": rng.uniform(top, self.ground),
                "size": rng.uniform(0.5, 1.2) * unit,
                "rise": rng.uniform(0.3, 0.9) * self.height * 0.5,
                "drift": rng.uniform(-2.2, 2.2) * unit,
                "spin": rng.uniform(-0.7, 0.7),
                "delay": index / 60.0 + rng.uniform(0.0, 0.14),
                "profile": [rng.uniform(0.82, 1.16)
                            for _ in range(self.PUFF_POINTS)]})

    def _puff(self, position: float, ember: bool = False) -> None:
        """Mover y agrandar el humo. Nunca opaco: se lee por acumulación."""
        if not self.smoke:
            self._make_smoke()
        pale = "#C2B6AA" if not ember else "#E88A34"
        dark = "#4A423E" if not ember else "#8A3410"
        for puff in self.smoke:
            local = (position - puff["delay"]) / max(0.15, 1.0 - puff["delay"])
            if local <= 0:
                continue
            local = min(1.0, local)
            radius = puff["size"] * (0.45 + 1.5 * local)
            cx = puff["x"] + puff["drift"] * local
            cy = puff["y"] - puff["rise"] * local * local
            spin = puff["spin"] * local * 2.2
            points: List[float] = []
            for index, wobble in enumerate(puff["profile"]):
                angle = spin + index * 2.0 * math.pi / self.PUFF_POINTS
                points.append(cx + math.cos(angle) * radius * wobble
                              * (1.0 + 0.5 * local))
                points.append(cy + math.sin(angle) * radius * wobble
                              * (1.0 - 0.25 * local))
            strength = math.sin(math.pi * local) ** 0.8
            colour = mix(self.backdrop, mix(dark, pale, local), strength * 0.24)
            try:
                self.canvas.coords(puff["item"], *points)
                self.canvas.itemconfigure(puff["item"], fill=colour,
                                          outline=colour)
            except tk.TclError:
                return

    # -- la salida ----------------------------------------------------------------

    LEAVE_FRAMES = {"smoke": 84, "recede": 92, "vanish": 52, "ascend": 86,
                    "burn": 62}

    def _leave(self) -> None:
        self.phase = "leave"
        self.tick = 0
        self._hide_box()
        if self.bed:
            ambience.stop(self.bed)
        self._cue(self.exit_sound)

    def _step_leave(self) -> None:
        steps = self.LEAVE_FRAMES.get(self.departure, 40)
        position = min(1.0, self.tick / steps)
        portrait = self.portrait

        if self.departure in ("smoke", "burn"):
            self._puff(position, ember=self.departure == "burn")
            # El humo apaga al que se va en silencio; el fuego no. Cuando se
            # va ardiendo se queda con la cara que tenía --- que es toda la
            # escena --- y lo único que lo tapa son las brasas.
            if (self.departure == "smoke" and position > 0.4
                    and portrait.pose != "oscuro"):
                portrait.show("oscuro", portrait.step)
                self._settle(portrait.step)
            if position > (0.86 if self.departure == "burn" else 0.78):
                portrait.hide()
        elif self.departure == "recede":
            self._recede(position)
        elif self.departure == "vanish":
            # Cerrás los ojos y ya no está. Sin humo, sin pasos, sin nada:
            # es la salida de alguien que nunca hizo ruido para entrar.
            #
            # El negro se cierra **y se queda**. La primera versión lo volvía
            # a abrir sobre el escenario vacío y después lo cerraba otra vez
            # para terminar, así que se veían dos pestañeos y un hueco en el
            # medio --- que es justo lo contrario de desaparecer.
            self._eyelids(min(1.0, position * 2.2))
            if position > 0.45:
                portrait.hide()
        elif self.departure == "ascend":
            portrait.place(self.centre,
                           self.ground - (self.ground + 240) * position ** 2.2)

        if position >= 1.0:
            over = self.tick - steps
            # Las salidas que ya terminan en negro no vuelven a cerrar nada.
            if self.departure not in ("vanish",):
                self._eyelids(min(1.0, over / 12.0))
            if over >= 12:
                self._done()

    def _recede(self, position: float) -> None:
        """La partida en dos parpadeos: lejos, más lejos, ya no está."""
        for index, mark in enumerate((0.28, 0.62)):
            local = (position - mark) * 12
            if 0 <= local <= 1:
                self._eyelids(math.sin(math.pi * local))
                if abs(local - 0.5) < 0.09:
                    step = 1 - index
                    self.portrait.show("oscuro", max(0, step))
                    self._settle(max(0, step))
                return
        self._eyelids(0.0)
        if position > 0.84:
            self.portrait.hide()

    def _done(self) -> None:
        finish, self.on_done = self.on_done, None
        if self.blackout:
            # Atrás viene otra escena. La pantalla se queda en negro, se le
            # avisa a quien corresponda --- que va a abrir la que sigue
            # encima de ésta --- y recién después esta escena se muere. Así
            # nunca se ve el programa entre una y otra.
            self._eyelids(1.0)
            if finish is not None:
                finish()
            try:
                # Bien después de que la que sigue se haya dibujado encima.
                # Con 120 ms moría antes, y en ese hueco se veía la
                # aplicación por un cuadro --- el parpadeo del lobby.
                self.app.after(600, lambda: self.close(release=False))
            except tk.TclError:
                self.close(release=False)
            return

        def close_now() -> None:
            self.close()
            if finish is not None:
                finish()

        try:
            self.app.after(260, close_now)
        except tk.TclError:
            close_now()


# ---------------------------------------------------------------------------
# Las escenas concretas
# ---------------------------------------------------------------------------

#: Cómo se ve y cómo suena cada personaje al aparecer y al irse.
STAGING = {
    # El señor llega desde el fondo del valle y se deshace en humo. Las dos
    # cosas dicen lo mismo de él: que estaba antes de que uno lo viera, y que
    # no se va a ninguna parte.
    story.DEVIL: dict(sky="valley", bed="valley", entrance="approach",
                      departure="smoke", enter_sound="wind",
                      exit_sound="wind"),
    # El guitarrista aparece desde lejos, sin ruido de llegada, y se va por
    # donde vino. La cama es la misma del valle: su escena quedaba en
    # silencio absoluto entre línea y línea, que no se lee como intimidad
    # sino como que se rompió el sonido.
    story.DJANGO: dict(sky="room", bed="valley", entrance="approach",
                       departure="vanish", enter_sound="", exit_sound="sax"),
    # El señor también se desvanece cuando lo ignoran: mandarlo caminando
    # hasta el horizonte le daba una despedida larga que no se ganó.
    # La figura de luz ya está cuando la oscuridad se abre, y vuelve a subir.
    # **Sin cama**: lo suyo es el coro, y el coro entra cuando él entra y
    # vuelve a sonar cuando se va. Con la cama debajo el coro quedaba
    # enterrado en un bordón que además se repetía sin parar, y toda la
    # escena sonaba a una sola nota larga.
    story.JESUS: dict(sky="heaven", bed="", entrance="descend",
                      departure="ascend", enter_sound="choir_up",
                      exit_sound="choir_down"),
    # Las tres visitas comparten fondo: el negro.
    #
    # **Los dos maestros están y dejan de estar, en un pestañeo.** No se los
    # ve venir de lejos ni irse caminando: la pantalla se abre y ya están
    # parados ahí, y cuando terminan de hablar uno cierra los ojos y no
    # quedó nadie. El acercamiento --- que es la entrada del señor del
    # sombrero --- cuenta una historia que no es la de ellos: la de algo que
    # se viene acercando hace rato. Éstos no se acercan. Aparecen.
    #
    # Bach no tiene cama de ambiente: lo suyo es el clave, que entra con él.
    # Un bordón repitiéndose debajo de un arpegio de cuerda pulsada se come
    # el arpegio entero.
    visitors.BACH: dict(sky="void", bed="", entrance="present",
                        departure="vanish", enter_sound="clavier",
                        exit_sound="clavier"),
    # Gregorio tampoco: lo suyo es el organum, y la escena tiene que quedar
    # tan vacía como el canto que viene a explicar.
    visitors.GREGORY: dict(sky="void", bed="", entrance="present",
                           departure="vanish", enter_sound="plainchant",
                           exit_sound="plainchant"),
    # La entidad sí, y es lo único que la sostiene: sin el bordón debajo, un
    # personaje que no se mueve y no tiene fondo se lee como una imagen
    # pegada. Se va como vino --- no se lo ve irse ---, así que su salida es
    # el pestañeo y nada más.
    # Y llega de **un** salto, no de dos: se pestañea una vez y ya está
    # encima, con la campana. Los dos saltos del señor del sombrero cuentan a
    # alguien que se viene acercando desde hace rato; ella no se acerca ---
    # dice que estuvo mirando todo el tiempo, así que aparecer a media
    # distancia y después acercarse la contradecía.
    visitors.WATCHER: dict(sky="void", bed="hollow", entrance="approach",
                           leap=True, departure="vanish", enter_sound="toll",
                           exit_sound="toll"),
}


def staging_for(speaker: str) -> dict:
    return dict(STAGING.get(speaker, STAGING[story.DEVIL]))


def offer(app, on_choice: Callable[[str], None], font_scale: float = 1.0
          ) -> Cutscene:
    """El ofrecimiento: la única aparición sin ruido de llegada."""
    setup = staging_for(story.DEVIL)
    setup["enter_sound"] = ""
    scene = Cutscene(app, story.OFFER, speaker=story.DEVIL,
                     choices=story.CHOICES, on_choice=on_choice,
                     font_scale=font_scale,
                     dream=story.dream_line(story.DEVIL, 0),
                     title="—  algo interrumpe el trabajo  —", **setup)
    scene.start()
    return scene


def speak(app, speaker: str, lines: Sequence[story.Line], *,
          on_done: Optional[Callable[[], None]] = None,
          keepsake: Tuple[str, str] = ("", ""),
          reveal_name: str = "", title: str = "",
          entrance: str = "", departure: str = "", sky: str = "",
          opening=True, blackout: bool = False, dream: str = "",
          font_scale: float = 1.0) -> Optional[Cutscene]:
    """Una escena de diálogo suelta, con la puesta que le toca al personaje."""
    if not lines:
        if on_done is not None:
            on_done()
        return None
    setup = staging_for(speaker)
    if entrance:
        setup["entrance"] = entrance
        # Un salto único es una manera de acercarse, así que pedir otra
        # entrada lo cancela.
        setup.pop("leap", None)
    if departure:
        setup["departure"] = departure
    if sky:
        setup["sky"] = sky
    scene = Cutscene(app, lines, speaker=speaker, on_done=on_done,
                     keepsake=keepsake, reveal_name=reveal_name, title=title,
                     opening=opening, blackout=blackout, dream=dream,
                     font_scale=font_scale, **setup)
    scene.start()
    return scene


# ---------------------------------------------------------------------------
# La visión
# ---------------------------------------------------------------------------

class Vision(SoundCues):
    """
    El camino, el tren y el que se va: una escena sin una sola palabra.

    Es la única cosa del programa que no se puede provocar. Ocurre al abrir
    la ventana, una vez de cada cinco, una sola vez en la vida del programa,
    y después no vuelve nunca. Por eso no tiene cuadro de diálogo, no tiene
    nombre en el cartelito, no tiene rótulo arriba y **no dice nada en
    ninguna parte**: ni sobre el negro del principio ni al terminar. Lo único
    que deja es una anotación en el libro, y hay que ir a encontrarla.

    Está aparte de :class:`Cutscene` porque no comparte casi nada con ella.
    Una escena de diálogo es un personaje que entra, habla y se va; ésta es
    un plano fijo con un tren cruzando el fondo y alguien que se aleja sin
    decir nada. Lo único que se repite es el pestañeo --- cerrar los ojos y
    que al abrirlos algo esté en otro lado --- porque es el idioma con el
    que este programa mueve a la gente por la pantalla.
    """

    WAKE_FRAMES = 40           # lo que tarda en abrirse al principio
    ROAD_FRAMES = 152          # el camino y el tren: cinco segundos
    BLACK_FRAMES = 91          # tres segundos de negro, de golpe y de golpe
    STARE_FRAMES = 92          # el que apareció, quieto, mirando
    HOLD_FRAMES = 46           # lo que se queda quieto entre salto y salto
    # El parpadeo va lento a propósito, y más lento que el de las escenas de
    # diálogo: acá es lo único que pasa en pantalla durante diez segundos, y
    # cuanto más dura menos se parece a un corte de montaje y más a un
    # pestañeo de verdad.
    BLINK_CLOSE = 17
    BLINK_OPEN = 25
    END_FRAMES = 100           # el camino vacío, con la guitarra sonando
    BLACKOUT_FRAMES = 30       # y el negro, antes de devolver el programa

    #: Dónde aparece: divisor del recorte, a qué altura del camino apoya los
    #: pies --- 0 es el horizonte y 1 el pie de la pantalla --- y con qué
    #: pose.
    #:
    #: **Lejos.** Encima de la cámara se lee como un personaje que viene a
    #: hablar, y éste no viene a hablar: está parado en el camino, mirando,
    #: y la distancia es la mitad de lo que lo hace incómodo.
    NEAR = (3, 0.56, "frente")

    #: Por dónde se va yendo. Se da vuelta en el primer salto y **no vuelve a
    #: darse vuelta nunca**: se va, y lo último que se ve de él es la
    #: espalda. Que mirara una última vez desde lejos lo convertía en alguien
    #: que se despide, y éste no se despide.
    WALK = ((4, 0.34, "espalda"),
            (6, 0.17, "espalda"),
            (8, 0.06, "espalda"))

    def __init__(self, app, on_done: Optional[Callable[[], None]] = None):
        self.app = app
        self.on_done = on_done
        self.phase = "wake"
        self.tick = 0
        self.hop = 0
        self.particles: List[dict] = []
        self.blades: List[dict] = []
        self._after: Optional[str] = None
        self._closed = False
        self._bed_on = False
        #: Cuadros que el viento tiene que quedarse callado. Es lo que deja
        #: sonar solo a lo que importa.
        self._bed_hold = 0
        self._image = None
        self._sounded = False
        self._init_cues()

    # -- ciclo de vida ------------------------------------------------------

    def start(self) -> None:
        app = self.app
        app.update_idletasks()
        self.width = max(720, app.winfo_width())
        self.height = max(520, app.winfo_height())
        # Bien arriba: lo que tiene que llenar la pantalla es el camino, que
        # es por donde se va. Un horizonte al medio deja la mitad de la
        # ventana de cielo vacío.
        self.horizon = self.height * 0.44
        self.centre = self.width * 0.5

        bands = SKIES["crossroads"]
        self.canvas = tk.Canvas(app, width=self.width, height=self.height,
                                highlightthickness=0, bd=0, bg=bands[0])
        self.canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        tk.Misc.lift(self.canvas)

        self._draw_night(bands)
        self._draw_road(bands)
        self._draw_train(bands)
        self._draw_grass(bands)
        self._draw_particles()
        # La sombra va **debajo** del retrato y se crea antes que él, que es
        # todo lo que hace falta para que quede abajo: en un lienzo el orden
        # de creación es el orden de dibujo.
        self.shadow = self.canvas.create_oval(0, 0, 0, 0, fill="#0A0A0C",
                                              outline="", state="hidden",
                                              stipple="gray50")
        self.figure = self.canvas.create_image(self.centre, self.height,
                                               anchor="s", state="hidden")
        self._draw_eyelids()
        # Un clic no la saltea. Dura veinte segundos, ocurre una vez en la
        # vida del programa y no pide nada a cambio: lo único que se puede
        # hacer con ella es mirarla.
        self._loop()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._after is not None:
            try:
                self.app.after_cancel(self._after)
            except Exception:                               # noqa: BLE001
                pass
            self._after = None
        # Sólo el bucle: lo que suena una sola vez se deja terminar. El coro
        # con el que se va la figura de luz dura más que la animación de la
        # partida, y cortarlo era lo que se oía como un tijeretazo. Una cola
        # que sigue sonando encima del programa que vuelve, además, tapa la
        # costura entre la escena y la ventana.
        ambience.stop_beds()
        try:
            self.canvas.destroy()
        except tk.TclError:
            pass

    # -- el fondo -----------------------------------------------------------

    def _draw_night(self, bands) -> None:
        """El cielo, las estrellas, la luna y el campo. Una sola vez."""
        steps = 40
        for index in range(steps):
            position = index / (steps - 1)
            colour = (mix(bands[0], bands[1], position * 2.0) if position < 0.5
                      else mix(bands[1], bands[2], (position - 0.5) * 2.0))
            top = self.horizon * position
            self.canvas.create_rectangle(
                0, top, self.width, top + self.horizon / steps + 2,
                fill=colour, outline=colour)
        rng = random.Random(1938)
        for _ in range(110):
            x = rng.uniform(0, self.width)
            y = rng.uniform(4, self.horizon - 10)
            # Las de abajo se apagan: el aire cerca del horizonte se lleva
            # puestas las estrellas de verdad.
            height = 1.0 - y / max(1.0, self.horizon)
            size = 1.0 + rng.random() * 1.7 * height
            self.canvas.create_oval(
                x, y, x + size, y + size, outline="",
                fill=mix(bands[0], "#E8ECFF",
                         0.15 + 0.6 * rng.random() * height))
        self._draw_moon(bands)
        self.canvas.create_rectangle(0, self.horizon, self.width, self.height,
                                     fill=bands[3], outline="")

    #: Dónde está la luna y de qué tamaño. Justo encima del punto de fuga:
    #: el camino se va hacia ella, que es lo único que hace falta para que
    #: una escena vacía tenga un centro.
    MOON_RADIUS = 44

    def _draw_moon(self, bands) -> None:
        """
        La luna llena, perfectamente centrada sobre el final del camino.

        El halo son óvalos macizos, uno adentro del otro, del color del cielo
        hacia el de la luna: el mismo degradado por franjas del cielo pero en
        redondo. Tramarlo no serviría --- el patrón de un `stipple` se ancla
        al lienzo y no a la figura, así que dos formas tramadas iguales
        pintan *los mismos* píxeles y superponerlas no aclara nada.

        La mitad iluminada es un arco de media vuelta con la cuerda cerrada,
        que es lo único que hay que pedirle a Tk para que dibuje media luna.
        """
        moon_y = self.horizon - 132
        sky = self._sky_at(bands, moon_y)
        # Doce anillos y no nueve, y cada uno apenas más claro que el
        # anterior: un halo se tiene que notar sin que se vean los escalones,
        # y la única manera de que un degradado por franjas no muestre las
        # franjas es hacerlas muchas y con poca diferencia entre ellas.
        for step in range(12, 0, -1):
            radius = self.MOON_RADIUS * (1.0 + step * 0.22)
            self.canvas.create_oval(
                self.centre - radius, moon_y - radius,
                self.centre + radius, moon_y + radius,
                fill=mix(sky, "#C9D4E8", 0.012 * (13 - step)), outline="")
        radius = self.MOON_RADIUS
        self.canvas.create_oval(
            self.centre - radius, moon_y - radius,
            self.centre + radius, moon_y + radius,
            fill="#DCE2EE", outline="")
        # Los mares: las manchas grises que tiene la luna de verdad. Sin
        # ellas el disco se lee como un círculo blanco perfecto --- que es
        # justamente lo que la luna no es --- y la escena entera parece
        # dibujada con una regla.
        rng = random.Random(1911)
        for offset_x, offset_y, size in ((-0.30, -0.28, 0.30),
                                         (0.16, -0.34, 0.20),
                                         (-0.10, 0.22, 0.34),
                                         (0.34, 0.16, 0.22),
                                         (-0.42, 0.06, 0.16)):
            cx = self.centre + radius * offset_x
            cy = moon_y + radius * offset_y
            span = radius * size
            self.canvas.create_oval(
                cx - span, cy - span * rng.uniform(0.7, 1.0),
                cx + span * rng.uniform(0.8, 1.1), cy + span,
                fill=mix("#DCE2EE", "#8E99B0", rng.uniform(0.22, 0.40)),
                outline="")

    def _sky_at(self, bands, y: float) -> str:
        position = min(1.0, max(0.0, y / max(1.0, self.horizon)))
        if position < 0.5:
            return mix(bands[0], bands[1], position * 2.0)
        return mix(bands[1], bands[2], (position - 0.5) * 2.0)

    # -- el camino ------------------------------------------------------------

    def _road_half(self, depth: float) -> float:
        """Medio ancho del camino a esta profundidad. 0 es el horizonte."""
        return 12.0 + (self.width * 0.74 - 12.0) * depth

    def _road_y(self, depth: float) -> float:
        return self.horizon + (self.height - self.horizon) * depth

    def _draw_road(self, bands) -> None:
        """
        Un camino de tierra: sin líneas, sin asfalto y sin bordes rectos.

        Se dibuja en franjas de arriba hacia abajo, cada una un poco más
        clara que la anterior: el polvo del piso devuelve la luz de la luna y
        lo lejano se va lavando. Encima van las dos huellas que dejan las
        ruedas y las piedras, con el tamaño creciendo con el cuadrado de la
        distancia --- repartidas parejo se ven como un empedrado.

        Nada de esto se mueve nunca: son figuras del lienzo y quedarse
        quietas no le cuesta nada a la ventana.
        """
        # La tierra, del fondo hacia acá. Apagada: de noche el piso devuelve
        # la luz de la luna y nada más, y un camino claro se lee como de día.
        far, near = "#1B1712", "#382E23"
        bands_count = 16
        for index in range(bands_count):
            top = (index / bands_count) ** 1.8
            bottom = ((index + 1) / bands_count) ** 1.8
            colour = mix(far, near, index / (bands_count - 1))
            self.canvas.create_polygon(
                self.centre - self._road_half(top), self._road_y(top),
                self.centre + self._road_half(top), self._road_y(top),
                self.centre + self._road_half(bottom), self._road_y(bottom),
                self.centre - self._road_half(bottom), self._road_y(bottom),
                fill=colour, outline=colour)

        # Las dos huellas que dejan las ruedas. Van más juntas que los bordes
        # --- es el ancho de un eje, no el del camino --- y se dibujan con
        # las mismas franjas que el piso, cada una un poco más oscura que la
        # tierra *de esa franja*. De un solo color, la huella terminaba negra
        # justo donde el camino es más claro, y se leía como una zanja.
        for side in (-1, 1):
            for index in range(bands_count):
                top = (index / bands_count) ** 1.8
                bottom = ((index + 1) / bands_count) ** 1.8
                ground = mix(far, near, index / (bands_count - 1))
                colour = mix(ground, "#000000", 0.30)
                self.canvas.create_polygon(
                    self.centre + side * self._road_half(top) * 0.40,
                    self._road_y(top),
                    self.centre + side * self._road_half(top) * 0.24,
                    self._road_y(top),
                    self.centre + side * self._road_half(bottom) * 0.24,
                    self._road_y(bottom),
                    self.centre + side * self._road_half(bottom) * 0.40,
                    self._road_y(bottom),
                    fill=colour, outline=colour)

        rng = random.Random(37)
        for _ in range(120):
            depth = rng.random() ** 1.6
            y = self._road_y(depth)
            half = self._road_half(depth)
            x = self.centre + rng.uniform(-half, half)
            size = 0.8 + 5.0 * depth * rng.random()
            colour = mix(mix(far, near, depth), "#8A7A62" if rng.random() < 0.6
                         else "#100D0A", 0.35 + 0.4 * rng.random())
            self.canvas.create_oval(x, y, x + size, y + size * 0.6,
                                    fill=colour, outline="")

    #: Cuántas matas de pasto hay a los costados.
    BLADES = 96

    def _draw_grass(self, bands) -> None:
        """
        El pasto de las banquinas, que es lo único vivo que hay acá.

        Cada mata es un triángulo con la punta suelta: el pie queda fijo y la
        punta va y viene con el viento. Es lo más barato que se puede animar
        en un lienzo --- tres puntos por cuadro --- y alcanza para que el
        campo no se vea pintado.

        Sirve además para tapar el borde del camino, que es una línea recta
        perfecta y se nota.
        """
        rng = random.Random(1911)
        for index in range(self.BLADES):
            depth = rng.random() ** 1.5
            side = -1 if index % 2 else 1
            edge = self._road_half(depth)
            base_x = (self.centre + side * edge
                      + side * rng.uniform(-6.0, self.width * 0.30 * depth))
            if not -40 < base_x < self.width + 40:
                continue
            base_y = self._road_y(depth) + rng.uniform(-4.0, 6.0)
            height = (6.0 + 46.0 * depth) * rng.uniform(0.6, 1.3)
            item = self.canvas.create_polygon(0, 0, 1, 1, 2, 2, outline="",
                                              fill=mix(bands[3], "#697259",
                                                       0.30 + 0.55 * depth))
            self.blades.append({
                "item": item, "x": base_x, "y": base_y, "height": height,
                "width": 1.2 + 3.0 * depth,
                "lean": rng.uniform(-0.25, 0.25),
                "amp": (2.0 + 9.0 * depth) * rng.uniform(0.5, 1.2),
                "phase": rng.uniform(0, math.tau),
                "speed": rng.uniform(0.05, 0.09)})
        self._move_grass()

    def _move_grass(self) -> None:
        for blade in self.blades:
            blade["phase"] += blade["speed"]
            # Una ráfaga no es un vaivén parejo: el seno elevado hace que la
            # mata se quede tumbada y vuelva de golpe.
            push = math.sin(blade["phase"])
            push = push * abs(push) ** 0.4
            tip_x = (blade["x"] + blade["lean"] * blade["height"]
                     + blade["amp"] * push)
            try:
                self.canvas.coords(
                    blade["item"],
                    blade["x"] - blade["width"], blade["y"],
                    tip_x, blade["y"] - blade["height"],
                    blade["x"] + blade["width"], blade["y"])
            except tk.TclError:
                return

    # -- el tren ---------------------------------------------------------------

    #: El tren: cuántos vagones y de qué tamaño. Grande a propósito --- es lo
    #: único que pasa en cinco segundos de plano fijo --- pero siempre en el
    #: horizonte: nunca se acerca.
    CARS = 16
    CAR_WIDTH = 62
    CAR_HEIGHT = 26

    def _draw_train(self, bands) -> None:
        """
        El tren, cruzando el camino allá lejos y perpendicular a él.

        Va de un lado al otro por la línea del horizonte sin acercarse nunca.
        Son cajas con ventanas encendidas, la locomotora adelante con su
        farol y su chimenea, y una hilera de humo que se queda flotando
        detrás.
        """
        self.train: List[int] = []
        top = self.horizon - self.CAR_HEIGHT - 2
        # Los rieles y el terraplén, apenas insinuados: sin ellos el tren
        # flota en el aire.
        self.canvas.create_rectangle(
            0, self.horizon - 3, self.width, self.horizon + 3,
            fill=mix(bands[3], "#2E323D", 0.5), outline="")

        def car(x, width, height, body, windows, lit):
            box = self.canvas.create_rectangle(
                x, self.horizon - height - 2, x + width, self.horizon - 2,
                fill=body, outline=mix(body, "#6A7280", 0.45))
            self.train.append(box)
            for slot in range(windows):
                left = x + width * (0.16 + 0.68 * slot / max(1, windows - 1))
                self.train.append(self.canvas.create_rectangle(
                    left, self.horizon - height + 5, left + 9,
                    self.horizon - height + 14, fill=lit, outline=""))

        # De atrás hacia adelante, así la locomotora queda dibujada encima.
        for index in range(self.CARS, 0, -1):
            car(-index * (self.CAR_WIDTH + 8), self.CAR_WIDTH,
                self.CAR_HEIGHT, "#0F1219", 3, "#E8C77A")
        # La locomotora: más alta, con la chimenea y el farol.
        car(0, self.CAR_WIDTH + 16, self.CAR_HEIGHT + 8, "#151A23", 2,
            "#FFF2C4")
        self.train.append(self.canvas.create_rectangle(
            22, self.horizon - self.CAR_HEIGHT - 22, 34,
            self.horizon - self.CAR_HEIGHT - 8, fill="#151A23", outline=""))
        self.train.append(self.canvas.create_oval(
            self.CAR_WIDTH + 6, self.horizon - 22, self.CAR_WIDTH + 18,
            self.horizon - 10, fill="#FFF6D8", outline=""))
        # El humo, colgado de la chimenea y desarmándose hacia atrás.
        # **Sin humo.** Hubo una hilera de volutas colgadas de la chimenea y
        # se sacó: la locomotora pasa justo por debajo de la luna, y el halo
        # que tiene detrás es más claro que cualquier humo, así que las
        # volutas se veían como una mancha oscura pegada a la luna. A esta
        # distancia y de noche, un tren es una fila de ventanas encendidas y
        # nada más.
        self.train_span = (self.CARS + 2) * (self.CAR_WIDTH + 8)
        # Y todo el tren se corre hasta quedar afuera, del lado izquierdo.
        #
        # La locomotora se dibuja en x = 0, o sea *adentro* de la pantalla, y
        # hasta que el plano no empieza no se mueve nada: lo que se veía era
        # un tren quieto pegado al borde durante el segundo y pico que tardan
        # en abrirse los ojos, y recién después arrancaba. Un tren que aparece
        # frenado y después acelera no es un tren: es un dibujo que se movió.
        #
        # Se corre **lo justo**: hasta que la punta quede unos píxeles afuera
        # y ni uno más. En cinco segundos el tren tiene que entrar entero y
        # salir entero, y cada píxel que se lo aleje de más es un píxel que
        # después le falta para terminar de pasar --- con un corrimiento del
        # largo del tren, lo que se veía era la locomotora asomando cuando la
        # escena ya se estaba yendo a negro.
        edges = [self.canvas.coords(item) for item in self.train]
        front = max(max(shape[0::2]) for shape in edges)
        for item in self.train:
            self.canvas.move(item, -front - 24, 0)

    def _move_train(self) -> None:
        """Cruza la pantalla entera en los cinco segundos que dura el plano."""
        step = (self.width + self.train_span + 80) / float(self.ROAD_FRAMES)
        for item in self.train:
            self.canvas.move(item, step, 0)

    # -- el viento -------------------------------------------------------------

    def _draw_particles(self) -> None:
        rng = random.Random(27)
        for _ in range(26):
            x = rng.uniform(0, self.width)
            y = rng.uniform(self.horizon * 0.5, self.height * 0.9)
            item = self.canvas.create_line(x, y, x + rng.uniform(16, 44), y,
                                           fill="#333849", width=1)
            self.particles.append({"item": item, "x": x, "y": y,
                                   "speed": rng.uniform(1.2, 3.4),
                                   "phase": rng.uniform(0, math.tau),
                                   "sway": rng.uniform(0.3, 1.2)})

    def _move_particles(self) -> None:
        for dot in self.particles:
            dot["phase"] += 0.05
            dot["x"] += dot["speed"] * 2.2
            y = dot["y"] + math.sin(dot["phase"]) * 5.0 * dot["sway"]
            if dot["x"] > self.width + 40:
                dot["x"] = -40
            length = 14 + dot["speed"] * 8
            try:
                self.canvas.coords(dot["item"], dot["x"], y,
                                   dot["x"] + length, y)
            except tk.TclError:
                return

    # -- el párpado ----------------------------------------------------------

    def _draw_eyelids(self) -> None:
        self.lid_top = self.canvas.create_rectangle(
            0, 0, self.width, 0, fill=BLACK, outline="")
        self.lid_bottom = self.canvas.create_rectangle(
            0, self.height, self.width, self.height, fill=BLACK, outline="")
        self._eyelids(1.0)

    def _eyelids(self, amount: float) -> None:
        amount = max(0.0, min(1.0, amount))
        half = self.height * 0.5 * amount
        try:
            self.canvas.coords(self.lid_top, 0, 0, self.width, half)
            self.canvas.coords(self.lid_bottom, 0, self.height - half,
                               self.width, self.height)
            self.canvas.tag_raise(self.lid_top)
            self.canvas.tag_raise(self.lid_bottom)
        except tk.TclError:
            pass

    # -- la figura -----------------------------------------------------------

    def _show(self, plane) -> None:
        """
        Ponerlo en un plano del camino: tamaño, altura, pose y sombra.

        La sombra es un óvalo tramado a sus pies. Sin ella la figura se ve
        pegada encima del camino y no parada sobre él, que es la diferencia
        entre alguien que está ahí y una calcomanía.
        """
        divisor, depth, pose = plane
        image = load_pose(visitors.ROBERT, pose, divisor)
        if image is None:
            return
        self._image = image
        floor = self._road_y(depth)
        width = image.width()
        try:
            self.canvas.itemconfigure(self.figure, image=image, state="normal")
            self.canvas.coords(self.figure, self.centre, floor)
            self.canvas.coords(self.shadow,
                               self.centre - width * 0.42, floor - width * 0.10,
                               self.centre + width * 0.42, floor + width * 0.10)
            self.canvas.itemconfigure(self.shadow, state="normal")
        except tk.TclError:
            return

    def _hide(self) -> None:
        for item in (self.figure, self.shadow):
            try:
                self.canvas.itemconfigure(item, state="hidden")
            except tk.TclError:
                return

    # -- el bucle -------------------------------------------------------------

    def _loop(self) -> None:
        if self._closed:
            return
        try:
            if not self.canvas.winfo_exists():
                return
        except tk.TclError:
            return
        self.tick += 1
        ambience.pump()
        self._start_bed()
        self._pump_cues()
        self._move_particles()
        self._move_grass()
        {"wake": self._step_wake,
         "road": self._step_road,
         "black": self._step_black,
         "stare": self._step_stare,
         "walk": self._step_walk,
         "gone": self._step_gone}.get(self.phase, self._step_gone)()
        try:
            self._after = self.app.after(FRAME, self._loop)
        except tk.TclError:
            return

    def _start_bed(self) -> None:
        """El viento, salvo que esté callado a propósito."""
        if self._bed_hold > 0:
            self._bed_hold -= 1
            return
        if self._bed_on or not ambience.made("gale"):
            return
        ambience.play("gale", loop=True)
        self._bed_on = True

    def _hush(self, frames: int) -> None:
        """
        Apagar el viento durante un rato.

        Es lo único que hace de mezclador acá adentro. MCI no sabe bajarle el
        volumen a un sonido que está sonando ---toca o no toca--- así que
        cuando algo tiene que escucharse por encima del viento, lo que se
        hace es sacar el viento. Y suena mejor que bajarlo: el aire que se
        corta de golpe es, además, la manera más vieja de anunciar que algo
        va a pasar.
        """
        self._bed_hold = frames
        if self._bed_on:
            ambience.stop("gale")
            self._bed_on = False

    def _step_wake(self) -> None:
        self._eyelids(1.0 - self.tick / self.WAKE_FRAMES)
        if self.tick >= self.WAKE_FRAMES:
            self.phase, self.tick = "road", 0

    def _step_road(self) -> None:
        self._move_train()
        # El tren se oye desde que empieza a cruzar, y los búhos un momento
        # después: dos animales contestándose es lo que dice que no hay nadie
        # más.
        if self.tick == 2:
            self._cue("train")
        elif self.tick == 26:
            self._cue("owls")
        if self.tick >= self.ROAD_FRAMES:
            # De golpe. No hay fundido: el corte a negro es lo que convierte
            # un paisaje en una visión.
            self._eyelids(1.0)
            self.phase, self.tick = "black", 0

    def _step_black(self) -> None:
        if self.tick < self.BLACK_FRAMES:
            return
        # Y de golpe vuelve, con alguien parado en el medio del camino que
        # antes no estaba.
        self._show(self.NEAR)
        self._eyelids(0.0)
        self.phase, self.tick = "stare", 0
        if not self._sounded:
            self._sounded = True
            # **Se corta el viento.** El ruido de la aparición tiene que
            # llegar solo: con la cama debajo se lo comía entera, y encima
            # el silencio repentino hace la mitad del trabajo. El aire vuelve
            # cinco segundos más tarde, cuando él ya está parado ahí.
            self._hush(150)
            self._cue("crossroads")

    def _step_stare(self) -> None:
        """Se queda mirando. No hace nada más, y dura a propósito."""
        if self.tick >= self.STARE_FRAMES:
            self.phase, self.tick, self.hop = "walk", 0, 0

    def _step_walk(self) -> None:
        """
        Se da vuelta y se va, un pestañeo por vez.

        Nunca se lo ve caminar. Cada vez que uno cierra los ojos está más
        lejos, y a la última se da vuelta para mirar. Es el mismo gesto con
        el que entra el señor del sombrero, al revés.
        """
        cycle = self.HOLD_FRAMES + self.BLINK_CLOSE + self.BLINK_OPEN + 2
        position = self.tick % cycle
        if position < self.HOLD_FRAMES:
            return
        step = position - self.HOLD_FRAMES
        if step <= self.BLINK_CLOSE:
            self._eyelids(step / self.BLINK_CLOSE)
            return
        if step == self.BLINK_CLOSE + 1:
            # Con los ojos cerrados: el salto ocurre acá, sin que se vea.
            if self.hop < len(self.WALK):
                self._show(self.WALK[self.hop])
            else:
                self._hide()
                # Y cuando ya no está queda la guitarra, **sola**: el viento
                # se va con él. Es lo único que se parece a música en toda la
                # escena y llega cuando el que la tocaba ya se fue, que es
                # exactamente lo que la leyenda dice de él.
                self._hush(10 ** 6)
                self._cue("blues", patience=30)
            self.hop += 1
        opened = step - self.BLINK_CLOSE
        self._eyelids(max(0.0, 1.0 - opened / self.BLINK_OPEN))
        if opened >= self.BLINK_OPEN and self.hop > len(self.WALK):
            self.phase, self.tick = "gone", 0

    def _step_gone(self) -> None:
        """
        El camino vacío con la guitarra sonando, y después el negro.

        Los tres segundos y medio de camino sin nadie son la mitad de la
        escena: es donde el blues suena solo y donde se entiende que lo que
        se fue no va a volver. Y el final es **de golpe** --- un pantallazo
        negro, no un fundido --- porque la visión no termina: se corta.
        """
        if self.tick < self.END_FRAMES:
            return
        self._eyelids(1.0)
        if self.tick - self.END_FRAMES >= self.BLACKOUT_FRAMES:
            self._done()

    def _done(self) -> None:
        finish, self.on_done = self.on_done, None

        def close_now() -> None:
            self.close()
            if finish is not None:
                finish()

        try:
            self.app.after(260, close_now)
        except tk.TclError:
            close_now()


def vision(app, on_done: Optional[Callable[[], None]] = None) -> Vision:
    """La visión del cruce de caminos. Una vez, y nunca más."""
    scene = Vision(app, on_done=on_done)
    scene.start()
    return scene
