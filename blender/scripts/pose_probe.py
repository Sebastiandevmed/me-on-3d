# blender/scripts/pose_probe.py
# Renderiza 12 imagenes: +60 grados en X, Y, Z para thighL, upper_armL, spine006 y forearmL.
# Sirve para leer, por hueso, que eje/signo lo dobla hacia adelante (+Y), hacia afuera y de giro.
# Uso: tools/run_blender.sh blender/character.blend blender/scripts/pose_probe.py
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
arm = bpy.data.objects['Armature']
common.add_camera((2.6, -2.6, 1.2), (0, 0, 0.9), lens=45)
common.add_light('k', 'AREA', (1.5, -2, 2.5), 300, size=1.5)
for bone in ('thighL', 'upper_armL', 'spine006', 'forearmL'):
    for axis_i, axis in enumerate('XYZ'):
        for pb in arm.pose.bones:
            pb.rotation_mode = 'XYZ'; pb.rotation_euler = (0, 0, 0)
        pb = arm.pose.bones[bone]
        e = [0, 0, 0]; e[axis_i] = math.radians(60)
        pb.rotation_euler = e
        common.render(os.path.join(common.RENDERS, f'probe_{bone}_{axis}.png'), res=(480, 640), samples=8)
for pb in arm.pose.bones: pb.rotation_euler = (0, 0, 0)
