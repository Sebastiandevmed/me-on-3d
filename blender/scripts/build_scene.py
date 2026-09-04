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
m_wall = mat('Wall', (0.10, 0.11, 0.14, 1), roughness=0.92)
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
# La cara superior del laptop es donde se apoyan las manos: `poses.py` / `calibrate_hands.py`
# estan calibrados contra DESK_Z + 0.030. Para dar definicion al teclado SIN mover esa altura,
# la base baja 1.5 mm y las teclas rellenan justo ese 1.5 mm, asi que el TOPE DE LAS TECLAS
# vuelve a caer en DESK_Z + 0.030. Las ranuras entre teclas las dibuja el pase de contorno.
KEY_TOP = DESK_Z + 0.030        # altura de apoyo de las manos (no tocar sin recalibrar la pose)
KEY_H = 0.0015                  # m de resalte de la tecla sobre el hundido
box('laptop_base', (0.32, 0.22, 0.012 - KEY_H), (0, 0.98, DESK_Z + 0.024 - KEY_H / 2), m_alu, col)

# rejilla de teclas: 14 columnas x 5 filas sobre la mitad delantera de la base
KEY_COLS, KEY_ROWS = 14, 5
KEY_AREA_X, KEY_AREA_Y = 0.26, 0.090
KEY_CY = 1.000                  # centro Y de la zona de teclas
KEY_GAP = 0.0022                # m de ranura entre teclas
m_key = mat('Key', (0.045, 0.045, 0.05, 1), roughness=0.65)
px, py = KEY_AREA_X / KEY_COLS, KEY_AREA_Y / KEY_ROWS
keys = []
for r in range(KEY_ROWS):
    for c in range(KEY_COLS):
        kx = -KEY_AREA_X / 2 + (c + 0.5) * px
        ky = KEY_CY - KEY_AREA_Y / 2 + (r + 0.5) * py
        keys.append(box(f'key_{r}_{c}', (px - KEY_GAP, py - KEY_GAP, KEY_H),
                        (kx, ky, KEY_TOP - KEY_H / 2), m_key, col))
# barra espaciadora y trackpad, delante de la rejilla (lado del personaje = -Y)
keys.append(box('key_space', (0.105, py - KEY_GAP, KEY_H), (0, KEY_CY - KEY_AREA_Y / 2 - py * 0.75, KEY_TOP - KEY_H / 2), m_key, col))
keys.append(box('trackpad', (0.085, 0.052, KEY_H), (0, 0.912, KEY_TOP - KEY_H / 2), m_alu, col))
# unir en una sola malla: 72 objetos sueltos ensucian el grafo del GLB
bpy.ops.object.select_all(action='DESELECT')
for k in keys: k.select_set(True)
bpy.context.view_layer.objects.active = keys[0]
bpy.ops.object.join()
bpy.context.active_object.name = 'laptop_keys'
bpy.ops.object.select_all(action='DESELECT')
print('TECLADO', len(keys), 'teclas unidas, tope en z', round(KEY_TOP, 4))
box('laptop_lid', (0.32, 0.008, 0.21), (0, 1.09, DESK_Z + 0.135), m_alu, col,
    rotation=(math.radians(-12), 0, 0))
m_screen_laptop = screen_mat('Screen_Laptop', 'code.png')
m_screen_laptop.use_backface_culling = True
plane('screen_laptop', (0.29, 0.18), (0, 1.085, DESK_Z + 0.135), rotation=(math.radians(90 - 12), 0, 0),
      material=m_screen_laptop, collection=col)

# --- 3 monitores (bajos, en arco, para dejar la cara del personaje visible por encima)
# Nota de controlador: la camara de aprobacion queda AL OTRO LADO del escritorio
# (ver camara mas abajo), por lo que las pantallas siguen mirando hacia -Y (hacia
# el personaje, como en el brief original); el guinado de las laterales hacia el
# centro es lo que deja asomar parte de la pantalla derecha hacia la camara.
# El LOGO va en el monitor CENTRAL (pedido del usuario): es el mas grande y el que queda de
# frente cuando la camara rodea el escritorio hasta ver las pantallas.
MON = [('L', -0.62, 0.52, 0.28, 'screen_left', 'Screen_Left', 'code.png', 32),
       ('C', 0.0, 0.60, 0.32, 'screen_center', 'Screen_Center', 'logo.png', 0),
       ('R', 0.62, 0.52, 0.28, 'screen_right', 'Screen_Right', 'stack.png', -32)]
for tag, x, w, h, sname, mname, png, yaw in MON:
    zc = DESK_Z + 0.06 + h / 2
    y = 1.45
    yaw_rad = math.radians(yaw)
    box(f'monitor_{tag}', (w, 0.03, h), (x, y, zc), m_black, col, rotation=(0, 0, yaw_rad))
    scr_mat = screen_mat(mname, png)
    scr_mat.use_backface_culling = True
    scr_x = x + 0.016 * math.sin(yaw_rad)
    scr_y = y - 0.016 * math.cos(yaw_rad)
    # SIN emparentar a la carcasa: el emparentamiento usaba matrix_parent_inverse calculada
    # sobre un matrix_world todavia sin evaluar, y ambas mallas ya viven en coordenadas de
    # mundo. Cada una lleva su propia rotacion horneada y no necesitan jerarquia.
    plane(sname, (w - 0.02, h - 0.02), (scr_x, scr_y, zc), rotation=(math.radians(90), 0, yaw_rad),
          material=scr_mat, collection=col)
    cylinder(f'monitor_stand_{tag}', 0.02, 0.12, (x, y, DESK_Z + 0.06), material=m_alu, collection=col)
    base = box(f'monitor_base_{tag}', (0.22, 0.16, 0.012), (x, y, DESK_Z + 0.02), m_alu, col)

# --- barras RGB (parte del telon de fondo detras del personaje)
BAR_Y, BAR_BOT = -1.25, 0.79        # BAR_BOT = base de la barra = DESK_Z + 0.5 - 0.9/2
for tag, x in (('L', -1.05), ('R', 1.05)):
    cylinder(f'rgb_bar_{tag}', 0.018, 0.9, (x, BAR_Y, DESK_Z + 0.5), material=m_rgb, verts=12, collection=col)
    # tripode negro: poste del suelo a la barra + 3 patas abiertas a 120 grados
    cylinder(f'rgb_post_{tag}', 0.011, BAR_BOT - 0.03, (x, BAR_Y, (BAR_BOT + 0.03) / 2),
             material=m_black, verts=10, collection=col)
    cylinder(f'rgb_hub_{tag}', 0.030, 0.024, (x, BAR_Y, 0.030), material=m_black, verts=12, collection=col)
    for i in range(3):
        a = math.radians(90 + i * 120)
        box(f'rgb_leg_{tag}{i}', (0.17, 0.018, 0.014),
            (x + 0.085 * math.cos(a), BAR_Y + 0.085 * math.sin(a), 0.010), m_black, col,
            rotation=(0, 0, a))

# --- habitacion: paredes y techo (antes no existian y el visor quedaba negro)
# Cuarto encogido (pedido del usuario: "haz la habitacion mas pequena para que se vea mejor
# la repisa"). Antes 5.6 x 2.8 m de alto con la pared trasera a -1.7: la repisa quedaba a 2.0 m
# del eje, casi fuera de encuadre. Ahora el cuarto es 4.1 m de ancho y 2.5 de alto, y la repisa
# se acerca a 1.5. La ventana se reescala manteniendo 16:9.
ROOM_X, ROOM_Y_BACK, ROOM_H = 2.05, -1.45, 2.5        # medias anchuras / pared trasera / altura
WIN_X0, WIN_X1, WIN_Z0, WIN_Z1 = -1.5, 0.9, 0.72, 2.07  # hueco de la ventana (2.4 x 1.35 = 16:9)
WALL_T = 0.10
yb = ROOM_Y_BACK - WALL_T / 2                          # centro de las cajas de la pared trasera
box('wall_back_L', (WIN_X0 + ROOM_X, WALL_T, ROOM_H), ((WIN_X0 - ROOM_X) / 2, yb, ROOM_H / 2), m_wall, col)
box('wall_back_R', (ROOM_X - WIN_X1, WALL_T, ROOM_H), ((WIN_X1 + ROOM_X) / 2, yb, ROOM_H / 2), m_wall, col)
box('wall_back_top', (WIN_X1 - WIN_X0, WALL_T, ROOM_H - WIN_Z1), ((WIN_X0 + WIN_X1) / 2, yb, (WIN_Z1 + ROOM_H) / 2), m_wall, col)
box('wall_back_bottom', (WIN_X1 - WIN_X0, WALL_T, WIN_Z0), ((WIN_X0 + WIN_X1) / 2, yb, WIN_Z0 / 2), m_wall, col)
box('wall_left', (WALL_T, 6.0, ROOM_H), (-ROOM_X - WALL_T / 2, 1.0, ROOM_H / 2), m_wall, col)
box('wall_right', (WALL_T, 6.0, ROOM_H), (ROOM_X + WALL_T / 2, 1.0, ROOM_H / 2), m_wall, col)
box('ceiling', (2 * ROOM_X + 2 * WALL_T, 6.0, WALL_T), (0, 1.0, ROOM_H + WALL_T / 2), m_wall, col)

# --- repisa con soportes en L sobre la pared trasera derecha (+X = izquierda de la camara)
SHELF_X, SHELF_Z = 1.5, DESK_Z + 0.71
SHELF_D = 0.24
shelf_y = ROOM_Y_BACK + SHELF_D / 2                     # pegada a la cara interior de la pared
box('shelf', (0.55, SHELF_D, 0.03), (SHELF_X, shelf_y, SHELF_Z), m_dark, col)
for i, dx in enumerate((-0.18, 0.18)):
    box(f'shelf_bracket_{i}', (0.025, 0.025, 0.16), (SHELF_X + dx, ROOM_Y_BACK + 0.0125, SHELF_Z - 0.095), m_alu, col)
    box(f'shelf_arm_{i}', (0.025, SHELF_D - 0.02, 0.025), (SHELF_X + dx, shelf_y - 0.01, SHELF_Z - 0.0275), m_alu, col)
bpy.ops.object.empty_add(location=(SHELF_X, shelf_y, SHELF_Z + 0.015)); bpy.context.active_object.name = 'moto_anchor'

# --- taza y control
cylinder('mug', 0.045, 0.1, (0.45, 0.95, DESK_Z + 0.07), material=m_black, verts=20, collection=col)
ctrl = box('controller', (0.16, 0.1, 0.045), (-0.42, 0.92, DESK_Z + 0.04), m_black, col,
           rotation=(0, 0, math.radians(20)))
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
wcx, wcz = (WIN_X0 + WIN_X1) / 2, (WIN_Z0 + WIN_Z1) / 2
plane('window_far', (WIN_X1 - WIN_X0, WIN_Z1 - WIN_Z0), (wcx, ROOM_Y_BACK - 0.02, wcz),
      rotation=(math.radians(90), 0, math.radians(180)), material=m_far, collection=col)
m_frame = mat('Window_Frame', (0.03, 0.03, 0.035, 1), roughness=0.6)
box('window_near', (WIN_X1 - WIN_X0 + 0.16, 0.08, 0.06), (wcx, ROOM_Y_BACK + 0.04, WIN_Z0 - 0.03), m_frame, col)   # antepecho
for tag, x in (('L', WIN_X0 - 0.04), ('R', WIN_X1 + 0.04)):
    box(f'window_post_{tag}', (0.08, 0.08, WIN_Z1 - WIN_Z0 + 0.12), (x, ROOM_Y_BACK + 0.04, wcz), m_frame, col)
box('window_head', (WIN_X1 - WIN_X0 + 0.16, 0.08, 0.06), (wcx, ROOM_Y_BACK + 0.04, WIN_Z1 + 0.03), m_frame, col)

# --- vidrio. Plano casi transparente DELANTE de la imagen de la ciudad. En Blender apenas se
# nota; el efecto de reflejo lo pinta el visor, que reconoce el material por nombre y le monta
# un shader aditivo (dos bandas diagonales + realce fresnel en angulo rasante). Se resuelve asi
# y no con una reflexion real (planar/cubemap) porque el look es cel-shaded: en ilustracion una
# ventana se lee como vidrio por el DESTELLO, no por reflejar la habitacion, y una reflexion
# real costaria una pasada de render entera para verse peor.
m_glass = mat('Window_Glass', (0.55, 0.72, 1.0, 1.0), roughness=0.03, metallic=0.0)
# La transparencia va en la entrada Alpha del Principled, NO en el 4o canal del color base:
# ese canal se ignora y el plano se renderiza OPACO, tapando la ciudad con un rectangulo azul
# (se vio en assembled_v1.png). Alpha 0.02 lo deja practicamente invisible en Blender, que es
# lo que se quiere: el destello lo pinta el visor sustituyendo el material entero (lib/glass.js).
m_glass.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0.02
m_glass.blend_method = 'BLEND'
plane('window_glass', (WIN_X1 - WIN_X0, WIN_Z1 - WIN_Z0), (wcx, ROOM_Y_BACK + 0.012, wcz),
      rotation=(math.radians(90), 0, math.radians(180)), material=m_glass, collection=col)

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
