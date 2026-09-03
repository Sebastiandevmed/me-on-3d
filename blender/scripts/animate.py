# blender/scripts/animate.py
"""Las 7 animaciones de 'Me on 3D' como acciones + pistas NLA.

Uso: tools/run_blender.sh blender/character.blend blender/scripts/animate.py
Guarda SOLO blender/character_anim.blend (nunca character.blend ni scene.blend).

Reglas de la tarea:
  * El rig de Meshy NO tiene huesos de dedos: `typing` mueve manos y antebrazos.
  * Solo `vibe` y `lookAround` tocan spine006 (la cabeza).
  * `typing` toca unicamente huesos de brazo/mano (jamas columna ni cabeza).
  * Solo `vibe` mueve el hueso `headphones` (la pieza de audifonos).
  * Cada accion keyframea en su frame 1 la pose SIT completa de los huesos que anima,
    asi el clip es autocontenido al exportarse a glTF.
  * Duraciones a 24 fps: introAnimation 72, typing 48, idle 96, Blink 240,
    browup 18, vibe 216, lookAround 96. Todas empiezan en el frame 1 y la pista
    NLA se llama igual que la accion.

Ejes de los brazos: upper_arm/forearm/hand tienen ejes locales a ~45 grados del plano
sagital, asi que `poses.rot()` NO sirve. Los valores de SIT salieron de `poses.aim()`
apuntando cada hueso a una direccion del mundo; aqui se hace lo mismo perturbando esas
direcciones base (verificado contra SIT: reproducen exactamente TYPING_HOME).
"""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common, poses
from poses import rot, SIT
from mathutils import Vector

arm = bpy.data.objects['Armature']
sc = bpy.context.scene
sc.render.fps = common.FPS

HEAD = 'spine006'
NECK = 'spine005'
SPINE = ['spine001', 'spine002', 'spine003']
ARM_BONES = ['upper_armL', 'upper_armR', 'forearmL', 'forearmR', 'handL', 'handR']
LIDS = ['eyelidL', 'eyelidR']
BROWS = ['eyebrow_L', 'eyebrow_R']

# Direcciones del mundo que reproducen TYPING_HOME con poses.aim() (sx = +1 en L, -1 en R).
SX = {'L': 1.0, 'R': -1.0}
DIR_UPPER = lambda s: (-SX[s] * 0.06, 0.0, -0.998)      # brazo vertical, codo al torso
DIR_FORE = lambda s: (SX[s] * 0.13, 0.99, 0.02)         # antebrazo adelante y al centro
DIR_HAND = lambda s: (SX[s] * 0.05, 0.995, 0.0)         # mano horizontal sobre el teclado
# Brazos colgando (pose reclinada del intro).
DIR_UPPER_DOWN = lambda s: (-SX[s] * 0.16, -0.30, -0.94)
DIR_FORE_DOWN = lambda s: (-SX[s] * 0.10, 0.10, -0.99)
DIR_HAND_DOWN = lambda s: (-SX[s] * 0.04, 0.22, -0.97)


# --------------------------------------------------------------------------- utilidades

fcurves_of = common.fcurves_of


def key(bone, frame, euler=None, loc=None):
    pb = arm.pose.bones.get(bone)
    if pb is None:      # un nombre mal escrito perderia el canal en silencio
        raise KeyError(f'key(): el hueso {bone!r} no existe en {arm.name}')
    pb.rotation_mode = 'XYZ'
    if euler is not None:
        pb.rotation_euler = euler
        pb.keyframe_insert('rotation_euler', frame=frame)
    if loc is not None:
        pb.location = loc
        pb.keyframe_insert('location', frame=frame)


def key_pose(frame, pose):
    for b, e in pose.items():
        key(b, frame, e)


def base(bones, frame=1):
    """Escribe la pose SIT de `bones` en `frame` (clip autocontenido)."""
    for b in bones:
        if b in SIT:
            key(b, frame, SIT[b])
        elif b in LIDS:
            key(b, frame, (0.0, 0.0, 0.0))
        elif b in BROWS:
            key(b, frame, loc=(0.0, 0.0, 0.0))


def new_action(name, bones_for_base):
    act = bpy.data.actions.new(name)
    ad = arm.animation_data
    ad.action = act
    if hasattr(ad, 'action_slot'):      # Blender 4.4+: la accion necesita un slot
        try:
            slot = act.slots[0] if len(act.slots) else act.slots.new('OBJECT', arm.name)
            ad.action_slot = slot
        except Exception as exc:
            print('SLOT_AUTO', name, exc)
    base(bones_for_base, 1)
    return act


def finish(act, length, cyclic):
    for fc in fcurves_of(act):
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
        if cyclic and not any(m.type == 'CYCLES' for m in fc.modifiers):
            fc.modifiers.new('CYCLES')
    act.use_frame_range = True
    act.frame_start, act.frame_end = 1, length
    arm.animation_data.action = None
    track = arm.animation_data.nla_tracks.new()
    track.name = act.name
    strip = track.strips.new(act.name, 1, act)
    strip.name = act.name
    strip.frame_start, strip.frame_end = 1, length
    track.mute = True   # las pistas no se mezclan en Blender; el exportador glTF las lee igual
    print('CLIP', act.name, length, 'fcurves', len(fcurves_of(act)))
    return act


def solve_arms(torso=None, upper=None, fore=None, hand=None):
    """Resuelve los eulers de la cadena del brazo apuntando a direcciones del mundo.

    Aplica SIT a todo el rig, encima el `torso` del frame (para que los brazos queden
    coherentes con la inclinacion), y luego aim() en orden padre->hijo.
    Devuelve {hueso: euler}.
    """
    poses.apply(arm, SIT)
    if torso:
        for b, e in torso.items():
            pb = arm.pose.bones.get(b)
            if pb:
                pb.rotation_mode = 'XYZ'
                pb.rotation_euler = e
    bpy.context.view_layer.update()
    out = {}
    for s in 'LR':
        if upper:
            out[f'upper_arm{s}'] = poses.aim(arm, f'upper_arm{s}', upper(s))
        if fore:
            out[f'forearm{s}'] = poses.aim(arm, f'forearm{s}', fore(s))
        if hand:
            out[f'hand{s}'] = poses.aim(arm, f'hand{s}', hand(s))
    return out


# --------------------------------------------------------------------------- audifonos
HP = 'headphones'
HP_JSON = os.path.join(common.BLEND_DIR, 'headphones.json')
HP_ON = poses.headphones_on()
if HP_ON is None:
    common.fail('falta blender/headphones.json (ejecutar add_headphones.py)')
with open(HP_JSON) as _f:
    HP_DATA = json.load(_f)


def hp_state(u):
    """Interpola el hueso headphones entre reposo (u=0, colgando del cuello) y puestos (u=1)."""
    eul = tuple(lerp(0.0, HP_ON[0][i], u) for i in range(3))
    loc = tuple(lerp(0.0, HP_ON[1][i], u) for i in range(3))
    return eul, loc


def cup_world(side, u):
    """Centro de la copa `side` en el mundo con el hueso headphones en el estado u (0..1).
    Requiere que el resto de la pose (torso, cabeza) ya este aplicada.

    `cup_offset_rest` esta en la trama de REPOSO del hueso (add_headphones.py lo midio con
    `A.inverted() @ centro`, A = matrix_world @ bone.matrix_local), asi que basta con pasarlo por
    `pb.matrix`, que ya lleva dentro el basis del estado u que acaba de poner `hp_state`.
    `cup_offset_head` del JSON es redundante: es exactamente `basis_on @ cup_offset_rest`
    (verificado, error 6e-5 m). Interpolarlos linealmente seria recorrer la CUERDA de un arco de
    70 grados y radio 0.134 m: 2.2 cm de error en u = 0.5, justo en los frames de agarre a media
    altura.
    """
    pb = arm.pose.bones[HP]
    eul, loc = hp_state(u)
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = eul
    pb.location = loc
    bpy.context.view_layer.update()
    return arm.matrix_world @ (pb.matrix @ Vector(HP_DATA['cup_offset_rest'][side]))


def seg_len(parent, child):
    """Largo real de un segmento: distancia entre las cabezas de dos huesos en reposo.

    OJO: `bone.length` NO sirve en este rig. El importador de Meshy dejo los tails en la
    direccion correcta pero 100 veces mas lejos (upper_armL: length 25.99 m, segmento 0.26 m).
    """
    return (arm.data.bones[child].head_local - arm.data.bones[parent].head_local).length


def reach(side, wrist_world, hand_dir, palm_dir, elbow_hint):
    """IK analitica de dos huesos: coloca la muneca (cabeza de hand<side>) en `wrist_world`.

    `hand_dir` es hacia donde apuntan los dedos y `palm_dir` hacia donde mira la palma (los dos
    en el mundo). Devuelve {upper_arm, forearm, hand: euler}. El resto de la pose debe estar
    aplicada.
    """
    s = side
    ua, fa, ha = f'upper_arm{s}', f'forearm{s}', f'hand{s}'
    for b in (ua, fa, ha):
        arm.pose.bones[b].rotation_euler = SIT[b]
    bpy.context.view_layer.update()
    S = arm.matrix_world @ arm.pose.bones[ua].head
    L1, L2 = seg_len(ua, fa), seg_len(fa, ha)
    T = Vector(wrist_world)
    d = T - S
    dist = min(d.length, (L1 + L2) * 0.995)
    if dist < 1e-6:
        common.fail('reach: objetivo en el hombro')
    d.normalize()
    # angulo del brazo respecto a la recta hombro-muneca (ley de cosenos)
    cos_a = max(-1.0, min(1.0, (L1 * L1 + dist * dist - L2 * L2) / (2 * L1 * dist)))
    a = math.acos(cos_a)
    hint = Vector(elbow_hint).normalized()      # obligatorio: hoy siempre ELBOW_HINT(s)
    perp = hint - d * hint.dot(d)
    perp.normalize()
    E = S + (d * math.cos(a) + perp * math.sin(a)) * L1
    out = {ua: poses.aim(arm, ua, tuple(E - S))}
    out[fa] = poses.aim(arm, fa, tuple(T - E))
    out[ha] = poses.aim_roll(arm, ha, tuple(Vector(hand_dir)), tuple(Vector(palm_dir)),
                             poses.PALM_LOCAL[s])
    return out


def lids(frame, deg):
    for b in LIDS:
        key(b, frame, (math.radians(deg), 0.0, 0.0))


def neck(fwd_deg, yaw_deg=0.0):
    """spine005: X local inclina adelante, +Y local gira la cara a su izquierda (-X mundo)."""
    return (math.radians(fwd_deg), math.radians(yaw_deg), 0.0)


def lerp(a, b, u):
    return a + (b - a) * u


def lerp3(a, b, u):
    return tuple(lerp(a[i], b[i], u) for i in range(3))


# --------------------------------------------------------------------------- limpieza
ad = arm.animation_data or arm.animation_data_create()
for t in list(ad.nla_tracks):        # el importador de Meshy dejo 'Armature|clip0|baselayer'
    ad.nla_tracks.remove(t)
ad.action = None
for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
poses.apply(arm, SIT)

# Guardia: la pose de brazos del frame 1 de typing/intro (solve_arms con las direcciones
# base, up=0) tiene que reproducir los eulers de brazos horneados en poses.SIT. Si se
# reimporta el rig (otros ejes locales de hueso) SIT queda invalidado y esto lo delata.
def check_sit_arms(tol_deg=1.0):
    from mathutils import Euler
    solved = solve_arms(upper=DIR_UPPER, fore=DIR_FORE, hand=DIR_HAND)
    worst = 0.0
    for b, e in solved.items():
        qa = Euler(e, 'XYZ').to_quaternion(); qb = Euler(SIT[b], 'XYZ').to_quaternion()
        d = math.degrees(qa.rotation_difference(qb).angle)
        worst = max(worst, d)
        if d > tol_deg:
            common.fail(f'solve_arms() no reproduce poses.SIT en {b}: {d:.2f} grados de diferencia '
                        f'(tolerancia {tol_deg}); recalibrar TYPING_HOME en poses.py con poses.aim()')
    print('SIT_ARMS_OK max_diff_deg', round(worst, 3))
    poses.apply(arm, SIT)
check_sit_arms()


# --------------------------------------------------------------------------- 1) typing
# 48 frames en bucle. Sin dedos: cada mano "golpea" 6 veces por ciclo en instantes irregulares
# (no a contratiempo perfecto) con una bajada rapida de 2 frames desde un hover bajo; entre
# golpes las manos apenas flotan (HOVER) y derivan lateralmente despacio como si buscaran
# teclas. La carrera maxima (0.18) es menor que la version 1 (0.30), que parecia dar masajes.
# `up` = 0 es la pose SIT (palma sobre el laptop); 1 = mano arriba.
STRIKES = {'L': (3, 11, 17, 27, 35, 43), 'R': (7, 13, 21, 31, 39, 45)}
# El bucle de abajo solo keyframea los frames impares (range(1, 50, 2)): el fondo del golpe
# (up = 0) cae en un key SOLO si el frame del golpe es impar. Con un golpe en frame par el
# bezier lo suaviza y el golpe desaparece.
assert all(f % 2 == 1 for v in STRIKES.values() for f in v), 'STRIKES: los golpes deben caer en frames impares'
HOVER, STROKE, DIP_FRAMES = 0.35, 0.18, 2.0


def typing_up(side, f):
    """0..1: hover entre golpes, cae a 0 en el frame del golpe (ventana triangular de 2 frames)."""
    fc = ((f - 1) % 48) + 1
    best = min(min(abs(fc - s), 48 - abs(fc - s)) for s in STRIKES[side])
    dip = max(0.0, 1.0 - best / DIP_FRAMES)
    return HOVER * (1.0 - dip)


act = new_action('typing', ARM_BONES)
for f in range(1, 50, 2):                       # 1..49; el 49 repite el 1 (bucle limpio)
    t = (f - 1) / 48.0 * 2 * math.pi
    drift = 0.02 * math.sin(t)                  # deriva lateral lenta (m, en la direccion de la mano)
    up = lambda s: typing_up(s, f)
    key_pose(f, solve_arms(
        upper=lambda s: (-SX[s] * 0.06 + drift * 0.3, 0.0 + 0.012 * up(s), -0.998),
        fore=lambda s: (SX[s] * 0.13 + drift, 0.99, 0.02 + 0.05 * up(s)),
        hand=lambda s: (SX[s] * 0.05 + drift, 0.995, STROKE * up(s)),
    ))
finish(act, 48, cyclic=True)


# --------------------------------------------------------------------------- 2) idle
# Respiracion sutil en la columna (2 ciclos en 96 frames). SOLO spine001/002/003/005: los
# brazos siguen al torso como hijos, y asi `typing` puede superponerse en el reproductor
# web sin que el mixer promedie escrituras sobre los mismos huesos (idle = base continua,
# typing encima con huesos disjuntos; vibe/lookAround en exclusiva con idle fundido).
# El cuello contrarresta para que la cabeza (no animada) quede quieta.
IDLE_BONES = SPINE + [NECK]
act = new_action('idle', IDLE_BONES)


def idle_torso(t):
    return {
        'spine003': rot('spine003', 6 + 1.5 * math.sin(t)),
        'spine002': rot('spine002', 4 + 1.9 * math.sin(t + 0.25)),
        'spine001': rot('spine001', 2 + 0.9 * math.sin(t + 0.5)),
        NECK: rot(NECK, 4 - 1.7 * math.sin(t + 0.35)),
    }


for f in range(1, 98, 8):                       # 1..97; el 97 repite el 1
    t = (f - 1) / 96.0 * 2 * 2 * math.pi        # dos respiraciones
    key_pose(f, idle_torso(t))
finish(act, 96, cyclic=True)


# --------------------------------------------------------------------------- 3) Blink
# 240 frames en bucle con 2 parpadeos rapidos. Cerrado <= 4 frames (el parpado recorre
# ~2 cm: mas tiempo cerrado se ve como si se saliera de la cabeza).
act = new_action('Blink', LIDS)
lids(1, 0)
for start in (58, 163):
    lids(start, 0)
    lids(start + 2, 70)
    lids(start + 4, 70)
    lids(start + 8, 0)
lids(240, 0)
finish(act, 240, cyclic=True)


# --------------------------------------------------------------------------- 4) browup
# 18 frames: sube las cejas y vuelve. +0.012 en Z local es el tope (mas deja ver la ceja pintada).
act = new_action('browup', BROWS + LIDS)
for b in BROWS:
    key(b, 1, loc=(0, 0, 0))
    key(b, 5, loc=(0, 0, 0.012))
    key(b, 11, loc=(0, 0, 0.012))
    key(b, 18, loc=(0, 0, 0))
for b in LIDS:                                  # los ojos se abren un pelo con la ceja
    key(b, 1, (0, 0, 0))
    key(b, 5, (math.radians(-5), 0, 0))
    key(b, 11, (math.radians(-5), 0, 0))
    key(b, 18, (0, 0, 0))
finish(act, 18, cyclic=False)


# --------------------------------------------------------------------------- 5) vibe
# 216 frames (9 s a 24 fps): se pone los audifonos con las manos, cabecea y se los quita.
#   f1-20    las manos suben del teclado a las copas (audifonos colgando del cuello), por un
#            arco por delante del pecho (key intermedio en f11)
#   f20-44   las manos llevan los audifonos a la cabeza (hueso headphones: reposo -> puestos)
#   f44-52   ajuste (pausa)
#   f52-76   las manos vuelven al teclado
#   f60-152  cabeceo de rap (ojos cerrados f66..f146), envolvente de 14 frames
#   f152-168 las manos suben a las copas (ya en la cabeza)
#   f168-192 bajan los audifonos al cuello
#   f192-216 las manos vuelven al teclado; f216 = SIT exacto (empalma con idle/typing)
# Cabeceo: spine006 oscila entre -16 (levantada, entre golpes) y +14 (golpe abajo); con env=0
# cae EXACTAMENTE en SIT (-8).
# Mientras la cabeza cabecea, el hueso `headphones` es hijo de spine006 y la acompana solo.
VIBE_BONES = [HEAD, NECK, 'spine003', 'shoulderL', 'shoulderR'] + LIDS + ARM_BONES + [HP]
VIBE_LEN = 216
BEAT = 15.0
# AGARRE de la copa: la palma apoyada en su cara EXTERIOR mirando hacia la cabeza y los dedos
# subiendo hacia atras (~45 grados), envolviendola. Es la MISMA pose relativa a la copa en el
# cuello (u=0) y en la cabeza (u=1): la mano sigue a la copa sin cambiar de agarre.
# `poses.aim()` solo fija la direccion del hueso, no su giro sobre el propio eje, y la mano
# salia con la palma al frente y los dedos rectos hacia arriba ("manos de jazz"); por eso la
# mano se resuelve con `poses.aim_roll()`, que ademas apunta la palma.
WRIST_OFF = lambda s: Vector((SX[s] * -0.058, 0.03, -0.045))   # afuera, algo adelante y abajo
HAND_DIR = (0.0, -0.50, 0.85)                    # dedos arriba y ATRAS (mira a +Y: atras = -Y)
PALM_DIR = lambda s: (SX[s] * 1.0, 0.0, 0.0)     # la palma mira hacia la cabeza
ELBOW_HINT = lambda s: (SX[s] * -1.0, 0.25, -0.6)   # codo al costado, algo adelante y abajo
# Arco del viaje teclado <-> copas: la muneca pasa por delante del pecho, no por el costado.
TRAVEL_ARC = lambda s: Vector((SX[s] * -0.03, 0.08, 0.0))


def smooth(u):
    return u * u * (3 - 2 * u)


poses.apply(arm, SIT)
bpy.context.view_layer.update()
SIT_WRIST = {s: (arm.matrix_world @ arm.pose.bones[f'hand{s}'].head).copy() for s in 'LR'}


def zero_shoulders():
    """Hombros en reposo antes de resolver la IK.

    `reach()` lee la matriz de mundo del hombro, que depende de shoulderL/R. Sin esto la IK
    dependeria del valor que las fases anteriores hayan dejado en esos huesos (hoy 0 por el
    orden en que se construye el clip, pero es una dependencia invisible).
    """
    for b in ('shoulderL', 'shoulderR'):
        arm.pose.bones[b].rotation_euler = (0.0, 0.0, 0.0)


def hands_to_cups(f, u_hp):
    """Coloca ambas manos en las copas con headphones en el estado u_hp y keyframea todo.

    Resuelve la IK con el torso y la cabeza en SIT: durante el cabeceo (f60-152) las manos
    estan en el teclado y no se recalculan, asi que la mezcla sigue siendo coherente.
    """
    poses.apply(arm, SIT)
    zero_shoulders()
    eul, loc = hp_state(u_hp)
    key(HP, f, euler=eul, loc=loc)
    for s in 'LR':
        cw = cup_world(s, u_hp)
        key_pose(f, reach(s, cw + WRIST_OFF(s), HAND_DIR, PALM_DIR(s), ELBOW_HINT(s)))


def hands_travel(f, u_hp, t):
    """Key intermedio del viaje teclado <-> copas (t = 0 teclado, 1 copas).

    Sin el, el bezier entre "palmas sobre el teclado" y el agarre pasaba por una pose de manos
    abiertas al frente. Aqui la muneca describe un arco por delante del pecho y los dedos giran
    de "adelante" (teclado) a "arriba y atras" (copa) con la palma ya mirando hacia adentro.
    """
    poses.apply(arm, SIT)
    zero_shoulders()
    eul, loc = hp_state(u_hp)
    key(HP, f, euler=eul, loc=loc)
    for s in 'LR':
        goal = cup_world(s, u_hp) + WRIST_OFF(s)
        w = Vector(lerp3(SIT_WRIST[s], goal, t)) + TRAVEL_ARC(s) * math.sin(math.pi * t)
        key_pose(f, reach(s, w, lerp3(DIR_HAND(s), HAND_DIR, t), PALM_DIR(s), ELBOW_HINT(s)))


def key_arms_sit(f):
    for b in ARM_BONES:
        key(b, f, SIT[b])


def nod(f, env):
    t = (f - 60) / BEAT * 2 * math.pi
    pulse = max(0.0, math.sin(t)) ** 1.5                            # golpe hacia abajo
    nod_deg = -8 + env * (30 * pulse - 8)                           # env=0 -> SIT (-8)
    key(HEAD, f, rot(HEAD, nod_deg, side_deg=env * 5.0 * math.sin(t / 2)))
    key(NECK, f, neck(4 + env * 6.0 * pulse, env * 2.5 * math.sin(t / 2)))
    key('spine003', f, rot('spine003', 6 + env * 4.5 * math.sin(t)))
    key('shoulderL', f, rot('shoulderL', env * 6.0 * math.sin(t)))
    key('shoulderR', f, rot('shoulderR', env * 6.0 * math.sin(t + math.pi)))


act = new_action('vibe', VIBE_BONES)
key(HP, 1, euler=(0, 0, 0), loc=(0, 0, 0))
# fase 1: teclado -> copas en el cuello
key_arms_sit(1)
hands_travel(11, 0.0, 0.5)
hands_to_cups(20, 0.0)
# fase 2: subir los audifonos
for f, u in ((26, 0.15), (32, 0.45), (38, 0.8), (44, 1.0)):
    hands_to_cups(f, smooth(u))
# fase 3: ajuste
hands_to_cups(52, 1.0)
# fase 4: manos al teclado (los audifonos se quedan puestos)
hands_travel(64, 1.0, 0.5)
key_arms_sit(76)
key(HP, 76, euler=HP_ON[0], loc=HP_ON[1])
# fase 5: cabeceo (la cabeza vuelve a SIT justo antes de la fase 6). El key de brazos en 152
# es imprescindible: sin el, el bezier entre f76 y f168 arrastraria las manos hacia las copas
# durante los 92 frames del cabeceo.
for f in range(60, 153, 2):
    env = min(1.0, (f - 60) / 14.0) * min(1.0, (152 - f) / 14.0)    # fade in/out
    nod(f, env)
key_arms_sit(152)
key(HP, 152, euler=HP_ON[0], loc=HP_ON[1])
# fase 6: manos a las copas (en la cabeza)
hands_travel(160, 1.0, 0.5)
hands_to_cups(168, 1.0)
# fase 7: bajar los audifonos
for f, u in ((174, 0.8), (180, 0.45), (186, 0.15), (192, 0.0)):
    hands_to_cups(f, smooth(u))
# fase 8: manos al teclado, todo en SIT
hands_travel(204, 0.0, 0.5)
key_arms_sit(216)
key(HP, 216, euler=(0, 0, 0), loc=(0, 0, 0))
for b in (HEAD, NECK, 'spine003'):
    for f in (1, 58, 154, 216):
        key(b, f, SIT[b])
for b in ('shoulderL', 'shoulderR'):
    for f in (1, 58, 154, 216):
        key(b, f, (0, 0, 0))
lids(1, 0)
lids(60, 0)
lids(66, 70)
lids(146, 70)
lids(152, 0)
lids(216, 0)
finish(act, VIBE_LEN, cyclic=False)


# --------------------------------------------------------------------------- 6) lookAround
# 96 frames: mira a su izquierda, a su derecha, arriba y vuelve al centro.
# side_deg > 0 gira la cara hacia -X (su izquierda). El cuello acompana un 35%.
act = new_action('lookAround', [HEAD, NECK])
for f, fwd, yaw in ((1, -8, 0), (16, -10, 28), (30, -10, 28), (46, -10, -28),
                    (58, -10, -28), (70, -24, 0), (82, -24, 0), (96, -8, 0)):
    key(HEAD, f, rot(HEAD, fwd, side_deg=yaw))
    key(NECK, f, neck(4 + (fwd + 8) * -0.15, yaw * 0.35))
finish(act, 96, cyclic=False)


# --------------------------------------------------------------------------- 7) introAnimation
# 72 frames: entra reclinado hacia atras con los brazos colgando y se acomoda al teclado
# (pose SIT) con un pequeno rebase en el frame 52. No toca spine006.
INTRO_BONES = SPINE + [NECK] + ARM_BONES
act = new_action('introAnimation', INTRO_BONES)
LEAN_A = {'spine003': -7.0, 'spine002': -5.0, 'spine001': -3.0, NECK: 15.0}
LEAN_B = {'spine003': 6.0, 'spine002': 4.0, 'spine001': 2.0, NECK: 4.0}


def intro_torso(u):
    return {b: rot(b, lerp(LEAN_A[b], LEAN_B[b], u)) for b in LEAN_A}


for f, u in ((1, 0.0), (18, 0.22), (36, 0.62), (52, 1.07), (62, 0.97), (72, 1.0)):
    torso = intro_torso(u)
    key_pose(f, torso)
    key_pose(f, solve_arms(
        torso=torso,
        upper=lambda s: lerp3(DIR_UPPER_DOWN(s), DIR_UPPER(s), u),
        fore=lambda s: lerp3(DIR_FORE_DOWN(s), DIR_FORE(s), u),
        hand=lambda s: lerp3(DIR_HAND_DOWN(s), DIR_HAND(s), u),
    ))
finish(act, 72, cyclic=False)


# ---------------------------------------------------------------------------
poses.apply(arm, SIT)
sc.frame_start, sc.frame_end = 1, 240
common.save(os.path.join(common.BLEND_DIR, 'character_anim.blend'))
print('ACTIONS', sorted(a.name for a in bpy.data.actions))
print('TRACKS', [t.name for t in arm.animation_data.nla_tracks])
