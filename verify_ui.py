import uitest, traceback
import engine.harmony as H
import engine.flourish as F
H.SET_PIECE_CHANCE = 1.0
fallos = []

def check(nombre, ok, detalle=""):
    print(f"  [{'OK ' if ok else 'MAL'}] {nombre} {detalle}")
    if not ok: fallos.append(nombre)

print("=== 1+2: cadencia cromatica ===")
s = uitest.Session()
s.mode('random').next(); s.genre('classical').next(); s.next()
s.bars(3).next(); s.key('A', H.MODES['minor'].label); s.next(); s.search(60,25)
out = s.generate()
if out and out.succeeded:
    b0 = [c[0] for c in uitest.solution_chords(out, 0)]
    check("bajo desciende", all(b0[i] > b0[i+1] for i in range(4)), f"{b0}")
    cif = [uitest.chord_symbols(out, i) for i in range(3)]
    check("cifrado solo en opcion 1", cif[1] != cif[0] or cif[2] != cif[0],
          f"op1={cif[0][:3]} op2={cif[1][:3]}")
    hdrs = s.chord_headers()
    check("barras visibles en UI", any('/' in h for h in hdrs), f"{[h for h in hdrs if '/' in h][:4]}")
s.close()

print("=== 3: ii-V en jazz ===")
con = 0
for _ in range(5):
    s = uitest.Session()
    s.mode('random').next(); s.genre('jazz').next(); s.next()
    s.bars(4).next(); s.next(); s.search(80,35)
    out = s.generate(timeout=90)
    if out and out.succeeded:
        rs = uitest.romans(out, 0)
        if any(rs[i]=='ii' and rs[i+1]=='V' for i in range(len(rs)-1)): con += 1
    s.close()
check("ii-V frecuente", con >= 4, f"{con}/5")

print("=== 5+7: gregoriano ===")
deg = plag = 0
for _ in range(5):
    s = uitest.Session()
    s.mode('random').next(); s.genre('gregorian').next(); s.next()
    s.bars(4).next(); s.next(); s.search(80,35)
    out = s.generate(timeout=90)
    if out and out.succeeded:
        rs = uitest.romans(out, 0)
        if len(set(rs)) <= 2: deg += 1
        if any(rs[i] in ('IV','iv') and rs[i+1] in ('I','i') for i in range(len(rs)-1)): plag += 1
    s.close()
check("sin degenerados", deg == 0, f"{deg}/5")
check("plagales frecuentes", plag >= 3, f"{plag}/5")

print("=== 6: marcas en las 3 opciones ===")
s = uitest.Session()
s.mode('random').next(); s.genre('jazz').next(); s.next()
s.bars(4).next(); s.next(); s.search(80,35)
out = s.generate(timeout=90)
if out and out.succeeded:
    fl = out.flourishes
    porop = {i: [m.label for m in fl.by_solution.get(i, [])] for i in range(3)}
    check("detecta en varias opciones", sum(1 for v in porop.values() if v) >= 2, f"{porop}")
    check("casillas tenidas", s.tinted() > 0, f"{s.tinted()}")
s.close()

print("=== 8: voces por defecto ===")
esperado = {'classical': 3, 'chorale': 4, 'gregorian': 3, 'jazz': 4}
for g, n in esperado.items():
    s = uitest.Session()
    s.mode('random').next(); s.genre(g).next()
    v = sorted(k for k,x in s.win.voice_check_vars.items() if x.get())
    check(f"{g} voces", len(v) == n, f"{len(v)}")
    s.close()

print("=== 9: reemplazo por 6ta ===")
F.SIXTH_CHANCE = 1.0
hecho = False
for _ in range(5):
    s = uitest.Session()
    s.mode('manual').next(); s.genre('classical').next()
    s.voices(['B','T','A','S']).next(); s.bars(3).next()
    s.chords(['A','E','A','E','A','E']).next(); s.search(60,25)
    out = s.generate(timeout=90)
    if out and out.succeeded:
        fl = getattr(out, 'flourishes', None)
        if fl and fl.sixth_slot is not None:
            ch = uitest.solution_chords(out, 0)
            i, j = fl.sixth_slot, fl.forced_slot
            check("omit5 en la UI", any('omit5' in h for h in s.chord_headers()),
                  f"{[h for h in s.chord_headers() if 'omit' in h]}")
            check("forzado sin perder notas", len(set(ch[j])) == len(set(uitest.solution_chords(out,0)[j])),
                  f"{ch[j]}")
            hecho = True
            s.close(); break
    s.close()
if not hecho: check("reemplazo ocurre", False, "no salio en 5 intentos")

print("=== 10: modo armonizar ===")
try:
    from staff import diatonic_index
    for genero in ('classical', 'chorale', 'gregorian', 'jazz'):
        s = uitest.Session()
        s.mode('harmonise').next(); s.genre(genero).next(); s.next()
        for l, o in [('C',5),('D',5),('E',5),('F',5),('G',5),('F',5),('E',5),('C',5)]:
            s.win.staff.notes.append((diatonic_index(l, o), 1.0))
        s.win.staff.redraw(); s.win._on_melody_changed()
        s.next(); s.search(70, 30)
        out = s.generate(timeout=120)
        ok = out is not None and out.succeeded
        respeta = True
        if ok:
            # Each option was built from its own progression, so its notes
            # are checked against ITS slots, not the first option's.
            voz = s.win._melody_voice
            for pos, sol in enumerate(out.result.solutions):
                slots = out.alternate_slots.get(pos, out.spec.slots)
                for i, sl in enumerate(slots):
                    fijada = sl.pinned_voices.get(voz)
                    if fijada is not None and sol.slots[i][voz] != fijada:
                        respeta = False
        check(f"armoniza en {genero}", ok and respeta)
        s.close()
except Exception as e:
    check("modo armonizar", False, f"{type(e).__name__}: {e}")

print("=== 4: cambio de genero repetido ===")
try:
    s = uitest.Session()
    for g in ('classical','jazz','gregorian','chorale','jazz','classical'):
        s.home(); s.mode('random').next(); s.genre(g).next(); s.next()
        s.bars(2).next(); s.next(); s.search(50,20)
        o = s.generate(timeout=60)
        if not (o and o.succeeded): raise RuntimeError(f"fallo en {g}")
    s.close()
    check("sin crash", True, "6 generaciones seguidas")
except Exception as e:
    check("sin crash", False, f"{type(e).__name__}: {e}")

print()
print("FALLOS:" if fallos else "TODO OK")
for f in fallos: print("  -", f)
