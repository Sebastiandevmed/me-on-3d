# blender/scripts/render_hdr.py
# Renderiza un HDR equirectangular nocturno (1024x512, Cycles 16 samples) en export/night.hdr:
# cielo casi negro con un gradiente sutil, luces de ciudad naranjas en el horizonte,
# un plano emisivo azul (las pantallas) delante y dos barras RGB. Se usa como mundo
# del render de aprobacion (assemble.py) y como environment del visor web.
# Uso: tools/run_blender.sh - blender/scripts/render_hdr.py
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
common.ensure_dirs(); common.reset_scene()
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.samples = 16
sc.render.resolution_x, sc.render.resolution_y = 1024, 512
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'HDR'
w = bpy.data.worlds.new('Night'); sc.world = w; w.use_nodes = True
nt = w.node_tree; bg = nt.nodes['Background']
grad = nt.nodes.new('ShaderNodeTexGradient'); grad.gradient_type = 'LINEAR'
map_ = nt.nodes.new('ShaderNodeMapping'); tc = nt.nodes.new('ShaderNodeTexCoord')
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.004, 0.006, 0.02, 1)
ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1)
map_.inputs['Rotation'].default_value = (0, math.radians(-90), 0)
nt.links.new(tc.outputs['Generated'], map_.inputs['Vector']); nt.links.new(map_.outputs['Vector'], grad.inputs['Vector'])
nt.links.new(grad.outputs['Fac'], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 1.0
# luces de ciudad y pantallas como planos emisivos alrededor
m_city = common.mat('CityGlow', (0, 0, 0, 1), emission=(1.0, 0.7, 0.4, 1), emission_strength=4)
m_screen = common.mat('ScreenGlow', (0, 0, 0, 1), emission=(0.6, 0.75, 1.0, 1), emission_strength=8)
m_rgb = common.mat('RGBGlow', (0, 0, 0, 1), emission=(0.25, 0.55, 1.0, 1), emission_strength=10)
for i in range(24):
    a = i / 24 * 2 * math.pi
    common.box(f'city{i}', (0.2, 0.2, 0.05), (6 * math.cos(a), 6 * math.sin(a), -0.3 + 0.2 * math.sin(i)), m_city)
common.plane('screens', (3, 1.2), (0, 3, 1.0), rotation=(math.radians(90), 0, 0), material=m_screen)
common.box('rgbL', (0.1, 0.1, 2), (-3, 3, 1), m_rgb); common.box('rgbR', (0.1, 0.1, 2), (3, 3, 1), m_rgb)
cam = bpy.data.cameras.new('Pano'); cam.type = 'PANO'
try: cam.panorama_type = 'EQUIRECTANGULAR'
except Exception: cam.cycles.panorama_type = 'EQUIRECTANGULAR'
ob = bpy.data.objects.new('Pano', cam); sc.collection.objects.link(ob)
ob.location = (0, 0, 1.2); ob.rotation_euler = (math.radians(90), 0, 0); sc.camera = ob
sc.render.filepath = os.path.join(common.EXPORT, 'night.hdr')
bpy.ops.render.render(write_still=True)
print('HDR', sc.render.filepath, os.path.getsize(sc.render.filepath))
