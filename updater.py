# -*- coding: utf-8 -*-
"""
El cartel de «hay una versión nueva», antes de que el programa se abra.

:mod:`engine.updates` pregunta y contesta; acá se dibuja lo único que se ve.

**El cartel vive en su propia ventana y `ChordWeaverApp` todavía no existe
cuando aparece.** No es un detalle de presentación: armar la aplicación deja
timers puestos ---el tutorial de la primera vez, la visión del arranque, las
visitas--- y un `wait_window` sobre una ventana ya construida es un bucle de
eventos como cualquier otro, así que esos timers dispararían **detrás del
cartel**: alguien se encontraría con una cinemática empezada y un velo de
tutorial encima antes de haber contestado. Por eso :func:`greet` no recibe
la aplicación: se lo llama antes de crearla, y su respuesta decide si se la
crea.

Dos botones y nada más:

* **Actualizar** abre la página en el navegador y **no** abre el programa.
  No abrirlo es parte del gesto: quien va a reemplazar la carpeta no puede
  hacerlo con el ejecutable en uso.
* **Ahora no** cierra el cartel y el programa se abre como cualquier otro
  día. No se vuelve a preguntar hasta el próximo arranque.

Como :mod:`spectrum` y :mod:`analyzer`, este módulo **no importa
``app``**: recibe la paleta por parámetro. Y como todo lo que toca la red,
no puede impedir que el programa arranque: cualquier problema termina en un
``True`` --- abrirlo igual --- y en silencio.
"""

from __future__ import annotations

import webbrowser
from typing import Callable, Dict, Optional

import customtkinter as ctk

from engine import __version__ as APP_VERSION
from engine import updates
from engine.i18n import tr, trf, trs

#: Cuánto se espera a la consulta antes de abrir la ventana igual. Corre
#: desde que arrancó el programa, así que casi siempre ya está contestada
#: para cuando se llega acá.
BUDGET = 2.0

WIDTH = 560

#: El alto mínimo. El de verdad lo pide el contenido: la línea de qué trae
#: la versión nueva la escribe quien publica y puede ocupar dos renglones o
#: cuatro, y un alto fijo le corta el último o le deja media ventana vacía.
MIN_HEIGHT = 250

#: Cuanto espera el enganche de pruebas antes de tocar la ventana. Ver
#: `notice`: no puede ser cero.
READY_DELAY_MS = 500

#: La paleta de reserva, para cuando a `greet` no le pasan ninguna. Es la de
#: la aplicación; la de verdad llega por parámetro justamente para que
#: cambiarla allá alcance.
FALLBACK = {
    "surface": "#1B1D22",
    "panel": "#25282F",
    "text": "#E6E8EB",
    "muted": "#98A0AC",
    "accent": "#5B8FD6",
    "accent_hover": "#6FA0E2",
    "border": "#353942",
    "gold": "#E8C97A",
}


def _hand_back_the_scaling_loop() -> None:
    """
    Devolverle a customtkinter el permiso de volver a mirar el DPI.

    El vigilante de escala es **uno solo para todas las ventanas**: se
    reagenda sobre cualquiera que siga viva y, cuando no queda ninguna, baja
    una bandera para que la proxima que se abra lo vuelva a levantar. Cerrar
    la ultima ventana que hay lo deja a mitad de camino ---la bandera arriba
    y ninguna ventana donde correr--- y entonces la ventana de la aplicacion,
    que se abre despues, no lo reanuda: el programa deja de enterarse de que
    alguien cambio la escala de su pantalla mientras estaba abierto.

    Esto es exactamente lo que hace `check_dpi_scaling` cuando se queda sin
    ventanas, hecho desde afuera porque el cartel es la unica que hay.
    """
    try:
        from customtkinter.windows.widgets.scaling.scaling_tracker import (
            ScalingTracker)
        if not ScalingTracker.window_widgets_dict:
            ScalingTracker.update_loop_running = False
    except Exception:                                       # noqa: BLE001
        # Una version de customtkinter que lo haya movido de lugar. Lo unico
        # que se pierde es una comodidad, y no vale un arranque roto.
        pass


def _centre(window, width: int, height: int) -> None:
    """Al medio de la pantalla, que es donde se mira cuando no hay nada más."""
    x = max(0, (window.winfo_screenwidth() - width) // 2)
    y = max(0, (window.winfo_screenheight() - height) // 3)
    window.geometry("%dx%d+%d+%d" % (width, height, x, y))


def notice(release: updates.Release, colours: Dict[str, str],
           current: str = APP_VERSION,
           open_page: Callable[[str], object] = webbrowser.open,
           on_ready: Optional[Callable[[object], object]] = None) -> bool:
    """
    Mostrar el cartel y contestar si el programa se abre.

    Devuelve `True` para abrirlo y `False` cuando el usuario eligió
    actualizar --- en ese caso la página ya se abrió y no hay que armar
    ninguna ventana más.

    La ventana del cartel es su **propia** raíz de Tk, con su propio bucle
    de eventos, y se destruye antes de volver: mientras está en pantalla no
    hay ninguna otra ventana viva que pueda tener un timer puesto.
    """
    fuente = colours.get("font") or (lambda spec: spec)
    seguir = {"valor": True}

    cartel = ctk.CTk(fg_color=colours["surface"])
    cartel.title("ChordWeaver")
    cartel.resizable(False, False)

    caja = ctk.CTkFrame(cartel, fg_color=colours["panel"], corner_radius=14,
                        border_width=1, border_color=colours["border"])
    caja.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(caja, text=tr("Hay una versión nueva"),
                 font=fuente(("Segoe UI Semibold", 20)),
                 text_color=colours["text"]).pack(anchor="w", padx=26,
                                                  pady=(24, 2))
    ctk.CTkLabel(caja,
                 text="ChordWeaver %s  ·  la tuya es la %s"
                      % (release.version, current),
                 font=fuente(("Segoe UI", 12)),
                 text_color=colours["gold"]).pack(anchor="w", padx=26,
                                                  pady=(0, 14))

    if release.headline:
        ctk.CTkLabel(caja, text=release.headline, justify="left", anchor="w",
                     wraplength=WIDTH - 90, font=fuente(("Segoe UI", 13)),
                     text_color=colours["text"]).pack(anchor="w", padx=26,
                                                      pady=(0, 10))

    ctk.CTkLabel(caja,
                 text=tr("No perdés tu progreso. Los logros, el libro, el "
                         "sendero y el historial se pasan a la carpeta nueva, "
                         "y la página explica cómo."),
                 justify="left", anchor="w", wraplength=WIDTH - 90,
                 font=fuente(("Segoe UI", 12)),
                 text_color=colours["muted"]).pack(anchor="w", padx=26,
                                                   pady=(0, 20))

    botones = ctk.CTkFrame(caja, fg_color="transparent")
    botones.pack(fill="x", padx=26, pady=(0, 22))

    def cerrar() -> None:
        # Primero se esconde: es lo que el usuario ve, y tiene que pasar
        # aunque lo que sigue falle. Con todo en un mismo `try`, un error en
        # `quit()` salteaba el `destroy()` y el cartel quedaba en pantalla al
        # lado del programa, que se abría igual: dos ventanas.
        try:
            cartel.withdraw()
        except Exception:                                   # noqa: BLE001
            pass
        # `quit()` antes de `destroy()`: el primero termina el bucle y el
        # segundo desarma la ventana. Sólo con `destroy()`, un `after` que
        # quedara pendiente se ejecutaría sobre widgets que ya no están.
        # Cada uno en su `try`, por lo mismo.
        try:
            # Los `after` que quedan puestos ---los de customtkinter, que se
            # reagendan solos--- se cancelan antes de destruir la ventana. Si
            # no, el que llegue tarde se ejecuta contra un interprete que ya
            # no esta y Tcl escribe el error por la salida de errores.
            for pendiente in cartel.tk.call("after", "info"):
                try:
                    cartel.after_cancel(pendiente)
                except Exception:                           # noqa: BLE001
                    continue
        except Exception:                                   # noqa: BLE001
            pass
        for paso in (cartel.quit, cartel.destroy):
            try:
                paso()
            except Exception:                               # noqa: BLE001
                continue

    def quedarse() -> None:
        seguir["valor"] = True
        cerrar()

    def actualizar() -> None:
        seguir["valor"] = False
        try:
            open_page(release.page)
        except Exception:                                   # noqa: BLE001
            # Si el navegador no abre, no abrir el programa sería dejar al
            # usuario sin las dos cosas. Se abre como si nada.
            seguir["valor"] = True
        cerrar()

    ctk.CTkButton(botones, text=tr("Actualizar"), width=150, height=38,
                  corner_radius=10, font=fuente(("Segoe UI Semibold", 13)),
                  fg_color=colours["accent"],
                  hover_color=colours["accent_hover"],
                  text_color="#0C1016",
                  command=actualizar).pack(side="left")
    ctk.CTkButton(botones, text=tr("Ahora no"), width=120, height=38,
                  corner_radius=10, font=fuente(("Segoe UI", 13)),
                  fg_color="transparent", border_width=1,
                  border_color=colours["border"],
                  text_color=colours["muted"],
                  hover_color=colours["surface"],
                  command=quedarse).pack(side="left", padx=10)

    # El alto sale de lo que ocupó el contenido, y recién ahora: los
    # `wraplength` de arriba no saben en cuántos renglones cayeron hasta que
    # Tk los acomoda.
    cartel.update_idletasks()
    _centre(cartel, WIDTH, max(MIN_HEIGHT, caja.winfo_reqheight() + 32))

    # Cerrar el cartel con la cruz o con Escape es «ahora no». Lo contrario
    # ---tomarlo por una respuesta que no dio--- cerraría el programa de
    # alguien que sólo quiso sacarse el cartel de encima.
    cartel.protocol("WM_DELETE_WINDOW", quedarse)
    cartel.bind("<Escape>", lambda _event: quedarse())

    cartel.lift()
    cartel.attributes("-topmost", True)
    cartel.after(200, lambda: cartel.attributes("-topmost", False))
    cartel.focus_force()
    # El enganche del arnes de pruebas: es la unica manera de apretarle un
    # boton a una ventana que se dibuja sola y se queda esperando. Con
    # retraso y no en el primer hueco libre: `CTk.mainloop` empieza
    # acomodando el color de la barra de titulo ---y para eso llama a
    # `update()`---, asi que un `after(0)` corre **antes** de que el bucle
    # arranque y le deja la ventana destruida abajo de los pies.
    if on_ready is not None:
        cartel.after(READY_DELAY_MS, lambda: on_ready(cartel))
    try:
        cartel.mainloop()
    finally:
        # Salga como salga el bucle ---un botón, la cruz, un error---, el
        # cartel no se queda: si no, el programa se abre con él al lado.
        try:
            if cartel.winfo_exists():
                cartel.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        _hand_back_the_scaling_loop()
    return seguir["valor"]


def greet(colours: Optional[Dict[str, str]] = None,
          current: str = APP_VERSION, budget: float = BUDGET) -> bool:
    """
    Preguntar y, si hay algo que decir, decirlo. `True` = abrir el programa.

    Se la llama **antes** de construir `ChordWeaverApp`: hasta que esto no
    conteste no hay ninguna ventana de la aplicación viva, y por lo tanto
    tampoco ningún tutorial ni ninguna escena esperando su turno.

    Todo lo que salga mal acá ---la red, el archivo, el cartel--- termina en
    un `True`: un aviso de versión no puede ser el motivo por el que alguien
    se queda sin abrir el programa.
    """
    try:
        release = updates.answer(budget)
        if release is None:
            return True
        if not updates.newer(release.version, current):
            # La consulta ya comparó contra `engine.__version__`; esto es
            # para cuando `current` es otra cosa ---una prueba, un arranque
            # que quiere fingir otra versión---, y para que el parámetro
            # decida de verdad en vez de decorar el cartel.
            return True
        paleta = dict(FALLBACK)
        if colours:
            paleta.update(colours)
        return notice(release, paleta, current)
    except Exception:                                       # noqa: BLE001
        return True
