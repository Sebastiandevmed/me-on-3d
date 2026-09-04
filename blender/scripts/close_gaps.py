# blender/scripts/close_gaps.py
# La malla de Meshy es un mosaico de ~4500 islas cuyos bordes NO coinciden: entre isla e isla quedan
# rendijas de 0.5 a 5 mm (medido sobre 8563 vertices de borde: 27 % tiene el borde vecino a 0.5-1 mm,
# 18 % a 1-2 mm, 11 % a 2-3 mm). Por ellas se ve el interior oscuro de la malla, y en el visor y en
# los renders salen como rayas finas negras en la cara, la gorra y el hoodie ("grietas"). Se
# comprobo que son geometria y no textura: aparecen igual con material plano sin textura, con
# backface culling y sin normales personalizadas (generated/renders/headprobe/crack_trio.png).
# Soldar por distancia no las cierra (los vertices de un borde no caen sobre los del otro).
#
# Arreglo: cada vertice de borde se acerca al punto mas cercano del borde de OTRA isla (proyeccion
# sobre la arista de borde mas proxima, a menos de SNAP), avanzando la mitad del camino en cada
# iteracion; como las dos orillas lo hacen a la vez, convergen a la curva media y la rendija se
# cierra. Solo se emparejan superficies que miran hacia el mismo lado (normal · normal > NDOT):
# la cara superior e inferior de la visera, o las dos paredes de una copa, estan a 2-3 mm y no
# deben pegarse. Los pesos, las UV y los huesos no se tocan (un vertice se mueve como maximo SNAP).
#
# Va DESPUES de fix_head_weights.py y ANTES de repack_uvs.py (el reempaquetado suelda y
# re-desenvuelve la malla; si ya se ejecuto, repetirlo con --force). Idempotente:
# Body['gaps_closed']. Renders de control con material plano (las rendijas se ven mejor sin
# textura): generated/renders/gaps_before.png y gaps_after.png.
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/close_gaps.py [--dry-run]
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh, common
import numpy as np
from mathutils import Vector, kdtree

SNAP = 0.003      # m: distancia maxima vertice-borde ajeno para considerarlo una rendija (p90 medido 2.6 mm; a 4 mm la visera sale mellada)
NDOT = 0.3        # coseno minimo entre normales para emparejar dos bordes (descarta caras opuestas)
ITERS = 6         # pasadas (cada una recorre la mitad del camino: 6 pasadas = 98 % cerrado)
MERGE = 0.0003    # m: soldadura final de los vertices que quedaron encima unos de otros


def closest_on_segment(p, a, b):
    ab = b - a
    L2 = ab.length_squared
    if L2 < 1e-16:
        return a.copy(), 0.0
    t = max(0.0, min(1.0, (p - a).dot(ab) / L2))
    return a + ab * t, t


def render_flat(name, arm):
    """Render de la cara con material plano (sin textura) para ver las rendijas."""
    common.ensure_dirs()
    m = bpy.data.materials.get('Character')
    bsdf = m.node_tree.nodes['Principled BSDF']
    link = bsdf.inputs['Base Color'].links[0] if bsdf.inputs['Base Color'].is_linked else None
    from_socket = link.from_socket if link else None
    if link: m.node_tree.links.remove(link)
    prev_col = tuple(bsdf.inputs['Base Color'].default_value)
    bsdf.inputs['Base Color'].default_value = (0.8, 0.5, 0.4, 1.0)
    sc = bpy.context.scene
    created = sc.world is None
    if created: sc.world = bpy.data.worlds.new('CG_World')
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get('Background')
    prev_bg = (tuple(bg.inputs[0].default_value), bg.inputs[1].default_value)
    bg.inputs[0].default_value = (0.42, 0.44, 0.50, 1.0); bg.inputs[1].default_value = 0.55
    hz = (arm.matrix_world @ arm.pose.bones['spine006'].head).z
    common.add_camera((0.0, 0.85, hz + 0.10), (0.0, 0.0, hz + 0.09), lens=85, name='CG_Cam')
    common.add_light('CG_key', 'AREA', (-0.6, 0.9, hz + 0.5), 160, size=0.9)
    common.add_light('CG_fill', 'AREA', (0.7, 0.8, hz + 0.1), 90, size=0.9)
    common.render(os.path.join(common.RENDERS, name), res=(900, 900), samples=48)
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA', 'LIGHT') and o.name.startswith('CG_'): bpy.data.objects.remove(o)
    bg.inputs[0].default_value = prev_bg[0]; bg.inputs[1].default_value = prev_bg[1]
    bsdf.inputs['Base Color'].default_value = prev_col
    if from_socket is not None: m.node_tree.links.new(from_socket, bsdf.inputs['Base Color'])


def main():
    args = common.args(); DRY = '--dry-run' in args
    body = bpy.data.objects.get('Body'); arm = bpy.data.objects.get('Armature')
    if body is None or arm is None:
        common.fail('faltan Body/Armature')
    if body.get('gaps_closed'):
        print('GAPS ya aplicado; nada que hacer'); return
    render_flat('gaps_before.png', arm)
    me = body.data
    bm = bmesh.new(); bm.from_mesh(me)
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
    bedges = [e for e in bm.edges if e.is_boundary]
    bverts = [v for v in bm.verts if any(e.is_boundary for e in v.link_edges)]
    print('GAPS vertices', len(bm.verts), 'de borde', len(bverts), 'aristas de borde', len(bedges))
    if not bedges:
        body['gaps_closed'] = True; print('GAPS sin bordes; nada que cerrar'); return
    enormal = {}
    for e in bedges:
        f = e.link_faces[0]
        enormal[e.index] = f.normal.copy()
    maxlen = max(e.calc_length() for e in bedges)
    moved_total = 0; dist_hist = []
    for it in range(ITERS):
        kd = kdtree.KDTree(len(bedges))
        for i, e in enumerate(bedges):
            kd.insert((e.verts[0].co + e.verts[1].co) * 0.5, i)
        kd.balance()
        targets = {}
        for v in bverts:
            near = {e.index for e in v.link_edges} | {e2.index for e in v.link_edges for e2 in e.other_vert(v).link_edges}
            best = None
            for co, i, d in kd.find_range(v.co, SNAP + maxlen * 0.5):
                e = bedges[i]
                if e.index in near: continue
                if enormal[e.index].dot(v.normal) < NDOT: continue
                p, _ = closest_on_segment(v.co, e.verts[0].co, e.verts[1].co)
                dd = (p - v.co).length
                if dd <= SNAP and (best is None or dd < best[0]):
                    best = (dd, p)
            if best is not None:
                targets[v.index] = best
        for v in bverts:
            if v.index in targets:
                dd, p = targets[v.index]
                if it == 0: dist_hist.append(dd)
                v.co = v.co + (p - v.co) * 0.5
        moved_total = len(targets)
        print('GAPS pasada %d: %d vertices de borde acercados' % (it + 1, len(targets)))
    h = np.array(dist_hist) * 1000
    if len(h):
        print('GAPS ancho de rendija inicial (mm): p50 %.2f p90 %.2f max %.2f' % tuple(np.percentile(h, [50, 90, 100])))
    bmesh.ops.remove_doubles(bm, verts=bverts, dist=MERGE)
    n_after = len(bm.verts)
    bm.to_mesh(me); bm.free(); me.update()
    print('GAPS vertices tras soldar a %.1f mm: %d' % (MERGE * 1000, n_after))
    if moved_total < 100:
        common.fail('se acercaron muy pocos vertices (%d): revisar SNAP/NDOT' % moved_total)
    body['gaps_closed'] = True
    if 'normals_smoothed' in body: del body['normals_smoothed']
    if 'uv_repacked' in body:
        print('GAPS OJO: Body ya estaba reempaquetado; repetir repack_uvs.py --force y lo que sigue')
    render_flat('gaps_after.png', arm)
    if DRY:
        print('GAPS dry-run; no se guarda')
    else:
        common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
        print('GAPS OK')


if __name__ == '__main__':
    main()
