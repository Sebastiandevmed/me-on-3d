# blender/scripts/animate.py
"""Las 7 animaciones de 'Me on 3D' como acciones + pistas NLA.

Uso: tools/run_blender.sh blender/character.blend blender/scripts/animate.py
Guarda SOLO blender/character_anim.blend (nunca character.blend ni scene.blend).

Reglas de la tarea:
  * El rig de Meshy NO tiene huesos de dedos: `typing` mueve manos y antebrazos.
  * Solo `vibe` y `lookAround` tocan spine006 (la cabeza).
  * `typing` toca unicamente huesos de brazo/mano (jamas columna ni cabeza).
  * Cada accion keyframea en su frame 1 la pose SIT completa de los huesos que anima,
    asi el clip es autocontenido al exportarse a glTF.
  * Duraciones a 24 fps: introAnimation 72, typing 48, idle 96, Blink 240,
    browup 18, vibe 120, lookAround 96. Todas empiezan en el frame 1 y la pista
    NLA se llama igual que la accion.

Ejes de los brazos: upper_arm/forearm/hand tienen ejes locales a ~45 grados del plano
sagital, asi que `poses.rot()` NO sirve. Los valores de SIT salieron de `poses.aim()`
apuntando cada hueso a una direccion del mundo; aqui se hace lo mismo perturbando esas
direcciones base (verificado contra SIT: reproducen exactamente TYPING_HOME).
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common, poses
from poses import rot, SIT

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

def fcurves_of(act):
    """F-curves de una accion, con o sin 'slots' (Blender >= 4.4)."""
    fcs = list(getattr(act, 'fcurves', []) or [])
    if fcs:
        return fcs
    for layer in getattr(act, 'layers', []):
        for strip in layer.strips:
            for cb in getattr(strip, 'channelbags', []):
                fcs += list(cb.fcurves)
    return fcs


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


# --------------------------------------------------------------------------- 1) typing
# 48 frames en bucle. Sin dedos: alterna el levante de muneca de cada mano (~8 grados) y
# acompana con un levante minimo de antebrazo. Ni columna ni cabeza.
# La oscilacion es ASIMETRICA: `up` va de 0 (pose SIT, palma sobre el laptop) a 1 (mano
# arriba). Con +-amp simetrico la carrera hacia abajo metia las yemas ~3.4 cm en el
# escritorio (hallazgo de la tarea 11: 319 vertices dentro del tablero en f12).
act = new_action('typing', ARM_BONES)
for f in range(1, 50, 4):                       # 1..49; el 49 repite el 1 (bucle limpio)
    t = (f - 1) / 48.0 * 2 * math.pi
    ph = {'L': t, 'R': t + math.pi}
    up = lambda s: 0.5 * (1.0 + math.sin(ph[s]))        # 0..1, L y R a contratiempo
    key_pose(f, solve_arms(
        upper=lambda s: (-SX[s] * 0.06, 0.0 + 0.024 * up(s), -0.998),
        fore=lambda s: (SX[s] * 0.13, 0.99, 0.02 + 0.10 * up(s)),
        hand=lambda s: (SX[s] * (0.05 + 0.030 * math.sin(ph[s] * 2)), 0.995, 0.30 * up(s)),
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
# Cabeceo de rap con los OJOS CERRADOS: 8 tiempos de 15 frames (96 BPM) en 120 frames.
# La cabeza cae en el golpe y sube entre golpes; hombros y spine003 acompanan.
# Amplitud subida (feedback del controlador: el cabeceo original -8.5..0.5 grados era
# casi imperceptible en una tira de 6 frames). Ahora spine006 oscila entre -16 (levantada,
# entre golpes) y +14 (golpe abajo): swing de 30 grados, 22 por debajo de SIT (-8); el
# cuello suma 6 grados mas en el golpe. Envolvente de 14 frames al inicio y al final: con
# env=0 la cabeza cae EXACTAMENTE en SIT (-8), asi encadena desde idle/typing sin salto.
# Los ojos abren en f1 y f120 (cerrados f7..f112) por la misma razon.
VIBE_BONES = [HEAD, NECK, 'spine003', 'shoulderL', 'shoulderR'] + LIDS
act = new_action('vibe', VIBE_BONES)
BEAT = 15.0
for f in range(1, 121, 2):
    t = (f - 1) / BEAT * 2 * math.pi
    env = min(1.0, (f - 1) / 14.0) * min(1.0, (121 - f) / 14.0)     # fade in/out
    pulse = max(0.0, math.sin(t)) ** 1.5                            # golpe hacia abajo
    nod = -8 + env * (30 * pulse - 8)                               # env=0 -> SIT (-8)
    key(HEAD, f, rot(HEAD, nod, side_deg=env * 5.0 * math.sin(t / 2)))
    key(NECK, f, neck(4 + env * 6.0 * pulse, env * 2.5 * math.sin(t / 2)))
    key('spine003', f, rot('spine003', 6 + env * 4.5 * math.sin(t)))
    key('shoulderL', f, rot('shoulderL', env * 6.0 * math.sin(t)))
    key('shoulderR', f, rot('shoulderR', env * 6.0 * math.sin(t + math.pi)))
lids(1, 0)
lids(7, 70)
lids(112, 70)
lids(120, 0)
finish(act, 120, cyclic=False)


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
