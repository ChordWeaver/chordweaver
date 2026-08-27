# ChordWeaver

**[chordweaver.github.io](https://chordweaver.github.io)** · [Descargar la última versión](https://github.com/ChordWeaver/chordweaver/releases/latest)

Tus acordes, tu melodía, o una hoja en blanco: un algoritmo genético convierte
cualquiera de las tres en una progresión escrita a varias voces. Decide qué nota
del acorde canta cada voz y en qué octava, para que el movimiento total sea el
mínimo posible sin romper las reglas de contrapunto del género elegido.

El AG **nunca cambia los acordes ni su orden** — sólo el registro y el reparto de
notas. En el Organizador los acordes los escribís vos; en el Generador los arma
el programa; en el Armonizador los busca debajo de la melodía que dibujaste.

Y al revés: el **analizador** toma una partitura que ya existe --- escrita a
mano o importada --- y le pone nombre a lo que hace, acorde por acorde y paso
por paso.

![La pantalla que abre el programa: los tres modos y las dos herramientas](capturas/01-modos.png)

*Los tres modos --- las tres terminan en lo mismo, una progresión escrita a
varias voces, y lo que cambia es cuánto ponés vos --- y debajo las dos
herramientas que no componen nada.*

## Estructura de carpetas (IMPORTANTE)

Tiene que quedar exactamente así. Si `engine/` no es una subcarpeta,
Python tira `No module named engine`:

```
ChordWeaver/
├── app.py                 <- la aplicación con interfaz
├── staff.py               <- el pentagrama que se puede escribir
├── analyzer.py            <- la pantalla del analizador
├── cinematic.py           <- las escenas del modo historia
├── cli.py                 <- la misma lógica por línea de comandos
├── tests.py
├── README.md
├── requirements.txt
├── ChordWeaver.spec
└── engine/
    ├── __init__.py
    ├── theory.py          <- notas, voces, parser de cifrado
    ├── voicing.py         <- duplicaciones y omisiones
    ├── style.py           <- reglas de contrapunto por género
    ├── fitness.py         <- restricciones duras + penalizaciones
    ├── ga.py              <- torneo, elitismo, paralelismo
    ├── export.py          <- MusicXML y MIDI
    ├── history.py         <- últimas 10 producciones
    ├── book.py            <- el texto del libro de teoría
    ├── achievements.py    <- catálogo, estrellas y detectores
    ├── story.py           <- el modo historia: guion y estado
    ├── visitors.py        <- las visitas: quién aparece y cuándo
    ├── ambience.py        <- los ruidos, sintetizados a mano
    ├── harmonics.py       <- la serie armónica y su síntesis
    ├── analysis.py        <- leer una partitura ya escrita
    └── session.py         <- fachada
```

Y al lado de `app.py`, los cuatro módulos de interfaz que no son la ventana:
`staff.py` (el pentagrama que se escribe, de una línea y de dos),
`spectrum.py` (el experimentador de armónicos), `analyzer.py` (el analizador)
y `cinematic.py` (las escenas).

## Cómo correrlo

La aplicación con interfaz necesita una sola dependencia:

```bash
pip install customtkinter
python app.py
```

El motor por su cuenta es Python puro (3.9+) y no necesita nada instalado.
Parate en la carpeta `ChordWeaver/` y corré:

```bash
python tests.py                                        # 384 tests
python cli.py --chords "Cmaj7 Am7 Dm7 G7 Cmaj7" --genre jazz
python cli.py --chords "C Am F G C F G C" --genre chorale
python cli.py --chords "Dm7 G7 Cmaj7" --time 3/4 --duration 1
```

Los archivos salen en `output/`, al lado del código. Con `--out` elegís otra carpeta.

Si te tira `No module named engine`, casi siempre es una de estas dos:
1. Estás parado en otra carpeta -> hacé `cd` a la carpeta que contiene `cli.py`.
2. Los `.py` del motor quedaron sueltos en vez de adentro de `engine/`.

## Cómo se usa la interfaz

Siete pantallas en carrusel, siempre podés volver atrás. La primera elige el
modo de trabajo, que es lo que decide quién pone los acordes:

- **Organizador** — vos escribís la progresión (o la importás) y el programa
  sólo reparte las voces.
- **Armonizador** — vos dibujás la melodía y el programa le busca los acordes.
- **Generador** — el programa arma la progresión entera y después la escribe.

Cada modo tiene su color, y ese color tiñe el riel de progreso del encabezado
durante todo el recorrido.

Debajo de las tres, dos tarjetas más que no llevan a componer nada: el
**experimentador de armónicos** y el **analizador**. Y debajo de ésas, los
logros y el libro de teoría.

![El Armonizador: la melodía dibujada en el pentagrama](capturas/10-armonizador.png)

*El Armonizador. Las notas doradas son las que van a llevar acorde, y se
recalculan con cada tecla: es la misma cuenta que hace la búsqueda, sin
elegir los acordes todavía. Podés marcar cualquier otra y ésa recibe el suyo.*

Las pantallas que siguen:

1. **Género** — define qué reglas se aplican y cómo se ponderan.
2. **Voces** — de 3 a 6 del catálogo (S, MS, A, T, Bar, B), con sus rangos editables.
3. **Compases** — métrica base y cantidad; cada compás puede tener otra métrica.
4. **Acordes** — cifrado americano con validación en vivo. Si el acorde tiene más
   notas que voces te avisa qué grados omite. Si no lo reconoce, el botón
   `piano` abre un teclado para elegir las notas a mano.
5. **Parámetros** — todos los switches de reglas y los parámetros del AG.
6. **Resultado** — las 3 mejores, y elegís formato y carpeta para guardar.

![La pantalla de género: Barroco, Gregoriano y Jazz](capturas/02-estilos.png)

*La pantalla de género. El modo coral no es una tarjeta: es un switch
adentro de Barroco, porque es el mismo contrapunto apretado más fuerte.*

![La pantalla de resultado, con las tres mejores soluciones](capturas/salida.png)

*El resultado. Las tres mejores, cada una con lo que el programa reconoció
adentro --- una cadencia rota, un 6/4 cadencial, una sexta en lugar de
quinta --- y explicado en una línea. Se escuchan sin salir de la pantalla.*

El botón `Historial` arriba a la derecha muestra las últimas 10 producciones.

## El experimentador de armónicos

En la segunda fila de la pantalla inicial, al lado del analizador, hay una
puerta que no lleva a componer nada. Adentro hay una nota sola, dibujada como lo que es: una barra por cada
armónico, colocada por frecuencia y alta por amplitud.

El gráfico no ilustra el sonido, **es** el sonido. Arrastrar una barra para
arriba amplifica ese armónico; para el costado lo corre de su múltiplo exacto
y lo desafina contra los demás, que es como se escuchan las pulsaciones. Se
puede aislar uno y oírlo solo, silenciarlo, devolverlo a su lugar exacto,
cambiar la nota desde el teclado, aplicarle vibrato o trémolo a todo el
conjunto, y saltar entre las ocho recetas clásicas --- seno, diente de sierra,
cuadrada, triangular, cuerda pulsada, clarinete, órgano, voz --- que no son
ocho maneras de vibrar sino la misma serie con otras alturas de barra. Con
vibrato encendido las barras se dibujan a rayas, como un fuelle: la afinación
está oscilando y una barra maciza es lo que se dibuja cuando está quieta.

Debajo, la lectura del armónico elegido: su frecuencia, qué nota temperada le
queda cerca, a cuántos cents, y a qué distancia está de la fundamental. Ahí se
ve de un vistazo que el segundo armónico es una octava, el tercero una octava
y una quinta, que el quinto cae catorce cents por debajo de la tercera del
piano y el séptimo treinta y uno por debajo de la séptima.

`Guardar timbre…` se lleva el resultado afuera. No es exportar el sonido: el
archivo sale con la nota que representa y con el tramo que se repite anotados
adentro, que es lo que hace que cualquier sampler que lea WAV --- TX16Wx,
Kontakt, el AudioFileProcessor de LMMS, el Simpler de Live, Polyphone para
armar un SoundFont --- lo tome como el timbre de un instrumento: afinado en
todo el teclado y sostenido mientras la tecla siga apretada. Que el bucle no
chasque en cada vuelta es lo difícil, y para eso cada componente se acomoda al
múltiplo más cercano de la duración del bucle --- un desvío de centésimas de
cent --- y el vibrato se escribe como modulación de fase, que es lo único que
vuelve a la misma fase con la que salió.

Usarlo otorga *Licenciado en física* y escribe el capítulo **X** del libro.

## El analizador

Los tres modos escriben música. El analizador la lee: se le da una partitura
--- escrita a mano en un sistema de dos pentagramas o traída de un archivo
MusicXML --- y contesta las dos preguntas con las que se estudia una obra
ajena.

![El analizador con los primeros compases del Preludio BWV 846](capturas/11-analizador.png)

*Los cuatro primeros compases del Preludio en Do mayor de Bach, importados y
analizados: I - ii4/2 - V6/5 - I, con el cifrado del bajo continuo debajo de
cada acorde.*

**Qué acorde es cada momento y qué hace.** La tonalidad sale de la armadura,
del acorde de arranque y del de reposo, así que puede ser un modo y no sólo
mayor o menor. Encima del sistema aparece el cifrado americano y debajo el
del bajo continuo, escrito en columna como se escribe; el grado y el área
funcional --- tónica, subdominante, dominante --- van en la lista de la
izquierda, que es donde hay ancho para leerlos. Un acorde que no es de la
escala se
explica: si es una **interdominante** dice a qué grado apunta y si llega a
resolver; si es un **intercambio modal** dice de qué modo viene y qué grado es
allá; y si hay varios ajenos seguidos, se leen juntos --- una tonicización,
una modulación o una cadena de dominantes. Las cuartas suspendidas que
después corrigen la cuarta por la tercera se señalan como lo que son.

Cada nota se escribe como corresponde y no como salga: un sexto grado bemol
es un La bemol y no el Sol sostenido de al lado, y la quinta de un Si con
séptima es un Fa sostenido aunque la pieza vaya llena de bemoles. Cuando el
archivo no trae armadura --- las que exporta este mismo programa no la
traen --- se deduce de lo que suena.

Cuando dos lecturas son igual de buenas se ofrecen las dos: do-mi-sol-la es
un Do6 y un Lam7 y no hay nada en esas cuatro notas que lo decida.

**Qué está haciendo el contrapunto.** El movimiento entre cada par de voces
--- contrario, oblicuo, paralelo, directo --- contado paso por paso, y
**tocable**: al elegir uno, cada par de voces que se mueve así queda marcado
en el sistema con un trazo que une las dos notas y una flecha en cada una
diciendo adónde va. Un movimiento contrario se reconoce viendo las dos
flechas apuntar al revés.
Después las quintas y octavas paralelas, las ocultas, los cruces, los
solapamientos y los saltos de trítono, cada uno en su compás; y los adornos
melódicos --- las notas que no pertenecen al acorde --- con el nombre que les
corresponde: nota de paso, bordadura, apoyatura, escapada, retardo,
anticipación, cambiata, mordente, grupeto, nota pedal y anacrusa. Cada uno
dice en qué compás y en qué tiempo cae, y al pasarle el mouse por encima, qué
es.

Las cadencias se nombran todas: auténtica perfecta e imperfecta, plagal,
rota, semicadencia y frigia, más las tres progresiones con nombre propio que
el generador puede citar --- la frigia de cuatro acordes, el ciclo de Vivaldi
y el bajo cromático descendente. Cada una aparece como un rótulo con su
compás, y tocándolo se marca en el sistema el tramo exacto donde ocurre.

Las reglas de contrapunto no están escritas dos veces: las paralelas y las
quintas ocultas se las pregunta al mismo evaluador que usa el algoritmo
genético, así que el analizador no puede aprobar lo que el generador prohíbe.

### Cómo se usa

Se elige la armadura y el compás como en el armonizador, se elige qué voz se
está escribiendo y con qué figura, y se hace click donde va cada nota: la
altura sale de dónde se toca en el sistema y **el momento, de a qué altura
del compás**. Si la voz todavía no llegó hasta ahí, el hueco se rellena solo
con silencios; y si el click cae dentro de una nota ya escrita, esa nota se
parte y las dos puntas siguen siendo lo que eran --- que es lo que hace falta
para meter una corchea de paso en el medio de una redonda sin desarmar nada.
Ninguna nota puede quedar a caballo de una barra de compás.

El botón derecho borra la nota que esté debajo --- dejando un silencio, para
que la voz no se corra ---, `Ctrl+Z` deshace el último cambio sea cual sea, y
`Tab` pasa a la voz siguiente sin tener que ir al menú. Los accidentes que no
están en la armadura --- sostenido, bemol, becuadro --- se eligen antes de
escribir la nota.

Para leer no hace falta tocar nada: con el mouse encima de cualquier nota, el
renglón de abajo dice cuál es, en qué compás y tiempo cae y qué hace dentro de
su acorde.

El compás no es uno solo para toda la pieza: se elige el compás, se escribe
**desde qué compás** rige y de ahí en más las barras se dibujan donde
corresponde. Elegir en un compás el mismo que ya regía saca ese cambio de la
lista.

Bajo y tenor van en clave de fa y alto y soprano en clave de sol, igual que
en la partitura exportada. Cuántas voces hay no se elige: se cuenta lo que
está escrito, y una partitura importada con más de cuatro se recorta a las
cuatro más graves avisando. Una barra de color al costado marca en qué clave
se está escribiendo.

El analizador **no dice nada hasta que haya tres voces escritas**: un acorde
es una tríada, y nombrar acordes a partir de una nota o dos sería inventarlos.

`▶ Escuchar` reproduce lo que haya escrito, voz por voz y con su ritmo, haya
o no un análisis: con dos voces no hay acordes que nombrar y sí hay música
que oír. `Exportar…` la guarda en MusicXML y MIDI, con su armadura, sus dos
claves y sus cambios de compás, igual que en los otros tres modos. Un
análisis no se anota en el historial: el historial guarda corridas del motor
y esto no lo es.

`Importar…` abre en `assets/partituras/`, donde está el Preludio en Do mayor
de Bach: es la pieza con la que se ajustó el analizador y sirve para probarlo
sin tener que conseguir un archivo primero. Todo lo que exportan el
organizador, el generador y el armonizador también vuelve a entrar por acá.

Abrirlo otorga *El principio del final*, e importar una partitura, *Vine
preparado*.

## Tutorial y libro de teoría

La primera vez que se abre el programa arranca un recorrido guiado que resalta
cada modo y cada estilo sobre la interfaz real, con el resto de la pantalla
oscurecido. Se puede omitir en cualquier momento, y se vuelve a ver desde el
engranaje (`Ver el tutorial otra vez`). Al terminarlo o saltearlo lleva a la
pantalla de logros y otorga *Aprendiz*.

Ese recorrido muestra dónde está cada cosa. Después hay tres **guías de
pantalla** que explican cómo se usa, y se abren solas la primera vez que se
llega a la pantalla donde cada modo hace su trabajo de verdad:

| Modo | Dónde | Qué explica |
|---|---|---|
| Organizador | la pantalla de acordes | el cifrado, las duraciones y los silencios, que el compás cierre exacto, el candado y el piano |
| Armonizador | la pantalla del pentagrama | escribir con click o con el piano, las figuras, qué significan las notas doradas, la armadura y qué voz sos |
| Generador | la pantalla de reglas | qué es una regla dura, el dial de balance, la consonancia en los reposos y qué pasa al generar |

Se omiten con un botón, aparecen una sola vez, y vuelven todas juntas con el
mismo `Ver el tutorial otra vez` del engranaje.

Al lado de los logros está el **libro de teoría**: armonía básica, conducción de
voces, los tres estilos, las cadencias que el programa reconoce --- con la
receta para que aparezcan --- y un capítulo de ingeniería sobre el algoritmo
genético. Está escrito para alguien que no estudió música. Abrirlo otorga
*Lector comprometido*.

![El libro de teoría, abierto en el capítulo de conducción de voces](capturas/06-libro.png)

El libro no está escrito entero de entrada: cada apartado está atado a un logro
y se escribe sólo cuando el usuario se topa con esa cadencia, ese movimiento o
ese recurso. Cuando eso pasa, el apartado nuevo aparece con una anotación a
mano al pie.

Dos capítulos se abren de una vez y no de a un apartado: *Armonizar una
melodía*, la primera vez que se usa el Armonizador --- explica dónde va cada
acorde y en qué intervalo suele caer la nota de la melodía, con los mismos
pesos que usa el motor ---, y *La física en la música*, la primera vez que se
usa el experimentador de armónicos. Ese último es el único capítulo con
gráficos a escala: la serie armónica dibujada por frecuencia y amplitud, la
serie subarmónica, dos timbres sobre la misma nota, y la ampliación donde se
ve que el séptimo armónico no cae en ninguna tecla del piano.

Y se avisa: por unos segundos aparece esa misma anotación a mano en el medio del
pie --- *Has descubierto algo nuevo* --- y después se va sola. Lo que espera es el
libro, donde el capítulo que recibió lo nuevo queda en azul en el índice hasta
que se lo lea.

## Modo historia

Después de cinco minutos de uso --- y sólo con la pantalla inicial a la vista, el
tutorial terminado y ninguna búsqueda corriendo --- se enciende un botón dorado en
la pantalla inicial. No dice qué es. Cuando lo toques aparece una figura que
ofrece un poder, y lo que se le conteste abre uno de tres senderos:

| Respuesta | Sendero | Quién acompaña |
|---|---|---|
| Aceptar | Blues | el señor del sombrero |
| Ignorar | Jazz | un guitarrista anónimo |
| Rechazar | Góspel | Jesús |

Cada sendero son tres tramos y siempre en los mismos tres lugares: una progresión
escrita a mano en el **Organizador**, un botón dorado en el **Generador** y un
gesto dorado en el **Armonizador**. Los dos botones dorados nacen bloqueados:
para encenderlos hay que repetir la cadencia del tramo en tres tonalidades
distintas, y leer el apartado nuevo que el sendero escribió en el libro.

Los tramos automáticos no pasan por el algoritmo genético ni por los parámetros:
la pieza --- los doce compases del blues, *All of Me*, la regla de la octava del
góspel, *Amazing Grace* --- está escrita de antemano y sale al instante. Tampoco
reparten logros: la escribió el programa, no vos. Sí quedan en el historial y se
pueden exportar como cualquier otra.

El capítulo **VIII** del libro, *La música de los reprimidos*, se llena con los
tramos recorridos en vez de con logros. Cuenta de dónde salió cada cosa: el
cruce de caminos del delta del Misisipi, los jazzes que no son uno solo, los
*spirituals* y el capitán de barco negrero que escribió *Amazing Grace*.

Al final de cada camino se entrega el logro legendario que le corresponde, su
título y un recuerdo, que queda al lado de los títulos en la pantalla de logros.
Ahí mismo está el botón **Arrepentirse**: vuelve a la encrucijada y deja elegir
de nuevo. Lo conseguido no se pierde --- los logros, los títulos y lo que quedó
escrito en el libro siguen siendo tuyos --- y lo único que vuelve a cero es el
sendero.

![Una figura a lo lejos, de noche, en un valle](capturas/misterio.png)

*Algo interrumpe el trabajo.*

Todo el sonido de las escenas --- el viento del valle, los pájaros, la voz de cada
personaje, el coro, los vientos que cierran un tema --- está sintetizado por el
programa, igual que el audio del botón `Escuchar`. No se empaqueta ningún archivo
de sonido.

## Paralelismo

La búsqueda usa varios procesos, no hilos: es trabajo de CPU puro en Python y
el GIL haría que los hilos se turnen en vez de correr en paralelo. La cantidad
se decide sola según la máquina donde corre (`workers=None`):

- deja un núcleo libre para que la ventana siga respondiendo,
- topea en 8 porque más allá el costo de serializar supera la ganancia,
- y se desactiva en trabajos chicos, donde paralelizar cuesta más de lo que ahorra.

Podés forzar un número con `GAConfig(workers=N)`.

## Géneros

| Género      | Paralelas 5tas/8vas | Tritono   | Voicings especiales | Carácter |
|-------------|---------------------|-----------|---------------------|----------|
| `classical` | prohibidas          | libre     | sí                  | premia movimiento contrario, saltos chicos |
| `chorale`   | prohibidas          | libre     | sí                  | como el clásico pero más estricto en espaciado y tesitura |
| `gregorian` | permitidas (organum)| prohibido | no                  | casi todo por grado conjunto |
| `jazz`      | permitidas          | libre     | sí                  | voicings cerrados, mantiene tensiones |

Todos los switches se pueden prender y apagar por separado; el género sólo
define el valor inicial.

## Reglas de contrapunto por género

Además de minimizar el movimiento, el fitness pondera las reglas propias de
cada tradición (ver `engine/style.py`):

- **Clásico / coral**: nunca duplicar la sensible; la séptima resuelve bajando
  y la sensible subiendo; sin solapamiento de voces entre acordes contiguos;
  saltos de tritono y séptima castigados; un salto grande se compensa con
  movimiento contrario; se premian las notas comunes y el movimiento contrario
  al bajo. El coral aplica todo esto más fuerte.
- **Gregoriano**: casi todo por grado conjunto, ámbito estrecho, segundas y
  séptimas entre voces castigadas, tritono prohibido por defecto.
- **Jazz**: se premia que las guide tones (3ra y 7ma) se conecten por grado
  conjunto, las séptimas bajan, se mantienen notas comunes y se evitan las
  novenas menores (avoid notes).

## Reglas duras vs penalizaciones

**Duras** (anulan el cromosoma, nunca aparecen en el resultado):
rangos vocales, cobertura del acorde, cruce de voces, y lo que prendas de
paralelas / tritono.

**Ponderadas** (el AG las negocia): movimiento total (el peso más grande),
tamaño de saltos, espaciado, tesitura, repetición estática de acorde,
quintas directas, movimiento contrario.

## Compilar el motor (opcional)

Los tres módulos que la búsqueda pisa millones de veces por corrida --el
evaluador, las reglas de estilo y la representación de las notas-- se pueden
compilar a C con Cython:

```bash
pip install cython setuptools     # además de MSVC (Build Tools de Visual Studio)
python build_engine.py            # deja engine/*.pyd al lado de los .py
python build_engine.py --clean    # los borra y vuelve a Python puro
```

**Es opcional y no cambia nada de lo que el programa hace.** Los `.py` no se
tocan: se compilan tal como están, con una hoja de tipos aparte
(`engine/fitness.pxd`, `engine/style.pxd`) que Python ignora. Si el `.pyd`
está al lado del `.py`, Python lo prefiere solo; si no está, corre el `.py`.
Sin compilador el programa anda igual, más lento, y `pyinstaller
ChordWeaver.spec` sigue dando un ejecutable que funciona.

Medido sobre 16 acordes con la búsqueda de fábrica (200x300): la búsqueda pasa
de 17,4 a 8,2 segundos en un proceso y de 8,3 a 5,7 con los ocho del pool. El
resultado es idéntico bit a bit --verificado sobre 14 corridas, cuatro géneros
por tres semillas más los dos modos generativos.

## Empaquetar el .exe

```bash
pip install pyinstaller customtkinter
pyinstaller ChordWeaver.spec
```

Queda en `dist/ChordWeaver/`, portable: copiala a donde quieras. Es build de
carpeta y no `--onefile` a propósito, porque con onefile el programa se
descomprime en un temporal y el historial no persistiría al lado del exe.

## Auditoría contrapuntística (`python audit.py`)

La pregunta que responde: ¿cada género *realmente* escribe según su tradición,
o todos convergen a "la solución que menos se mueve" con distinta etiqueta?

El script corre varias progresiones con cada género y mide el resultado contra
reglas que el fitness nunca ve como un solo número, comparando siempre contra
un control: la misma búsqueda con todos los pesos de estilo apagados.

Resultados medidos (promedio sobre 4 progresiones x 2 semillas):

| métrica | control | clásico | coral | gregoriano | jazz |
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

- **Clásico y coral se diferencian con claridad.** El movimiento contrario casi
  se duplica y las séptimas pasan de resolver 68% a 86-96%. No es placebo.
- **Jazz se diferencia moderadamente**: las guide tones conectan por grado 52%
  contra 42% del control.
- **Gregoriano es el más débil**, y hay una razón estructural: el carácter modal
  vive sobre todo en la *armonía* (cadencias modales, ausencia de sensible,
  quintas al aire), y en esta app los acordes los elige el usuario. Lo único que
  el AG controla es el registro y el reparto de notas. Igual se diferencia donde
  sus reglas apuntan: ambitus 3.8 contra 4.7, y más intervalos perfectos.
- Los géneros con reglas fuertes **pagan** movimiento por estilo (1.3 contra 1.2
  semitonos de media), que es exactamente el intercambio que se busca.

Durante la auditoría se detectó que el umbral de ambitus estaba en 9 semitonos
cuando los ámbitos reales rondan 5, o sea que la regla no se activaba nunca.
Corregido a 5.

## Las visitas

Aparte del sendero hay seis apariciones sueltas. No se eligen y no se pueden
abandonar: ocurren cuando ocurren, y cada una deja algo. La tabla son las cinco
que se pueden provocar; las otras dos van más abajo.

| Quién | Cuándo | Qué deja |
|---|---|---|
| Bach | a la quinta partitura barroca | el capítulo IX del libro |
| Bach, otra vez | la primera vez que se usa el modo coral | otro apartado |
| Gregorio I | a la quinta partitura gregoriana | otro apartado |
| Alguien de negro | al armar tres sonidos en el experimentador | otro apartado, y *La cuarta pared* |
| Una entidad encapuchada | al conseguir el 100% de los logros | la partitura quemada y la lista de los huevos |

Los dos maestros felicitan y explican: Bach, que la música se escribía en voces
y no en acordes, y que es lo que separa a un coral de todo lo demás; Gregorio,
el organum --- la *vox principalis* y su sombra a la quinta ---, que es de donde
sale todo lo que el programa hace. Los dos cierran con una cita suya de verdad.

El de negro es el único que sabe que esto es un programa, y por eso es el único
que puede contar las dos mitades del mismo asunto sin cambiar de tema: de dónde
sale la serie armónica, y cómo se escribe eso en una máquina --- cuarenta y
cuatro mil cien números por segundo, dieciséis bits cada uno. Casi no se lo ve:
es una silueta a contraluz de su propia pantalla.

La entidad no explica nada. Dice que estuvo mirando, que no entiende cómo se
llegó hasta ahí, y avisa de alguien que va a venir. Deja el cuarto objeto ---
una partitura quemada de la que no se llega a leer de quién es --- y, al pie de
la pantalla de logros, la lista de los seis huevos de pascua con los pasos
exactos para provocarlos. Es lo único del programa que los nombra: hasta ese
momento el contador dice cuántos hay y ninguno cuál.

La quinta aparición es **la visión**, y es la única que no se puede provocar de
ninguna manera. Al abrir el programa, una vez de cada cinco --- con el tutorial
ya hecho u omitido --- y una sola vez en la vida, se ve un camino de tierra de
noche, la luna llena y un tren cruzando a lo
lejos. Nadie habla y el programa tampoco: no avisa nada al terminar. Queda
escrita en el libro la historia de Robert Johnson, en dorado, como un legendario,
y hay que ir a encontrarla.

Y hay una sexta, que es la misma noche otra vez. Corre el mismo sorteo, en los
arranques en que la primera ya ocurrió, y también pasa una sola vez. Empieza
igual --- el mismo camino, el mismo tren, la misma figura parada en el medio ---
y termina distinto: la pantalla se apaga de golpe y vuelve con dos. Él sigue de
frente y donde estaba; delante suyo, de espaldas y en negro puro, hay alguien
que no estaba. Después queda negro y se dice lo único que se dice en las dos
escenas: *«Una sabia decisión…»*. Al continuar, negro otra vez y de vuelta al
menú. Deja otro apartado dorado en el mismo
capítulo, sobre el supuesto pacto y lo que la historia le hizo a esta música
durante ochenta años.

Para volver a mirarlas hay dos caminos. En la configuración --- el engranaje ---
hay una sección **Volver a ver** con un botón por aparición, y **aparece
solamente la que ya te ocurrió**: listarlas todas contaría, con nombre y
condición, las seis cosas que el programa esconde. Y desde afuera, tres
variables de entorno:
`CHORDWEAVER_VISIT` fuerza una visita al abrir (`watcher`, `bach_baroque`,
`bach_chorale`, `gregory`), `CHORDWEAVER_VISION=1` fuerza la visión y
`CHORDWEAVER_PACT=1` la segunda.

Las dos formas juegan la escena entera y entregan lo que entrega de verdad, así
que la que mires desde ahí no vuelve a aparecer sola.

## Importar una partitura

Hay tres puertas para traer música de afuera, y cada una lee el archivo de
una manera distinta porque le sirve otra cosa: el Organizador junta lo que
suena a la vez y lo lee como acordes, el Armonizador se queda con la nota más
aguda de cada momento, y el analizador conserva **cada voz por separado** ---
que es lo único con lo que se puede medir un contrapunto.

En el modo de acordes propios, el botón `Importar partitura...` lee un archivo
MusicXML (`.musicxml`, `.xml` o `.mxl` comprimido) y carga sus acordes con su
ritmo y sus compases. El orden de las voces que trae el archivo queda como
punto de partida y es lo que propone el candado, pero el programa puede
reacomodarlo: para eso se importa. Si querés conservar una disposición tal
cual vino, fijala con el candado.

## Cómo contribuir

Las reglas del proyecto --- qué no se toca, qué hay que correr antes de un pull
request y las cinco trampas que fallan en silencio --- están en
[`CONTRIBUTING.md`](CONTRIBUTING.md). Antes de tocar cualquier cosa musical,
[`MUSIC_LOGIC.md`](MUSIC_LOGIC.md).

## Estado

- Parte 1 (motor): terminada y testeada (384 tests).
- Parte 2 (interfaz): terminada. Probada de punta a punta bajo display virtual (Claude) y real.

## Licencia

[MIT](LICENSE).
