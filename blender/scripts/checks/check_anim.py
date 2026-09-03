# blender/scripts/checks/check_anim.py
# Uso: tools/run_blender.sh blender/character_anim.blend blender/scripts/checks/check_anim.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy, common

arm = bpy.data.objects['Armature']
NEED = {'introAnimation': 72, 'typing': 48, 'idle': 96, 'Blink': 240,
        'browup': 18, 'vibe': 120, 'lookAround': 96}
HEAD = 'spine006'
# Huesos que `typing` tiene permitido tocar (este rig no tiene huesos de dedos).
TYPING_OK = {'shoulderL', 'shoulderR', 'upper_armL', 'upper_armR',
             'forearmL', 'forearmR', 'handL', 'handR'}
# Unicos clips que pueden mover la cabeza.
HEAD_OK = {'vibe', 'lookAround'}
# idle es la base continua: solo columna/cuello, para que typing se superponga sin
# escribir sobre los mismos huesos.
IDLE_OK = {'spine001', 'spine002', 'spine003', 'spine005'}
# Clips en bucle: deben ser continuos (modificador CYCLES o primer valor == ultimo).
LOOPS = {'typing', 'idle', 'Blink'}


fcurves_of = common.fcurves_of


def bones_in(act):
    return {fc.data_path.split('"')[1] for fc in fcurves_of(act)
            if fc.data_path.startswith('pose.bones')}


def fc_label(fc):
    return f'{fc.data_path}[{fc.array_index}]'


def not_keyed_at_1(act):
    """F-curves cuyo primer keyframe no esta en el frame 1."""
    bad = []
    for fc in fcurves_of(act):
        kps = fc.keyframe_points
        if not len(kps) or abs(kps[0].co[0] - 1) > 0.001:
            bad.append(fc_label(fc))
    return bad


def not_seamless(act):
    """F-curves de un bucle sin modificador CYCLES y con primer valor != ultimo."""
    bad = []
    for fc in fcurves_of(act):
        if any(m.type == 'CYCLES' for m in fc.modifiers):
            continue
        kps = fc.keyframe_points
        if not len(kps) or abs(kps[0].co[1] - kps[-1].co[1]) > 1e-4:
            bad.append(fc_label(fc))
    return bad


if arm.animation_data is None:
    common.fail('el Armature no tiene animation_data')
tracks = {t.name: t for t in arm.animation_data.nla_tracks}

if len(bpy.data.actions) != len(NEED):
    common.fail(f'hay {len(bpy.data.actions)} acciones, esperadas {len(NEED)}: '
                f'{sorted(a.name for a in bpy.data.actions)}')
if len(tracks) != len(NEED):
    common.fail(f'hay {len(tracks)} pistas NLA, esperadas {len(NEED)}: {sorted(tracks)}')

for n, ln in NEED.items():
    if n not in bpy.data.actions:
        common.fail(f'falta accion {n}')
    if n not in tracks:
        common.fail(f'falta pista NLA {n}')
    if len(tracks[n].strips) != 1:
        common.fail(f'la pista {n} tiene {len(tracks[n].strips)} strips')
    st = tracks[n].strips[0]
    if st.action.name != n:
        common.fail(f'pista {n} apunta a {st.action.name}')
    if abs(st.frame_start - 1) > 0.001:
        common.fail(f'{n} empieza en {st.frame_start}, esperado 1')
    if abs((st.frame_end - st.frame_start) - (ln - 1)) > 0.001:
        common.fail(f'{n} dura {st.frame_end - st.frame_start}, esperado {ln - 1}')
    act = bpy.data.actions[n]
    if not fcurves_of(act):
        common.fail(f'la accion {n} no tiene f-curves')
    bad = not_keyed_at_1(act)
    if bad:
        common.fail(f'{n}: f-curves sin key en el frame 1: {bad}')
    if n in LOOPS:
        bad = not_seamless(act)
        if bad:
            common.fail(f'{n} es un bucle pero no es continuo (sin CYCLES y extremos '
                        f'distintos): {bad}')
    print(f'CLIP {n:15s} frames {int(st.frame_start)}..{int(st.frame_end)} '
          f'({ln})  huesos {sorted(bones_in(act))}')

for n in NEED:
    b = bones_in(bpy.data.actions[n])
    if HEAD in b and n not in HEAD_OK:
        common.fail(f'{n} anima la cabeza ({HEAD}); solo {sorted(HEAD_OK)} pueden')
for n in HEAD_OK:
    if HEAD not in bones_in(bpy.data.actions[n]):
        common.fail(f'{n} no anima la cabeza ({HEAD})')

extra = bones_in(bpy.data.actions['typing']) - TYPING_OK
if extra:
    common.fail(f'typing toca huesos que no son de brazo/mano: {sorted(extra)}')
if not {'handL', 'handR'} <= bones_in(bpy.data.actions['typing']):
    common.fail('typing no mueve las manos')
extra = bones_in(bpy.data.actions['idle']) - IDLE_OK
if extra:
    common.fail(f'idle toca huesos fuera de columna/cuello: {sorted(extra)}')
if not {'eyelidL', 'eyelidR'} <= bones_in(bpy.data.actions['Blink']):
    common.fail('Blink sin parpados')
if not {'eyelidL', 'eyelidR'} <= bones_in(bpy.data.actions['vibe']):
    common.fail('vibe deberia cerrar los ojos (sin parpados)')
if not {'eyebrow_L', 'eyebrow_R'} <= bones_in(bpy.data.actions['browup']):
    common.fail('browup sin cejas')

print('CHECK_ANIM OK')
