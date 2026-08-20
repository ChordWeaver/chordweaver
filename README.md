# ChordWeaver

Optimiza el *voice leading* entre acordes elegidos por vos, usando un
algoritmo genetico. Vos elegis los acordes y su duracion; el AG decide
que nota del acorde canta cada voz y en que octava, para que el
movimiento total entre voces sea el minimo posible.

## Estructura de carpetas (IMPORTANTE)

Tiene que quedar exactamente asi. Si `engine/` no es una subcarpeta,
Python tira `No module named engine`:

```
ChordWeaver/
├── app.py                 <- la aplicacion con interfaz
├── staff.py               <- el pentagrama que se puede escribir
├── cinematic.py           <- las escenas del modo historia
├── cli.py                 <- la misma logica por linea de comandos
├── tests.py
├── README.md
├── requirements.txt
├── ChordWeaver.spec
└── engine/
    ├── __init__.py
    ├── theory.py          <- notas, voces, parser de cifrado
    ├── voicing.py         <- duplicaciones y omisiones
    ├── style.py           <- reglas de contrapunto por genero
    ├── fitness.py         <- restricciones duras + penalizaciones
    ├── ga.py              <- torneo, elitismo, paralelismo
    ├── export.py          <- MusicXML y MIDI
    ├── history.py         <- ultimas 10 producciones
    ├── book.py            <- el texto del libro de teoria
    ├── achievements.py    <- catalogo, estrellas y detectores
    ├── story.py           <- el modo historia: guion y estado
    ├── visitors.py        <- las visitas: quien aparece y cuando
    ├── ambience.py        <- los ruidos, sintetizados a mano
    └── session.py         <- fachada
```

## Como correrlo

La aplicacion con interfaz necesita una sola dependencia:

```bash
pip install customtkinter
python app.py
```

El motor por su cuenta es Python puro (3.9+) y no necesita nada instalado.
Parate en la carpeta `ChordWeaver/` y corre:

```bash
python tests.py                                        # 369 tests
python cli.py --chords "Cmaj7 Am7 Dm7 G7 Cmaj7" --genre jazz
python cli.py --chords "C Am F G C F G C" --genre chorale
python cli.py --chords "Dm7 G7 Cmaj7" --time 3/4 --duration 1
```

Los archivos salen en `output/`, al lado del codigo. Con `--out` elegis otra carpeta.

Si te tira `No module named engine`, casi siempre es una de estas dos:
1. Estas parado en otra carpeta -> hace `cd` a la carpeta que contiene `cli.py`.
2. Los `.py` del motor quedaron sueltos en vez de adentro de `engine/`.

## Como se usa la interfaz

Siete pantallas en carrusel, siempre podes volver atras. La primera elige el
modo de trabajo, que es lo que decide quien pone los acordes:

- **Organizador** — vos escribis la progresion (o la importas) y el programa
  solo reparte las voces.
- **Armonizador** — vos dibujas la melodia y el programa le busca los acordes.
- **Generador** — el programa arma la progresion entera y despues la escribe.

Cada modo tiene su color, y ese color tine el riel de progreso del encabezado
durante todo el recorrido.

Las pantallas que siguen:

1. **Genero** — define que reglas se aplican y como se ponderan.
2. **Voces** — de 3 a 6 del catalogo (S, MS, A, T, Bar, B), con sus rangos editables.
3. **Compases** — metrica base y cantidad; cada compas puede tener otra metrica.
4. **Acordes** — cifrado americano con validacion en vivo. Si el acorde tiene mas
   notas que voces te avisa que grados omite. Si no lo reconoce, el boton
   `piano` abre un teclado para elegir las notas a mano.
5. **Parametros** — todos los switches de reglas y los parametros del AG.
6. **Resultado** — las 3 mejores, y elegis formato y carpeta para guardar.

El boton `Historial` arriba a la derecha muestra las ultimas 10 producciones.

## Tutorial y libro de teoria

La primera vez que se abre el programa arranca un recorrido guiado que resalta
cada modo y cada estilo sobre la interfaz real, con el resto de la pantalla
oscurecido. Se puede omitir en cualquier momento, y se vuelve a ver desde el
engranaje (`Ver el tutorial otra vez`). Al terminarlo o saltearlo lleva a la
pantalla de logros y otorga *Aprendiz*.

Debajo de los logros esta el **libro de teoria**: armonia basica, conduccion de
voces, los tres estilos, las cadencias que el programa reconoce --- con la
receta para que aparezcan --- y un capitulo de ingenieria sobre el algoritmo
genetico. Esta escrito para alguien que no estudio musica. Abrirlo otorga
*Lector comprometido*.

El libro no esta escrito entero de entrada: cada apartado esta atado a un logro
y se escribe solo cuando el usuario se topa con esa cadencia, ese movimiento o
ese recurso. Cuando eso pasa, el apartado nuevo aparece con una anotacion a
mano al pie.

## Modo historia

Despues de cinco minutos de uso --- y solo con la pantalla inicial a la vista, el
tutorial terminado y ninguna busqueda corriendo --- se enciende un boton dorado en
la pantalla inicial. No dice que es. Cuando lo toques aparece una figura que
ofrece un poder, y lo que se le conteste abre uno de tres senderos:

| Respuesta | Sendero | Quien acompana |
|---|---|---|
| Aceptar | Blues | el senor del sombrero |
| Ignorar | Jazz | un guitarrista anonimo |
| Rechazar | Gospel | Jesus |

Cada sendero son tres tramos y siempre en los mismos tres lugares: una progresion
escrita a mano en el **Organizador**, un boton dorado en el **Generador** y un
gesto dorado en el **Armonizador**. Los dos botones dorados nacen bloqueados:
para encenderlos hay que repetir la cadencia del tramo en tres tonalidades
distintas, y leer el apartado nuevo que el sendero escribio en el libro.

Los tramos automaticos no pasan por el algoritmo genetico ni por los parametros:
la pieza --- los doce compases del blues, *All of Me*, la regla de la octava del
gospel, *Amazing Grace* --- esta escrita de antemano y sale al instante. Tampoco
reparten logros: la escribio el programa, no vos. Si quedan en el historial y se
pueden exportar como cualquier otra.

El capitulo **VII** del libro, *La musica de los reprimidos*, se llena con los
tramos recorridos en vez de con logros. Cuenta de donde salio cada cosa: el
cruce de caminos del delta del Misisipi, los jazzes que no son uno solo, los
*spirituals* y el capitan de barco negrero que escribio *Amazing Grace*.

Al final de cada camino se entrega el logro legendario que le corresponde, su
titulo y un recuerdo, que queda al lado de los titulos en la pantalla de logros.
Ahi mismo esta el boton **Arrepentirse**: vuelve a la encrucijada y deja elegir
de nuevo. Lo conseguido no se pierde --- los logros, los titulos y lo que quedo
escrito en el libro siguen siendo tuyos --- y lo unico que vuelve a cero es el
sendero.

Todo el sonido de las escenas --- el viento del valle, los pajaros, la voz de cada
personaje, el coro, los vientos que cierran un tema --- esta sintetizado por el
programa, igual que el audio del boton `Escuchar`. No se empaqueta ningun archivo
de sonido.

## Paralelismo

La busqueda usa varios procesos, no hilos: es trabajo de CPU puro en Python y
el GIL haria que los hilos se turnen en vez de correr en paralelo. La cantidad
se decide sola segun la maquina donde corre (`workers=None`):

- deja un nucleo libre para que la ventana siga respondiendo,
- topea en 8 porque mas alla el costo de serializar supera la ganancia,
- y se desactiva en trabajos chicos, donde paralelizar cuesta mas de lo que ahorra.

Podes forzar un numero con `GAConfig(workers=N)`.

## Generos

| Genero      | Paralelas 5tas/8vas | Tritono   | Voicings especiales | Caracter |
|-------------|---------------------|-----------|---------------------|----------|
| `classical` | prohibidas          | libre     | si                  | premia movimiento contrario, saltos chicos |
| `chorale`   | prohibidas          | libre     | si                  | como el clasico pero mas estricto en espaciado y tesitura |
| `gregorian` | permitidas (organum)| prohibido | no                  | casi todo por grado conjunto |
| `jazz`      | permitidas          | libre     | si                  | voicings cerrados, mantiene tensiones |

Todos los switches se pueden prender y apagar por separado; el genero solo
define el valor inicial.

## Reglas de contrapunto por genero

Ademas de minimizar el movimiento, el fitness pondera las reglas propias de
cada tradicion (ver `engine/style.py`):

- **Clasico / coral**: nunca duplicar la sensible; la septima resuelve bajando
  y la sensible subiendo; sin solapamiento de voces entre acordes contiguos;
  saltos de tritono y septima castigados; un salto grande se compensa con
  movimiento contrario; se premian las notas comunes y el movimiento contrario
  al bajo. El coral aplica todo esto mas fuerte.
- **Gregoriano**: casi todo por grado conjunto, ambito estrecho, segundas y
  septimas entre voces castigadas, tritono prohibido por defecto.
- **Jazz**: se premia que las guide tones (3ra y 7ma) se conecten por grado
  conjunto, las septimas bajan, se mantienen notas comunes y se evitan las
  novenas menores (avoid notes).

## Reglas duras vs penalizaciones

**Duras** (anulan el cromosoma, nunca aparecen en el resultado):
rangos vocales, cobertura del acorde, cruce de voces, y lo que prendas de
paralelas / tritono.

**Ponderadas** (el AG las negocia): movimiento total (el peso mas grande),
tamaño de saltos, espaciado, tesitura, repeticion estatica de acorde,
quintas directas, movimiento contrario.

## Compilar el motor (opcional)

Los tres modulos que la busqueda pisa millones de veces por corrida --el
evaluador, las reglas de estilo y la representacion de las notas-- se pueden
compilar a C con Cython:

```bash
pip install cython setuptools     # ademas de MSVC (Build Tools de Visual Studio)
python build_engine.py            # deja engine/*.pyd al lado de los .py
python build_engine.py --clean    # los borra y vuelve a Python puro
```

**Es opcional y no cambia nada de lo que el programa hace.** Los `.py` no se
tocan: se compilan tal como estan, con una hoja de tipos aparte
(`engine/fitness.pxd`, `engine/style.pxd`) que Python ignora. Si el `.pyd`
esta al lado del `.py`, Python lo prefiere solo; si no esta, corre el `.py`.
Sin compilador el programa anda igual, mas lento, y `pyinstaller
ChordWeaver.spec` sigue dando un ejecutable que funciona.

Medido sobre 16 acordes con la busqueda de fabrica (200x300): la busqueda pasa
de 17,4 a 8,2 segundos en un proceso y de 8,3 a 5,7 con los ocho del pool. El
resultado es identico bit a bit --verificado sobre 14 corridas, cuatro generos
por tres semillas mas los dos modos generativos.

## Empaquetar el .exe

```bash
pip install pyinstaller customtkinter
pyinstaller ChordWeaver.spec
```

Queda en `dist/ChordWeaver/`, portable: copiala a donde quieras. Es build de
carpeta y no `--onefile` a proposito, porque con onefile el programa se
descomprime en un temporal y el historial no persistiria al lado del exe.

## Auditoria contrapuntistica (`python audit.py`)

La pregunta que responde: cada genero *realmente* escribe segun su tradicion,
o todos convergen a "la solucion que menos se mueve" con distinta etiqueta?

El script corre varias progresiones con cada genero y mide el resultado contra
reglas que el fitness nunca ve como un solo numero, comparando siempre contra
un control: la misma busqueda con todos los pesos de estilo apagados.

Resultados medidos (promedio sobre 4 progresiones x 2 semillas):

| metrica | control | clasico | coral | gregoriano | jazz |
|---|---|---|---|---|---|
| % grado conjunto | 86.5 | 79.2 | 79.0 | **91.2** | 87.0 |
| % movimiento contrario | 11.3 | **18.8** | **20.8** | 13.1 | 10.1 |
| 5tas/8vas paralelas | 1.5 | **0.0** | **0.0** | 1.4 | 2.0 |
| solapamientos | 0.4 | **0.0** | **0.0** | 0.0 | 0.0 |
| % 7mas que resuelven bajando | 67.9 | **85.7** | **96.4** | 67.9 | 78.6 |
| % guide tones por grado | 41.6 | 37.5 | 32.1 | 41.0 | **51.9** |
| ambitus medio por voz | 4.7 | 5.4 | 5.5 | **3.8** | 5.3 |
| % perfectas sobre el bajo | 36.5 | 40.1 | 36.5 | 39.6 | 39.1 |

Lectura honesta:

- **Clasico y coral se diferencian con claridad.** El movimiento contrario casi
  se duplica y las septimas pasan de resolver 68% a 86-96%. No es placebo.
- **Jazz se diferencia moderadamente**: las guide tones conectan por grado 52%
  contra 42% del control.
- **Gregoriano es el mas debil**, y hay una razon estructural: el caracter modal
  vive sobre todo en la *armonia* (cadencias modales, ausencia de sensible,
  quintas al aire), y en esta app los acordes los elige el usuario. Lo unico que
  el AG controla es el registro y el reparto de notas. Igual se diferencia donde
  sus reglas apuntan: ambitus 3.8 contra 4.7, y mas intervalos perfectos.
- Los generos con reglas fuertes **pagan** movimiento por estilo (1.3 contra 1.2
  semitonos de media), que es exactamente el intercambio que se busca.

Durante la auditoria se detecto que el umbral de ambitus estaba en 9 semitonos
cuando los ambitos reales rondan 5, o sea que la regla no se activaba nunca.
Corregido a 5.

## Las visitas

Aparte del sendero hay cuatro apariciones sueltas. No se eligen y no se pueden
abandonar: ocurren cuando ocurren, y cada una deja algo.

| Quien | Cuando | Que deja |
|---|---|---|
| Bach | a la quinta partitura barroca | el capitulo VIII del libro |
| Bach, otra vez | la primera vez que se usa el modo coral | otro apartado |
| Gregorio I | a la quinta partitura gregoriana | otro apartado |
| Una entidad encapuchada | al conseguir el 100% de los logros | la partitura quemada y la lista de los huevos |

Los dos maestros felicitan y explican: Bach, que la musica se escribia en voces
y no en acordes, y que es lo que separa a un coral de todo lo demas; Gregorio,
el organum --- la *vox principalis* y su sombra a la quinta ---, que es de donde
sale todo lo que el programa hace. Los dos cierran con una cita suya de verdad.

La entidad no explica nada. Dice que estuvo mirando, que no entiende como se
llego hasta ahi, y avisa de alguien que va a venir. Deja el cuarto objeto ---
una partitura quemada de la que no se llega a leer de quien es --- y, al pie de
la pantalla de logros, la lista de los seis huevos de pascua con los pasos
exactos para provocarlos. Es lo unico del programa que los nombra: hasta ese
momento el contador dice cuantos hay y ninguno cual.

La quinta aparicion es **la vision**, y es la unica que no se puede provocar de
ninguna manera. Al abrir el programa, una vez de cada cinco --- con el tutorial
ya hecho u omitido --- y una sola vez en la vida, se ve un camino de tierra de
noche, la luna llena y un tren cruzando a lo
lejos. Nadie habla y el programa tampoco: no avisa nada al terminar. Queda
escrita en el libro la historia de Robert Johnson, en dorado, como un legendario,
y hay que ir a encontrarla.

Para mirarlas hay dos caminos. En la configuracion --- el engranaje --- hay una
seccion **Escenas (prueba)** con un boton por aparicion; es provisoria y se saca
cuando deje de hacer falta. Y desde afuera, dos variables de entorno:
`CHORDWEAVER_VISIT` fuerza una visita al abrir (`watcher`, `bach_baroque`,
`bach_chorale`, `gregory`) y `CHORDWEAVER_VISION=1` fuerza la vision.

Las dos formas juegan la escena entera y entregan lo que entrega de verdad, asi
que la que mires desde ahi no vuelve a aparecer sola.

## Importar una partitura

En el modo de acordes propios, el boton `Importar partitura...` lee un archivo
MusicXML (`.musicxml`, `.xml` o `.mxl` comprimido) y carga sus acordes con su
ritmo y sus compases. El orden de las voces que trae el archivo queda como
punto de partida y es lo que propone el candado, pero el programa puede
reacomodarlo: para eso se importa. Si queres conservar una disposicion tal
cual vino, fijala con el candado.

## Estado

- Parte 1 (motor): terminada y testeada (369 tests).
- Parte 2 (interfaz): terminada. Probada de punta a punta bajo display virtual,
  pero **no** en Windows real ni empaquetada como .exe -- eso lo tenes que
  verificar vos.
