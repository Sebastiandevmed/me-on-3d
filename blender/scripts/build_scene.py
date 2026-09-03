# blender/scripts/build_scene.py
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
from common import box, cylinder, plane, mat

common.ensure_dirs(); common.reset_scene()
sc = bpy.context.scene
col = bpy.data.collections.new('Scene'); sc.collection.children.link(col)
SCREENS = os.path.join(common.GEN, 'screens')

# --- materiales
m_desk = mat('Desk', (0.02, 0.02, 0.022, 1), roughness=0.45)
m_black = mat('MatteBlack', (0.01, 0.01, 0.012, 1), roughness=0.7)
m_dark = mat('DarkGrey', (0.05, 0.05, 0.055, 1), roughness=0.5)
m_white = mat('White', (0.85, 0.85, 0.85, 1), roughness=0.4)
m_alu = mat('Aluminium', (0.6, 0.6, 0.62, 1), roughness=0.35, metallic=0.9)
m_rgb = mat('RGB_Bar', (0.1, 0.1, 0.1, 1), emission=(0.25, 0.55, 1.0, 1), emission_strength=6.0)
m_floor = mat('Floor', (0.015, 0.015, 0.017, 1), roughness=0.8)
def screen_mat(name, png):
    p = os.path.join(SCREENS, png)
    if os.path.exists(p):
        return mat(name, (0, 0, 0, 1), roughness=0.2, image_path=p, emission=(1, 1, 1, 1), emission_strength=0.0)
    print(f'WARNING PLACEHOLDER pantalla {name} sin textura: falta {p} (ejecutar tools/screens/make_screens.sh)')
    return mat(name, (0.02, 0.02, 0.03, 1), roughness=0.2, emission=(0.2, 0.4, 1, 1), emission_strength=0.0)

# --- piso y escritorio
plane('floor', (8, 8), (0, 1, 0), material=m_floor, collection=col)
DESK_Z = 0.74
box('desk', (2.0, 0.8, 0.035), (0, 1.15, DESK_Z), m_desk, col)   # borde delantero en y=0.75
for i, x in enumerate((-0.92, 0.92)):
    box(f'desk_leg_{i}', (0.05, 0.7, DESK_Z), (x, 1.15, DESK_Z / 2), m_black, col)

# --- silla (vista de espaldas)
box('chair_seat', (0.5, 0.5, 0.08), (0, 0.55, 0.43), m_black, col)
box('chair_back', (0.5, 0.08, 0.6), (0, 0.32, 0.78), m_black, col)
cylinder('chair_post', 0.03, 0.4, (0, 0.55, 0.2), material=m_alu, collection=col)
bpy.ops.object.empty_add(location=(0, 0.55, 0.47)); bpy.context.active_object.name = 'seat_anchor'

# --- laptop
box('laptop_base', (0.32, 0.22, 0.012), (0, 0.98, DESK_Z + 0.024), m_alu, col)
lap_screen = box('laptop_lid', (0.32, 0.008, 0.21), (0, 1.09, DESK_Z + 0.135), m_alu, col)
lap_screen.rotation_euler = (math.radians(-12), 0, 0)
m_screen_laptop = screen_mat('Screen_Laptop', 'code.png')
m_screen_laptop.use_backface_culling = True
plane('screen_laptop', (0.29, 0.18), (0, 1.085, DESK_Z + 0.135), rotation=(math.radians(90 - 12), 0, 0),
      material=m_screen_laptop, collection=col)

# --- 3 monitores (bajos, en arco, para dejar la cara del personaje visible por encima)
# Nota de controlador: la camara de aprobacion queda AL OTRO LADO del escritorio
# (ver camara mas abajo), por lo que las pantallas siguen mirando hacia -Y (hacia
# el personaje, como en el brief original); el guinado de las laterales hacia el
# centro es lo que deja asomar parte de la pantalla derecha hacia la camara.
MON = [('L', -0.62, 0.52, 0.28, 'screen_left', 'Screen_Left', 'code.png', 32),
       ('C', 0.0, 0.60, 0.32, 'screen_center', 'Screen_Center', 'stack.png', 0),
       ('R', 0.62, 0.52, 0.28, 'screen_right', 'Screen_Right', 'logo.png', -32)]
for tag, x, w, h, sname, mname, png, yaw in MON:
    zc = DESK_Z + 0.06 + h / 2
    y = 1.45
    yaw_rad = math.radians(yaw)
    body = box(f'monitor_{tag}', (w, 0.03, h), (x, y, zc), m_black, col)
    body.rotation_euler = (0, 0, yaw_rad)
    scr_mat = screen_mat(mname, png)
    scr_mat.use_backface_culling = True
    scr_x = x + 0.016 * math.sin(yaw_rad)
    scr_y = y - 0.016 * math.cos(yaw_rad)
    scr = plane(sname, (w - 0.02, h - 0.02), (scr_x, scr_y, zc), rotation=(math.radians(90), 0, yaw_rad),
                material=scr_mat, collection=col)
    scr.parent = body; scr.matrix_parent_inverse = body.matrix_world.inverted()
    cylinder(f'monitor_stand_{tag}', 0.02, 0.12, (x, y, DESK_Z + 0.06), material=m_alu, collection=col)
    base = box(f'monitor_base_{tag}', (0.22, 0.16, 0.012), (x, y, DESK_Z + 0.02), m_alu, col)

# --- barras RGB (parte del telon de fondo detras del personaje)
for tag, x in (('L', -1.05), ('R', 1.05)):
    cylinder(f'rgb_bar_{tag}', 0.018, 0.9, (x, -1.3, DESK_Z + 0.5), material=m_rgb, verts=12, collection=col)

# --- repisa flotante con anchor para la moto (atras-izquierda, visible detras del personaje)
box('shelf', (0.5, 0.22, 0.03), (-1.25, -0.6, DESK_Z + 0.75), m_dark, col)
bpy.ops.object.empty_add(location=(-1.25, -0.6, DESK_Z + 0.765)); bpy.context.active_object.name = 'moto_anchor'

# --- taza y control
cylinder('mug', 0.045, 0.1, (0.45, 0.95, DESK_Z + 0.07), material=m_black, verts=20, collection=col)
ctrl = box('controller', (0.16, 0.1, 0.045), (-0.42, 0.92, DESK_Z + 0.04), m_black, col)
ctrl.rotation_euler = (0, 0, math.radians(20))
bev = ctrl.modifiers.new('bevel', 'BEVEL'); bev.width = 0.015; bev.segments = 3

# --- ventana: ahora DETRAS del personaje, hace de telon de fondo nocturno.
# La normal se orienta hacia +Y (hacia la sala/camara) en vez de -Y como en el
# brief original, porque la ventana se movio al lado opuesto del cuarto.
WIN = os.path.join(common.GEN, 'window', 'medellin.png')
if os.path.exists(WIN):
    m_far = mat('Window_Far', (0, 0, 0, 1), roughness=1.0, image_path=WIN,
                emission=(1, 1, 1, 1), emission_strength=1.2)
else:
    # sin imagen todavia: fondo nocturno azulado en vez de blanco quemado
    print(f'WARNING PLACEHOLDER ventana Window_Far sin imagen: falta {WIN} (imagen de Higgsfield, insumo irremplazable)')
    m_far = mat('Window_Far', (0, 0, 0, 1), roughness=1.0,
                emission=(0.02, 0.05, 0.12, 1), emission_strength=0.4)
# rotación (90°,0,180°): normal hacia +Y (la habitación) y el eje V de la textura hacia +Z.
# Con (-90,0,0) la normal también mira a +Y pero la imagen queda cabeza abajo.
plane('window_far', (4.0, 2.25), (0, -1.6, 1.55), rotation=(math.radians(90), 0, math.radians(180)), material=m_far, collection=col)
m_frame = mat('Window_Frame', (0.03, 0.03, 0.035, 1), roughness=0.6)
box('window_near', (4.2, 0.06, 0.25), (0, -1.4, 0.42), m_frame, col)          # antepecho
for x in (-2.1, 2.1):
    box(f'window_post_{int(x)}', (0.08, 0.06, 2.4), (x, -1.4, 1.5), m_frame, col)

# --- camara y luces para renders de aprobacion
# Ruling del controlador: la camara debe quedar ENFRENTE del personaje, cruzando
# el escritorio, para que se vea su cara (el personaje mira hacia +Y).
cam = common.add_camera((-1.3, 3.7, 1.95), (0, 0.5, 1.05), lens=35)
common.add_light('key', 'AREA', (-1.2, 2.4, 2.2), 80, (0.75, 0.85, 1.0), size=1.2)
common.add_light('screen_glow', 'AREA', (0, 1.3, 1.1), 25, (0.6, 0.75, 1.0), size=1.5)
sc.world = bpy.data.worlds.new('World'); sc.world.use_nodes = True
sc.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.002, 0.003, 0.006, 1)

common.render(os.path.join(common.RENDERS, 'scene_v1.png'))

# --- segundo render de aprobacion: punto de vista del personaje, para
# verificar que las 3 pantallas de los monitores y el laptop se lean bien
# y sin espejado (backface culling ya activo en sus materiales).
SCREEN_MAT_NAMES = ('Screen_Left', 'Screen_Center', 'Screen_Right', 'Screen_Laptop')
cam.location = (0, 0.55, 1.25)
common.look_at(cam, (0, 1.45, 1.0))
cam.data.lens = 24
screen_mats = [bpy.data.materials[n] for n in SCREEN_MAT_NAMES]
for sm in screen_mats:
    sm.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
common.render(os.path.join(common.RENDERS, 'scene_v1_screens.png'))
for sm in screen_mats:
    sm.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 0.0

# restaurar la camara de aprobacion original antes de guardar: las tareas
# posteriores abren scene.blend y renderizan directamente con esa camara.
cam.location = (-1.3, 3.7, 1.95)
common.look_at(cam, (0, 0.5, 1.05))
cam.data.lens = 35

print('SCENE_TRIS', common.scene_tri_count())
common.save(os.path.join(common.BLEND_DIR, 'scene.blend'))
