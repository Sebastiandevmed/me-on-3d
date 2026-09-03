# blender/scripts/poses.py
"""Constantes de pose para el personaje de 'Me on 3D'.

Los valores de AXES/SIDE se rellenaron con lo observado en `pose_probe.py` (12 renders,
+60 grados en X/Y/Z sobre thighL, upper_armL, spine006 y forearmL) y con un volcado
numerico de `bone.matrix_local` (ejes locales de reposo expresados en el mundo).

Convencion de la escena: el personaje mira a +Y, su lado izquierdo esta en -X, pies en z=0.
El importador glTF deja los huesos en QUATERNION: `apply()` fuerza 'XYZ' antes de asignar.

CALIBRACION MEDIDA (eje local -> direccion en el mundo):

  hueso            X local        Y local (=hueso)   Z local        lectura
  -------------    ------------   ----------------   ------------   ---------------------------
  thighL/R         -X mundo       abajo              -Y mundo       +X = pierna atras;  +Z = tobillo hacia +X
  shinL/R          -X mundo       abajo              -Y mundo       +X = flexion de rodilla (talon atras)
  footL/R          -X mundo       adelante-abajo     ~-Y/-Z         +X = punta del pie abajo (flexion plantar)
  spine001/2/3/5   -X mundo       arriba             +Y mundo       +X = inclinar el torso adelante
  spine006 (head)  -X mundo       arriba-adelante    +Y/-Z          +X = asentir hacia abajo; +Z = girar a su derecha (+X)
  shoulderL/R      -+Y mundo      hacia el hombro    -Z mundo       +Z = adelante (L) / atras (R); +X = hombro abajo
  upper_armL       diagonal 45    abajo-afuera       diagonal 45    +X = brazo atras-adentro; +Z = aduccion (pegar al torso) + adelante
  forearmL/handL   diagonal 45    abajo-afuera       diagonal 45    +X = antebrazo atras; +Z = adelante-adentro
  (R es espejo en X y en Z para los brazos; para las piernas NO: ambos femures
   comparten los mismos ejes locales, +Z lleva el tobillo hacia +X en los dos)

OJO: en brazos y antebrazos los ejes locales estan a ~45 grados del plano sagital, asi que
un giro "puro hacia adelante" necesita X y Z a la vez (adelante ~ -X y +Z a partes iguales;
abrir hacia afuera y arriba ~ -X y -Z). Por eso los valores de brazos en SIT son eulers
explicitos calculados apuntando el hueso a una direccion del mundo (ver `aim()`), no rot().

El rig NO tiene huesos de dedos (Meshy los omitio): el bucle de dedos de abajo es inocuo
porque `apply()` usa `pose.bones.get()`.
"""
import math

# Eje (indice 0,1,2) y signo que dobla el hueso HACIA ADELANTE (+Y del mundo).
# Ej: {'thighL': (0, -1)} = rotar en X con valor negativo lleva el muslo hacia +Y.
AXES = {
    'thighL': (0, -1), 'thighR': (0, -1),
    'shinL': (0, -1), 'shinR': (0, -1),      # medido: +X flexiona la rodilla (el brief traia (0,1))
    'footL': (0, -1), 'footR': (0, -1),      # +X baja la punta del pie
    'upper_armL': (0, -1), 'upper_armR': (0, -1),
    'forearmL': (0, -1), 'forearmR': (0, -1),
    'handL': (0, -1), 'handR': (0, -1),
    'spine006': (0, 1), 'spine005': (0, 1),  # en spine006 "adelante" = asentir hacia abajo
    'spine002': (0, 1), 'spine003': (0, 1), 'spine001': (0, 1),
    'shoulderL': (2, 1), 'shoulderR': (2, -1),
}
# Ejes secundarios: (indice, signo) que abre el miembro hacia AFUERA / gira la cabeza a su izquierda (-X).
SIDE = {
    'upper_armL': (2, -1), 'upper_armR': (2, 1),   # -Z (L) abre el brazo; +Z lo pega al torso
    'thighL': (2, -1), 'thighR': (2, 1),           # abre las piernas
    'spine006': (2, -1),                           # -Z gira la cara hacia -X (su izquierda)
}
FINGER_AXIS = (0, -1)   # eje que cerraria los dedos (este rig no tiene huesos de dedos)


def rot(bone, forward_deg=0.0, side_deg=0.0, twist_deg=0.0):
    """Devuelve euler (radianes) para un hueso dado un angulo hacia adelante y lateral."""
    e = [0.0, 0.0, 0.0]
    ai, s = AXES.get(bone, (0, 1))
    e[ai] += math.radians(forward_deg) * s
    if side_deg and bone in SIDE:
        si, ss = SIDE[bone]; e[si] += math.radians(side_deg) * ss
    if twist_deg:
        ti = 3 - ai - (SIDE.get(bone, (1, 1))[0] if bone in SIDE else 1)
        e[ti % 3] += math.radians(twist_deg)
    return tuple(e)


def finger_rot(deg):
    e = [0.0, 0.0, 0.0]; e[FINGER_AXIS[0]] = math.radians(deg) * FINGER_AXIS[1]
    return tuple(e)


def deg(x, y, z):
    """Euler explicito en grados -> radianes (para huesos de ejes diagonales)."""
    return (math.radians(x), math.radians(y), math.radians(z))


def aim(arm, bone, direction):
    """Rota `bone` (euler XYZ local) para que apunte a `direction` en coordenadas del mundo.

    Es el generador de los valores de brazos y piernas de SIT: se aplica en orden padre->hijo
    y con el resto de la cadena ya posada. Requiere `bpy` y un depsgraph actualizado.
    """
    import bpy
    from mathutils import Vector
    pb = arm.pose.bones[bone]
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    m = (arm.matrix_world @ pb.matrix).to_3x3()
    u = m.inverted() @ Vector(direction).normalized()
    u.normalize()
    pb.rotation_euler = Vector((0, 1, 0)).rotation_difference(u).to_euler('XYZ')
    bpy.context.view_layer.update()
    return tuple(pb.rotation_euler)



# Normal de la PALMA en el espacio local del hueso hand{L,R}. Medida sobre la malla deformada:
# eje mas delgado de la nube de vertices de la mano (PCA) desambiguado con la curvatura de los
# dedos (las yemas se doblan HACIA la palma); sale igual en reposo y en SIT. No coincide con
# ningun eje local puro: la palma mira a -0.75 X + 0.65 Z en handL y a +0.75 X + 0.65 Z en handR
# (los huesos del brazo derecho son espejo en X). En SIT la palma queda mirando hacia adentro.
PALM_LOCAL = {'L': (-0.750, -0.120, 0.650), 'R': (0.751, -0.118, 0.650)}


def aim_roll(arm, bone, direction, palm, palm_local):
    """Como `aim()` pero fijando TAMBIEN el giro del hueso sobre su propio eje.

    `aim()` usa la rotacion minima (`rotation_difference`), asi que clava la direccion del hueso
    pero deja el roll al azar: en una mano eso significa que la palma acaba mirando a cualquier
    lado. Aqui se construye la orientacion completa: el +Y local del hueso va a `direction` y
    `palm_local` (p.ej. `PALM_LOCAL[lado]`) va a `palm`. Los dos objetivos van en coordenadas
    del mundo y se ortogonalizan entre si; manda `direction`.
    """
    import bpy
    from mathutils import Vector, Matrix

    def frame(d, p):
        e1 = Vector(d).normalized()
        e2 = Vector(p) - e1 * Vector(p).dot(e1)
        if e2.length < 1e-6:
            raise ValueError(f'aim_roll({bone!r}): la palma es paralela a la direccion del hueso')
        e2.normalize()
        return Matrix((e1, e2, e1.cross(e2))).transposed()   # columnas = e1, e2, e3

    pb = arm.pose.bones[bone]
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    m = (arm.matrix_world @ pb.matrix).to_3x3().inverted()
    src = frame((0.0, 1.0, 0.0), palm_local)
    dst = frame(m @ Vector(direction), m @ Vector(palm))
    pb.rotation_euler = (dst @ src.transposed()).to_euler('XYZ')
    bpy.context.view_layer.update()
    return tuple(pb.rotation_euler)


# Altura a la que hay que subir la articulacion de la cadera sobre `seat_anchor` (tope del
# asiento, z=0.47) para que el muslo apoye por su eje y no por su piel: ~medio grosor de muslo.
SEAT_LIFT = 0.07

# --- brazos: manos sobre el teclado del laptop (base en y=0.87..1.09, cara superior z=0.770).
# Direcciones del mundo usadas con aim():  brazo (+-0.06, 0.0, -0.998) = vertical, codo pegado
# al torso; antebrazo (-+0.13, 0.99, 0.02) = horizontal hacia adelante y algo hacia el centro;
# mano (-+0.05, 0.995, 0.0) = horizontal, apoyada sobre el teclado.
# Deja la muneca en (+-0.145, 0.84, 0.828): la palma queda sobre la cara superior del laptop
# y las yemas no alcanzan la tapa (borde inferior en y=1.068).
TYPING_HOME = {
    'upper_armL': deg(7.06, -2.58, 40.13), 'upper_armR': deg(6.63, 2.41, -39.90),
    'forearmL': deg(-47.18, 20.31, 44.60), 'forearmR': deg(-46.59, -20.32, -45.19),
    'handL': deg(4.60, 0.61, -15.17), 'handR': deg(4.09, -0.58, 16.23),
}

# --- pose sentada frente al teclado.
# Piernas por aim():  muslo (+-0.11, 0.985, -0.20) casi horizontal y 11 grados hacia abajo,
# tibia (+-0.06, -0.02, -1.0) vertical, pie (+-0.06, 0.72, -0.69) = plano en el piso.
SIT = {
    'thighL': deg(-76.03, 1.75, 2.24), 'thighR': deg(-76.22, -1.35, -1.72),
    'shinL': deg(64.94, -3.41, 5.36), 'shinR': deg(65.44, 3.39, -5.27),
    'footL': deg(12.20, 0.09, -0.85), 'footR': deg(12.74, -0.01, 0.10),
    # torso: 12 grados de inclinacion repartidos (spine003 es el mas bajo en este rig,
    # spine001 el mas alto: el importador invirtio la numeracion respecto a Rigify).
    'spine003': rot('spine003', 6), 'spine002': rot('spine002', 4), 'spine001': rot('spine001', 2),
    # cuello adelante y cabeza levantada: la mirada queda ~8 grados bajo la horizontal,
    # apuntando a los monitores (y=1.45, z~0.96) y dejando la cara visible.
    'spine005': rot('spine005', 4), 'spine006': rot('spine006', -8),
}
SIT.update(TYPING_HOME)
for f in ('thumb', 'f_index', 'f_middle', 'f_ring', 'f_pinky'):
    for i in (1, 2, 3):
        for s in 'LR':
            SIT[f'{f}0{i}{s}'] = finger_rot(18 if f != 'thumb' else 8)


def apply(arm, pose, frame=None, loc=None):
    """Asigna eulers (y opcionalmente traslaciones locales `loc={hueso: (x,y,z)}`); keyframea si `frame`."""
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
    for name, e in pose.items():
        pb = arm.pose.bones.get(name)
        if not pb: continue
        pb.rotation_euler = e
        if frame is not None:
            pb.keyframe_insert('rotation_euler', frame=frame)
    for name, l in (loc or {}).items():
        pb = arm.pose.bones.get(name)
        if not pb: continue
        pb.location = l
        if frame is not None:
            pb.keyframe_insert('location', frame=frame)


# --- audifonos (hueso 'headphones', hijo de spine006; reposo = colgando del cuello).
# Estado "puestos": lo escribe add_headphones.py en blender/headphones.json (rotacion en grados
# y traslacion en espacio local del hueso). Se carga perezosamente para que poses.py siga
# importable antes de que exista el archivo.
import json as _json, os as _os
_HP_JSON = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'headphones.json')


def headphones_on():
    """(euler_rad, location_local) del estado 'puestos'; None si aun no existe headphones.json."""
    if not _os.path.exists(_HP_JSON):
        return None
    with open(_HP_JSON) as f:
        d = _json.load(f)['on_head']
    return (tuple(math.radians(v) for v in d['rotation_deg']), tuple(d['location']))
