# -*- coding: utf-8 -*-
"""
Adónde va lo que el programa escribe en la consola cuando no hay consola.

El ejecutable se compila sin consola (`console=False` en `ChordWeaver.spec`),
y en ese modo PyInstaller deja `sys.stdout` y `sys.stderr` en ``None``. No es
un detalle: cualquier `write` sobre ellos levanta `AttributeError`, y el
programa muere con «Failed to execute script 'app'». Basta con que una
librería avise algo. customtkinter lo hace **al importarse** cuando no puede
cargar su fuente de formas ---Windows no carga fuentes de rutas de más de
260 caracteres, y alcanza con descomprimir el programa dentro de un par de
carpetas largas---, así que el ejecutable ni siquiera abría. Desde el fuente
no pasaba nunca: ahí la consola existe.

`guard_streams()` cambia los ``None`` por un registro en disco. Tiene que
correr **antes** del primer import de customtkinter.
"""

from __future__ import annotations

import io
import os
import sys
from typing import Iterable, Optional

from engine import history

#: El registro, junto a los datos del usuario. Un aviso de una librería o un
#: error tragado por una escena quedan acá en vez de perderse.
LOG_NAME = "chordweaver.log"

#: Pasado este tamaño, el registro arranca de nuevo al abrir el programa.
LOG_LIMIT = 1_000_000


class _Log(io.TextIOBase):
    """
    Un flujo de texto que escribe en el registro, abierto recién al usarse.

    Es un `io.TextIOBase` y contesta lo que se le pregunta a un flujo de
    verdad: hay librerías que miran `sys.stderr.encoding` antes de escribir
    o le piden `fileno()` para pasárselo a otra cosa. Con una clase suelta
    que sólo sabía `write`, cualquiera de esas preguntas era un
    `AttributeError`, y el ejecutable sin consola volvía a morir igual que
    sin este arreglo.
    """

    #: Con qué se escribe el registro, y qué se hace con lo que no entra en
    #: esa codificación: lo mismo que se le pasa a `open`.
    encoding = "utf-8"
    errors = "replace"

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        self._file = None
        self._broken = False

    def _open(self):
        if self._file is None and not self._broken:
            try:
                mode = "a"
                if (os.path.exists(self.path)
                        and os.path.getsize(self.path) > LOG_LIMIT):
                    mode = "w"
                self._file = open(self.path, mode, encoding="utf-8",
                                  errors="replace", buffering=1)
            except OSError:
                # Una carpeta de solo lectura no puede tumbar el programa:
                # se calla y se sigue.
                self._broken = True
        return self._file

    def write(self, text: str) -> int:
        handle = self._open()
        if handle is not None:
            try:
                handle.write(text)
            except (OSError, ValueError):
                pass
        return len(text)

    def writelines(self, lines: Iterable[str]) -> None:
        # La de `IOBase` levanta si el flujo se cerró; ésta, como `write`,
        # no levanta nunca.
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        if self._file is not None:
            try:
                self._file.flush()
            except (OSError, ValueError):
                pass

    def close(self) -> None:
        # `IOBase` llama a esto al recolectar el objeto: sin soltar el
        # archivo, quedaba abierto hasta que lo cerrara el intérprete.
        handle, self._file = self._file, None
        if handle is not None:
            try:
                handle.close()
            except (OSError, ValueError):
                pass
        super().close()

    def writable(self) -> bool:
        return True

    def fileno(self) -> int:
        # No hay descriptor detrás: el archivo se abre recién al escribir, y
        # puede no abrirse nunca. `UnsupportedOperation` es lo que contesta
        # cualquier flujo sin archivo del sistema (`io.StringIO`, por
        # ejemplo), y quien pregunta sabe atajarla; un `AttributeError`, no.
        # El mensaje es el mismo que el de `io.StringIO`: no lo lee nadie.
        raise io.UnsupportedOperation("fileno")

    def isatty(self) -> bool:
        return False


def log_path() -> str:
    return os.path.join(history.base_directory(), LOG_NAME)


def guard_streams(path: Optional[str] = None) -> bool:
    """
    Dar un destino a `sys.stdout` y `sys.stderr` si no lo tienen.

    Devuelve si cambió alguno. Con consola no toca nada.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return False
    log = _Log(path or log_path())
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log
    return True
