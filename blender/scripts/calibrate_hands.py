# blender/scripts/calibrate_hands.py
# Recalcula los eulers de brazos de poses.TYPING_HOME y los imprime listos para pegar.
#
# Por que hace falta: TYPING_HOME esta HORNEADO en poses.py (son eulers explicitos, porque
# los huesos del brazo tienen ejes locales a ~45 grados del plano sagital y `rot()` no sirve).
# Se generaron en su dia con `poses.aim()`, que fija a donde apunta el hueso pero deja el giro
# sobre su propio eje al azar: las manos quedaron VERTICALES, palma contra palma, en vez de
# apoyadas sobre el teclado. Ahora se resuelven con `poses.aim_palm()`, que ademas apunta la
# palma y reparte la torsion entre antebrazo (pronacion) y muneca.
#
# El guardia `check_sit_arms()` de animate.py compara solve_arms() contra poses.SIT, asi que
# las direcciones de aqui tienen que ser LAS MISMAS que las de animate.py (se importan de ahi
# no se puede: animate.py construye todos los clips al importarse). Estan duplicadas a
# proposito y el guardia es justamente quien detecta si se desincronizan.
#
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/calibrate_hands.py
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common, poses

SX = {'L': 1.0, 'R': -1.0}
DIR_UPPER = lambda s: (-SX[s] * 0.06, 0.0, -0.998)
DIR_FORE = lambda s: (SX[s] * 0.13, 0.99, 0.02)
DIR_HAND = lambda s: (SX[s] * 0.05, 0.995, 0.0)
DIR_PALM = lambda s: (SX[s] * 0.15, -0.05, -0.985)

ORDER = ('upper_armL', 'upper_armR', 'forearmL', 'forearmR', 'handL', 'handR')


def main():
    arm = bpy.data.objects.get('Armature')
    if arm is None:
        common.fail('falta Armature: abrir blender/character.blend')

    poses.apply(arm, poses.SIT)
    bpy.context.view_layer.update()
    out = {}
    for s in 'LR':
        out[f'upper_arm{s}'] = poses.aim(arm, f'upper_arm{s}', DIR_UPPER(s))
        out.update(poses.aim_palm(arm, s, DIR_FORE(s), DIR_HAND(s), DIR_PALM(s)))

    # Comprobacion: la palma tiene que acabar mirando a donde se pidio.
    from mathutils import Vector
    for s in 'LR':
        m = (arm.matrix_world @ arm.pose.bones[f'hand{s}'].matrix).to_3x3()
        palm = (m @ Vector(poses.PALM_LOCAL[s])).normalized()
        want = Vector(DIR_PALM(s)).normalized()
        err = math.degrees(palm.angle(want))
        print(f'PALMA {s} -> {tuple(round(v, 3) for v in palm)}  error {err:.2f} grados')
        # 8 grados de tolerancia: `aim_roll` ortogonaliza y manda la direccion del hueso, y
        # ni PALM_LOCAL (-0.750, -0.120, 0.650) ni DIR_PALM son exactamente perpendiculares a
        # DIR_HAND, asi que un residuo de ~4-5 grados es inevitable. El sintoma que esto
        # tiene que cazar es la palma vertical, que son ~80-90 grados.
        if err > 8.0:
            common.fail(f'la palma {s} quedo a {err:.1f} grados de la direccion pedida')
        # Cuanta torsion se queda en la muneca (el resto se la lleva el antebrazo).
        print(f'MUNECA {s} euler_deg {tuple(round(math.degrees(v), 2) for v in out[f"hand{s}"])}')

    print('\n--- pegar en poses.py (TYPING_HOME) ---')
    for i in range(0, len(ORDER), 2):
        a, b = ORDER[i], ORDER[i + 1]
        f = lambda n: 'deg(%s)' % ', '.join(f'{math.degrees(v):.2f}' for v in out[n])
        print(f"    '{a}': {f(a)}, '{b}': {f(b)},")
    print('--- fin ---')


main()
