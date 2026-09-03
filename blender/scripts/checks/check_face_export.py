# blender/scripts/checks/check_face_export.py
# Comprueba que las partes de la cara añadidas en Task 8 (párpados, cejas y candongas,
# parentadas a HUESO y no skinneadas) sobreviven a la exportación glTF: cada malla debe
# quedar como un NODO HIJO del nodo del hueso correspondiente, para que en tiempo de
# ejecución girar el hueso 'eyelidL' +70° en X mueva de verdad 'eyelid_L' (convención de
# Task 9). Blender a veces "aplana" los objetos parentados a hueso colgándolos de la raíz
# del armature; si eso pasara, este check falla y habría que pasar a skinning.
#
# Exporta generated/face_export_test.glb con el personaje POSADO (ojos cerrados, cejas
# arriba) y lee el JSON del GLB directamente para reconstruir la jerarquía de nodos.
#
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/checks/check_face_export.py
import sys, os, math, json, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tools'))
import bpy, common, poses
import glb_inspect
from mathutils import Matrix, Quaternion, Vector

# malla -> hueso del que debe colgar
EXPECTED = {
    'eyelid_L': 'eyelidL',
    'eyelid_R': 'eyelidR',
    'eyebrow_L_mesh': 'eyebrow_L',
    'eyebrow_R_mesh': 'eyebrow_R',
    'earring_L1': 'spine006',
    'earring_L2': 'spine006',
    'earring_R1': 'spine006',
    'earring_R2': 'spine006',
    # Task 4: la pieza de audifonos cuelga de su propio hueso
    'headphones_band': 'headphones',
    'headphones_cup_L': 'headphones',
    'headphones_cup_R': 'headphones',
}


def gltf_json(path):
    with open(path, 'rb') as f:
        data = f.read()
    magic, _, length = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67, 'no es un GLB'
    off = 12
    while off < length:
        clen, ctype = struct.unpack_from('<II', data, off)
        if ctype == 0x4E4F534A:
            return json.loads(data[off + 8: off + 8 + clen].decode('utf-8'))
        off += 8 + clen
    raise RuntimeError('sin chunk JSON')


def node_matrix(n):
    if 'matrix' in n:
        m = n['matrix']   # glTF guarda column-major
        return Matrix([[m[0], m[4], m[8], m[12]], [m[1], m[5], m[9], m[13]],
                       [m[2], m[6], m[10], m[14]], [m[3], m[7], m[11], m[15]]])
    t = Vector(n.get('translation', (0.0, 0.0, 0.0)))
    q = n.get('rotation', (0.0, 0.0, 0.0, 1.0))
    s = Vector(n.get('scale', (1.0, 1.0, 1.0)))
    return (Matrix.Translation(t)
            @ Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4()
            @ Matrix.Diagonal(s.to_4d()))


# Blender es Z-up; el exportador usa export_yup=True: (x, y, z) -> (x, z, -y).
YUP = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))


def to_yup(m):
    """Matriz de mundo de Blender -> matriz de mundo en el espacio Y-up del glTF."""
    return YUP @ m @ YUP.inverted()


def maxdiff(a, b):
    return max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4))


def main():
    common.ensure_dirs()
    arm = bpy.data.objects['Armature']
    rest_w = {n: bpy.data.objects[n].matrix_world.copy() for n in EXPECTED}

    # pose de prueba: ojos cerrados (+70° X local) y cejas arriba (+0.012 Z local)
    for s in 'LR':
        pb = arm.pose.bones[f'eyelid{s}']
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (math.radians(70.0), 0.0, 0.0)
        arm.pose.bones[f'eyebrow_{s}'].location = (0.0, 0.0, 0.012)
    hp_on = poses.headphones_on()
    if hp_on is None:
        common.fail('falta blender/headphones.json (lo escribe add_headphones.py)')
    hp = arm.pose.bones['headphones']
    hp.rotation_mode = 'XYZ'
    hp.rotation_euler, hp.location = hp_on
    bpy.context.view_layer.update()
    posed_w = {n: bpy.data.objects[n].matrix_world.copy() for n in EXPECTED}

    path = os.path.join(common.GEN, 'face_export_test.glb')
    common.export_glb(path, draco=False, animations=False)

    for s in 'LR':
        arm.pose.bones[f'eyelid{s}'].rotation_euler = (0.0, 0.0, 0.0)
        arm.pose.bones[f'eyebrow_{s}'].location = (0.0, 0.0, 0.0)
    hp.rotation_euler, hp.location = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    info = glb_inspect.inspect(path)
    print('GLB_INFO tris=', info['triangles'], 'nodos=', len(info['nodes']),
          'skins=', info['skins'], 'meshes=', len(info['meshes']), 'bytes=', info['size_bytes'])

    g = gltf_json(path)
    nodes = g.get('nodes', [])
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get('children', []):
            parent[c] = i
    by_name = {}
    for i, n in enumerate(nodes):
        by_name.setdefault(n.get('name', ''), i)

    def world(i):
        m = Matrix.Identity(4)
        stack = []
        j = i
        while j is not None:
            stack.append(j)
            j = parent.get(j)
        for j in reversed(stack):
            m = m @ node_matrix(nodes[j])
        return m

    def chain(i):
        out = []
        while i is not None:
            out.append(nodes[i].get('name', f'<{i}>'))
            i = parent.get(i)
        return ' <- '.join(out)

    ok = True
    for mesh_name, bone_name in EXPECTED.items():
        i = by_name.get(mesh_name)
        if i is None:
            print('EXPORT_FAIL falta el nodo', mesh_name)
            ok = False
            continue
        p = parent.get(i)
        pname = nodes[p].get('name', '') if p is not None else None
        has_skin = 'skin' in nodes[i]
        t = nodes[i].get('translation', [0.0, 0.0, 0.0])
        wm = world(i)
        wt = wm.translation
        d_rest = maxdiff(wm, to_yup(rest_w[mesh_name]))
        d_pose = maxdiff(wm, to_yup(posed_w[mesh_name]))
        print(f'NODE {mesh_name:16s} parent={pname!s:12s} skin={has_skin} '
              f'mesh={"mesh" in nodes[i]} T={[round(v, 4) for v in t]}')
        print('     chain:', chain(i))
        print(f'     world(glTF)={[round(v, 4) for v in wt]} '
              f'err_matriz_vs_reposo={d_rest * 1000:.3f} mm '
              f'err_matriz_vs_posado={d_pose * 1000:.3f} mm')
        if min(d_rest, d_pose) > 0.001:
            print(f'EXPORT_FAIL {mesh_name}: la matriz de mundo compuesta en el glTF no '
                  f'coincide ni con la pose de reposo ni con la posada')
            ok = False
        if pname != bone_name and not has_skin:
            print(f'EXPORT_FAIL {mesh_name}: cuelga de {pname!r}, se esperaba {bone_name!r}')
            ok = False

    for bn in ('eyelidL', 'eyelidR', 'eyebrow_L', 'eyebrow_R', 'spine006', 'headphones'):
        if bn not in by_name:
            print('EXPORT_FAIL falta el nodo de hueso', bn)
            ok = False

    if not ok:
        common.fail('las partes de la cara no exportan colgando de sus huesos')
    print('CHECK_FACE_EXPORT OK', len(EXPECTED), 'mallas cuelgan de su hueso en el glTF')


if __name__ == '__main__':
    main()
