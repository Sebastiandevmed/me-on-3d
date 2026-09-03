# blender/scripts/export_glb.py
# Task 12: exporta blender/avatar.blend a export/avatar.glb (Draco) y
# export/avatar_uncompressed.glb (misma configuracion sin Draco, solo para depurar) y
# verifica el resultado (presupuesto, triangulos, animaciones, nodos, pantallas, pose base).
#
# Estado de exportacion (todo en memoria; este script NUNCA guarda avatar.blend):
#  - Pantallas con Emission Strength 1.0: con 0.0 el exportador descarta la emissiveTexture.
#    El visor (Task 13) arranca con emissiveIntensity 0 y sube a 2.5.
#  - Sin camaras ni luces. Se conservan los empties seat_anchor / moto_anchor / moto_mini.
#  - Texturas: personaje 2k, resto 1k (se reescalan en memoria si son mayores).
#  - Las 7 pistas NLA se exportan como 7 clips (NLA_TRACKS) con su nombre. Se dejan MUTEADAS
#    (estado neutro del archivo): el exportador mutea todas las pistas y activa una a una al
#    muestrear, asi que el mute inicial no afecta a los clips, pero SI a la pose base (abajo).
#  - export_rest_position_armature=False: la pose base de los nodos-hueso es la pose ACTUAL
#    del archivo (SIT), no el reposo A-pose de Meshy. Asi los huesos sin canales en un clip
#    (p.ej. brazos durante 'idle') se quedan sentados en three.js en vez de saltar a la A-pose.
#    Si se desmutearan las pistas, la pose evaluada en el frame 1 seria el frame 1 de
#    'introAnimation' (pista superior, extrapolacion HOLD), cuyo brazo esta ~48 grados fuera
#    de SIT, y eso quedaria como pose base. Por eso NO se desmutea.
#  - export_reset_pose_bones=False: por defecto el exportador pone matrix_basis=identidad en
#    TODOS los huesos antes de hornear cada pista, asi que los huesos que un clip no anima se
#    muestrean en el reposo (A-pose) y salen como canal constante (brazos en A-pose durante
#    'idle'), y ademas la pose base queda destruida. Con False conservan los valores de canal
#    del archivo (SIT). Se verifica leyendo los clips del GLB.
#  - export_optimize_animation_keep_anim_armature=False: sin esto cada clip lleva canales
#    constantes para los 28 huesos; en three.js, al superponer clips (Blink sobre typing) esos
#    canales constantes se mezclan por peso y diluyen el movimiento. Con False cada clip solo
#    contiene los huesos que anima; los demas se quedan en la pose base (modelo de Task 13).
#  - Verificado empiricamente (Blender 5.2): la pose base de los nodos-hueso se toma del estado
#    que queda DESPUES de hornear las animaciones y restaurar mutes/frame, no del estado previo.
#    Con reset=False ese estado es el frame final de la ultima pista (introAnimation, que
#    termina en SIT) para los huesos que anima y los valores del archivo para el resto.
#    Diferencia respecto al SIT del archivo: < 6 grados (manos ~5 grados, Task 10 las cerro en un
#    SIT ligeramente distinto). Se verifica.
#  - Todas las texturas se exportan en JPEG (el atlas del personaje a CHAR_QUALITY = 92). Si
#    avatar.glb supera los 10 MiB se baja por una escalera de calidad: JPEG 92 -> JPEG 85 ->
#    JPEG 70 -> personaje a 1536. Ninguna textura depende de alfa (se verifica), asi que JPEG
#    global es seguro; el exportador conserva PNG solo para imagenes con canal alfa.
#
# Uso: tools/run_blender.sh blender/avatar.blend blender/scripts/export_glb.py 2>&1 | grep -E 'EXPORT|GLB|CHECK|Error|Traceback'
import sys, os, json, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
import bpy, common, glb_inspect
from mathutils import Quaternion

BUDGET = 10 * 1024 * 1024
MAX_TRIS = 80000
SCREENS = ('Screen_Left', 'Screen_Center', 'Screen_Right', 'Screen_Laptop')
SCREEN_EMISSION = 1.0
TRACKS = ['introAnimation', 'typing', 'idle', 'Blink', 'browup', 'vibe', 'lookAround']
NODES = ['spine006', 'headphones', 'screen_left', 'screen_center', 'screen_right',
         'screen_laptop', 'rgb_bar_L', 'rgb_bar_R', 'earring_L1', 'earring_R2']
KEEP_EMPTIES = ('seat_anchor', 'moto_anchor', 'moto_mini')
POSE_BONES = ('upper_armL', 'handL')     # huesos que 'idle' no anima: deben exportar posados
POSE_TOL = 0.9948                         # |dot| de cuaterniones: ~5.8 grados
# reglas de animate.py (Task 10) que deben sobrevivir a la exportacion
SPINE_BONES = {'spine', 'spine001', 'spine002', 'spine003', 'spine004', 'spine005', 'spine006'}
EYELIDS = {'eyelidL', 'eyelidR'}
OTHER_TEX = 1024
TEX_LIMITS = {'medellin': 2048}      # la ventana se ve enorme en pantalla: no reescalar (1504x846)
# la clave es el NOMBRE SIN EXTENSION: el datablock de Blender se llama 'medellin.png' pero el
# glTF exporta la imagen como 'medellin' (que es lo que comprueba el check de mas abajo).
CHAR_QUALITY = 92                    # el atlas del personaje tiene miles de bordes: JPEG alto
CHAR_IMAGE = 'character_texture_clean'   # nombre de la imagen del atlas dentro del GLB
# escalera de calidad (formato de imagen, calidad JPEG del resto, lado maximo de la textura del personaje)
# El primer escalon NO puede ser fmt='AUTO': para el exportador glTF, AUTO significa "PNG se queda
# PNG", y tanto el atlas del personaje (bpy.data.images.new + file_format='PNG') como medellin.png
# son PNG, asi que CHAR_QUALITY quedaba inerte y el GLB salia con 6 imagenes image/png (10.2 MB).
# Con fmt='JPEG' el exportador convierte todo a JPEG salvo las imagenes con alfa (que conserva en
# PNG); arriba ya se verifica que ninguna textura alimenta Alpha, asi que es seguro.
LADDER = [
    dict(fmt='JPEG', quality=CHAR_QUALITY, char=2048),
    dict(fmt='JPEG', quality=85, char=2048),
    dict(fmt='JPEG', quality=70, char=2048),
    dict(fmt='JPEG', quality=70, char=1536),
]

common.ensure_dirs()
sc = bpy.context.scene
arm = bpy.data.objects['Armature']
OUT = os.path.join(common.EXPORT, 'avatar.glb')
OUT_RAW = os.path.join(common.EXPORT, 'avatar_uncompressed.glb')
valid = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}
assert 'export_rest_position_armature' in valid, 'este Blender no tiene export_rest_position_armature'

# ------------------------------------------------------------------ helpers glTF
def gltf_json(path):
    with open(path, 'rb') as f:
        data = f.read()
    magic, _, length = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67, 'no es un GLB'
    off = 12
    js = binbuf = None
    while off < length:
        clen, ctype = struct.unpack_from('<II', data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A: js = json.loads(chunk.decode('utf-8'))
        elif ctype == 0x004E4942: binbuf = chunk
        off += 8 + clen
    return js, binbuf


def image_info(g, binbuf):
    """(nombre, mimeType, ancho, alto, bytes) de cada imagen embebida en el GLB."""
    out = []
    for im in g.get('images', []):
        bv = g['bufferViews'][im['bufferView']]
        b = binbuf[bv.get('byteOffset', 0): bv.get('byteOffset', 0) + bv['byteLength']]
        w = h = None
        if b[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = struct.unpack('>II', b[16:24])
        elif b[:2] == b'\xff\xd8':
            i = 2
            while i < len(b) - 9:
                if b[i] != 0xFF: i += 1; continue
                marker = b[i + 1]
                if marker in (0xC0, 0xC1, 0xC2):
                    h, w = struct.unpack('>HH', b[i + 5:i + 9]); break
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7: i += 2; continue
                i += 2 + struct.unpack('>H', b[i + 2:i + 4])[0]
        out.append((im.get('name', ''), im.get('mimeType', ''), w, h, len(b)))
    return out


def read_accessor(g, binbuf, i):
    a = g['accessors'][i]; bv = g['bufferViews'][a['bufferView']]
    n = {'SCALAR': 1, 'VEC3': 3, 'VEC4': 4}[a['type']]
    assert a['componentType'] == 5126, f'accessor {i} no es float32'
    start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = bv.get('byteStride', 4 * n)
    return [struct.unpack_from('<' + 'f' * n, binbuf, start + k * stride) for k in range(a['count'])]


def local_quat(pb):
    m = (pb.parent.matrix.inverted() @ pb.matrix) if pb.parent else pb.matrix
    return m.to_quaternion()


def rest_quat(b):
    m = (b.parent.matrix_local.inverted() @ b.matrix_local) if b.parent else b.matrix_local
    return m.to_quaternion()


# ------------------------------------------------------------------ 0. pose base de referencia (SIT)
# Se captura ANTES de tocar nada: estado neutro del archivo (frame 1, sin accion, pistas muteadas).
bpy.context.view_layer.update()
assert arm.animation_data.action is None and all(t.mute for t in arm.animation_data.nla_tracks), \
    'avatar.blend no esta en estado neutro (accion activa o pistas sin mute)'
sit_ref = {pb.name: local_quat(pb) for pb in arm.pose.bones if pb.parent}   # cuaternion local (wxyz)
pose_ref = {}
for bn in POSE_BONES:
    r, p = rest_quat(arm.data.bones[bn]), sit_ref[bn]
    pose_ref[bn] = dict(rest=[round(v, 5) for v in r], posed=[round(v, 5) for v in p])
    print('EXPORT pose_ref', bn, 'rest(wxyz)', pose_ref[bn]['rest'], 'posed(wxyz)', pose_ref[bn]['posed'],
          'dot', round(abs(r.dot(p)), 4))

# ------------------------------------------------------------------ 1. pantallas
for m in SCREENS:
    bpy.data.materials[m].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = SCREEN_EMISSION
print('EXPORT pantallas emission', SCREEN_EMISSION)

# ------------------------------------------------------------------ 2. camaras / luces fuera
removed = []
for o in list(bpy.data.objects):
    if o.type in ('CAMERA', 'LIGHT'):
        removed.append(o.name); bpy.data.objects.remove(o)
for e in KEEP_EMPTIES:
    assert e in bpy.data.objects, f'falta el empty {e}'
print('EXPORT objetos quitados', removed, '| empties conservados', list(KEEP_EMPTIES))

# ------------------------------------------------------------------ 3. texturas
def images_of(mat_name):
    m = bpy.data.materials[mat_name]
    return {n.image for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image}

char_imgs = images_of('Character')
# ninguna textura debe alimentar Alpha (JPEG global descarta el canal alfa)
for m in bpy.data.materials:
    if not m.node_tree: continue
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image and n.outputs['Alpha'].is_linked:
            common.fail(f'{m.name}: la textura {n.image.name} usa Alpha; JPEG no es seguro')

def limit_textures(char_limit):
    for img in bpy.data.images:
        if img.size[0] == 0: continue
        limit = char_limit if img in char_imgs else TEX_LIMITS.get(os.path.splitext(img.name)[0], OTHER_TEX)
        w, h = img.size
        if w > limit:
            img.scale(limit, max(1, int(h * limit / w)))
            img.pack()
            print('EXPORT textura', img.name, 'de', (w, h), 'a', tuple(img.size))

limit_textures(LADDER[0]['char'])
print('EXPORT texturas', [(i.name, tuple(i.size)) for i in bpy.data.images if i.size[0]])

# ------------------------------------------------------------------ 4. pistas NLA (muteadas, ver cabecera)
sc.frame_set(1)
bpy.context.view_layer.update()
print('EXPORT pistas', [(t.name, 'mute' if t.mute else 'on') for t in arm.animation_data.nla_tracks],
      'frame', sc.frame_current)
# la pose evaluada tras quitar camaras/luces (rebuild del depsgraph) debe seguir siendo SIT
drift = max(1 - abs(local_quat(arm.pose.bones[bn]).dot(q)) for bn, q in sit_ref.items())
print('EXPORT pose base vs SIT del archivo, desviacion maxima', round(drift, 6))
if drift > 1e-4: common.fail('la pose base antes de exportar ya no es SIT')

# ------------------------------------------------------------------ 5. exportar (escalera)
def do_export(path, draco, step):
    # el exportador glTF no admite calidad JPEG por imagen: la calidad del escalon se aplica a
    # todas. El primer escalon ya vale CHAR_QUALITY (ver LADDER).
    quality = step['quality']
    common.export_glb(path, draco=draco, animations=True,
                      export_image_format=step['fmt'],
                      export_jpeg_quality=quality,     # Blender >= 4.2
                      export_image_quality=quality,    # Blender < 4.2 (JPEG) / WebP
                      export_rest_position_armature=False,
                      export_reset_pose_bones=False,
                      export_optimize_animation_keep_anim_armature=False,
                      export_cameras=False, export_lights=False)
    return os.path.getsize(path)

chosen = None
for step in LADDER:
    limit_textures(step['char'])
    size = do_export(OUT, True, step)
    print('EXPORT intento', step, 'bytes', size, 'MB', round(size / 1048576, 2))
    if size < BUDGET:
        chosen = step; break
if chosen is None:
    common.fail(f'avatar.glb sigue por encima de {BUDGET} bytes tras la escalera')
size_raw = do_export(OUT_RAW, False, chosen)
print('EXPORT final', chosen, 'avatar.glb', os.path.getsize(OUT), 'avatar_uncompressed.glb', size_raw)

# ------------------------------------------------------------------ 6. verificacion
r = glb_inspect.inspect(OUT)
with open(os.path.join(common.GEN, 'avatar_inspect.json'), 'w') as f:
    json.dump(r, f, indent=2, ensure_ascii=False)
ok = True
def check(cond, msg):
    global ok
    print(('EXPORT_CHECK ok  ' if cond else 'EXPORT_CHECK FAIL') , msg)
    ok = ok and bool(cond)

check(r['size_bytes'] < BUDGET, f"size {r['size_bytes']} < {BUDGET}")
check(r['triangles'] < MAX_TRIS, f"tris {r['triangles']} < {MAX_TRIS}")
check(r['draco'], 'draco')
check(r['skins'] == 1, f"skins {r['skins']} == 1")
for a in TRACKS: check(a in r['animations'], f'animacion {a}')
check(sorted(r['animations']) == sorted(TRACKS), f"animaciones exactas {r['animations']}")
for n in NODES: check(n in r['nodes'], f'nodo {n}')
for e in KEEP_EMPTIES: check(e in r['nodes'], f'empty {e}')
check(not any(n in r['nodes'] for n in removed), f'sin camaras/luces {removed}')

g, binbuf = gltf_json(OUT)
imgs = image_info(g, binbuf)
for name, mime, w, h, nb in imgs:
    print('EXPORT imagen', name, mime, f'{w}x{h}', nb, 'bytes')
check(all(w <= 2048 and h <= 2048 for _, _, w, h, _ in imgs), 'imagenes <= 2048')
mats = {m.get('name'): m for m in g.get('materials', [])}
for m in SCREENS:
    mm = mats.get(m, {})
    check('emissiveTexture' in mm, f'{m} emissiveTexture={mm.get("emissiveTexture")} '
          f'factor={mm.get("emissiveFactor")} alphaMode={mm.get("alphaMode", "OPAQUE")}')
print('EXPORT alphaMode', {k: v.get('alphaMode', 'OPAQUE') for k, v in mats.items()})

ch = mats.get('Character', {})
pbr = ch.get('pbrMetallicRoughness', {})
check(pbr.get('metallicFactor', 1.0) == 0, f"Character metallicFactor={pbr.get('metallicFactor', 'ausente=1.0')}")
check(0.7 <= pbr.get('roughnessFactor', 1.0) <= 0.95, f"Character roughnessFactor={pbr.get('roughnessFactor', 'ausente=1.0')}")
check('emissiveTexture' not in ch, 'Character sin emissiveTexture')
check('KHR_materials_specular' not in ch.get('extensions', {}), 'Character sin KHR_materials_specular')
win = next((w for n, _, w, h, _ in imgs if n == 'medellin'), None)
check(win == 1504, f'medellin exportada a {win} de ancho (esperado 1504, sin reescalar)')
# el atlas del personaje DEBE salir en JPEG: en PNG pesa ~5 MB y CHAR_QUALITY seria inerte
char_mime = next((m for n, m, _, _, _ in imgs if n == CHAR_IMAGE), None)
check(char_mime == 'image/jpeg', f'{CHAR_IMAGE} mime={char_mime} (esperado image/jpeg, q{CHAR_QUALITY})')
png = [n for n, m, _, _, _ in imgs if m == 'image/png']
print('EXPORT imagenes PNG restantes (solo se justifican con alfa)', png)

by_name = {}
for i, n in enumerate(g.get('nodes', [])):
    by_name.setdefault(n.get('name', ''), n)

def glb_quat(bn):
    q = by_name[bn].get('rotation', [0, 0, 0, 1])       # glTF: xyzw
    return Quaternion((q[3], q[0], q[1], q[2]))

for bn in POSE_BONES:
    qg = glb_quat(bn)
    d_rest = abs(qg.dot(Quaternion(pose_ref[bn]['rest'])))
    d_posed = abs(qg.dot(Quaternion(pose_ref[bn]['posed'])))
    print('EXPORT pose_glb', bn, 'rotation(wxyz)', [round(v, 4) for v in qg], 'dot_rest', round(d_rest, 4), 'dot_posed', round(d_posed, 4))
    check(d_posed > POSE_TOL, f'{bn} exporta la pose SIT')
# upper_armL: SIT y reposo distan ~21 grados (dot 0.93); handL solo ~4.6, no discrimina
qg = glb_quat('upper_armL')
check(abs(qg.dot(Quaternion(pose_ref['upper_armL']['rest']))) < 0.99, 'upper_armL NO exporta el reposo (A-pose)')
# todos los huesos (con padre) del GLB deben llevar la pose SIT del archivo como pose base
devs = sorted(((round(abs(glb_quat(bn).dot(q)), 5), bn) for bn, q in sit_ref.items() if bn in by_name))
print('EXPORT pose base vs SIT del archivo, huesos con mas desviacion', devs[:4])
check(devs[0][0] > POSE_TOL, f'pose base de todos los huesos = SIT (peor {devs[0]})')

# clips: cada clip solo debe llevar los huesos que anima (sin canales constantes)
node_names = [n.get('name', '') for n in g.get('nodes', [])]
clip_bones = {}
for an in g.get('animations', []):
    moving, const = set(), []
    for c in an['channels']:
        bn = node_names[c['target']['node']]
        vals = read_accessor(g, binbuf, an['samplers'][c['sampler']]['output'])
        if all(max(abs(a - b) for a, b in zip(v, vals[0])) < 1e-6 for v in vals):
            const.append((bn, c['target']['path']))
        else:
            moving.add(bn)
    clip_bones[an['name']] = moving
    print('EXPORT clip', an['name'], 'canales', len(an['channels']), 'huesos animados', sorted(moving),
          '| canales constantes', const)
    check(not const, f"{an['name']} sin canales constantes")
check(not (clip_bones.get('typing', set()) & SPINE_BONES), 'typing no toca columna ni cabeza')
check(not (clip_bones.get('idle', set()) & {'upper_armL', 'upper_armR', 'handL', 'handR'}), 'idle no toca brazos')
check(clip_bones.get('Blink', set()) == EYELIDS, 'Blink solo parpados')
check({n for n, b in clip_bones.items() if 'spine006' in b} == {'vibe', 'lookAround'}, 'solo vibe/lookAround mueven spine006')
check({n for n, b in clip_bones.items() if 'headphones' in b} == {'vibe'}, 'solo vibe mueve headphones')

if not ok:
    common.fail('verificacion del GLB')
print('GLB OK', r['size_bytes'] // 1024, 'KB', r['triangles'], 'tris', r['animations'])
