# -*- coding: utf-8 -*-
"""
Preguntar si salió una versión más nueva.

La página publica un `version.json` con la última versión, a dónde mandar a
quien la quiera y una línea de qué trae. Este módulo lo pide, lo compara con
:data:`engine.__version__` y contesta una de dos cosas: nada, o la versión
nueva. Quién muestra el cartel es :mod:`updater`; acá no se dibuja nada.

Cómo está armado
----------------
* :func:`start` dispara la consulta en un hilo y vuelve enseguida. Se la
  llama antes de armar la ventana, así la espera se solapa con el arranque
  y no se le suma.
* :func:`answer` es la que espera --- lo que quede del presupuesto, y no
  más. Si la red no contestó a tiempo, devuelve ``None`` y el programa
  arranca como si nada: **un aviso no vale una demora**.
* :func:`enabled` decide si se pregunta. Desde el fuente no se pregunta
  nunca; en el ejecutable, sí. `CHORDWEAVER_UPDATE_CHECK` fuerza las dos
  cosas, que es la única manera de probar el cartel sin compilar.

Nada de esto descarga nada. Lo único que viaja es un pedido de lectura de
un archivo de veinte líneas, y la respuesta se lee con un tope: un servidor
que devuelva un archivo de un giga no puede colgar el arranque.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from . import __version__

#: De dónde sale la respuesta. Es un archivo de la propia página, y no la
#: API de GitHub, por dos motivos: no tiene límite de pedidos por hora y lo
#: controla quien publica --- una release puede existir sin estar todavía
#: anunciada, y ese día el aviso no tiene que salir.
FEED = "https://chordweaver.github.io/version.json"

#: Cuánto se espera a la red, en segundos. Cuatro es de sobra para un
#: archivo de veinte líneas y poco para que alguien lo note, porque además
#: corre mientras la ventana se arma.
TIMEOUT = 4.0

#: Lo máximo que se lee de la respuesta. El archivo real no llega al
#: kilobyte.
MAX_BYTES = 64 * 1024

#: El interruptor de la variable de entorno. `1` pregunta siempre --- que
#: es como se prueba el cartel desde el fuente --- y `0` no pregunta nunca.
SWITCH = "CHORDWEAVER_UPDATE_CHECK"

#: De dónde leer, si no es de la página. Existe para poder probar el cartel
#: contra un archivo puesto a mano ---también un `file://`--- sin publicar
#: nada ni tocar el código.
FEED_VARIABLE = "CHORDWEAVER_UPDATE_FEED"

_TRUE = ("1", "si", "sí", "on", "true", "yes")
_FALSE = ("0", "no", "off", "false")


@dataclass(frozen=True)
class Release:
    """La versión que hay publicada, tal como la cuenta la página."""

    version: str
    page: str
    notes: str
    download: str
    headline: str
    released: str = ""
    #: La línea en cada idioma que publica el archivo, como pares
    #: ``(idioma, texto)``. Se elige al mostrarla y no al leerla: la consulta
    #: arranca antes de que el usuario elija idioma la primera vez, y
    #: eligiéndola acá un programa en inglés anunciaba en castellano.
    headlines: Tuple[Tuple[str, str], ...] = ()

    def headline_in(self, language: str) -> str:
        """La línea en ese idioma, o la de siempre si no la hay."""
        for code, text in self.headlines:
            if code == language:
                return text
        return self.headline


def feed() -> str:
    """La dirección del archivo: la de la página, o la que pida el entorno."""
    return os.environ.get(FEED_VARIABLE, "").strip() or FEED


def enabled() -> bool:
    """Si corresponde preguntar."""
    raw = os.environ.get(SWITCH, "").strip().lower()
    if raw in _FALSE:
        return False
    if raw in _TRUE:
        return True
    # Desde el fuente no se pregunta: quien lo corre así lo está
    # desarrollando, y su copia es por definición más nueva que la
    # publicada. En el ejecutable, sí.
    return bool(getattr(sys, "frozen", False))


def _parts(version: str) -> Tuple[int, ...]:
    """`"1.0.1"` → `(1, 0, 1)`. Lo que no sea número vale cero."""
    out = []
    for chunk in str(version).strip().split("."):
        digits = ""
        for char in chunk:
            if not char.isdigit():
                break
            digits += char
        out.append(int(digits) if digits else 0)
    return tuple(out)


def newer(candidate: str, current: str) -> bool:
    """Si `candidate` es posterior a `current`.

    Se comparan de a números y rellenando con ceros, así que `1.1` gana a
    `1.0.1` y `1.1` **no** gana a `1.1.0`: son la misma.
    """
    a, b = _parts(candidate), _parts(current)
    largo = max(len(a), len(b))
    a += (0,) * (largo - len(a))
    b += (0,) * (largo - len(b))
    return a > b


def _headlines(raw) -> Tuple[Tuple[str, str], ...]:
    """La línea de qué trae, por idioma."""
    if not isinstance(raw, dict):
        return ()
    return tuple((str(code), value.strip()) for code, value in raw.items()
                 if isinstance(value, str) and value.strip())


def _headline(raw) -> str:
    """La línea de qué trae. El archivo la publica por idioma."""
    if isinstance(raw, dict):
        for key in ("es", "en"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
    return raw.strip() if isinstance(raw, str) else ""


def fetch(url: Optional[str] = None,
          timeout: float = TIMEOUT) -> Optional[Dict]:
    """Traer el archivo. Cualquier problema es un `None`, nunca una excepción."""
    pedido = urllib.request.Request(
        url or feed(),
        headers={"User-Agent": "ChordWeaver/%s" % __version__,
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as respuesta:
            crudo = respuesta.read(MAX_BYTES)
        datos = json.loads(crudo.decode("utf-8"))
    except Exception:                                       # noqa: BLE001
        # Sin internet, con un proxy de por medio, con el archivo a medio
        # publicar o con la página caída: en todos los casos lo correcto es
        # abrir el programa sin decir nada.
        return None
    return datos if isinstance(datos, dict) else None


def look(current: str = __version__, url: Optional[str] = None,
         timeout: float = TIMEOUT) -> Optional[Release]:
    """La versión publicada, si es más nueva que la que corre."""
    datos = fetch(url, timeout)
    if not datos:
        return None
    version = str(datos.get("version", "")).strip()
    if not version or not newer(version, current):
        return None
    page = str(datos.get("page", "")).strip()
    if not page.startswith("https://"):
        # Sin una página a dónde mandar, el cartel no tiene botón. Y sólo
        # `https`: el aviso termina en un navegador que se abre solo.
        return None
    return Release(version=version, page=page,
                   notes=str(datos.get("notes", "")).strip() or page,
                   download=str(datos.get("download", "")).strip(),
                   headline=_headline(datos.get("headline")),
                   headlines=_headlines(datos.get("headline")),
                   released=str(datos.get("released", "")).strip())


# ---------------------------------------------------------------------------
# La consulta en segundo plano
# ---------------------------------------------------------------------------
#
# El hilo es demonio a propósito: si el usuario cierra el programa mientras
# la red piensa, el proceso tiene que poder terminar igual.

_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_answer: Optional[Release] = None


def start(current: str = __version__) -> None:
    """Disparar la consulta. Vuelve enseguida; nunca levanta nada."""
    global _thread
    if not enabled():
        return
    with _lock:
        if _thread is not None:
            return

        def trabajo() -> None:
            global _answer
            resultado = look(current)
            with _lock:
                _answer = resultado

        _thread = threading.Thread(target=trabajo, name="chordweaver-updates",
                                   daemon=True)
        _thread.start()


def answer(budget: float = 2.0) -> Optional[Release]:
    """
    Lo que contestó la consulta, esperándola como mucho `budget` segundos.

    Si todavía no contestó, devuelve `None` y se sigue de largo: el hilo
    queda dando vueltas hasta que la red conteste o el proceso termine, y su
    respuesta tardía no le importa a nadie.
    """
    hilo = _thread
    if hilo is None:
        return None
    if hilo.is_alive():
        hilo.join(max(0.0, budget))
    with _lock:
        return _answer
