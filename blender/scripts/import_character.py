# blender/scripts/import_character.py
import sys, os, re, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
from mathutils import Vector

# Meshy usa nombres tipo Mixamo (sin prefijo mixamorig: en este GLB, sin dedos).
# Mapa a la convención moncy/Rigify sin puntos.
RENAME = {
    'Hips': 'spine', 'Spine': 'spine001', 'Spine01': 'spine002', 'Spine02': 'spine003',
    'neck': 'spine005', 'Head': 'spine006',
    'LeftShoulder': 'shoulderL', 'LeftArm': 'upper_armL', 'LeftForeArm': 'forearmL', 'LeftHand': 'handL',
    'RightShoulder': 'shoulderR', 'RightArm': 'upper_armR', 'RightForeArm': 'forearmR', 'RightHand': 'handR',
    'LeftUpLeg': 'thighL', 'LeftLeg': 'shinL', 'LeftFoot': 'footL', 'LeftToeBase': 'toeL',
    'RightUpLeg': 'thighR', 'RightLeg': 'shinR', 'RightFoot': 'footR', 'RightToeBase': 'toeR',
}
FINGERS = {'Thumb': 'thumb', 'Index': 'f_index', 'Middle': 'f_middle', 'Ring': 'f_ring', 'Pinky': 'f_pinky'}

def canonical(name):
    n = name.replace('mixamorig:', '').replace('mixamorig_', '')
    if n in RENAME: return RENAME[n]
    m = re.match(r'(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)(\d)', n)
    if m:
        side = 'L' if m.group(1) == 'Left' else 'R'
        return f'{FINGERS[m.group(2)]}0{m.group(3)}{side}'
    return None

def main():
    common.ensure_dirs(); common.reset_scene()
    bpy.ops.import_scene.gltf(filepath=os.path.join(common.GEN, 'meshy', 'character_rigged.glb'))
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    arm.name = 'Armature'

    # 0b. el importador glTF de Blender a veces fabrica objetos malla ajenos al archivo fuente
    # (p.ej. un "Icosphere" sin padre ni vertex groups, no presente en el glTF original).
    # Se eliminan: solo interesan las mallas realmente skinned al armature.
    junk = [o for o in bpy.data.objects if o.type == 'MESH'
            and o.parent != arm and not o.vertex_groups]
    for o in junk:
        print('REMOVING_JUNK_MESH', o.name)
        bpy.data.objects.remove(o, do_unlink=True)

    meshes = [o for o in bpy.data.objects if o.type == 'MESH']

    # 0. eliminar acciones importadas (clip de bind/reposo): el personaje no debe exportar animación.
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)

    # 1. renombrar huesos (los vertex groups se renombran solos al cambiar bone.name)
    unknown = []
    for b in arm.data.bones:
        c = canonical(b.name)
        if c: b.name = c
        else: unknown.append(b.name)
    print('UNKNOWN_BONES', unknown)

    # 2. escala a 1.75 m y origen en los pies, mirando a +Y
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True); bpy.context.view_layer.objects.active = arm
    for m in meshes: m.select_set(True)
    zs = [(m.matrix_world @ Vector(v.co)).z for m in meshes for v in m.data.vertices]
    h = max(zs) - min(zs)
    s = 1.75 / h
    # multiplicar la escala existente (Meshy importa el armature con escala 0.01), no sobrescribirla.
    arm.scale = (arm.scale.x * s, arm.scale.y * s, arm.scale.z * s)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    zs = [(m.matrix_world @ Vector(v.co)).z for m in meshes for v in m.data.vertices]
    arm.location.z -= min(zs)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    # 3. orientación: la cara debe mirar a +Y. Se detecta con el hueso 'headfront' (Meshy lo coloca
    #    delante de la cara, hijo de Head/spine006): si su cabeza queda en el lado -Y de spine006, el
    #    personaje mira a -Y y se rota 180° en Z. '--flip' invierte el resultado (override manual).
    hf = arm.data.bones.get('headfront'); s6 = arm.data.bones.get('spine006')
    if hf is None or s6 is None:
        raise RuntimeError('faltan los huesos headfront/spine006 para detectar la orientación')
    dy = (arm.matrix_world @ hf.head_local).y - (arm.matrix_world @ s6.head_local).y
    faces_neg_y = dy < 0
    flip = faces_neg_y != ('--flip' in common.args())
    print('FACING', 'dy_headfront=', round(dy, 4), '-> rotar 180°' if flip else '-> ok (+Y)')
    if flip:
        arm.rotation_mode = 'XYZ'  # el importador glTF deja QUATERNION y rotation_euler se ignoraría
        arm.rotation_euler = (0, 0, math.pi)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    for i, m in enumerate(meshes):
        m.name = 'Body' if i == 0 else f'Body_{i}'
        if m.data.materials:
            m.data.materials[0].name = 'Character'

    # 3b. decimar a <= 40000 tris (mantener el modificador Armature por encima en la pila).
    total_tris = sum(common.tri_count(m) for m in meshes)
    ratio = min(1.0, 38000 / total_tris) if total_tris > 0 else 1.0
    if ratio < 1.0:
        for m in meshes:
            if not m.name.startswith('Body'):
                continue
            bpy.ops.object.select_all(action='DESELECT')
            m.select_set(True); bpy.context.view_layer.objects.active = m
            dec = m.modifiers.new('Decimate', 'DECIMATE')
            dec.decimate_type = 'COLLAPSE'
            dec.ratio = ratio
            # el modificador Decimate debe ir antes que el Armature en la pila para aplicarlo.
            while m.modifiers.find(dec.name) > 0:
                bpy.ops.object.modifier_move_up(modifier=dec.name)
            bpy.ops.object.modifier_apply(modifier=dec.name)

    # 4. asegurar que las mallas cuelgan del armature con modificador
    for m in meshes:
        if not any(md.type == 'ARMATURE' for md in m.modifiers):
            md = m.modifiers.new('Armature', 'ARMATURE'); md.object = arm

    # 5. render de control
    # cámara en +Y (el personaje ya mira a +Y): el render debe mostrar la cara.
    common.add_camera((0, 3.2, 1.0), (0, 0, 0.9), lens=50)
    common.add_light('k', 'AREA', (-1.5, 2, 2.5), 300, size=1.5)
    common.render(os.path.join(common.RENDERS, 'character_imported.png'), res=(720, 1000))
    print('CHAR_TRIS', sum(common.tri_count(m) for m in meshes))
    common.save(os.path.join(common.BLEND_DIR, 'character.blend'))

if __name__ == '__main__':
    main()
