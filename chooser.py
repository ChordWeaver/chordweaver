# -*- coding: utf-8 -*-
"""
En qué idioma habla el programa, preguntado una sola vez.

**El cartel sale antes de construir `ChordWeaverApp`, y en su propia raíz de
Tk**, por la misma razón que el de versión nueva: armar la aplicación deja
timers puestos ---el tutorial de la primera vez, la visión del arranque, las
visitas--- y cualquier bucle de eventos posterior los dispara. Preguntando
antes no hay ninguna ventana de la aplicación viva que pueda tener nada
agendado, y además el idioma ya está puesto para cuando se dibuja la primera
letra.

Va **primero de todo**, incluso antes del cartel de versión nueva, que es lo
único que se dibuja antes que la ventana: preguntarlo después dejaría ese
cartel escrito en un idioma que el usuario todavía no eligió.

Se pregunta una sola vez en la vida de una instalación --- después se cambia
desde el engranaje. Cerrar el cartel sin elegir **no** guarda nada: el
programa abre en castellano y vuelve a preguntar la próxima vez, que es lo
correcto para alguien que lo cerró sin querer.

Como :mod:`spectrum`, :mod:`analyzer` y :mod:`updater`, este módulo **no
importa ``app``**: recibe la paleta por parámetro.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

import customtkinter as ctk

from engine import i18n
# La misma copia que usa el cartel de versión nueva, y a propósito una sola:
# son dos arreglos para particularidades de Tk y de customtkinter ---ver
# allá--- y dos copias se desincronizan el día que eso cambie de lugar.
from updater import _centre, _hand_back_the_scaling_loop

WIDTH = 520
MIN_HEIGHT = 300

#: Cuanto espera el enganche de pruebas antes de tocar la ventana. Por lo
#: mismo que en `updater.notice`: no puede ser cero.
READY_DELAY_MS = 500

#: La paleta de reserva, para cuando a `ask` no le pasan ninguna.
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

#: Lo que dice el cartel, en los dos idiomas a la vez y en ese orden. Es la
#: única pantalla del programa que **no** se puede traducir: se dibuja justo
#: antes de que haya un idioma elegido, así que tiene que poder leerla
#: cualquiera de los dos.
TITLE = "Elegí tu idioma"
TITLE_EN = "Choose your language"
BLURB = "Se puede cambiar cuando quieras desde el engranaje."
BLURB_EN = "You can change it any time from the gear."

#: Cómo se presenta cada idioma: una línea escrita en él mismo, que es lo que
#: deja elegir sin entender el resto del cartel.
BLURBS = {
    "es": "Castellano rioplatense, el idioma en el que está escrito el "
          "programa. Las notas se dicen Do, Re, Mi.",
    "en": "American English. Notes are called C, D, E.",
}


def ask(colours: Optional[Dict[str, str]] = None,
        on_ready: Optional[Callable[[object], object]] = None) -> Optional[str]:
    """
    Preguntar el idioma. Devuelve su clave, o `None` si no eligió ninguno.

    `None` significa «no contestó»: quien llama no guarda nada y el programa
    abre en castellano.
    """
    palette = dict(FALLBACK)
    if colours:
        palette.update(colours)
    font = palette.get("font") or (lambda spec: spec)
    picked: Dict[str, Optional[str]] = {"code": None}

    window = ctk.CTk(fg_color=palette["surface"])
    window.title("ChordWeaver")
    window.resizable(False, False)

    box = ctk.CTkFrame(window, fg_color=palette["panel"], corner_radius=14,
                       border_width=1, border_color=palette["border"])
    box.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(box, text=TITLE, font=font(("Segoe UI Semibold", 20)),
                 text_color=palette["text"]).pack(anchor="w", padx=26,
                                                  pady=(24, 0))
    ctk.CTkLabel(box, text=TITLE_EN, font=font(("Segoe UI", 15)),
                 text_color=palette["gold"]).pack(anchor="w", padx=26,
                                                  pady=(0, 16))

    def close() -> None:
        # `quit()` antes de `destroy()`, y las dos entre `try`: igual que en
        # `updater.notice`, y por lo mismo.
        try:
            for pending in window.tk.call("after", "info"):
                try:
                    window.after_cancel(pending)
                except Exception:                           # noqa: BLE001
                    continue
        except Exception:                                   # noqa: BLE001
            pass
        try:
            window.quit()
            window.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    def choose(code: str) -> None:
        picked["code"] = code
        close()

    for code, label in i18n.languages():
        card = ctk.CTkFrame(box, fg_color="transparent", corner_radius=12,
                            border_width=1, border_color=palette["border"])
        card.pack(fill="x", padx=26, pady=5)
        ctk.CTkButton(card, text=label, height=40, corner_radius=10,
                      anchor="w", font=font(("Segoe UI Semibold", 15)),
                      fg_color="transparent", hover_color=palette["surface"],
                      text_color=palette["text"],
                      command=lambda c=code: choose(c)
                      ).pack(fill="x", padx=6, pady=(6, 0))
        ctk.CTkLabel(card, text=BLURBS[code], justify="left", anchor="w",
                     wraplength=WIDTH - 110, font=font(("Segoe UI", 11)),
                     text_color=palette["muted"]
                     ).pack(anchor="w", padx=18, pady=(0, 10))

    ctk.CTkLabel(box, text="%s\n%s" % (BLURB, BLURB_EN), justify="left",
                 anchor="w", font=font(("Segoe UI", 11)),
                 text_color=palette["muted"]).pack(anchor="w", padx=26,
                                                   pady=(14, 22))

    # El alto sale de lo que ocupó el contenido, y recién ahora: los
    # `wraplength` no saben en cuántos renglones cayeron hasta que Tk los
    # acomoda.
    window.update_idletasks()
    _centre(window, WIDTH, max(MIN_HEIGHT, box.winfo_reqheight() + 32))

    # Cerrar sin elegir deja `picked` en `None`, que es «no contestó».
    window.protocol("WM_DELETE_WINDOW", close)
    window.bind("<Escape>", lambda _event: close())

    window.lift()
    window.attributes("-topmost", True)
    window.after(200, lambda: window.attributes("-topmost", False))
    window.focus_force()
    if on_ready is not None:
        window.after(READY_DELAY_MS, lambda: on_ready(window))
    window.mainloop()
    _hand_back_the_scaling_loop()
    return picked["code"]


def settle(settings: Dict[str, object], save,
           colours: Optional[Dict[str, str]] = None) -> str:
    """
    Dejar el idioma puesto, preguntando si es la primera vez.

    Recibe las preferencias ya leídas y con qué guardarlas para no decidir
    acá dónde viven --- eso lo sabe `engine.history`, y el arnés de pruebas
    las manda a un descartable.

    Nada de lo que pase acá puede impedir que el programa abra: cualquier
    problema termina en el idioma de fábrica.
    """
    try:
        stored = str(settings.get("language", "") or "").strip()
        if stored in i18n.codes():
            return i18n.set_language(stored)
        chosen = ask(colours)
        if chosen:
            settings["language"] = chosen
            try:
                save(settings)
            except Exception:                               # noqa: BLE001
                # Una carpeta de sólo lectura no puede ser el motivo por el
                # que el programa no abre; lo único que se pierde es que la
                # próxima vez vuelve a preguntar.
                pass
            return i18n.set_language(chosen)
        return i18n.set_language(i18n.DEFAULT)
    except Exception:                                       # noqa: BLE001
        return i18n.set_language(i18n.DEFAULT)
