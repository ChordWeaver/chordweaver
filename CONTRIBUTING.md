# Cómo contribuir a ChordWeaver

Gracias por pasar. Este archivo es corto a propósito: casi todo lo que hay que
saber para no romper nada ya está escrito en otros dos lugares, y lo que sigue
te dice cuál leer antes de tocar qué.

- [`README.md`](README.md) — qué hace el programa y cómo correrlo.
- [`MUSIC_LOGIC.md`](MUSIC_LOGIC.md) — **lectura obligatoria antes de tocar
  cualquier cosa musical.** Documenta, con referencias `archivo:línea`, cómo se
  representan notas, voces e intervalos; los tres criterios distintos de
  consonancia y por qué no coinciden; el catálogo completo de reglas; y las
  excepciones que parecen bugs y no lo son.
- [`CLAUDE.md`](CLAUDE.md) — el mapa de las decisiones de diseño y de las
  optimizaciones medidas. Si algo del código parece innecesariamente raro,
  probablemente esté explicado ahí, con el número que lo justifica.

## Poner a andar el proyecto

```bash
pip install customtkinter     # la única dependencia para correr la app
python app.py                 # la aplicación con interfaz
python tests.py               # la suite del motor (369 tests)
python cli.py --chords "Cmaj7 Am7 Dm7 G7" --genre jazz
```

Hay que estar parado en la carpeta que contiene `cli.py`; si no, Python tira
`No module named engine`.

## Antes de mandar un pull request

1. **`python tests.py` tiene que pasar entero.** Son 369 tests y tardan menos
   de dos minutos. Un test nuevo por cada comportamiento nuevo.
2. **Si tocaste `engine/fitness.py` o `engine/style.py`, corré también
   `python audit.py`** y pegá el resultado en el PR. Los pesos están calibrados
   contra esa auditoría: cambiar un número altera el resultado musical de todas
   las generaciones **sin que falle ningún test**. El README tiene la tabla de
   control con la que comparar.
3. **Contá qué mediste.** Este proyecto tiene varias optimizaciones que sólo se
   justifican con números —el relleno de la población, el intervalo de cambio
   de hilo, los marcos de tkinter pelado— y todas están documentadas con el
   antes y el después. Si tu cambio es por rendimiento, medilo.

## Las cinco trampas que se llevan puestas a todo el mundo

Ninguna de estas falla con un error. Todas fallan en silencio.

1. **Si el motor está compilado, editar el `.py` no hace nada.**
   `python build_engine.py` deja `engine/*.pyd` al lado de los `.py`, y un
   `.pyd` gana en el orden de importación. Editás, corrés, no pasa nada, y
   buscás el bug en otro lado. `ls engine/*.pyd` te dice en un segundo si el
   motor está compilado; `python build_engine.py --clean` lo devuelve a Python
   puro mientras trabajás.

2. **Y con el motor compilado, parchear una función de `engine/` desde afuera
   tampoco hace nada** si quien la llama está en el mismo módulo: Cython
   resuelve esas llamadas a nivel C. Cualquier script que instrumente el motor
   por dentro tiene que correr con `--clean`. `tests.py` no lo necesita, porque
   prueba por la API pública.

3. **Una preferencia nueva que no esté en `DEFAULT_SETTINGS`
   (`engine/history.py`) se guarda bien y se pierde al reabrir.** Es una lista
   blanca: `load_settings` descarta cualquier clave que no figure ahí.

4. **Un módulo nuevo en `engine/` tiene que agregarse a los `hiddenimports` de
   `ChordWeaver.spec`.** Están listados a mano justamente para que un import
   faltante rompa el build en vez del ejecutable ya entregado.

5. **Cualquier script que abra la ventana tiene que pasar por
   `uitest.Session`.** Construir `ChordWeaverApp` directo escribe sobre los
   datos de verdad del usuario: el historial guarda las diez últimas
   producciones, así que diez corridas de prueba lo borran entero. `Session`
   manda todo a archivos descartables y pone `CHORDWEAVER_DATA_DIR` **antes de
   importar `app`**.

## Los límites del diseño

Estos no son preferencias de estilo: son lo que hace que el proyecto sea lo que
es. Un PR que los cruce se va a discutir aunque el código esté bien.

- **El motor no tiene dependencias.** `engine/` es librería estándar pura.
  MusicXML, MIDI y el audio WAV se escriben a mano para que el ejecutable quede
  chico y sin dependencias: **no introducir `music21`, `mido`, `numpy` ni
  ninguna librería de audio.** La única dependencia real del proyecto es
  `customtkinter`, y es de la interfaz.
- **Ningún módulo de `engine/` importa un toolkit gráfico.** Es lo que permite
  correr el motor desde los tests, el CLI o la app indistintamente.
- **El grafo de dependencias no tiene ciclos** y `engine/session.py` es la
  fachada: la GUI y el CLI sólo hablan con ese módulo. Capacidad nueva del
  motor, se expone ahí.
- **Los perfiles de género sólo cambian pesos y valores por defecto, nunca la
  mecánica.** Si una regla nueva necesita lógica distinta según el género, va
  como peso, no como rama. Y todo switch se tiene que poder prender y apagar
  por separado: el género define el valor inicial y nada más.
- **Las rutas son portables.** `history.base_directory()` devuelve la carpeta
  del `.exe` cuando está congelado y la raíz del proyecto cuando corre desde
  fuente. Nunca escribir en el home del usuario ni en una ubicación de sistema
  salvo que el usuario la elija en un diálogo. El arte del programa cuelga de
  `program_directory()`, que es otra cosa.
- **Cython es opcional y los `.py` no se tocan para complacerlo.** Los tipos
  viven en `engine/fitness.pxd` y `engine/style.pxd`, que Python ignora por
  completo. Reescribir una función para poder declararla sería exactamente lo
  que esta separación existe para no hacer. Los `.pxd` **son fuente**, se
  editan a mano, y una firma de ahí tiene que coincidir con la del `.py`.

## Convenciones de código

- Python 3.9+. Sin formateador automático configurado: mirá el archivo que
  estás editando y escribí como está escrito.
- **Identificadores y docstrings en inglés; los comentarios de prosa, en
  español.** Es lo que hay en todo el código y conviene seguirlo.
- Los comentarios largos explican **por qué**, no qué. El código ya dice qué
  hace.
- Tk no es thread-safe: la búsqueda corre en un hilo de fondo y reporta por una
  cola que el main loop drena por timer. **El worker nunca toca un widget**, y
  un hilo de fondo tampoco puede agendar nada con `after`.

## Qué no se commitea

El `.gitignore` ya los cubre, pero por si acaso: `history.json`,
`achievements.json`, `story.json`, `eggs.json`, `visitors.json` y
`settings.json` son **datos del usuario**, no código. Igual que `output/`,
`build/`, `dist/` y los `engine/*.pyd`, que se regeneran.

## Reportar un bug

Contá qué esperabas y qué pasó, y agregá:

- el modo (Organizador, Generador o Armonizador) y el género,
- los acordes o la melodía con los que pasó,
- **la semilla**, si la fijaste: con la misma semilla el resultado es idéntico
  bit a bit, así que es lo que hace el bug reproducible,
- si el motor estaba compilado (`ls engine/*.pyd`).

Si es un bug musical —"esto no debería sonar así"— decí qué regla creés que se
está violando y, si podés, dónde la encontrás en `MUSIC_LOGIC.md`. Varias cosas
que parecen errores están documentadas ahí como excepciones deliberadas.

## Licencia

Al contribuir aceptás que tu aporte se distribuya bajo la
[licencia MIT](LICENSE), que es la del proyecto.
