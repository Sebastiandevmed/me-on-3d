# blender/scripts/anim_strip.py
# Renders de aprobacion de las 7 animaciones: desmutea una pista NLA a la vez y saca
# unos frames clave a generated/renders/anim_<clip>_<frame>.png.
# Uso: tools/run_blender.sh blender/character_anim.blend blender/scripts/anim_strip.py [-- vibe vibeface ...]
# Sin argumentos renderiza todos los shots; con nombres despues de '--' solo esos.
# Las tiras (contact sheets) se arman despues con ffmpeg, p.ej. para un shot de N frames:
#   cd generated/renders && ffmpeg -y -pattern_type glob -i 'anim_vibe_*.png' -filter_complex tile=6x1 strip_vibe.png
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import bpy, common, poses

arm = bpy.data.objects['Armature']
common.ensure_dirs()

def reset_pose():
    """Devuelve el rig a SIT con parpados abiertos y cejas abajo.

    El NLA no resetea los huesos que la accion activa NO anima: conservan el ultimo
    valor evaluado. Sin esto, despues de renderizar `vibe` (ojos cerrados) los clips
    siguientes salian con los ojos cerrados.
    """
    poses.apply(arm, poses.SIT)
    for b in ('eyelidL', 'eyelidR'):
        pb = arm.pose.bones[b]
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0.0, 0.0, 0.0)
    for b in ('eyebrow_L', 'eyebrow_R'):
        arm.pose.bones[b].location = (0.0, 0.0, 0.0)
    hp = arm.pose.bones.get('headphones')       # solo `vibe` lo anima: sin esto los demas
    if hp:                                      # clips saldrian con los audifonos puestos
        hp.rotation_mode = 'XYZ'
        hp.rotation_euler = (0.0, 0.0, 0.0)
        hp.location = (0.0, 0.0, 0.0)


P = lambda n: [round(v, 3) for v in (arm.matrix_world @ arm.pose.bones[n].head)]
print('BONE head', P('spine006'), 'headfront', P('headfront'), 'hand', P('handL'))

cam = bpy.data.objects.get('Camera') or common.add_camera((0, 2, 1.4), (0, 0, 1.3))
bpy.context.scene.camera = cam
for o in bpy.data.objects:
    if o.type == 'LIGHT':
        o.data.energy = 700
common.add_light('fill', 'AREA', (1.8, 2.2, 1.6), 500, size=2.0)
common.add_light('rim', 'AREA', (-1.4, -1.8, 2.2), 350, size=2.0)
common.add_light('face', 'AREA', (0.6, 1.5, 1.35), 220, size=1.2)

# tres cuartos frontal: se ven cara, hombros, brazos y manos
BODY = ((0.85, 1.75, 1.34), (0.0, 0.05, 1.16), 50)
# primer plano de la cara para parpados, cejas y giros de cabeza
# La visera de la gorra tapa las cejas si la camara mira desde arriba: se sube el
# objetivo y se baja la camara para ver por debajo de la visera.
FACE = ((0.22, 0.90, 1.50), (0.0, 0.10, 1.585), 58)

SHOTS = [
    # vibe v2 (216 f): copas en el cuello (20), audifonos a media altura (32), puestos (44),
    # manos de vuelta al teclado (76), cabeceo (100), manos a las copas (168), bajada (186).
    ('vibe', BODY, (1, 20, 32, 44, 76, 100, 168, 186, 216)),
    ('vibeface', FACE, (20, 32, 44, 100, 180, 192), 'vibe'),
    ('typing', BODY, (1, 13, 25, 37)),
    ('introAnimation', BODY, (1, 18, 36, 52, 72)),
    ('idle', BODY, (1, 13, 25, 37, 49)),
    ('Blink', FACE, (56, 59, 61, 64, 66)),
    ('browup', FACE, (1, 5, 8, 11, 18)),
    ('lookAround', FACE, (1, 23, 52, 76, 96)),
]

ONLY = set(common.args())
for shot in SHOTS:
    name, (loc, tgt, lens), frames = shot[0], shot[1], shot[2]
    if ONLY and name not in ONLY:
        continue
    clip = shot[3] if len(shot) > 3 else name
    for t in arm.animation_data.nla_tracks:
        t.mute = (t.name != clip)
    cam.location = loc
    common.look_at(cam, tgt)
    cam.data.lens = lens
    for f in frames:
        reset_pose()
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        common.render(os.path.join(common.RENDERS, f'anim_{name}_{f:03d}.png'),
                      res=(480, 640), samples=16)

for t in arm.animation_data.nla_tracks:
    t.mute = True
print('STRIP_DONE')
