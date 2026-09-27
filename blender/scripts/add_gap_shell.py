# blender/scripts/add_gap_shell.py
# Las "grietas negras" de la cara son rendijas entre islas de la malla de Meshy por las que se
# ve a traves de la cabeza (el visor dibuja FrontSide, asi que el interior no existe y lo que
# asoma es el fondo oscuro del cuarto). close_gaps.py cierra las de hasta 3 mm; medido sobre
# character.blend DESPUES de ese paso, en la cara (479 vertices de borde mirando al frente)
# el 46 % sigue teniendo su borde vecino a 3-10 mm: son las rayas finas que se ven en el
# visor tambien con ?fx=off (o sea, sin contorno y sin cel-shading: es geometria).
#
# Subir SNAP de close_gaps no sirve (a 4 mm ya mella la visera) y un duplicado desplazado hacia
# dentro tampoco: tendria LAS MISMAS rendijas, y de frente se veria a traves de las dos.
#
# Arreglo: una cascara interior CERRADA. Se copia la cabeza, se le da grosor (Solidify) y se
# remalla por voxels: una sola superficie estanca que une las islas y tapa las rendijas.
# Luego cada vertice se AJUSTA a OFFSET por debajo de la piel (rayo por su normal contra
# Body: el remallado y el alisado desvian la superficie +-2.5 mm y sin este ajuste asoma en
# las zonas concavas —frente bajo la visera, cuenca de los ojos, comisuras— justo donde mas
# rendijas hay) y se conservan solo las caras que tienen piel encima entre MIN_DEPTH y
# MAX_DEPTH (asi la cascara nunca asoma por una zona delgada como la visera, y la cara
# interior de la losa, que mira hacia dentro, se descarta). La cascara recibe UV y pesos de
# la cara mas cercana de Body (Data Transfer), o sea que por la rendija se ve LA MISMA textura
# de piel/barba/gorra y no negro, y se deforma con la cabeza. Se une a Body para que sea
# parte del mismo objeto (mismo material, misma sensibilidad a tinta del contorno).
#
# Lo que queda de la rendija es un ESCALON de profundidad de ~OFFSET, que el contorno del
# visor entintaba igual: por eso postfx.js ignora saltos de profundidad menores de `depthMin`
# (8 mm, `?dmin=`), que es mas de lo que mide la cascara y menos que cualquier pliegue real.
#
# Va DESPUES de redilate_texture.py (la textura ya esta terminada) y ANTES de smooth_normals.py:
# unir mallas descarta las normales personalizadas, y ademas la cascara necesita recibir las
# normales alisadas de la superficie exterior (POLYINTERP_NEAREST se las da de la cara mas
# proxima del remallado). Idempotente: Body['gap_shell'].
# Renders de control con material plano: generated/renders/gapshell_before.png / gapshell_shell.png (la
# cascara sola) / gapshell_after.png. Medido con un rayo hacia dentro desde cada vertice de borde de la cara:
# la cobertura por ancho de rendija se imprime en cada corrida (GAPSHELL cobertura ...).
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/add_gap_shell.py [--dry-run]
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh, common
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import close_gaps

VOXEL = 0.004        # m: voxel del remallado (rendijas de hasta ~2 voxeles quedan unidas)
SMOOTH_IT = 1        # pasadas de Smooth sobre el remallado: solo para quitar el escalonado del voxel
OFFSET = 0.0025      # m: cuanto queda la cascara bajo la piel (el ajuste por rayo la deja exactamente ahi)
SOLID = 0.004        # m: grosor de la losa que se le da a cada isla antes de remallar (sin el, el remallado no une nada)
MIN_DEPTH = 0.0012   # m: una cara de la cascara se conserva solo si tiene piel encima al menos a esta distancia...
MAX_DEPTH = 0.009    # m: ...y como mucho a esta (mas hondo es la cara interior de la losa, o el otro lado de la cabeza)
RELAX_IT = 3         # pasadas de relajacion para los vertices sin piel encima (los de debajo de una rendija)
TARGET_TRIS = 7000   # tope de triangulos de la cascara (check_rig.py presupuesta 48 000 para todo el personaje)
Z_MARGIN = 0.01      # m: la region "cabeza" empieza este poco por debajo de la base del cuello (queda dentro del collar)


def coverage_report(body, shell, neck_z, dg):
    """Desde cada vertice de borde de la cara (mirando al frente), rayo hacia dentro por su normal
    alisada: ¿hay cascara a menos de 15 mm? Se reporta por ancho de rendija (distancia al borde
    ajeno mas cercano, como en close_gaps.py). Es la medida que dice si la cascara tapa lo que
    tiene que tapar; el render solo lo confirma a ojo."""
    import collections
    from mathutils import kdtree
    me = body.data
    acc = collections.defaultdict(lambda: Vector((0, 0, 0)))
    for l in me.loops: acc[l.vertex_index] += me.corner_normals[l.index].vector
    bmb = bmesh.new(); bmb.from_mesh(me); bmb.edges.ensure_lookup_table()
    bedges = [e for e in bmb.edges if e.is_boundary]
    kd = kdtree.KDTree(len(bedges))
    for i, e in enumerate(bedges): kd.insert((e.verts[0].co + e.verts[1].co) * 0.5, i)
    kd.balance(); maxlen = max(e.calc_length() for e in bedges)
    bvh_sh = BVHTree.FromObject(shell, dg, deform=False)
    bins = [(0, 3), (3, 5), (5, 10), (10, 20)]; stats = {b: [0, 0] for b in bins}
    for v in bmb.verts:
        if not any(e.is_boundary for e in v.link_edges) or v.co.z <= neck_z or v.normal.y <= 0.25: continue
        near = {e.index for e in v.link_edges} | {e2.index for e in v.link_edges for e2 in e.other_vert(v).link_edges}
        best = 99.0
        for co, i, d in kd.find_range(v.co, 0.02 + maxlen * 0.5):
            e = bedges[i]
            if e.index in near: continue
            p, _ = close_gaps.closest_on_segment(v.co, e.verts[0].co, e.verts[1].co)
            best = min(best, (p - v.co).length * 1000)
        b = next((b for b in bins if b[0] <= best < b[1]), None)
        if b is None: continue
        n = acc[v.index].normalized() if acc[v.index].length > 1e-6 else v.normal
        stats[b][0] += 1
        if bvh_sh.ray_cast(v.co + n * 0.001, -n, 0.015)[0] is not None: stats[b][1] += 1
    bmb.free()
    print('GAPSHELL cobertura de rendijas de la cara (vertices de borde con cascara detras): ' +
          ' '.join('%d-%dmm %d/%d' % (b[0], b[1], s[1], s[0]) for b, s in stats.items()))
    n_mid = sum(stats[b][0] for b in bins[1:3]); c_mid = sum(stats[b][1] for b in bins[1:3])
    if n_mid and c_mid / n_mid < 0.6:
        common.fail('la cascara tapa solo el %.0f %% de las rendijas de 3-10 mm; revisar VOXEL/OFFSET' % (100 * c_mid / n_mid))


def main():
    args = common.args(); DRY = '--dry-run' in args
    body = bpy.data.objects.get('Body'); arm = bpy.data.objects.get('Armature')
    if body is None or arm is None:
        common.fail('faltan Body/Armature')
    if body.get('gap_shell'):
        print('GAPSHELL ya aplicado; nada que hacer'); return
    common.ensure_dirs()
    close_gaps.render_flat('gapshell_before.png', arm)

    M = body.matrix_world
    neck_z = (arm.matrix_world @ arm.pose.bones['spine005'].head).z
    tris_before = common.tri_count(body)

    for o in bpy.data.objects: o.select_set(False)
    # 1) copia de la cabeza
    shell = body.copy(); shell.data = body.data.copy(); shell.name = 'GapShell'
    bpy.context.scene.collection.objects.link(shell)
    shell.modifiers.clear(); shell.vertex_groups.clear()
    bm = bmesh.new(); bm.from_mesh(shell.data)
    kill = [f for f in bm.faces if (M @ f.calc_center_median()).z < neck_z - Z_MARGIN]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bm.to_mesh(shell.data); bm.free()
    print('GAPSHELL cabeza: %d caras de Body' % len(shell.data.polygons))

    # 2) darle grosor a la copia y remallar por voxels: cada isla se vuelve una losa cerrada y
    #    el remallado une las losas vecinas en una sola superficie estanca (sin grosor previo,
    #    el remallado de una malla abierta sale como bandas finas sueltas y no rellena nada:
    #    probado). La losa va hacia dentro desde la piel: su cara exterior queda a ras.
    def apply(m):
        bpy.context.view_layer.objects.active = shell; shell.select_set(True)
        bpy.ops.object.modifier_apply(modifier=m); shell.select_set(False)
    so = shell.modifiers.new('SO', 'SOLIDIFY'); so.thickness = SOLID; so.offset = -1; apply('SO')
    r = shell.modifiers.new('R', 'REMESH'); r.mode = 'VOXEL'; r.voxel_size = VOXEL; r.use_smooth_shade = True
    r.use_remove_disconnected = False; apply('R')
    s = shell.modifiers.new('S', 'SMOOTH'); s.factor = 1.0; s.iterations = SMOOTH_IT; apply('S')
    n_remesh = common.tri_count(shell)
    if n_remesh < 5000:
        common.fail('el remallado de la cabeza salio demasiado pobre (%d tris); revisar VOXEL' % n_remesh)
    print('GAPSHELL remallado: %d tris' % n_remesh)

    # 3) ajustar cada vertice a OFFSET bajo la piel. Rayo hacia fuera por su normal: si pega en
    #    una cara frontal de Body a distancia d, el vertice se mueve d-OFFSET (hacia fuera si
    #    estaba hondo, hacia dentro si asomaba poco). Si no pega nada hacia fuera, puede que
    #    este ASOMANDO del todo: rayo hacia dentro; si pega en el reves de la piel a d, se
    #    hunde d+OFFSET. Los que no ven piel en ninguna direccion estan bajo una rendija: se
    #    relajan hacia la media de sus vecinos (ya ajustados) para que no hagan bulto.
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, dg, deform=False)   # Body en reposo, coordenadas locales (shell comparte transformada)
    bm = bmesh.new(); bm.from_mesh(shell.data); bm.verts.ensure_lookup_table(); bm.normal_update()
    loose = []
    for v in bm.verts:
        n = v.normal
        loc, nrm, idx, dist = bvh.ray_cast(v.co, n, MAX_DEPTH * 2)
        if loc is not None and nrm.dot(n) > 0.0:
            v.co = v.co + n * (dist - OFFSET); continue
        loc, nrm, idx, dist = bvh.ray_cast(v.co, -n, MAX_DEPTH)
        if loc is not None and nrm.dot(n) > 0.0:      # reves de la piel: el vertice estaba fuera
            v.co = v.co - n * (dist + OFFSET); continue
        loose.append(v)
    for _ in range(RELAX_IT):
        new = {}
        for v in loose:
            nb = [e.other_vert(v) for e in v.link_edges]
            if nb: new[v] = sum((o.co for o in nb), Vector()) / len(nb)
        for v, co in new.items(): v.co = co
    print('GAPSHELL ajuste: %d vertices, %d sin piel encima (bajo rendijas), relajados' % (len(bm.verts), len(loose)))
    bm.normal_update()

    # 4) conservar solo lo que tiene piel encima: desde el centro y los vertices de cada cara se
    #    lanza un rayo hacia fuera por su normal; la cara vive si ALGUN rayo pega en una cara
    #    frontal de Body entre MIN_DEPTH y MAX_DEPTH. Con el centro solo, las caras justo debajo
    #    de una rendija (las que hacen falta) se perderian. Esto descarta a la vez lo que asoma
    #    (nada encima), la cara interior de la losa (mira hacia dentro: no pega en nada) y la
    #    superficie de la cascara en zonas finas como la visera. Un "punto mas cercano" no sirve
    #    aqui: en la frente bajo la visera el punto mas cercano de Body es la visera, no la piel.
    def skin_above(p, n):
        loc, nrm, idx, dist = bvh.ray_cast(p, n, MAX_DEPTH)
        return loc is not None and dist >= MIN_DEPTH and nrm.dot(n) > 0.0
    drop = [f for f in bm.faces if not any(skin_above(p, f.normal) for p in [f.calc_center_median()] + [v.co for v in f.verts])]
    keep = len(bm.faces) - len(drop)
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(shell.data); bm.free(); shell.data.update()
    n_shell = common.tri_count(shell)
    print('GAPSHELL caras con piel encima: %d conservadas, %d descartadas -> %d tris' % (keep, len(drop), n_shell))
    if n_shell < 5000:
        common.fail('la cascara quedo casi vacia (%d tris); revisar OFFSET/MIN_DEPTH/MAX_DEPTH' % n_shell)
    if n_shell > TARGET_TRIS:
        d = shell.modifiers.new('D', 'DECIMATE'); d.decimate_type = 'COLLAPSE'; d.ratio = TARGET_TRIS / n_shell
        d.use_collapse_triangulate = True; apply('D')
        n_shell = common.tri_count(shell)
        print('GAPSHELL decimado -> %d tris' % n_shell)
    coverage_report(body, shell, neck_z, dg)
    body.hide_render = True
    close_gaps.render_flat('gapshell_shell.png', arm)   # la cascara sola: debe verse una cabeza casi entera, sin parches
    body.hide_render = False

    # 5) UV y pesos por proyeccion desde Body (cara mas cercana, interpolada)
    uvname = body.data.uv_layers.active.name
    for l in list(shell.data.uv_layers): shell.data.uv_layers.remove(l)
    shell.data.uv_layers.new(name=uvname)
    for g in body.vertex_groups: shell.vertex_groups.new(name=g.name)
    dt = shell.modifiers.new('DT', 'DATA_TRANSFER'); dt.object = body
    dt.use_loop_data = True; dt.data_types_loops = {'UV'}; dt.loop_mapping = 'POLYINTERP_NEAREST'
    dt.layers_uv_select_src = 'ALL'; dt.layers_uv_select_dst = 'NAME'
    dt.use_vert_data = True; dt.data_types_verts = {'VGROUP_WEIGHTS'}; dt.vert_mapping = 'POLYINTERP_NEAREST'
    dt.layers_vgroup_select_src = 'ALL'; dt.layers_vgroup_select_dst = 'NAME'
    bpy.context.view_layer.objects.active = shell; shell.select_set(True)
    bpy.ops.object.modifier_apply(modifier='DT')
    shell.select_set(False)
    # comprobacion: cada vertice de la cascara debe tener peso
    unweighted = sum(1 for v in shell.data.vertices if not v.groups)
    if unweighted:
        common.fail('%d vertices de la cascara sin pesos' % unweighted)
    shell.data.materials.clear()
    for m in body.data.materials: shell.data.materials.append(m)
    for p in shell.data.polygons: p.use_smooth = True

    # 6) unir a Body
    for o in bpy.data.objects: o.select_set(False)
    shell.select_set(True); body.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.select_set(False)
    tris_after = common.tri_count(body)
    print('GAPSHELL Body %d -> %d tris (+%d de cascara)' % (tris_before, tris_after, tris_after - tris_before))
    body['gap_shell'] = True
    if 'normals_smoothed' in body: del body['normals_smoothed']   # smooth_normals.py debe repetirse (join descarta las custom normals)
    close_gaps.render_flat('gapshell_after.png', arm)
    if DRY:
        print('GAPSHELL dry-run; no se guarda')
    else:
        common.save(os.path.join(common.BLEND_DIR, 'character.blend'))
        print('GAPSHELL OK')


if __name__ == '__main__':
    main()
